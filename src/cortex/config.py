"""Centralised settings loaded from .env and config/settings.yaml."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── M365 ──────────────────────────────────────────────────────────────
    m365_tenant_id: str = ""
    m365_client_id: str = ""
    m365_cert_thumbprint: str = "6119074C16A1EC9619159106CB6390CAD77A8399"
    m365_cert_pfx_path: str = ""
    m365_cert_pfx_password: str = ""
    m365_mailbox: str = "Knowledge@technijian.com"
    m365_folder: str = "Brain"

    # ── Anthropic ─────────────────────────────────────────────────────────
    anthropic_api_key: str = ""

    # ── OpenAI ────────────────────────────────────────────────────────────
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"

    # ── GitHub ────────────────────────────────────────────────────────────
    github_token: str = ""

    # ── SQL Server ────────────────────────────────────────────────────────
    db_server: str = "localhost"
    db_database: str = "cortex"
    db_trusted_connection: str = "yes"
    db_trust_server_cert: str = "yes"

    # ── Vault ─────────────────────────────────────────────────────────────
    vault_root: str = Field(
        default="C:/Users/Administrator/OneDrive - Technijian, Inc/Documents/obsidian/rjain557-knowledge/rjain557-knowledge"
    )

    # ── Optional search APIs ──────────────────────────────────────────────
    tavily_api_key: str = ""
    exa_api_key: str = ""
    groq_api_key: str = ""

    # ── Webhook server ────────────────────────────────────────────────────
    webhook_secret: str = ""
    webhook_port: int = 8765

    @property
    def vault_path(self) -> Path:
        return Path(self.vault_root)

    @property
    def db_connection_string(self) -> str:
        trusted = "yes" if self.db_trusted_connection.lower() == "yes" else "no"
        trust_cert = "yes" if self.db_trust_server_cert.lower() == "yes" else "no"
        return (
            f"DRIVER={{ODBC Driver 18 for SQL Server}};"
            f"SERVER={self.db_server};DATABASE={self.db_database};"
            f"Trusted_Connection={trusted};Encrypt=yes;TrustServerCertificate={trust_cert};"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


@lru_cache(maxsize=1)
def get_yaml_config() -> dict:
    repo_root = Path(__file__).parent.parent.parent
    cfg_path = repo_root / "config" / "settings.yaml"
    if cfg_path.exists():
        with open(cfg_path) as f:
            return yaml.safe_load(f) or {}
    return {}


@lru_cache(maxsize=1)
def get_domains_config() -> dict:
    repo_root = Path(__file__).parent.parent.parent
    cfg_path = repo_root / "config" / "target-domains.yaml"
    if cfg_path.exists():
        with open(cfg_path) as f:
            return yaml.safe_load(f) or {}
    return {}
