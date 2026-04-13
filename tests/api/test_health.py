"""Contract tests for health endpoints."""


class TestHealthEndpoints:
    """Tests for /health and /health/ready."""

    def test_health_returns_200(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert "status" in data
        assert data["status"] == "healthy"

    def test_health_ready_returns_200(self, client):
        r = client.get("/health/ready")
        assert r.status_code == 200
        data = r.json()
        assert "status" in data
