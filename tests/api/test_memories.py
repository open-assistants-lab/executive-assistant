"""Contract tests for memory endpoints."""


class TestListMemories:
    """Tests for GET /memories."""

    def test_list_memories_default(self, client, test_user_id):
        r = client.get("/memories", params={"user_id": test_user_id})
        assert r.status_code == 200
        data = r.json()
        assert "memories" in data
        assert isinstance(data["memories"], list)

    def test_list_memories_with_domain_filter(self, client, test_user_id):
        r = client.get("/memories", params={"user_id": test_user_id, "domain": "personal"})
        assert r.status_code == 200

    def test_list_memories_with_type_filter(self, client, test_user_id):
        r = client.get("/memories", params={"user_id": test_user_id, "memory_type": "fact"})
        assert r.status_code == 200

    def test_list_memories_with_confidence_filter(self, client, test_user_id):
        r = client.get("/memories", params={"user_id": test_user_id, "min_confidence": 0.5})
        assert r.status_code == 200

    def test_list_memories_with_scope_filter(self, client, test_user_id):
        r = client.get("/memories", params={"user_id": test_user_id, "scope": "global"})
        assert r.status_code == 200

    def test_memory_response_schema(self, client, test_user_id):
        r = client.get("/memories", params={"user_id": test_user_id})
        data = r.json()
        if data["memories"]:
            mem = data["memories"][0]
            for key in ("id", "trigger", "action", "confidence", "domain", "memory_type"):
                assert key in mem


class TestAddMemory:
    """Tests for POST /memories."""

    def test_add_memory_minimal(self, client, test_user_id):
        r = client.post(
            "/memories",
            params={"trigger": "test trigger", "action": "test action", "user_id": test_user_id},
        )
        assert r.status_code == 200
        data = r.json()
        assert "memory" in data

    def test_add_memory_full(self, client, test_user_id):
        r = client.post(
            "/memories",
            params={
                "trigger": "when user asks about weather",
                "action": "check weather API",
                "domain": "weather",
                "memory_type": "workflow",
                "user_id": test_user_id,
            },
        )
        assert r.status_code == 200


class TestSearchMemories:
    """Tests for POST /memories/search."""

    def test_search_memories_hybrid(self, client, test_user_id):
        r = client.post(
            "/memories/search",
            json={"query": "weather", "method": "hybrid", "limit": 5, "user_id": test_user_id},
        )
        assert r.status_code == 200
        data = r.json()
        assert "query" in data
        assert "method" in data
        assert "results" in data

    def test_search_memories_fts(self, client, test_user_id):
        r = client.post(
            "/memories/search",
            json={"query": "test", "method": "fts", "limit": 5, "user_id": test_user_id},
        )
        assert r.status_code == 200

    def test_search_memories_semantic(self, client, test_user_id):
        r = client.post(
            "/memories/search",
            json={
                "query": "coding preferences",
                "method": "semantic",
                "limit": 5,
                "user_id": test_user_id,
            },
        )
        assert r.status_code == 200

    def test_search_all(self, client, test_user_id):
        r = client.post(
            "/memories/search-all",
            json={
                "query": "test",
                "memories_limit": 3,
                "messages_limit": 3,
                "insights_limit": 2,
                "user_id": test_user_id,
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert "memories" in data
        assert "insights" in data
        assert "messages" in data


class TestMemoryConnections:
    """Tests for POST /memories/connections."""

    def test_add_connection(self, client, test_user_id):
        r = client.post(
            "/memories/connections",
            json={
                "memory_id": "nonexistent1",
                "target_id": "nonexistent2",
                "relationship": "relates_to",
                "strength": 1.0,
                "user_id": test_user_id,
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "connected"


class TestMemoryInsights:
    """Tests for /memories/insights endpoints."""

    def test_list_insights(self, client, test_user_id):
        r = client.get("/memories/insights", params={"user_id": test_user_id, "limit": 10})
        assert r.status_code == 200
        data = r.json()
        assert "insights" in data

    def test_search_insights(self, client, test_user_id):
        r = client.post(
            "/memories/insights/search",
            json={"query": "test", "method": "hybrid", "limit": 5, "user_id": test_user_id},
        )
        assert r.status_code == 200


class TestMemoryStats:
    """Tests for GET /memories/stats."""

    def test_memory_stats(self, client, test_user_id):
        r = client.get("/memories/stats", params={"user_id": test_user_id})
        assert r.status_code == 200


class TestConsolidateMemories:
    """Tests for POST /memories/consolidate."""

    def test_consolidate(self, client, test_user_id):
        r = client.post("/memories/consolidate", params={"user_id": test_user_id})
        assert r.status_code == 200


class TestDeleteMemory:
    """Tests for DELETE /memories/{memory_id}."""

    def test_delete_nonexistent_memory(self, client, test_user_id):
        r = client.delete("/memories/nonexistent_id", params={"user_id": test_user_id})
        assert r.status_code == 200
        data = r.json()
        assert "status" in data
