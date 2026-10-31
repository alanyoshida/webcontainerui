"""Capas padrão do catálogo, seedadas no startup a partir de assets versionados.

Os PNGs 1200x400 vivem em `agent-images/covers/` (gerados por
`agent-images/covers/generate.py`, que usa os logos oficiais versionados em
`agent-images/covers/logos/`). O seed resolve o logo pelo nome de exibição,
repositório e tag de cada entrada existente no catálogo no momento do startup
e cadastra a capa correspondente — sem depender de rede nem de build. Capas
enviadas pelo administrador (`icon_source = 'admin'`) nunca são sobrescritas;
capas padrão (`icon_source = 'default'`) são atualizadas quando o arquivo
versionado muda.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings
from app.db import connect
from app.services.agent_images import default_agent_images_dir
from app.services.images import list_catalog_for_admin

GENERIC_KEY = "generic"
COVERS_SUBDIR = "covers"

_DESKTOP_KEYWORDS: tuple[str, ...] = (
    "xfce",
    "kde",
    "plasma",
    "mate",
    "gnome",
    "cinnamon",
    "lxde",
    "lxqt",
    "i3",
    "sway",
)


@dataclass(frozen=True)
class LogoSpec:
    key: str
    keywords: tuple[str, ...]


LOGOS: tuple[LogoSpec, ...] = (
    # Ambientes de desktop primeiro: quando o nome traz distro + ambiente
    # ("ubuntu kde", "alpine MATE"), é o ambiente que identifica a capa.
    LogoSpec("xfce", ("xfce",)),
    LogoSpec("kde", ("kde", "plasma")),
    LogoSpec("mate", ("mate",)),
    LogoSpec("gnome", ("gnome",)),
    LogoSpec("cinnamon", ("cinnamon",)),
    LogoSpec("lxde", ("lxde",)),
    LogoSpec("lxqt", ("lxqt",)),
    LogoSpec("i3", ("i3",)),
    LogoSpec("sway", ("sway",)),
    # Agentes de código (provisionados pelo seed de agent_images).
    LogoSpec("claude", ("claude",)),
    LogoSpec("hermes", ("hermes",)),
    LogoSpec("agy", ("agy", "antigravity")),
    LogoSpec("opencode", ("opencode",)),
    LogoSpec("oh-my-pi", ("oh-my-pi", "oh my pi", "omp")),
)


def default_covers_dir() -> Path:
    return default_agent_images_dir() / COVERS_SUBDIR


def _normalize(value: str) -> str:
    lowered = value.lower()
    tokens = re.findall(r"[a-z0-9]+", lowered)
    return " ".join(tokens)


def resolve_logo_key(*fields: str | None) -> str:
    """Resolve a chave do logo a partir do nome, repositório e tag da entrada.

    Ambientes de desktop têm precedência sobre agentes e sobre distros: o
    nome vem primeiro na busca, depois repositório e tag. Sem correspondência,
    cai na capa genérica.
    """
    texts = [f for f in fields if f]
    normalized = [_normalize(text) for text in texts]
    for spec in LOGOS:
        for keyword in spec.keywords:
            token = _normalize(keyword)
            for text in normalized:
                if re.search(rf"\b{re.escape(token)}\b", text):
                    return spec.key
    return GENERIC_KEY


def _cover_path(base_dir: Path, key: str) -> Path:
    return base_dir / f"{key}.png"


def _default_filename(image_id: int, content: bytes) -> str:
    digest = hashlib.sha256(content).hexdigest()
    return f"{image_id}-default-{digest}.png"


def seed_image_covers(settings: Settings, *, base_dir: Path | str | None = None) -> None:
    """Garante capa padrão em toda entrada existente no catálogo (idempotente).

    Percorre inclusive entradas desabilitadas e em falha — a capa não depende
    do resultado do provisionamento. Falha em uma entrada (asset ausente,
    disco, etc.) é isolada e não impede as demais nem o startup.
    """
    root = Path(base_dir) if base_dir is not None else default_covers_dir()
    conn = connect(settings.db_path)
    try:
        for row in list_catalog_for_admin(conn):
            try:
                _ensure_cover(conn, row, root, settings)
            except Exception:
                # Isolamento por entrada (mesmo princípio do seed_agent_images):
                # uma capa que falha não pode derrubar o startup.
                pass
    finally:
        conn.close()


def _ensure_cover(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    root: Path,
    settings: Settings,
) -> None:
    if row["icon_path"] and row["icon_source"] == "admin":
        return

    key = resolve_logo_key(row["display_name"], row["repository"], row["tag"])
    cover_path = _cover_path(root, key)
    content = cover_path.read_bytes()

    filename = _default_filename(row["id"], content)
    if row["icon_path"] == filename and (settings.uploads_dir / filename).exists():
        return

    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    (settings.uploads_dir / filename).write_bytes(content)

    if row["icon_path"]:
        _delete_icon_file(settings, row["icon_path"])

    conn.execute(
        "UPDATE images SET icon_path = ?, icon_source = 'default' WHERE id = ?",
        (filename, row["id"]),
    )


def _delete_icon_file(settings: Settings, icon_path: str) -> None:
    file_path = settings.uploads_dir / icon_path
    try:
        file_path.unlink()
    except FileNotFoundError:
        pass