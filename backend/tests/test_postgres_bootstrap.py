"""Bootstrap do schema em PostgreSQL real (change postgres-for-production).

Opt-in (`pytest -m e2e`): exige Docker. O teste SQLite equivalente
(banco legado + idempotência) vive em `test_db.py` e roda na suíte padrão.
"""

import sqlalchemy as sa
import pytest

from app.db import init_db, make_engine

from .postgres_server import postgres_url  # noqa: F401 - fixture

pytestmark = pytest.mark.e2e

_TABELAS = {
    "users",
    "sessions",
    "groups",
    "user_groups",
    "images",
    "group_images",
    "instances",
    "instance_runs",
    "ssh_identities",
    "agent_md_documents",
    "agent_skills",
    "image_skills",
    "mcp_servers",
    "image_mcp_servers",
}


def test_bootstrap_cria_schema_e_e_idempotente_no_postgres(postgres_url):
    engine = make_engine(postgres_url)
    try:
        init_db(engine)
        inspector = sa.inspect(engine)
        assert _TABELAS <= set(inspector.get_table_names())

        indices = {i["name"] for i in inspector.get_indexes("instances")}
        assert "uq_instances_user_image_live" in indices
        assert "idx_instances_user_id" in indices

        with engine.connect() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO users (email, password_hash)"
                    " VALUES ('persistente@pg.test', 'hash')"
                )
            )

        # Reiniciar sobre um banco já migrado é uma operação nula.
        init_db(engine)

        with engine.connect() as conn:
            total = conn.execute(
                sa.text("SELECT COUNT(*) FROM users WHERE email = 'persistente@pg.test'")
            ).scalar_one()
        assert total == 1
    finally:
        engine.dispose()
