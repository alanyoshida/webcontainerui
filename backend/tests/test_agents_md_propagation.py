"""Testes da propagacao e remocao do documento em instancias vivas."""

import io
import tarfile

from app.db import connect, init_db
from app.runtime.errors import RuntimeOperationError
from app.services.agents_md import (
    create_document,
    propagate_document_to_live_instances,
    remove_document_from_live_instances,
    set_image_document,
    update_document,
)
from app.services.instances import create_instance
from app.services.passwords import hash_password

from .conftest import add_user_to_group, grant_image_to_group, insert_group, insert_image


def _tar_content(tar_bytes):
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r") as tar:
        return tar.extractfile("AGENTS.md").read()


def _login(client, email, password="senha-usuario-123"):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["id"]


def _criar_usuario_com_imagens(seed_user, client, app_settings, email, repositories):
    seed_user(email, "senha-usuario-123")
    user_id = _login(client, email)
    conn = connect(app_settings.db_path)
    init_db(conn)
    image_ids = []
    for repository in repositories:
        image_ids.append(insert_image(conn, repository=repository))
    group_id = insert_group(conn, "grupo-" + email)
    add_user_to_group(conn, user_id, group_id)
    for image_id in image_ids:
        grant_image_to_group(conn, group_id, image_id)
    document_id = create_document(conn, "Regras", "# Regras", settings=app_settings)
    for image_id in image_ids:
        set_image_document(conn, image_id, document_id)
    conn.close()
    return user_id, image_ids, document_id


async def test_editar_documento_propaga_para_instancias_vivas(client, seed_user, app_settings, fake_runtime):
    user_id, image_ids, document_id = _criar_usuario_com_imagens(
        seed_user, client, app_settings, "prop-edita@exemplo.test", ["r-prop-a", "r-prop-b"]
    )
    conn = connect(app_settings.db_path)
    for image_id in image_ids:
        await create_instance(conn, fake_runtime, app_settings, user_id, image_id)
    conn.close()
    fake_runtime.put_archive_calls.clear()

    conn = connect(app_settings.db_path)
    update_document(conn, document_id, content="# versao 2", settings=app_settings)
    failures = await propagate_document_to_live_instances(
        conn, fake_runtime, app_settings, document_id
    )
    conn.close()

    assert failures == []
    assert len(fake_runtime.put_archive_calls) == 2
    esperado = _tar_content(fake_runtime.put_archive_calls[0]["tar_bytes"])
    assert esperado.rstrip() == "# versao 2".encode()


async def test_propagacao_nao_alcanca_instancia_parada(client, seed_user, app_settings, fake_runtime):
    user_id, image_ids, document_id = _criar_usuario_com_imagens(
        seed_user, client, app_settings, "prop-parada@exemplo.test", ["r-parada"]
    )
    conn = connect(app_settings.db_path)
    await create_instance(conn, fake_runtime, app_settings, user_id, image_ids[0])
    conn.execute("UPDATE instances SET state = 'stopped'")
    fake_runtime.put_archive_calls.clear()

    failures = await propagate_document_to_live_instances(
        conn, fake_runtime, app_settings, document_id
    )

    assert failures == []
    assert fake_runtime.put_archive_calls == []
    conn.close()


async def test_vincular_propaga_para_instancias_vivas(client, seed_user, app_settings, fake_runtime):
    user_id, image_ids, document_id = _criar_usuario_com_imagens(
        seed_user, client, app_settings, "prop-vincula@exemplo.test", ["r-vinc"]
    )
    image_id = image_ids[0]
    conn = connect(app_settings.db_path)
    instance = await create_instance(conn, fake_runtime, app_settings, user_id, image_id)
    fake_runtime.put_archive_calls.clear()
    set_image_document(conn, image_id, document_id)
    failures = await propagate_document_to_live_instances(
        conn, fake_runtime, app_settings, document_id
    )
    conn.close()

    assert failures == []
    assert len(fake_runtime.put_archive_calls) == 1
    assert fake_runtime.put_archive_calls[0]["container_id"] == instance["container_id"]


async def test_desvincular_remove_das_instancias_vivas(client, seed_user, app_settings, fake_runtime):
    user_id, image_ids, document_id = _criar_usuario_com_imagens(
        seed_user, client, app_settings, "prop-desvincula@exemplo.test", ["r-desvinc"]
    )
    image_id = image_ids[0]
    conn = connect(app_settings.db_path)
    await create_instance(conn, fake_runtime, app_settings, user_id, image_id)
    container_id = conn.execute(
        "SELECT container_id FROM instances WHERE container_id IS NOT NULL"
    ).fetchone()["container_id"]
    fake_runtime.exec_calls.clear()
    conn.close()

    conn = connect(app_settings.db_path)
    set_image_document(conn, image_id, None)
    failures = await remove_document_from_live_instances(conn, fake_runtime, image_id)
    conn.close()

    assert failures == []
    assert fake_runtime.exec_calls == [
        {"container_id": container_id, "command": ["rm", "-f", "/config/AGENTS.md"]}
    ]


async def test_desvincular_isola_falha_por_instancia(client, seed_user, app_settings, fake_runtime):
    seed_user("prop-falha-a@exemplo.test", "senha-usuario-1234")
    seed_user("prop-falha-b@exemplo.test", "senha-usuario-123")
    user_a = _login(client, "prop-falha-a@exemplo.test", "senha-usuario-1234")
    user_b = _login(client, "prop-falha-b@exemplo.test", "senha-usuario-123")
    conn = connect(app_settings.db_path)
    init_db(conn)
    image_a = insert_image(conn, repository="r-falha-a")
    image_b = insert_image(conn, repository="r-falha-b")
    group_a = insert_group(conn, "grupo-falha-a")
    group_b = insert_group(conn, "grupo-falha-b")
    add_user_to_group(conn, user_a, group_a)
    add_user_to_group(conn, user_b, group_b)
    grant_image_to_group(conn, group_a, image_a)
    grant_image_to_group(conn, group_b, image_b)
    document_id = create_document(conn, "Regras", "# Regras", settings=app_settings)
    set_image_document(conn, image_a, document_id)
    set_image_document(conn, image_b, document_id)
    conn.close()

    conn = connect(app_settings.db_path)
    await create_instance(conn, fake_runtime, app_settings, user_a, image_a)
    conn.close()
    conn = connect(app_settings.db_path)
    conn = connect(app_settings.db_path)
    await create_instance(conn, fake_runtime, app_settings, user_b, image_b)
    conn.close()

    conn = connect(app_settings.db_path)
    fake_runtime.exec_calls.clear()
    fake_runtime.fail_next("exec", RuntimeOperationError("docker exec falhou"))
    failures_a = await remove_document_from_live_instances(conn, fake_runtime, image_a)
    failures_b = await remove_document_from_live_instances(conn, fake_runtime, image_b)
    conn.close()
