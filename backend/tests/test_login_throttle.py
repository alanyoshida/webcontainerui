from app.services.login_throttle import LoginThrottle


class FakeClock:
    def __init__(self) -> None:
        self.value = 1000.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def make_throttle(clock, *, max_failures=3, window=300, lock=300) -> LoginThrottle:
    return LoginThrottle(
        max_failures=max_failures,
        window_seconds=window,
        lock_seconds=lock,
        now=clock,
    )


def test_abaixo_do_limite_nao_ha_recusa():
    clock = FakeClock()
    throttle = make_throttle(clock, max_failures=3)

    for _ in range(2):
        throttle.record_failure("email:ana@x.test")

    assert throttle.retry_after_seconds("email:ana@x.test") is None


def test_limite_atingido_na_consulta_seguinte():
    clock = FakeClock()
    throttle = make_throttle(clock, max_failures=3)

    for _ in range(3):
        throttle.record_failure("email:ana@x.test")

    # a tentativa que estourou o limiar foi processada; a próxima encontra recusa
    retry = throttle.retry_after_seconds("email:ana@x.test")
    assert retry is not None and 1 <= retry <= 300


def test_recusa_expira_e_zera_a_contagem():
    clock = FakeClock()
    throttle = make_throttle(clock, max_failures=3, window=300, lock=300)

    for _ in range(3):
        throttle.record_failure("email:ana@x.test")
    assert throttle.retry_after_seconds("email:ana@x.test") is not None

    clock.advance(301)

    # vencida a recusa, as falhas antigas não re-travam a chave na hora
    assert throttle.retry_after_seconds("email:ana@x.test") is None


def test_recusa_aplica_se_mesmo_com_novas_falhas_antes_de_expirar():
    clock = FakeClock()
    throttle = make_throttle(clock, max_failures=3, window=300, lock=300)

    for _ in range(3):
        throttle.record_failure("email:ana@x.test")
    # consulta trava a chave em t=1000 (libera em 1300)
    assert throttle.retry_after_seconds("email:ana@x.test") is not None

    clock.advance(100)
    throttle.record_failure("email:ana@x.test")

    # ainda dentro da recusa: falha extra não estende nem encerra o lock
    retry = throttle.retry_after_seconds("email:ana@x.test")
    assert retry is not None and 190 <= retry <= 200


def test_falhas_fora_da_janela_nao_contam():
    clock = FakeClock()
    throttle = make_throttle(clock, max_failures=3, window=300)

    throttle.record_failure("email:ana@x.test")
    clock.advance(301)
    throttle.record_failure("email:ana@x.test")
    clock.advance(301)
    throttle.record_failure("email:ana@x.test")

    # três falhas no total, mas nunca duas dentro da mesma janela
    assert throttle.retry_after_seconds("email:ana@x.test") is None


def test_chaves_sao_independentes():
    clock = FakeClock()
    throttle = make_throttle(clock, max_failures=3)

    for _ in range(3):
        throttle.record_failure("email:ana@x.test")

    assert throttle.retry_after_seconds("email:ana@x.test") is not None
    assert throttle.retry_after_seconds("email:bia@x.test") is None
    assert throttle.retry_after_seconds("ip:10.0.0.1") is None


def test_recusa_da_chave_mais_restritiva_vence():
    clock = FakeClock()
    throttle = make_throttle(clock, max_failures=2, lock=300)

    throttle.record_failure("email:ana@x.test", "ip:10.0.0.1")
    throttle.record_failure("email:ana@x.test", "ip:10.0.0.1")
    # consulta trava a conta em t=1000 (libera em 1300); o IP tem as mesmas
    # falhas mas só trava na próxima consulta que o envolver
    assert throttle.retry_after_seconds("email:ana@x.test") is not None

    clock.advance(50)  # t=1050
    throttle.record_failure("ip:10.0.0.1")
    throttle.record_failure("ip:10.0.0.1")

    # conta libera em 1300 (faltam 250); IP libera em 1350 (faltam 300);
    # a conta é a mais restritiva e define o Retry-After
    retry = throttle.retry_after_seconds("email:ana@x.test", "ip:10.0.0.1")
    assert retry is not None and 240 <= retry <= 250


def test_sucesso_zera_so_a_chave_informada():
    clock = FakeClock()
    throttle = make_throttle(clock, max_failures=2)

    throttle.record_failure("email:ana@x.test", "ip:10.0.0.1")
    throttle.record_failure("email:ana@x.test", "ip:10.0.0.1")
    # ambos os buckets bateram o limiar
    assert throttle.retry_after_seconds("email:ana@x.test", "ip:10.0.0.1") is not None

    throttle.record_success("email:ana@x.test")

    assert throttle.retry_after_seconds("email:ana@x.test") is None
    assert throttle.retry_after_seconds("ip:10.0.0.1") is not None


def test_poda_remove_entradas_abandonadas():
    clock = FakeClock()
    throttle = make_throttle(clock, max_failures=3, window=300)

    throttle.record_failure("email:antiga@x.test")
    clock.advance(301)
    throttle.record_failure("email:nova@x.test")

    # a poda acontece no acesso: consultada depois da janela, a chave antiga
    # perde a falha expirada e sai do mapa
    assert throttle.retry_after_seconds("email:antiga@x.test") is None
    assert "email:antiga@x.test" not in throttle._failures
    assert len(throttle._failures) == 1


def test_retry_after_minimo_e_um_segundo():
    clock = FakeClock()
    throttle = make_throttle(clock, max_failures=1, lock=300)

    throttle.record_failure("email:ana@x.test")
    assert throttle.retry_after_seconds("email:ana@x.test") is not None  # trava em t=1000
    clock.advance(299.9)

    # faltam 0.1s para liberar: Retry-After nunca desce de 1 segundo
    retry = throttle.retry_after_seconds("email:ana@x.test")
    assert retry == 1
