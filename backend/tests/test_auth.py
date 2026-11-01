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


def test_excesso_de_falhas_por_conta_responde_429(client, seed_user):
    seed_user("kiko@exemplo.test", "senha-correta-123")

    for _ in range(10):
        resp = client.post("/api/auth/login", json={"email": "kiko@exemplo.test", "password": "senha-errada"})
        assert resp.status_code == 401

    # a 11ª tentativa é recusada mesmo com a senha correta: verificar a senha
    # aqui viraria oráculo de senha correta sob recusa
    resp = client.post("/api/auth/login", json={"email": "kiko@exemplo.test", "password": "senha-correta-123"})

    assert resp.status_code == 429
    assert int(resp.headers["Retry-After"]) >= 1
    assert "wcui_session" not in resp.cookies


def test_429_nao_revela_existencia_da_conta(client, seed_user):
    seed_user("lia@exemplo.test", "senha-correta-123")

    for _ in range(10):
        client.post("/api/auth/login", json={"email": "lia@exemplo.test", "password": "senha-errada"})
        client.post("/api/auth/login", json={"email": "nao-existe@exemplo.test", "password": "senha-errada"})

    resp_existente = client.post("/api/auth/login", json={"email": "lia@exemplo.test", "password": "x"})
    resp_inexistente = client.post("/api/auth/login", json={"email": "nao-existe@exemplo.test", "password": "x"})

    assert resp_existente.status_code == resp_inexistente.status_code == 429
    assert resp_existente.json() == resp_inexistente.json()


def test_login_correto_dentro_do_limite_funciona(client, seed_user):
    seed_user("mario@exemplo.test", "senha-correta-123")

    for _ in range(9):
        client.post("/api/auth/login", json={"email": "mario@exemplo.test", "password": "senha-errada"})

    resp = client.post("/api/auth/login", json={"email": "mario@exemplo.test", "password": "senha-correta-123"})

    assert resp.status_code == 200


def test_recusa_expirada_permite_login_correto(client, seed_user, monkeypatch):
    seed_user("nina@exemplo.test", "senha-correta-123")
    throttle = client.app.state.login_throttle
    base = throttle.now()
    offset = {"valor": 0.0}
    monkeypatch.setattr(throttle, "now", lambda: base + offset["valor"])

    for _ in range(10):
        client.post("/api/auth/login", json={"email": "nina@exemplo.test", "password": "senha-errada"})
    recusado = client.post("/api/auth/login", json={"email": "nina@exemplo.test", "password": "senha-correta-123"})
    assert recusado.status_code == 429

    offset["valor"] = 301.0
    resp = client.post("/api/auth/login", json={"email": "nina@exemplo.test", "password": "senha-correta-123"})

    assert resp.status_code == 200


def test_variacao_de_caixa_do_email_conta_no_mesmo_limite(client, seed_user):
    seed_user("olga@exemplo.test", "senha-correta-123")

    # o contador da conta usa e-mail normalizado: alternar caixa não bifurca
    variacoes = ["olga@exemplo.test", "OLGA@exemplo.test", "Olga@Exemplo.Test"]
    for i in range(10):
        client.post("/api/auth/login", json={"email": variacoes[i % 3], "password": "senha-errada"})

    resp = client.post("/api/auth/login", json={"email": "olga@exemplo.test", "password": "senha-correta-123"})

    assert resp.status_code == 429


def test_conta_desabilitada_passa_pelo_hash(client, seed_user, monkeypatch):
    """A checagem de desabilitação vem depois do Argon2: o tempo de resposta
    de uma conta desabilitada não a distingue das demais falhas."""
    seed_user("pia@exemplo.test", "senha-correta-123", disabled=True)

    from app.api import auth as auth_module

    chamadas = []
    original = auth_module.verify_password

    def spy(senha, hash_):
        chamadas.append(hash_)
        return original(senha, hash_)

    monkeypatch.setattr(auth_module, "verify_password", spy)

    resp = client.post("/api/auth/login", json={"email": "pia@exemplo.test", "password": "senha-correta-123"})

    assert resp.status_code == 401
    assert "wcui_session" not in resp.cookies
    # o hash da conta rodou (não o dummy): a verificação precede a checagem
    assert len(chamadas) == 1 and chamadas[0].startswith("$argon2")


def test_conta_desabilitada_registra_falha_no_limitador(client, seed_user):
    seed_user("quim@exemplo.test", "senha-correta-123", disabled=True)

    for _ in range(10):
        client.post("/api/auth/login", json={"email": "quim@exemplo.test", "password": "senha-correta-123"})

    resp = client.post("/api/auth/login", json={"email": "quim@exemplo.test", "password": "senha-correta-123"})

    assert resp.status_code == 429


def _insert_session(conn, token_hash, *, user_id=1, expires_at, revoked_at=None):
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at, revoked_at) VALUES (?, ?, ?, ?)",
        (token_hash, user_id, expires_at, revoked_at),
    )


def test_purga_remove_expirada_alem_da_carencia(db_conn):
    from app.services.sessions import purge_sessions

    db_conn.execute("INSERT INTO users (email, password_hash) VALUES ('a@x.test', 'hash')")
    _insert_session(db_conn, "h-expirada", expires_at="2020-01-01 00:00:00")

    removidas = purge_sessions(db_conn, grace_hours=24)

    assert removidas == 1
    assert db_conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0


def test_purga_preserva_revogada_recente(db_conn):
    from datetime import datetime, timedelta, timezone

    from app.services.sessions import purge_sessions

    db_conn.execute("INSERT INTO users (email, password_hash) VALUES ('a@x.test', 'hash')")
    revogada_ha_1h = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    _insert_session(
        db_conn, "h-revogada",
        expires_at="2099-01-01 00:00:00", revoked_at=revogada_ha_1h,
    )

    removidas = purge_sessions(db_conn, grace_hours=24)

    assert removidas == 0
    assert db_conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1


def test_purga_nunca_remove_ativa(db_conn):
    from app.services.sessions import purge_sessions

    db_conn.execute("INSERT INTO users (email, password_hash) VALUES ('a@x.test', 'hash')")
    _insert_session(db_conn, "h-ativa", expires_at="2099-01-01 00:00:00")

    removidas = purge_sessions(db_conn, grace_hours=24)

    assert removidas == 0
    row = db_conn.execute(
        "SELECT token_hash FROM sessions"
    ).fetchone()
    assert row["token_hash"] == "h-ativa"
