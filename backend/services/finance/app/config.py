from functools import lru_cache
import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "Aethereon Finance Service"
    service_version: str = "0.1.0"
    service_port: int = 18003
    finance_host: str = "127.0.0.1"
    database_url: str = "postgresql+psycopg2://aethereon:REPLACE_WITH_LOCAL_ROLE_PASSWORD@localhost:15432/aethereon_erp"
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    jwt_issuer: str = "aethereon-identity"
    jwt_audience: str = "aethereon-erp"
    cors_origins: str = "http://localhost:4200,http://127.0.0.1:4200"
    log_level: str = "info"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def configured_port(self) -> int:
        return int(os.getenv("FINANCE_PORT", str(self.service_port)))


@lru_cache
def get_settings() -> Settings:
    return Settings()
