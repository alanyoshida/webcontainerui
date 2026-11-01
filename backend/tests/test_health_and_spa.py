from app.config import Settings
from app.main import create_app
from app.runtime.errors import RuntimeOperationError
from fastapi.testclient import TestClient


def test_health_ok_quando_banco_e_runtime_respondem(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"status": "ok", "database": "ok", "runtime": "ok"}


def test_health_reporta_falha_do_runtime(app_settings, fake_runtime):
    fake_runtime.fail_next("inspect_container", RuntimeOperationError("docker indisponível"))
    app = create_app(app_settings, runtime=fake_runtime)
    with TestClient(app) as client:
        resp = client.get("/health")

    assert resp.status_code == 503
    assert resp.json()["runtime"] == "error"
    assert resp.json()["database"] == "ok"


def test_frontend_ausente_nao_quebra_a_inicializacao(tmp_path, fake_runtime):
    settings = Settings(
        db_path=tmp_path / "x.db",
        uploads_dir=tmp_path / "uploads",
        frontend_dist=tmp_path / "nao-existe",
    )
    app = create_app(settings, runtime=fake_runtime)
    with TestClient(app) as client:
        # sem build do front-end, a rota raiz não é interceptada por um
        # fallback de SPA — a API continua respondendo normalmente.
        resp = client.get("/api/config")
        assert resp.status_code == 200


def test_frontend_presente_e_servido_na_raiz_com_fallback_de_spa(tmp_path, fake_runtime):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html><body>app</body></html>", encoding="utf-8")
    (dist / "assets" / "index.js").write_text("console.log('x')", encoding="utf-8")

    settings = Settings(db_path=tmp_path / "x.db", uploads_dir=tmp_path / "uploads", frontend_dist=dist)
    app = create_app(settings, runtime=fake_runtime)
    with TestClient(app) as client:
        raiz = client.get("/")
        rota_cliente = client.get("/admin")  # rota só existe no React Router
        asset = client.get("/assets/index.js")

    assert raiz.status_code == 200
    assert "app" in raiz.text
    assert rota_cliente.status_code == 200
    assert "app" in rota_cliente.text  # devolve o index.html, React Router assume
    assert asset.status_code == 200
    assert "console.log" in asset.text


def test_arquivo_de_capa_enviado_e_servido_em_uploads(client, seed_user):
    seed_user("admin@exemplo.test", "senha-admin-123", is_admin=True)
    client.post("/api/auth/login", json={"email": "admin@exemplo.test", "password": "senha-admin-123"})
    criada = client.post(
        "/api/admin/images",
        json={"display_name": "Webtop", "repository": "lscr.io/linuxserver/webtop", "tag": "custom-dev"},
    ).json()
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
        b"\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00"
        b"\x00IEND\xaeB`\x82"
    )
    upload = client.post(
        f"/api/admin/images/{criada['id']}/icon",
        files={"file": ("capa.png", png, "image/png")},
    )
    icon_url = upload.json()["icon_url"]

    served = client.get(icon_url)

    assert served.status_code == 200
    assert served.headers["content-type"] == "image/png"
    assert served.content == png
