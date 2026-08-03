"""Central configuration for the Hermes assistant backend.

All secrets come from environment variables (or an ``assistant/.env`` file).
Nothing here should ever be hard-coded or committed.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ASSISTANT_DIR = Path(__file__).parent
DATA_DIR = ASSISTANT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


class Settings(BaseSettings):
    """Runtime settings, loaded once at import time."""

    model_config = SettingsConfigDict(
        env_file=ASSISTANT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LLM providers (set the ones you use; Settings app picks at runtime) ---
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""
    openrouter_api_key: str = ""
    assistant_model: str = "anthropic:claude-sonnet-5"
    # Cheap model for background memory/skill review runs.
    review_model: str = "anthropic:claude-haiku-4-5-20251001"

    # --- Identity ---
    user_id: str = "kevyn"
    user_name: str = "Kevyn"
    timezone: str = "Asia/Jerusalem"

    # --- Database (Postgres + pgvector; see docker-compose.yml) ---
    database_url: str = "postgresql://hermes:hermes@localhost:5433/hermes"

    # --- Memory ---
    mem0_api_key: str = ""  # empty -> local mem0 backed by pgvector
    memory_char_limit: int = 2200  # MEMORY.md budget (Hermes convention)
    user_profile_char_limit: int = 1375  # USER.md budget
    review_every_n_turns: int = 6  # post-turn background review cadence

    # --- Web search ---
    tavily_api_key: str = ""

    # --- Google (Gmail + Calendar + YouTube Data API) ---
    google_credentials_path: Path = ASSISTANT_DIR / "credentials.json"
    google_token_path: Path = DATA_DIR / "google_token.json"
    youtube_api_key: str = ""

    # --- Apple Mail (iCloud IMAP/SMTP with an app-specific password) ---
    icloud_email: str = ""
    icloud_app_password: str = ""

    # --- WhatsApp (Meta Cloud API) ---
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = ""  # webhook verification handshake
    whatsapp_owner_phone: str = ""  # only this number may talk to the agent

    # --- Sandbox (code execution) ---
    sandbox_provider: str = "none"  # none | daytona | modal | e2b
    daytona_api_key: str = ""
    e2b_api_key: str = ""

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8787
    # Bearer token the iPhone app must present. Generate with: openssl rand -hex 32
    api_auth_token: str = ""

    # --- Push notifications (APNs, for proactive routines) ---
    apns_key_path: Path = ASSISTANT_DIR / "apns_key.p8"
    apns_key_id: str = ""
    apns_team_id: str = ""
    apns_bundle_id: str = "com.kevyn.hermes"
    apns_use_sandbox: bool = True

    # --- Workspace (agent scratch files when no sandbox) ---
    workspace_dir: Path = DATA_DIR / "workspace"


settings = Settings()
settings.workspace_dir.mkdir(parents=True, exist_ok=True)
