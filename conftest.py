"""Guarda global: a suíte não fala com banco remoto.

Este arquivo existe por causa de um incidente real, registrado no Apêndice B de
`docs/revisoes/REVIEW_feat-endpoint-pontos-de-interesse.md`. Rodar `pytest` na
máquina de desenvolvimento lê o `.env` do projeto — que aponta para o Supabase
de PRODUÇÃO —, e o pytest-django CRIA e DERRUBA um banco `test_<nome>` na
instância que encontrar. Naquela ocasião sobrou um `test_postgres` órfão, porque
o teardown falhou com "is being accessed by other users".

A metade do STORAGE foi fechada em `tests/conftest.py`, que troca o backend de
arquivos por um temporário. A metade do BANCO é esta, e ficou aberta por um
tempo: o compose resolve o caso do `runserver` com `DJANGO_IGNORE_DOTENV=True`,
mas o `pytest` rodado do host não passa por lugar nenhum que ligue essa flag.

Mora na RAIZ, e não em `tests/`, de propósito. Só os conftest iniciais — o da
rootdir e o dos caminhos passados na linha de comando — têm `pytest_configure`
chamado antes da coleta. Em `tests/conftest.py` o gancho pode ser carregado
tarde demais, e "tarde demais" aqui significa depois de o banco de teste já ter
sido criado na instância errada.

A guarda FALHA, e não redireciona sozinha para o banco local. Redirecionar em
silêncio seria a mesma armadilha do bug original com o sinal trocado: quem
rodasse a suíte não saberia contra o que ela rodou. Errar alto custa uma
mensagem; errar baixo custou 34 objetos sobrescritos.
"""
import pytest

#: Hosts que representam um Postgres descartável — na máquina ou no compose.
#: `db` é o nome do serviço no `infra/docker-compose.yml`; vazio é o socket
#: local. Qualquer coisa fora desta lista é tratada como remota.
HOSTS_LOCAIS = frozenset({"", "localhost", "127.0.0.1", "::1", "db"})

RECADO = """
A suíte foi interrompida ANTES de tocar o banco.

  banco de destino: {host}

Esse host não é local, e o pytest-django criaria e derrubaria um banco
`test_...` nele. Se for o Supabase, é a instância de produção do projeto.

Rode a suíte dentro do container, que é o caminho recomendado:

    cd infra
    docker compose run --rm backend pytest

Ou, para rodar da máquina, aponte para o Postgres do compose antes:

    $env:DJANGO_IGNORE_DOTENV = "True"
    $env:DATABASE_URL = "postgres://ecosol:ecosol@localhost:5432/ecosol"
    pytest

(Em bash: `DJANGO_IGNORE_DOTENV=True DATABASE_URL=... pytest`.)
"""


def pytest_configure(config):
    """Interrompe a sessão se o banco configurado não for local.

    O acesso a `settings` é adiado para dentro da função: no topo do módulo ele
    aconteceria antes de o pytest-django exportar o `DJANGO_SETTINGS_MODULE` que
    está no `pyproject.toml`.
    """
    from django.conf import settings

    host = (settings.DATABASES["default"].get("HOST") or "").strip()

    if host.lower() in HOSTS_LOCAIS:
        return

    raise pytest.UsageError(RECADO.format(host=host))
