"""Contract tests for contacts endpoints."""


class TestListContacts:
    """Tests for GET /contacts."""

    def test_list_contacts(self, client, test_user_id):
        r = client.get("/contacts", params={"user_id": test_user_id})
        assert r.status_code == 200
        data = r.json()
        assert "contacts" in data


class TestSearchContacts:
    """Tests for GET /contacts/search."""

    def test_search_contacts(self, client, test_user_id):
        r = client.get("/contacts/search", params={"query": "alice", "user_id": test_user_id})
        assert r.status_code == 200
        data = r.json()
        assert "results" in data


class TestAddContact:
    """Tests for POST /contacts."""

    def test_add_contact_minimal(self, client, test_user_id):
        r = client.post(
            "/contacts",
            params={"email": "test@example.com", "user_id": test_user_id},
        )
        assert r.status_code == 200
        data = r.json()
        assert "result" in data

    def test_add_contact_full(self, client, test_user_id):
        r = client.post(
            "/contacts",
            params={
                "email": "full@example.com",
                "name": "Full Contact",
                "phone": "555-1234",
                "company": "Test Corp",
                "user_id": test_user_id,
            },
        )
        assert r.status_code == 200


class TestUpdateContact:
    """Tests for PUT /contacts/{contact_id}."""

    def test_update_contact(self, client, test_user_id):
        r = client.put(
            "/contacts/nonexistent_id",
            params={"name": "Updated Name", "user_id": test_user_id},
        )
        assert r.status_code == 200


class TestDeleteContact:
    """Tests for DELETE /contacts/{contact_id}."""

    def test_delete_contact(self, client, test_user_id):
        r = client.delete("/contacts/nonexistent_id", params={"user_id": test_user_id})
        assert r.status_code == 200
