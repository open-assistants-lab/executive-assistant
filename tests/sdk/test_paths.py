"""Tests for DataPaths path restructuring."""

from src.storage.paths import DataPaths


def test_root_defaults_to_home_ea():
    dp = DataPaths(user_id="tester", ea_root="/tmp/ea-test-root")
    assert str(dp.root) == "/tmp/ea-test-root"


def test_user_skills_dir():
    dp = DataPaths(user_id="tester", ea_root="/tmp/ea-test-root")
    assert str(dp.user_skills_dir()) == "/tmp/ea-test-root/Skills"


def test_user_subagents_dir():
    dp = DataPaths(user_id="tester", ea_root="/tmp/ea-test-root")
    assert str(dp.user_subagents_dir()) == "/tmp/ea-test-root/Subagents"


def test_user_prompt_path():
    dp = DataPaths(user_id="tester", ea_root="/tmp/ea-test-root")
    assert str(dp.user_prompt_path()) == "/tmp/ea-test-root/AGENTS.md"


def test_email_dir():
    dp = DataPaths(user_id="tester", ea_root="/tmp/ea-test-root")
    assert str(dp.email_dir()) == "/tmp/ea-test-root/Email"


def test_email_db():
    dp = DataPaths(user_id="tester", ea_root="/tmp/ea-test-root")
    assert str(dp.email_db()) == "/tmp/ea-test-root/Email/emails.db"


def test_gmail_cache_dir():
    dp = DataPaths(user_id="tester", ea_root="/tmp/ea-test-root")
    assert str(dp.gmail_cache_dir()) == "/tmp/ea-test-root/Email/gmail_cache"


def test_contacts_dir():
    dp = DataPaths(user_id="tester", ea_root="/tmp/ea-test-root")
    assert str(dp.contacts_dir()) == "/tmp/ea-test-root/Contacts"


def test_contacts_db():
    dp = DataPaths(user_id="tester", ea_root="/tmp/ea-test-root")
    assert str(dp.contacts_db()) == "/tmp/ea-test-root/Contacts/contacts.db"


def test_todos_dir():
    dp = DataPaths(user_id="tester", ea_root="/tmp/ea-test-root")
    assert str(dp.todos_dir()) == "/tmp/ea-test-root/Todos"


def test_todos_db():
    dp = DataPaths(user_id="tester", ea_root="/tmp/ea-test-root")
    assert str(dp.todos_db()) == "/tmp/ea-test-root/Todos/todos.db"


def test_conversation_dir():
    dp = DataPaths(user_id="tester", ea_root="/tmp/ea-test-root")
    assert str(dp.conversation_dir()) == "/tmp/ea-test-root/Conversation"


def test_conversation_db():
    dp = DataPaths(user_id="tester", ea_root="/tmp/ea-test-root")
    assert str(dp.conversation_db()) == "/tmp/ea-test-root/Conversation/messages.db"


def test_user_memory_dir():
    dp = DataPaths(user_id="tester", ea_root="/tmp/ea-test-root")
    assert str(dp.user_memory_dir()) == "/tmp/ea-test-root/Memory/global"


def test_user_apps_dir():
    dp = DataPaths(user_id="tester", ea_root="/tmp/ea-test-root")
    assert str(dp.user_apps_dir()) == "/tmp/ea-test-root/Apps"


def test_user_mcp_config():
    dp = DataPaths(user_id="tester", ea_root="/tmp/ea-test-root")
    assert str(dp.user_mcp_config()) == "/tmp/ea-test-root/.mcp.json"


def test_research_dir():
    dp = DataPaths(user_id="tester", ea_root="/tmp/ea-test-root", workspace_id="testws")
    assert str(dp.research_dir()) == "/tmp/ea-test-root/Research/tester/testws"


def test_companion_dir():
    dp = DataPaths(user_id="tester", ea_root="/tmp/ea-test-root")
    assert str(dp.companion_dir()) == "/tmp/ea-test-root/Companion"


def test_companion_notifications_db():
    dp = DataPaths(user_id="tester", ea_root="/tmp/ea-test-root")
    assert str(dp.companion_notifications_db()) == "/tmp/ea-test-root/Companion/notifications.db"


def test_companion_memory_db():
    dp = DataPaths(user_id="tester", ea_root="/tmp/ea-test-root")
    assert str(dp.companion_memory_db()) == "/tmp/ea-test-root/Companion/memory.db"


def test_workspace_skills_dir_uppercase():
    dp = DataPaths(user_id="tester", ea_root="/tmp/ea-test-root", workspace_id="testws")
    assert str(dp.workspace_skills_dir()) == "/tmp/ea-test-root/Workspaces/testws/Skills"


def test_workspace_subagents_dir_uppercase():
    dp = DataPaths(user_id="tester", ea_root="/tmp/ea-test-root", workspace_id="testws")
    assert str(dp.workspace_subagents_dir()) == "/tmp/ea-test-root/Workspaces/testws/Subagents"


def test_workspace_files_dir_uppercase():
    dp = DataPaths(user_id="tester", ea_root="/tmp/ea-test-root", workspace_id="testws")
    assert str(dp.workspace_files_dir()) == "/tmp/ea-test-root/Workspaces/testws/Files"


def test_workspace_memory_dir_uppercase():
    dp = DataPaths(user_id="tester", ea_root="/tmp/ea-test-root", workspace_id="testws")
    assert str(dp.workspace_memory_dir()) == "/tmp/ea-test-root/Workspaces/testws/Memory"


def test_workspace_conversation_path():
    dp = DataPaths(user_id="tester", ea_root="/tmp/ea-test-root", workspace_id="testws")
    assert str(dp.workspace_conversation_path()) == "/tmp/ea-test-root/Workspaces/testws/conversation.app.db"


def test_deprecated_skills_dir_warns():
    import warnings
    dp = DataPaths(user_id="tester", ea_root="/tmp/ea-test-root")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = dp.skills_dir()
        assert len(w) == 1
        assert "deprecated" in str(w[0].message).lower()
    assert str(result) == "/tmp/ea-test-root/Skills"


def test_deprecated_global_subagents_dir_warns():
    import warnings
    dp = DataPaths(user_id="tester", ea_root="/tmp/ea-test-root")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = dp.global_subagents_dir()
        assert len(w) == 1
        assert "deprecated" in str(w[0].message).lower()
    assert str(result) == "/tmp/ea-test-root/Subagents"


def test_model_cache_path():
    dp = DataPaths(user_id="tester", data_path="/tmp/ea-test-data")
    assert "cache" in str(dp.model_cache_path())


def test_work_queue_db():
    dp = DataPaths(user_id="tester", ea_root="/tmp/ea-test-root")
    path = dp.work_queue_db()
    assert "Subagents" in str(path)
    assert path.name == "work_queue.db"
