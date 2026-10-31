import secrets
import sqlite3
import uuid

from app.config import Settings
from app.runtime.errors import ContainerNotFoundError, RuntimeOperationError
from app.runtime.protocol import ContainerRuntime, ContainerSpec
from app.services.access_control import is_permitted
from app.services.errors import NotFoundError, PermissionDeniedError, ValidationFailedError
from app.services.images import get_image

_VOLUME_MOUNT_PATH = "/config"

# Junção com `images` para expor nome/repositório/tag junto da instância,
# evitando que quem lista instâncias precise de uma segunda consulta por
# imagem. `img.*` não é usado de propósito: só os três campos relevantes
# são expostos, sem colidir com as colunas de `instances`.
_INSTANCE_SELECT = """
    SELECT i.*, img.display_name AS image_display_name,
           img.repository AS image_repository, img.tag AS image_tag
    FROM instances i JOIN images img ON img.id = i.image_id
"""


def _find_live(conn: sqlite3.Connection, user_id: int, image_id: int) -> sqlite3.Row | None:
    return conn.execute(
        _INSTANCE_SELECT + " WHERE i.user_id = ? AND i.image_id = ? AND i.deleted_at IS NULL",
        (user_id, image_id),
    ).fetchone()


def _get_by_id(conn: sqlite3.Connection, instance_id: str) -> sqlite3.Row:
    return conn.execute(_INSTANCE_SELECT + " WHERE i.id = ?", (instance_id,)).fetchone()


def get_owned_instance(conn: sqlite3.Connection, instance_id: str, user_id: int) -> sqlite3.Row:
    """Busca a instância garantindo que pertence ao usuário.

    Instância inexistente e instância de outro usuário levantam o mesmo
    erro — a chamada não deve revelar qual dos dois casos ocorreu.
    """
    row = conn.execute(
        _INSTANCE_SELECT + " WHERE i.id = ? AND i.deleted_at IS NULL", (instance_id,)
    ).fetchone()
    if row is None or row["user_id"] != user_id:
        raise NotFoundError(f"instância não encontrada: {instance_id}")
    return row


def list_instances_for_user(conn: sqlite3.Connection, user_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        _INSTANCE_SELECT + " WHERE i.user_id = ? AND i.deleted_at IS NULL ORDER BY i.created_at",
        (user_id,),
    ).fetchall()


def _open_run(conn: sqlite3.Connection, instance_id: str, user_id: int, image_id: int) -> None:
    """Abre um registro de execução para métricas de uso (D1/design.md).

    O `WHERE NOT EXISTS` torna a chamada idempotente: chamar de novo para
    uma instância que já tem run aberto não duplica a linha. Necessário
    porque os pontos que religam uma instância (`_resume_existing`) podem,
    em tese, ser alcançados mais de uma vez sem que o run anterior tenha
    sido fechado.
    """
    conn.execute(
        """INSERT INTO instance_runs (instance_id, user_id, image_id)
           SELECT ?, ?, ? WHERE NOT EXISTS (
               SELECT 1 FROM instance_runs WHERE instance_id = ? AND ended_at IS NULL
           )""",
        (instance_id, user_id, image_id, instance_id),
    )


def _close_run(conn: sqlite3.Connection, instance_id: str, reason: str) -> None:
    """Fecha o registro de execução aberto da instância, se houver.

    `WHERE ended_at IS NULL` torna a chamada idempotente: fechar de novo
    uma instância sem run aberto (ex.: `stop_instance` chamado numa
    instância já parada) não altera nenhuma linha.
    """
    conn.execute(
        """UPDATE instance_runs SET ended_at = datetime('now'), ended_reason = ?
           WHERE instance_id = ? AND ended_at IS NULL""",
        (reason, instance_id),
    )


def _build_spec(
    settings: Settings,
    image: sqlite3.Row,
    instance_id: str,
    container_name: str,
    volume_name: str,
    inner_user: str,
    inner_password: str,
) -> ContainerSpec:
    return ContainerSpec(
        name=container_name,
        repository=image["repository"],
        tag=image["tag"],
        network=settings.docker_network,
        volume_name=volume_name,
        volume_mount_path=_VOLUME_MOUNT_PATH,
        env={
            "SUBFOLDER": f"/i/{instance_id}/",
            "CUSTOM_USER": inner_user,
            "PASSWORD": inner_password,
            # Obrigatório (D6): os links nativos de compartilhamento do
            # Selkies concedem controle total da sessão, incluindo o
            # terminal com sudo sem senha, sem autenticação própria.
            "SELKIES_ENABLE_SHARING": "false",
            "SELKIES_ENABLE_SHARED": "false",
            "PUID": str(settings.puid),
            "PGID": str(settings.pgid),
            "TZ": settings.timezone,
        },
        mem_limit_mb=image["mem_limit_mb"],
        cpu_limit=image["cpu_limit"],
        shm_size_mb=image["shm_size_mb"],
    )


async def _provision_and_start(
    conn: sqlite3.Connection,
    runtime: ContainerRuntime,
    settings: Settings,
    image: sqlite3.Row,
    row: sqlite3.Row,
    container_name: str,
) -> sqlite3.Row:
    """Cria o container do zero e inicia, reaproveitando o volume e as
    credenciais já associadas a `row` (tanto numa instância nova quanto
    numa recriação após o container ter desaparecido do runtime)."""
    spec = _build_spec(
        settings, image, row["id"], container_name, row["volume_name"], row["inner_user"], row["inner_password"]
    )

    try:
        await runtime.ensure_volume(row["volume_name"])
        container_id = await runtime.create_container(spec)
    except RuntimeOperationError as exc:
        conn.execute(
            "UPDATE instances SET state = 'error', error_message = ? WHERE id = ?", (str(exc), row["id"])
        )
        return _get_by_id(conn, row["id"])

    try:
        await runtime.start_container(container_id)
    except RuntimeOperationError as exc:
        # criado mas não iniciado: remove para não deixar container órfão.
        try:
            await runtime.remove_container(container_id)
        except (ContainerNotFoundError, RuntimeOperationError):
            pass
        conn.execute(
            "UPDATE instances SET state = 'error', error_message = ? WHERE id = ?", (str(exc), row["id"])
        )
        return _get_by_id(conn, row["id"])

    conn.execute(
        "UPDATE instances SET state = 'running', error_message = NULL, container_id = ?, container_name = ? WHERE id = ?",
        (container_id, container_name, row["id"]),
    )
    _open_run(conn, row["id"], row["user_id"], row["image_id"])
    return _get_by_id(conn, row["id"])


async def _resume_existing(
    conn: sqlite3.Connection, runtime: ContainerRuntime, settings: Settings, image: sqlite3.Row, row: sqlite3.Row
) -> sqlite3.Row:
    """Religa uma instância parada ou em erro.

    `stop_instance` nunca remove o container, só o para — então religar é
    só `start_container` de novo. Isso só não vale quando o container já
    não existe no runtime (removido por fora, ou a criação anterior
    falhou antes de chegar a existir), caso em que se recria do zero
    reaproveitando volume e credenciais.
    """
    if row["container_id"] is not None:
        try:
            await runtime.start_container(row["container_id"])
        except ContainerNotFoundError:
            pass  # container não existe mais: recria abaixo
        except RuntimeOperationError as exc:
            conn.execute(
                "UPDATE instances SET state = 'error', error_message = ? WHERE id = ?", (str(exc), row["id"])
            )
            return _get_by_id(conn, row["id"])
        else:
            conn.execute(
                "UPDATE instances SET state = 'running', error_message = NULL WHERE id = ?", (row["id"],)
            )
            _open_run(conn, row["id"], row["user_id"], row["image_id"])
            return _get_by_id(conn, row["id"])

    container_name = f"{settings.container_prefix}-{row['id']}"
    return await _provision_and_start(conn, runtime, settings, image, row, container_name)


async def create_instance(
    conn: sqlite3.Connection, runtime: ContainerRuntime, settings: Settings, user_id: int, image_id: int
) -> sqlite3.Row:
    image = get_image(conn, image_id)  # levanta NotFoundError se não existir
    if not image["enabled"] or image["pull_state"] != "ready":
        raise ValidationFailedError("imagem não está pronta para uso")
    if not is_permitted(conn, user_id, image_id):
        raise PermissionDeniedError("usuário não tem permissão sobre esta imagem")

    existing = _find_live(conn, user_id, image_id)
    if existing is not None:
        if existing["state"] in ("running", "starting"):
            return existing
        # parada ou em erro: "iniciar" aqui precisa religar de verdade,
        # não só devolver a linha como estava.
        return await _resume_existing(conn, runtime, settings, image, existing)

    instance_id = str(uuid.uuid4())
    volume_name = f"{settings.volume_prefix}-u{user_id}-i{image_id}"
    container_name = f"{settings.container_prefix}-{instance_id}"
    inner_user = secrets.token_urlsafe(8)
    inner_password = secrets.token_urlsafe(16)

    try:
        conn.execute(
            """INSERT INTO instances
                   (id, user_id, image_id, volume_name, inner_user, inner_password, state)
               VALUES (?, ?, ?, ?, ?, ?, 'starting')""",
            (instance_id, user_id, image_id, volume_name, inner_user, inner_password),
        )
    except sqlite3.IntegrityError:
        # outra criação concorrente para o mesmo par (usuário, imagem) venceu
        # a corrida; a unicidade é garantida pelo índice parcial (D5/2.2).
        return _find_live(conn, user_id, image_id)

    row = _get_by_id(conn, instance_id)
    return await _provision_and_start(conn, runtime, settings, image, row, container_name)


async def stop_instance(
    conn: sqlite3.Connection,
    runtime: ContainerRuntime,
    instance_id: str,
    user_id: int,
    reason: str = "user_stop",
) -> None:
    """Para o container preservando o volume. Idempotente: parar uma
    instância já parada, ou cujo container já não existe no runtime, não é
    erro.

    `reason` identifica, para as métricas de uso, por que a execução
    terminou — "user_stop" por padrão (parada pela rota HTTP do usuário);
    `reap_idle_instances` chama com "idle_timeout".
    """
    row = get_owned_instance(conn, instance_id, user_id)
    if row["container_id"] is not None:
        try:
            await runtime.stop_container(row["container_id"])
        except ContainerNotFoundError:
            pass
    _close_run(conn, instance_id, reason)
    conn.execute("UPDATE instances SET state = 'stopped' WHERE id = ?", (instance_id,))


async def delete_instance(
    conn: sqlite3.Connection,
    runtime: ContainerRuntime,
    instance_id: str,
    user_id: int,
    *,
    confirmed: bool,
) -> None:
    if not confirmed:
        raise ValidationFailedError("exclusão requer confirmação explícita")

    row = get_owned_instance(conn, instance_id, user_id)
    if row["container_id"] is not None:
        try:
            await runtime.remove_container(row["container_id"])
        except ContainerNotFoundError:
            pass
    await runtime.remove_volume(row["volume_name"])
    _close_run(conn, instance_id, "deleted")
    conn.execute("UPDATE instances SET deleted_at = datetime('now') WHERE id = ?", (instance_id,))


def backfill_open_runs(conn: sqlite3.Connection) -> None:
    """Abre um run para toda instância já 'running' sem run aberto (D3/design.md).

    Cobre instâncias que já estavam em execução antes desta funcionalidade
    existir — sem isso, elas nunca apareceriam na visão "rodando agora" até
    a próxima parada/início. `started_at` usa a melhor aproximação
    disponível (`last_seen_at`, ou `created_at` na ausência dele), já que o
    instante real de início não foi registrado. Chamada no `lifespan` após
    `reconcile_instance_states`, para que uma instância marcada "running"
    mas na verdade morta já tenha sido corrigida antes deste passo rodar —
    senão abriria (e a reconciliação teria que fechar) um run para algo que
    não estava de fato em execução. Idempotente, como `_open_run`: rodar de
    novo em reinícios futuros não duplica nada.
    """
    rows = conn.execute(
        """SELECT id, user_id, image_id, COALESCE(last_seen_at, created_at) AS approx_started_at
           FROM instances WHERE state = 'running' AND deleted_at IS NULL"""
    ).fetchall()
    for row in rows:
        conn.execute(
            """INSERT INTO instance_runs (instance_id, user_id, image_id, started_at)
               SELECT ?, ?, ?, ? WHERE NOT EXISTS (
                   SELECT 1 FROM instance_runs WHERE instance_id = ? AND ended_at IS NULL
               )""",
            (row["id"], row["user_id"], row["image_id"], row["approx_started_at"], row["id"]),
        )


async def stop_all_running_for_user(conn: sqlite3.Connection, runtime: ContainerRuntime, user_id: int) -> None:
    """Usada ao desabilitar uma conta: para tudo que estiver em execução,
    preservando os volumes."""
    rows = conn.execute(
        "SELECT id FROM instances WHERE user_id = ? AND state = 'running' AND deleted_at IS NULL",
        (user_id,),
    ).fetchall()
    for row in rows:
        await stop_instance(conn, runtime, row["id"], user_id)
