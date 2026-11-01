"""Garante que o passo de instalação de skills nos 5 Dockerfiles de agente
isola falha por skill (`|| true`), já validado manualmente com build real
(`docker build --build-arg SKILLS="owner-inexistente/repo-fake"` conclui
com sucesso — ver design.md). Este teste é a trava de regressão: se algum
dia alguém remover o `|| true` de um dos ramos do loop, ele falha aqui sem
precisar de Docker."""

import pytest

from app.services.agent_images import AGENT_IMAGES, default_agent_images_dir


@pytest.mark.parametrize("spec", AGENT_IMAGES, ids=lambda spec: spec.context_subdir)
def test_dockerfile_de_agente_isola_falha_por_skill(spec):
    dockerfile = default_agent_images_dir() / spec.context_subdir / "Dockerfile"
    conteudo = dockerfile.read_text(encoding="utf-8")

    assert 'ARG SKILLS=""' in conteudo
    # os dois ramos do if/else (com e sem --skill) terminam em `|| true`
    assert conteudo.count("|| true") == 2
    assert "--agent" in conteudo
    assert "-y -g" in conteudo


def test_cada_dockerfile_de_agente_usa_seu_proprio_slug():
    slugs_esperados = {
        "claude-code": "claude-code",
        "hermes": "hermes-agent",
        "agy": "antigravity",
        "opencode": "opencode",
        "oh-my-pi": "pi",
    }
    root = default_agent_images_dir()
    for spec in AGENT_IMAGES:
        conteudo = (root / spec.context_subdir / "Dockerfile").read_text(encoding="utf-8")
        slug = slugs_esperados[spec.context_subdir]
        assert f"--agent {slug} " in conteudo
