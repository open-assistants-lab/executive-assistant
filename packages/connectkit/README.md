# ConnectKit

> **Purposefully built for AI Agents.** ConnectKit gives agents access to user SaaS accounts — Gmail, Calendar, Drive, GitHub, Slack, and 520+ more — through one YAML file per service. OAuth, API keys, token vault, and tool discovery handled automatically. Used in production by the [Executive Assistant](https://github.com/open-assistants-lab) agent system.

> **Embedded. Local. Open source.** No cloud APIs, no hosted auth services. Runs entirely on-device with an encrypted SQLite credential vault + local YAML specs. Ships as a single Python package with zero external infrastructure dependencies.

**Connect AI agents to SaaS.** One YAML file per service. OAuth, token vault, tool discovery — handled automatically.

```python
from connectkit import ConnectKitBridge

bridge = ConnectKitBridge(user_id="alice")
await bridge.discover()

# Agent gets tools for all connected services
tools = bridge.get_tool_definitions()
# → [google-workspace__gmail_list, github__issue_list, salesforce__soql_query, ...]

# Show the connector catalog
catalog = bridge.list_available()
# → [{name: "google-workspace", connected: true, setup_guide_url: "..."}, ...]
```

## Why ConnectKit?

Every AI agent that needs access to user SaaS accounts ends up wiring three things together: OAuth flows, credential storage, and CLI/MCP tool wrappers. You build `/auth/google/login`, `/auth/google/callback`, token refresh logic, subprocess calls for `gws gmail list`... then you do it again for GitHub, again for Outlook.

ConnectKit does all of that once, done right. One YAML file per service. No Python code per connector.

| Feature | Status |
|---------|--------|
| 524 SaaS connectors (from Nango's 779-provider baseline) | ✅ |
| YAML-based connector spec (no Python code per service) | ✅ |
| Encrypted SQLite credential vault (Fernet) | ✅ |
| Universal OAuth 2.0 router (one endpoint, all services) | ✅ |
| CLI adapter backend (wraps any SaaS CLI) | ✅ |
| MCP adapter backend (connects to MCP servers) | ✅ |
| Dual CLI + MCP support per connector (53+ connectors) | ✅ |
| Connector catalog (list available services + status) | ✅ |
| Agent meta-tools (list, connect, disconnect, health) | ✅ |
| Per-user credential isolation | ✅ |
| Self-hosted support (base_url for self-hosted instances) | ✅ |
| No external API dependencies (works offline) | ✅ |

## Installation

```bash
pip install connectkit
```

## Core Concepts

### One YAML file per service

```yaml
# connectors/google-workspace.yaml
name: google-workspace
display: "Google Workspace"
setup_guide_url: "https://developers.google.com/workspace/guides/create-credentials"
auth:
  type: oauth2
  oauth2:
    authorize_url: https://accounts.google.com/o/oauth2/v2/auth
    token_url: https://oauth2.googleapis.com/token
    scopes:
      - https://www.googleapis.com/auth/gmail.readonly
      - https://www.googleapis.com/auth/calendar.readonly
  required_fields:
    - name: client_id
      label: "Client ID"
      input_type: text
    - name: client_secret
      label: "Client Secret"
      input_type: password
tool_sources:
  - type: cli
    command: gws
    install: npm install -g @googleworkspace/cli
  - type: mcp
    server_name: google-workspace
    command: gws mcp
```

### Auth types

| Type | Use for | Example |
|------|---------|---------|
| `oauth2` | OAuth 2.0 (Google, Microsoft, GitHub, Slack, 234+ services) | Browser authorization → tokens vaulted |
| `api_key` | API keys (Firecrawl, Stripe, Twilio, 288+ services) | Paste key into form → vaulted |
| `none` | No auth needed (local tools) | Auto-connected |

### Tool source backends

| Backend | Count | Best for |
|---------|-------|----------|
| **CLI** | 63 | SaaS with official CLIs (gws, gh, glab, m365, stripe, sf, vercel, etc.) |
| **MCP** | 514 | SaaS with MCP servers (first-party or community) |
| **Dual** (CLI + MCP) | 53 | Best available backend picked at runtime |

### CredentialVault

All tokens are stored in an encrypted SQLite database (Fernet encryption). One vault per user. Master key from `CONNECTKIT_VAULT_KEY` env var.

```python
from connectkit import CredentialVault

vault = CredentialVault("./data/users/alice")
vault.store_token("google-workspace", "oauth2", {
    "access_token": "ya29...", "refresh_token": "1//..."
})
token = vault.get_token("google-workspace")
```

### OAuth flow

```python
# 1. User fills in client_id + client_secret → stored in vault via POST /connectors/connect
# 2. Flutter renders "Connect" button → opens:
#    GET /auth/login?service=google-workspace&user_id=alice
# 3. Browser redirects to Google OAuth → user authorizes
# 4. Google redirects to:
#    GET /auth/callback?code=...&state=...
# 5. Gateway exchanges code for tokens → stores in vault
# 6. Google Workspace: ✅ Connected
```

OAuth states are Fernet-encrypted and self-contained — any vault with the same key can validate them (10-minute TTL).

### Self-Hosted Support

Services like Firecrawl, Sentry, GitLab offer self-hosted deployments. ConnectKit supports them with an optional `base_url` field:

```yaml
required_fields:
  - name: base_url
    label: "Self-Hosted URL"
    placeholder: "https://firecrawl.example.com"
    input_type: url
    help_text: "Leave empty for cloud version"
    optional: true
```

## Connector Catalog

| Category | Count | Services |
|----------|-------|----------|
| dev-tools | 120+ | GitHub, GitLab, Jira, Bitbucket, GitLab, Sentry, Datadog, PagerDuty, Snowflake, Vercel, Netlify, Postman, Figma |
| productivity | 80+ | Google Workspace, Microsoft 365, Notion, Airtable, Monday, ClickUp, Trello, Asana, Evernote |
| crm | 50+ | HubSpot, Salesforce, Pipedrive, Zoho CRM, Close, Copper |
| communication | 40+ | Slack, Discord, Zoom, Twilio, WhatsApp, Intercom, Zendesk |
| payment | 30+ | Stripe, Square, PayPal, Braintree, Adyen, Checkout.com |
| marketing | 30+ | Mailchimp, Klaviyo, SendGrid, Apollo, Brevo, Constant Contact |
| e-commerce | 25+ | Shopify, WooCommerce, Amazon Selling Partner, BigCommerce |
| analytics | 20+ | Mixpanel, Amplitude, PostHog, Tableau, Looker, Heap |
| hr | 20+ | BambooHR, Workday, Gusto, Personio, Greenhouse, Lever |
| storage | 15+ | Dropbox, Box, Google Drive, OneDrive, Egnyte |
| other | 90+ | Everything else |

## License

MIT — see [LICENSE](LICENSE).

## Author

Eddy Xu

## Status

Alpha — actively developed. Core spec model, vault, OAuth router, and adapter backends are stable with full test coverage (152+ tests). 524 connectors shipped. Currently used in production in the Executive Assistant agent system.
