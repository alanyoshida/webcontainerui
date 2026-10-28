from app.services.activity import ActivityTracker


def test_toques_intensos_geram_no_maximo_uma_escrita_por_janela(db_conn):
    from .conftest import insert_image, insert_user

    user_id = insert_user(db_conn)
    image_id = insert_image(db_conn)
    instance_id = "inst-1"
    db_conn.execute(
        """INSERT INTO instances (id, user_id, image_id, volume_name, inner_user, inner_password)
           VALUES (?, ?, ?, 'vol', 'u', 'p')""",
        (instance_id, user_id, image_id),
    )

    tracker = ActivityTracker()
    for _ in range(500):  # tráfego intenso simulado
        tracker.touch(instance_id)

    escritas = tracker.flush(db_conn)

    assert escritas == 1
    row = db_conn.execute(
        "SELECT last_seen_at FROM instances WHERE id = ?", (instance_id,)
    ).fetchone()
    assert row["last_seen_at"] is not None


def test_sem_toques_flush_nao_escreve_nada(db_conn):
    tracker = ActivityTracker()
    assert tracker.flush(db_conn) == 0
