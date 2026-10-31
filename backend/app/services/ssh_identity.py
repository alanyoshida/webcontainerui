import io
import sqlite3
import tarfile
import time

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.config import Settings

# Chaves de host SSH publicadas pelo GitHub, GitLab e Bitbucket, obtidas via
# `ssh-keyscan` direto contra cada servidor (conferidas também contra
# https://api.github.com/meta e https://bitbucket.org/site/ssh) — pré-
# cadastradas para que o primeiro `git clone`/`ssh` não trave esperando
# confirmação de host desconhecido (spec: known_hosts pré-cadastrado).
KNOWN_HOSTS = """\
github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl
github.com ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBEmKSENjQEezOmxkZMy7opKgwFB9nkt5YRrYMjNuG5N87uRgg6CLrbo5wAdT/y6v0mKV0U2w0WZ2YB/++Tpockg=
github.com ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQCj7ndNxQowgcQnjshcLrqPEiiphnt+VTTvDP6mHBL9j1aNUkY4Ue1gvwnGLVlOhGeYrnZaMgRK6+PKCUXaDbC7qtbW8gIkhL7aGCsOr/C56SJMy/BCZfxd1nWzAOxSDPgVsmerOBYfNqltV9/hWCqBywINIR+5dIg6JTJ72pcEpEjcYgXkE2YEFXV1JHnsKgbLWNlhScqb2UmyRkQyytRLtL+38TGxkxCflmO+5Z8CSSNY7GidjMIZ7Q4zMjA2n1nGrlTDkzwDCsw+wqFPGQA179cnfGWOWRVruj16z6XyvxvjJwbz0wQZ75XK5tKSb7FNyeIEs4TT4jk+S4dhPeAUC5y+bDYirYgM4GC7uEnztnZyaVWQ7B381AK4Qdrwt51ZqExKbQpTUNn+EjqoTwvqNj4kqx5QUCI0ThS/YkOxJCXmPUWZbhjpCg56i+2aB6CmK2JGhn57K5mj0MNdBXA4/WnwH6XoPWJzK5Nyu2zB3nAZp+S5hpQs+p1vN1/wsjk=
gitlab.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAfuCHKVTjquxvt6CM6tdG4SLp1Btn/nOeHHE5UOzRdf
gitlab.com ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBFSMqzJeV9rUzU4kWitGjeR4PWSa29SPqJ1fVkhtj3Hw9xjLVXVYrU9QlYWrOLXBpQ6KWjbjTDTdDkoohFzgbEY=
gitlab.com ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCsj2bNKTBSpIYDEGk9KxsGh3mySTRgMtXL583qmBpzeQ+jqCMRgBqB98u3z++J1sKlXHWfM9dyhSevkMwSbhoR8XIq/U0tCNyokEi/ueaBMCvbcTHhO7FcwzY92WK4Yt0aGROY5qX2UKSeOvuP4D6TPqKF1onrSzH9bx9XUf2lEdWT/ia1NEKjunUqu1xOB/StKDHMoX4/OKyIzuS0q/T1zOATthvasJFoPrAjkohTyaDUz2LN5JoH839hViyEG82yB+MjcFV5MU3N1l1QL3cVUCh93xSaua1N85qivl+siMkPGbO5xR/En4iEY6K2XPASUEMaieWVNTRCtJ4S8H+9
bitbucket.org ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIIazEu89wgQZ4bqs3d63QSMzYVa0MuJ2e2gKTKqu+UUO
bitbucket.org ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBPIQmuzMBuKdWeF4+a2sjSSpBK0iqitSQ+5BM9KhpexuGt20JpTVM7u5BDZngncgrqDMbWdxMWWOGtZ9UgbqgZE=
bitbucket.org ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDQeJzhupRu0u0cdegZIa8e86EG2qOCsIsD1Xw0xSeiPDlCr7kq97NLmMbpKTX6Esc30NuoqEEHCuc7yWtwp8dI76EEEB1VqY9QJq6vk+aySyboD5QF61I/1WeTwu+deCbgKMGbUijeXhtfbxSxm6JwGrXrhBdofTsbKRUsrN1WoNgUa8uqN1Vx6WAJw1JHPhglEGGHea6QICwJOAr/6mrui/oB7pkaWKHj3z7d1IC4KWLtY47elvjbaTlkN04Kc/5LFEirorGYVbt15kAUlqGM65pk6ZBxtaO3+30LVlORZkxOh+LKL/BvbZ/iRNhItLqNyieoQj/uh/7Iv4uyH/cV/0b4WDSd3DptigWq84lJubb9t/DnZlrJazxyDCulTmKdOR7vs9gMTo+uoIrPSb8ScTtvw65+odKAlBj59dhnVp9zd7QUojOpXlL62Aw56U4oO+FALuevvMjiWeavKhJqlR7i5n9srYcrNV7ttmDw7kf/97P5zauIhxcjX+xHv4M=
"""

_SELECT_IDENTITY = (
    "SELECT user_id, public_key, private_key_encrypted, created_at "
    "FROM ssh_identities WHERE user_id = ?"
)


def _generate_keypair() -> tuple[bytes, bytes]:
    """Gera um par Ed25519 e serializa ambas as metades em formato OpenSSH,
    prontas para uso por `ssh`/`git` sem conversão adicional (design.md D1)."""
    private_key = Ed25519PrivateKey.generate()
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH,
    )
    return private_bytes, public_bytes


def _fernet(settings: Settings) -> Fernet:
    return Fernet(settings.ssh_key_encryption_key.encode())


def _get_identity_row(conn: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    return conn.execute(_SELECT_IDENTITY, (user_id,)).fetchone()


def get_or_create_identity(conn: sqlite3.Connection, settings: Settings, user_id: int) -> sqlite3.Row:
    """Retorna a identidade SSH do usuário, gerando-a sob demanda se ainda
    não existir (spec: "Identidade gerada sob demanda"). Nunca sobrescreve
    uma identidade já existente — só `regenerate_identity` faz isso."""
    row = _get_identity_row(conn, user_id)
    if row is not None:
        return row

    private_bytes, public_bytes = _generate_keypair()
    encrypted = _fernet(settings).encrypt(private_bytes)
    conn.execute(
        "INSERT INTO ssh_identities (user_id, public_key, private_key_encrypted) VALUES (?, ?, ?)",
        (user_id, public_bytes.decode(), encrypted),
    )
    return _get_identity_row(conn, user_id)


def regenerate_identity(conn: sqlite3.Connection, settings: Settings, user_id: int) -> sqlite3.Row:
    """Substitui a identidade SSH do usuário por uma nova — a chave pública
    antiga deixa de corresponder à nova chave privada (spec: "Regeneração
    troca a chave pública exibida")."""
    private_bytes, public_bytes = _generate_keypair()
    encrypted = _fernet(settings).encrypt(private_bytes)
    conn.execute(
        """INSERT INTO ssh_identities (user_id, public_key, private_key_encrypted)
               VALUES (?, ?, ?)
           ON CONFLICT (user_id) DO UPDATE SET
               public_key = excluded.public_key,
               private_key_encrypted = excluded.private_key_encrypted,
               created_at = datetime('now')""",
        (user_id, public_bytes.decode(), encrypted),
    )
    return _get_identity_row(conn, user_id)


def decrypt_private_key(settings: Settings, identity_row: sqlite3.Row) -> bytes:
    """Decifra a chave privada de uma linha de `ssh_identities` — uso
    interno (montagem do pacote a injetar no container, `build_ssh_archive`
    abaixo). Nunca exposta a uma resposta de API."""
    return _fernet(settings).decrypt(identity_row["private_key_encrypted"])


def _add_tar_member(
    tar: tarfile.TarFile,
    name: str,
    content: bytes,
    mode: int,
    *,
    uid: int,
    gid: int,
    mtime: int,
    is_dir: bool = False,
) -> None:
    info = tarfile.TarInfo(name=name)
    info.mode = mode
    info.uid = uid
    info.gid = gid
    info.mtime = mtime
    if is_dir:
        info.type = tarfile.DIRTYPE
        tar.addfile(info)
    else:
        info.size = len(content)
        tar.addfile(info, io.BytesIO(content))


def build_ssh_archive(private_key: bytes, public_key: str, *, uid: int, gid: int) -> bytes:
    """Monta o tar a injetar via `put_archive` em `~/.ssh` de uma instância
    (design.md D3): `.ssh/` (700), `id_ed25519` (600), `id_ed25519.pub`
    (644) e `known_hosts` pré-cadastrado (644), todos com o dono (`uid`/
    `gid`) informado pelo chamador — root para imagens de agente, PUID/PGID
    para imagens webtop (a distinção não é responsabilidade deste módulo)."""
    buffer = io.BytesIO()
    now = int(time.time())
    public_key_bytes = (public_key.rstrip("\n") + "\n").encode()
    private_key_bytes = private_key if private_key.endswith(b"\n") else private_key + b"\n"

    with tarfile.open(fileobj=buffer, mode="w") as tar:
        _add_tar_member(tar, ".ssh", b"", 0o700, uid=uid, gid=gid, mtime=now, is_dir=True)
        _add_tar_member(tar, ".ssh/id_ed25519", private_key_bytes, 0o600, uid=uid, gid=gid, mtime=now)
        _add_tar_member(tar, ".ssh/id_ed25519.pub", public_key_bytes, 0o644, uid=uid, gid=gid, mtime=now)
        _add_tar_member(tar, ".ssh/known_hosts", KNOWN_HOSTS.encode(), 0o644, uid=uid, gid=gid, mtime=now)

    return buffer.getvalue()
