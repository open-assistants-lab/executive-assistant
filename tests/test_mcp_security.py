"""Security tests for User MCP implementation.

Tests security features including:
- HTTPS enforcement for remote servers
- Server name validation (no injection attacks)
- Command validation
- Thread isolation
- Path traversal prevention
- Input validation
"""

from pathlib import Path
from unittest.mock import patch
import json

import pytest

from executive_assistant.storage.user_mcp_storage import UserMCPStorage
from executive_assistant.tools.user_mcp_tools import (
    mcp_add_server,
    mcp_add_remote_server,
    mcp_import_config,
)
from executive_assistant.storage.file_sandbox import set_thread_id, clear_thread_id


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def thread_context():
    """Set thread_id context for all tests."""
    set_thread_id("security_test")
    yield
    clear_thread_id()


@pytest.fixture
def temp_mcp_dir(tmp_path):
    """Create a temporary MCP directory."""
    mcp_dir = tmp_path / "users" / "security_test" / "mcp"
    mcp_dir.mkdir(parents=True, exist_ok=True)

    with patch("executive_assistant.storage.user_mcp_storage.get_thread_mcp_dir", return_value=mcp_dir.parent):
        yield mcp_dir


# =============================================================================
# HTTPS Enforcement Tests
# =============================================================================

class TestHTTPSEnforcement:
    """Test HTTPS requirement for remote servers."""

    def test_https_url_allowed(self, temp_mcp_dir):
        """Test that HTTPS URLs are accepted."""
        storage = UserMCPStorage("security_test")
        config = {
            "mcpServers": {
                "api": {
                    "url": "https://api.example.com/mcp"
                }
            }
        }

        # Should not raise
        storage.save_remote_config(config)

    def test_http_url_rejected(self, temp_mcp_dir):
        """Test that HTTP URLs are rejected."""
        storage = UserMCPStorage("security_test")
        config = {
            "mcpServers": {
                "api": {
                    "url": "http://api.example.com/mcp"
                }
            }
        }

        with pytest.raises(ValueError, match="must use HTTPS"):
            storage.save_remote_config(config)

    def test_localhost_http_allowed(self, temp_mcp_dir):
        """Test that localhost HTTP URLs are allowed."""
        storage = UserMCPStorage("security_test")

        allowed_urls = [
            "http://localhost/mcp",
            "http://localhost:8080/mcp",
            "http://localhost:3000/mcp",
            "http://127.0.0.1/mcp",
            "http://127.0.0.1:9000/mcp",
        ]

        for url in allowed_urls:
            config = {
                "mcpServers": {
                    "local": {
                        "url": url
                    }
                }
            }
            # Should not raise
            storage.save_remote_config(config)

    def test_localhost_variations(self, temp_mcp_dir):
        """Test various localhost URL formats."""
        storage = UserMCPStorage("security_test")

        # Test localhost with different ports
        for port in [80, 443, 3000, 8080, 9000]:
            config = {
                "mcpServers": {
                    f"local{port}": {
                        "url": f"http://localhost:{port}/mcp"
                    }
                }
            }
            storage.save_remote_config(config)

    def test_non_localhost_ip_rejected(self, temp_mcp_dir):
        """Test that non-localhost IPs with HTTP are rejected."""
        storage = UserMCPStorage("security_test")

        rejected_ips = [
            "http://192.168.1.1/mcp",
            "http://10.0.0.1/mcp",
            "http://172.16.0.1/mcp",
        ]

        for url in rejected_ips:
            config = {
                "mcpServers": {
                    "internal": {
                        "url": url
                    }
                }
            }

            with pytest.raises(ValueError, match="must use HTTPS"):
                storage.save_remote_config(config)

    def test_ftp_url_rejected(self, temp_mcp_dir):
        """Test that FTP URLs are rejected."""
        storage = UserMCPStorage("security_test")
        config = {
            "mcpServers": {
                "ftp": {
                    "url": "ftp://ftp.example.com/mcp"
                }
            }
        }

        with pytest.raises(ValueError, match="must use HTTPS"):
            storage.save_remote_config(config)


# =============================================================================
# Server Name Validation Tests (Injection Prevention)
# =============================================================================

class TestServerNameValidation:
    """Test server name validation prevents injection attacks."""

    def test_reject_path_traversal_in_name(self, temp_mcp_dir):
        """Test that path traversal in server name is rejected."""
        storage = UserMCPStorage("security_test")

        malicious_names = [
            "../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "../../ malicious",
            "....//etc",
        ]

        for name in malicious_names:
            config = {
                "mcpServers": {
                    name: {"command": "echo"}
                }
            }

            with pytest.raises(ValueError, match="Invalid server name"):
                storage.save_local_config(config)

    def test_reject_command_injection_in_name(self, temp_mcp_dir):
        """Test that command injection patterns in name are rejected."""
        storage = UserMCPStorage("security_test")

        injection_names = [
            "server; rm -rf /",
            "server && cat /etc/passwd",
            "server | malicious",
            "server`whoami`",
            "server$(whoami)",
            "server; DROP TABLE users",
        ]

        for name in injection_names:
            config = {
                "mcpServers": {
                    name: {"command": "echo"}
                }
            }

            with pytest.raises(ValueError, match="Invalid server name"):
                storage.save_local_config(config)

    def test_reject_null_bytes(self, temp_mcp_dir):
        """Test that null bytes in name are rejected."""
        storage = UserMCPStorage("security_test")
        config = {
            "mcpServers": {
                "server\x00.exe": {"command": "echo"}
            }
        }

        with pytest.raises(ValueError, match="Invalid server name"):
            storage.save_local_config(config)

    def test_reject_special_characters(self, temp_mcp_dir):
        """Test that special characters are rejected."""
        storage = UserMCPStorage("security_test")

        bad_names = [
            "server.exe",  # Could be mistaken for executable
            "server@evil",  # Could be email/mention
            "server$HOME",  # Could expand to environment variable
            "server*",
            "server?",
            "server|",
            "server;",
            "server&",
            "server`",
        ]

        for name in bad_names:
            config = {
                "mcpServers": {
                    name: {"command": "echo"}
                }
            }

            with pytest.raises(ValueError, match="Invalid server name"):
                storage.save_local_config(config)

    def test_allow_valid_names(self, temp_mcp_dir):
        """Test that valid names are accepted."""
        storage = UserMCPStorage("security_test")

        valid_names = [
            "test",
            "test-server",
            "test_server",
            "test123",
            "TestServer123",
            "my-api-server",
            "server_v2",
            "123server",
        ]

        for name in valid_names:
            config = {
                "mcpServers": {
                    name: {"command": "echo"}
                }
            }
            # Should not raise
            storage.save_local_config(config)


# =============================================================================
# Command Validation Tests
# =============================================================================

class TestCommandValidation:
    """Test command field validation."""

    def test_command_must_be_string(self, temp_mcp_dir):
        """Test that command must be a string."""
        storage = UserMCPStorage("security_test")

        invalid_commands = [
            123,
            ["echo", "hello"],
            {"cmd": "echo"},
            None,
            True,
        ]

        for cmd in invalid_commands:
            config = {
                "mcpServers": {
                    "test": {
                        "command": cmd
                    }
                }
            }

            with pytest.raises(ValueError, match="command must be a string"):
                storage.save_local_config(config)

    def test_args_must_be_list(self, temp_mcp_dir):
        """Test that args must be a list."""
        storage = UserMCPStorage("security_test")

        invalid_args = [
            "echo hello",
            123,
            {"arg": "value"},
            None,
        ]

        for args in invalid_args:
            config = {
                "mcpServers": {
                    "test": {
                        "command": "echo",
                        "args": args
                    }
                }
            }

            with pytest.raises(ValueError, match="args must be a list"):
                storage.save_local_config(config)

    def test_arg_elements_must_be_strings(self, temp_mcp_dir):
        """Test that arg elements must be strings."""
        storage = UserMCPStorage("security_test")

        invalid_arg_lists = [
            [123, "hello"],
            ["hello", None],
            ["hello", {"arg": "value"}],
            ["hello", ["nested"]],
        ]

        for args in invalid_arg_lists:
            config = {
                "mcpServers": {
                    "test": {
                        "command": "echo",
                        "args": args
                    }
                }
            }

            with pytest.raises(ValueError, match="must be a string"):
                storage.save_local_config(config)

    def test_env_must_be_dict(self, temp_mcp_dir):
        """Test that env must be a dictionary."""
        storage = UserMCPStorage("security_test")

        invalid_envs = [
            "KEY=value",
            ["KEY=value"],
            123,
            None,
        ]

        for env in invalid_envs:
            config = {
                "mcpServers": {
                    "test": {
                        "command": "echo",
                        "env": env
                    }
                }
            }

            with pytest.raises(ValueError, match="env must be a dictionary"):
                storage.save_local_config(config)

    def test_env_values_must_be_strings(self, temp_mcp_dir):
        """Test that env values must be strings."""
        storage = UserMCPStorage("security_test")

        invalid_envs = [
            {"KEY": 123},
            {"KEY": None},
            {"KEY": ["value"]},
            {123: "value"},  # Key must also be string
            {None: "value"},
        ]

        for env in invalid_envs:
            config = {
                "mcpServers": {
                    "test": {
                        "command": "echo",
                        "env": env
                    }
                }
            }

            with pytest.raises(ValueError, match="must be strings"):
                storage.save_local_config(config)


# =============================================================================
# Thread Isolation Tests
# =============================================================================

class TestThreadIsolation:
    """Test thread isolation prevents cross-thread data access."""

    def test_threads_separated(self, temp_mcp_dir):
        """Test that different threads have separate configs."""
        storage1 = UserMCPStorage("thread_1")
        storage2 = UserMCPStorage("thread_2")

        # Add server to thread 1
        config1 = {
            "mcpServers": {
                "thread1-server": {"command": "echo1"}
            }
        }
        storage1.save_local_config(config1)

        # Add different server to thread 2
        config2 = {
            "mcpServers": {
                "thread2-server": {"command": "echo2"}
            }
        }
        storage2.save_local_config(config2)

        # Verify isolation
        loaded1 = storage1.load_local_config()
        loaded2 = storage2.load_local_config()

        assert "thread1-server" in loaded1["mcpServers"]
        assert "thread2-server" not in loaded1["mcpServers"]
        assert "thread2-server" in loaded2["mcpServers"]
        assert "thread1-server" not in loaded2["mcpServers"]

    def test_thread_paths_separate(self, temp_mcp_dir):
        """Test that thread directories are separate."""
        storage1 = UserMCPStorage("user1")
        storage2 = UserMCPStorage("user2")

        # Paths should be different
        assert storage1.mcp_dir != storage2.mcp_dir
        assert "user1" in str(storage1.mcp_dir)
        assert "user2" in str(storage2.mcp_dir)

    def test_cross_thread_data_leak_prevention(self, temp_mcp_dir):
        """Test that data cannot leak between threads."""
        # Create two threads
        storage1 = UserMCPStorage("secure_thread")
        storage2 = UserMCPStorage("other_thread")

        # Add sensitive data to thread 1
        sensitive_config = {
            "mcpServers": {
                "secret-api": {
                    "command": "secret-cmd",
                    "env": {"API_KEY": "secret123"}
                }
            }
        }
        storage1.save_local_config(sensitive_config)

        # Thread 2 should not see this
        config2 = storage2.load_local_config()
        assert "secret-api" not in config2["mcpServers"]
        assert config2["mcpServers"] == {}


# =============================================================================
# Import Validation Tests
# =============================================================================

class TestImportSecurity:
    """Test security of configuration import."""

    def test_import_rejects_duplicate_names(self, temp_mcp_dir):
        """Test that import rejects duplicate server names."""
        # Add existing server
        mcp_add_server.invoke({"name": "existing", "command": "echo"})

        # Try to import with same name
        import_config = {
            "local": {
                "mcpServers": {
                    "existing": {"command": "malicious-cmd"}
                }
            },
            "remote": {"mcpServers": {}}
        }

        result = mcp_import_config.invoke({
            "config_json": json.dumps(import_config)
        })

        assert "❌" in result
        assert "already exists" in result

        # Verify original not overwritten
        storage = UserMCPStorage("security_test")
        config = storage.load_local_config()
        assert config["mcpServers"]["existing"]["command"] == "echo"

    def test_import_validates_structure(self, temp_mcp_dir):
        """Test that import validates config structure."""
        # Invalid structure
        import_configs = [
            "not json",
            "{invalid}",
            '["array", "instead", "of", "object"]',
            'null',
            'true',
        ]

        for invalid in import_configs:
            result = mcp_import_config.invoke({"config_json": invalid})
            assert "❌" in result

    def test_import_validates_server_names(self, temp_mcp_dir):
        """Test that import validates server names."""
        import_config = {
            "local": {
                "mcpServers": {
                    "invalid name!": {"command": "echo"}
                }
            },
            "remote": {"mcpServers": {}}
        }

        result = mcp_import_config.invoke({
            "config_json": json.dumps(import_config)
        })

        assert "❌" in result

    def test_import_validates_urls(self, temp_mcp_dir):
        """Test that import validates HTTPS requirement."""
        import_config = {
            "local": {"mcpServers": {}},
            "remote": {
                "mcpServers": {
                    "bad-remote": {
                        "url": "http://api.example.com/mcp"
                    }
                }
            }
        }

        result = mcp_import_config.invoke({
            "config_json": json.dumps(import_config)
        })

        assert "❌" in result


# =============================================================================
# Backup Security Tests
# =============================================================================

class TestBackupSecurity:
    """Test backup security."""

    def test_backup_names_are_safe(self, temp_mcp_dir):
        """Test that backup filenames are safe."""
        storage = UserMCPStorage("security_test")

        # Create a backup
        config = {"mcpServers": {"test": {"command": "echo"}}}
        storage.save_local_config(config)
        storage.save_local_config(config)  # Create backup

        backups = storage.list_backups("mcp.json")

        if backups:
            # Backup name should be safe
            backup_name = backups[0]["name"]

            # Should match expected pattern
            assert backup_name.startswith("mcp.json.backup_")

            # Should not contain path traversal
            assert ".." not in backup_name
            assert "/" not in backup_name
            assert "\\" not in backup_name

    def test_restore_validates_backup_name(self, temp_mcp_dir):
        """Test that restore validates backup filename."""
        storage = UserMCPStorage("security_test")

        malicious_names = [
            "../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "/etc/passwd",
            "mcp.json.backup_../../../malicious",
            "mcp.json.backup_$(whoami)",
        ]

        for name in malicious_names:
            with pytest.raises((FileNotFoundError, ValueError)):
                storage.restore_backup(name)

    def test_restore_only_allowed_files(self, temp_mcp_dir):
        """Test that restore only allows mcp.json backups."""
        storage = UserMCPStorage("security_test")

        # Try to restore non-backup file
        with pytest.raises(ValueError, match="Invalid backup filename"):
            storage.restore_backup("malicious.json")
            storage.restore_backup("etc_passwd")
            storage.restore_backup("../../../etc/passwd")


# =============================================================================
# JSON Security Tests
# =============================================================================

class TestJSONSecurity:
    """Test JSON parsing security."""

    def test_invalid_json_rejected(self, temp_mcp_dir):
        """Test that invalid JSON is rejected."""
        storage = UserMCPStorage("security_test")

        # Write invalid JSON to config file
        with open(storage.mcp_dir / "mcp.json", "w") as f:
            f.write('{"invalid": json}')

        # Should raise ValueError, not crash
        with pytest.raises(ValueError, match="Invalid JSON"):
            storage.load_local_config()

    def test_malicious_json_rejected(self, temp_mcp_dir):
        """Test that malicious JSON patterns are rejected."""
        storage = UserMCPStorage("security_test")

        # Try to save config with invalid server name
        malicious_configs = [
            {"mcpServers": {"../../etc": {"command": "echo"}}},
            {"mcpServers": {"`whoami`": {"command": "echo"}}},
            {"mcpServers": {"\x00evil": {"command": "echo"}}},
        ]

        for config in malicious_configs:
            with pytest.raises(ValueError):
                storage.save_local_config(config)


# =============================================================================
# Environment Variable Security
# =============================================================================

class TestEnvironmentVariableSecurity:
    """Test environment variable handling security."""

    def test_env_keys_are_strings(self, temp_mcp_dir):
        """Test that env keys must be strings."""
        storage = UserMCPStorage("security_test")

        # Non-string keys should be rejected
        bad_envs = [
            {123: "value"},
            {None: "value"},
            {True: "value"},
        ]

        for env in bad_envs:
            config = {
                "mcpServers": {
                    "test": {
                        "command": "echo",
                        "env": env
                    }
                }
            }

            with pytest.raises(ValueError, match="must be strings"):
                storage.save_local_config(config)

    def test_env_values_are_strings(self, temp_mcp_dir):
        """Test that env values must be strings."""
        storage = UserMCPStorage("security_test")

        # Non-string values should be rejected
        bad_envs = [
            {"KEY": None},
            {"KEY": 123},
            {"KEY": ["array"]},
            {"KEY": {"object": "value"}},
        ]

        for env in bad_envs:
            config = {
                "mcpServers": {
                    "test": {
                        "command": "echo",
                        "env": env
                    }
                }
            }

            with pytest.raises(ValueError, match="must be strings"):
                storage.save_local_config(config)


# =============================================================================
# Remote Server Headers Security
# =============================================================================

class TestRemoteHeadersSecurity:
    """Test remote server headers security."""

    def test_headers_must_be_dict(self, temp_mcp_dir):
        """Test that headers must be a dictionary."""
        storage = UserMCPStorage("security_test")

        invalid_headers = [
            ["Authorization: Bearer"],
            "Authorization: Bearer",
            123,
            None,
        ]

        for headers in invalid_headers:
            config = {
                "mcpServers": {
                    "api": {
                        "url": "https://api.example.com/mcp",
                        "headers": headers
                    }
                }
            }

            with pytest.raises(ValueError, match="headers must be a dictionary"):
                storage.save_remote_config(config)


# =============================================================================
# Resource Limit Tests
# =============================================================================

class TestResourceLimits:
    """Test resource limits and DoS prevention."""

    def test_backup_rotation_prevents_disk_fill(self, temp_mcp_dir):
        """Test that backup rotation prevents unlimited disk usage."""
        storage = UserMCPStorage("security_test")

        config = {"mcpServers": {"test": {"command": "echo"}}}

        # Create many saves (should rotate backups)
        for _ in range(10):
            storage.save_local_config(config)

        backups = storage.list_backups("mcp.json")

        # Should keep at most 5 backups
        assert len(backups) <= 5

    def test_empty_server_list_allowed(self, temp_mcp_dir):
        """Test that empty server list is valid."""
        storage = UserMCPStorage("security_test")

        empty_config = {"mcpServers": {}}

        # Should not raise
        storage.save_local_config(empty_config)
        storage.save_remote_config(empty_config)


# =============================================================================
# Input Sanitization Tests
# =============================================================================

class TestInputSanitization:
    """Test input sanitization."""

    def test_extra_fields_in_config_ignored(self, temp_mcp_dir):
        """Test that extra fields are preserved but don't cause errors."""
        storage = UserMCPStorage("security_test")

        config = {
            "mcpServers": {
                "test": {
                    "command": "echo",
                    "extra_field": "value",
                    "another_extra": 123
                }
            },
            "unknown_field": "value"
        }

        # Should not raise - extra fields are allowed
        storage.save_local_config(config)

        # Verify saved
        loaded = storage.load_local_config()
        assert loaded["mcpServers"]["test"]["extra_field"] == "value"
