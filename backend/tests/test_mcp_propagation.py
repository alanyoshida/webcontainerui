"""Testes da escrita do config de MCP no container (merge + validação
pós-escrita) e da propagação para instâncias vivas (tarefas 7.4 e 8.1)."""

import io
import itertools
import json
import tarfile


import pytest

from app.runtime.fake import FakeContainerRuntime
from app.runtime.protocol import ContainerSpec
from app.services.images import get_image
from app.services.mcp_servers import (
    apply_mcp_config_to_container,
    create_mcp_server,
    link_mcp_server,
    propagate_mcp_removal_to_live_instances,
    propagate_mcp_servers_to_live_instances,
    unlink_mcp_server,
)

from .conftest import insert_image, insert_instance, insert_user


def _spec():
    return ContainerSpec(
        name="x",
        repository="wcui-agent-claude-code",
        tag="latest",
        network="wcui_net",
        volume_name="vol",
        volume_mount_path="/config",
        env={},
        mem_limit_mb=64,
        cpu_limit=0.5,
        shm_size_mb=64,
    )


def _tar_of(name: str, content: bytes) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        info = tarfile.TarInfo(name=name)
        info.size = len(content)
        tar.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


def _seed_instance(db_conn, image_id: int, container_id: str) -> str:
    """Instância viva apontando para um container do runtime fake."""
    user_id = insert_user(db_conn, email=f"u{next(_counter)}@exemplo.test")
    instance_id = insert_instance(db_conn, user_id, image_id)
    db_conn.execute(
        "UPDATE instances SET container_id = ? WHERE id = ?", (container_id, instance_id)
    )
    return instance_id


_counter = itertools.count(1)


@pytest.fixture
def image_id(db_conn):
    return insert_image(db_conn, repository="wcui-agent-claude-code", provision_kind="build")


@pytest.fixture
def runtime():
    return FakeContainerRuntime()


# ------------------------------------------------- tarefa 7.4 (escrita+validação)

async def test_escrita_faz_merge_e_valida_de_volta(db_conn, runtime, app_settings, image_id):
    mcp_id = create_mcp_server(
        db_conn, "Local", "stdio", settings=app_settings, command="npx", args=["-y", "pkg"]
    )
    link_mcp_server(db_conn, image_id, mcp_id)
    container_id = await runtime.create_container(_spec())
    await runtime.put_archive(
        container_id,
        "/config",
        _tar_of(
            ".claude.json",
            json.dumps({"outraChave": {"estado": 1}, "mcpServers": {"antigo": {}}}).encode(),
        ),
    )

    errors = await apply_mcp_config_to_container(
        db_conn, runtime, app_settings, get_image(db_conn, image_id), container_id
    )

    assert errors == []
    escrito = json.loads(runtime._files[container_id]["/config/.claude.json"])
    assert escrito["outraChave"] == {"estado": 1}  # estado alheio sobrevive
    assert set(escrito["mcpServers"]) == {"Local"}  # estado inteiro recomputado


async def test_validacao_pos_escrita_detecta_quebra_sem_excecao(db_conn, runtime, app_settings, image_id):
    """Cadastro que o tradutor deixa passar (aqui, `args` com tipo errado —
    gravado direto no banco, simulando um bug de tradutor ou mudança de
    versão da ferramenta) é escrito e a validação de volta reporta o campo
    — sem lançar exceção, e sem desfazer a escrita."""
    mcp_id = create_mcp_server(
        db_conn, "Quebrado", "stdio", settings=app_settings, command="npx", args=["-y"]
    )
    db_conn.execute("UPDATE mcp_servers SET args_json = '\"texto\"' WHERE id = ?", (mcp_id,))
    link_mcp_server(db_conn, image_id, mcp_id)
    container_id = await runtime.create_container(_spec())

    errors = await apply_mcp_config_to_container(
        db_conn, runtime, app_settings, get_image(db_conn, image_id), container_id
    )

    assert errors == ["MCP 'Quebrado': campo 'args': 'texto' is not of type 'array'"]
    assert "/config/.claude.json" in runtime._files[container_id]


async def test_escrita_do_hermes_gera_yaml_e_env(db_conn, runtime, app_settings):
    image_id = insert_image(db_conn, repository="wcui-agent-hermes", provision_kind="build")
    mcp_id = create_mcp_server(
        db_conn,
        "Remoto",
        "sse",
        settings=app_settings,
        url="https://mcp.test/sse",
        headers={"Authorization": "Bearer abc-123"},
    )
    link_mcp_server(db_conn, image_id, mcp_id)
    container_id = await runtime.create_container(_spec())

    errors = await apply_mcp_config_to_container(
        db_conn, runtime, app_settings, get_image(db_conn, image_id), container_id
    )

    assert errors == []
    yaml_text = runtime._files[container_id]["/config/.hermes/config.yaml"].decode()
    assert "url: https://mcp.test/sse" in yaml_text
    assert "Bearer ${MCP_REMOTO_API_KEY}" in yaml_text
    env_text = runtime._files[container_id]["/config/.hermes/.env"].decode()
    assert env_text == "MCP_REMOTO_API_KEY=abc-123\n"


# --------------------------------------------------- tarefa 8.1 (propagação)

async def test_propagacao_alcancas_instancias_vivas_e_isola_falhas(
    db_conn, runtime, app_settings, image_id
):
    mcp_id = create_mcp_server(db_conn, "Local", "stdio", settings=app_settings, command="npx")
    link_mcp_server(db_conn, image_id, mcp_id)
    container_instavel = await runtime.create_container(_spec())
    instancia_instavel = _seed_instance(db_conn, image_id, container_instavel)
    container_ok = await runtime.create_container(_spec())
    _seed_instance(db_conn, image_id, container_ok)
    runtime.fail_next("get_archive", RuntimeError("docker indisponível"))

    failures, validation = await propagate_mcp_servers_to_live_instances(
        db_conn, runtime, app_settings, image_id
    )

    assert [(f["instance_id"], f["error"]) for f in failures] == [
        (instancia_instavel, "docker indisponível")
    ]
    assert validation == []
    escrito = json.loads(runtime._files[container_ok]["/config/.claude.json"])
    assert "Local" in escrito["mcpServers"]  # a outra instância recebeu normalmente


async def test_propagacao_reporta_quebra_de_contrato_por_instancia(
    db_conn, runtime, app_settings, image_id
):
    mcp_id = create_mcp_server(
        db_conn, "Quebrado", "stdio", settings=app_settings, command="npx", args=["-y"]
    )
    db_conn.execute("UPDATE mcp_servers SET args_json = '\"texto\"' WHERE id = ?", (mcp_id,))
    link_mcp_server(db_conn, image_id, mcp_id)
    container_id = await runtime.create_container(_spec())
    instance_id = _seed_instance(db_conn, image_id, container_id)

    failures, validation = await propagate_mcp_servers_to_live_instances(
        db_conn, runtime, app_settings, image_id
    )

    assert failures == []
    assert len(validation) == 1
    assert validation[0]["instance_id"] == instance_id
    assert validation[0]["error"] == "MCP 'Quebrado': campo 'args': 'texto' is not of type 'array'"


async def test_propagacao_sem_instancia_viva_nao_faz_nada(db_conn, runtime, app_settings, image_id):
    mcp_id = create_mcp_server(db_conn, "Local", "stdio", settings=app_settings, command="npx")
    link_mcp_server(db_conn, image_id, mcp_id)

    failures, validation = await propagate_mcp_servers_to_live_instances(
        db_conn, runtime, app_settings, image_id
    )

    assert failures == [] and validation == []
    assert runtime.put_archive_calls == []


async def test_propagacao_de_imagem_desconhecida_e_inofensiva(db_conn, runtime, app_settings):
    failures, validation = await propagate_mcp_servers_to_live_instances(
        db_conn, runtime, app_settings, 999
    )
    assert failures == [] and validation == []


async def test_removal_recompute_deixa_arquivo_sem_o_servidor(db_conn, runtime, app_settings):
    image_id = insert_image(db_conn, repository="wcui-agent-claude-code", provision_kind="build")
    mcp_id = create_mcp_server(db_conn, "Alvo", "stdio", settings=app_settings, command="npx")
    outro_id = create_mcp_server(db_conn, "Outro", "stdio", settings=app_settings, command="python")
    link_mcp_server(db_conn, image_id, mcp_id)
    link_mcp_server(db_conn, image_id, outro_id)
    container_id = await runtime.create_container(_spec())
    _seed_instance(db_conn, image_id, container_id)

    # Remoção: o serviço apaga os vínculos (o que `delete_mcp_server` faz)
    # e o chamador propaga para as imagens afetadas.
    unlink_mcp_server(db_conn, image_id, mcp_id)
    failures, validation = await propagate_mcp_removal_to_live_instances(
        db_conn, runtime, app_settings, [image_id]
    )

    assert failures == [] and validation == []
    escrito = json.loads(runtime._files[container_id]["/config/.claude.json"])
    assert set(escrito["mcpServers"]) == {"Outro"}
