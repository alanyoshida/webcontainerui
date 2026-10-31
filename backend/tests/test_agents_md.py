"""Testes da biblioteca de documentos AGENTS.md."""

import pytest

from app.config import Settings
from app.db import connect, init_db
from app.services.agents_md import (
    create_document,
    delete_document,
    get_document,
    get_document_for_image,
    linked_image_ids,
    list_documents,
    set_image_document,
    update_document,
)
from app.services.errors import ConflictError, NotFoundError, ValidationFailedError

from .conftest import insert_image


def test_criacao_listagem_e_recuperacao(db_conn, app_settings):
    id1 = create_document(db_conn, "Padrão da equipe", "# Equipe", settings=app_settings)
    id2 = create_document(db_conn, "Regras backend", "# Backend", settings=app_settings)

    nomes = [row["name"] for row in list_documents(db_conn)]
    assert nomes == ["Padrão da equipe", "Regras backend"]  # ordenado por nome

    doc = get_document(db_conn, id1)
    assert doc["name"] == "Padrão da equipe"
    assert doc["content"] == "# Equipe"
    assert doc["linked_images"] == 0


def test_nome_duplicado_e_recusado_com_conflito(db_conn, app_settings):
    create_document(db_conn, "Padrão", "# P", settings=app_settings)
    with pytest.raises(ConflictError):
        create_document(db_conn, "Padrão", "# Outro", settings=app_settings)


def test_nome_vazio_e_conteudo_vazio_sao_recusados(db_conn, app_settings):
    with pytest.raises(ValidationFailedError):
        create_document(db_conn, "  ", "# x", settings=app_settings)
    with pytest.raises(ValidationFailedError):
        create_document(db_conn, "Nome", "   \n  ", settings=app_settings)


def test_conteudo_acima_do_limite_e_recusado(db_conn, tmp_path):
    settings = Settings(
        db_path=tmp_path / "x.db", uploads_dir=tmp_path / "u", max_agents_md_bytes=10
    )
    with pytest.raises(ValidationFailedError):
        create_document(db_conn, "Grande", "x" * 11, settings=settings)
    # a entrada não pode existir após a recusa
    assert [row["name"] for row in list_documents(db_conn)] == []


def test_edicao_de_nome_e_conteudo(db_conn, app_settings):
    document_id = create_document(db_conn, "Antigo", "# Antigo", settings=app_settings)

    update_document(db_conn, document_id, name="Novo", content="# Novo", settings=app_settings)

    doc = get_document(db_conn, document_id)
    assert doc["name"] == "Novo"
    assert doc["content"] == "# Novo"
    assert doc["updated_at"] is not None


def test_edicao_parcial_nao_apaga_o_resto(db_conn, app_settings):
    document_id = create_document(db_conn, "Doc", "# Original", settings=app_settings)

    update_document(db_conn, document_id, content="# Só conteúdo", settings=app_settings)

    doc = get_document(db_conn, document_id)
    assert doc["name"] == "Doc"  # nome intacto


def test_edicao_de_nome_para_existente_e_conflito(db_conn, app_settings):
    id1 = create_document(db_conn, "A", "# a", settings=app_settings)
    create_document(db_conn, "B", "# b", settings=app_settings)
    with pytest.raises(ConflictError):
        update_document(db_conn, id1, name="B", settings=app_settings)


def test_edicao_de_inexistente_e_nao_encontrado(db_conn, app_settings):
    with pytest.raises(NotFoundError):
        update_document(db_conn, 999, content="x", settings=app_settings)


def test_remocao_recusada_com_vinculo_ativo(db_conn, app_settings):
    document_id = create_document(db_conn, "Doc", "# x", settings=app_settings)
    image_id = insert_image(db_conn)
    set_image_document(db_conn, image_id, document_id)

    with pytest.raises(ConflictError):
        delete_document(db_conn, document_id)

    assert get_document(db_conn, document_id)["name"] == "Doc"  # intacto


def test_remocao_permitida_sem_vinculo(db_conn, app_settings):
    document_id = create_document(db_conn, "Doc", "# x", settings=app_settings)
    delete_document(db_conn, document_id)
    with pytest.raises(NotFoundError):
        get_document(db_conn, document_id)


def test_vinculo_troca_e_remocao_de_vinculo(db_conn, app_settings):
    image_id = insert_image(db_conn)
    id1 = create_document(db_conn, "Doc 1", "# 1", settings=app_settings)
    id2 = create_document(db_conn, "Doc 2", "# 2", settings=app_settings)

    set_image_document(db_conn, image_id, id1)
    assert get_document_for_image(db_conn, image_id)["id"] == id1
    assert linked_image_ids(db_conn, id1) == [image_id]

    set_image_document(db_conn, image_id, id2)  # troca
    assert get_document_for_image(db_conn, image_id)["id"] == id2
    assert linked_image_ids(db_conn, id1) == []  # anterior segue na biblioteca
    assert get_document(db_conn, id1)["name"] == "Doc 1"

    set_image_document(db_conn, image_id, None)  # desvincula
    assert get_document_for_image(db_conn, image_id) is None
    assert get_document(db_conn, id2)["name"] == "Doc 2"  # doc intacto


def test_vinculo_de_imagem_inexistente_e_nao_encontrado(db_conn, app_settings):
    document_id = create_document(db_conn, "Doc", "# x", settings=app_settings)
    with pytest.raises(NotFoundError):
        set_image_document(db_conn, 999, document_id)


def test_vinculo_de_documento_inexistente_e_nao_encontrado(db_conn, app_settings):
    image_id = insert_image(db_conn)
    with pytest.raises(NotFoundError):
        set_image_document(db_conn, image_id, 999)

def test_tar_do_documento_tem_nome_conteudo_modo_e_dono(db_conn):
    import io
    import tarfile

    from app.services.agents_md import build_agents_md_archive

    tar_bytes = build_agents_md_archive("# Regras do projeto", uid=1000, gid=1000)

    with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as tar:
        member = tar.getmember("AGENTS.md")
        assert oct(member.mode) == "0o644"
        assert member.uid == 1000
        assert member.gid == 1000
        assert tar.extractfile("AGENTS.md").read() == b"# Regras do projeto\n"


def test_tar_do_documento_termina_com_quebra_de_linha(db_conn):
    import io
    import tarfile

    from app.services.agents_md import build_agents_md_archive

    tar_bytes = build_agents_md_archive("# sem quebra final", uid=0, gid=0)

    with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as tar:
        assert tar.extractfile("AGENTS.md").read().endswith(b"\n")
