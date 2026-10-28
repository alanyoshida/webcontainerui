from pathlib import Path

from app.db import connect
from app.runtime.errors import RuntimeOperationError
from app.runtime.protocol import ContainerRuntime
from app.services.images import mark_pull_failed, mark_pull_progress, mark_pull_ready


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
        mark_pull_ready(conn, image_id)
    except RuntimeOperationError as exc:
        mark_pull_failed(conn, image_id, str(exc))
    finally:
        conn.close()
