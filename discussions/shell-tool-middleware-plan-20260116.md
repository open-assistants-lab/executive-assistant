# ShellToolMiddleware Implementation Plan

## Objective

Add LangChain's `ShellToolMiddleware` with `HostExecutionPolicy()` to enable shell command execution within a thread-scoped workspace directory (`data/users/{thread_id}/files`).

**Reference:** [LangChain Built-in Middleware - Shell Tool](https://docs.langchain.com/oss/python/langchain/middleware/built-in#shell-tool)

---

## Why ShellToolMiddleware?

- **Persistent shell session** - Commands can set state (cd, environment variables) that persists across calls
- **Sequential execution** - Multiple commands can build on each other (e.g., `git clone`, `cd`, `make`)
- **Integration with Python** - Works alongside `execute_python` in the same workspace
- **Developer experience** - Natural shell operations for file management, git, package installation

### What Shell Brings That Python Doesn't

| Category | Shell Examples | Python Equivalent |
|----------|----------------|------------------|
| **Version control** | `git clone`, `git status`, `git commit` | Needs `gitpython` library |
| **Package management** | `pip install`, `npm install`, `cargo build` | Needs subprocess (blocked in sandbox) |
| **File operations** | `curl`, `wget`, `rsync`, `find` | Limited module whitelist |
| **Data processing** | `jq`, `awk`, `sed`, `ripgrep` | Needs external libraries |
| **Media** | `ffmpeg`, `convert` (ImageMagick) | Needs `ffmpeg-python`, `wand` |
| **Chaining** | `curl url \| jq '.data' \| head -5` | Complex in Python |

**Complementary use:**
- **Shell** → System operations, external tools, quick workflows
- **Python** → Complex logic, data analysis, calculations, ML

---

## Architecture

### Workspace Isolation

```
data/users/{thread_id}/files/     # Thread-scoped workspace
  ├── project/                    # Shell can navigate and create subdirectories
  ├── .venv/                      # Can create virtual environments
  └── output.csv                  # Python and shell share files
```

### Execution Flow

```
User Message
    ↓
LangChain Agent
    ↓
ShellToolMiddleware (per-thread bash session)
    ├── workspace_root: data/users/{thread_id}/files
    ├── execution_policy: HostExecutionPolicy()
    └── shell: /bin/bash
```

---

## Implementation Steps

### 1. Add Settings (`src/executive_assistant/config/settings.py`)

```python
# ShellToolMiddleware (HostExecutionPolicy - runs in same container)
MW_SHELL_ENABLED: bool = False  # Disabled by default (security)
MW_SHELL_COMMAND_TIMEOUT: float = 30.0  # Command timeout in seconds
MW_SHELL_MAX_OUTPUT_LINES: int = 100  # Max output lines to capture
MW_SHELL_CPU_TIME_SECONDS: int | None = 60  # CPU time limit via resource.prlimit
MW_SHELL_MEMORY_BYTES: int | None = 512_000_000  # Memory limit (512MB) via resource.prlimit
MW_SHELL_STARTUP_COMMANDS: list[str] = []  # Commands to run on session start
MW_SHELL_ENV: dict[str, str] = {}  # Environment variables for shell session

# Optional: Switch to DockerExecutionPolicy for stronger isolation
MW_SHELL_USE_DOCKER: bool = False  # Set true for container-per-command isolation
MW_SHELL_DOCKER_IMAGE: str = "python:3.12-slim"  # Container image for DockerExecutionPolicy
MW_SHELL_DOCKER_NETWORK: bool = False  # Network access in container
```

### 2. Wire Up Middleware (`src/executive_assistant/agent/langchain_agent.py`)

```python
from langchain.agents.middleware import ShellToolMiddleware, HostExecutionPolicy, DockerExecutionPolicy

def _build_middleware(model, thread_id: str | None = None):
    middleware = [... existing middleware ...]

    # Shell tool middleware (thread-scoped workspace)
    if settings.MW_SHELL_ENABLED and thread_id:
        from executive_assistant.storage.file_storage import get_thread_files_path

        workspace = get_thread_files_path(thread_id)

        # Choose execution policy based on settings
        if settings.MW_SHELL_USE_DOCKER:
            # Strong isolation: each command runs in ephemeral container
            policy = DockerExecutionPolicy(
                command_timeout=settings.MW_SHELL_COMMAND_TIMEOUT,
                max_output_lines=settings.MW_SHELL_MAX_OUTPUT_LINES,
                image=settings.MW_SHELL_DOCKER_IMAGE,
                network_enabled=settings.MW_SHELL_DOCKER_NETWORK,
                memory_bytes=settings.MW_SHELL_MEMORY_BYTES,
                cpus="2.0",
                read_only_rootfs=True,
                extra_run_args=[
                    f"-v{workspace}:/workspace:rw",
                    "-w", "/workspace",
                    "--security-opt", "no-new-privileges",
                ],
            )
        else:
            # Default: run in same container with resource limits
            policy = HostExecutionPolicy(
                command_timeout=settings.MW_SHELL_COMMAND_TIMEOUT,
                max_output_lines=settings.MW_SHELL_MAX_OUTPUT_LINES,
                cpu_time_seconds=settings.MW_SHELL_CPU_TIME_SECONDS,
                memory_bytes=settings.MW_SHELL_MEMORY_BYTES,
            )

        middleware.append(
            ShellToolMiddleware(
                workspace_root=str(workspace),
                execution_policy=policy,
                startup_commands=settings.MW_SHELL_STARTUP_COMMANDS,
                env=settings.MW_SHELL_ENV,
                shell_command=["/bin/bash", "-i"],
            )
        )

    return middleware
```

### 3. Update `.env.example`

```bash
# ShellToolMiddleware (disabled by default - security risk!)
# Default: HostExecutionPolicy (runs in same container)
MW_SHELL_ENABLED=false
MW_SHELL_COMMAND_TIMEOUT=30.0
MW_SHELL_MAX_OUTPUT_LINES=100
MW_SHELL_CPU_TIME_SECONDS=60
MW_SHELL_MEMORY_BYTES=512000000

# Optional: DockerExecutionPolicy for stronger isolation
# MW_SHELL_USE_DOCKER=true
# MW_SHELL_DOCKER_IMAGE=python:3.12-slim
# MW_SHELL_DOCKER_NETWORK=false

# Shell session setup
MW_SHELL_STARTUP_COMMANDS=[]
MW_SHELL_ENV={}
```

### 4. Update Prompts (`src/executive_assistant/agent/prompts.py`)

Add guidance for shell usage:

```markdown
**Shell Commands**

Execute shell commands in your workspace directory (data/users/{thread_id}/files).

Tools: run_shell, execute_python

Shell capabilities:
- File operations: ls, cp, mv, rm, mkdir, find
- Git operations: clone, status, commit, push, pull
- Package management: pip, npm, cargo (if installed)
- Data processing: awk, sed, grep, jq

Example workflow:
1. run_shell("git clone https://github.com/user/repo")
2. run_shell("cd repo && pip install -r requirements.txt")
3. execute_python("import repo; print(repo.run_analysis())")
```

### 5. Tests (`tests/test_langchain_agent_unit.py`)

```python
def test_shell_middleware_when_enabled(monkeypatch):
    """ShellToolMiddleware should be included when enabled."""
    from langchain.agents.middleware import ShellToolMiddleware

    monkeypatch.setattr(settings, "MW_SHELL_ENABLED", True)
    monkeypatch.setattr(settings, "MW_SUMMARIZATION_ENABLED", False)
    # ... disable other middleware ...

    middleware = _build_middleware(ToolBindingFakeChatModel(messages=iter([])), thread_id="test-thread")
    assert any(isinstance(m, ShellToolMiddleware) for m in middleware)

def test_shell_middleware_disabled_by_default(monkeypatch):
    """ShellToolMiddleware should NOT be included when disabled (default)."""
    from langchain.agents.middleware import ShellToolMiddleware

    monkeypatch.setattr(settings, "MW_SHELL_ENABLED", False)
    # ... disable other middleware ...

    middleware = _build_middleware(ToolBindingFakeChatModel(messages=iter([])), thread_id="test-thread")
    assert not any(isinstance(m, ShellToolMiddleware) for m in middleware)
```

---

## Docker Deployment Considerations

### docker-compose.yml (HostExecutionPolicy - Default)

```yaml
services:
  executive_assistant:
    build: .
    # Resource limits apply to entire container including shell commands
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M
    # Volume for persistent data
    volumes:
      - ./data:/app/data
    # Security options
    security_opt:
      - no-new-privileges:true
    environment:
      - MW_SHELL_ENABLED=true
      - MW_SHELL_COMMAND_TIMEOUT=30.0
      - MW_SHELL_CPU_TIME_SECONDS=60
      - MW_SHELL_MEMORY_BYTES=512000000
```

### docker-compose.yml (DockerExecutionPolicy - Strict Mode)

```yaml
services:
  executive_assistant:
    build: .
    # Need Docker-in-Docker for DockerExecutionPolicy
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./data:/app/data
    environment:
      - MW_SHELL_ENABLED=true
      - MW_SHELL_USE_DOCKER=true
      - MW_SHELL_DOCKER_IMAGE=executive_assistant-shell:latest
      - MW_SHELL_DOCKER_NETWORK=false
```

### Dockerfile

```dockerfile
# Install common shell utilities
RUN apt-get update && apt-get install -y \
    bash \
    curl \
    git \
    jq \
    ripgrep \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for running the app
RUN useradd -m -u 1000 executive_assistant
USER executive_assistant
WORKDIR /app
```

---

## Security Concerns & Mitigations

| Concern | Mitigation |
|---------|------------|
| **Command injection** | Agent controls commands; no user input directly passed to shell |
| **Path traversal** | `workspace_root` confines shell to thread directory |
| **Resource exhaustion** | Timeout + CPU/memory limits via `resource.prlimit` |
| **Network access** | Same as execute_python (both can make network requests) |
| **File system escape** | Run as non-root user; already in Docker container |
| **Secret exfiltration** | Don't enable in multi-tenant environments without isolation |

### Security Model Consistency

| Tool | Runs Where | Network Access | Isolation |
|------|------------|----------------|-----------|
| `execute_python` | In-process | Yes (via urllib) | Module whitelist |
| `run_shell` (Host) | In-process | Yes (curl, wget) | Resource limits |
| `run_shell` (Docker) | Per-command container | Configurable | Strong isolation |

**Key point:** With `execute_python` already in-process and capable of network requests, `HostExecutionPolicy` for shell is consistent. Enable `MW_SHELL_USE_DOCKER` only if you need stronger isolation than the current Python sandbox provides.

### Critical Security Notes

1. **Disabled by default** - `MW_SHELL_ENABLED=false`
2. **HostExecutionPolicy is default** - Sufficient for single-user/trusted environments
3. **DockerExecutionPolicy optional** - Enable via `MW_SHELL_USE_DOCKER=true` for stricter isolation
4. **No inter-thread isolation** - All threads run in same container; shell sessions isolated by directory only
5. **Already containerized** - Your deployment is already in Docker, which provides the main isolation boundary

---

## Integration with execute_python

Both tools share the same workspace:

```python
# User: "Download a CSV, analyze it with Python, and save a chart"

# Agent calls:
run_shell("curl -o data.csv https://example.com/data.csv")

execute_python("""
import pandas as pd
import matplotlib.pyplot as plt
df = pd.read_csv('data.csv')
df.plot().savefig('chart.png')
""")

run_shell("ls -lh *.png")  # Shows chart.png
```

---

## Execution Policy API Reference

Based on actual LangChain source code (`langchain/agents/middleware/_execution.py`):

### BaseExecutionPolicy (all policies inherit these)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `command_timeout` | float | 30.0 | Command timeout in seconds |
| `startup_timeout` | float | 30.0 | Shell startup timeout |
| `termination_timeout` | float | 10.0 | Shell termination timeout |
| `max_output_lines` | int | 100 | Maximum output lines to capture |
| `max_output_bytes` | int \| None | None | Maximum output bytes (None = no limit) |

### HostExecutionPolicy (direct host execution)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cpu_time_seconds` | int \| None | None | CPU time limit via `resource.prlimit` |
| `memory_bytes` | int \| None | None | Memory limit via `resource.prlimit` |
| `create_process_group` | bool | True | Create process group for signal handling |

### DockerExecutionPolicy (container isolation)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `binary` | str | "docker" | Docker binary path |
| `image` | str | "python:3.12-alpine3.19" | Container image |
| `remove_container_on_exit` | bool | True | Auto-remove container |
| `network_enabled` | bool | False | Network access in container |
| `extra_run_args` | Sequence[str] \| None | None | Extra `docker run` arguments |
| `memory_bytes` | int \| None | None | Memory limit |
| `cpus` | str \| None | None | CPU limit (e.g., "2.0") |
| `read_only_rootfs` | bool | False | Read-only root filesystem |
| `user` | str \| None | None | User to run as inside container |

### CodexSandboxExecutionPolicy (Codex CLI sandbox)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `binary` | str | "codex" | Codex binary path |
| `platform` | "auto" \| "macos" \| "linux" | "auto" | Platform detection |
| `config_overrides` | Mapping[str, Any] | {} | Codex config overrides |

### ShellToolMiddleware Constructor

```python
ShellToolMiddleware(
    workspace_root: str | Path | None = None,
    startup_commands: tuple[str, ...] | list[str] | str | None = None,
    shutdown_commands: tuple[str, ...] | list[str] | str | None = None,
    execution_policy: BaseExecutionPolicy | None = None,
    redaction_rules: tuple[RedactionRule, ...] | list[RedactionRule] | None = None,
    tool_description: str | None = None,
    tool_name: str = "run_shell",
    shell_command: Sequence[str] | str | None = None,  # e.g., ["/bin/bash", "-i"]
    env: Mapping[str, Any] | None = None,
)
```

---

## Quality Gates

- [ ] ShellToolMiddleware only added when `MW_SHELL_ENABLED=true`
- [ ] `thread_id` is properly passed to middleware builder
- [ ] Workspace directory exists before shell session starts
- [ ] Tests verify both enabled and disabled states
- [ ] Prompts updated to guide shell usage
- [ ] Docker compose includes resource limits
- [ ] Security warnings documented in README

---

## Rollback Strategy

- Runtime toggle: Set `MW_SHELL_ENABLED=false` to disable immediately
- No data migration required (shell sessions are ephemeral)
- Remove middleware from `_build_middleware()` to uninstall

---

## Future Enhancements

1. **Command whitelisting** - Restrict to safe commands only (`ls`, `cat`, `grep`, etc.) via custom redaction rules
2. **Audit logging** - Log all shell commands for security review
3. **Redaction rules** - Sanitize sensitive data (API keys, passwords) from command output
4. **CodexSandboxExecutionPolicy** - For local dev on macOS/Linux with syscall restrictions

---

## Sources

- [LangChain Shell Tool Middleware Documentation](https://docs.langchain.com/oss/python/langchain/middleware/built-in#shell-tool)
- [LangChain Middleware Reference](https://reference.langchain.com/python/langchain/middleware/)
- [LangChain GitHub Issue - ShellToolMiddleware with HIL](https://github.com/langchain-ai/langchain/issues/33684)
- [LangChain Source: shell_tool.py](https://github.com/langchain-ai/langchain/blob/develop/libs/langchain_v1/langchain/agents/middleware/shell_tool.py) - ShellToolMiddleware implementation (865 lines)
- [LangChain Source: _execution.py](https://github.com/langchain-ai/langchain/blob/develop/libs/langchain_v1/langchain/agents/middleware/_execution.py) - Execution policy implementations (385 lines)
