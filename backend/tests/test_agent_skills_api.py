"""Testes de API da biblioteca de skills e do vínculo com imagens de agente."""

import asyncio

from app.db import connect
from app.services.agent_images import AGENT_IMAGES

from .conftest import insert_image


def _login_admin(client, seed_user, email="admin@exemplo.test", password="senha-admin-123"):
    seed_user(email, password, is_admin=True)
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200


def _login_comum(client, seed_user, email="comum@exemplo.test", password="senha-usuario-123"):
    seed_user(email, password)
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200


def test_admin_cria_lista_e_edita_skill(client, seed_user):
    _login_admin(client, seed_user)

    criada = client.post(
        "/api/admin/agent-skills",
        json={"display_name": "Minha skill", "repo_owner": "owner", "repo_name": "repo"},
    )
    assert criada.status_code == 201
    skill_id = criada.json()["id"]
    assert criada.json()["linked_images"] == 0
    assert criada.json()["subpath"] == ""

    editada = client.patch(
        f"/api/admin/agent-skills/{skill_id}",
        json={"display_name": "Minha skill v2", "subpath": "onboarding"},
    )
    assert editada.status_code == 200
    assert editada.json()["display_name"] == "Minha skill v2"
    assert editada.json()["subpath"] == "onboarding"
    assert editada.json()["repo_owner"] == "owner"  # intacto

    lista = client.get("/api/admin/agent-skills")
    assert [s["display_name"] for s in lista.json()] == ["Minha skill v2"]


def test_nome_duplicado_retorna_409(client, seed_user):
    _login_admin(client, seed_user)
    client.post(
        "/api/admin/agent-skills",
        json={"display_name": "Skill", "repo_owner": "owner", "repo_name": "repo-a"},
    )

    duplicada = client.post(
        "/api/admin/agent-skills",
        json={"display_name": "Skill", "repo_owner": "owner", "repo_name": "repo-b"},
    )

    assert duplicada.status_code == 409


def test_owner_vazio_e_recusado(client, seed_user):
    _login_admin(client, seed_user)
    resp = client.post(
        "/api/admin/agent-skills",
        json={"display_name": "Skill", "repo_owner": "  ", "repo_name": "repo"},
    )
    assert resp.status_code == 400


def test_usuario_comum_nao_gerencia_skills(client, seed_user):
    _login_comum(client, seed_user)

    criar = client.post(
        "/api/admin/agent-skills",
        json={"display_name": "Skill", "repo_owner": "owner", "repo_name": "repo"},
    )
    listar = client.get("/api/admin/agent-skills")
    editar = client.patch("/api/admin/agent-skills/1", json={"display_name": "x"})
    remover = client.delete("/api/admin/agent-skills/1")

    assert criar.status_code == 403
    assert listar.status_code == 403
    assert editar.status_code == 403
    assert remover.status_code == 403


def test_remocao_permitida_mesmo_vinculada_e_desvincula(client, seed_user, app_settings):
    _login_admin(client, seed_user)
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn, provision_kind="build")
    conn.close()

    skill_id = client.post(
        "/api/admin/agent-skills",
        json={"display_name": "Skill", "repo_owner": "owner", "repo_name": "repo"},
    ).json()["id"]
    client.post(f"/api/admin/agent-skills/images/{image_id}/skills/{skill_id}")

    remocao = client.delete(f"/api/admin/agent-skills/{skill_id}")
    assert remocao.status_code == 204

    imagens = client.get("/api/admin/agent-skills/images").json()
    alvo = [img for img in imagens if img["id"] == image_id][0]
    assert alvo["skill_ids"] == []


def test_remocao_de_skill_inexistente_e_404(client, seed_user):
    _login_admin(client, seed_user)
    resp = client.delete("/api/admin/agent-skills/999")
    assert resp.status_code == 404


def test_vinculo_e_desvinculo_via_api(client, seed_user, app_settings):
    _login_admin(client, seed_user)
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn, provision_kind="build")
    conn.close()

    skill_id = client.post(
        "/api/admin/agent-skills",
        json={"display_name": "Skill", "repo_owner": "owner", "repo_name": "repo"},
    ).json()["id"]

    vinculado = client.post(f"/api/admin/agent-skills/images/{image_id}/skills/{skill_id}")
    assert vinculado.status_code == 200
    assert vinculado.json()["skill_ids"] == [skill_id]
    # pull_state já reflete "pulling" na própria resposta, antes do build de
    # fundo rodar — é o que dá feedback visual imediato no admin.
    assert vinculado.json()["pull_state"] == "pulling"

    imagens = client.get("/api/admin/agent-skills/images").json()
    alvo = [img for img in imagens if img["id"] == image_id][0]
    assert alvo["skill_ids"] == [skill_id]

    desvinculado = client.delete(f"/api/admin/agent-skills/images/{image_id}/skills/{skill_id}")
    assert desvinculado.status_code == 200
    assert desvinculado.json()["skill_ids"] == []


def test_vincular_a_imagem_pull_retorna_400(client, seed_user, app_settings):
    _login_admin(client, seed_user)
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn, provision_kind="pull")
    conn.close()

    skill_id = client.post(
        "/api/admin/agent-skills",
        json={"display_name": "Skill", "repo_owner": "owner", "repo_name": "repo"},
    ).json()["id"]

    resp = client.post(f"/api/admin/agent-skills/images/{image_id}/skills/{skill_id}")
    assert resp.status_code == 400


def test_vincular_imagem_inexistente_e_404(client, seed_user):
    _login_admin(client, seed_user)
    skill_id = client.post(
        "/api/admin/agent-skills",
        json={"display_name": "Skill", "repo_owner": "owner", "repo_name": "repo"},
    ).json()["id"]

    resp = client.post(f"/api/admin/agent-skills/images/999/skills/{skill_id}")
    assert resp.status_code == 404


def test_vincular_skill_inexistente_e_404(client, seed_user, app_settings):
    _login_admin(client, seed_user)
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn, provision_kind="build")
    conn.close()

    resp = client.post(f"/api/admin/agent-skills/images/{image_id}/skills/999")
    assert resp.status_code == 404


async def test_vincular_dispara_rebuild_em_background_com_buildargs_corretos(
    client, seed_user, app_settings, fake_runtime
):
    """Cobre o ciclo completo (tarefa 6.2): vincular -> build em andamento
    -> build conclui -> skill aparece no buildargs recebido pelo runtime."""
    _login_admin(client, seed_user)
    alvo = AGENT_IMAGES[0]
    # `client` já sobe a aplicação real, cujo lifespan semeia as 5 imagens
    # de agente no startup (ver seed_agent_images) — a linha já existe.
    conn = connect(app_settings.db_path)
    image_id = conn.execute(
        "SELECT id FROM images WHERE repository = ?", (alvo.repository,)
    ).fetchone()[0]
    conn.close()
    fake_runtime.build_calls.clear()

    fake_runtime.set_delay("build_image", 0.2)
    skill_id = client.post(
        "/api/admin/agent-skills",
        json={"display_name": "Skill", "repo_owner": "owner", "repo_name": "repo"},
    ).json()["id"]

    resp = client.post(f"/api/admin/agent-skills/images/{image_id}/skills/{skill_id}")
    assert resp.status_code == 200

    # a resposta já voltou: o build ainda está em andamento (delay simulado)
    conn = connect(app_settings.db_path)
    em_andamento = conn.execute(
        "SELECT pull_state FROM images WHERE id = ?", (image_id,)
    ).fetchone()["pull_state"]
    conn.close()
    assert em_andamento == "pulling"

    await asyncio.sleep(0.4)  # espera o build de fundo concluir

    conn = connect(app_settings.db_path)
    pronto = conn.execute(
        "SELECT pull_state FROM images WHERE id = ?", (image_id,)
    ).fetchone()["pull_state"]
    conn.close()
    assert pronto == "ready"

    builds_do_alvo = [c for c in fake_runtime.build_calls if c["repository"] == alvo.repository]
    assert len(builds_do_alvo) == 1
    assert builds_do_alvo[0]["buildargs"] == {"SKILLS": "owner/repo"}
