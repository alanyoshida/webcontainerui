from app.services.usage_metrics import (
    daily_series,
    hours_by_group,
    hours_by_user,
    image_ranking,
    list_live_runs,
    list_runs,
    peak_concurrency,
    reason_breakdown,
)

from .conftest import (
    add_user_to_group,
    insert_group,
    insert_image,
    insert_instance,
    insert_run,
    insert_user,
)

PERIOD_SINCE = "2024-06-01 00:00:00"
PERIOD_UNTIL = "2024-06-30 23:59:59"


def test_live_runs_lista_instancias_de_usuarios_diferentes_em_execucao(db_conn):
    image_id = insert_image(db_conn)
    outra_image_id = insert_image(db_conn, repository="lscr.io/linuxserver/webtop", tag="alpine-kde")
    user_a = insert_user(db_conn, "a@exemplo.test")
    user_b = insert_user(db_conn, "b@exemplo.test")
    inst_a = insert_instance(db_conn, user_a, image_id)
    inst_b = insert_instance(db_conn, user_b, image_id)
    insert_run(db_conn, inst_a, user_a, image_id, "2024-06-10 10:00:00")
    insert_run(db_conn, inst_b, user_b, image_id, "2024-06-10 11:00:00")
    # run fechado, não deve aparecer
    other_inst = insert_instance(db_conn, user_a, outra_image_id, state="stopped")
    insert_run(db_conn, other_inst, user_a, outra_image_id, "2024-06-01 00:00:00", "2024-06-01 01:00:00", "user_stop")

    live = list_live_runs(db_conn)

    assert {row["instance_id"] for row in live} == {inst_a, inst_b}
    assert all(row["ended_at"] is None for row in live)


def test_runs_fora_do_periodo_nao_aparecem_e_run_aberto_tem_fim_vazio(db_conn):
    image_id = insert_image(db_conn)
    outra_image_id = insert_image(db_conn, repository="lscr.io/linuxserver/webtop", tag="alpine-kde")
    user_id = insert_user(db_conn)
    dentro = insert_instance(db_conn, user_id, image_id)
    insert_run(db_conn, dentro, user_id, image_id, "2024-06-15 00:00:00")  # ainda aberto
    fora = insert_instance(db_conn, user_id, outra_image_id, state="stopped")
    insert_run(db_conn, fora, user_id, outra_image_id, "2024-01-01 00:00:00", "2024-01-01 01:00:00", "user_stop")

    rows, total = list_runs(db_conn, PERIOD_SINCE, PERIOD_UNTIL)

    assert total == 1
    assert rows[0]["instance_id"] == dentro
    assert rows[0]["ended_at"] is None


def test_horas_por_usuario_soma_duracao_incluindo_run_em_curso(db_conn):
    image_id = insert_image(db_conn)
    outra_image_id = insert_image(db_conn, repository="lscr.io/linuxserver/webtop", tag="alpine-kde")
    user_id = insert_user(db_conn)
    fechado = insert_instance(db_conn, user_id, image_id, state="stopped")
    insert_run(db_conn, fechado, user_id, image_id, "2024-06-10 10:00:00", "2024-06-10 12:00:00", "user_stop")
    aberto = insert_instance(db_conn, user_id, outra_image_id)
    db_conn.execute(
        "INSERT INTO instance_runs (instance_id, user_id, image_id, started_at) VALUES (?, ?, ?, ?)",
        (aberto, user_id, outra_image_id, PERIOD_SINCE),
    )

    totals = hours_by_user(db_conn, PERIOD_SINCE, PERIOD_UNTIL)

    assert len(totals) == 1
    assert totals[0]["user_id"] == user_id
    assert totals[0]["seconds"] >= 2 * 3600  # ao menos as 2h do run fechado + parte do aberto


def test_horas_por_grupo_conta_usuario_em_dois_grupos_nos_dois(db_conn):
    image_id = insert_image(db_conn)
    user_id = insert_user(db_conn)
    grupo_a = insert_group(db_conn, "A")
    grupo_b = insert_group(db_conn, "B")
    add_user_to_group(db_conn, user_id, grupo_a)
    add_user_to_group(db_conn, user_id, grupo_b)
    instance_id = insert_instance(db_conn, user_id, image_id, state="stopped")
    insert_run(db_conn, instance_id, user_id, image_id, "2024-06-10 10:00:00", "2024-06-10 12:00:00", "user_stop")

    totals = hours_by_group(db_conn, PERIOD_SINCE, PERIOD_UNTIL)

    assert {t["group_id"] for t in totals} == {grupo_a, grupo_b}
    for t in totals:
        assert t["seconds"] == 2 * 3600


def test_ranking_de_imagens_ordena_por_uso(db_conn):
    user_a = insert_user(db_conn, "a@exemplo.test")
    user_b = insert_user(db_conn, "b@exemplo.test")
    popular = insert_image(db_conn, repository="lscr.io/linuxserver/webtop", tag="latest")
    rara = insert_image(db_conn, repository="lscr.io/linuxserver/webtop", tag="alpine-kde")
    inst_popular_1 = insert_instance(db_conn, user_a, popular, state="stopped")
    inst_popular_2 = insert_instance(db_conn, user_b, popular, state="stopped")
    inst_rara = insert_instance(db_conn, user_a, rara, state="stopped")
    insert_run(db_conn, inst_popular_1, user_a, popular, "2024-06-10 00:00:00", "2024-06-10 01:00:00", "user_stop")
    insert_run(db_conn, inst_popular_2, user_b, popular, "2024-06-11 00:00:00", "2024-06-11 01:00:00", "user_stop")
    insert_run(db_conn, inst_rara, user_a, rara, "2024-06-12 00:00:00", "2024-06-12 01:00:00", "user_stop")

    ranking = image_ranking(db_conn, PERIOD_SINCE, PERIOD_UNTIL)

    assert ranking[0]["image_id"] == popular
    assert ranking[0]["run_count"] == 2
    assert ranking[1]["image_id"] == rara
    assert ranking[1]["run_count"] == 1


def test_distribuicao_por_motivo_cobre_os_quatro_motivos(db_conn):
    user_id = insert_user(db_conn)
    for reason in ("user_stop", "idle_timeout", "reconciled", "deleted"):
        image_id = insert_image(db_conn, repository="lscr.io/linuxserver/webtop", tag=reason)
        instance_id = insert_instance(db_conn, user_id, image_id, state="stopped")
        insert_run(db_conn, instance_id, user_id, image_id, "2024-06-10 00:00:00", "2024-06-10 01:00:00", reason)

    breakdown = {row["reason"]: row["count"] for row in reason_breakdown(db_conn, PERIOD_SINCE, PERIOD_UNTIL)}

    assert breakdown == {"user_stop": 1, "idle_timeout": 1, "reconciled": 1, "deleted": 1}


def test_serie_diaria_conta_run_que_atravessa_meia_noite_nos_dois_dias(db_conn):
    image_id = insert_image(db_conn)
    user_id = insert_user(db_conn)
    instance_id = insert_instance(db_conn, user_id, image_id, state="stopped")
    insert_run(db_conn, instance_id, user_id, image_id, "2024-06-10 23:00:00", "2024-06-11 01:00:00", "user_stop")

    series = {row["date"]: row["count"] for row in daily_series(db_conn, "2024-06-09 00:00:00", "2024-06-12 23:59:59")}

    assert series["2024-06-10"] == 1
    assert series["2024-06-11"] == 1
    assert series["2024-06-09"] == 0
    assert series["2024-06-12"] == 0


def test_pico_de_simultaneidade_conta_sobreposicao_e_nao_apenas_sequencia(db_conn):
    user_a = insert_user(db_conn, "a@exemplo.test")
    user_b = insert_user(db_conn, "b@exemplo.test")
    image_id = insert_image(db_conn)

    # dois runs sobrepostos: pico 2
    inst_1 = insert_instance(db_conn, user_a, image_id, state="stopped")
    inst_2 = insert_instance(db_conn, user_b, image_id, state="stopped")
    insert_run(db_conn, inst_1, user_a, image_id, "2024-06-10 10:00:00", "2024-06-10 12:00:00", "user_stop")
    insert_run(db_conn, inst_2, user_b, image_id, "2024-06-10 11:00:00", "2024-06-10 13:00:00", "user_stop")

    assert peak_concurrency(db_conn, PERIOD_SINCE, PERIOD_UNTIL) == 2


def test_pico_de_simultaneidade_runs_sequenciais_sem_sobreposicao_e_um(db_conn):
    user_a = insert_user(db_conn, "a@exemplo.test")
    user_b = insert_user(db_conn, "b@exemplo.test")
    image_id = insert_image(db_conn)
    inst_1 = insert_instance(db_conn, user_a, image_id, state="stopped")
    inst_2 = insert_instance(db_conn, user_b, image_id, state="stopped")
    insert_run(db_conn, inst_1, user_a, image_id, "2024-06-10 10:00:00", "2024-06-10 11:00:00", "user_stop")
    insert_run(db_conn, inst_2, user_b, image_id, "2024-06-10 12:00:00", "2024-06-10 13:00:00", "user_stop")

    assert peak_concurrency(db_conn, PERIOD_SINCE, PERIOD_UNTIL) == 1
