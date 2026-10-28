def test_config_publico_nao_exige_autenticacao(client, app_settings):
    resp = client.get("/api/config")
    assert resp.status_code == 200
    assert resp.json()["idle_timeout_minutes"] == app_settings.idle_timeout_minutes
