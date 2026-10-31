import io
import tarfile

from app.services.ssh_identity import (
    KNOWN_HOSTS,
    build_ssh_archive,
    decrypt_private_key,
    get_or_create_identity,
    regenerate_identity,
)

from .conftest import insert_user


def test_gera_identidade_na_primeira_chamada(db_conn, app_settings):
    user_id = insert_user(db_conn)

    row = get_or_create_identity(db_conn, app_settings, user_id)

    assert row["user_id"] == user_id
    assert row["public_key"].startswith("ssh-ed25519 ")
    assert row["private_key_encrypted"]


def test_segunda_chamada_nao_duplica_nem_troca_a_chave(db_conn, app_settings):
    user_id = insert_user(db_conn)

    primeira = get_or_create_identity(db_conn, app_settings, user_id)
    segunda = get_or_create_identity(db_conn, app_settings, user_id)

    assert segunda["public_key"] == primeira["public_key"]
    total = db_conn.execute(
        "SELECT COUNT(*) FROM ssh_identities WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    assert total == 1


def test_regenerate_identity_troca_a_chave_publica(db_conn, app_settings):
    user_id = insert_user(db_conn)
    original = get_or_create_identity(db_conn, app_settings, user_id)

    nova = regenerate_identity(db_conn, app_settings, user_id)

    assert nova["public_key"] != original["public_key"]
    total = db_conn.execute(
        "SELECT COUNT(*) FROM ssh_identities WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    assert total == 1  # substitui, não acumula


def test_regenerate_identity_funciona_mesmo_sem_identidade_previa(db_conn, app_settings):
    user_id = insert_user(db_conn)

    row = regenerate_identity(db_conn, app_settings, user_id)

    assert row["public_key"].startswith("ssh-ed25519 ")


def test_private_key_encrypted_nao_e_a_chave_em_texto_puro(db_conn, app_settings):
    user_id = insert_user(db_conn)

    row = get_or_create_identity(db_conn, app_settings, user_id)

    assert b"OPENSSH PRIVATE KEY" not in row["private_key_encrypted"]


def test_decrypt_private_key_recupera_uma_chave_openssh_valida(db_conn, app_settings):
    user_id = insert_user(db_conn)
    row = get_or_create_identity(db_conn, app_settings, user_id)

    private_key = decrypt_private_key(app_settings, row)

    assert private_key.startswith(b"-----BEGIN OPENSSH PRIVATE KEY-----")


def test_identidades_de_usuarios_diferentes_sao_independentes(db_conn, app_settings):
    user_a = insert_user(db_conn, "a@exemplo.test")
    user_b = insert_user(db_conn, "b@exemplo.test")

    row_a = get_or_create_identity(db_conn, app_settings, user_a)
    row_b = get_or_create_identity(db_conn, app_settings, user_b)

    assert row_a["public_key"] != row_b["public_key"]


def _tar_members(tar_bytes: bytes) -> dict[str, tarfile.TarInfo]:
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r") as tar:
        return {member.name: member for member in tar.getmembers()}


def _tar_content(tar_bytes: bytes, name: str) -> bytes:
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r") as tar:
        return tar.extractfile(name).read()


def test_build_ssh_archive_tem_os_quatro_membros_esperados(db_conn, app_settings):
    user_id = insert_user(db_conn)
    identity = get_or_create_identity(db_conn, app_settings, user_id)
    private_key = decrypt_private_key(app_settings, identity)

    tar_bytes = build_ssh_archive(private_key, identity["public_key"], uid=0, gid=0)

    members = _tar_members(tar_bytes)
    assert set(members) == {".ssh", ".ssh/id_ed25519", ".ssh/id_ed25519.pub", ".ssh/known_hosts"}


def test_build_ssh_archive_modos_dos_membros(db_conn, app_settings):
    user_id = insert_user(db_conn)
    identity = get_or_create_identity(db_conn, app_settings, user_id)
    private_key = decrypt_private_key(app_settings, identity)

    tar_bytes = build_ssh_archive(private_key, identity["public_key"], uid=0, gid=0)

    members = _tar_members(tar_bytes)
    assert members[".ssh"].isdir()
    assert oct(members[".ssh"].mode) == "0o700"
    assert oct(members[".ssh/id_ed25519"].mode) == "0o600"
    assert oct(members[".ssh/id_ed25519.pub"].mode) == "0o644"
    assert oct(members[".ssh/known_hosts"].mode) == "0o644"


def test_build_ssh_archive_dono_fixado_para_imagem_de_agente(db_conn, app_settings):
    user_id = insert_user(db_conn)
    identity = get_or_create_identity(db_conn, app_settings, user_id)
    private_key = decrypt_private_key(app_settings, identity)

    tar_bytes = build_ssh_archive(private_key, identity["public_key"], uid=0, gid=0)

    members = _tar_members(tar_bytes)
    for member in members.values():
        assert (member.uid, member.gid) == (0, 0)


def test_build_ssh_archive_dono_fixado_para_imagem_webtop(db_conn, app_settings):
    user_id = insert_user(db_conn)
    identity = get_or_create_identity(db_conn, app_settings, user_id)
    private_key = decrypt_private_key(app_settings, identity)

    tar_bytes = build_ssh_archive(private_key, identity["public_key"], uid=1000, gid=1000)

    members = _tar_members(tar_bytes)
    for member in members.values():
        assert (member.uid, member.gid) == (1000, 1000)


def test_build_ssh_archive_conteudo_da_chave_privada_e_publica(db_conn, app_settings):
    user_id = insert_user(db_conn)
    identity = get_or_create_identity(db_conn, app_settings, user_id)
    private_key = decrypt_private_key(app_settings, identity)

    tar_bytes = build_ssh_archive(private_key, identity["public_key"], uid=0, gid=0)

    stored_private_key = _tar_content(tar_bytes, ".ssh/id_ed25519")
    assert stored_private_key.rstrip(b"\n") == private_key.rstrip(b"\n")
    assert stored_private_key.endswith(b"\n")
    assert _tar_content(tar_bytes, ".ssh/id_ed25519.pub").decode() == identity["public_key"] + "\n"


def test_build_ssh_archive_known_hosts_cobre_github_gitlab_bitbucket(db_conn, app_settings):
    user_id = insert_user(db_conn)
    identity = get_or_create_identity(db_conn, app_settings, user_id)
    private_key = decrypt_private_key(app_settings, identity)

    tar_bytes = build_ssh_archive(private_key, identity["public_key"], uid=0, gid=0)

    known_hosts = _tar_content(tar_bytes, ".ssh/known_hosts").decode()
    assert known_hosts == KNOWN_HOSTS
    for host in ("github.com", "gitlab.com", "bitbucket.org"):
        assert host in known_hosts
