#!/bin/sh
set -eu

# A porta é a mesma que o portal usa no proxy (images.port -> env PORT).
port="${PORT:-3000}"

if [ -n "${SUBFOLDER:-}" ]; then
    set -- --base-path "${SUBFOLDER%/}" "$@"
fi

if [ -n "${CUSTOM_USER:-}" ] && [ -n "${PASSWORD:-}" ]; then
    set -- --credential "${CUSTOM_USER}:${PASSWORD}" "$@"
fi

# Garante que o HOME exista mesmo se a imagem for executada sem o volume.
mkdir -p "${HOME:-/config}"

# --writable: sem isso o ttyd é somente leitura e o usuário não digita no
# terminal do agente.
exec ttyd --writable -p "$port" "$@"
