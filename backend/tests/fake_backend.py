"""Servidor real e mínimo que faz o papel do container nos testes do proxy.

O proxy sob teste (`app/api/session_proxy.py`) faz chamadas de rede de
verdade com `httpx` e `websockets`; por isso este backend roda num
servidor `uvicorn` de fato, não só numa transport ASGI em memória, e os
testes resolvem o container de cada instância para o endereço dele.
"""

import asyncio
import threading
import time

import uvicorn
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI()


@app.api_route("/i/{instance_id}/echo-headers", methods=["GET", "POST"])
async def echo_headers(instance_id: str, request: Request) -> JSONResponse:
    body = await request.body()
    return JSONResponse(
        {
            "instance_id": instance_id,
            "authorization": request.headers.get("authorization"),
            "method": request.method,
            "body": body.decode("utf-8", errors="replace"),
        }
    )


@app.get("/i/{instance_id}/stream")
async def stream(instance_id: str):
    async def chunks():
        for i in range(5):
            yield f"chunk-{i}\n".encode()
            await asyncio.sleep(0.05)

    return StreamingResponse(chunks(), media_type="text/plain")


@app.websocket("/i/{instance_id}/ws")
async def ws_echo(websocket: WebSocket, instance_id: str) -> None:
    requested = websocket.scope.get("subprotocols") or []
    await websocket.accept(subprotocol=requested[0] if requested else None)
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
            if message.get("text") is not None:
                await websocket.send_text("echo:" + message["text"])
            elif message.get("bytes") is not None:
                await websocket.send_bytes(b"echo:" + message["bytes"])
    except Exception:
        pass


class FakeBackendServer:
    """Controla o ciclo de vida do servidor uvicorn usado nos testes.

    Roda numa thread com seu próprio event loop (via `Server.run`, que
    internamente faz `asyncio.run`), não como uma task no loop do teste.
    O `TestClient` do app sob teste usa sua própria thread/loop (o
    "portal" do Starlette) para cada chamada síncrona; se este servidor
    fosse apenas uma task no loop do pytest-asyncio, esse loop ficaria
    parado durante o corpo síncrono do teste e a conexão nunca seria
    processada — exatamente o sintoma que gerou `httpx.ReadTimeout` até
    esta classe ser reescrita para rodar numa thread de verdade, como um
    servidor externo de fato se comportaria.
    """

    def __init__(self) -> None:
        config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning", lifespan="off")
        self.server = uvicorn.Server(config)
        self._thread: threading.Thread | None = None

    def start(self) -> int:
        self._thread = threading.Thread(target=self.server.run, daemon=True)
        self._thread.start()
        while not self.server.started:
            time.sleep(0.01)
        return self.server.servers[0].sockets[0].getsockname()[1]

    def stop(self) -> None:
        self.server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=5)
