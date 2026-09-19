"""Targeted engine edge coverage: contest budget/expiry, strategy semantics, and leaderboard ordering."""

import asyncio
import os
import sys
import uuid
from pathlib import Path

import pytest
import requests
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import game_worker
import strategy_routes
from contest_logic import leaderboard
from engine import make_agent
from game_worker import advance_game
from strategies import choose, evaluate, preset, score, step
from strategy_models import GameState


PUBLIC_BASE_URL = os.environ["REACT_APP_BACKEND_URL"]

_LOOP = None


def run(coro):
    global _LOOP
    if _LOOP is None or _LOOP.is_closed():
        _LOOP = asyncio.new_event_loop()
        asyncio.set_event_loop(_LOOP)
    return _LOOP.run_until_complete(coro)


@pytest.fixture
def edge_db():
    """Use a dedicated temporary Mongo DB for isolated edge-case tests."""
    mongo_url = os.environ.get("MONGO_URL")
    if not mongo_url:
        pytest.skip("MONGO_URL is missing; skipping edge engine tests.")

    run(asyncio.sleep(0))
    client = AsyncIOMotorClient(mongo_url, io_loop=_LOOP)
    db_name = f"test_edge_{uuid.uuid4().hex[:10]}"
    db = client[db_name]

    run(db.agents.create_index("id", unique=True))
    run(db.events.create_index("id", unique=True))
    run(db.contest_archive.create_index("id", unique=True))
    run(db.contest_archive.create_index("season_id"))
    run(db.strategy_history.create_index("id", unique=True))

    try:
        yield db
    finally:
        run(client.drop_database(db_name))
        client.close()


def _contest(season_id: str, ends_at: float, entered_at: str = "2026-02-02T00:00:00+00:00"):
    return {
        "season_id": season_id,
        "entered_at": entered_at,
        "entered_ts": ends_at - 3600,
        "ends_at": ends_at,
        "status": "active",
        "actions_used": 0,
        "score": 0,
        "delivered": 0,
        "banked_points": 0,
        "exploration_points": 0,
        "penalties": 0,
        "incidents": 0,
        "completed_at": None,
    }


def _agent_doc(agent_id: str, *, owner: str | None = None):
    agent = make_agent(agent_id, f"TEST_EDGE_{agent_id[-4:]}", "brass", "balanced", "Curious", is_bot=False)
    if owner:
        agent["owner"] = owner
    return agent


def test_rewards_public_contract_has_finances_key():
    """Single public assertion requested: rewards payload exposes finances key."""
    response = requests.get(f"{PUBLIC_BASE_URL}/api/rewards", timeout=20)
    assert response.status_code == 200
    payload = response.json()
    assert "finances" in payload


def test_exactly_600_actions_freeze_contest_but_mining_continues_without_duplication(edge_db, monkeypatch):
    """600 cap freezes contest scoring; same target idempotent; mining still advances post-cap."""
    now_ref = {"t": 2_000_000_000.0}
    monkeypatch.setattr(game_worker.time, "time", lambda: now_ref["t"])

    agent = _agent_doc("edge-600")
    agent.update(
        {
            "status": "active",
            "started_at": now_ref["t"] - (620 * 18),
            "elapsed_before": 0.0,
            "step": 0,
            "decision_cursor": 0,
            "contest": _contest("2026-02-02", now_ref["t"] + 10_000),
        }
    )
    run(edge_db.agents.insert_one(agent))

    run(advance_game(edge_db, agent))
    first = run(edge_db.agents.find_one({"id": "edge-600"}, {"_id": 0}))
    assert first["decision_cursor"] == 620
    assert first["contest"]["actions_used"] == 600
    assert first["contest"]["status"] == "completed"

    events_before = run(edge_db.events.count_documents({"agent_id": "edge-600"}))
    first_ore = first["ore"]
    first_contest = first["contest"].copy()

    run(advance_game(edge_db, first))
    second = run(edge_db.agents.find_one({"id": "edge-600"}, {"_id": 0}))
    events_after_same_target = run(edge_db.events.count_documents({"agent_id": "edge-600"}))

    assert second["ore"] == first_ore
    assert second["contest"] == first_contest
    assert events_after_same_target == events_before

    now_ref["t"] += 10 * 18
    run(advance_game(edge_db, second))
    third = run(edge_db.agents.find_one({"id": "edge-600"}, {"_id": 0}))
    assert third["decision_cursor"] == 630
    assert third["ore"] >= first_ore
    assert third["contest"] == first_contest


def test_strategy_save_keeps_earned_totals_and_changed_rules_affect_future_decisions(edge_db, monkeypatch):
    """Edited strategy retains earned progress and applies changed rule on future decision."""
    now_ref = {"t": 2_100_000_000.0}
    monkeypatch.setattr(game_worker.time, "time", lambda: now_ref["t"])
    monkeypatch.setattr(strategy_routes.time, "time", lambda: now_ref["t"])

    owner_id = "owner-edge-1"
    agent = _agent_doc("edge-save", owner=owner_id)
    agent.update(
        {
            "status": "active",
            "started_at": now_ref["t"] - (120 * 18),
            "elapsed_before": 0.0,
            "step": 0,
            "decision_cursor": 0,
            "contest": _contest("2026-02-02", now_ref["t"] + 50_000),
        }
    )
    run(edge_db.agents.insert_one(agent))

    run(advance_game(edge_db, agent))
    before_save = run(edge_db.agents.find_one({"id": "edge-save"}, {"_id": 0}))

    async def fake_owner(_: str | None):
        return owner_id

    app = FastAPI()
    app.include_router(strategy_routes.make_strategy_router(edge_db, fake_owner))

    edited = before_save["strategy"].copy()
    edited["name"] = "TEST_EDGE_ALWAYS_SURVEY"
    edited["rules"] = [
        {
            "id": "always-survey",
            "name": "Always Survey",
            "enabled": True,
            "match": "all",
            "groups": [
                {
                    "match": "all",
                    "conditions": [{"field": "quality", "operator": "lte", "value": 100}],
                }
            ],
            "action": "survey",
        }
    ]

    async def save_request():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            return await ac.post(
                "/api/agent/strategy",
                headers={"Authorization": "Bearer edge-token"},
                json={"expected_version": before_save["strategy_version"], "strategy": edited},
            )

    save = run(save_request())
    assert save.status_code == 200

    after_save = run(edge_db.agents.find_one({"id": "edge-save"}, {"_id": 0}))
    assert after_save["contest"]["score"] == before_save["contest"]["score"]
    assert after_save["contest"]["delivered"] == before_save["contest"]["delivered"]
    assert after_save["contest"]["actions_used"] == before_save["contest"]["actions_used"]
    assert after_save["ore"] == before_save["ore"]
    assert after_save["game"]["mined"] == before_save["game"]["mined"]

    run(
        edge_db.agents.update_one(
            {"id": "edge-save"},
            {
                "$set": {
                    "game.energy": 70,
                    "game.tool": 70,
                    "game.cargo": 0,
                    "game.returning": False,
                    "game.quality": 60,
                }
            },
        )
    )
    now_ref["t"] += 18
    run(advance_game(edge_db, after_save))
    after_tick = run(edge_db.agents.find_one({"id": "edge-save"}, {"_id": 0}))
    assert after_tick["game"]["last_action"] == "survey"
    assert after_tick["game"]["last_reason"] == "Rule: Always Survey"


def test_expired_contest_closes_for_paused_and_active_without_new_due_tick(edge_db, monkeypatch):
    """Contest closes at ends_at for paused and active agents with no new due decision."""
    now_ref = {"t": 2_200_000_000.0}
    monkeypatch.setattr(game_worker.time, "time", lambda: now_ref["t"])

    paused = _agent_doc("edge-paused")
    paused.update(
        {
            "status": "paused",
            "decision_cursor": 10,
            "step": 10,
            "contest": _contest("2026-02-02", now_ref["t"] - 1),
        }
    )

    active = _agent_doc("edge-active")
    active.update(
        {
            "status": "active",
            "elapsed_before": 180.0,
            "started_at": now_ref["t"],
            "decision_cursor": 10,
            "step": 10,
            "contest": _contest("2026-02-02", now_ref["t"] - 2),
        }
    )

    run(edge_db.agents.insert_many([paused, active]))
    run(advance_game(edge_db, paused))
    run(advance_game(edge_db, active))

    paused_after = run(edge_db.agents.find_one({"id": "edge-paused"}, {"_id": 0}))
    active_after = run(edge_db.agents.find_one({"id": "edge-active"}, {"_id": 0}))
    assert paused_after["contest"]["status"] == "closed"
    assert active_after["contest"]["status"] == "closed"


def test_reentry_conflict_then_new_season_entry_archives_previous_and_preserves_lifetime(edge_db, monkeypatch):
    """Same-season reentry=409; new season entry archives previous result and keeps lifetime totals."""
    now_ref = {"t": 2_300_000_000.0}
    monkeypatch.setattr(game_worker.time, "time", lambda: now_ref["t"])
    monkeypatch.setattr(strategy_routes.time, "time", lambda: now_ref["t"])

    owner_id = "owner-edge-2"
    season_a = {
        "id": "2026-02-02",
        "name": "Brass Hollow Open",
        "starts_at": "2026-02-02T00:00:00+00:00",
        "ends_at": "2026-02-09T00:00:00+00:00",
        "ends_ts": now_ref["t"] + 86_400,
        "action_budget": 600,
        "decision_seconds": 18,
        "prize_status": "to_be_announced",
        "prize_amount": None,
        "prize_asset": None,
        "funding_source": "Separate project or sponsor pool",
        "holder_pool_used": False,
        "wallet_verification_required_for_prizes": True,
        "rules_version": "brass-hollow-v1",
    }
    season_b = {
        **season_a,
        "id": "2026-02-09",
        "starts_at": "2026-02-09T00:00:00+00:00",
        "ends_at": "2026-02-16T00:00:00+00:00",
    }

    season_ref = {"season": season_a}
    monkeypatch.setattr(strategy_routes, "season_info", lambda now=None: season_ref["season"])

    agent = _agent_doc("edge-reentry", owner=owner_id)
    agent.update(
        {
            "status": "paused",
            "ore": 321,
            "expeditions": 11,
            "discoveries": ["pyrite", "quartz", "azurite"],
            "contest": {
                "season_id": season_a["id"],
                "entered_at": "2026-02-02T05:00:00+00:00",
                "entered_ts": now_ref["t"] - 50_000,
                "ends_at": now_ref["t"] + 1000,
                "status": "completed",
                "actions_used": 600,
                "score": 777,
                "delivered": 456,
                "banked_points": 700,
                "exploration_points": 102,
                "penalties": 25,
                "incidents": 1,
                "completed_at": "2026-02-07T12:00:00+00:00",
            },
        }
    )
    run(edge_db.agents.insert_one(agent))

    async def fake_owner(_: str | None):
        return owner_id

    app = FastAPI()
    app.include_router(strategy_routes.make_strategy_router(edge_db, fake_owner))

    async def call_enter():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            return await ac.post("/api/contest/enter", headers={"Authorization": "Bearer edge-token"})

    same_season = run(call_enter())
    assert same_season.status_code == 409

    season_ref["season"] = season_b
    new_season = run(call_enter())
    assert new_season.status_code == 200
    entered = new_season.json()

    assert entered["ore"] == 321
    assert entered["expeditions"] == 11
    assert entered["discoveries"] == ["pyrite", "quartz", "azurite"]
    assert entered["contest"]["season_id"] == "2026-02-09"
    assert entered["contest"]["score"] == 0
    assert entered["contest"]["actions_used"] == 0

    archived = run(edge_db.contest_archive.find_one({"id": "edge-reentry:2026-02-02"}, {"_id": 0}))
    assert archived is not None
    assert archived["score"] == 777
    assert archived["delivered"] == 456


def test_leaderboard_tie_ordering_score_delivered_actions_then_entry_time(edge_db):
    """Tie order: score desc, delivered desc, fewer actions, earlier entry time."""
    season = "2026-02-02"
    rows = [
        {
            "id": "tie-a",
            "name": "A",
            "avatar": "brass",
            "is_bot": False,
            "contest": {
                "season_id": season,
                "entered_at": "2026-02-02T03:00:00+00:00",
                "entered_ts": 3,
                "ends_at": 9_999_999,
                "status": "active",
                "actions_used": 12,
                "score": 100,
                "delivered": 50,
                "banked_points": 0,
                "exploration_points": 0,
                "penalties": 0,
                "incidents": 0,
                "completed_at": None,
            },
        },
        {
            "id": "tie-b",
            "name": "B",
            "avatar": "brass",
            "is_bot": False,
            "contest": {
                "season_id": season,
                "entered_at": "2026-02-02T02:00:00+00:00",
                "entered_ts": 2,
                "ends_at": 9_999_999,
                "status": "active",
                "actions_used": 11,
                "score": 100,
                "delivered": 50,
                "banked_points": 0,
                "exploration_points": 0,
                "penalties": 0,
                "incidents": 0,
                "completed_at": None,
            },
        },
        {
            "id": "tie-c",
            "name": "C",
            "avatar": "brass",
            "is_bot": False,
            "contest": {
                "season_id": season,
                "entered_at": "2026-02-02T01:00:00+00:00",
                "entered_ts": 1,
                "ends_at": 9_999_999,
                "status": "active",
                "actions_used": 99,
                "score": 100,
                "delivered": 51,
                "banked_points": 0,
                "exploration_points": 0,
                "penalties": 0,
                "incidents": 0,
                "completed_at": None,
            },
        },
    ]
    run(edge_db.agents.insert_many(rows))
    ordered, _ = run(leaderboard(edge_db, season, limit=10))
    assert [item.agent_id for item in ordered[:3]] == ["tie-c", "tie-b", "tie-a"]


def test_nested_groups_first_match_enabled_false_safety_and_no_point_farming():
    """Rule semantics: nested ANY/ALL, first-match, disabled ignored, safety precedence, anti-farm."""
    state = GameState().model_dump()
    config = preset("balanced")
    config["rules"] = [
        {
            "id": "disabled-first",
            "name": "Disabled First",
            "enabled": False,
            "match": "all",
            "groups": [{"match": "all", "conditions": [{"field": "energy", "operator": "lte", "value": 100}]}],
            "action": "mine",
        },
        {
            "id": "nested-first",
            "name": "Nested First",
            "enabled": True,
            "match": "any",
            "groups": [
                {
                    "match": "all",
                    "conditions": [
                        {"field": "energy", "operator": "lte", "value": 50},
                        {"field": "tool", "operator": "lte", "value": 20},
                    ],
                },
                {
                    "match": "any",
                    "conditions": [
                        {"field": "quality", "operator": "gte", "value": 50},
                        {"field": "depth", "operator": "eq", "value": 3},
                    ],
                },
            ],
            "action": "survey",
        },
        {
            "id": "later-match",
            "name": "Later Match",
            "enabled": True,
            "match": "all",
            "groups": [{"match": "all", "conditions": [{"field": "energy", "operator": "lte", "value": 100}]}],
            "action": "rest",
        },
    ]

    action, reason = choose(config, state)
    assert action == "survey"
    assert reason == "Rule: Nested First"

    low_state = {**state, "energy": 5}
    forced_mine = {
        **config,
        "rules": [
            {
                "id": "force-mine",
                "name": "Force Mine",
                "enabled": True,
                "match": "all",
                "groups": [{"match": "all", "conditions": [{"field": "energy", "operator": "lte", "value": 100}]}],
                "action": "mine",
            }
        ],
    }
    action2, reason2 = choose(forced_mine, low_state)
    assert action2 == "rest"
    assert "Safety override" in reason2

    return_rule = {
        **preset("balanced"),
        "rules": [
            {
                "id": "return-empty",
                "name": "Return Empty",
                "enabled": True,
                "match": "all",
                "groups": [{"match": "all", "conditions": [{"field": "energy", "operator": "lte", "value": 100}]}],
                "action": "return",
            }
        ],
    }
    after, _, _ = step(return_rule, GameState().model_dump(), seed="edge-seed")
    assert after["last_action"] == "survey"
    assert score(after) == 0
    assert after["delivered"] == 0


def test_depth_milestone_not_farmable_and_preset_variants_diverge():
    """Depth milestone points should not re-award; preset variants should diverge."""
    deeper_cfg = {
        **preset("balanced"),
        "rules": [
            {
                "id": "always-deeper",
                "name": "Always Deeper",
                "enabled": True,
                "match": "all",
                "groups": [{"match": "all", "conditions": [{"field": "energy", "operator": "lte", "value": 100}]}],
                "action": "deeper",
            }
        ],
    }
    shallower_cfg = {
        **preset("balanced"),
        "rules": [
            {
                "id": "always-shallower",
                "name": "Always Shallower",
                "enabled": True,
                "match": "all",
                "groups": [{"match": "all", "conditions": [{"field": "energy", "operator": "lte", "value": 100}]}],
                "action": "shallower",
            }
        ],
    }

    state = GameState().model_dump()
    state, _, _ = step(deeper_cfg, state, seed="edge-depth")
    first_points = state["exploration_points"]
    assert state["depth"] == 2
    assert first_points == 10

    state, _, _ = step(shallower_cfg, state, seed="edge-depth")
    assert state["depth"] == 1

    state, _, _ = step(deeper_cfg, state, seed="edge-depth")
    assert state["depth"] == 2
    assert state["exploration_points"] == first_points

    balanced = evaluate(preset("balanced"), decisions=120)
    prospector = evaluate(preset("prospector"), decisions=120)
    guardian = evaluate(preset("guardian"), decisions=120)
    signatures = {
        (balanced["score"], balanced["delivered"], balanced["incidents"]),
        (prospector["score"], prospector["delivered"], prospector["incidents"]),
        (guardian["score"], guardian["delivered"], guardian["incidents"]),
    }
    assert len(signatures) >= 2
