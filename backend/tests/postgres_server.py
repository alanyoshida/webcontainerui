"""PostgreSQL efêmero para os testes e2e (via Docker).

Não é um módulo de teste (nome sem `test_`) — é o utilitário compartilhado
por `test_postgres_bootstrap.py` e `test_e2e_postgres.py`. Só é importado
por testes marcados `e2e`, que exigem Docker e são desselecionados por
padrão.
"""

import socket
import subprocess
import time
import uuid

import pytest

IMAGE = "postgres:16-alpine"
USER = "wcui"
PASSWORD = "senha-dos-testes-e2e"
DATABASE = "wcui"


def docker_available() -> bool:
    try:
        return (
            subprocess.run(
                ["docker", "version"], capture_output=True, check=False
            ).returncode
            == 0
        )
    except FileNotFoundError:
        return False


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class PostgresServer:
    def __init__(self) -> None:
        self.name = f"wcui-e2e-pg-{uuid.uuid4().hex[:8]}"
        self.port = _free_port()

    @property
    def url(self) -> str:
        return f"postgresql+psycopg://{USER}:{PASSWORD}@127.0.0.1:{self.port}/{DATABASE}"

    def start(self) -> str:
        subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--rm",
                "--name",
                self.name,
                "-e",
                f"POSTGRES_PASSWORD={PASSWORD}",
                "-e",
                f"POSTGRES_USER={USER}",
                "-e",
                f"POSTGRES_DB={DATABASE}",
                "-p",
                f"127.0.0.1:{self.port}:5432",
                IMAGE,
            ],
            check=True,
            capture_output=True,
        )
        deadline = time.time() + 60
        while time.time() < deadline:
            if (
                subprocess.run(
                    ["docker", "exec", self.name, "pg_isready", "-U", USER, "-d", DATABASE],
                    capture_output=True,
                    check=False,
                ).returncode
                == 0
            ):
                return self.url
            time.sleep(0.5)
        raise RuntimeError("PostgreSQL de teste não ficou pronto")

    def stop(self) -> None:
        subprocess.run(
            ["docker", "rm", "-f", self.name], check=False, capture_output=True
        )


@pytest.fixture(scope="module")
def postgres_url():
    if not docker_available():
        pytest.skip("Docker indisponível para o teste e2e de PostgreSQL")
    server = PostgresServer()
    try:
        yield server.start()
    finally:
        server.stop()
