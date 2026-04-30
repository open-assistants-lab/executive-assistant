"""Connector specification model — the YAML schema.

A connector is a YAML file that describes:
1.  Service identity (name, display name, icon, category)
2.  Authentication (oauth2, api_key, basic, or none)
3.  Tool source (how tools are discovered: cli, mcp, or http)
4.  Tool descriptions (LLM-optimized, per tool)
"""

from enum import Enum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator


class AuthType(str, Enum):
    OAUTH2 = "oauth2"
    API_KEY = "api_key"
    BASIC = "basic"
    NONE = "none"


class ToolSourceType(str, Enum):
    CLI = "cli"
    MCP = "mcp"
    HTTP = "http"


class OAuth2Config(BaseModel):
    authorize_url: str
    token_url: str
    scopes: list[str]
    extra_params: dict = Field(default_factory=dict)
    pkce: bool = False
    token_env_var: str = ""


class ApiKeyConfig(BaseModel):
    header_name: str = "Authorization"
    header_prefix: str = "Bearer"
    env_var: str


class AuthConfig(BaseModel):
    type: AuthType
    oauth2: OAuth2Config | None = None
    api_key: ApiKeyConfig | None = None


class CLIToolSource(BaseModel):
    type: Literal["cli"]
    command: str
    install: str
    env_mapping: dict[str, str] = Field(default_factory=dict)


class MCPToolSource(BaseModel):
    type: Literal["mcp"]
    server_name: str
    command: str
    env_mapping: dict[str, str] = Field(default_factory=dict)


class HTTPToolEndpoint(BaseModel):
    name: str
    description: str
    path: str
    method: str = "GET"
    parameters: dict[str, str] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)


class HTTPToolSource(BaseModel):
    type: Literal["http"]
    base_url: str
    tools: list[HTTPToolEndpoint]


ToolSource = CLIToolSource | MCPToolSource | HTTPToolSource


class ToolDescription(BaseModel):
    name: str
    description: str
    parameter_descriptions: dict[str, str] = Field(default_factory=dict)


class ConnectorSpec(BaseModel):
    name: str
    display: str
    icon: str = "plug"
    category: str = "other"
    version: str = "1.0"
    description: str = ""
    auth: AuthConfig
    tool_source: ToolSource
    tool_descriptions: list[ToolDescription] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def name_must_be_slug(cls, v: str) -> str:
        import re

        if not re.match(r"^[a-z0-9][a-z0-9_-]*$", v):
            raise ValueError(
                f"Connector name '{v}' must be lowercase alphanumeric with hyphens/underscores"
            )
        return v

    @classmethod
    def from_yaml(cls, path: str | Path) -> "ConnectorSpec":
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)

    @classmethod
    def from_yaml_dir(cls, directory: str | Path) -> list["ConnectorSpec"]:
        specs = []
        for yaml_file in sorted(Path(directory).glob("*.yaml")):
            try:
                specs.append(cls.from_yaml(yaml_file))
            except Exception:
                import logging

                logging.getLogger("agent_connect").warning(
                    f"Failed to load connector spec {yaml_file}", exc_info=False
                )
        return specs
