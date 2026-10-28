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
    settings = Settings(db_path=tmp_path / "x.db", frontend_dist=tmp_path / "nao-existe")
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

    settings = Settings(db_path=tmp_path / "x.db", frontend_dist=dist)
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
