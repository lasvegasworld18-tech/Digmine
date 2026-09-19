"""Core API regression for strategy editor, rewards metadata, and contest entry/leaderboard."""

import os
import uuid

import pytest
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")


@pytest.fixture(scope="session")
def api_base_url():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is missing; skipping API tests.")
    return BASE_URL.rstrip("/") + "/api"


@pytest.fixture
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


def create_session(api_client: requests.Session, api_base_url: str) -> str:
    response = api_client.post(f"{api_base_url}/session", timeout=15)
    assert response.status_code == 200
    token = response.json().get("token")
    assert isinstance(token, str) and len(token) > 10
    return token


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def create_agent(
    api_client: requests.Session,
    api_base_url: str,
    token: str,
    *,
    name: str,
    strategy_preset: str = "balanced",
):
    payload = {
        "name": name,
        "avatar": "brass",
        "preference": "balanced",
        "strategy_preset": strategy_preset,
    }
    return api_client.post(
        f"{api_base_url}/agent",
        headers=auth_headers(token),
        json=payload,
        timeout=20,
    )


def get_me(api_client: requests.Session, api_base_url: str, token: str):
    return api_client.get(f"{api_base_url}/agent", headers=auth_headers(token), timeout=15)


class TestRewardsAndClaims:
    """Rewards metadata contract and claim lock behavior."""

    def test_rewards_metadata_matches_solana_stonk_requirements(self, api_client, api_base_url):
        response = api_client.get(f"{api_base_url}/rewards", timeout=15)
        assert response.status_code == 200
        data = response.json()
        assert data["network"] == "Solana"
        assert data["platform"] == "Stonk.fun"
        assert data["distribution_basis"] == "pro_rata_holdings"
        assert data["agent_required"] is False
        assert data["contest_affects_holder_share"] is False
        assert data["period_hours"] is None
        assert "finances" in data and data["finances"] is None

    def test_reward_claim_stays_conflict(self, api_client, api_base_url):
        response = api_client.post(f"{api_base_url}/rewards/claim", timeout=15)
        assert response.status_code == 409
        detail = response.json().get("detail", "")
        assert "not available" in detail.lower()


class TestStrategyAccessValidationAndPrivacy:
    """Preset discovery, strategy ownership/auth, save validation, stale version, and privacy boundaries."""

    def test_strategy_presets_public_contains_expected_ids(self, api_client, api_base_url):
        response = api_client.get(f"{api_base_url}/strategy/presets", timeout=15)
        assert response.status_code == 200
        presets = response.json()
        ids = {item["id"] for item in presets}
        assert {"balanced", "prospector", "guardian", "hauler"}.issubset(ids)

    def test_agent_strategy_requires_auth(self, api_client, api_base_url):
        response = api_client.get(f"{api_base_url}/agent/strategy", timeout=15)
        assert response.status_code == 401

    def test_agent_strategy_requires_existing_agent(self, api_client, api_base_url):
        token = create_session(api_client, api_base_url)
        response = api_client.get(f"{api_base_url}/agent/strategy", headers=auth_headers(token), timeout=15)
        assert response.status_code == 404

    def test_strategy_save_version_conflict_and_history_increment(self, api_client, api_base_url):
        token = create_session(api_client, api_base_url)
        created = create_agent(api_client, api_base_url, token, name=f"TEST Strategy {uuid.uuid4().hex[:6]}")
        assert created.status_code == 201

        current = api_client.get(f"{api_base_url}/agent/strategy", headers=auth_headers(token), timeout=15)
        assert current.status_code == 200
        current_data = current.json()
        version = current_data["version"]
        strategy = current_data["strategy"]

        strategy["name"] = "TEST Strategy Updated"
        save = api_client.post(
            f"{api_base_url}/agent/strategy",
            headers=auth_headers(token),
            json={"expected_version": version, "strategy": strategy},
            timeout=20,
        )
        assert save.status_code == 200
        saved_data = save.json()
        assert saved_data["version"] == version + 1
        assert saved_data["strategy"]["name"] == "TEST Strategy Updated"
        assert len(saved_data["history"]) >= 1
        assert saved_data["history"][0]["version"] == version + 1

        stale = api_client.post(
            f"{api_base_url}/agent/strategy",
            headers=auth_headers(token),
            json={"expected_version": version, "strategy": strategy},
            timeout=20,
        )
        assert stale.status_code == 409

    def test_strategy_rejects_invalid_types_and_duplicate_rule_ids(self, api_client, api_base_url):
        token = create_session(api_client, api_base_url)
        created = create_agent(api_client, api_base_url, token, name=f"TEST Validate {uuid.uuid4().hex[:6]}")
        assert created.status_code == 201

        current = api_client.get(f"{api_base_url}/agent/strategy", headers=auth_headers(token), timeout=15)
        assert current.status_code == 200
        payload = current.json()

        bad_strategy = payload["strategy"]
        bad_strategy["target_depth"] = 3.5
        bad_strategy["rules"] = [
            {
                "id": "dup-rule",
                "name": "Rule A",
                "enabled": True,
                "match": "all",
                "groups": [{"match": "all", "conditions": [{"field": "energy", "operator": "lte", "value": 20}]}],
                "action": "rest",
            },
            {
                "id": "dup-rule",
                "name": "Rule B",
                "enabled": True,
                "match": "all",
                "groups": [{"match": "all", "conditions": [{"field": "depth", "operator": "gte", "value": 3}]}],
                "action": "mine",
            },
        ]
        response = api_client.post(
            f"{api_base_url}/agent/strategy",
            headers=auth_headers(token),
            json={"expected_version": payload["version"], "strategy": bad_strategy},
            timeout=20,
        )
        assert response.status_code == 422

    def test_world_and_leaderboard_do_not_expose_strategy_rules(self, api_client, api_base_url):
        world = api_client.get(f"{api_base_url}/world", timeout=15)
        assert world.status_code == 200
        world_data = world.json()
        if world_data["agents"]:
            assert "strategy" not in world_data["agents"][0]

        board = api_client.get(f"{api_base_url}/contest/leaderboard", timeout=15)
        assert board.status_code == 200
        board_data = board.json()
        if board_data["entries"]:
            first = board_data["entries"][0]
            assert "strategy" not in first
            assert "rules" not in first

    def test_create_agent_rejects_injected_score_fields(self, api_client, api_base_url):
        token = create_session(api_client, api_base_url)
        payload = {
            "name": f"TEST Inject {uuid.uuid4().hex[:6]}",
            "avatar": "brass",
            "preference": "balanced",
            "strategy_preset": "balanced",
            "score": 999999,
            "game": {"energy": 1},
        }
        response = api_client.post(
            f"{api_base_url}/agent",
            headers=auth_headers(token),
            json=payload,
            timeout=20,
        )
        assert response.status_code == 422


class TestEvaluationAndContestFlow:
    """Deterministic strategy evaluation and one-entry-per-season contest behavior."""

    def test_evaluate_is_deterministic_and_non_mutating(self, api_client, api_base_url):
        token = create_session(api_client, api_base_url)
        created = create_agent(api_client, api_base_url, token, name=f"TEST Eval {uuid.uuid4().hex[:6]}")
        assert created.status_code == 201

        strategy_resp = api_client.get(f"{api_base_url}/agent/strategy", headers=auth_headers(token), timeout=15)
        assert strategy_resp.status_code == 200
        strategy = strategy_resp.json()["strategy"]

        me_before = get_me(api_client, api_base_url, token)
        assert me_before.status_code == 200
        before = me_before.json()["agent"]

        first = api_client.post(
            f"{api_base_url}/agent/strategy/evaluate",
            headers=auth_headers(token),
            json={"strategy": strategy, "decisions": 120},
            timeout=20,
        )
        second = api_client.post(
            f"{api_base_url}/agent/strategy/evaluate",
            headers=auth_headers(token),
            json={"strategy": strategy, "decisions": 120},
            timeout=20,
        )
        assert first.status_code == 200
        assert second.status_code == 200
        first_data, second_data = first.json(), second.json()
        assert first_data["score"] == second_data["score"]
        assert first_data["delivered"] == second_data["delivered"]
        assert first_data["trace"] == second_data["trace"]
        assert first_data["decisions"] == 120

        me_after = get_me(api_client, api_base_url, token)
        assert me_after.status_code == 200
        after = me_after.json()["agent"]
        assert after["ore"] == before["ore"]
        assert after["step"] == before["step"]
        assert after["game"]["decision"] == before["game"]["decision"]

    def test_evaluate_enforces_safety_overrides(self, api_client, api_base_url):
        token = create_session(api_client, api_base_url)
        created = create_agent(api_client, api_base_url, token, name=f"TEST Override {uuid.uuid4().hex[:6]}")
        assert created.status_code == 201

        strategy_resp = api_client.get(f"{api_base_url}/agent/strategy", headers=auth_headers(token), timeout=15)
        assert strategy_resp.status_code == 200
        strategy = strategy_resp.json()["strategy"]
        strategy["rules"] = [
            {
                "id": "force-mine",
                "name": "Force mine",
                "enabled": True,
                "match": "all",
                "groups": [{"match": "all", "conditions": [{"field": "energy", "operator": "lte", "value": 100}]}],
                "action": "mine",
            }
        ]

        result = api_client.post(
            f"{api_base_url}/agent/strategy/evaluate",
            headers=auth_headers(token),
            json={"strategy": strategy, "decisions": 300},
            timeout=20,
        )
        assert result.status_code == 200
        trace = result.json()["trace"]
        reasons = " ".join(item["reason"] for item in trace)
        assert "Safety override" in reasons or "Delivery commitment" in reasons

    def test_contest_enter_once_and_leaderboard_excludes_bots(self, api_client, api_base_url):
        token = create_session(api_client, api_base_url)
        created = create_agent(api_client, api_base_url, token, name=f"TEST Contest {uuid.uuid4().hex[:6]}")
        assert created.status_code == 201
        before = created.json()

        enter = api_client.post(f"{api_base_url}/contest/enter", headers=auth_headers(token), timeout=20)
        assert enter.status_code == 200
        entered = enter.json()
        assert entered["status"] == "active"
        assert entered["contest"]["actions_used"] == 0
        assert entered["contest"]["score"] == 0
        assert entered["game"]["energy"] == 100
        assert entered["game"]["tool"] == 100
        assert entered["game"]["cargo"] == 0
        assert entered["game"]["depth"] == 1
        assert entered["ore"] == before["ore"]

        second = api_client.post(f"{api_base_url}/contest/enter", headers=auth_headers(token), timeout=20)
        assert second.status_code == 409

        board = api_client.get(f"{api_base_url}/contest/leaderboard", timeout=20)
        assert board.status_code == 200
        entries = board.json()["entries"]
        assert all(not row["agent_id"].startswith("crew-") for row in entries)

    def test_evaluate_rejects_out_of_range_decisions(self, api_client, api_base_url):
        token = create_session(api_client, api_base_url)
        created = create_agent(api_client, api_base_url, token, name=f"TEST Decisions {uuid.uuid4().hex[:6]}")
        assert created.status_code == 201

        strategy_resp = api_client.get(f"{api_base_url}/agent/strategy", headers=auth_headers(token), timeout=15)
        assert strategy_resp.status_code == 200
        strategy = strategy_resp.json()["strategy"]

        response = api_client.post(
            f"{api_base_url}/agent/strategy/evaluate",
            headers=auth_headers(token),
            json={"strategy": strategy, "decisions": 10},
            timeout=20,
        )
        assert response.status_code == 422


class TestPresetCreationCoverage:
    """Agent creation across all strategy presets for regression coverage."""

    @pytest.mark.parametrize("preset_key", ["balanced", "prospector", "guardian", "hauler"])
    def test_create_agent_with_each_strategy_preset(self, api_client, api_base_url, preset_key):
        token = create_session(api_client, api_base_url)
        name = f"TEST {preset_key[:4]} {uuid.uuid4().hex[:5]}"
        created = create_agent(
            api_client,
            api_base_url,
            token,
            name=name,
            strategy_preset=preset_key,
        )
        assert created.status_code == 201
        agent = created.json()
        assert agent["name"] == name
        assert agent["strategy_version"] == 1
        assert isinstance(agent["strategy_name"], str) and len(agent["strategy_name"]) >= 2
