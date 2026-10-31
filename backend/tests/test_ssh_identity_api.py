from app.db import connect, init_db

from .conftest import add_user_to_group, grant_image_to_group, insert_group, insert_image


def _login_as(client, seed_user, email, password="senha-usuario-123"):
    seed_user(email, password)
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["id"]


def test_consulta_sem_sessao_e_recusada(client):
    resp = client.get("/api/me/ssh-identity")
    assert resp.status_code == 401


def test_regenerar_sem_sessao_e_recusada(client):
    resp = client.post("/api/me/ssh-identity/regenerate")
    assert resp.status_code == 401


def test_primeira_consulta_gera_e_proxima_retorna_a_mesma_chave(client, seed_user):
    _login_as(client, seed_user, "primeira@exemplo.test")

    primeira = client.get("/api/me/ssh-identity")
    segunda = client.get("/api/me/ssh-identity")

    assert primeira.status_code == 200
    assert primeira.json()["public_key"].startswith("ssh-ed25519 ")
    assert segunda.json()["public_key"] == primeira.json()["public_key"]


def test_regenerar_troca_a_chave_publica(client, seed_user):
    _login_as(client, seed_user, "regenera@exemplo.test")
    original = client.get("/api/me/ssh-identity").json()["public_key"]

    resp = client.post("/api/me/ssh-identity/regenerate")

    assert resp.status_code == 200
    assert resp.json()["public_key"] != original
    assert resp.json()["propagation_failures"] == []


def test_regenerar_propaga_para_instancia_existente(client, seed_user, app_settings, fake_runtime):
    user_id = _login_as(client, seed_user, "propaga-api@exemplo.test")
    conn = connect(app_settings.db_path)
    init_db(conn)
    image_id = insert_image(conn)
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()
    client.post("/api/instances", json={"image_id": image_id})

    fake_runtime.put_archive_calls.clear()
    resp = client.post("/api/me/ssh-identity/regenerate")

    assert resp.status_code == 200
    assert len(fake_runtime.put_archive_calls) == 1


def test_identidades_de_usuarios_diferentes_sao_isoladas(client, seed_user):
    _login_as(client, seed_user, "isolado-a@exemplo.test")
    chave_a = client.get("/api/me/ssh-identity").json()["public_key"]

    client.cookies.clear()
    _login_as(client, seed_user, "isolado-b@exemplo.test")
    chave_b = client.get("/api/me/ssh-identity").json()["public_key"]

    assert chave_a != chave_b
    # não há parâmetro de usuário na rota: o único jeito de "ver" a
    # identidade de outro usuário seria a sessão dele mesmo, que o cliente
    # não tem — a consulta acima prova que cada sessão só alcança a sua.
