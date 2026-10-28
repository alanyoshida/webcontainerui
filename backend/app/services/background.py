import asyncio
from collections.abc import Coroutine
from typing import Any

from fastapi import FastAPI


def spawn(app: FastAPI, coro: Coroutine[Any, Any, Any]) -> asyncio.Task:
    """Agenda uma tarefa de fundo rastreada por `app.state.background_tasks`.

    O rastreamento existe para que o `lifespan` consiga cancelar e aguardar
    tarefas pendentes no desligamento, em vez de deixá-las soltas quando o
    event loop fecha.
    """
    task = asyncio.create_task(coro)
    app.state.background_tasks.add(task)
    task.add_done_callback(app.state.background_tasks.discard)
    return task


async def cancel_all(app: FastAPI) -> None:
    tasks = list(app.state.background_tasks)
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
