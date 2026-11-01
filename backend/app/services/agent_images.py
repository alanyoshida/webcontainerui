"""Imagens de agentes de código em CLI, provisionadas por build local.

O seed roda no startup (D4/D6/D8 em design.md): garante a imagem base e as
5 imagens de agente no catálogo, construindo apenas o que ainda não existe
ou cujo contexto (Dockerfile e arquivos ao redor) mudou desde o último build
bem-sucedido. Falha de uma imagem não impede as demais nem o startup.
"""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings
from app.db import connect
from app.runtime.errors import RuntimeOperationError
from app.runtime.protocol import ContainerRuntime
from app.services.agent_skills import resolve_image_skill_refs
from app.services.errors import ConflictError
from app.services.images import (
    create_image,
    mark_pull_failed,
    mark_pull_progress,
    mark_pull_ready,
    mark_pull_started,
)

BASE_IMAGE_REPOSITORY = "wcui-agent-base"
BASE_IMAGE_TAG = "latest"
BASE_CONTEXT_SUBDIR = "_base"


@dataclass(frozen=True)
class AgentImageSpec:
    display_name: str
    repository: str
    tag: str
    context_subdir: str
    port: int = 3000


AGENT_IMAGES: tuple[AgentImageSpec, ...] = (
    AgentImageSpec(
        display_name="Claude Code",
        repository="wcui-agent-claude-code",
        tag="latest",
        context_subdir="claude-code",
    ),
    AgentImageSpec(
        display_name="Hermes",
        repository="wcui-agent-hermes",
        tag="latest",
        context_subdir="hermes",
    ),
    AgentImageSpec(
        display_name="Agy",
        repository="wcui-agent-agy",
        tag="latest",
        context_subdir="agy",
    ),
    AgentImageSpec(
        display_name="OpenCode",
        repository="wcui-agent-opencode",
        tag="latest",
        context_subdir="opencode",
    ),
    AgentImageSpec(
        display_name="oh-my-pi",
        repository="wcui-agent-oh-my-pi",
        tag="latest",
        context_subdir="oh-my-pi",
    ),
)


def default_agent_images_dir() -> Path:
    """Localiza `agent-images/` tanto no repositório quanto na imagem do portal.

    Em desenvolvimento o pacote está em `backend/app/services`; na imagem do
    portal, em `/app/app/services`. Os dois candidatos cobrem os dois casos.
    """
    module_dir = Path(__file__).resolve().parents[2]
    for candidate in (module_dir / "agent-images", module_dir.parent / "agent-images"):
        if candidate.is_dir():
            return candidate
    return module_dir / "agent-images"


def agent_context_dirs(spec: AgentImageSpec, base_dir: Path | str) -> list[Path]:
    root = Path(base_dir)
    return [root / BASE_CONTEXT_SUBDIR, root / spec.context_subdir]


def context_hash(context_dirs: Sequence[Path]) -> str:
    """Hash estável do conteúdo dos diretórios de contexto.

    Inclui o caminho relativo de cada arquivo, para que renomear conte com
    mudança, e não depende de mtime — só do conteúdo versionado.
    """
    digest = hashlib.sha256()
    for directory in context_dirs:
        directory = Path(directory)
        for path in sorted(p for p in directory.rglob("*") if p.is_file()):
            relative = path.relative_to(directory).as_posix()
            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def build_hash_for(
    spec: AgentImageSpec, base_dir: Path | str, *, skill_refs: Sequence[str] = ()
) -> str:
    """Hash do contexto de arquivos combinado com as skills vinculadas.

    `skill_refs` (vazio por padrão, mantendo o hash só de arquivo para quem
    não passa o argumento) entra no hash para que vincular/desvincular uma
    skill também conte como "contexto alterado", mesmo sem nenhum arquivo
    em disco ter mudado — ver design.md, "Gatilho de rebuild".
    """
    digest = hashlib.sha256(context_hash(agent_context_dirs(spec, base_dir)).encode("utf-8"))
    for ref in sorted(skill_refs):
        digest.update(b"\0")
        digest.update(ref.encode("utf-8"))
    return digest.hexdigest()


def skills_buildargs(skill_refs: Sequence[str]) -> dict[str, str]:
    """`buildargs` passado a `runtime.build_image` com a lista de skills.

    Sempre inclui a chave `SKILLS` (mesmo vazia) para refletir explicitamente
    o estado atual do vínculo — nunca um valor anterior guardado em algum
    lugar (ver design.md, decisão "Gatilho de rebuild").
    """
    return {"SKILLS": " ".join(skill_refs)}


def find_agent_image(repository: str, tag: str) -> AgentImageSpec | None:
    for spec in AGENT_IMAGES:
        if spec.repository == repository and spec.tag == tag:
            return spec
    return None


async def run_build(
    db_path: Path,
    runtime: ContainerRuntime,
    image_id: int,
    repository: str,
    tag: str,
    *,
    context_dir: str,
    build_hash: str | None = None,
    buildargs: dict[str, str] | None = None,
) -> None:
    """Executa o build e atualiza o estado da entrada, como `run_pull` faz.

    O hash só é gravado após sucesso: assim uma falha é tentada de novo no
    próximo startup (em vez de ser tratada como contexto já construído).
    """
    conn = connect(db_path)
    try:
        mark_pull_started(conn, image_id)
        async for progress in runtime.build_image(
            context_dir, repository, tag, buildargs=buildargs
        ):
            if progress.detail:
                mark_pull_progress(conn, image_id, progress.detail)
        if build_hash is not None:
            conn.execute(
                "UPDATE images SET build_hash = ? WHERE id = ?", (build_hash, image_id)
            )
        mark_pull_ready(conn, image_id)
    except RuntimeOperationError as exc:
        mark_pull_failed(conn, image_id, str(exc))
    finally:
        conn.close()


async def _build_base(runtime: ContainerRuntime, base_dir: Path) -> None:
    """Constrói a base antes dos agentes (D6). Falha aqui não propaga."""
    try:
        async for _ in runtime.build_image(
            str(base_dir / BASE_CONTEXT_SUBDIR), BASE_IMAGE_REPOSITORY, BASE_IMAGE_TAG
        ):
            pass
    except Exception:
        # Os agentes vão falhar individualmente ao partir da base ausente,
        # mas o portal deve subir mesmo assim (D5/D6).
        pass


def _find_row(conn: sqlite3.Connection, spec: AgentImageSpec) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT id, pull_state, provision_kind, build_hash FROM images"
        " WHERE repository = ? AND tag = ?",
        (spec.repository, spec.tag),
    ).fetchone()


async def _provision_agent(
    conn: sqlite3.Connection,
    settings: Settings,
    runtime: ContainerRuntime,
    spec: AgentImageSpec,
    base_dir: Path,
) -> None:
    row = _find_row(conn, spec)

    if row is None:
        try:
            image_id = create_image(
                conn,
                spec.display_name,
                spec.repository,
                spec.tag,
                settings=settings,
                port=spec.port,
                provision_kind="build",
            )
        except ConflictError:
            row = _find_row(conn, spec)
            if row is None:
                raise
        else:
            # Imagem recém-criada: ainda não pode ter skill vinculada (o
            # vínculo exige a imagem já existir), mas resolve mesmo assim
            # para seguir a mesma regra "sempre a partir do banco" de baixo.
            skill_refs = resolve_image_skill_refs(conn, image_id)
            await run_build(
                settings.db_path,
                runtime,
                image_id,
                spec.repository,
                spec.tag,
                context_dir=str(base_dir / spec.context_subdir),
                build_hash=build_hash_for(spec, base_dir, skill_refs=skill_refs),
                buildargs=skills_buildargs(skill_refs),
            )
            return

    if row["provision_kind"] != "build":
        return
    skill_refs = resolve_image_skill_refs(conn, row["id"])
    current_hash = build_hash_for(spec, base_dir, skill_refs=skill_refs)
    if row["build_hash"] == current_hash and row["pull_state"] == "ready":
        return
    await run_build(
        settings.db_path,
        runtime,
        row["id"],
        spec.repository,
        spec.tag,
        context_dir=str(base_dir / spec.context_subdir),
        build_hash=current_hash,
        buildargs=skills_buildargs(skill_refs),
    )


async def rebuild_agent_image(
    settings: Settings,
    runtime: ContainerRuntime,
    image_id: int,
    *,
    base_dir: Path | str | None = None,
) -> None:
    """Rebuild sob demanda de uma imagem de agente já registrada.

    Chamado pelas rotas de vínculo/desvínculo de skill (api/agent_skills.py)
    — fora do seed de startup —, sempre resolvendo as skills vinculadas no
    momento da chamada, nunca um valor anterior (ver design.md, "Gatilho de
    rebuild"). Assume que o chamador já validou que a imagem existe e é
    `provision_kind == 'build'` (mesma checagem de `agent_skills.link_skill`).
    """
    root = Path(base_dir) if base_dir is not None else default_agent_images_dir()
    conn = connect(settings.db_path)
    try:
        row = conn.execute(
            "SELECT repository, tag FROM images WHERE id = ?", (image_id,)
        ).fetchone()
        if row is None:
            return
        spec = find_agent_image(row["repository"], row["tag"])
        if spec is None:
            return
        skill_refs = resolve_image_skill_refs(conn, image_id)
    finally:
        conn.close()

    await run_build(
        settings.db_path,
        runtime,
        image_id,
        spec.repository,
        spec.tag,
        context_dir=str(root / spec.context_subdir),
        build_hash=build_hash_for(spec, root, skill_refs=skill_refs),
        buildargs=skills_buildargs(skill_refs),
    )


async def seed_agent_images(
    settings: Settings,
    runtime: ContainerRuntime,
    *,
    base_dir: Path | str | None = None,
) -> None:
    """Garante a base e as 5 imagens de agente no catálogo (idempotente).

    Aguarda cada build (D8), mas isola falhas por imagem (D5): uma entrada
    que falhar é marcada como `failed` e as demais seguem.
    """
    root = Path(base_dir) if base_dir is not None else default_agent_images_dir()

    await _build_base(runtime, root)

    conn = connect(settings.db_path)
    try:
        for spec in AGENT_IMAGES:
            try:
                await _provision_agent(conn, settings, runtime, spec, root)
            except Exception as exc:
                row = _find_row(conn, spec)
                if row is not None:
                    mark_pull_failed(conn, row["id"], str(exc))
    finally:
        conn.close()
