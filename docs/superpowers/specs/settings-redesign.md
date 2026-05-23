# Settings & Connectors Redesign

## Overview

Split settings into two entry points in the sidebar:

| Icon | Entry | What it opens |
|------|-------|---------------|
| `Symbols.cable` / 🔌 | Conectors | Connectors modal (LLM Providers + Services tabs) |
| `Symbols.tune` / ⚙️ | Ajustes | Compact Settings dialog |

## Settings Dialog (`Symbols.tune`)

A compact dialog, not a full page. Fields:

- **Server URL** — text field (default `http://localhost:8000`)
- **Default Model** — dropdown. Shows models from **configured** providers only (providers where user entered an API key). Below the dropdown: `Manage providers →` text button → opens Connectors modal to LLM Providers tab.
- **About** — version, data directory path

**Manage providers → bridge:**
- Settings dialog is dismissed when "Manage providers →" is clicked
- Connectors modal opens immediately, switches to **LLM Providers tab**
- When Connectors modal is closed, Settings re-opens (or user can just close Connectors; they know where to find Settings)

## Connectors Modal (`Symbols.cable` / 🔌)

Full-screen modal with two tabs.

### Tab 1: LLM Providers

**Search bar** at top — filters both provider name and model names.

**Tree view** — each provider is expandable:

- **Collapsed**: provider name + status badge (🔑 configured / ⚠️ needs key)
- **Expanded (no key)**: API key text field + "Save" button. Model list is hidden until key is saved.
- **Expanded (has key)**: Radio button list of models. Selected model is highlighted.

At the bottom: **"Set as default"** button (writes to `config.yaml` default_model field).

### Tab 2: Services (Connectors)

**Search bar** + **category chips** (Productivity, Dev Tools, Finance, AI/ML, Communication, etc.).

**List**: each connector row shows icon + name + description + status. Connected services are pinned to top.

**Connect flow** (click a disconnected service):
- Dynamic form based on ConnectKit spec's `auth_type`:
  - **OAuth2**: "Sign in" button (default app) + optional "Use my app" expandable fields (client_id, client_secret, scopes)
  - **API key**: single text field
  - **Basic**: username + password fields
  - **None**: just "Connect" button

**Disconnect**: confirmation dialog, then removes credentials.

## Data Flow

```
Connectors Modal

  Tab 1: LLM tab
    ├─ Registry (4172 models, filterable)
    ├─ User adds API key → saved to vault
    ├─ User selects model → saved to provider.model config
    └─ "Set as default" → writes config.yaml default_model

  Tab 2: Services tab
    └─ ConnectKit auth flow → creates credential vault entry

Settings Dialog
    └─ Reads provider config (keys + models) → populates dropdown
         └─ "Manage providers →" opens Connectors → LLM tab
```

## Key Decisions

- Settings stays compact; provider configuration lives in Connectors.
- "Manage providers" link bridges the two without bloating Settings.
- LLM Providers tab uses tree view (expandable provider cards) rather than a flat list — avoids overwhelming user with 4172 rows.
- Connector auth flows are dynamic forms rendered from spec, not hardcoded per service.
