"""Credential and vault models."""

from typing import Literal

from pydantic import BaseModel, Field


class Credential(BaseModel):
    """Email account credential stored in vault."""

    name: str = Field(description="Friendly name, e.g., 'work-gmail'")
    provider: Literal["gmail", "outlook", "yahoo", "office365", "imap"] = Field(
        description="Email provider type"
    )
    email: str = Field(description="Email address")
    imap_host: str = Field(description="IMAP server hostname")
    imap_port: int = Field(default=993, description="IMAP port")
    smtp_host: str = Field(description="SMTP server hostname")
    smtp_port: int = Field(default=587, description="SMTP port")
    username: str = Field(description="IMAP/SMTP username (usually email)")
    password: str = Field(description="Password or app password")
    use_ssl: bool = Field(default=True, description="Use SSL for IMAP")
    use_tls: bool = Field(default=True, description="Use TLS for SMTP")


class VaultConfig(BaseModel):
    """Vault configuration."""

    salt: str = Field(description="Salt for key derivation")
    iterations: int = Field(default=100000, description="PBKDF2 iterations")
    encrypted_data: str = Field(description="Encrypted JSON data")
