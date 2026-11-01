FROM wcui-agent-base:latest

RUN npm install -g opencode-ai

# Skills vinculadas a esta imagem no admin (ver agent_skills.py), uma lista
# separada por espaço de `owner/repo` ou `owner/repo:nome-da-skill` (`:`
# seleciona uma skill específica num repositório com várias — ver
# design.md da change agent-skills-library para a sintaxe real do CLI,
# testada e confirmada). Cada skill é instalada isoladamente: uma falhar
# (repositório inexistente, rede, slug inválido) não derruba o build nem
# impede as demais. `--agent opencode` é o slug confirmado para esta
# ferramenta; `-y -g` evita prompt interativo e instala em $HOME (/config).
ARG SKILLS=""
RUN for s in $SKILLS; do \
      src="${s%%:*}"; skill="${s#*:}"; \
      if [ "$skill" = "$s" ]; then \
        npx --yes skills add "$src" --agent opencode -y -g || true; \
      else \
        npx --yes skills add "$src" --skill "$skill" --agent opencode -y -g || true; \
      fi; \
    done

CMD ["opencode"]
