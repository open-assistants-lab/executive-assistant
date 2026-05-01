"""Tests that all shipped connector YAMLs parse correctly."""

from pathlib import Path

from connectkit.spec import ConnectorSpec

CONNECTORS_DIR = Path(__file__).parent.parent / "connectors"


def test_all_yamls_parse():
    for yaml_file in sorted(CONNECTORS_DIR.glob("*.yaml")):
        spec = ConnectorSpec.from_yaml(str(yaml_file))
        assert spec.name, f"{yaml_file.name}: missing name"
        assert spec.auth.type, f"{yaml_file.name}: missing auth type"
        sources = spec.get_tool_sources()
        assert len(sources) >= 1, f"{yaml_file.name}: no tool sources"


def test_firecrawl():
    spec = ConnectorSpec.from_yaml(CONNECTORS_DIR / "firecrawl.yaml")
    assert spec.auth.type.value == "api_key"
    fields = {f.name: f for f in spec.auth.required_fields}
    assert "base_url" in fields and fields["base_url"].optional


def test_google_workspace():
    spec = ConnectorSpec.from_yaml(CONNECTORS_DIR / "google-workspace.yaml")
    assert spec.auth.oauth2.extra_params["access_type"] == "offline"


def test_github():
    spec = ConnectorSpec.from_yaml(CONNECTORS_DIR / "github.yaml")
    assert "repo" in spec.auth.oauth2.scopes


def test_microsoft_365():
    spec = ConnectorSpec.from_yaml(CONNECTORS_DIR / "microsoft-365.yaml")
    assert "offline_access" in spec.auth.oauth2.scopes


def test_slack():
    spec = ConnectorSpec.from_yaml(CONNECTORS_DIR / "slack.yaml")
    assert "chat:write" in spec.auth.oauth2.scopes
    types = {s.type for s in spec.get_tool_sources()}
    assert {"cli", "mcp"} == types


def test_notion():
    spec = ConnectorSpec.from_yaml(CONNECTORS_DIR / "notion.yaml")
    assert spec.get_tool_sources()[0].type == "mcp"


def test_jira():
    spec = ConnectorSpec.from_yaml(CONNECTORS_DIR / "jira.yaml")
    assert len(spec.get_tool_sources()) == 2


def test_gitlab():
    spec = ConnectorSpec.from_yaml(CONNECTORS_DIR / "gitlab.yaml")
    assert len(spec.get_tool_sources()) == 2
    assert "base_url" in {f.name for f in spec.auth.required_fields}


def test_stripe():
    spec = ConnectorSpec.from_yaml(CONNECTORS_DIR / "stripe.yaml")
    assert len(spec.get_tool_sources()) == 2


def test_hubspot():
    spec = ConnectorSpec.from_yaml(CONNECTORS_DIR / "hubspot.yaml")
    assert len(spec.get_tool_sources()) == 2


def test_sentry():
    spec = ConnectorSpec.from_yaml(CONNECTORS_DIR / "sentry.yaml")
    assert "base_url" in {f.name for f in spec.auth.required_fields}


def test_vercel():
    spec = ConnectorSpec.from_yaml(CONNECTORS_DIR / "vercel.yaml")
    assert spec.get_tool_sources()[0].command == "vercel"


def test_figma():
    spec = ConnectorSpec.from_yaml(CONNECTORS_DIR / "figma.yaml")
    assert spec.get_tool_sources()[0].server_name == "figma"


def test_salesforce():
    spec = ConnectorSpec.from_yaml(CONNECTORS_DIR / "salesforce.yaml")
    assert len(spec.get_tool_sources()) == 2


def test_box():
    spec = ConnectorSpec.from_yaml(CONNECTORS_DIR / "box.yaml")
    types = {s.type for s in spec.get_tool_sources()}
    assert {"cli", "mcp"} == types


def test_airtable():
    spec = ConnectorSpec.from_yaml(CONNECTORS_DIR / "airtable.yaml")
    assert spec.auth.type.value == "api_key"
    assert spec.get_tool_sources()[0].type == "mcp"


def test_monday():
    spec = ConnectorSpec.from_yaml(CONNECTORS_DIR / "monday.yaml")
    assert len(spec.get_tool_sources()) == 2


def test_clickup():
    spec = ConnectorSpec.from_yaml(CONNECTORS_DIR / "clickup.yaml")
    assert len(spec.get_tool_sources()) == 2


def test_postman():
    spec = ConnectorSpec.from_yaml(CONNECTORS_DIR / "postman.yaml")
    assert len(spec.get_tool_sources()) == 2


def test_datadog():
    spec = ConnectorSpec.from_yaml(CONNECTORS_DIR / "datadog.yaml")
    assert len(spec.get_tool_sources()) == 2


def test_pagerduty():
    spec = ConnectorSpec.from_yaml(CONNECTORS_DIR / "pagerduty.yaml")
    assert spec.get_tool_sources()[0].type == "mcp"


def test_twilio():
    spec = ConnectorSpec.from_yaml(CONNECTORS_DIR / "twilio.yaml")
    assert len(spec.get_tool_sources()) == 2


def test_discord():
    spec = ConnectorSpec.from_yaml(CONNECTORS_DIR / "discord.yaml")
    assert spec.get_tool_sources()[0].type == "mcp"


def test_zoom():
    spec = ConnectorSpec.from_yaml(CONNECTORS_DIR / "zoom.yaml")
    assert spec.auth.type.value == "oauth2"


def test_dropbox():
    spec = ConnectorSpec.from_yaml(CONNECTORS_DIR / "dropbox.yaml")
    assert len(spec.get_tool_sources()) == 2


def test_linear():
    spec = ConnectorSpec.from_yaml(CONNECTORS_DIR / "linear.yaml")
    assert len(spec.get_tool_sources()) == 2


def test_zendesk():
    spec = ConnectorSpec.from_yaml(CONNECTORS_DIR / "zendesk.yaml")
    assert "subdomain" in {f.name for f in spec.auth.required_fields}


def test_netlify():
    spec = ConnectorSpec.from_yaml(CONNECTORS_DIR / "netlify.yaml")
    assert spec.get_tool_sources()[0].type == "cli"


def test_trello():
    spec = ConnectorSpec.from_yaml(CONNECTORS_DIR / "trello.yaml")
    assert spec.get_tool_sources()[0].type == "mcp"
