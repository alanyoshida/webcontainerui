from app.db import connect


def _login(client, seed_user, email="admin@exemplo.test", password="senha-admin-123", is_admin=True):
    seed_user(email, password, is_admin=is_admin)
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp


def test_usuario_comum_nao_cria_conta(client, seed_user):
    _login(client, seed_user, "comum@exemplo.test", "senha-comum-123", is_admin=False)

    resp = client.post(
        "/api/admin/users", json={"email": "novo@exemplo.test", "password": "senha-nova-123"}
    )

    assert resp.status_code == 403


def test_administrador_cria_conta_e_ela_consegue_autenticar(client, seed_user):
    _login(client, seed_user)

    criado = client.post(
        "/api/admin/users", json={"email": "novo@exemplo.test", "password": "senha-nova-123"}
    )
    assert criado.status_code == 201

    login_novo = client.post(
        "/api/auth/login", json={"email": "novo@exemplo.test", "password": "senha-nova-123"}
    )
    assert login_novo.status_code == 200


def test_email_ja_em_uso_e_recusado(client, seed_user):
    _login(client, seed_user)
    seed_user("existente@exemplo.test", "qualquer-coisa-123")

    resp = client.post(
        "/api/admin/users", json={"email": "existente@exemplo.test", "password": "senha-nova-123"}
    )

    assert resp.status_code == 409


def test_senha_inicial_curta_e_recusada(client, seed_user, app_settings):
    _login(client, seed_user)

    resp = client.post("/api/admin/users", json={"email": "x@exemplo.test", "password": "curta"})

    assert resp.status_code == 400
    total = connect(app_settings.db_path).execute(
        "SELECT COUNT(*) FROM users WHERE email = 'x@exemplo.test'"
    ).fetchone()[0]
    assert total == 0


def test_nao_existe_rota_de_auto_cadastro(client):
    paths = set(client.app.openapi()["paths"].keys())
    assert "/api/auth/register" not in paths
    assert "/api/register" not in paths

    resp = client.post("/api/admin/users", json={"email": "a@exemplo.test", "password": "senha-123456"})
    assert resp.status_code == 401  # sem sessão, não 201 — nada público cria conta


def test_desabilitar_conta_revoga_sessao_existente(client, seed_user):
    from fastapi.testclient import TestClient

    _login(client, seed_user)
    seed_user("logada@exemplo.test", "senha-logada-123")

    # sessão própria do usuário comum, num cliente separado para não
    # perder o cookie quando o admin logar de novo no `client`
    with TestClient(client.app, base_url="http://testserver") as client_usuario:
        login_usuario = client_usuario.post(
            "/api/auth/login", json={"email": "logada@exemplo.test", "password": "senha-logada-123"}
        )
        assert login_usuario.status_code == 200
        user_id = client_usuario.get("/api/auth/me").json()["id"]
        assert client_usuario.get("/api/auth/me").status_code == 200

        resp = client.post(f"/api/admin/users/{user_id}/disable")
        assert resp.status_code == 204

        apos_desabilitar = client_usuario.get("/api/auth/me")
        assert apos_desabilitar.status_code == 401

    # a conta não foi apagada: o registro continua existindo, apenas desabilitado
    conn = connect(client.app.state.settings.db_path)
    row = conn.execute("SELECT disabled_at FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    assert row is not None
    assert row["disabled_at"] is not None


def test_conflito_de_nome_de_grupo(client, seed_user):
    _login(client, seed_user)
    client.post("/api/admin/groups", json={"name": "devs"})

    resp = client.post("/api/admin/groups", json={"name": "devs"})

    assert resp.status_code == 409


def test_remocao_de_grupo_preserva_contas_dos_membros(client, seed_user, app_settings):
    _login(client, seed_user)
    membro_id = client.post(
        "/api/admin/users", json={"email": "membro@exemplo.test", "password": "senha-membro-123"}
    ).json()["id"]
    group_id = client.post("/api/admin/groups", json={"name": "equipe"}).json()["id"]
    client.post(f"/api/admin/groups/{group_id}/members", json={"user_id": membro_id})

    resp = client.delete(f"/api/admin/groups/{group_id}")
    assert resp.status_code == 204

    conn = connect(app_settings.db_path)
    ainda_existe = conn.execute(
        "SELECT disabled_at FROM users WHERE id = ?", (membro_id,)
    ).fetchone()
    conn.close()
    assert ainda_existe is not None
    assert ainda_existe["disabled_at"] is None


def test_usuario_pode_pertencer_a_multiplos_grupos_e_remover_um_preserva_o_outro(
    client, seed_user, app_settings
):
    from app.services.groups import groups_for_user

    _login(client, seed_user)
    membro_id = client.post(
        "/api/admin/users", json={"email": "multi@exemplo.test", "password": "senha-multi-123"}
    ).json()["id"]
    grupo_a = client.post("/api/admin/groups", json={"name": "grupo-a"}).json()["id"]
    grupo_b = client.post("/api/admin/groups", json={"name": "grupo-b"}).json()["id"]
    client.post(f"/api/admin/groups/{grupo_a}/members", json={"user_id": membro_id})
    client.post(f"/api/admin/groups/{grupo_b}/members", json={"user_id": membro_id})

    client.delete(f"/api/admin/groups/{grupo_a}/members/{membro_id}")

    conn = connect(app_settings.db_path)
    try:
        assert groups_for_user(conn, membro_id) == [grupo_b]
    finally:
        conn.close()


def test_bootstrap_primeiro_administrador(tmp_path):
    from app.config import Settings
    from app.main import create_app
    from fastapi.testclient import TestClient

    settings = Settings(
        db_path=tmp_path / "bootstrap.db",
        uploads_dir=tmp_path / "uploads",
        admin_email="root@exemplo.test",
        admin_password="senha-root-bem-longa",
    )

    with TestClient(create_app(settings)) as client:
        login = client.post(
            "/api/auth/login", json={"email": "root@exemplo.test", "password": "senha-root-bem-longa"}
        )
        assert login.status_code == 200
        assert login.json()["is_admin"] is True


def test_segunda_inicializacao_nao_cria_nem_sobrescreve(tmp_path):
    from app.config import Settings
    from app.main import create_app
    from fastapi.testclient import TestClient

    settings = Settings(
        db_path=tmp_path / "bootstrap.db",
        uploads_dir=tmp_path / "uploads",
        admin_email="root@exemplo.test",
        admin_password="senha-root-bem-longa",
    )

    with TestClient(create_app(settings)):
        pass  # primeira inicialização cria o admin

    # segunda inicialização, mesmo banco, mesmas credenciais configuradas
    with TestClient(create_app(settings)):
        pass

    conn = connect(settings.db_path)
    total = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    assert total == 1
