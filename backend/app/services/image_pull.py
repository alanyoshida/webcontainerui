from pathlib import Path

from app.db import connect
from app.runtime.errors import RuntimeOperationError
from app.runtime.protocol import ContainerRuntime
from app.services.images import (
    mark_pull_failed,
    mark_pull_progress,
    mark_pull_ready,
    set_image_version,
    version_from_image_info,
)


async def run_pull(
    db_path: Path, runtime: ContainerRuntime, image_id: int, repository: str, tag: str
) -> None:
    """Executa o download em segundo plano e atualiza o estado da entrada.

    Abre sua própria conexão porque roda fora do ciclo de uma requisição —
    não há `request` nem conexão de quem agendou esta tarefa para herdar.
    """
    conn = connect(db_path)
    try:
        async for progress in runtime.pull_image(repository, tag):
            if progress.detail:
                mark_pull_progress(conn, image_id, progress.detail)
        # Best-effort: o download em si já concluiu — uma falha na
        # inspeção deixa a entrada pronta, só sem versão nova registrada.
        # `Exception` de propósito: um erro inesperado aqui não pode deixar
        # a entrada presa em "pulling" para sempre (o download concluiu).
        try:
            version = version_from_image_info(await runtime.inspect_image(repository, tag))
            if version:
                set_image_version(conn, image_id, version)
        except Exception:
            pass
        mark_pull_ready(conn, image_id)
    except RuntimeOperationError as exc:
        mark_pull_failed(conn, image_id, str(exc))
    finally:
        conn.close()
