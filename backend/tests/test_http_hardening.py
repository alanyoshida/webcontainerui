"""Change http-hardening: cabeçalhos de segurança e docs desligada por padrão."""

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

_HEADERS = (
    "x-content-type-options",
    "referrer-policy",
    "x-frame-options",
    "content-security-policy",
)


def test_respostas_do_portal_carregam_cabecalhos_de_seguranca(client):
    for path in ("/", "/api/config", "/health"):
        resp = client.get(path)
        for header in _HEADERS:
            assert resp.headers.get(header), f"{header} ausente em {path}"

    csp = client.get("/").headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'self'" in csp


def test_encaminhamento_de_sessao_nao_recebe_cabecalhos_do_portal(proxy_client, seed_user):
    seed_user("helo@exemplo.test", "senha-correta-123")
    client = proxy_client
    client.post("/api/auth/login", json={"email": "helo@exemplo.test", "password": "senha-correta-123"})

    resp = client.get("/i/qualquer-id/")

    # 404 = instância inexistente respondida pelo próprio proxy: o que importa
    # aqui é que a resposta dele não carrega os cabeçalhos do portal
    assert resp.status_code == 404
    for header in _HEADERS:
        assert not resp.headers.get(header), f"{header} não deveria estar em {header}"


def test_documentacao_interativa_desligada_por_padrao(client):
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404, path


def test_documentacao_interativa_habilitada_por_flag(tmp_path, fake_runtime):
    settings = Settings(
        db_path=tmp_path / "t.db", uploads_dir=tmp_path / "uploads", docs_enabled=True
    )
    app = create_app(settings, runtime=fake_runtime)
    with TestClient(app, base_url="http://testserver") as c:
        assert c.get("/docs").status_code == 200
        assert c.get("/openapi.json").status_code == 200


def test_docs_desligados_nao_caiem_no_catch_all_do_spa(tmp_path, fake_runtime):
    """Com o front-end montado (produção), /docs desligado não pode ser
    servido como index.html com 200 pelo catch-all — responde 404."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>spa</html>", encoding="utf-8")
    settings = Settings(db_path=tmp_path / "t.db", uploads_dir=tmp_path / "uploads", frontend_dist=dist)
    app = create_app(settings, runtime=fake_runtime)
    with TestClient(app, base_url="http://testserver") as c:
        for path in ("/docs", "/redoc", "/openapi.json"):
            assert c.get(path).status_code == 404, path
        # o catch-all continua servindo o SPA para rotas legítimas
        assert c.get("/rota-qualquer").status_code == 200
