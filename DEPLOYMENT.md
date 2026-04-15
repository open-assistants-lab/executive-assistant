# EA Deployment Architecture

## Overview

Executive Assistant supports two deployment modes:

1. **Self-hosted** — Individual installs EA on their primary device. .dmg (macOS) / .exe (Windows) with sandboxed CLIs. Zero terminal needed.
2. **Hosted server** — Team/enterprise deployment. Each user gets their own container on a shared server. Could be open-sourced for self-managed team deployment.

Both modes share the same codebase. The only difference is where data lives and how CLIs run.

---

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                     SELF-HOSTED (Individual)                     │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  EA.app / EA.exe                                           │ │
│  │  ┌──────────────┐  ┌─────────────┐  ┌──────────────────┐ │ │
│  │  │ EA Server    │  │ SQLite +     │  │ Firecrawl CLI     │ │ │
│  │  │ (FastAPI)    │  │ ChromaDB    │  │ (bundled Node)    │ │ │
│  │  │              │  │ (per-user)   │  │                   │ │ │
│  │  │              │  │             │  │ Browser-Use CLI   │ │ │
│  │  │              │  │             │  │ OR Agent-Browser   │ │ │
│  │  │              │  │             │  │ (bundled Rust)    │ │ │
│  │  │              │  │             │  │                   │ │ │
│  │  │              │  │             │  │ Playwright +      │ │ │
│  │  │              │  │             │  │ Chromium           │ │ │
│  │  └──────────────┘  └─────────────┘  └──────────────────┘ │ │
│  │                                                             │ │
│  │  data/users/{user_id}/                                     │ │
│  │  ├── email/emails.db                                       │ │
│  │  ├── contacts/contacts.db                                  │ │
│  │  ├── todos/todos.db                                        │ │
│  │  ├── conversation/messages.db                             │ │
│  │  ├── memory/                                               │ │
│  │  ├── skills/                                               │ │
│  │  ├── subagents/                                            │ │
│  │  ├── .mcp.json                                             │ │
│  │  └── workspace/                                            │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                       │
│  │ Desktop 2 │  │  Laptop  │  │  Phone   │                       │
│  │ (thin    │  │ (thin    │  │ (thin   │  ── All connect via    │
│  │  client) │  │  client) │  │  client)│     mesh VPN / LAN    │
│  └──────────┘  └──────────┘  └──────────┘     to primary       │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                      HOSTED SERVER (Team)                        │
│                                                                  │
│  ┌────────────────────────────────┐  ┌────────────────────────┐ │
│  │  Admin Panel (open source)     │  │  Traefik / Nginx      │ │
│  │  - User management             │  │  - TLS termination     │ │
│  │  - API key management          │  │  - Reverse proxy       │ │
│  │  - Audit logs                  │  │  - Per-user routing    │ │
│  │  - Cost tracking              │  │                        │ │
│  └────────────────────────────────┘  └────────────────────────┘ │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ Alice's       │  │ Bob's        │  │ Carol's       │  ...   │
│  │ Container     │  │ Container    │  │ Container     │         │
│  │ ┌────────────┐│  │ ┌────────────┐│  │ ┌────────────┐│         │
│  │ │EA Server   ││  │ │EA Server   ││  │ │EA Server   ││         │
│  │ │SQLite+Chrom││  │ │SQLite+Chrom││  │ │SQLite+Chrom││         │
│  │ │Agent-Browse││  │ │Agent-Browse││  │ │Agent-Browse││         │
│  │ │Firecrawl   ││  │ │Firecrawl   ││  │ │Firecrawl   ││         │
│  │ │(self-host) ││  │ │(self-host) ││  │ │(self-host) ││         │
│  │ └────────────┘│  │ └────────────┘│  │ └────────────┘│         │
│  │ data/alice/   │  │ data/bob/     │  │ data/carol/   │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Shared Services                                          │   │
│  │ ├── Firecrawl (self-hosted Docker — shared instance)     │   │
│  │ ├── Redis (session management, rate limiting)             │   │
│  │ └── Headscale (mesh VPN for desktop proxy, optional)    │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

---

## Self-Hosted (Individual)

### Install methods

| Method | Who | How |
|--------|-----|-----|
| **.dmg** (macOS) | Non-technical users | Drag EA.app to Applications. Double-click. Done. |
| **.exe** (Windows) | Non-technical users | Run installer. Done. |
| **pip** | Developers | `pip install -e ".[cli,http]"` then `ea http` |
| **Docker** | Self-hosters | `docker compose up` |

### .app / .exe bundle contents

```
EA.app (macOS)                           EA.exe (Windows)
├── Contents/                             ├── EA/
│   ├── MacOS/ea                          │   ├── ea.exe
│   │   ├── Python runtime                │   │   ├── Python runtime
│   │   └── src/ (your code)              │   │   └── src/ (your code)
│   ├── Resources/                        │   └── resources/
│   │   ├── agent-browser/               │       ├── agent-browser/
│   │   │   └── bin/agent-browser         │       │   └── agent-browser.exe
│   │   │       (standalone Rust binary)  │       │       (standalone Rust binary)
│   │   ├── firecrawl/                   │       ├── firecrawl/
│   │   │   └── bin/firecrawl             │       │   └── firecrawl.exe
│   │   │       (pkg'd Node.js binary)    │       │       (pkg'd Node.js binary)
│   │   └── playwright/                  │       └── playwright/
│   │       └── chromium/                │           └── chromium/
│   │           (headless browser, ~350MB)│               (headless browser)
│   └── data/                             │
│       (user data, symlinked to          │
│        ~/Library/Application Support/)  │
```

### Installation experience

```
1. Download EA.dmg from website (or brew install --cask ea)
2. Drag EA.app to Applications
3. Launch EA.app
4. Onboarding wizard:
   - "Enter your LLM API key" (Anthropic/OpenAI/Ollama)
   - "Enter Firecrawl API key" (optional, or use self-hosted URL)
   - "Choose browser tool" (Agent-Browser / Browser-Use CLI)
5. EA starts HTTP server on localhost:8080
6. Browser opens http://localhost:8080 — or Flutter desktop app connects
7. All CLIs work. Zero terminal. Zero Node.js install. Zero Python install.
```

### CLI sandboxing

Each CLI is bundled inside the app. The `CLIToolAdapter` resolves binaries by checking bundled paths before system PATH:

```python
class CLIToolAdapter:
    cli_name: str

    def _find_binary(self) -> str | None:
        # 1. Bundled path (inside .app / .exe)
        bundled = self._bundled_path()
        if bundled and os.path.isfile(bundled):
            return bundled

        # 2. System PATH (dev mode, globally installed)
        return shutil.which(self.cli_name)

    def _bundled_path(self) -> str | None:
        """Resolve binary path inside the app bundle."""
        if sys.platform == "darwin":
            base = Path(sys.executable).parent.parent / "Resources"
        elif sys.platform == "win32":
            base = Path(sys.executable).parent / "resources"
        else:
            base = Path(sys.executable).parent / "resources"

        return str(base / self.cli_name / "bin" / self.cli_name)
```

### Can users install additional CLIs?

Yes, via a config-driven plugin system:

```yaml
# ~/.ea/config.yaml  (or ~/Library/Application Support/EA/config.yaml)

clis:
  # Bundled CLIs (come with the app)
  agent-browser:
    auto: true          # auto-detected from bundle
  firecrawl:
    auto: true

  # Additional CLIs (user installs themselves)
  ffmpeg:
    binary: /opt/homebrew/bin/ffmpeg
    description: "Video and audio processing"
  pandoc:
    binary: /usr/local/bin/pandoc
    description: "Document format conversion"
  gh:
    binary: /opt/homebrew/bin/gh
    description: "GitHub CLI"
```

The tool registry scans for additional CLIs at startup:

```python
# In native_tools.py
def _register_user_clis(registry: ToolRegistry, config_path: Path) -> None:
    """Register additional CLI tools from user config."""
    config = load_config(config_path)
    for name, cli_config in config.get("clis", {}).items():
        if cli_config.get("auto") or cli_config.get("binary"):
            # Create a generic CLI tool wrapper
            tool = create_cli_tool(name, cli_config)
            registry.register(tool)
```

This lets power users add any CLI they want — ffmpeg, pandoc, gh, kubectl — and EA automatically creates tool wrappers with proper annotations (read-only, destructive, etc. based on config).

### Multi-device (primary + companions)

For self-hosted users with multiple devices:

| Device | Role | Data | CLIs | Connection |
|--------|------|------|------|------------|
| Primary desktop | Full EA | Local SQLite/ChromaDB | Full (firecrawl, browser, shell, filesystem) | Runs EA server |
| Other desktop | Thin client | None | None | Connects to primary via LAN or Tailscale |
| Phone | Thin client | None | None | Connects to primary via Tailscale |

Tailscale/Headscale provides:
- Auto-discovery (devices find each other by name)
- WireGuard encryption
- No port forwarding needed
- Works across LAN and WAN

When the primary desktop is offline, companions lose access. This is acceptable for individual users — they can always use EA directly on the primary.

### Sync between desktops (optional)

For users who want their data available when their primary is offline, offer a hosted migration path (see below). There is no desktop-to-desktop sync — that path leads to SQLite corruption and merge conflicts.

---

## Hosted Server (Team / Open Source)

### Architecture

Each user gets their own Docker container running the same EA binary. The only difference from self-hosted: data lives on the server, and some tools (filesystem, shell) are disabled or scoped.

```
┌──────────────────────────────────────────────────┐
│  Hosted Server (VPS or on-prem)                  │
│                                                  │
│  ┌────────────────────────────────────────────┐  │
│  │ ea-admin (FastAPI + Dashboard)            │  │
│  │ - User CRUD (create, delete, suspend)     │  │
│  │ - API key management (LLM keys per team)  │  │
│  │ - Policy engine (allowed models, tools)   │  │
│  │ - Audit log ingestion                     │  │
│  │ - Container lifecycle (start/stop/scale)  │  │
│  │ - Billing / usage tracking                 │  │
│  └────────────────────────────────────────────┘  │
│                                                  │
│  ┌──────────────┐ ┌──────────────┐              │
│  │ alice-ea     │ │ bob-ea       │  (per-user   │
│  │ :8081        │ │ :8082        │   containers)│
│  └──────┬───────┘ └──────┬──────┘              │
│         │                 │                      │
│  ┌──────┴─────────────────┴──────────────────┐  │
│  │ Traefik (reverse proxy + TLS)              │  │
│  │ alice.ea.example.com → :8081              │  │
│  │ bob.ea.example.com   → :8082              │  │
│  └────────────────────────────────────────────┘  │
│                                                  │
│  ┌────────────────────────────────────────────┐  │
│  │ Shared Services                            │  │
│  │ ┌─────────┐  ┌──────────┐  ┌───────────┐ │  │
│  │ │Firecrawl│  │ Redis    │  │ Headscale  │ │  │
│  │ │(self-   │  │ (rate    │  │ (optional  │ │  │
│  │ │ hosted) │  │  limit)  │  │  mesh VPN)│ │  │
│  │ └─────────┘  └──────────┘  └───────────┘ │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

### Per-user container spec

```yaml
# docker-compose.alice.yml
services:
  alice-ea:
    image: executive-assistant:latest
    restart: unless-stopped
    mem_limit: 2g
    cpus: 2.0
    env_file: users/alice/.env
    volumes:
      - users/alice/data:/app/data        # their entire data/
    ports:
      - "127.0.0.1:8081:8080"
    environment:
      - EA_DEPLOYMENT=team
      - EA_AUTH_JWT_SECRET=${JWT_SECRET}
      - EA_FIRECRAWL_URL=http://firecrawl:3002
      - EA_BROWSER_TOOL=playwright         # not CLI
      - EA_ADMIN_URL=http://ea-admin:8090
```

### What changes in team mode

| Aspect | Self-hosted | Team/hosted |
|--------|-------------|-------------|
| **Deployment** | Local .dmg | Docker container per user |
| **Data** | Local SQLite/ChromaDB per user | Same — but on server |
| **Firecrawl** | CLI (local) or API key | Self-hosted Firecrawl Docker (shared) |
| **Browser** | Agent-Browser CLI (local) | Playwright direct (on server) |
| **Filesystem/shell** | Full access to local files | Scoped to container `/app/data/` only |
| **Auth** | None (localhost) | JWT (shared secret per user) |
| **Config** | `config.yaml` local | Fetched from admin API on startup |
| **Audit** | Local JSON logs | Pushed to admin API |
| **Model/API keys** | User's own | Team-shared (admin panel manages) |

### Deployment config detection

```python
# src/config/settings.py
class DeploymentMode(str, Enum):
    SOLO = "solo"      # Individual, local
    TEAM = "team"      # Hosted, per-user container

class Settings(BaseSettings):
    deployment: DeploymentMode = DeploymentMode.SOLO

    # Solo settings
    firecrawl_url: str | None = None      # None = use CLI
    browser_tool: str = "agent-browser"   # agent-browser | browser-use | playwright

    # Team settings
    admin_url: str | None = None          # Team admin API
    auth_jwt_secret: str | None = None    # JWT for team mode
```

At runtime, tools detect the mode:

```python
# src/sdk/tools_core/firecrawl.py (simplified)
def scrape_url(url: str, user_id: str = "default") -> str:
    settings = get_settings()

    if settings.deployment == "team" and settings.firecrawl_url:
        # Self-hosted Firecrawl (shared instance on server)
        return _api_scrape(url, base_url=settings.firecrawl_url)
    else:
        # Solo mode — use CLI (bundled or system)
        return _cli_scrape(url)
```

### Migration from self-hosted to hosted

```bash
# On user's desktop (one-time):
$ ea export --output alice-backup.tar.gz
  # Creates tarball of data/users/alice/ + config + skills + subagents

# On hosted server:
$ ea import --input alice-backup.tar.gz --user alice
  # Restores to container volume
  # Creates user in admin panel
  # Starts container

# User's devices now connect to:
#   alice.ea.example.com (or app.ea.example.com/alice)
```

No sync complexity. The hosted container becomes the new primary. The desktop becomes a thin client.

### Hosted server — what the open source project provides

The entire hosted server setup is open source:

```
ea-hosted/
├── docker-compose.yml              # Production compose
├── docker-compose.dev.yml          # Development compose
├── ea-admin/                       # Admin panel (FastAPI + React)
│   ├── api/
│   │   ├── users.py               # User CRUD
│   │   ├── auth.py                 # JWT auth
│   │   ├── config.py              # Team config management
│   │   └── audit.py               # Audit log ingestion
│   └── dashboard/                 # React admin UI
├── ea-proxy/                       # Traefik config
│   ├── traefik.yml
│   └── dynamic/
├── scripts/
│   ├── add-user.sh                # Provision a new user container
│   ├── remove-user.sh             # Deprovision
│   └── backup.sh                  # Per-user backup
└── README.md
```

Teams can self-host this on their own VPS or on-prem. We also offer a managed version (ea.cloud) for teams that don't want to manage infrastructure.

---

## Browser Tool Comparison: Agent-Browser vs Browser-Use CLI

### Agent-Browser (Vercel Labs) — RECOMMENDED

| Aspect | Details |
|--------|---------|
| **License** | Apache 2.0 |
| **Runtime** | Pure Rust binary. No Node.js, no Python. Standalone. |
| **Architecture** | Rust CLI + Rust daemon (CDP directly). No Playwright dependency. |
| **Size** | ~15MB Rust binary + ~350MB Chromium |
| **Install** | `npm install -g agent-browser`, `brew install agent-browser`, or `cargo install` |
| **Speed** | ~50ms command latency (daemon persists between calls) |
| **Sessions** | Multiple isolated browser instances with separate auth/state |
| **Token cost** | Compact text snapshot (~200-400 tokens vs ~3000-5000 for full DOM) |
| **Ref system** | `snapshot -i` returns `@e1`, `@e2` refs. `click @e2`. Deterministic. |
| **Security** | Built-in domain allowlist, action policy, content boundaries |
| **iOS testing** | Controls real Mobile Safari via iOS Simulator |
| **50+ commands** | Navigation, forms, screenshots, network, storage, clipboard, diff, etc. |
| **Cloud providers** | Can use Browserless, Browserbase, Browser-Use Cloud as backends |
| **Batch mode** | `batch "cmd1" "cmd2"` or pipe JSON from stdin |
| **Dashboard** | Built-in web dashboard for monitoring sessions |

### Browser-Use CLI

| Aspect | Details |
|--------|---------|
| **License** | MIT |
| **Runtime** | Python + Playwright. Requires Python 3.11+. |
| **Architecture** | Python CLI + Playwright daemon. |
| **Size** | ~200MB Python venv + ~350MB Chromium + ~500MB Playwright deps |
| **Install** | `curl -fsSL https://browser-use.com/cli/install.sh \| bash` or `pip install browser-use` |
| **Speed** | ~50ms command latency (multi-session daemon) |
| **Sessions** | Multiple isolated sessions with `--session` flag |
| **Token cost** | JSON output, larger than agent-browser's compact format |
| **Ref system** | `state` command returns element indices. `click <index>`. Less deterministic. |
| **Security** | No built-in security features |
| **iOS testing** | Not supported |
| **~20 commands** | Navigation, interaction, tabs, screenshots, eval, wait |
| **Cloud** | `browser-use cloud connect` for zero-config cloud browser |
| **AI decision** | The CLI itself is agent-driven — it decides what to click based on LLM |

### Why Agent-Browser wins for EA

1. **No Python dependency** — Pure Rust binary. Bundles easily into .dmg/.exe. Browser-Use requires a full Python runtime alongside EA's own Python.

2. **Smaller bundle** — ~15MB vs ~200MB for Browser-Use's Python deps.

3. **Better for agent loops** — EA's agent loop already decides what to click. We don't need Browser-Use's built-in LLM decision-making. Agent-Browser gives us compact, deterministic snapshots that our agent can parse efficiently.

4. **50+ commands vs 20** — Agent-Browser covers more edge cases (clipboard, drag, network interception, PDF, diff, device emulation, iOS).

5. **Security** — Domain allowlists, action policies, content boundaries. Important for team deployments where you want to restrict what the browser can access.

6. **Token efficiency** — 200-400 tokens per snapshot vs 3000-5000 for full DOM. Directly impacts LLM cost and speed.

7. **iOS testing** — Agent-Browser can control real Mobile Safari. Future feature for mobile app testing.

### Migration from Browser-Use to Agent-Browser

The `CLIToolAdapter` pattern makes this straightforward:

```python
# src/sdk/tools_core/browser_use.py — rename to browser.py

class BrowserCLI(CLIToolAdapter):
    cli_name = "agent-browser"  # was: "browser-use"
    install_hint = "brew install agent-browser"
    # OR: bundled binary inside .app

_bu = BrowserCLI()
```

Commands map cleanly:

| Browser-Use CLI | Agent-Browser | Notes |
|-----------------|---------------|-------|
| `browser-use open <url>` | `agent-browser open <url>` | Same |
| `browser-use state` | `agent-browser snapshot -i` | Agent-Browser gives refs |
| `browser-use click <index>` | `agent-browser click @<ref>` | Refs replace indices |
| `browser-use input <index> "text"` | `agent-browser fill @<ref> "text"` | Same |
| `browser-use type "text"` | `agent-browser type "text"` | Same |
| `browser-use keys "Enter"` | `agent-browser press Enter` | Same |
| `browser-use scroll down` | `agent-browser scroll down` | Same |
| `browser-use screenshot` | `agent-browser screenshot` | Same |
| `browser-use eval "js"` | `agent-browser eval "js"` | Same |
| `browser-use get title` | `agent-browser get title` | Same |
| `browser-use get text` | `agent-browser get text` | Same |
| `browser-use sessions` | `agent-browser session list` | Same |
| `browser-use close --all` | `agent-browser close --all` | Same |

The key difference: **refs replace indices**. Browser-Use returns `{index: 5}`, Agent-Browser returns `[ref=e5]`. Both are used the same way (`click @e5` vs `click 5`), but refs are deterministic across snapshots while indices can shift.

---

## Firecrawl Self-Hosting

For team deployment, run Firecrawl as a shared Docker service:

```yaml
# docker-compose.yml (shared services)
services:
  firecrawl:
    image: mendableai/firecrawl:latest
    ports:
      - "3002:3002"
    environment:
      - PORT=3002
      - HOST=0.0.0.0
      - USE_DB_AUTHENTICATION=false
      - REDIS_URL=redis://redis:6379
      - PLAYWRIGHT_MICROSERVICE_URL=http://playwright-service:3000/scrape
    volumes:
      - firecrawl_data:/app/data

  playwright-service:
    build: apps/playwright-service
    ports:
      - "3000:3000"

  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
```

EA containers point to the shared instance:

```yaml
# In each user's .env
EA_FIRECRAWL_URL=http://firecrawl:3002
```

Resource cost: ~2GB RAM for the Firecrawl stack (API server + Playwright microservice + Redis).

---

## Resource Estimates

### Self-hosted (individual)

| Component | RAM | Disk |
|-----------|-----|------|
| EA server | ~200MB | ~100MB |
| Python runtime | ~50MB | ~200MB |
| Agent-Browser (Rust binary + Chromium) | ~500MB active | ~400MB |
| Firecrawl (Node.js binary) | ~100MB | ~80MB |
| SQLite + ChromaDB | ~200MB active | Varies |
| **Total** | **~1-2GB active** | **~800MB + user data** |

### Hosted server (per user)

| Component | RAM | Disk |
|-----------|-----|------|
| EA container | ~500MB | ~500MB + user data |
| Playwright + Chromium | ~500MB when active | ~350MB |
| SQLite + ChromaDB | ~200MB | Varies |
| **Total per user** | **~1.2GB active** | **~1GB + user data** |
| **20 users** | **~24GB** | **~20GB + data** |
| **VPS cost** | **~$80-120/mo** | (8 vCPU, 32GB RAM) |

---

## Implementation Priority

| Phase | What | Mode |
|-------|------|------|
| **Now** | Swap Browser-Use CLI → Agent-Browser in EA | Self-hosted |
| **Next** | Build .dmg / .exe bundle (PyInstaller + bundled CLIs) | Self-hosted |
| **Next** | Dockerize EA (single-user Dockerfile) | Foundation for hosted |
| **Next** | Auth layer (JWT) for HTTP API | Both |
| **Later** | `ToolBackend` abstraction (CLI vs API vs Playwright-direct) | Both |
| **Later** | ea-admin panel (user management, config, audit) | Hosted |
| **Later** | `ea export` / `ea import` for migration | Self-hosted → Hosted |
| **Later** | Multi-user compose + Traefik | Hosted |
| **Later** | Litestream for SQLite replication (optional) | Self-hosted with sync |