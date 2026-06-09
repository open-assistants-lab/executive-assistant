"""Contract tests for conversation endpoints."""


class TestGetConversation:
    """Tests for GET /conversation."""

    def test_get_conversation_default_user(self, client):
        r = client.get("/conversation")
        assert r.status_code == 200
        data = r.json()
        assert "messages" in data
        assert isinstance(data["messages"], list)

    def test_get_conversation_with_user_id(self, client, test_user_id):
        r = client.get("/conversation", params={"user_id": test_user_id})
        assert r.status_code == 200
        data = r.json()
        assert "messages" in data

    def test_get_conversation_with_limit(self, client, test_user_id):
        r = client.get("/conversation", params={"user_id": test_user_id, "limit": 5})
        assert r.status_code == 200

    def test_get_conversation_response_schema(self, client, test_user_id):
        r = client.get("/conversation", params={"user_id": test_user_id})
        data = r.json()
        for msg in data["messages"]:
            assert "role" in msg
            assert "content" in msg
            assert msg["role"] in ("user", "assistant", "tool", "summary")

    def test_get_conversation_filters_workspace_before_limit(self, client, test_user_id):
        from src.storage.messages import get_message_store

        store = get_message_store(test_user_id, "test")
        store.clear()
        store.add_message("user", "test workspace message", metadata={"workspace_id": "test"})
        for i in range(120):
            store.add_message("user", f"personal message {i}", metadata={"workspace_id": "personal"})

        r = client.get(
            "/conversation",
            params={"user_id": test_user_id, "workspace_id": "test", "limit": 100},
        )

        assert r.status_code == 200
        assert [m["content"] for m in r.json()["messages"]] == ["test workspace message"]


class TestClearConversation:
    """Tests for DELETE /conversation."""

    def test_clear_conversation(self, client, test_user_id):
        r = client.delete("/conversation", params={"user_id": test_user_id})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "cleared"
        assert data["user_id"] == test_user_id

    def test_clear_conversation_default_user(self, client):
        r = client.delete("/conversation")
        assert r.status_code == 200


class TestEditorParser:
    """Tests for _extract_editor() and _render_editor_surface()."""

    def test_extract_editor_basic(self):
        from src.http.routers.conversation import _extract_editor

        text = '```html:editor\nfilePath: /test/file.md\n---\n\n# Hello\n\nWorld\n```'
        result = _extract_editor(text)
        assert len(result) == 1
        assert result[0]["surface_type"] == "editor"
        assert result[0]["file_path"] == "/test/file.md"
        assert "Hello" in result[0]["html"]

    def test_extract_editor_multiple(self):
        from src.http.routers.conversation import _extract_editor

        text = (
            '```html:editor\nfilePath: /a.md\n---\n\nFile A\n```\n'
            'Some text\n'
            '```html:editor\nfilePath: /b.md\n---\n\nFile B\n```'
        )
        result = _extract_editor(text)
        assert len(result) == 2

    def test_extract_editor_no_file_path(self):
        from src.http.routers.conversation import _extract_editor

        text = '```html:editor\n---\n\nContent\n```'
        result = _extract_editor(text)
        assert result == []

    def test_extract_editor_empty(self):
        from src.http.routers.conversation import _extract_editor

        text = 'No fences here'
        result = _extract_editor(text)
        assert result == []

    def test_extract_editor_interleaved_with_canvas(self):
        from src.http.routers.conversation import _extract_editor, _extract_surfaces, _extract_canvas

        text = (
            '```html:canvas\n<div>hello</div>\n```\n'
            '```html:editor\nfilePath: /f.md\n---\n\ncontent\n```'
        )
        surfaces = _extract_surfaces(text)
        assert len(surfaces) == 2
        assert surfaces[0]["surface_type"] == "canvas"
        assert surfaces[1]["surface_type"] == "editor"

        canvas = _extract_canvas(text)
        assert len(canvas) == 1
        assert canvas[0]["surface_type"] == "canvas"

        editor = _extract_editor(text)
        assert len(editor) == 1
        assert editor[0]["surface_type"] == "editor"

    def test_strip_editor_fences(self):
        from src.http.routers.conversation import _strip_canvas_fences

        text = (
            'Some text\n'
            '```html:editor\nfilePath: /f.md\n---\n\ncontent\n```\n'
            'More text'
        )
        result = _strip_canvas_fences(text)
        assert "```html:editor" not in result
        assert "Some text" in result
        assert "More text" in result

    def test_render_editor_surface_contains_editor_id(self):
        from src.http.routers.conversation import _render_editor_surface

        html = _render_editor_surface("/test/file.md", "# Hello")
        assert "novel-mount" in html
        assert "# Hello" in html or "Hello" in html
