from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://rehab:rehab@localhost:5432/rehab"

    @field_validator("database_url", mode="before")
    @classmethod
    def use_psycopg_driver(cls, value):
        # Tiger Data supplies a standard PostgreSQL URI; SQLAlchemy needs the
        # installed psycopg 3 driver explicitly. Preserve credentials and TLS options.
        if not value:
            return "postgresql+psycopg://rehab:rehab@localhost:5432/rehab"
        for prefix in ("postgresql://", "postgres://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix) :]
        return value

    jwt_secret: str = "development-only-change-this-secret-32chars"
    public_origin: str = "https://localhost:3000"
    environment: str = "development"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""
    presage_enabled: bool = False


settings = Settings()
if settings.environment == "production" and (
    settings.jwt_secret.startswith("development") or len(settings.jwt_secret) < 32
):
    raise RuntimeError("Set a strong JWT_SECRET in production")
