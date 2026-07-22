"""Smoke test: garante que a suíte roda e o projeto sobe.

A suíte de verdade (regressão de LGPD + núcleo, PRD Seção 7) entra no PR 6.
"""


def test_a_suite_roda():
    assert True


def test_healthcheck_responde(client):
    resposta = client.get("/health/")
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}
