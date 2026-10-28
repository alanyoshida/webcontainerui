from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração do portal, lida do ambiente com prefixo WCUI_."""

    model_config = SettingsConfigDict(env_prefix="WCUI_", extra="ignore")

    db_path: Path = Path("/data/webcontainerui.db")

    # Build do front-end a servir em "/". Ausente em desenvolvimento (o
    # Vite serve o front-end ali, não o FastAPI) — por isso a montagem é
    # condicional, não um requisito de inicialização.
    frontend_dist: Path = Path("/app/frontend/dist")

    docker_network: str = Field(default="wcui_net", min_length=1)
    volume_prefix: str = Field(default="wcui", min_length=1)
    container_prefix: str = Field(default="wcui", min_length=1)

    # Provisionamento do primeiro administrador. Ambos vazios desativa o
    # provisionamento; informar apenas um é erro de configuração.
    admin_email: str = ""
    admin_password: str = ""

    session_ttl_hours: int = Field(default=12, gt=0)
    password_min_length: int = Field(default=12, gt=0)

    idle_timeout_minutes: int = Field(default=30, gt=0)
    reaper_interval_seconds: int = Field(default=60, gt=0)
    activity_debounce_seconds: int = Field(default=30, gt=0)

    default_shm_size_mb: int = Field(default=1024, gt=0)
    default_mem_limit_mb: int = Field(default=2048, gt=0)
    default_cpu_limit: float = Field(default=2.0, gt=0)

    # Diretório onde as imagens de capa enviadas pelo administrador são
    # armazenadas. Fica sob o mesmo volume de /data usado pelo SQLite, para
    # não exigir um volume novo no deploy.
    uploads_dir: Path = Path("/data/uploads/images")
    max_icon_upload_mb: int = Field(default=5, gt=0)

    puid: int = Field(default=1000, ge=0)
    pgid: int = Field(default=1000, ge=0)
    timezone: str = Field(default="Etc/UTC", min_length=1)

    @model_validator(mode="after")
    def _admin_pair_is_complete(self) -> "Settings":
        if bool(self.admin_email) != bool(self.admin_password):
            raise ValueError(
                "WCUI_ADMIN_EMAIL e WCUI_ADMIN_PASSWORD devem ser informados "
                "juntos ou ambos omitidos"
            )
        if self.admin_password and len(self.admin_password) < self.password_min_length:
            raise ValueError(
                f"WCUI_ADMIN_PASSWORD deve ter ao menos "
                f"{self.password_min_length} caracteres"
            )
        return self

    @property
    def bootstrap_admin(self) -> bool:
        return bool(self.admin_email and self.admin_password)


@lru_cache
def get_settings() -> Settings:
    return Settings()
