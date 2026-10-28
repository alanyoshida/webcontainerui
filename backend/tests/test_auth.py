from app.db import connect


def test_login_com_credenciais_corretas_emite_sessao(client, seed_user):
    seed_user("ana@exemplo.test", "senha-correta-123")

    resp = client.post("/api/auth/login", json={"email": "ana@exemplo.test", "password": "senha-correta-123"})

    assert resp.status_code == 200
    assert resp.json()["email"] == "ana@exemplo.test"
    assert "wcui_session" in resp.cookies

    # a sessão emitida autentica a requisição seguinte
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "ana@exemplo.test"


def test_email_inexistente_e_senha_incorreta_tem_resposta_identica(client, seed_user):
    seed_user("bea@exemplo.test", "senha-correta-123")

    resp_inexistente = client.post(
        "/api/auth/login", json={"email": "nao-existe@exemplo.test", "password": "qualquer"}
    )
    resp_senha_errada = client.post(
        "/api/auth/login", json={"email": "bea@exemplo.test", "password": "senha-errada"}
    )

    assert resp_inexistente.status_code == resp_senha_errada.status_code == 401
    assert resp_inexistente.json() == resp_senha_errada.json()
    assert "wcui_session" not in resp_inexistente.cookies
    assert "wcui_session" not in resp_senha_errada.cookies


def test_senha_armazenada_apenas_como_hash(app_settings, client, seed_user):
    seed_user("carla@exemplo.test", "senha-correta-123")

    conn = connect(app_settings.db_path)
    row = conn.execute(
        "SELECT password_hash FROM users WHERE email = ?", ("carla@exemplo.test",)
    ).fetchone()
    conn.close()

    assert "senha-correta-123" not in row["password_hash"]
    assert row["password_hash"].startswith("$argon2")


def test_sessao_expirada_e_rejeitada(client, seed_user, app_settings):
    seed_user("duda@exemplo.test", "senha-correta-123")
    client.post("/api/auth/login", json={"email": "duda@exemplo.test", "password": "senha-correta-123"})

    # expira manualmente a sessão criada, simulando o prazo já vencido
    conn = connect(app_settings.db_path)
    conn.execute("UPDATE sessions SET expires_at = '2000-01-01 00:00:00'")
    conn.close()

    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_logout_revoga_a_sessao_imediatamente(client, seed_user):
    seed_user("elis@exemplo.test", "senha-correta-123")
    client.post("/api/auth/login", json={"email": "elis@exemplo.test", "password": "senha-correta-123"})

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 204

    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_login_de_conta_desabilitada_e_recusado(client, seed_user):
    seed_user("fabio@exemplo.test", "senha-correta-123", disabled=True)

    resp = client.post("/api/auth/login", json={"email": "fabio@exemplo.test", "password": "senha-correta-123"})

    assert resp.status_code == 401
    assert "wcui_session" not in resp.cookies


def test_sessao_ativa_e_recusada_apos_desabilitar_a_conta(client, seed_user, app_settings):
    seed_user("gui@exemplo.test", "senha-correta-123")
    client.post("/api/auth/login", json={"email": "gui@exemplo.test", "password": "senha-correta-123"})
    assert client.get("/api/auth/me").status_code == 200

    conn = connect(app_settings.db_path)
    conn.execute("UPDATE users SET disabled_at = '2024-01-01 00:00:00' WHERE email = ?", ("gui@exemplo.test",))
    conn.close()

    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_cookie_e_httponly_e_samesite(client, seed_user):
    seed_user("hugo@exemplo.test", "senha-correta-123")

    resp = client.post("/api/auth/login", json={"email": "hugo@exemplo.test", "password": "senha-correta-123"})

    set_cookie_header = resp.headers.get("set-cookie", "")
    assert "HttpOnly" in set_cookie_header
    assert "samesite=lax" in set_cookie_header.lower()


def test_cookie_e_secure_sobre_https(https_client, seed_user):
    seed_user("ivo@exemplo.test", "senha-correta-123")

    resp = https_client.post("/api/auth/login", json={"email": "ivo@exemplo.test", "password": "senha-correta-123"})

    assert "Secure" in resp.headers.get("set-cookie", "")


def test_cookie_nao_e_secure_sobre_http(client, seed_user):
    seed_user("joana@exemplo.test", "senha-correta-123")

    resp = client.post("/api/auth/login", json={"email": "joana@exemplo.test", "password": "senha-correta-123"})

    assert "Secure" not in resp.headers.get("set-cookie", "")


def test_requisicao_anonima_a_rota_protegida_e_recusada(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
