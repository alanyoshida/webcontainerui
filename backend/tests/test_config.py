import pytest
from pydantic import ValidationError

from app.config import Settings


def test_valores_omitidos_usam_o_padrao():
    s = Settings()

    assert s.docker_network == "wcui_net"
    assert s.idle_timeout_minutes == 30
    assert s.default_shm_size_mb == 1024
    assert s.default_cpu_limit == 2.0
    assert s.puid == 1000
    assert s.timezone == "Etc/UTC"
    assert s.bootstrap_admin is False


def test_ambiente_sobrepoe_o_padrao(monkeypatch):
    monkeypatch.setenv("WCUI_DOCKER_NETWORK", "outra_rede")
    monkeypatch.setenv("WCUI_IDLE_TIMEOUT_MINUTES", "5")
    monkeypatch.setenv("WCUI_DEFAULT_CPU_LIMIT", "0.5")

    s = Settings()

    assert s.docker_network == "outra_rede"
    assert s.idle_timeout_minutes == 5
    assert s.default_cpu_limit == 0.5


@pytest.mark.parametrize(
    "var,valor",
    [
        ("WCUI_IDLE_TIMEOUT_MINUTES", "0"),
        ("WCUI_IDLE_TIMEOUT_MINUTES", "-1"),
        ("WCUI_IDLE_TIMEOUT_MINUTES", "nao-numero"),
        ("WCUI_REAPER_INTERVAL_SECONDS", "0"),
        ("WCUI_ACTIVITY_DEBOUNCE_SECONDS", "0"),
        ("WCUI_SESSION_TTL_HOURS", "0"),
        ("WCUI_DEFAULT_SHM_SIZE_MB", "0"),
        ("WCUI_DEFAULT_MEM_LIMIT_MB", "-5"),
        ("WCUI_DEFAULT_CPU_LIMIT", "0"),
        ("WCUI_DOCKER_NETWORK", ""),
        ("WCUI_PUID", "-1"),
    ],
)
def test_valor_invalido_falha_na_inicializacao(monkeypatch, var, valor):
    monkeypatch.setenv(var, valor)

    with pytest.raises(ValidationError):
        Settings()


def test_credencial_de_admin_incompleta_falha(monkeypatch):
    monkeypatch.setenv("WCUI_ADMIN_EMAIL", "admin@exemplo.test")

    with pytest.raises(ValidationError):
        Settings()


def test_senha_de_admin_sem_email_falha(monkeypatch):
    monkeypatch.setenv("WCUI_ADMIN_PASSWORD", "senha-bem-longa-123")

    with pytest.raises(ValidationError):
        Settings()


def test_senha_de_admin_curta_falha(monkeypatch):
    monkeypatch.setenv("WCUI_ADMIN_EMAIL", "admin@exemplo.test")
    monkeypatch.setenv("WCUI_ADMIN_PASSWORD", "curta")

    with pytest.raises(ValidationError):
        Settings()


def test_credencial_de_admin_completa_ativa_provisionamento(monkeypatch):
    monkeypatch.setenv("WCUI_ADMIN_EMAIL", "admin@exemplo.test")
    monkeypatch.setenv("WCUI_ADMIN_PASSWORD", "senha-bem-longa-123")

    s = Settings()

    assert s.bootstrap_admin is True
    assert s.admin_email == "admin@exemplo.test"
