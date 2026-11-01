"""Testes da biblioteca de skills e do seu vínculo com imagens de agente."""

import pytest

from app.services.agent_skills import (
    create_skill,
    delete_skill,
    get_skill,
    link_skill,
    linked_skill_ids,
    list_images_with_skills,
    list_skills,
    resolve_image_skill_refs,
    unlink_skill,
    update_skill,
)
from app.services.errors import ConflictError, NotFoundError, ValidationFailedError

from .conftest import insert_image


def test_criacao_listagem_e_recuperacao(db_conn):
    id1 = create_skill(db_conn, "Onboarding", "skills", "secure-code-game", "onboarding")
    id2 = create_skill(db_conn, "Draft PR", "skills", "secure-code-game", "draft-pr")

    nomes = [row["display_name"] for row in list_skills(db_conn)]
    assert nomes == ["Draft PR", "Onboarding"]  # ordenado por nome

    skill = get_skill(db_conn, id1)
    assert skill["display_name"] == "Onboarding"
    assert skill["repo_owner"] == "skills"
    assert skill["repo_name"] == "secure-code-game"
    assert skill["subpath"] == "onboarding"
    assert skill["linked_images"] == 0
    assert id2 != id1


def test_nome_duplicado_e_recusado_com_conflito(db_conn):
    create_skill(db_conn, "Minha skill", "owner", "repo-a")
    with pytest.raises(ConflictError):
        create_skill(db_conn, "Minha skill", "owner", "repo-b")


def test_repo_e_subpath_duplicados_sao_recusados_com_conflito(db_conn):
    create_skill(db_conn, "Skill A", "owner", "repo", "onboarding")
    with pytest.raises(ConflictError):
        create_skill(db_conn, "Skill B", "owner", "repo", "onboarding")


def test_nome_vazio_e_owner_repo_vazio_sao_recusados(db_conn):
    with pytest.raises(ValidationFailedError):
        create_skill(db_conn, "  ", "owner", "repo")
    with pytest.raises(ValidationFailedError):
        create_skill(db_conn, "Nome", "  ", "repo")
    with pytest.raises(ValidationFailedError):
        create_skill(db_conn, "Nome", "owner", "  ")


def test_edicao_parcial_nao_apaga_o_resto(db_conn):
    skill_id = create_skill(db_conn, "Skill", "owner", "repo", "sub")

    update_skill(db_conn, skill_id, display_name="Skill renomeada")

    skill = get_skill(db_conn, skill_id)
    assert skill["display_name"] == "Skill renomeada"
    assert skill["repo_owner"] == "owner"  # intacto
    assert skill["subpath"] == "sub"  # intacto
    assert skill["updated_at"] is not None


def test_edicao_de_inexistente_e_nao_encontrado(db_conn):
    with pytest.raises(NotFoundError):
        update_skill(db_conn, 999, display_name="x")


def test_edicao_para_nome_existente_e_conflito(db_conn):
    id1 = create_skill(db_conn, "A", "owner", "repo-a")
    create_skill(db_conn, "B", "owner", "repo-b")
    with pytest.raises(ConflictError):
        update_skill(db_conn, id1, display_name="B")


def test_remocao_permitida_mesmo_com_vinculo_ativo_e_desvincula(db_conn):
    image_id_1 = insert_image(db_conn, repository="r1/teste", provision_kind="build")
    image_id_2 = insert_image(db_conn, repository="r2/teste", provision_kind="build")
    skill_id = create_skill(db_conn, "Skill", "owner", "repo")
    link_skill(db_conn, image_id_1, skill_id)
    link_skill(db_conn, image_id_2, skill_id)

    delete_skill(db_conn, skill_id)

    with pytest.raises(NotFoundError):
        get_skill(db_conn, skill_id)
    assert linked_skill_ids(db_conn, image_id_1) == []
    assert linked_skill_ids(db_conn, image_id_2) == []


def test_remocao_de_inexistente_e_nao_encontrado(db_conn):
    with pytest.raises(NotFoundError):
        delete_skill(db_conn, 999)


def test_vinculo_e_desvinculo_entre_skill_e_imagem_de_build(db_conn):
    image_id = insert_image(db_conn, provision_kind="build")
    skill_id = create_skill(db_conn, "Skill", "owner", "repo")

    link_skill(db_conn, image_id, skill_id)
    assert linked_skill_ids(db_conn, image_id) == [skill_id]
    assert get_skill(db_conn, skill_id)["linked_images"] == 1

    unlink_skill(db_conn, image_id, skill_id)
    assert linked_skill_ids(db_conn, image_id) == []
    assert get_skill(db_conn, skill_id)["linked_images"] == 0


def test_vincular_skill_duas_vezes_e_idempotente(db_conn):
    image_id = insert_image(db_conn, provision_kind="build")
    skill_id = create_skill(db_conn, "Skill", "owner", "repo")

    link_skill(db_conn, image_id, skill_id)
    link_skill(db_conn, image_id, skill_id)  # não duplica, não falha

    assert linked_skill_ids(db_conn, image_id) == [skill_id]


def test_imagem_pode_ter_n_skills_e_skill_pode_estar_em_n_imagens(db_conn):
    image_id_1 = insert_image(db_conn, repository="r1/teste", provision_kind="build")
    image_id_2 = insert_image(db_conn, repository="r2/teste", provision_kind="build")
    skill_id_1 = create_skill(db_conn, "Skill 1", "owner", "repo-1")
    skill_id_2 = create_skill(db_conn, "Skill 2", "owner", "repo-2")

    link_skill(db_conn, image_id_1, skill_id_1)
    link_skill(db_conn, image_id_1, skill_id_2)
    link_skill(db_conn, image_id_2, skill_id_1)

    assert sorted(linked_skill_ids(db_conn, image_id_1)) == sorted([skill_id_1, skill_id_2])
    assert linked_skill_ids(db_conn, image_id_2) == [skill_id_1]

    unlink_skill(db_conn, image_id_1, skill_id_1)
    assert linked_skill_ids(db_conn, image_id_2) == [skill_id_1]  # outra imagem não afetada


def test_vincular_skill_a_imagem_pull_e_recusado(db_conn):
    image_id = insert_image(db_conn, provision_kind="pull")
    skill_id = create_skill(db_conn, "Skill", "owner", "repo")

    with pytest.raises(ValidationFailedError):
        link_skill(db_conn, image_id, skill_id)
    assert linked_skill_ids(db_conn, image_id) == []


def test_vincular_skill_a_imagem_inexistente_e_nao_encontrado(db_conn):
    skill_id = create_skill(db_conn, "Skill", "owner", "repo")
    with pytest.raises(NotFoundError):
        link_skill(db_conn, 999, skill_id)


def test_vincular_skill_inexistente_e_nao_encontrado(db_conn):
    image_id = insert_image(db_conn, provision_kind="build")
    with pytest.raises(NotFoundError):
        link_skill(db_conn, image_id, 999)


def test_list_images_with_skills_so_traz_imagens_de_build(db_conn):
    build_id = insert_image(db_conn, repository="r1/teste", provision_kind="build")
    insert_image(db_conn, repository="r2/teste", provision_kind="pull")

    imagens = [row["id"] for row in list_images_with_skills(db_conn)]
    assert imagens == [build_id]


def test_resolve_image_skill_refs_monta_owner_repo_e_subpath_ordenado(db_conn):
    image_id = insert_image(db_conn, provision_kind="build")
    skill_simples = create_skill(db_conn, "B simples", "owner", "repo-simples")
    skill_com_subpath = create_skill(db_conn, "A com subpath", "owner", "repo", "onboarding")
    link_skill(db_conn, image_id, skill_simples)
    link_skill(db_conn, image_id, skill_com_subpath)

    refs = resolve_image_skill_refs(db_conn, image_id)

    # ordenado por display_name: "A com subpath" antes de "B simples"
    assert refs == ["owner/repo:onboarding", "owner/repo-simples"]


def test_resolve_image_skill_refs_vazio_sem_vinculo(db_conn):
    image_id = insert_image(db_conn, provision_kind="build")
    assert resolve_image_skill_refs(db_conn, image_id) == []
