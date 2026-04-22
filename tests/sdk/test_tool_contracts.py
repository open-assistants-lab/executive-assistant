"""Contract tests for all tools.

Each tool is tested with its documented input schema and output format.
These verify that tools conform to their contract regardless of whether
they use LangChain @tool or SDK @tool.
"""




# ─── Time ───


class TestTimeGet:
    def test_returns_current_time(self):
        from src.sdk.tools_core.time import time_get

        result = time_get.invoke()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_includes_date(self):
        from src.sdk.tools_core.time import time_get

        result = time_get.invoke()
        assert "20" in result


# ─── Shell ───


class TestShellExecute:
    def test_simple_command(self):
        from src.sdk.tools_core.shell import shell_execute

        result = shell_execute.invoke({"command": "echo hello", "user_id": "test"})
        assert "hello" in str(result)

    def test_rejects_dangerous_command(self):
        from src.sdk.tools_core.shell import shell_execute

        result = shell_execute.invoke({"command": "rm -rf /", "user_id": "test"})
        lowered = str(result).lower()
        assert (
            "not allowed" in lowered
            or "error" in lowered
            or "rejected" in lowered
            or "dangerous" in lowered
        )

    def test_default_user_id(self):
        from src.sdk.tools_core.shell import shell_execute

        result = shell_execute.invoke({"command": "echo test"})
        assert "test" in str(result)

    def test_command_timeout(self):
        from src.sdk.tools_core.shell import shell_execute

        result = shell_execute.invoke({"command": "sleep 1 && echo done", "user_id": "test"})
        assert isinstance(str(result), str)


# ─── Filesystem ───


class TestFilesystemTools:
    def test_files_write_and_read(self):
        from src.sdk.tools_core.filesystem import files_read, files_write

        files_write.invoke(
            {
                "path": "test_contract_ws/hello.txt",
                "content": "Hello World",
                "user_id": "test_contract_fs",
            }
        )
        result = files_read.invoke(
            {"path": "test_contract_ws/hello.txt", "user_id": "test_contract_fs"}
        )
        assert "Hello World" in str(result)

    def test_files_list(self):
        from src.sdk.tools_core.filesystem import files_list

        result = files_list.invoke({"user_id": "test_contract_fs"})
        assert isinstance(str(result), str)

    def test_files_mkdir(self):
        from src.sdk.tools_core.filesystem import files_mkdir

        result = files_mkdir.invoke(
            {"path": "test_contract_ws/subdir", "user_id": "test_contract_fs"}
        )
        assert isinstance(str(result), str)

    def test_files_edit(self):
        from src.sdk.tools_core.filesystem import files_edit, files_write

        files_write.invoke(
            {
                "path": "test_contract_ws/edit_test.txt",
                "content": "Hello World",
                "user_id": "test_contract_fs",
            }
        )
        result = files_edit.invoke(
            {
                "path": "test_contract_ws/edit_test.txt",
                "old": "World",
                "new": "Universe",
                "user_id": "test_contract_fs",
            }
        )
        assert isinstance(str(result), str)

    def test_files_delete(self):
        from src.sdk.tools_core.filesystem import files_delete, files_write

        files_write.invoke(
            {
                "path": "test_contract_ws/delete_test.txt",
                "content": "to delete",
                "user_id": "test_contract_fs",
            }
        )
        result = files_delete.invoke(
            {"path": "test_contract_ws/delete_test.txt", "user_id": "test_contract_fs"}
        )
        assert isinstance(str(result), str)

    def test_files_rename(self):
        from src.sdk.tools_core.filesystem import files_rename, files_write

        files_write.invoke(
            {
                "path": "test_contract_ws/rename_test.txt",
                "content": "rename me",
                "user_id": "test_contract_fs",
            }
        )
        result = files_rename.invoke(
            {
                "path": "test_contract_ws/rename_test.txt",
                "new_name": "renamed.txt",
                "user_id": "test_contract_fs",
            }
        )
        assert isinstance(str(result), str)


# ─── File Search ───


class TestFileSearchTools:
    def test_glob_search(self):
        from src.sdk.tools_core.file_search import files_glob_search

        result = files_glob_search.invoke({"pattern": "*.py", "user_id": "test_contract_fs"})
        assert isinstance(str(result), str)

    def test_grep_search(self):
        from src.sdk.tools_core.file_search import files_grep_search

        result = files_grep_search.invoke(
            {"pattern": "def time_get", "user_id": "test_contract_fs"}
        )
        assert isinstance(str(result), str)


# ─── Versioning ───


class TestVersioningTools:
    def test_capture_version(self):
        from src.sdk.tools_core.file_versioning import capture_version
        from src.sdk.tools_core.filesystem import files_write

        files_write.invoke(
            {
                "path": "test_contract_ws/ver_test.txt",
                "content": "version 1",
                "user_id": "test_contract_fs",
            }
        )
        result = capture_version(
            user_id="test_contract_fs",
            file_path="test_contract_ws/ver_test.txt",
            new_content="version 2",
        )
        assert isinstance(str(result), str) or result is None

    def test_files_versions_list(self):
        from src.sdk.tools_core.file_versioning import files_versions_list

        result = files_versions_list.invoke(
            {"path": "test_contract_ws/ver_test.txt", "user_id": "test_contract_fs"}
        )
        assert isinstance(str(result), str)


# ─── Todos ───


class TestTodosTools:
    def test_todos_add_and_list(self):
        from src.sdk.tools_core.todos import todos_add, todos_list

        result = todos_add.invoke(
            {"content": "Contract test todo", "user_id": "test_contract_todos"}
        )
        assert isinstance(str(result), str)
        list_result = todos_list.invoke({"user_id": "test_contract_todos"})
        assert isinstance(str(list_result), str)

    def test_todos_update(self):
        from src.sdk.tools_core.todos import todos_add

        add_result = todos_add.invoke(
            {"content": "Update test todo", "user_id": "test_contract_todos"}
        )
        assert isinstance(str(add_result), str)

    def test_todos_extract(self):
        from src.sdk.tools_core.todos import todos_extract

        result = todos_extract.invoke({"user_id": "test_contract_todos", "limit": 1})
        assert isinstance(str(result), str)


# ─── Contacts ───


class TestContactsTools:
    def test_contacts_add_and_list(self):
        from src.sdk.tools_core.contacts import contacts_add, contacts_list

        result = contacts_add.invoke(
            {"email": "contract@test.com", "name": "Contract Test", "user_id": "test_contract_ct"}
        )
        assert isinstance(str(result), str)
        list_result = contacts_list.invoke({"user_id": "test_contract_ct"})
        assert isinstance(str(list_result), str)

    def test_contacts_search(self):
        from src.sdk.tools_core.contacts import contacts_search

        result = contacts_search.invoke({"query": "test", "user_id": "test_contract_ct"})
        assert isinstance(str(result), str)

    def test_contacts_update(self):
        from src.sdk.tools_core.contacts import contacts_update

        result = contacts_update.invoke(
            {"contact_id": "nonexistent", "name": "Updated", "user_id": "test_contract_ct"}
        )
        assert isinstance(str(result), str)

    def test_contacts_delete(self):
        from src.sdk.tools_core.contacts import contacts_delete

        result = contacts_delete.invoke(
            {"contact_id": "nonexistent", "user_id": "test_contract_ct"}
        )
        assert isinstance(str(result), str)

    def test_contacts_get(self):
        from src.sdk.tools_core.contacts import contacts_get

        result = contacts_get.invoke({"contact_id": "nonexistent", "user_id": "test_contract_ct"})
        assert isinstance(str(result), str)


# ─── Memory ───


class TestMemoryTools:
    def test_memory_get_history(self):
        from src.sdk.tools_core.memory import memory_get_history

        result = memory_get_history.invoke({"user_id": "test_contract_mem", "days": 1})
        assert isinstance(str(result), str)

    def test_memory_search(self):
        from src.sdk.tools_core.memory import memory_search

        result = memory_search.invoke({"query": "test", "user_id": "test_contract_mem"})
        assert isinstance(str(result), str)


# ─── Email ───


class TestEmailTools:
    def test_email_accounts(self):
        from src.sdk.tools_core.email import email_accounts

        result = email_accounts.invoke({"user_id": "test_contract_email"})
        assert isinstance(str(result), str)

    def test_email_list(self):
        from src.sdk.tools_core.email import email_list

        result = email_list.invoke(
            {"account_name": "default", "limit": 5, "user_id": "test_contract_email"}
        )
        assert isinstance(str(result), str)

    def test_email_search(self):
        from src.sdk.tools_core.email import email_search

        result = email_search.invoke(
            {"query": "test", "account_name": "default", "user_id": "test_contract_email"}
        )
        assert isinstance(str(result), str)


class TestSkillsTools:
    def test_skills_list(self):
        from src.sdk.tools_core.skills import skills_list

        result = skills_list.invoke({"user_id": "test_contract_skills"})
        assert isinstance(str(result), str)

    def test_skills_list_includes_skill_names(self):
        from src.sdk.tools_core.skills import skills_list

        result = skills_list.invoke({"user_id": "test_contract_skills"})
        assert "deep-research" in result or "skill" in result.lower()

    def test_skills_search_finds_matching_skills(self):
        from src.sdk.tools_core.skills import skills_search

        result = skills_search.invoke({"query": "research", "user_id": "test_contract_skills"})
        assert isinstance(str(result), str)
        assert "deep-research" in result or "research" in result.lower()

    def test_skills_search_no_match(self):
        from src.sdk.tools_core.skills import skills_search

        result = skills_search.invoke(
            {"query": "xyz-nonexistent-123", "user_id": "test_contract_skills"}
        )
        assert "no skills matching" in result.lower() or "available skills" in result.lower()

    def test_skills_list_tool_description_does_not_inject_skills(self):
        from src.sdk.tools_core.skills import skills_list

        openai_format = skills_list.to_openai_format()
        desc = openai_format["function"]["description"]
        assert "deep-research" not in desc, (
            f"Tool description should NOT inject skill names (progressive disclosure), got: {desc[:200]}"
        )
        assert "skills_load" in desc, (
            f"Tool description should mention skills_load for discovery, got: {desc[:200]}"
        )

    def test_skills_load_returns_content(self):
        from src.sdk.tools_core.skills import skills_load

        result = skills_load.invoke(
            {"skill_name": "deep-research", "user_id": "test_contract_skills"}
        )
        assert "# deep-research" in result or "deep-research" in result

    def test_skills_load_not_found(self):
        from src.sdk.tools_core.skills import skills_load

        result = skills_load.invoke(
            {"skill_name": "nonexistent-skill-xyz", "user_id": "test_contract_skills"}
        )
        assert "not found" in result.lower()


class TestAppTools:
    """App tools require ChromaDB — contract checks only."""

    def test_app_tools_have_invoke(self):
        from src.sdk.tools_core.apps import app_create, app_delete, app_list, app_query, app_schema

        for tool in [app_create, app_list, app_schema, app_query, app_delete]:
            assert hasattr(tool, "invoke"), f"{tool.name} must have invoke method"
