from app.services.passwords import hash_password, verify_password


def test_hash_tem_sal_e_dois_hashes_da_mesma_senha_diferem():
    h1 = hash_password("senha-correta-123")
    h2 = hash_password("senha-correta-123")

    assert h1 != h2
    assert "senha-correta-123" not in h1


def test_senha_correta_valida():
    h = hash_password("senha-correta-123")
    assert verify_password("senha-correta-123", h) is True


def test_senha_incorreta_nao_valida():
    h = hash_password("senha-correta-123")
    assert verify_password("senha-errada", h) is False
