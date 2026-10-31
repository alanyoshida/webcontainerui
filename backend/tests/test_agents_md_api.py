"""Testes de API da biblioteca de documentos AGENTS.md."""

from app.db import connect
from app.services.agents_md import create_document

from .conftest import insert_image


def _login_admin(client, seed_user, email="admin@exemplo.test", password="senha-admin-123"):
    seed_user(email, password, is_admin=True)
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200


def _login_comum(client, seed_user, email="comum@exemplo.test", password="senha-usuario-123"):
    seed_user(email, password)
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200


def test_admin_cria_lista_e_edita_documento(client, seed_user, app_settings):
    _login_admin(client, seed_user)

    criado = client.post(
        "/api/admin/agents-md",
        json={"name": "Padrão da equipe", "content": "# Regras"},
    )
    assert criado.status_code == 201
    document_id = criado.json()["id"]
    assert criado.json()["linked_images"] == 0

    editado = client.patch(
        f"/api/admin/agents-md/{document_id}",
        json={"name": "Padrão da equipe v2", "content": "# Regras novas"},
    )
    assert editado.status_code == 200
    assert editado.json()["document"]["name"] == "Padrão da equipe v2"
    assert editado.json()["propagation_failures"] == []

    lista = client.get("/api/admin/agents-md")
    assert [d["name"] for d in lista.json()] == ["Padrão da equipe v2"]


def test_nome_duplicado_retorna_409(client, seed_user, app_settings):
    _login_admin(client, seed_user)
    client.post("/api/admin/agents-md", json={"name": "Doc", "content": "# x"})

    duplicado = client.post(
        "/api/admin/agents-md", json={"name": "Doc", "content": "# y"}
    )

    assert duplicado.status_code == 409


def test_conteudo_vazio_e_recusado(client, seed_user, app_settings):
    _login_admin(client, seed_user)
    resp = client.post(
        "/api/admin/agents-md",
        json={"name": "Doc", "content": "   "},
    )
    assert resp.status_code == 400


def test_usuario_comum_nao_gerencia_documentos(client, seed_user, app_settings):
    _login_comum(client, seed_user)

    criar = client.post(
        "/api/admin/agents-md", json={"name": "Doc", "content": "# x"}
    )
    listar = client.get("/api/admin/agents-md")
    editar = client.patch("/api/admin/agents-md/1", json={"content": "# y"})
    remover = client.delete("/api/admin/agents-md/1")

    assert criar.status_code == 403
    assert listar.status_code == 403
    assert editar.status_code == 403
    assert remover.status_code == 403


def test_remocao_de_documento_em_uso_retorna_409(client, seed_user, app_settings):
    _login_admin(client, seed_user)
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn)
    conn.close()

    criado = client.post(
        "/api/admin/agents-md", json={"name": "Doc", "content": "# x"}
    )
    document_id = criado.json()["id"]

    vincular = client.put(
        f"/api/admin/agents-md/images/{image_id}", json={"document_id": document_id}
    )
    assert vincular.status_code == 200

    remover = client.delete(f"/api/admin/agents-md/{document_id}")
    assert remover.status_code == 409

    desvincular = client.put(
        f"/api/admin/agents-md/images/{image_id}", json={"document_id": None}
    )
    assert desvincular.status_code == 200

    remover_depois = client.delete(f"/api/admin/agents-md/{document_id}")
    assert remover_depois.status_code == 204


def test_vinculo_e_listagem_por_imagem(client, seed_user, app_settings):
    _login_admin(client, seed_user)
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn)
    conn.close()

    criado = client.post(
        "/api/admin/agents-md", json={"name": "Doc", "content": "# x"}
    )
    document_id = criado.json()["id"]

    vinculado = client.put(
        f"/api/admin/agents-md/images/{image_id}", json={"document_id": document_id}
    )
    assert vinculado.status_code == 200
    assert vinculado.json()["document_id"] == document_id

    imagens = client.get("/api/admin/agents-md/images").json()
    alvo = [img for img in imagens if img["id"] == image_id][0]
    assert alvo["document_id"] == document_id
    assert alvo["display_name"] == "Webtop"
