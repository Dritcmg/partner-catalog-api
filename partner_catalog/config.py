"""Explicit local configuration: startup fails without a suitable API key."""

import os
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    api_key: str
    database_url: str = "sqlite:///./var/partners.db"

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", self.api_key):
            raise ValueError("PARTNER_API_KEY must contain 32 to 256 ASCII URL-safe characters")
        if self.api_key.startswith("replace-this-placeholder"):
            raise ValueError("Replace the example API key before starting the application")
        if not self.database_url.startswith("sqlite:///"):
            raise ValueError("This small project supports SQLite file URLs only")
        if self.database_url == "sqlite:///:memory:":
            raise ValueError("Use a SQLite file so separate connections share the same database")

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            api_key=os.getenv("PARTNER_API_KEY", ""),
            database_url=os.getenv("PARTNER_DATABASE_URL", "sqlite:///./var/partners.db"),
        )
