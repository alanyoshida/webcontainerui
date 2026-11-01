# Build em duas etapas: o front-end primeiro, para que o FastAPI sirva seu
# resultado estático em produção (ver app/main.py — ausência deste diretório
# é o que faz o processo cair para "sem front-end", usado em desenvolvimento).

FROM node:20-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS portal
WORKDIR /app

COPY backend/pyproject.toml ./
COPY backend/app ./app
# pip e setuptools da base carregam CVEs conhecidos na instalação de
# wheels/sdists; o upgrade os elimina antes de qualquer install (scan
# trivy 2026-11-01).
RUN pip install --no-cache-dir --upgrade pip setuptools && pip install --no-cache-dir .

# Contextos de build das imagens de agente: o seed roda dentro deste
# container e envia o contexto para o daemon do host via docker.sock.
COPY agent-images ./agent-images

COPY --from=frontend-builder /frontend/dist ./frontend/dist

# /data é onde o volume nomeado do SQLite é montado (ver deploy/compose.yml).
RUN mkdir -p /data
VOLUME /data

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
