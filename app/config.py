"""Application configuration loaded from environment / .env.

Graph API credentials are Optional so the package can be imported before
Phase 0 setup is complete (e.g. while building the DB / analysis modules).
Any code path that actually calls the Graph API must first call
``settings.require_ig_credentials()``, which raises a friendly error
listing exactly what is missing (see risks.md R4 — fail loud, fail clear).
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Meta / Instagram credentials (filled after Phase 0) ---
    fb_app_id: str | None = None
    fb_app_secret: str | None = None
    # Instagram Login uses the *Instagram* app secret for ig_exchange_token, which
    # may differ from fb_app_secret. Optional; falls back to fb_app_secret if unset.
    ig_app_secret: str | None = None
    ig_user_id: str | None = None
    ig_access_token: str | None = None

    # We use the "Instagram API with Instagram Login" path → host graph.instagram.com.
    # Version VERIFY/UPDATE during Phase 2 (api-integration.md).
    graph_api_version: str = "v21.0"
    graph_api_base_url: str = "https://graph.instagram.com"

    # --- App config (names mirror .env.example) ---
    database_path: Path = Path("./ig_pulse.db")
    log_level: str = "INFO"
    timezone: str = "Asia/Jakarta"

    # --- Filesystem layout ---
    logs_dir: Path = Path("./logs")
    exports_dir: Path = Path("./exports")
    fixtures_dir: Path = Path("./tests/fixtures")

    # --- Sentiment model (final choice made in Phase 4; pin revision per R8) ---
    sentiment_model: str = "tabularisai/multilingual-sentiment-analysis"
    sentiment_model_fallback: str = "cardiffnlp/twitter-xlm-roberta-base-sentiment"
    sentiment_model_revision: str | None = None

    @property
    def graph_api_url(self) -> str:
        """Full versioned base for data calls, e.g. https://graph.instagram.com/v21.0"""
        return f"{self.graph_api_base_url}/{self.graph_api_version}"

    @property
    def app_secret(self) -> str | None:
        """Secret used for token exchange/refresh (Instagram secret, else Facebook)."""
        return self.ig_app_secret or self.fb_app_secret

    def require_ig_credentials(self) -> None:
        """Raise if the access token is missing. Call before any API use.

        Only IG_ACCESS_TOKEN is needed for data calls (Instagram Login scopes the
        token to the user, so we call /me directly — no IG_USER_ID required).
        """
        if not self.ig_access_token:
            raise RuntimeError(
                "Missing IG_ACCESS_TOKEN. Complete Phase 0 (docs/phase0-setup.md) "
                "and fill .env."
            )


settings = Settings()
