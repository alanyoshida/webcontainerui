"""Testes da biblioteca de servidores MCP e do seu vínculo com imagens."""

import pytest

from app.services.errors import ConflictError, NotFoundError, ValidationFailedError
from app.services.mcp_servers import (
    create_mcp_server,
    decrypt_dict,
    delete_mcp_server,
    get_mcp_server,
    has_secret,
    link_mcp_server,
    linked_mcp_server_ids,
    list_images_with_mcp_servers,
    list_mcp_servers,
    resolve_image_mcp_servers,
    unlink_mcp_server,
    update_mcp_server,
)

from .conftest import insert_image


def test_criacao_listagem_e_recuperacao(db_conn, app_settings):
    id1 = create_mcp_server(
        db_conn, "Servidor B", "stdio", settings=app_settings, command="npx", args=["-y", "pkg"]
    )
    id2 = create_mcp_server(db_conn, "Servidor A", "http", settings=app_settings, url="https://x.test/mcp")

    nomes = [row["display_name"] for row in list_mcp_servers(db_conn)]
    assert nomes == ["Servidor A", "Servidor B"]  # ordenado por nome

    mcp = get_mcp_server(db_conn, id1)
    assert mcp["display_name"] == "Servidor B"
    assert mcp["transport"] == "stdio"
    assert mcp["command"] == "npx"
    assert mcp["linked_images"] == 0
    assert id2 != id1


def test_nome_duplicado_e_recusado_com_conflito(db_conn, app_settings):
    create_mcp_server(db_conn, "MCP", "stdio", settings=app_settings, command="npx")
    with pytest.raises(ConflictError):
        create_mcp_server(db_conn, "MCP", "stdio", settings=app_settings, command="outro")


def test_stdio_sem_comando_e_recusado(db_conn, app_settings):
    with pytest.raises(ValidationFailedError):
        create_mcp_server(db_conn, "MCP", "stdio", settings=app_settings)


def test_remoto_sem_url_e_recusado(db_conn, app_settings):
    with pytest.raises(ValidationFailedError):
        create_mcp_server(db_conn, "MCP", "http", settings=app_settings)


def test_transporte_invalido_e_recusado(db_conn, app_settings):
    with pytest.raises(ValidationFailedError):
        create_mcp_server(db_conn, "MCP", "websocket", settings=app_settings, url="https://x.test")


def test_env_e_headers_sao_cifrados_e_decifraveis(db_conn, app_settings):
    mcp_id = create_mcp_server(
        db_conn,
        "MCP",
        "stdio",
        settings=app_settings,
        command="npx",
        env={"API_KEY": "segredo-123"},
    )

    row = get_mcp_server(db_conn, mcp_id)
    assert row["env_encrypted"] is not None
    assert b"segredo-123" not in row["env_encrypted"]  # nao fica em claro no blob
    assert has_secret(row, "env") is True
    assert has_secret(row, "headers") is False
    assert decrypt_dict(app_settings, row["env_encrypted"]) == {"API_KEY": "segredo-123"}


def test_resolve_image_mcp_servers_decifra_env_e_headers(db_conn, app_settings):
    image_id = insert_image(db_conn, provision_kind="build")
    mcp_id = create_mcp_server(
        db_conn,
        "MCP",
        "http",
        settings=app_settings,
        url="https://x.test/mcp",
        headers={"Authorization": "Bearer abc"},
    )
    link_mcp_server(db_conn, image_id, mcp_id)

    resolved = resolve_image_mcp_servers(db_conn, app_settings, image_id)
    assert len(resolved) == 1
    assert resolved[0]["headers"] == {"Authorization": "Bearer abc"}
    assert resolved[0]["url"] == "https://x.test/mcp"


def test_edicao_parcial_nao_apaga_o_resto(db_conn, app_settings):
    mcp_id = create_mcp_server(
        db_conn, "MCP", "stdio", settings=app_settings, command="npx", args=["-y", "pkg"]
    )

    update_mcp_server(db_conn, mcp_id, settings=app_settings, display_name="MCP renomeado")

    row = get_mcp_server(db_conn, mcp_id)
    assert row["display_name"] == "MCP renomeado"
    assert row["command"] == "npx"  # intacto
    assert row["updated_at"] is not None


def test_edicao_de_inexistente_e_nao_encontrado(db_conn, app_settings):
    with pytest.raises(NotFoundError):
        update_mcp_server(db_conn, 999, settings=app_settings, display_name="x")


def test_remocao_permitida_mesmo_com_vinculo_ativo_e_desvincula(db_conn, app_settings):
    image_id_1 = insert_image(db_conn, repository="r1/teste", provision_kind="build")
    image_id_2 = insert_image(db_conn, repository="r2/teste", provision_kind="build")
    mcp_id = create_mcp_server(db_conn, "MCP", "stdio", settings=app_settings, command="npx")
    link_mcp_server(db_conn, image_id_1, mcp_id)
    link_mcp_server(db_conn, image_id_2, mcp_id)

    delete_mcp_server(db_conn, mcp_id)

    with pytest.raises(NotFoundError):
        get_mcp_server(db_conn, mcp_id)
    assert linked_mcp_server_ids(db_conn, image_id_1) == []
    assert linked_mcp_server_ids(db_conn, image_id_2) == []


def test_remocao_de_inexistente_e_nao_encontrado(db_conn):
    with pytest.raises(NotFoundError):
        delete_mcp_server(db_conn, 999)


def test_vinculo_e_desvinculo_entre_mcp_e_imagem_de_build(db_conn, app_settings):
    image_id = insert_image(db_conn, provision_kind="build")
    mcp_id = create_mcp_server(db_conn, "MCP", "stdio", settings=app_settings, command="npx")

    link_mcp_server(db_conn, image_id, mcp_id)
    assert linked_mcp_server_ids(db_conn, image_id) == [mcp_id]
    assert get_mcp_server(db_conn, mcp_id)["linked_images"] == 1

    unlink_mcp_server(db_conn, image_id, mcp_id)
    assert linked_mcp_server_ids(db_conn, image_id) == []
    assert get_mcp_server(db_conn, mcp_id)["linked_images"] == 0


def test_vincular_mcp_duas_vezes_e_idempotente(db_conn, app_settings):
    image_id = insert_image(db_conn, provision_kind="build")
    mcp_id = create_mcp_server(db_conn, "MCP", "stdio", settings=app_settings, command="npx")

    link_mcp_server(db_conn, image_id, mcp_id)
    link_mcp_server(db_conn, image_id, mcp_id)

    assert linked_mcp_server_ids(db_conn, image_id) == [mcp_id]


def test_imagem_pode_ter_n_mcps_e_mcp_pode_estar_em_n_imagens(db_conn, app_settings):
    image_id_1 = insert_image(db_conn, repository="r1/teste", provision_kind="build")
    image_id_2 = insert_image(db_conn, repository="r2/teste", provision_kind="build")
    mcp_id_1 = create_mcp_server(db_conn, "MCP 1", "stdio", settings=app_settings, command="npx")
    mcp_id_2 = create_mcp_server(db_conn, "MCP 2", "stdio", settings=app_settings, command="npx")

    link_mcp_server(db_conn, image_id_1, mcp_id_1)
    link_mcp_server(db_conn, image_id_1, mcp_id_2)
    link_mcp_server(db_conn, image_id_2, mcp_id_1)

    assert sorted(linked_mcp_server_ids(db_conn, image_id_1)) == sorted([mcp_id_1, mcp_id_2])
    assert linked_mcp_server_ids(db_conn, image_id_2) == [mcp_id_1]

    unlink_mcp_server(db_conn, image_id_1, mcp_id_1)
    assert linked_mcp_server_ids(db_conn, image_id_2) == [mcp_id_1]  # outra imagem não afetada


def test_vincular_mcp_a_imagem_pull_e_recusado(db_conn, app_settings):
    image_id = insert_image(db_conn, provision_kind="pull")
    mcp_id = create_mcp_server(db_conn, "MCP", "stdio", settings=app_settings, command="npx")

    with pytest.raises(ValidationFailedError):
        link_mcp_server(db_conn, image_id, mcp_id)
    assert linked_mcp_server_ids(db_conn, image_id) == []


def test_vincular_mcp_a_imagem_inexistente_e_nao_encontrado(db_conn, app_settings):
    mcp_id = create_mcp_server(db_conn, "MCP", "stdio", settings=app_settings, command="npx")
    with pytest.raises(NotFoundError):
        link_mcp_server(db_conn, 999, mcp_id)


def test_vincular_mcp_inexistente_e_nao_encontrado(db_conn):
    image_id = insert_image(db_conn, provision_kind="build")
    with pytest.raises(NotFoundError):
        link_mcp_server(db_conn, image_id, 999)


def test_list_images_with_mcp_servers_so_traz_imagens_de_build(db_conn):
    build_id = insert_image(db_conn, repository="r1/teste", provision_kind="build")
    insert_image(db_conn, repository="r2/teste", provision_kind="pull")

    imagens = [row["id"] for row in list_images_with_mcp_servers(db_conn)]
    assert imagens == [build_id]
