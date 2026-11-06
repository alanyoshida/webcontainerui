from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração do portal, lida do ambiente com prefixo WCUI_."""

    model_config = SettingsConfigDict(env_prefix="WCUI_", extra="ignore")

    db_path: Path = Path("/data/webcontainerui.db")

    # URL do SQLAlchemy. Presente -> usa o banco apontado (PostgreSQL em
    # produção); ausente -> SQLite em `db_path` (dev/testes). Formato:
    # postgresql+psycopg://usuario:senha@host:5432/banco
    database_url: str | None = None

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

    # Limitação de tentativas de login com falha (change harden-login,
    # services/login_throttle.py): janela deslizante por conta e por IP.
    login_max_failures: int = Field(default=10, gt=0)
    login_window_seconds: int = Field(default=300, gt=0)
    login_lock_seconds: int = Field(default=300, gt=0)

    # Carência da purga de sessões (change login-account-hygiene, I5): uma
    # sessão expirada ou revogada só é removida do banco após este período.
    session_purge_grace_hours: int = Field(default=24, ge=1)

    # Documentação interativa da API (/docs, /redoc, /openapi.json). Padrão
    # desligado: em produção não entregam o mapa da API a anônimos (change
    # http-hardening).
    docs_enabled: bool = False

    idle_timeout_minutes: int = Field(default=30, gt=0)
    # Intervalo mínimo entre heartbeats de atividade aceitos por instância
    # (change external-stream-proxy): a visão de sessão sinaliza enquanto
    # está aberta, e o portal não precisa gravar mais que isso.
    heartbeat_min_seconds: int = Field(default=30, gt=0)
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

    # Limite do conteúdo de um documento AGENTS.md da biblioteca
    # (ver services/agents_md.py): evita documento gigante propagado
    # para N instâncias vivas de uma vez.
    max_agents_md_bytes: int = Field(default=262144, gt=0)

    puid: int = Field(default=1000, ge=0)
    pgid: int = Field(default=1000, ge=0)
    timezone: str = Field(default="Etc/UTC", min_length=1)

    # Segredo compartilhado com o plano de dados externo (Caddy): o
    # endpoint interno de autorização só responde a quem o apresentar.
    # Vazio desativa o endpoint — dev e testes não têm Caddy na frente.
    data_plane_secret: str = ""

    # Diretório compartilhado onde o portal publica as rotas de sessão que o
    # Caddy importa (plano de dados externo). Ausente desativa a publicação:
    # dev e testes continuam entregando as sessões pelo próprio portal.
    caddy_routes_dir: Path | None = None

    # Nome/ID do container do Caddy para o `reload` após publicar rotas.
    # Só é usado quando `caddy_routes_dir` está definido.
    caddy_container: str = "wcui-caddy"

    @field_validator("database_url", mode="before")
    @classmethod
    def _blank_database_url_is_none(cls, value):
        return None if value in ("", None) else value

    @field_validator("caddy_routes_dir", mode="before")
    @classmethod
    def _blank_caddy_routes_dir_is_none(cls, value):
        return None if value in ("", None) else value

    # Chave mestra usada para cifrar a chave privada SSH de cada usuário em
    # repouso (ver services/ssh_identity.py). Sem valor padrão: um deploy
    # sem essa variável não deve subir silenciosamente guardando segredo
    # sem cifragem real.
    ssh_key_encryption_key: str

    @model_validator(mode="after")
    def _ssh_key_encryption_key_is_valid_fernet_key(self) -> "Settings":
        try:
            Fernet(self.ssh_key_encryption_key.encode())
        except Exception as exc:
            raise ValueError(
                "WCUI_SSH_KEY_ENCRYPTION_KEY deve ser uma chave Fernet válida "
                "(32 bytes em base64 urlsafe, gerada por exemplo com "
                "Fernet.generate_key())"
            ) from exc
        return self

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
