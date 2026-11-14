from functools import lru_cache
import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "Aethereon Identity Service"
    service_version: str = "0.1.0"
    service_port: int = 18001
    identity_host: str = "127.0.0.1"
    identity_auto_port: bool = False
    database_url: str = "postgresql+psycopg2://aethereon:REPLACE_WITH_LOCAL_ROLE_PASSWORD@localhost:15432/aethereon_erp"
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    cors_origins: str = "http://localhost:42000,http://127.0.0.1:42000"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def configured_port(self) -> int:
        return int(os.getenv("IDENTITY_PORT", str(self.service_port)))


@lru_cache
def get_settings() -> Settings:
    result = Settings()
    if len(result.jwt_secret_key.encode("utf-8")) < 32:
        raise RuntimeError("JWT_SECRET_KEY es obligatoria y debe tener al menos 32 bytes. Configúrala en el archivo .env raíz.")
    if result.database_url.startswith("sqlite"):
        raise RuntimeError("Este servicio necesita PostgreSQL; no se admite SQLite como base ERP.")
    return result
