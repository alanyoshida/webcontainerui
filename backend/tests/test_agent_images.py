"""Testes do provisionamento por build e do seed de imagens de agente."""

import time
from pathlib import Path

import pytest

from app.config import Settings
from app.db import connect, init_db
from app.runtime.errors import RuntimeOperationError
from app.runtime.fake import FakeContainerRuntime
from app.services.agent_images import (
    AGENT_IMAGES,
    BASE_IMAGE_REPOSITORY,
    BASE_IMAGE_TAG,
    build_hash_for,
    find_agent_image,
    rebuild_agent_image,
    run_build,
    seed_agent_images,
)
from app.services.agent_skills import create_skill, link_skill

from .conftest import insert_image


def _settings(tmp_path: Path) -> Settings:
    return Settings(db_path=tmp_path / "agentes.db", uploads_dir=tmp_path / "uploads")


def _make_context(root: Path) -> None:
    (root / "_base").mkdir(parents=True)
    (root / "_base" / "Dockerfile").write_text("FROM debian:bookworm-slim\n", encoding="utf-8")
    for spec in AGENT_IMAGES:
        directory = root / spec.context_subdir
        directory.mkdir()
        (directory / "Dockerfile").write_text(
            f"FROM {BASE_IMAGE_REPOSITORY}:{BASE_IMAGE_TAG}\n", encoding="utf-8"
        )


def _agent_rows(settings: Settings) -> list:
    conn = connect(settings.db_path)
    try:
        return conn.execute(
            "SELECT * FROM images WHERE provision_kind = 'build' ORDER BY id"
        ).fetchall()
    finally:
        conn.close()


def _wait_for(predicate, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condição não satisfeita dentro do timeout")


def test_lista_tem_exatamente_os_cinco_agentes_com_campos_obrigatorios():
    assert [spec.display_name for spec in AGENT_IMAGES] == [
        "Claude Code",
        "Hermes",
        "Agy",
        "OpenCode",
        "oh-my-pi",
    ]
    for spec in AGENT_IMAGES:
        assert spec.repository
        assert spec.tag
        assert spec.context_subdir
        assert spec.port == 3000
    assert find_agent_image(AGENT_IMAGES[0].repository, "latest") is AGENT_IMAGES[0]
    assert find_agent_image("nao-existe", "latest") is None


async def test_run_build_sucesso_marca_pronta_e_grava_hash(tmp_path):
    settings = _settings(tmp_path)
    conn = connect(settings.db_path)
    init_db(conn)
    image_id = insert_image(
        conn, repository="wcui-agent-teste", tag="latest", pull_state="pulling",
        provision_kind="build",
    )
    conn.close()

    runtime = FakeContainerRuntime()
    await run_build(
        settings.db_path,
        runtime,
        image_id,
        "wcui-agent-teste",
        "latest",
        context_dir=str(tmp_path),
        build_hash="hash-1",
    )

    conn = connect(settings.db_path)
    row = conn.execute(
        "SELECT pull_state, build_hash, pull_error FROM images WHERE id = ?", (image_id,)
    ).fetchone()
    conn.close()
    assert row["pull_state"] == "ready"
    assert row["build_hash"] == "hash-1"
    assert row["pull_error"] is None
    assert runtime.build_calls == [
        {
            "context_dir": str(tmp_path),
            "repository": "wcui-agent-teste",
            "tag": "latest",
            "buildargs": {},
        }
    ]


async def test_run_build_falha_marca_falha_com_a_mensagem(tmp_path):
    settings = _settings(tmp_path)
    conn = connect(settings.db_path)
    init_db(conn)
    image_id = insert_image(
        conn, repository="wcui-agent-teste", tag="latest", pull_state="pulling",
        provision_kind="build",
    )
    conn.close()

    runtime = FakeContainerRuntime()
    runtime.fail_next("build_image", RuntimeOperationError("Dockerfile inválido"))
    await run_build(
        settings.db_path,
        runtime,
        image_id,
        "wcui-agent-teste",
        "latest",
        context_dir=str(tmp_path),
        build_hash="hash-1",
    )

    conn = connect(settings.db_path)
    row = conn.execute(
        "SELECT pull_state, build_hash, pull_error FROM images WHERE id = ?", (image_id,)
    ).fetchone()
    conn.close()
    assert row["pull_state"] == "failed"
    assert "Dockerfile inválido" in row["pull_error"]
    assert row["build_hash"] is None  # só grava após sucesso


async def test_seed_idempotente_e_nao_rebuilda_contexto_inalterado(tmp_path):
    settings = _settings(tmp_path)
    conn = connect(settings.db_path)
    init_db(conn)
    conn.close()
    root = tmp_path / "agent-images"
    _make_context(root)

    runtime = FakeContainerRuntime()
    await seed_agent_images(settings, runtime, base_dir=root)
    assert len(_agent_rows(settings)) == 5
    assert all(row["pull_state"] == "ready" for row in _agent_rows(settings))
    builds_primeira = len(
        [c for c in runtime.build_calls if c["repository"] != BASE_IMAGE_REPOSITORY]
    )
    assert builds_primeira == 5

    runtime.build_calls.clear()
    await seed_agent_images(settings, runtime, base_dir=root)

    assert len(_agent_rows(settings)) == 5  # sem duplicação
    assert [
        c for c in runtime.build_calls if c["repository"] != BASE_IMAGE_REPOSITORY
    ] == []


async def test_seed_rebuilda_somente_a_imagem_cujo_contexto_mudou(tmp_path):
    settings = _settings(tmp_path)
    conn = connect(settings.db_path)
    init_db(conn)
    conn.close()
    root = tmp_path / "agent-images"
    _make_context(root)
    runtime = FakeContainerRuntime()
    await seed_agent_images(settings, runtime, base_dir=root)

    alvo = AGENT_IMAGES[2]
    (root / alvo.context_subdir / "Dockerfile").write_text(
        "FROM wcui-agent-base:latest\nRUN echo mudou\n", encoding="utf-8"
    )

    runtime.build_calls.clear()
    await seed_agent_images(settings, runtime, base_dir=root)

    reconstruidas = [
        c["repository"]
        for c in runtime.build_calls
        if c["repository"] != BASE_IMAGE_REPOSITORY
    ]
    assert reconstruidas == [alvo.repository]
    assert len(_agent_rows(settings)) == 5


async def test_seed_isola_falha_de_uma_imagem(tmp_path):
    settings = _settings(tmp_path)
    conn = connect(settings.db_path)
    init_db(conn)
    conn.close()
    root = tmp_path / "agent-images"
    _make_context(root)
    falha = AGENT_IMAGES[1]

    class RuntimeComFalha(FakeContainerRuntime):
        async def build_image(self, context_dir, repository, tag, *, buildargs=None):
            if repository == falha.repository:
                self.build_calls.append(
                    {
                        "context_dir": context_dir,
                        "repository": repository,
                        "tag": tag,
                        "buildargs": dict(buildargs) if buildargs else {},
                    }
                )
                raise RuntimeOperationError("falha proposital")
            async for progress in super().build_image(
                context_dir, repository, tag, buildargs=buildargs
            ):
                yield progress

    runtime = RuntimeComFalha()
    await seed_agent_images(settings, runtime, base_dir=root)

    rows = {row["repository"]: row for row in _agent_rows(settings)}
    assert len(rows) == 5
    assert rows[falha.repository]["pull_state"] == "failed"
    assert "falha proposital" in rows[falha.repository]["pull_error"]
    for spec in AGENT_IMAGES:
        if spec.repository != falha.repository:
            assert rows[spec.repository]["pull_state"] == "ready"


async def test_seed_constroi_a_base_antes_dos_agentes(tmp_path):
    settings = _settings(tmp_path)
    conn = connect(settings.db_path)
    init_db(conn)
    conn.close()
    root = tmp_path / "agent-images"
    _make_context(root)

    runtime = FakeContainerRuntime()
    await seed_agent_images(settings, runtime, base_dir=root)

    assert runtime.build_calls[0]["repository"] == BASE_IMAGE_REPOSITORY
    assert {c["repository"] for c in runtime.build_calls[1:]} == {
        spec.repository for spec in AGENT_IMAGES
    }


def test_hash_inclui_a_base_e_muda_com_o_conteudo(tmp_path):
    root = tmp_path / "agent-images"
    _make_context(root)
    spec = AGENT_IMAGES[0]
    original = build_hash_for(spec, root)

    (root / "_base" / "Dockerfile").write_text("FROM debian:trixie-slim\n", encoding="utf-8")
    assert build_hash_for(spec, root) != original


def test_hash_muda_so_com_skills_vinculadas_sem_tocar_arquivo(tmp_path):
    root = tmp_path / "agent-images"
    _make_context(root)
    spec = AGENT_IMAGES[0]

    sem_skills = build_hash_for(spec, root)
    com_skills = build_hash_for(spec, root, skill_refs=["owner/repo"])

    assert com_skills != sem_skills
    # mesma lista, em outra ordem: hash estável (ordenação interna)
    assert build_hash_for(spec, root, skill_refs=["owner/repo"]) == com_skills


async def test_seed_resolve_skills_vinculadas_e_passa_nos_buildargs(tmp_path):
    settings = _settings(tmp_path)
    conn = connect(settings.db_path)
    init_db(conn)
    conn.close()
    root = tmp_path / "agent-images"
    _make_context(root)

    runtime = FakeContainerRuntime()
    await seed_agent_images(settings, runtime, base_dir=root)

    alvo = AGENT_IMAGES[0]
    conn = connect(settings.db_path)
    try:
        image_id = conn.execute(
            "SELECT id FROM images WHERE repository = ?", (alvo.repository,)
        ).fetchone()[0]
        skill_id = create_skill(conn, "Minha skill", "owner", "repo")
        link_skill(conn, image_id, skill_id)
    finally:
        conn.close()

    runtime.build_calls.clear()
    await seed_agent_images(settings, runtime, base_dir=root)  # hash mudou: rebuilda

    builds_do_alvo = [c for c in runtime.build_calls if c["repository"] == alvo.repository]
    assert len(builds_do_alvo) == 1
    assert builds_do_alvo[0]["buildargs"] == {"SKILLS": "owner/repo"}


async def test_rebuild_agent_image_resolve_skills_atuais_do_banco(tmp_path):
    settings = _settings(tmp_path)
    conn = connect(settings.db_path)
    init_db(conn)
    conn.close()
    root = tmp_path / "agent-images"
    _make_context(root)

    runtime = FakeContainerRuntime()
    await seed_agent_images(settings, runtime, base_dir=root)

    alvo = AGENT_IMAGES[0]
    conn = connect(settings.db_path)
    try:
        image_id = conn.execute(
            "SELECT id FROM images WHERE repository = ?", (alvo.repository,)
        ).fetchone()[0]
        skill_id = create_skill(conn, "Minha skill", "owner", "repo")
        link_skill(conn, image_id, skill_id)
    finally:
        conn.close()

    runtime.build_calls.clear()
    await rebuild_agent_image(settings, runtime, image_id, base_dir=root)

    assert len(runtime.build_calls) == 1
    assert runtime.build_calls[0]["repository"] == alvo.repository
    assert runtime.build_calls[0]["buildargs"] == {"SKILLS": "owner/repo"}

    conn = connect(settings.db_path)
    row = conn.execute("SELECT pull_state FROM images WHERE id = ?", (image_id,)).fetchone()
    conn.close()
    assert row["pull_state"] == "ready"


def test_seed_roda_no_lifespan_e_deixa_as_cinco_prontas(client):
    conn = connect(client.app.state.settings.db_path)
    try:
        rows = conn.execute(
            "SELECT pull_state FROM images WHERE provision_kind = 'build'"
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == 5
    assert all(row["pull_state"] == "ready" for row in rows)


def test_retry_de_imagem_buildada_dispara_build_e_nao_download(
    client, seed_user, app_settings, fake_runtime
):
    _login_admin(client, seed_user)
    spec = AGENT_IMAGES[3]
    conn = connect(app_settings.db_path)
    row = conn.execute(
        "SELECT id FROM images WHERE repository = ? AND tag = ?",
        (spec.repository, spec.tag),
    ).fetchone()
    conn.execute("UPDATE images SET pull_state = 'failed', pull_error = 'erro' WHERE id = ?", (row["id"],))
    conn.close()

    fake_runtime.build_calls.clear()
    fake_runtime.pull_calls.clear()
    resp = client.post(f"/api/admin/images/{row['id']}/retry-pull")

    assert resp.status_code == 200
    assert resp.json()["pull_state"] == "pulling"
    _wait_for(
        lambda: any(c["repository"] == spec.repository for c in fake_runtime.build_calls)
    )
    assert fake_runtime.pull_calls == []


def test_retry_de_imagem_de_download_continua_disparando_download(
    client, seed_user, app_settings, fake_runtime
):
    _login_admin(client, seed_user)
    criada = client.post(
        "/api/admin/images",
        json={"display_name": "Webtop", "repository": "exemplo/webtop", "tag": "latest"},
    ).json()
    conn = connect(app_settings.db_path)
    conn.execute(
        "UPDATE images SET pull_state = 'failed', pull_error = 'erro' WHERE id = ?",
        (criada["id"],),
    )
    conn.close()

    fake_runtime.build_calls.clear()
    fake_runtime.pull_calls.clear()
    resp = client.post(f"/api/admin/images/{criada['id']}/retry-pull")

    assert resp.status_code == 200
    _wait_for(
        lambda: any(c["repository"] == "exemplo/webtop" for c in fake_runtime.pull_calls)
    )
    assert fake_runtime.build_calls == []


def _login_admin(client, seed_user, email="admin@exemplo.test", password="senha-admin-123"):
    seed_user(email, password, is_admin=True)
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
