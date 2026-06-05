"""Contract tests for observation/reflection endpoints."""


class TestObservations:
    """Tests for GET /memories/observations."""

    def test_list_observations_default(self, client, test_user_id):
        r = client.get("/memories/observations", params={"user_id": test_user_id})
        assert r.status_code == 200
        data = r.json()
        assert "observations" in data
        assert isinstance(data["observations"], list)

    def test_list_observations_with_params(self, client, test_user_id):
        r = client.get(
            "/memories/observations",
            params={"user_id": test_user_id, "days": 14, "limit": 10},
        )
        assert r.status_code == 200


class TestReflections:
    """Tests for GET /memories/reflections."""

    def test_list_reflections_default(self, client, test_user_id):
        r = client.get("/memories/reflections", params={"user_id": test_user_id})
        assert r.status_code == 200
        data = r.json()
        assert "reflections" in data
        assert isinstance(data["reflections"], list)

    def test_list_reflections_with_limit(self, client, test_user_id):
        r = client.get(
            "/memories/reflections",
            params={"user_id": test_user_id, "limit": 5},
        )
        assert r.status_code == 200


class TestSearchReflections:
    """Tests for POST /memories/reflections/search."""

    def test_search_reflections_hybrid(self, client, test_user_id):
        r = client.post(
            "/memories/reflections/search",
            params={"query": "test", "method": "hybrid", "limit": 5, "user_id": test_user_id},
        )
        assert r.status_code == 200
        data = r.json()
        assert "query" in data
        assert "method" in data
        assert "results" in data

    def test_search_reflections_fts(self, client, test_user_id):
        r = client.post(
            "/memories/reflections/search",
            params={"query": "test", "method": "fts", "limit": 5, "user_id": test_user_id},
        )
        assert r.status_code == 200

    def test_search_reflections_semantic(self, client, test_user_id):
        r = client.post(
            "/memories/reflections/search",
            params={"query": "test", "method": "semantic", "limit": 5, "user_id": test_user_id},
        )
        assert r.status_code == 200


class TestSearchObservations:
    """Tests for POST /memories/observations/search."""

    def test_search_observations(self, client, test_user_id):
        r = client.post(
            "/memories/observations/search",
            params={"query": "test", "limit": 10, "user_id": test_user_id},
        )
        assert r.status_code == 200
        data = r.json()
        assert "query" in data
        assert "results" in data


class TestClearMemories:
    """Tests for DELETE /memories/clear."""

    def test_clear_memories(self, client, test_user_id):
        r = client.delete("/memories/clear", params={"user_id": test_user_id})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "cleared"
