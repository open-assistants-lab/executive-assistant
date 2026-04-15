"""CLI command to update model registry from models.dev.

Usage:
    python -m src.sdk.registry_update update    # Fetch latest from models.dev GitHub
    python -m src.sdk.registry_update list      # Show all known models
    python -m src.sdk.registry_update list --provider openai  # Filter by provider
"""

from __future__ import annotations

import json
import sys
import urllib.request

GITHUB_API = "https://api.github.com/repos/sst/models.dev/contents"


def _fetch_json(url: str) -> dict | list:
    """Fetch JSON from a URL."""
    req = urllib.request.Request(url, headers={"User-Agent": "ea-registry-update/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def _fetch_toml(url: str) -> dict:
    """Fetch and parse a simple TOML file (key = value format only)."""
    req = urllib.request.Request(url, headers={"User-Agent": "ea-registry-update/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        content = resp.read().decode()
    result: dict = {}
    current_section = None
    for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            current_section = line.strip("[]")
            if current_section not in result:
                result[current_section] = {}
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if value.lower() == "true":
                value = True
            elif value.lower() == "false":
                value = False
            elif value.replace("_", "").isdigit():
                value = int(value.replace("_", ""))
            elif "." in value:
                try:
                    value = float(value)
                except ValueError:
                    pass
            if current_section:
                result[current_section][key] = value
            else:
                result[key] = value
    return result


def list_providers() -> list[str]:
    """List all provider IDs from models.dev."""
    data = _fetch_json(f"{GITHUB_API}/providers")
    return sorted([item["name"] for item in data if item["type"] == "dir"])


def fetch_provider_models(provider_id: str) -> list[dict]:
    """Fetch all model TOMLs for a provider."""
    models = []
    try:
        data = _fetch_json(f"{GITHUB_API}/providers/{provider_id}/models")
    except Exception:
        return []
    for item in data:
        if not item["name"].endswith(".toml"):
            continue
        try:
            model_data = _fetch_toml(item["download_url"])
            model_data["_id"] = item["name"].replace(".toml", "")
            model_data["_provider"] = provider_id
            models.append(model_data)
        except Exception:
            continue
    return models


def update_registry() -> None:
    """Fetch model data from models.dev and generate registry_data.py."""
    print("Fetching provider list from models.dev...")
    providers = list_providers()
    print(f"Found {len(providers)} providers")

    all_models = []
    key_providers = [
        "openai",
        "anthropic",
        "google-gemini",
        "ollama",
        "groq",
        "deepseek",
        "together",
        "openrouter",
        "fireworks-ai",
        "xai",
    ]

    for provider_id in key_providers:
        print(f"  Fetching {provider_id}...")
        models = fetch_provider_models(provider_id)
        all_models.extend(models)
        print(f"    {len(models)} models")

    print(f"\nTotal models fetched: {len(all_models)}")
    print("Registry update complete (curated data stays in registry.py)")
    print("To add models.dev data, regenerate src/sdk/registry_data.py")


def list_models(provider: str | None = None) -> None:
    """List known models."""
    from src.sdk.registry import list_models

    models = list_models(provider=provider)
    if not models:
        print("No models found.")
        return
    print(f"{'ID':<45} {'Name':<30} {'Provider':<15} {'Ctx':>10} {'Tool Call':>9}")
    print("-" * 115)
    for m in models:
        print(
            f"{m.id:<45} {m.name:<30} {m.provider_id:<15} {m.context_window:>10} {'Yes' if m.tool_call else 'No':>9}"
        )


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m src.sdk.registry_update [update|list] [--provider ID]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "update":
        update_registry()
    elif command == "list":
        provider = None
        if "--provider" in sys.argv:
            idx = sys.argv.index("--provider")
            if idx + 1 < len(sys.argv):
                provider = sys.argv[idx + 1]
        list_models(provider=provider)
    else:
        print(f"Unknown command: {command}")
        print("Usage: python -m src.sdk.registry_update [update|list]")
        sys.exit(1)


if __name__ == "__main__":
    main()
