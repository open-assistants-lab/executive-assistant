# EA Deployment Architecture

## Overview

Three deployment tiers, one container image:

```
Solo Desktop               Shared Host                    Dedicated VM
─────────────              ───────────                    ────────────
$0 (your Mac)              $20/user/mo                    $80/user/mo
                              
1 AgentLoop process         1 container/user              1 VM/user
all tools locally           all tools in container        all tools in container  
                              
~/Executive Assistant/     data/users/{id}/              data/users/{id}/
data/users/default_user/   on host volume                on VM disk
                              
auth: none                 auth: JWT                      auth: JWT + SSO
isolation: macOS           isolation: container           isolation: VM
                              
Same codebase, different orchestration.
```

## Standard Tier: Per-User Containers on Shared Host

```
╔════════════════════ Server ═════════════════════╗
║                                                  ║
║  ┌─ Alice Container ──────────────────────────┐  ║     Alice's Mac
║  │  AgentLoop                                 │  ║     ┌─────────────┐
║  │  firecrawl / gws / agent-browser           │  ║     │ Flutter app │
║  │  shell_execute (sandboxed)                 │  ║──WS─│ thin client │
║  │  HybridDB (SQLite + ChromaDB)             │  ║     └─────────────┘
║  │  skills / subagents                        │  ║
║  │  data/users/alice/                          │  ║     Alice's iPhone
║  │  ├── workspace/    (canonical files)        │  ║     ┌─────────────┐
║  │  ├── conversation/                          │  ║──WS─│ Flutter app │
║  │  ├── memory/                                │  ║     └─────────────┘
║  │  ├── contacts/                              │  ║
║  │  ├── email/                                 │  ║
║  │  └── todos/                                 │  ║
║  └─────────────────────────────────────────────┘  ║
║                                                    ║
║  ┌─ Bob Container ──────────────────────────────┐  ║     Bob's Mac
║  │  ...same, data/users/bob/                     │  ║     ┌─────────────┐
║  └───────────────────────────────────────────────┘  ║──WS─│ Flutter app │
║                                                    ║     └─────────────┘
║  ┌─ Gateway (thin FastAPI) ──────────────────────┐  ║
║  │  Auth (JWT)                                   │  ║
║  │  WebSocket routing (client ↔ container)       │  ║
║  │  Container lifecycle (spawn, idle-kill)       │  ║
║  │  Team data proxy                              │  ║
║  └───────────────────────────────────────────────┘  ║
╚══════════════════════════════════════════════════════╝
```

Each container is fully self-contained. The gateway is a thin FastAPI process — auth + routing + container lifecycle. No agent code runs in the gateway.

### Container spec

| Resource | Idle | Active (LLM call + tools) |
|----------|------|---------------------------|
| RAM | ~500MB | ~1.5GB |
| CPU | 0 | 2 vCPU |
| Disk | ~2GB (HybridDB + workspace) | Grows with usage |
| Chromium | — | ~350MB (headless, per session) |

### Host economics

At ~15% concurrent usage (chat 2 min, idle 30 min):

| Host | vCPU | RAM | Cost/mo | Users @ idle | Concurrent |
|------|------|-----|---------|-------------|------------|
| Hetzner CX42 | 8 | 16GB | $16 | 32 | ~10 |
| Hetzner CX52 | 16 | 32GB | $33 | 64 | ~20 |
| Hetzner AX42 | 6+ | 64GB | $50 | 128 | ~40 |

At $20/user/mo, infrastructure cost is negligible (96-98% margin). The real cost is LLM API calls and support.

### Scaling beyond one host

When a single host hits capacity (RAM or concurrent CPU), add hosts behind a load balancer. The gateway becomes stateless — auth state is in JWT, container routing is based on user_id hash. Multiple gateway replicas behind Traefik or nginx.

## Premium Tier: Dedicated VM per User

```
Alice's VM (CX32: 4 vCPU, 8GB)     Bob's VM (CX32: 4 vCPU, 8GB)
┌──────────────────────────────┐   ┌──────────────────────────────┐
│  AgentLoop                   │   │  AgentLoop                   │
│  All CLIs                    │   │  All CLIs                    │
│  HybridDB                    │   │  HybridDB                    │
│  data/users/alice/           │   │  data/users/bob/             │
└──────────────────────────────┘   └──────────────────────────────┘
```

Same container image. Different host. The VM provides:
- Guaranteed CPU/RAM (no noisy neighbors)
- Full OS-level isolation (SOC2/HIPAA auditors happy)
- Custom firewall rules per user
- GPU passthrough for local LLM inference (if desired)

Pricing: Hetzner CX32 at $8/user/mo = 60% margin at $20/user. AWS/GCP dedicated instances = $20-40/user = break-even or loss. Premium tier should be $80-200/user on cloud providers.

## Solo Desktop (Current)

```
Your Mac
┌──────────────────────────────┐
│  EA Server (one process)     │
│  All CLIs locally            │
│  HybridDB locally            │
│  ~/Executive Assistant/      │
│  data/users/default_user/    │
│                              │
│  Auth: none (localhost)      │
└──────────────────────────────┘
        │
        ├──WS── Flutter (macOS)
        ├──WS── Flutter (iPhone, iPad) ← LAN/Tailscale
        └──WS── Flutter (web)
```

Works today. Zero config. The codebase is already built for this.

## Dockerfile (image shared across all tiers)

```dockerfile
FROM python:3.11-slim

# System deps for Chromium, Playwright, firecrawl
RUN apt-get update && apt-get install -y \
    chromium chromium-driver \
    nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv pip install --system -e ".[cli,http]"

# CLI tools
RUN npm install -g firecrawl@latest
RUN pip install agent-browser gws-cli

# App
COPY src/ src/
COPY config.yaml .

# Data volume
VOLUME /data

CMD ["ea", "http", "--host", "0.0.0.0", "--port", "8080"]
```

Per-user containers mount `data/users/{user_id}/` at `/data` via Docker volumes.

## Data Paths (Unified Across All Tiers)

```
data/
├── users/
│   ├── default_user/              # Solo mode
│   │   ├── conversation/
│   │   ├── memory/
│   │   ├── email/
│   │   ├── contacts/
│   │   ├── todos/
│   │   ├── workspace/
│   │   │   └── .versions/
│   │   ├── skills/
│   │   ├── subagents/
│   │   │   ├── agent_defs/
│   │   │   └── work_queue.db
│   │   └── .mcp.json
│   ├── alice@corp.com/            # Multi-tenant
│   │   └── (same structure)
│   └── bob@corp.com/
│       └── (same structure)
├── teams/
│   └── engineering/
│       ├── contacts/
│       ├── skills/
│       ├── memory/
│       ├── files/
│       └── config.yaml
├── cache/
│   └── models.json
├── logs/
└── traces/
```

Solo: `data/users/default_user/`. Multi-tenant: `data/users/{user_id}/`. Same path logic, just the user_id changes. Team data at `data/teams/{team_id}/` only exists in multi-tenant mode.

## Where Each Tool Runs

| Tool | Solo | Container/VM |
|------|------|-------------|
| `files_*` | `~/Executive Assistant/` | `data/users/{user_id}/workspace/` |
| `shell_execute` | Native terminal | Sandboxed in container |
| `firecrawl` | Local CLI | CLI in container |
| `gws` (email/contacts/todos) | Local CLI | CLI in container |
| `agent-browser` | Local Chromium | Headless Chromium in container |
| `memory_*` | HybridDB locally | HybridDB in container |
| `time_get` | Pure Python | Pure Python |

Everything runs inside the container. No MCP bridge needed for tools. Thin clients connect via WebSocket only.

## Auth

| Tier | Auth Method | Identity |
|------|------------|----------|
| Solo Desktop | None (localhost) or API key (LAN) | `user_id="default_user"` |
| Shared Host | JWT | `user_id` + `team_id` from token |
| Dedicated VM | JWT + SSO (SAML/OIDC) | Same |

Server tries JWT decode first, falls back to API key. One `Authorization: Bearer <token>` header.

## Per-User Isolation

| Tier | Mechanism | Bug Risk |
|------|-----------|----------|
| Solo | None needed | N/A |
| Shared Host | Container + per-user volume mount | Container breakout = data leak |
| Dedicated VM | VM hypervisor | VM escape = nation-state level only |

SQLite file-level locking is a non-issue: Alice's container writes `alice/emails.db`, Bob's writes `bob/emails.db`. Different files, zero contention.

## Team Data

Team data at `data/teams/{team_id}/` is mounted read-only into each container. Admin writes to it via a separate admin service (or CLI on the host). Agent picks up changes on next tool call.

Admin writes are safe because WAL mode allows concurrent readers + 1 writer. The admin service is the single writer.

## Container Lifecycle

```
User connects    →    Gateway spawns container if not running
User idle 5 min  →    Gateway sends SIGTERM → container drains → killed
User reconnects  →    Gateway spawns fresh container (data persisted on volume)
```

Containers are ephemeral. Data persists on the host volume. A container crash = AgentLoop restart with state recovery from HybridDB.

## What's Already Done

1. ✅ `DataPaths` — `data/users/{user_id}/` path structure
2. ✅ `DEFAULT_USER_ID = "default_user"` for solo mode
3. ✅ Per-user SQLite + ChromaDB (HybridDB)
4. ✅ All tools SDK-native (81 tools)
5. ✅ `files_*` default workspace: `~/Executive Assistant/` (solo)
6. ✅ WebSocket + HITL + streaming
7. ✅ Flutter app (thin client on macOS, iOS, iPadOS)

## What's Needed for Tiers

| Phase | What | Tier | Effort |
|-------|------|------|--------|
| Now | Solo desktop (current) | Solo | ✅ Done |
| 12 | API key auth for LAN/tailscale | Solo | 2-3 days |
| 13 | Dockerfile + docker-compose | All | 2 days |
| 14 | JWT auth | Shared | 3 days |
| 15 | Gateway (routing + container lifecycle) | Shared | 5-7 days |
| 16 | Team data isolation (read-only mounts) | Shared | 2 days |
| 17 | SSO / SAML | Premium | 5 days |
| 18 | Admin service (provisioning, billing) | Premium | 10-15 days |
