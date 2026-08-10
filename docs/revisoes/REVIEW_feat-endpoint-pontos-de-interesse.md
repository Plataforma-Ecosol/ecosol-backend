# Revisão de Código — diff local (feat/endpoint-pontos-de-interesse @ 899c999)
<!-- slug: feat-endpoint-pontos-de-interesse -->
> Revisado: `origin/staging...HEAD` (ba19b82…899c999) · Motor: sharp-review (multi-agente + verificação) · Status: APLICADO (8/8 aprovados)
> Todos os achados foram aprovados e aplicados na árvore de trabalho.

## 0. Resumo

A fatia entrega o que o PRD pediu: os dois serializers batem campo a campo e na ordem com as Seções 3.4 e 3.6, `ativo` não sai em nenhuma resposta nem entra em nenhum filtro, os dois querysets fixam `ativo=True`, as duas views são `ReadOnlyModelViewSet` com `permission_classes` explícito, a guarda do coletivo inativo fecha sem porta lateral, e a partição `proximos`/`passados` não sofre o problema de lógica trivalente com `data_fim` nula. Não há migration, não há model tocado, `ruff` passa e — com `DJANGO_USE_S3=False`, que é a configuração do CI — os 38 testes passam. Os dois candidatos 🔴 da passada determinística foram refutados por leitura (ver Apêndice A), e dois achados 🔵 sobre forma de declaração foram refutados por contrariarem código prescrito literalmente no PRD.

O que sobra é quase todo na suíte de testes, e um dele é sério: **a fixture `media_temporaria` não isola upload**, então rodar `pytest` numa máquina com o `.env` do projeto grava PNGs de teste no bucket `divulgacao` de produção — com `AWS_S3_FILE_OVERWRITE` no default `True`, sobrescrevendo qualquer objeto de mesma chave. Os outros sete são asserções que passariam mesmo com o código errado, e higiene de fixture. Nenhum toca exposição de dado pessoal.

| Severidade | Quantidade |
|---|---|
| 🔴 Crítico | 1 |
| 🟡 Nocivo | 3 |
| 🔵 Incongruência | 0 |
| 🟣 Qualidade de código | 4 |

## 1. 🔴 Crítico

### 1.1 A fixture `media_temporaria` não isola upload: com `DJANGO_USE_S3=True` a suíte escreve no bucket de produção — `tests/test_api_eventos.py:56`
**Problema:** a fixture sobrescreve apenas `settings.MEDIA_ROOT`, e `MEDIA_ROOT` só é lido pelo `FileSystemStorage`. Quando `DJANGO_USE_S3=True` (`config/settings.py:151-157`), `STORAGES["default"]` é `storages.backends.s3.S3Storage` e a fixture vira no-op: o `SimpleUploadedFile` sobe para o bucket real. O docstring afirma o contrário ("Manda os uploads do teste para uma pasta descartável"), que é a pior forma de garantia falsa — a que ninguém reconfere. Mesmo defeito em `tests/test_api_pontos.py:54`. `ImageField` sem `storage=` resolve `default_storage` (`django/db/models/fields/files.py:251`), e `FileField.pre_save` chama `storage.save()` — o PUT acontece antes de qualquer asserção.
**Por que importa:** são os primeiros testes do repositório a fazer upload real (nenhum outro usa `SimpleUploadedFile`; `tests/test_models.py:81` só atribui string literal), então a exposição nasce aqui. Escrita em banco o pytest-django reverte pelo `test_*` database; **escrita em S3 não é revertida por nada**. Por rodada são 34 objetos: `eventos/cartaz-{0,1,2}.png`, `eventos/cartaz-{0..9}-{0..2}.png` e `pontos-de-interesse/capa.png`. E o agravante: `AWS_S3_FILE_OVERWRITE` não é definido em `config/settings.py`, e o default do django-storages é `True` (`storages/backends/s3.py:410`), com `get_available_name` devolvendo `get_available_overwrite_name` (`:702-707`) — **não há renomeação em colisão**. Se alguém já tiver subido pelo Admin uma capa chamada `capa.png`, a rodada de teste a substitui em silêncio por um PNG de 1×1. Isso deixa de ser poluição e vira perda de dado existente. O PRD §12.7 manda rodar `pytest` a cada commit, e o `README.md:296` documenta o comando puro, do host — a recorrência é prescrita. O CI escapa por coincidência de configuração (`ci.yml` não define `DJANGO_USE_S3`), não por proteção.
**Correção:** trocar o backend de storage, e não só o caminho — e fazer a guarda global, porque isolamento opt-in falha no próximo teste que esquecer a fixture. Criar `tests/conftest.py` (o PRD §12.6 proíbe mexer em `config/settings.py`), o que de quebra resolve o achado 4.1:

```python
"""Guardas globais da suíte.

O `.env` da máquina de desenvolvimento aponta para o Supabase real
(`DJANGO_USE_S3=True`). Sem esta guarda todo upload de teste vai para o bucket
`divulgacao` de produção — e com `AWS_S3_FILE_OVERWRITE` no default `True`,
sobrescreve o objeto de mesma chave, sem renomear e sem log.
"""
import pytest


@pytest.fixture(autouse=True)
def media_temporaria(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.STORAGES = {
        **settings.STORAGES,
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    }
    return tmp_path
```

O spread é obrigatório: `StorageHandler.backends` faz `settings.STORAGES.copy()` sem mesclar defaults (`django/core/files/storage/handler.py:18-33`), então substituir o dict inteiro derrubaria o alias `staticfiles`. O override funciona nesta versão (Django 5.2.16): `django/test/signals.py:114-132` tem o receiver `storages_changed`, que zera `storages._backends` e faz `default_storage._wrapped = empty`; como o `FileField` guarda a referência lazy, o próximo acesso reconstrói o backend. Com `autouse`, os parâmetros `media_temporaria` em `test_api_eventos.py:336,359` e `test_api_pontos.py:369` podem sair. `InMemoryStorage` (Django 4.2+) também serve e deriva a URL de `MEDIA_URL` igual — escolha de gosto.
**Verificação:** CONFIRMADO · conf 95
- [x] aprovar   - [ ] descartar

## 2. 🟡 Nocivo

### 2.1 "URL absoluta" é exigência do contrato e a asserção não a prova — `tests/test_api_eventos.py:356`
**Problema:** o teste valida a URL da imagem com `assert "/media/eventos/" in imagem["imagem"]`. Essa asserção passa igual com `http://testserver/media/eventos/cartaz-0.png` e com `/media/eventos/cartaz-0.png`. O único ponto do contrato que a linha deveria travar — que a URL é **absoluta** — é justamente o que ela deixa passar. Varredura em `tests/` por `testserver|build_absolute_uri|startswith|urlparse` não encontra nenhuma outra asserção que cubra isso: o teste de conjunto de chaves prova só o nome da chave, e a linha 355 só a extensão. É lacuna, não redundância.
**Por que importa:** a URL absoluta não é detalhe de implementação, é o que o Next.js consome direto no `<img src>`. Ela depende de o `request` estar no contexto do serializer — `FileField.to_representation` devolve URL relativa quando não está. Qualquer refactor que serialize fora da view (um `@action`, um comando de export, um serializer instanciado à mão) passa a devolver relativo, o CI continua verde, e o frontend renderiza imagem quebrada em produção, onde o domínio da API é diferente do domínio do site. O PRD §3.4 e o checklist do PR J dizem "com URL absoluta"; o README repete.
**Correção:** ancorar no prefixo absoluto. `MEDIA_URL` resolve para `/media/` em runtime (o `_add_script_prefix` do Django prefixa o `"media/"` literal de `config/settings.py:145`), e `http://testserver` é estável — `setup_test_environment()` injeta `testserver` em `ALLOWED_HOSTS` e o esquema é `http` sem `secure=True`. Substituir a linha 356 por:

```suggestion
        assert imagem["imagem"].startswith("http://testserver/media/eventos/")
```

Mantenha o `endswith(".png")` da linha 355: `upload_to="eventos/"` e, em colisão, `get_available_name` sufixa antes da extensão, então `.png` permanece.
**Verificação:** CONFIRMADO · conf 88
- [x] aprovar   - [ ] descartar

### 2.2 Mesma lacuna em `imagem_capa` — `tests/test_api_pontos.py:382`
**Problema:** `assert "/media/pontos-de-interesse/" in resposta_com["imagem_capa"]`. O teste `test_imagem_capa_ausente_vem_null_e_presente_vem_url` cobre bem a metade "ausente → `null`" (linha 380), mas a metade "presente → **URL absoluta**" fica com um `in` que passa com URL relativa. É o par exato do achado 2.1, herdado junto com a estrutura do arquivo — mesma varredura, mesmo resultado: nada em `tests/test_api_pontos.py` prova a URL absoluta.
**Por que importa:** mesma consequência do 2.1, num campo que o mapa usa no popup do marcador. O PRD §3.6 lista `imagem_capa` como "URL absoluta ou `null`" e o checklist do PR K repete. Hoje nada na suíte falharia se o valor virasse relativo, e é o frontend do mapa — construído em paralelo, contra este contrato — que descobriria em produção.
**Correção:** mesma âncora, com o prefixo deste `upload_to` (`rede/models/ponto_interesse.py:38`). Substituir a linha 382 por:

```suggestion
        assert resposta_com["imagem_capa"].startswith(
            "http://testserver/media/pontos-de-interesse/"
        )
```

Trate junto com o 2.1 — é o mesmo aprendizado em dois arquivos, e resolver os dois é uma linha cada.
**Verificação:** CONFIRMADO · conf 86
- [x] aprovar   - [ ] descartar

### 2.3 A emenda 10.5 (data-hora ISO 8601 com fuso) entra sem nenhuma asserção — `tests/test_api_eventos.py:106`
**Problema:** a suíte prova o *conjunto de chaves* da resposta, mas nunca olha o *valor* de `data_inicio`. Procurei o teste que travaria o formato e ele não existe: `test_ordenacao_padrao_e_cronologica` (linhas 271-286) e `test_intervalo_de_ate_inclui_os_dias_limite` (227-243) comparam `slugs()` (linha 90, que extrai só `item["slug"]`) — nenhum dos dois lê o valor de `data_inicio` do JSON. Nenhuma asserção compara `data_fim` com `None`, tampouco.
**Por que importa:** a emenda 10.5 é a única mudança que esta fatia faz na convenção de datas do projeto inteiro — o v4.1 §9.1 dizia "datas em ISO 8601 (AAAA-MM-DD)", e agora Evento devolve data-hora com offset. É contrato novo e sem rede: basta alguém acrescentar `"DATETIME_FORMAT": "%d/%m/%Y %H:%M"` ao `REST_FRAMEWORK` (mudança de uma linha, tentadora para acertar o Admin) para `data_inicio` virar `"15/08/2026 18:00"`, a suíte inteira continuar verde e o `new Date(...)` do Next.js retornar `Invalid Date` na agenda.
**Correção:** acrescentar asserção de valor em `test_detalhe_por_slug` ou num teste próprio. **Atenção:** a forma ingênua `== evento.data_inicio.isoformat()` **falha** — o `enforce_timezone` do `DateTimeField` converte para `TIME_ZONE` (`America/Sao_Paulo`) antes de serializar, enquanto `timezone.now()` da fixture guarda UTC (medido: DRF devolve `...-03:00`, `isoformat()` do objeto devolve `...+00:00`). A forma correta:

```python
from django.utils import timezone

dados = api.get(f"/api/eventos/{evento_completo.slug}/").json()
assert dados["data_inicio"] == timezone.localtime(evento_completo.data_inicio).isoformat()
assert dados["data_inicio"].endswith("-03:00")  # a emenda 10.5 é sobre o offset
```

Os microssegundos batem, então não é preciso truncar; `refresh_from_db()` não ajudaria, o driver devolve UTC igual. A metade "`data_fim` sai `null` quando ausente" é 🟣, não 🟡 (verifiquei que a chave sai presente com `None` e não há `to_representation` no `EventoSerializer` que a removesse) — cabe como uma linha `assert dados["data_fim"] is None` na mesma asserção, num evento sem fim.
**Verificação:** CONFIRMADO · conf 82
- [x] aprovar   - [ ] descartar

## 3. 🔵 Incongruência

<!-- Nenhum achado nesta faixa sobreviveu à verificação. Os dois candidatos foram
     refutados por contrariarem código prescrito literalmente no PRD desta fatia:

     - `rede/filters.py:55` — trocar `PROXIMOS/PASSADOS/TODOS` + `PERIODOS` por
       `models.TextChoices`. REFUTADO (conf 88): o PRD §7.2 (linha 338) autoriza
       explicitamente "as três opções como constantes/`TextChoices` locais do filtro",
       e o bloco de exemplo (:344-353) compara com string crua — o código entregue,
       que usa `self.PROXIMOS`, está acima do exemplo. Escolher uma de duas formas
       prescritas não é achado (invariantes §9). Sem bug, sem mudança de comportamento.
       Não há precedente de `TextChoices` em `FilterSet` nesta base; o paralelo com
       `PontoDeInteresseFilter` não vale, porque lá a fonte da verdade é o model.

     - `rede/serializers.py:194` — trocar a declaração explícita de `latitude`/`longitude`
       por `Meta.extra_kwargs`. REFUTADO (conf 85): o PRD §7.1 (linhas 308-314) traz o
       bloco de código byte a byte igual ao entregue, e §5.3 registra a decisão de fazer
       "campo a campo, e não pela chave global `COERCE_DECIMAL_TO_STRING`". A proposta
       até funciona (`max_digits`/`decimal_places` NÃO estão na lista que
       `include_extra_kwargs` esvazia sob `read_only` — rest_framework/serializers.py:1406),
       mas produz campo idêntico: mudança puramente cosmética contra decisão registrada.
-->

## 4. 🟣 Qualidade de código

### 4.1 Fixtures e constante de teste duplicadas, sem `tests/conftest.py` — `tests/test_api_pontos.py:42`
**Problema:** `PNG_MINIMO` (linhas 42-45) é caractere a caractere igual a `tests/test_api_eventos.py:44-47`, mas sem o comentário `#:` que lá explica a escolha. A fixture `api()` (48-50) tem **quatro** cópias no repositório: aqui, em `test_api_eventos.py:50`, em `test_api_coletivos.py:35` e em `test_slug_historico.py:15`. E `media_temporaria` (53-57) é igual a `test_api_eventos.py:55-63` **com o docstring encolhido**: lá está escrito o porquê ("sem isto, cada rodada sujaria a `media/` da árvore do repositório com PNGs de um pixel"), aqui sobrou só a mecânica. Não existe `conftest.py` em lugar nenhum do repositório.
**Por que importa:** são as duas formas de erosão que o padrão desta base combate. `PNG_MINIMO` duplicado é candidato clássico a divergir — alguém troca o PNG num arquivo e não no outro, e as duas suítes passam a testar coisas diferentes sem ninguém notar. E o docstring encolhido é literalmente o item "docstring que só descreve a mecânica" da taxonomia (invariante 8.2): quem herdar o projeto e ler primeiro este arquivo vai ver a fixture, não entender que ela existe para não sujar a árvore, e removê-la por parecer acessória. A quarta cópia de `api()` mostra que a duplicação já virou padrão do repositório — o momento de parar é agora, quando chega a quarta suíte de API.
**Correção:** criar `tests/conftest.py` com `api` e `media_temporaria` (com o docstring **completo**, o de eventos), e `tests/helpers.py` com `PNG_MINIMO` — `conftest.py` é lugar de fixture e hook, constante importa-se de um módulo (`tests/__init__.py` existe, então o import funciona). São movimentos mecânicos: o pytest resolve fixture por conftest sem mudar uma linha dos testes. Verificado que não há colisão de nome (`test_admin.py` define `admin_logado` e `registros`, não `api`) e que nenhum módulo importa `em`/`api` de outro arquivo de teste. **Se o achado 1.1 for aprovado, este vem junto de graça** — o `conftest.py` daquela correção é o mesmo arquivo, e `media_temporaria` já sai de lá com `autouse`. Deixe `coletivo_ativo` (78-95) como está, mesmo depois: unificá-la com `coletivo_completo` de `test_api_coletivos.py` acoplaria a regressão de LGPD à suíte do mapa.
**Verificação:** CONFIRMADO · conf 80
- [x] aprovar   - [ ] descartar

### 4.2 `horas=0` no helper `em()` é parâmetro que nenhum chamador passa — `tests/test_api_eventos.py:85`
**Problema:** `def em(dias, horas=0)`, com corpo `timezone.now() + timedelta(days=dias, hours=horas)`. São 18 chamadas no arquivo (linhas 142, 170, 173, 176, 184, 185, 197-200, 212, 213, 249, 262, 278-280, 293, 370) e **todas** passam um único argumento posicional. `grep` por `horas` em `tests/` e `rede/` só encontra as duas linhas do próprio helper. Nenhum módulo importa `em` de fora.
**Por que importa:** é o degrau 1 da escada YAGNI num helper de teste. O custo não é o parâmetro, é o sinal que ele emite: quem ler `em(dias, horas=0)` vai supor que existe um teste sensível a hora e ir procurá-lo. O teste que de fato depende de hora — `test_intervalo_de_ate_inclui_os_dias_limite`, linhas 227-243 — não usa `em()`: constrói `timezone.make_aware(datetime(2026, 8, 15, 19, 0))` à mão, e com razão, porque precisa de data absoluta e não relativa. O PRD §7 pede explicitamente que se evite sobre-engenharia.
**Correção:** tirar o parâmetro; com `horas` sempre 0 o valor produzido é idêntico para as 18 chamadas.

```suggestion
def em(dias):
    """Instante relativo a agora, consciente de fuso (`USE_TZ=True`)."""
    return timezone.now() + timedelta(days=dias)
```

Reintroduzir `horas` no dia em que existir um teste que o passe. Isolado este é o mais leve dos quatro 🟣 — vale anexá-lo ao mesmo comentário do 4.1 (é higiene do mesmo par de arquivos) em vez de gastar um thread dedicado.
**Verificação:** CONFIRMADO · conf 90
- [x] aprovar   - [ ] descartar

### 4.3 A asserção marcada `# título` passaria com `titulo` fora de `search_fields` — `tests/test_api_eventos.py:253`
**Problema:** `assert api.get("/api/eventos/?q=ARARIBOIA").json()["count"] == 1  # título`. No escopo do teste existem dois eventos: `evento_completo` (`titulo="Feira do Circuito Arariboia"`, `descricao="Feira mensal de agroecologia e artesanato."`, `local="Praça Arariboia"`) e o inline das linhas 248-251. O termo "ARARIBOIA" casa **dois campos do mesmo objeto** — título e local — então a busca acha o evento por qualquer um dos dois caminhos.
**Por que importa:** o comentário promete cobrir `titulo` e não cobre. Verificado por mutação: com `EventoViewSet.search_fields` reduzido a `["descricao", "local"]`, `q=ARARIBOIA` continua devolvendo `count 1` e a linha passa verde — remover `"titulo"` de `rede/views.py:103` não derruba nada na suíte. É o caso literal da invariante 7.3, agravado pelo comentário, que faz com que ninguém volte a olhar. As outras duas linhas do bloco são carga real: `q=cooperativismo` só casa `descricao` e `q=praça` só casa `local`.
**Correção:** usar um termo exclusivo do título. "circuito" aparece só em `titulo="Feira do Circuito Arariboia"` — a descrição fala de agroecologia e artesanato, o local é "Praça Arariboia". Medido: com `titulo` em `search_fields`, `q=circuito` → `count 1`; sem, → `count 0`, ou seja, mata exatamente a mutação.

```suggestion
    assert api.get("/api/eventos/?q=circuito").json()["count"] == 1  # título
```
**Verificação:** CONFIRMADO · conf 97
- [x] aprovar   - [ ] descartar

### 4.4 Mesma asserção frouxa, agora marcada `# nome` — `tests/test_api_pontos.py:308`
**Problema:** `assert api.get(f"{base}ARARIBOIA").json()["count"] == 1  # nome`. Mesmo defeito de desenho de fixture do 4.3: `ponto_completo` tem `nome="Feira da Praça Arariboia"` e `endereco="Praça Arariboia, Centro, Niterói"` — "Arariboia" em dois campos do mesmo registro. O outro ponto no escopo é a "Casa Paul Singer" (`endereco="Rua Visconde de Sepetiba, Centro"`).
**Por que importa:** idem — é a única das quatro linhas do bloco que não cobre nada sozinha. Verificado por mutação: com `search_fields` reduzido a `["descricao", "endereco"]`, `q=ARARIBOIA` segue em `count 1` e a asserção passa; tirar `"nome"` de `rede/views.py:133` não deixa rastro vermelho. `q=referência` e `q=sepetiba` (linhas 309-310) estão corretas.
**Correção:** buscar por termo exclusivo do nome do outro ponto. Confirmado que "singer" não aparece no endereço nem na descrição da Casa Paul Singer; medido: com `nome`, `q=singer` → `count 1`; sem, → `count 0`.

```suggestion
    assert api.get(f"{base}singer").json()["count"] == 1  # nome
```

**Não reaproveite `q=circuito` aqui:** em pontos, "circuito" está na *descrição* do `ponto_completo` ("Feira semanal do circuito."), não no nome — casaria pelos dois lados e reproduziria o mesmo furo. O discriminante de `nome` neste arquivo é `singer`, e só ele.
**Verificação:** CONFIRMADO · conf 97
- [x] aprovar   - [ ] descartar

## Apêndice A — achados de LGPD apresentados mesmo tendo sido refutados

A skill proíbe descartar em silêncio qualquer achado de exposição de dado pessoal. A passada determinística do `review.py` levantou dois candidatos 🔴 nesta categoria; **ambos foram refutados por leitura do código e do PRD**, e ficam registrados aqui com os dois veredictos para que a decisão seja sua, não minha.

**A.1 — `rede/serializers.py:142` — `data_inicio` em serializer público**
- *Veredicto do driver (determinístico):* 🔴 campo não público exposto. `data_inicio` consta na lista da invariante 1.6.
- *Veredicto da revisão:* **REFUTADO.** O `data_inicio` proibido é o do **Coletivo** — a data de fundação, dado cadastral. Este é o do **Evento**: a data-hora em que o evento acontece, que o PRD §3.4 lista como campo público obrigatório e o README documenta. O driver casou pelo nome do campo, sem distinguir o model. O `Coletivo` não expõe `data_inicio` em lugar nenhum (`ColetivoSerializer.Meta.fields`, linhas 66-83, segue intacto).

**A.2 — `rede/serializers.py:246` — omissão de contato virando `null`**
- *Veredicto do driver (determinístico):* 🔴 a representação atribui `None` a uma chave em vez de removê-la (invariante 1.5).
- *Veredicto da revisão:* **REFUTADO.** A regra do `dados.pop` vale para os **contatos do Coletivo**, onde `null` comunicaria "existe um telefone, mas foi escondido". Aqui é a guarda do coletivo vinculado, e o PRD §4.3 e a emenda §10.4 mandam **exatamente** o contrário: `coletivo` vale `null`, indistinguível de "este ponto não tem coletivo", porque a maioria dos pontos não tem vínculo e omitir a chave é que denunciaria o caso oculto. O raciocínio está registrado no docstring de `to_representation` (linhas 226-243). A guarda foi auditada à parte e fecha: não há `?coletivo=` no filtro, `coletivo` não está em `search_fields` nem em `ordering_fields`.

## Apêndice B — incidente de execução durante esta revisão

Registro honesto do que a própria revisão causou, porque exige ação da equipe.

Dois agentes auditores rodaram `pytest` na árvore antes que a restrição de execução fosse imposta. O `.env` local tem `DJANGO_USE_S3=True` e aponta para o Supabase de produção, então — pelo mecanismo do achado 1.1 — **essas rodadas gravaram PNGs de teste no bucket `divulgacao` de produção**, nas chaves `eventos/cartaz-{0,1,2}.png`, `eventos/cartaz-{0..9}-{0..2}.png` e `pontos-de-interesse/capa.png`. Com `AWS_S3_FILE_OVERWRITE` no default `True`, qualquer objeto pré-existente nessas chaves foi substituído sem renomear e sem log.

Também ficou um banco `test_postgres` órfão na instância do Supabase (o teardown falhou com "is being accessed by other users").

A verificar, nesta ordem: (1) se o bucket `divulgacao` tem versionamento ligado — se tiver, os originais são recuperáveis; (2) se alguma linha de `PontoDeInteresse.imagem_capa` ou `ImagemEvento.imagem` aponta para uma dessas chaves, caso em que a imagem virou o PNG de 1×1; (3) derrubar o `test_postgres` órfão. Nada foi apagado do bucket — a limpeza é decisão da equipe.

Vale também um PR próprio, **fora do escopo desta fatia**, para o risco pré-existente que isto expôs: `pytest` rodado do host lê o `.env` de produção e cria/derruba banco no Supabase. O `infra/docker-compose.yml` já resolveu isso para o `runserver` via `DJANGO_IGNORE_DOTENV`; o `pytest` não tem equivalente.
