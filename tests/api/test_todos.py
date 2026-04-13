"""Contract tests for todos endpoints."""


class TestListTodos:
    """Tests for GET /todos."""

    def test_list_todos(self, client, test_user_id):
        r = client.get("/todos", params={"user_id": test_user_id})
        assert r.status_code == 200
        data = r.json()
        assert "todos" in data or "result" in data


class TestAddTodo:
    """Tests for POST /todos."""

    def test_add_todo_minimal(self, client, test_user_id):
        r = client.post(
            "/todos",
            params={"content": "Test todo item", "user_id": test_user_id},
        )
        assert r.status_code == 200
        data = r.json()
        assert "result" in data

    def test_add_todo_with_priority(self, client, test_user_id):
        r = client.post(
            "/todos",
            params={"content": "High priority todo", "priority": 1, "user_id": test_user_id},
        )
        assert r.status_code == 200


class TestUpdateTodo:
    """Tests for PUT /todos/{todo_id}."""

    def test_update_todo_status(self, client, test_user_id):
        r = client.put(
            "/todos/nonexistent_id",
            params={"status": "completed", "user_id": test_user_id},
        )
        assert r.status_code == 200


class TestDeleteTodo:
    """Tests for DELETE /todos/{todo_id}."""

    def test_delete_todo(self, client, test_user_id):
        r = client.delete("/todos/nonexistent_id", params={"user_id": test_user_id})
        assert r.status_code == 200
