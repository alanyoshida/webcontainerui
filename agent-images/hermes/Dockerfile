FROM wcui-agent-base:latest

# Hermes Agent (Nous Research) é uma CLI Python; instala num venv isolado
# para não depender do Python do sistema nem esbarrar em PEP 668.
RUN python3 -m venv /opt/hermes \
    && /opt/hermes/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/hermes/bin/pip install --no-cache-dir hermes-agent \
    && ln -s /opt/hermes/bin/hermes /usr/local/bin/hermes

CMD ["hermes"]
