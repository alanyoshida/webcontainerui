"""Testes da resolução de logos e do seed de capas padrão."""

import sqlite3
from pathlib import Path

from app.config import Settings
from app.db import connect, init_db
from app.runtime.fake import FakeContainerRuntime
from app.services.image_covers import (
    LOGOS,
    GENERIC_KEY,
    resolve_logo_key,
    seed_image_covers,
)

from .conftest import insert_image, insert_user

_PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xfc\xcf"
    b"\xc0\xf0\x1f\x00\x05\x05\x02\x00\xd6\xc6\xbex\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _settings(tmp_path: Path) -> Settings:
    return Settings(db_path=tmp_path / "capas.db", uploads_dir=tmp_path / "uploads")


def _make_covers_dir(root: Path, keys: set[str] | None = None) -> Path:
    covers = root / "covers"
    covers.mkdir(parents=True)
    for spec in LOGOS:
        key = spec.key
        if keys is not None and key not in keys:
            continue
        (covers / f"{key}.png").write_bytes(_PNG_1X1 + key.encode())
    (covers / f"{GENERIC_KEY}.png").write_bytes(_PNG_1X1 + b"generico")
    return covers


def _rows(settings: Settings) -> list[sqlite3.Row]:
    conn = connect(settings.db_path)
    try:
        return conn.execute(
            "SELECT id, display_name, icon_path, icon_source FROM images ORDER BY id"
        ).fetchall()
    finally:
        conn.close()


def test_resolve_ambiente_de_desktop_tem_precedencia_sobre_distro():
    assert resolve_logo_key("Webtop XFCE") == "xfce"
    assert resolve_logo_key("ubuntu kde") == "kde"
    assert resolve_logo_key("alpine MATE") == "mate"
    assert resolve_logo_key("Ubuntu MATE", "lscr.io/linuxserver/webtop", "ubuntu-mate") == "mate"


def test_resolve_agente_de_codigo_pelo_nome():
    assert resolve_logo_key("Claude Code") == "claude"
    assert resolve_logo_key("Hermes") == "hermes"
    assert resolve_logo_key("Agy") == "agy"
    assert resolve_logo_key("OpenCode") == "opencode"
    assert resolve_logo_key("oh-my-pi") == "oh-my-pi"


def test_resolve_vscode_pelo_nome_e_pelo_repositorio():
    assert resolve_logo_key("VS Code") == "vscode"
    assert resolve_logo_key("Visual Studio Code") == "vscode"
    assert resolve_logo_key("VS Code", "lscr.io/linuxserver/vscode", "latest") == "vscode"
    assert resolve_logo_key("Webtop", "lscr.io/linuxserver/vscode", "latest") == "vscode"


def test_resolve_por_repositorio_e_tag():
    assert resolve_logo_key("Agente", "wcui-agent-claude-code", "latest") == "claude"
    assert resolve_logo_key("Agente", "wcui-agent-oh-my-pi", "latest") == "oh-my-pi"


def test_resolve_sem_correspondencia_usa_capa_generica():
    assert resolve_logo_key("Webtop") == GENERIC_KEY
    assert resolve_logo_key("Meu Desktop", "registry.exemplo/foo", "v1") == GENERIC_KEY


def test_seed_cadastra_capa_em_todas_as_entradas_sem_capa(tmp_path):
    settings = _settings(tmp_path)
    conn = connect(settings.db_path)
    init_db(conn)
    insert_image(conn, display_name="Webtop XFCE", repository="lscr.io/linuxserver/webtop")
    insert_image(conn, display_name="Hermes", repository="wcui-agent-hermes")
    conn.close()

    covers = _make_covers_dir(tmp_path)
    seed_image_covers(settings, base_dir=covers)

    rows = {row["display_name"]: row for row in _rows(settings)}
    assert rows["Webtop XFCE"]["icon_path"].startswith("1-default-")
    assert rows["Webtop XFCE"]["icon_source"] == "default"
    assert rows["Hermes"]["icon_path"].startswith("2-default-")
    assert rows["Hermes"]["icon_source"] == "default"

    arquivo = settings.uploads_dir / rows["Webtop XFCE"]["icon_path"]
    assert arquivo.exists()
    assert arquivo.read_bytes() == (covers / "xfce.png").read_bytes()
    assert (settings.uploads_dir / rows["Hermes"]["icon_path"]).read_bytes() == (
        covers / "hermes.png"
    ).read_bytes()


def test_seed_preserva_capa_do_admin(tmp_path):
    settings = _settings(tmp_path)
    conn = connect(settings.db_path)
    init_db(conn)
    image_id = insert_image(conn, display_name="Claude Code")
    conn.execute(
        "UPDATE images SET icon_path = ?, icon_source = 'admin' WHERE id = ?",
        ("1-admin-enviada.png", image_id),
    )
    conn.close()

    covers = _make_covers_dir(tmp_path)
    (settings.uploads_dir).mkdir(parents=True, exist_ok=True)
    (settings.uploads_dir / "1-admin-enviada.png").write_bytes(_PNG_1X1 + b"admin")

    seed_image_covers(settings, base_dir=covers)

    row = _rows(settings)[0]
    assert row["icon_path"] == "1-admin-enviada.png"
    assert row["icon_source"] == "admin"


def test_seed_usa_capa_generica_para_nome_desconhecido(tmp_path):
    settings = _settings(tmp_path)
    conn = connect(settings.db_path)
    init_db(conn)
    insert_image(conn, display_name="Coisa Estranha")
    conn.close()

    covers = _make_covers_dir(tmp_path)
    seed_image_covers(settings, base_dir=covers)

    row = _rows(settings)[0]
    assert row["icon_source"] == "default"
    arquivo = settings.uploads_dir / row["icon_path"]
    assert arquivo.read_bytes() == (covers / "generic.png").read_bytes()


def test_seed_e_idempotente_com_asset_inalterado(tmp_path):
    settings = _settings(tmp_path)
    conn = connect(settings.db_path)
    init_db(conn)
    insert_image(conn, display_name="Claude Code")
    conn.close()

    covers = _make_covers_dir(tmp_path)
    seed_image_covers(settings, base_dir=covers)
    primeiro = _rows(settings)[0]["icon_path"]
    arquivo = settings.uploads_dir / primeiro
    stat_antes = arquivo.stat().st_mtime_ns

    seed_image_covers(settings, base_dir=covers)

    assert _rows(settings)[0]["icon_path"] == primeiro
    assert arquivo.stat().st_mtime_ns == stat_antes  # nada foi regravado


def test_seed_substitui_capa_padrao_quando_asset_muda(tmp_path):
    settings = _settings(tmp_path)
    conn = connect(settings.db_path)
    init_db(conn)
    insert_image(conn, display_name="Claude Code")
    conn.close()

    covers = _make_covers_dir(tmp_path)
    seed_image_covers(settings, base_dir=covers)
    primeira = _rows(settings)[0]["icon_path"]
    antigo = settings.uploads_dir / primeira
    assert antigo.exists()

    (covers / "claude.png").write_bytes(_PNG_1X1 + b"nova versao")
    seed_image_covers(settings, base_dir=covers)

    segunda = _rows(settings)[0]["icon_path"]
    assert segunda != primeira
    assert not antigo.exists()  # arquivo padrão anterior foi removido
    novo = settings.uploads_dir / segunda
    assert novo.read_bytes() == _PNG_1X1 + b"nova versao"


def test_seed_isola_falha_de_asset_ausente(tmp_path):
    settings = _settings(tmp_path)
    conn = connect(settings.db_path)
    init_db(conn)
    insert_image(conn, display_name="Claude Code", repository="wcui-agent-claude")  # logo existe
    insert_image(
        conn, display_name="Webtop XFCE", repository="lscr.io/linuxserver/webtop"
    )  # logo ficou de fora do mapa
    conn.close()

    covers = _make_covers_dir(tmp_path, keys={"claude"})
    seed_image_covers(settings, base_dir=covers)  # não propaga exceção

    rows = {row["display_name"]: row for row in _rows(settings)}
    assert rows["Claude Code"]["icon_source"] == "default"
    assert rows["Webtop XFCE"]["icon_path"] is None  # falhou isolada


def test_seed_cobre_entrada_desabilitada_e_em_falha(tmp_path):
    settings = _settings(tmp_path)
    conn = connect(settings.db_path)
    init_db(conn)
    insert_image(
        conn, display_name="Webtop XFCE", repository="lscr.io/linuxserver/webtop", enabled=False
    )
    insert_image(conn, display_name="Hermes", repository="wcui-agent-hermes", pull_state="failed")
    conn.close()

    covers = _make_covers_dir(tmp_path)
    seed_image_covers(settings, base_dir=covers)

    rows = {row["display_name"]: row for row in _rows(settings)}
    assert rows["Webtop XFCE"]["icon_source"] == "default"
    assert rows["Hermes"]["icon_source"] == "default"


def test_imagem_registrada_depois_do_startup_so_recebe_capa_no_proximo_seed(tmp_path):
    settings = _settings(tmp_path)
    conn = connect(settings.db_path)
    init_db(conn)
    conn.close()

    covers = _make_covers_dir(tmp_path)
    seed_image_covers(settings, base_dir=covers)
    assert _rows(settings) == []

    conn = connect(settings.db_path)
    insert_image(conn, display_name="Claude Code")
    conn.close()
    assert _rows(settings)[0]["icon_path"] is None  # nada automático na criação

    seed_image_covers(settings, base_dir=covers)
    assert _rows(settings)[0]["icon_source"] == "default"


async def test_startup_cadastra_capa_nas_entradas_existentes(client, app_settings):
    """Integração via TestClient: o lifespan roda seed_agent_images +
    seed_image_covers, então as entradas de agente ganham capa no startup."""
    conn = connect(app_settings.db_path)
    try:
        rows = conn.execute(
            "SELECT display_name, icon_path, icon_source FROM images ORDER BY id"
        ).fetchall()
        assert {row["display_name"] for row in rows} == {
            "Claude Code",
            "Hermes",
            "Agy",
            "OpenCode",
            "oh-my-pi",
        }
        for row in rows:
            assert row["icon_path"] is not None
            assert row["icon_source"] == "default"
    finally:
        conn.close()


async def test_seed_de_capas_nao_dispara_rebuild_de_imagem(app_settings, fake_runtime):
    """Capas vivem fora do contexto de build: mudar um PNG em covers/ não
    altera build_hash nem dispara rebuild no próximo seed de agentes."""
    from app.services.agent_images import BASE_IMAGE_REPOSITORY, seed_agent_images

    conn = connect(app_settings.db_path)
    init_db(conn)
    conn.close()
    covers = _make_covers_dir(app_settings.db_path.parent)
    seed_image_covers(app_settings, base_dir=covers)
    await seed_agent_images(app_settings, fake_runtime)
    hash_antes = {
        row["repository"]: row["build_hash"]
        for row in connect(app_settings.db_path).execute(
            "SELECT repository, build_hash FROM images"
        )
    }
    # A base é reconstruída a cada seed; só os builds de agente interessam aqui.
    builds_antes = len(
        [c for c in fake_runtime.build_calls if c["repository"] != BASE_IMAGE_REPOSITORY]
    )

    (covers / "claude.png").write_bytes(_PNG_1X1 + b"versao nova da capa")
    seed_image_covers(app_settings, base_dir=covers)
    await seed_agent_images(app_settings, fake_runtime)

    conn = connect(app_settings.db_path)
    hash_depois = {
        row["repository"]: row["build_hash"]
        for row in conn.execute("SELECT repository, build_hash FROM images")
    }
    conn.close()
    assert hash_antes == hash_depois  # capa não entra no hash de contexto
    builds_depois = len(
        [c for c in fake_runtime.build_calls if c["repository"] != BASE_IMAGE_REPOSITORY]
    )
    assert builds_depois == builds_antes  # nem dispara rebuild


async def test_falha_de_build_de_agente_nao_impede_capa_nem_startup(
    app_settings, tmp_path
):
    from app.runtime.errors import RuntimeOperationError
    from app.services.agent_images import AGENT_IMAGES, seed_agent_images

    class RuntimeComFalha(FakeContainerRuntime):
        async def build_image(self, context_dir, repository, tag, *, buildargs=None):
            if repository == AGENT_IMAGES[0].repository:
                self.build_calls.append(
                    {
                        "context_dir": context_dir,
                        "repository": repository,
                        "tag": tag,
                        "buildargs": dict(buildargs) if buildargs else {},
                    }
                )
                raise RuntimeOperationError("falha proposital no build")
            async for progress in super().build_image(
                context_dir, repository, tag, buildargs=buildargs
            ):
                yield progress

    settings = Settings(
        db_path=tmp_path / "falha-build.db", uploads_dir=tmp_path / "uploads-falha"
    )
    conn = connect(settings.db_path)
    init_db(conn)
    conn.close()
    covers = _make_covers_dir(tmp_path)

    await seed_agent_images(settings, RuntimeComFalha())
    seed_image_covers(settings, base_dir=covers)  # não propaga exceção

    conn = connect(settings.db_path)
    rows = {row["display_name"]: row for row in conn.execute(
        "SELECT display_name, pull_state, icon_path, icon_source FROM images"
    )}
    conn.close()
    assert rows["Claude Code"]["pull_state"] == "failed"
    assert rows["Claude Code"]["icon_source"] == "default"  # falha não impediu capa
    assert rows["OpenCode"]["pull_state"] == "ready"


async def test_falha_do_seed_de_capas_nao_impede_o_startup(app_settings, fake_runtime, monkeypatch, tmp_path):
    """Todas as capas ausentes: cada entrada falha isolada e o lifespan
    conclui o startup normalmente."""
    import app.services.image_covers as image_covers
    from fastapi.testclient import TestClient

    from app.main import create_app

    vazio = tmp_path / "covers-vazios"
    vazio.mkdir()
    # Antes de criar a app: o lifespan consulta default_covers_dir() no startup.
    monkeypatch.setattr(image_covers, "default_covers_dir", lambda: vazio)

    app = create_app(app_settings, runtime=fake_runtime)
    with TestClient(app, base_url="http://testserver") as c:
        c.get("/api/me")  # se o startup falhasse, o TestClient teria explodido

    conn = connect(app_settings.db_path)
    rows = conn.execute("SELECT icon_path, icon_source FROM images").fetchall()
    conn.close()
    assert len(rows) == 5
    for row in rows:
        assert row["icon_path"] is None  # falha isolada: nada gravado
        assert row["icon_source"] is None