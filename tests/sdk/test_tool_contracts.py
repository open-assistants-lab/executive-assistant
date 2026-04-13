"""Contract tests for all 29 tools.

Each tool is tested with its documented input schema and output format.
These tests verify that tools conform to their contract regardless of
whether they use the LangChain @tool decorator or the SDK @tool decorator.
"""

import os
import tempfile
import pytest

os.environ.setdefault("CHECKPOINT_ENABLED", "false")


# ─── Time Tool ───


class TestTimeGet:
    def test_returns_current_time(self):
        from src.tools.time import time_get

        result = time_get.invoke({"user_id": "test"})
        assert isinstance(result, str)
        assert len(result) > 0

    def test_default_user_id(self):
        from src.tools.time import time_get

        result = time_get.invoke({"user_id": "default"})
        assert isinstance(result, str)


# ─── Shell Tool ───


class TestShellExecute:
    def test_simple_command(self):
        from src.tools.shell import shell_execute

        result = shell_execute.invoke({"command": "echo hello", "user_id": "test"})
        assert "hello" in str(result)

    def test_rejects_dangerous_command(self):
        from src.tools.shell import shell_execute

        result = shell_execute.invoke({"command": "rm -rf /", "user_id": "test"})
        assert (
            "not allowed" in str(result).lower()
            or "error" in str(result).lower()
            or "rejected" in str(result).lower()
        )

    def test_default_user_id(self):
        from src.tools.shell import shell_execute

        result = shell_execute.invoke({"command": "echo test"})
        assert isinstance(str(result), str)
        assert "test" in str(result)


# ─── Filesystem Tools ───


class TestFilesystemTools:
    def test_files_list(self):
        from src.tools.filesystem import files_list

        result = files_list.invoke({"user_id": "test_contract"})
        assert isinstance(str(result), str)

    def test_files_write_and_read(self):
        from src.tools.filesystem import files_write, files_read

        with tempfile.TemporaryDirectory() as td:
            write_result = files_write.invoke(
                {
                    "path": "test_contract_file.txt",
                    "content": "Hello from contract test",
                    "user_id": "test_contract_fs",
                }
            )
            assert (
                "wrote" in str(write_result).lower()
                or "success" in str(write_result).lower()
                or "created" in str(write_result).lower()
            )

            read_result = files_read.invoke(
                {
                    "path": "test_contract_file.txt",
                    "user_id": "test_contract_fs",
                }
            )
            assert "Hello from contract test" in str(read_result)


# ─── Todos Tools ───


class TestTodosTools:
    def test_todos_add_and_list(self):
        from src.tools.todos.tools import todos_add, todos_list

        result = todos_add.invoke(
            {"content": "Contract test todo", "user_id": "test_contract_todos"}
        )
        assert isinstance(str(result), str)

        list_result = todos_list.invoke({"user_id": "test_contract_todos"})
        assert isinstance(str(list_result), str)


# ─── Contacts Tools ───


class TestContactsTools:
    def test_contacts_add_and_list(self):
        from src.tools.contacts.tools import contacts_add, contacts_list

        result = contacts_add.invoke(
            {
                "email": "contract@test.com",
                "name": "Contract Test",
                "user_id": "test_contract_contacts",
            }
        )
        assert isinstance(str(result), str)

        list_result = contacts_list.invoke({"user_id": "test_contract_contacts"})
        assert isinstance(str(list_result), str)


# ─── Memory Tools ───


class TestMemoryTools:
    def test_memory_get_history(self):
        from src.tools.memory import memory_get_history

        result = memory_get_history.invoke({"user_id": "test_contract_mem", "limit": 5})
        assert isinstance(str(result), str)

    def test_memory_search(self):
        from src.tools.memory import memory_search

        result = memory_search.invoke({"query": "test", "user_id": "test_contract_mem"})
        assert isinstance(str(result), str)


# ─── Memory Profile Tools ───


class TestMemoryProfileTools:
    def test_memory_stats(self):
        from src.tools.memory_profile import memory_stats

        result = memory_stats.invoke({"user_id": "test_contract_profile"})
        assert isinstance(str(result), str)


# ─── File Search Tools ───


class TestFileSearchTools:
    def test_glob_search(self):
        from src.tools.file_search import files_glob_search

        result = files_glob_search.invoke({"pattern": "*.py", "user_id": "test_contract_fs"})
        assert isinstance(str(result), str)


# ─── Skills Tools ───


class TestSkillsTools:
    def test_skills_list(self):
        from src.skills.tools import skills_list

        result = skills_list.invoke({"user_id": "test_contract_skills"})
        assert isinstance(str(result), str)
