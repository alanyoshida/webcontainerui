#!/usr/bin/env bash
# webcontainerui — instalação guiada (produção).
#
# Verifica os pré-requisitos, coleta a configuração obrigatória (domínio,
# e-mail/senha do primeiro administrador, chave de cifra das identidades
# SSH), grava tudo em deploy/.env e sobe a composição de produção
# (Caddy + portal). Ver deploy/README.md para a ordem de subida manual,
# variáveis opcionais e o procedimento de reversão.
#
# Uso:
#   ./install.sh
#
# As variáveis abaixo, se já exportadas no ambiente, pulam o prompt
# correspondente — útil para instalação não interativa (CI, provisionamento
# automatizado):
#   WCUI_DOMAIN, WCUI_ADMIN_EMAIL, WCUI_ADMIN_PASSWORD,
#   WCUI_SSH_KEY_ENCRYPTION_KEY
#
# Rodar de novo (ex.: depois de um `git pull`) reaproveita o deploy/.env já
# gravado e só reconstrói e reinicia os containers.

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit 0
fi

echo "== webcontainerui — instalação =="
echo

# --- pré-requisitos -----------------------------------------------------

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker não encontrado. Instale antes de continuar:" >&2
  echo "  https://docs.docker.com/engine/install/" >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Plugin 'docker compose' (Docker Compose v2) não encontrado." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Não foi possível falar com o daemon do Docker." >&2
  echo "Ele está rodando? Seu usuário está no grupo 'docker'?" >&2
  exit 1
fi

echo "Docker ok."

# --- configuração ---------------------------------------------------------
# deploy/.env de uma instalação anterior vira o valor padrão de cada
# variável; só prompta o que ainda estiver faltando.

ENV_FILE="deploy/.env"
if [[ -f "$ENV_FILE" ]]; then
  echo "Reaproveitando configuração existente em $ENV_FILE."
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

if [[ -z "${WCUI_DOMAIN:-}" ]]; then
  read -rp "Domínio público do portal (ex.: desktop.seu-dominio.test): " WCUI_DOMAIN
fi
if [[ -z "$WCUI_DOMAIN" ]]; then
  echo "WCUI_DOMAIN é obrigatório." >&2
  exit 1
fi

if [[ -z "${WCUI_ADMIN_EMAIL:-}" ]]; then
  read -rp "E-mail do primeiro administrador: " WCUI_ADMIN_EMAIL
fi
if [[ -z "$WCUI_ADMIN_EMAIL" ]]; then
  echo "WCUI_ADMIN_EMAIL é obrigatório." >&2
  exit 1
fi

if [[ -z "${WCUI_ADMIN_PASSWORD:-}" ]]; then
  while true; do
    read -rsp "Senha do primeiro administrador (mínimo 12 caracteres): " WCUI_ADMIN_PASSWORD
    echo
    if [[ "${#WCUI_ADMIN_PASSWORD}" -ge 12 ]]; then
      break
    fi
    echo "Precisa ter pelo menos 12 caracteres — tente de novo." >&2
  done
elif [[ "${#WCUI_ADMIN_PASSWORD}" -lt 12 ]]; then
  echo "WCUI_ADMIN_PASSWORD precisa ter pelo menos 12 caracteres." >&2
  exit 1
fi

if [[ -z "${WCUI_SSH_KEY_ENCRYPTION_KEY:-}" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    WCUI_SSH_KEY_ENCRYPTION_KEY=$(python3 -c \
      "import secrets, base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())")
  else
    # Equivalente sem depender de python3: 32 bytes aleatórios em base64
    # urlsafe — mesmo formato que Fernet.generate_key() produz.
    WCUI_SSH_KEY_ENCRYPTION_KEY=$(openssl rand -base64 32 | tr '+/' '-_')
  fi
  echo "Chave de cifra das identidades SSH gerada automaticamente."
  echo "Guarde-a com segurança: perdê-la impede descriptografar chaves já cifradas."
fi

# --- grava deploy/.env -----------------------------------------------------

mkdir -p deploy
cat > "$ENV_FILE" <<EOF
WCUI_DOMAIN=$WCUI_DOMAIN
WCUI_ADMIN_EMAIL=$WCUI_ADMIN_EMAIL
WCUI_ADMIN_PASSWORD=$WCUI_ADMIN_PASSWORD
WCUI_SSH_KEY_ENCRYPTION_KEY=$WCUI_SSH_KEY_ENCRYPTION_KEY
EOF
chmod 600 "$ENV_FILE"

# --- confirmação e subida ---------------------------------------------------

echo
echo "Configuração pronta em $ENV_FILE:"
echo "  WCUI_DOMAIN=$WCUI_DOMAIN"
echo "  WCUI_ADMIN_EMAIL=$WCUI_ADMIN_EMAIL"
echo "  WCUI_ADMIN_PASSWORD=(oculta)"
echo "  WCUI_SSH_KEY_ENCRYPTION_KEY=(oculta)"
echo
echo "A seguir: build da imagem e subida de Caddy + portal, expondo as portas"
echo "80/443 deste host e solicitando certificado Let's Encrypt para o domínio"
echo "acima (ele precisa já apontar para este host)."
read -rp "Continuar? [s/N] " confirm
if [[ ! "$confirm" =~ ^[sSyY]$ ]]; then
  echo "Cancelado. A configuração em $ENV_FILE foi mantida para a próxima vez."
  exit 0
fi

(cd deploy && docker compose up -d --build)

echo
echo "Pronto. Assim que o DNS e o certificado propagarem, acesse:"
echo "  https://$WCUI_DOMAIN"
echo
echo "Entre com WCUI_ADMIN_EMAIL/WCUI_ADMIN_PASSWORD, registre as imagens do"
echo "catálogo e conceda acesso a grupos — ver deploy/README.md."
