FROM wcui-agent-base:latest

# Hermes Agent (Nous Research) é uma CLI Python; instala num venv isolado
# para não depender do Python do sistema nem esbarrar em PEP 668.
RUN python3 -m venv /opt/hermes \
    && /opt/hermes/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/hermes/bin/pip install --no-cache-dir hermes-agent \
    && ln -s /opt/hermes/bin/hermes /usr/local/bin/hermes

# Skills vinculadas a esta imagem no admin (ver agent_skills.py), uma lista
# separada por espaço de `owner/repo` ou `owner/repo:nome-da-skill` (`:`
# seleciona uma skill específica num repositório com várias — ver
# design.md da change agent-skills-library para a sintaxe real do CLI,
# testada e confirmada). Cada skill é instalada isoladamente: uma falhar
# (repositório inexistente, rede, slug inválido) não derruba o build nem
# impede as demais. `--agent hermes-agent` é o slug confirmado para esta
# ferramenta (não é "hermes"); `-y -g` evita prompt interativo e instala em
# $HOME (/config).
ARG SKILLS=""
RUN for s in $SKILLS; do \
      src="${s%%:*}"; skill="${s#*:}"; \
      if [ "$skill" = "$s" ]; then \
        npx --yes skills add "$src" --agent hermes-agent -y -g || true; \
      else \
        npx --yes skills add "$src" --skill "$skill" --agent hermes-agent -y -g || true; \
      fi; \
    done

CMD ["hermes"]
