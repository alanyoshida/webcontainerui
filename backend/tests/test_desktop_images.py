"""Change seed-desktop-images: seed idempotente das entradas de desktop."""

import asyncio
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.db import connect, init_db
from app.runtime.fake import FakeContainerRuntime
from app.services.desktop_images import DESKTOP_IMAGES, seed_desktop_images


class FakeApp:
    """O spawn só precisa de `state.background_tasks`."""

    def __init__(self) -> None:
        self.state = SimpleNamespace(background_tasks=set())


@pytest.fixture
def setup(tmp_path):
    db_path = tmp_path / "t.db"
    conn = connect(db_path)
    init_db(conn)
    conn.close()
    settings = Settings(db_path=db_path, uploads_dir=tmp_path / "uploads")
    app = FakeApp()
    runtime = FakeContainerRuntime()
    return app, settings, runtime


def _roda_com_loop(app, acao):
    """O spawn exige event loop rodando (no lifespan ele existe); no teste o
    seed roda dentro de um loop e os pulls disparados são drenados até fim."""

    async def fluxo():
        acao()
        for _ in range(5):
            await asyncio.sleep(0)
        await asyncio.gather(*app.state.background_tasks, return_exceptions=True)

    asyncio.run(fluxo())


def test_banco_vazio_registra_as_quatro_e_dispara_pull(setup):
    app, settings, runtime = setup

    _roda_com_loop(app, lambda: seed_desktop_images(app, settings, runtime))

    conn = connect(settings.db_path)
    linhas = conn.execute(
        """SELECT display_name, repository, tag, pull_state, provision_kind
           FROM images WHERE repository LIKE 'lscr.io/%' ORDER BY repository, tag"""
    ).fetchall()
    conn.close()

    assert [(r["repository"], r["tag"]) for r in linhas] == sorted(
        [(s.repository, s.tag) for s in DESKTOP_IMAGES]
    )
    assert all(r["provision_kind"] == "pull" for r in linhas)
    # o pull rodou até a prontidão (fake) — o estado não fica preso
    assert all(r["pull_state"] == "ready" for r in linhas)
    repos_pullados = {c["repository"] for c in runtime.pull_calls}
    assert repos_pullados == {s.repository for s in DESKTOP_IMAGES}


def test_entrada_existente_nao_e_duplicada_ni_tocada(setup):
    app, settings, runtime = setup
    conn = connect(settings.db_path)
    init_db(conn)
    conn.execute(
        """INSERT INTO images
               (display_name, repository, tag, shm_size_mb, mem_limit_mb, cpu_limit,
                pull_state, enabled)
           VALUES ('Meu Webtop', 'lscr.io/linuxserver/webtop', 'latest', 512, 4096, 1.0,
                   'ready', 0)"""
    )
    conn.commit()
    conn.close()

    _roda_com_loop(app, lambda: seed_desktop_images(app, settings, runtime))

    conn = connect(settings.db_path)
    linhas = conn.execute(
        """SELECT display_name, enabled, mem_limit_mb, pull_state
           FROM images WHERE repository = 'lscr.io/linuxserver/webtop' AND tag = 'latest'"""
    ).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM images").fetchone()[0]
    conn.close()

    assert len(linhas) == 1
    # desabilitada, com limites editados e nome do admin: intocada
    assert (linhas[0]["display_name"], linhas[0]["enabled"], linhas[0]["mem_limit_mb"]) == (
        "Meu Webtop",
        0,
        4096,
    )
    # as outras três são registradas; a existente não gera pull novo
    assert len([c for c in runtime.pull_calls if c["repository"] == "lscr.io/linuxserver/webtop"]) == 2
    assert total == 4  # 1 existente + 3 novas


def test_falha_em_uma_entrada_nao_impede_as_demais(setup, monkeypatch):
    app, settings, runtime = setup

    import app.services.desktop_images as modulo

    original = modulo.create_image

    def falha_no_vscode(conn, display_name, repository, tag, **kwargs):
        if repository == "lscr.io/linuxserver/vscode":
            raise RuntimeError("falha simulada de registro")
        return original(conn, display_name, repository, tag, **kwargs)

    monkeypatch.setattr(modulo, "create_image", falha_no_vscode)

    # não levanta: a falha é isolada e logada
    _roda_com_loop(app, lambda: seed_desktop_images(app, settings, runtime))

    conn = connect(settings.db_path)
    repos = {r[0] for r in conn.execute("SELECT repository FROM images").fetchall()}
    conn.close()

    assert "lscr.io/linuxserver/vscode" not in repos
    assert "lscr.io/linuxserver/webtop" in repos


def test_lifespan_registra_desktops_com_capa_no_mesmo_boot(tmp_path, fake_runtime):
    """Integração (tarefa 1.2): app criado com banco vazio termina o lifespan
    com as quatro entradas no catálogo e capas padrão aplicadas no mesmo boot."""
    from fastapi.testclient import TestClient

    from app.main import create_app

    settings = Settings(db_path=tmp_path / "t.db", uploads_dir=tmp_path / "uploads")
    app = create_app(settings, runtime=fake_runtime)
    with TestClient(app, base_url="http://testserver"):
        pass

    conn = connect(settings.db_path)
    desktops = conn.execute(
        """SELECT display_name, pull_state, icon_path, icon_source
           FROM images
           WHERE (repository, tag) IN (
               ('lscr.io/linuxserver/webtop', 'latest'),
               ('lscr.io/linuxserver/webtop', 'ubuntu-kde'),
               ('lscr.io/linuxserver/webtop', 'alpine-mate'),
               ('lscr.io/linuxserver/vscode', 'latest'))
           ORDER BY display_name"""
    ).fetchall()
    conn.close()

    assert [r["display_name"] for r in desktops] == ["Alpine MATE", "Ubuntu KDE", "VS Code", "Webtop XFCE"]
    for r in desktops:
        assert r["icon_source"] == "default", r["display_name"]
        assert r["icon_path"], r["display_name"]
    # o nome do arquivo carrega o digest, não a chave — identifica a capa
    # pelo hash do conteúdo contra os assets versionados
    import hashlib

    from app.services.image_covers import default_covers_dir

    por_digest = {
        hashlib.sha256((default_covers_dir() / f"{k}.png").read_bytes()).hexdigest(): k
        for k in ("xfce", "kde", "mate", "vscode")
    }
    esperadas = {"Webtop XFCE": "xfce", "Ubuntu KDE": "kde", "Alpine MATE": "mate", "VS Code": "vscode"}
    for r in desktops:
        digest = r["icon_path"].rsplit("-default-", 1)[-1].removesuffix(".png")
        assert por_digest[digest] == esperadas[r["display_name"]], r["display_name"]
