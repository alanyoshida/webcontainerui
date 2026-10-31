"""Testes da injeção do documento AGENTS.md na criação da instância."""

import io
import tarfile

from app.db import connect, init_db
from app.services.agents_md import create_document, set_image_document

from .conftest import add_user_to_group, grant_image_to_group, insert_group, insert_image


def _tar_content(tar_bytes: bytes, name: str) -> bytes:
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r") as tar:
        return tar.extractfile(name).read()


def _login_as(client, seed_user, email, password="senha-usuario-123"):
    seed_user(email, password)
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["id"]


def _permitted_image(client, seed_user, app_settings, email, group_name="grupo", **image_kwargs):
    user_id = _login_as(client, seed_user, email)
    conn = connect(app_settings.db_path)
    init_db(conn)
    image_id = insert_image(conn, **image_kwargs)
    group_id = insert_group(conn, group_name)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()
    return user_id, image_id


def test_criacao_injeta_o_documento_vinculado(client, seed_user, app_settings, fake_runtime):
    user_id, image_id = _permitted_image(client, seed_user, app_settings, "doc@exemplo.test")
    conn = connect(app_settings.db_path)
    create_document(conn, "Regras", "# Regras do time", settings=app_settings)
    conn.execute("UPDATE images SET agents_md_id = ?", (1,))
    conn.close()

    resp = client.post("/api/instances", json={"image_id": image_id})
    assert resp.status_code == 201

    # dois arquivos injetados: identidade SSH + documento
    assert len(fake_runtime.put_archive_calls) == 2
    document_tar = fake_runtime.put_archive_calls[1]["tar_bytes"]
    assert _tar_content(document_tar, "AGENTS.md") == b"# Regras do time\n"


def test_criacao_sem_vinculo_nao_injeta_documento(client, seed_user, app_settings, fake_runtime):
    _user_id, image_id = _permitted_image(client, seed_user, app_settings, "semdoc@exemplo.test")

    resp = client.post("/api/instances", json={"image_id": image_id})
    assert resp.status_code == 201

    # só a identidade SSH: o documento ausente não gera segunda chamada
    assert len(fake_runtime.put_archive_calls) == 1


def test_dono_do_documento_conforme_provision_kind(client, seed_user, app_settings, fake_runtime):
    user_id = _login_as(client, seed_user, "dono-unique@exemplo.test")
    conn = connect(app_settings.db_path)
    init_db(conn)
    image_agente = insert_image(conn, repository="wcui-agent-teste", provision_kind="build")
    image_webtop = insert_image(conn, repository="lscr.io/linuxserver/webtop", tag="v2")
    group_id = insert_group(conn, "grupo-unico")
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_agente)
    grant_image_to_group(conn, group_id, image_webtop)
    create_document(conn, "Regras", "# R", settings=app_settings)
    set_image_document(conn, image_agente, 1)
    set_image_document(conn, image_webtop, 1)
    conn.close()

    client.post("/api/instances", json={"image_id": image_agente})
    client.post("/api/instances", json={"image_id": image_webtop})

    # cada criação injetou SSH + documento: tars de documento nos índices 1 e 3
    agente_doc_tar = fake_runtime.put_archive_calls[1]["tar_bytes"]
    webtop_doc_tar = fake_runtime.put_archive_calls[3]["tar_bytes"]
    with tarfile.open(fileobj=io.BytesIO(agente_doc_tar), mode="r") as tar:
        member = tar.getmember("AGENTS.md")
        assert (member.uid, member.gid) == (0, 0)  # agente roda como root
    with tarfile.open(fileobj=io.BytesIO(webtop_doc_tar), mode="r") as tar:
        member = tar.getmember("AGENTS.md")
        assert (member.uid, member.gid) == (app_settings.puid, app_settings.pgid)


def test_falha_de_injecao_do_documento_nao_impede_a_instancia(
    client, seed_user, app_settings, fake_runtime
):
    from app.runtime.errors import RuntimeOperationError

    _user_id, image_id = _permitted_image(client, seed_user, app_settings, "falhadoc@exemplo.test")
    conn = connect(app_settings.db_path)
    create_document(conn, "Regras", "# R", settings=app_settings)
    conn.execute("UPDATE images SET agents_md_id = ?", (1,))
    conn.close()

    # a primeira injeção (SSH, índice 0) falha; o documento (índice 1) também
    # será tentado — ambas best-effort, instância segue pronta.
    fake_runtime.fail_next("put_archive", RuntimeOperationError("docker travou"))

    resp = client.post("/api/instances", json={"image_id": image_id})

    assert resp.status_code == 201  # best-effort: falha engolida
    assert resp.json()["state"] == "running"