"""Imagens de desktop (webtop e VS Code) garantidas no catálogo pelo startup.

Espelho simplificado do seed de agentes (`services/agent_images.py`) para
entradas de `pull`: a tupla abaixo é o catálogo de referência de desktops do
produto — um deploy do zero nasce com as quatro baixando em segundo plano.
Entrada já existente no catálogo (por repositório+tag, em qualquer estado) é
apenas ignorada: estado, limites editados, desabilitação e capa manual do
administrador prevalecem (change seed-desktop-images, D1).
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass

from fastapi import FastAPI

from app.config import Settings
from app.db import connect
from app.runtime.protocol import ContainerRuntime
from app.services.background import spawn
from app.services.errors import ConflictError
from app.services.image_pull import run_pull
from app.services.images import create_image

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DesktopImageSpec:
    display_name: str
    repository: str
    tag: str


# Os nomes de exibição contêm as palavras-chave que o seed de capas resolve
# (xfce, kde, mate, vscode) — a capa padrão nasce no mesmo boot do registro
# (D4 do design).
DESKTOP_IMAGES: tuple[DesktopImageSpec, ...] = (
    DesktopImageSpec("Webtop XFCE", "lscr.io/linuxserver/webtop", "latest"),
    DesktopImageSpec("Ubuntu KDE", "lscr.io/linuxserver/webtop", "ubuntu-kde"),
    DesktopImageSpec("Alpine MATE", "lscr.io/linuxserver/webtop", "alpine-mate"),
    DesktopImageSpec("VS Code", "lscr.io/linuxserver/vscode", "latest"),
)


def seed_desktop_images(app: FastAPI, settings: Settings, runtime: ContainerRuntime) -> None:
    """Garante as entradas de desktop no catálogo (idempotente, D1).

    Cada entrada é isolada: falha ao registrar uma não impede as demais nem o
    startup. O download é disparado em segundo plano (`spawn`, D2) — o portal
    sobe sem esperar os pulls, que aparecem com progresso no painel.
    """
    conn = connect(settings.db_path)
    try:
        for spec in DESKTOP_IMAGES:
            try:
                _provision_desktop(app, settings, runtime, conn, spec)
            except Exception:
                logger.exception(
                    "falha ao garantir a entrada de desktop %s:%s", spec.repository, spec.tag
                )
    finally:
        conn.close()


def _provision_desktop(
    app: FastAPI,
    settings: Settings,
    runtime: ContainerRuntime,
    conn: sqlite3.Connection,
    spec: DesktopImageSpec,
) -> None:
    exists = conn.execute(
        "SELECT 1 FROM images WHERE repository = ? AND tag = ?", (spec.repository, spec.tag)
    ).fetchone()
    if exists is not None:
        return

    try:
        image_id = create_image(
            conn,
            spec.display_name,
            spec.repository,
            spec.tag,
            settings=settings,
            provision_kind="pull",
        )
    except ConflictError:
        # corrida improvável (worker único): a entrada já existe — fica como está
        return

    spawn(app, run_pull(settings.db_path, runtime, image_id, spec.repository, spec.tag))
