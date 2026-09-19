"""API coverage for MINEPX public world, session auth, agent actions, journal, and rewards."""

import os
import time
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


def create_session(client: requests.Session, api_base: str) -> str:
    response = client.post(f"{api_base}/session", timeout=15)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data.get("token"), str)
    assert len(data["token"]) > 10
    return data["token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def create_agent(client: requests.Session, api_base: str, token: str, *, name: str, avatar: str = "brass", preference: str = "balanced"):
    return client.post(
        f"{api_base}/agent",
        headers=auth_headers(token),
        json={"name": name, "avatar": avatar, "preference": preference},
        timeout=20,
    )


class TestPublicEndpoints:
    """Public world, journal, and rewards behavior without leaking ownership fields."""

    def test_health_endpoint(self, api_client, api_base_url):
        response = api_client.get(f"{api_base_url}/health", timeout=15)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert isinstance(data["worker_online"], bool)

    def test_world_is_public_and_has_crew_bots(self, api_client, api_base_url):
        response = api_client.get(f"{api_base_url}/world", timeout=20)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["agents"], list)
        assert data["crew_bots"] >= 12
        assert data["active_agents"] >= 12
        assert data["crew_bots"] <= data["active_agents"]
        if data["agents"]:
            sample = data["agents"][0]
            assert "owner" not in sample
            assert "token" not in sample

    def test_journal_limit_and_filter(self, api_client, api_base_url):
        all_events = api_client.get(f"{api_base_url}/journal?limit=5", timeout=15)
        assert all_events.status_code == 200
        all_data = all_events.json()
        assert len(all_data) <= 5
        assert all("agent_id" in item for item in all_data)

        if all_data:
            agent_id = all_data[0]["agent_id"]
            filtered = api_client.get(f"{api_base_url}/journal?agent_id={agent_id}&limit=5", timeout=15)
            assert filtered.status_code == 200
            filtered_data = filtered.json()
            assert all(item["agent_id"] == agent_id for item in filtered_data)

    def test_rewards_status_and_claim_conflict(self, api_client, api_base_url):
        rewards = api_client.get(f"{api_base_url}/rewards", timeout=15)
        assert rewards.status_code == 200
        rewards_data = rewards.json()
        assert rewards_data["status"] == "awaiting_verification"
        assert rewards_data["network"] == "Solana"
        assert rewards_data["platform"] == "Stonk.fun"
        assert rewards_data["distribution_basis"] == "pro_rata_holdings"
        assert rewards_data["period_hours"] is None
        assert rewards_data["pool_balance"] is None
        assert rewards_data["fee_allocation"] is None

        claim = api_client.post(f"{api_base_url}/rewards/claim", timeout=15)
        assert claim.status_code == 409
        claim_data = claim.json()
        assert "not available" in claim_data["detail"].lower()


class TestSessionAndAgentAuth:
    """Session token enforcement, isolated ownership, and create validation."""

    def test_agent_requires_bearer(self, api_client, api_base_url):
        without_auth = api_client.get(f"{api_base_url}/agent", timeout=15)
        assert without_auth.status_code == 401

        invalid_auth = api_client.get(
            f"{api_base_url}/agent",
            headers={"Authorization": "Bearer invalid-token"},
            timeout=15,
        )
        assert invalid_auth.status_code == 401

    def test_create_agent_name_validation(self, api_client, api_base_url):
        token = create_session(api_client, api_base_url)

        invalid = create_agent(api_client, api_base_url, token, name="!!!")
        assert invalid.status_code == 422

        whitespace = create_agent(api_client, api_base_url, token, name="    ")
        assert whitespace.status_code == 422

        valid = create_agent(api_client, api_base_url, token, name="TEST-Agent_01")
        assert valid.status_code == 201
        created = valid.json()
        assert created["name"] == "TEST-Agent_01"
        assert created["avatar"] == "brass"
        assert created["preference"] == "balanced"
        assert created["status"] == "ready"
        assert created["is_bot"] is False

    def test_duplicate_agent_same_session_conflicts(self, api_client, api_base_url):
        token = create_session(api_client, api_base_url)
        first = create_agent(api_client, api_base_url, token, name=f"TEST Dup {uuid.uuid4().hex[:5]}")
        assert first.status_code == 201

        duplicate = create_agent(api_client, api_base_url, token, name=f"TEST Dup {uuid.uuid4().hex[:5]}")
        assert duplicate.status_code == 409

    def test_session_isolation_between_two_tokens(self, api_client, api_base_url):
        token_a = create_session(api_client, api_base_url)
        token_b = create_session(api_client, api_base_url)

        create_a = create_agent(api_client, api_base_url, token_a, name=f"TEST A {uuid.uuid4().hex[:5]}")
        assert create_a.status_code == 201
        agent_a_id = create_a.json()["id"]

        me_b_before = api_client.get(f"{api_base_url}/agent", headers=auth_headers(token_b), timeout=15)
        assert me_b_before.status_code == 200
        assert me_b_before.json()["agent"] is None

        create_b = create_agent(api_client, api_base_url, token_b, name=f"TEST B {uuid.uuid4().hex[:5]}")
        assert create_b.status_code == 201
        agent_b_id = create_b.json()["id"]
        assert agent_a_id != agent_b_id

        me_a = api_client.get(f"{api_base_url}/agent", headers=auth_headers(token_a), timeout=15)
        me_b = api_client.get(f"{api_base_url}/agent", headers=auth_headers(token_b), timeout=15)
        assert me_a.status_code == 200
        assert me_b.status_code == 200
        assert me_a.json()["agent"]["id"] == agent_a_id
        assert me_b.json()["agent"]["id"] == agent_b_id


class TestAgentProgressionAndPersistence:
    """Start/pause/resume and server-side progression behavior across elapsed time."""

    def test_start_pause_resume_flow(self, api_client, api_base_url):
        token = create_session(api_client, api_base_url)
        created = create_agent(api_client, api_base_url, token, name=f"TEST Flow {uuid.uuid4().hex[:6]}", preference="deep")
        assert created.status_code == 201

        start = api_client.post(
            f"{api_base_url}/agent/action",
            headers=auth_headers(token),
            json={"action": "start"},
            timeout=20,
        )
        assert start.status_code == 200
        started = start.json()
        assert started["status"] == "active"

        time.sleep(7)
        paused = api_client.post(
            f"{api_base_url}/agent/action",
            headers=auth_headers(token),
            json={"action": "pause"},
            timeout=20,
        )
        assert paused.status_code == 200
        paused_data = paused.json()
        assert paused_data["status"] == "paused"

        time.sleep(6)
        frozen = api_client.get(f"{api_base_url}/agent", headers=auth_headers(token), timeout=15)
        assert frozen.status_code == 200
        frozen_agent = frozen.json()["agent"]
        assert frozen_agent["status"] == "paused"
        assert frozen_agent["step"] == paused_data["step"]
        assert frozen_agent["ore"] == paused_data["ore"]

        resume = api_client.post(
            f"{api_base_url}/agent/action",
            headers=auth_headers(token),
            json={"action": "resume"},
            timeout=20,
        )
        assert resume.status_code == 200
        resumed = resume.json()
        assert resumed["status"] == "active"

    def test_progress_continues_when_unpolled(self, api_client, api_base_url):
        token = create_session(api_client, api_base_url)
        created = create_agent(api_client, api_base_url, token, name=f"TEST Persist {uuid.uuid4().hex[:6]}")
        assert created.status_code == 201

        start = api_client.post(
            f"{api_base_url}/agent/action",
            headers=auth_headers(token),
            json={"action": "start"},
            timeout=20,
        )
        assert start.status_code == 200

        before = api_client.get(f"{api_base_url}/agent", headers=auth_headers(token), timeout=15)
        assert before.status_code == 200
        before_agent = before.json()["agent"]

        time.sleep(22)

        after = api_client.get(f"{api_base_url}/agent", headers=auth_headers(token), timeout=15)
        assert after.status_code == 200
        after_agent = after.json()["agent"]
        assert after_agent["step"] >= before_agent["step"] + 1
        assert after_agent["ore"] >= before_agent["ore"]

    def test_cycle_unlocks_pyrite_and_event_ids_are_unique(self, api_client, api_base_url):
        token = create_session(api_client, api_base_url)
        created = create_agent(api_client, api_base_url, token, name=f"TEST Cycle {uuid.uuid4().hex[:6]}", preference="careful")
        assert created.status_code == 201
        agent_id = created.json()["id"]

        start = api_client.post(
            f"{api_base_url}/agent/action",
            headers=auth_headers(token),
            json={"action": "start"},
            timeout=20,
        )
        assert start.status_code == 200

        time.sleep(110)
        me = api_client.get(f"{api_base_url}/agent", headers=auth_headers(token), timeout=20)
        assert me.status_code == 200
        me_agent = me.json()["agent"]
        assert me_agent["step"] >= 5
        assert me_agent["ore"] >= 1
        assert me_agent["game"]["decision"] >= 5

        events = api_client.get(f"{api_base_url}/journal?agent_id={agent_id}&limit=100", timeout=20)
        assert events.status_code == 200
        event_list = events.json()
        assert len(event_list) >= 1
        ids = [item["id"] for item in event_list]
        assert len(ids) == len(set(ids))
