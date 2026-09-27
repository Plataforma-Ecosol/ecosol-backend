# PRD de Implementação — Endpoint público de Coletivos + Regressão de LGPD

**Projeto:** Plataforma de Rede da Economia Solidária de Niterói
**Centro Público de Referência em Economia Solidária (Casa Paul Singer) · ITES / IFRJ Campus Niterói**

| | |
|---|---|
| **Documento** | PRD de Implementação — Fatia 2: Endpoint de Coletivos |
| **Versão** | 1.0 |
| **Deriva de** | PRD Técnico v4.1 (Seções 6 e 9; Seção 11, **item 2**) e PRD de Implementação — Backend v1.1 (PRs 5 e 6) |
| **Escopo** | Serializer público do Coletivo + endpoint `GET /api/coletivos/` e detalhe por slug + busca, filtros, ordenação e paginação + estabilidade de links (histórico de slugs) + teste de regressão de LGPD |
| **Fora de escopo** | Django Admin, endpoints de Eventos e Pontos de Interesse, qualquer rota de escrita, frontend Next.js (fatias seguintes) |
| **Repositório** | `apps/ecosol-backend` (dentro da umbrella `ecosol-fullstack`) |
| **Status** | Pronto para desenvolvimento — a ser executado via Claude Code |

---

## 0. Objetivo deste documento

Este PRD detalha **como** executar o **item 2 da Seção 11 do PRD Técnico v4.1**:

> *"Implementar o endpoint de Coletivos conforme o contrato da Seção 9, com o teste de regressão de LGPD."*

No mapa de PRs do PRD de Implementação Backend v1.1, isso corresponde a **PR 5 (serializer + endpoint de coletivos)** e **PR 6 (regressão LGPD + núcleo, em PR próprio)**. A fatia anterior — conexão ao Supabase e models — **já está concluída** no repositório.

Este é o **primeiro endpoint público do projeto** e o PRD Técnico o define explicitamente como **modelo para os demais** (Eventos e Pontos de Interesse). O padrão criado aqui — serializer explícito, omissão por consentimento, paginação, filtros, anti-N+1 e suíte de regressão — será copiado. Vale, portanto, mais cuidado do que o tamanho do endpoint sugere.

O documento é autossuficiente para ser lido por um agente (Claude Code) e transformado em código, sem reabrir os PRDs anteriores. Ele **não contradiz** nenhuma decisão validada; registra na Seção 10 duas **emendas** que precisam voltar ao PRD Técnico v4.1.

**Decisão de escopo desta fatia (validada):** inclui o **histórico de slugs** (Seção 5) como parte do PR, e não como melhoria posterior. O motivo é de sequência: o slug passa a ser a chave pública das URLs neste PR, e o frontend da fase 2 vai publicar esses links. Entregar a rota sem estabilidade de link significaria publicar endereços sob risco desde o primeiro dia.

---

## 1. Estado atual do repositório (ponto de partida)

O que **já existe** e **não deve ser refeito** (confirmado no código):

- **`config/settings.py`** — DRF já configurado e pronto para esta fatia:
  - `REST_FRAMEWORK` com `DjangoFilterBackend`, `SearchFilter` e `OrderingFilter` já em `DEFAULT_FILTER_BACKENDS`.
  - `PageNumberPagination` como paginação padrão, com `PAGE_SIZE = 20`.
  - `DEFAULT_PERMISSION_CLASSES = ["rest_framework.permissions.IsAuthenticatedOrReadOnly"]`.
  - `AUTH_USER_MODEL = "rede.Usuario"`, lógica de duas conexões (pooler/direta) e bloco de Storage. **Não reescrever.**
- **`rede/models/`** — pacote com `Usuario`, `Categoria`, `Coletivo`, `Pessoa`, `Evento`, `ImagemEvento`, `PontoDeInteresse`, reexportados no `__init__.py`. No `Coletivo` já existem `slug` (único), `bairro` (indexado), `ativo` (indexado, default `True`), os três contatos e as três flags `exibir_*_publicamente` (default `False`), o M2M `categorias` e os metadados.
- **`rede/migrations/`** — `0001` a `0003` aplicadas.
- **`tests/test_models.py`** — núcleo de testes de models (fatia anterior) e `tests/test_smoke.py` (healthcheck).
- **`config/urls.py`** — apenas `admin/` e `health/`, com o comentário-âncora: *"As rotas da API pública (/api/coletivos/) entram no PR 5"*.
- **CI** (`.github/workflows/ci.yml`) rodando `ruff` → `makemigrations --check --dry-run` → `pytest`, com `main` e `staging` protegidas.

O que **não existe ainda** e nasce nesta fatia: `rede/serializers.py`, `rede/filters.py`, `rede/pagination.py`, `rede/views.py`, `rede/urls.py` e a suíte de API.

> **Princípio-guia:** esta fatia **abre a primeira porta pública do sistema**. Toda decisão aqui é sobre o que sai — e o que nunca sai. `rede/admin.py` permanece vazio de propósito (Django Admin é a fatia seguinte).

---

## 2. Resultado esperado (Definition of Done da fatia)

A fatia está concluída quando **todos** os itens abaixo forem verdadeiros:

1. `GET /api/coletivos/` responde `200` com o envelope de paginação do DRF, listando **apenas coletivos ativos**.
2. `GET /api/coletivos/{slug}/` responde `200` para o slug atual e `404` para coletivo inativo ou inexistente.
3. Um **slug antigo** de coletivo visível responde `301` com `Location` apontando para a URL canônica.
4. Busca (`q`), filtros (`categoria`, `bairro`), ordenação (`ordering`) e paginação (`page`, `page_size`, teto 100) funcionam conforme a Seção 3.
5. O serializer declara campos **explicitamente**; contatos sem consentimento têm a **chave omitida** da resposta.
6. Nenhum dado de Pessoa, endereço, dado cadastral ou flag de consentimento aparece na API pública.
7. O **teste de regressão de LGPD** passa e é **bloqueante no CI**.
8. A listagem responde **sem N+1** — provado por teste de contagem de queries, não por inspeção visual.
9. `ruff` passa, `makemigrations --check --dry-run` fica limpo e o CI fica **verde**.
10. O `README.md` do backend ganha a seção **"API pública"** documentando rotas, parâmetros e as duas regras de exposição (omissão por consentimento e `301` de slug antigo).

> A migration desta fatia (`0004`, do histórico de slugs) é validada contra o **Postgres local do docker-compose**. A aplicação no Supabase é passo manual posterior, conforme `docs/alteração_models.md` — **não** faz parte do PR.

---

## 3. Contrato da API pública

Implementa a Seção 9 do PRD Técnico v4.1 e a Seção 6 do PRD Backend v1.1.

### 3.1. Convenções

- Chaves em `snake_case`; datas em ISO 8601.
- Respostas de lista usam o envelope do DRF: `count`, `next`, `previous`, `results`.
- Paginação: `page_size` padrão **20**, máximo **100**.
- Todo endpoint público é **somente leitura** (`GET`) e `AllowAny`.

### 3.2. Endpoints

| Método e path | Descrição | Permissão |
|---|---|---|
| `GET /api/coletivos/` | Lista paginada de coletivos **ativos** | Público (`AllowAny`) |
| `GET /api/coletivos/{slug}/` | Detalhe de um coletivo, buscado por `slug` | Público (`AllowAny`) |

> O detalhe usa `slug` como `lookup_field` (ex.: `/api/coletivos/sementes-do-vale/`), casando com as URLs do frontend. O `id` continua sendo detalhe interno do banco, sem rota própria. Ver emenda **10.1**.

### 3.3. Parâmetros de consulta (listagem)

| Parâmetro | Tipo | Comportamento | Obrigatório |
|---|---|---|---|
| `q` | string | Busca textual case-insensitive em `nome` e `descricao` | Não |
| `categoria` | int | Filtra pelo id de uma Categoria (M2M). Valor não numérico → `400` | Não |
| `bairro` | string | Filtra por bairro (`iexact`) — valor público, nunca logradouro | Não |
| `ordering` | string | `nome`, `-nome`, `criado_em`, `-criado_em`. Padrão: `nome` | Não |
| `page` | int | Número da página (default 1) | Não |
| `page_size` | int | Itens por página (default 20, máx 100) | Não |

> **`ativo` não é parâmetro exposto.** Ver emenda **10.2**.

### 3.4. Campos da resposta (Coletivo)

Exatamente estes, nesta ordem:

| Grupo | Campos |
|---|---|
| Institucionais | `id`, `nome`, `slug`, `descricao`, `bairro`, `site` |
| Relacionamento | `categorias` — lista de objetos `{id, nome, slug}` |
| Datas | `criado_em`, `atualizado_em` |
| Contatos condicionais | `telefone`, `email`, `instagram` — **a chave só existe com consentimento** |

### 3.5. Erros

| Código | Quando ocorre |
|---|---|
| `301` | Slug antigo de um coletivo visível → `Location` com a URL canônica |
| `400` | Tipo inválido em parâmetro (ex.: `categoria=texto` onde se espera número) |
| `404` | Slug inexistente, coletivo inativo, ou página fora da faixa (nativo do DRF) |

---

## 4. Blindagem de LGPD na serialização

O cadastro reúne dados pessoais e sensíveis. Esta é a fatia em que a promessa de privacidade do projeto **deixa de ser modelagem e vira comportamento observável**. As regras abaixo são requisito, não recomendação.

### 4.1. Blindagem na origem

Campos sensíveis **não são sequer declarados** no serializer público — é mais seguro do que filtrar em tempo de execução, pois um refactor futuro não reintroduz vazamento por acidente. Serializers usam sempre lista explícita de campos; **nunca** `fields = "__all__"`, e **nunca** `exclude` (que é uma lista negra: o campo novo entra sozinho).

### 4.2. O que nunca sai

| Categoria | Campos |
|---|---|
| Pessoa | **Tudo**, por qualquer caminho — nem nome, nem contagem, nem relação aninhada |
| Endereço do coletivo | `logradouro`, `numero`, `complemento`, `cep` |
| Dados cadastrais | `cnpj`, `data_inicio`, `responsavel_grupo`, `motivo_criacao`, `renda_obtida`, `historico_editais` |
| Controle e metadados | `ativo`, `situacao`, `nome_entrevistador`, `observacoes` |
| Flags de consentimento | `exibir_telefone_publicamente`, `exibir_email_publicamente`, `exibir_instagram_publicamente` |

`bairro` é o **único** dado geográfico público: dá contexto sem revelar a sede, que pode ser a casa de alguém.

### 4.3. Contatos por consentimento (omissão de chave)

`telefone`, `email` e `instagram` só entram na resposta se a flag correspondente for `True`. Sem consentimento, **a chave é removida do JSON** — não retorna `null`, não retorna string vazia.

> **Por que omitir em vez de `null`:** retornar `null` ainda comunicaria *"existe um dado aqui, mas foi escondido"*. Omitir a chave é a aplicação prática da minimização de dados: o consumidor da API não recebe sequer o indício de que há um dado. No frontend isso vira `telefone?: string`, e não `string | null`.

Implementação: `to_representation` no serializer do Coletivo, removendo as chaves sem consentimento após a serialização base. O mapa contato→flag deve ser uma **constante da classe**, para que quem adicionar um contato novo amanhã veja onde declarar o consentimento.

---

## 5. Identidade pública e estabilidade de links (histórico de slugs)

Com o detalhe servido por slug, o slug passa a ser a **identidade pública** do coletivo — o que vai no cartaz, no WhatsApp e no índice do buscador. Um slug corrigido no back-office não pode transformar links publicados em `404`.

### 5.1. Decisão

Guardar o **histórico de slugs** de cada coletivo e responder **`301 Moved Permanently`** quando um slug antigo for requisitado.

**Alternativas consideradas e descartadas:**

| Alternativa | Por que não |
|---|---|
| Tornar o slug imutável após a criação | Impede corrigir erro de digitação sem intervenção técnica; empurra o custo para a equipe do Centro Público |
| Aceitar `id` **ou** slug na mesma rota | Duas identidades para o mesmo recurso — ambiguidade que quem herdar o projeto teria que decifrar, contra o requisito de compreensibilidade do v4.1 |
| Deixar quebrar | Contradiz o objetivo de descoberta/SEO da Seção 7 do v4.1: o link publicado é o principal ativo de visibilidade dos coletivos |

O `301` é o que fecha o ciclo de SEO: o buscador **consolida** a autoridade do endereço antigo no novo, em vez de indexar duplicata. O `fetch` do Next.js segue redirect por padrão, então a página de perfil continua renderizando; comparando o `slug` do payload com o da URL, o frontend emite o próprio `301` na fase 2.

### 5.2. Model `ColetivoSlugAnterior`

Novo model em `rede/models/coletivo.py`, ao lado do `Coletivo`:

| Campo | Tipo | Regras |
|---|---|---|
| `coletivo` | `ForeignKey(Coletivo, on_delete=CASCADE, related_name="slugs_anteriores")` | apagar o coletivo limpa seu histórico |
| `slug` | `SlugField(max_length=220, unique=True)` | **único** — um slug jamais aponta para dois lugares |
| `criado_em` | `DateTimeField(auto_now_add=True)` | auto |

`Meta.ordering = ["-criado_em"]`. `__str__` retorna `f"{self.slug} → {self.coletivo.slug}"`.

### 5.3. Registro automático no `save()`

O administrador edita o slug no Admin normalmente e **não precisa saber que isso existe**. O `Coletivo.save()` compara o slug em banco com o novo e registra a diferença:

```python
    def save(self, *args, **kwargs):
        slug_antigo = (
            Coletivo.objects.filter(pk=self.pk).values_list("slug", flat=True).first()
            if self.pk
            else None
        )
        with transaction.atomic():
            # O slug atual sempre vence o histórico: se este slug já foi de
            # alguém (inclusive deste mesmo coletivo, num vaivém a→b→a), a
            # entrada antiga sai para não haver dois donos do mesmo slug.
            ColetivoSlugAnterior.objects.filter(slug=self.slug).delete()
            super().save(*args, **kwargs)
            if slug_antigo and slug_antigo != self.slug:
                ColetivoSlugAnterior.objects.update_or_create(
                    slug=slug_antigo, defaults={"coletivo": self},
                )
```

O `delete()` antes do `save()` combinado com `unique=True` é o que garante a invariante da 5.2, inclusive no caso de vaivém (`a` → `b` → `a`), em que o histórico de `a` se limpa sozinho.

### 5.4. Comportamento resultante

| Requisição | Resposta |
|---|---|
| Slug atual | `200` |
| Slug antigo, coletivo ativo | `301` + `Location` para o slug canônico |
| Slug antigo, coletivo **inativo** ou apagado | `404` — o histórico **não fura** a regra de visibilidade |
| Slug nunca usado | `404` |

---

## 6. Ordem de execução (sequência de PRs)

Continua a numeração da fatia anterior (que terminou no PR C). Executar **nesta ordem**:

| # | Branch | Conteúdo | Bloqueia? |
|---|---|---|---|
| **D** | `feat/historico-slug-coletivo` | Model `ColetivoSlugAnterior` + `save()` do Coletivo + migration `0004` + teste de model do histórico | Sim — o endpoint depende dele |
| **E** | `feat/endpoint-coletivos` | Serializer, paginação, filtros, ViewSet (com o `301`), rotas e seção "API pública" no README | Depende de D |
| **F** | `test/regressao-lgpd` | Suíte de regressão de LGPD e de contrato (Seção 8), bloqueante no CI | Depende de E |

> **Por que a regressão de LGPD é PR próprio:** é a decisão já tomada no PRD Backend v1.1 (PR 6). Separar dá ao revisor um PR pequeno, em que a única pergunta é *"este teste realmente prova a promessa?"* — sem competir com a atenção gasta em revisar implementação.

Cada PR sai de `staging`, segue Conventional Commits em português e vai a revisão. `main` e `staging` permanecem protegidas.

---

## 7. Implementação

Um único app de domínio `rede`, com arquivos organizados por assunto (Seção 4.8 do PRD Backend v1.1).

### 7.1. `rede/serializers.py` (novo)

- `CategoriaResumoSerializer` — `ModelSerializer` de `Categoria`, `fields = ["id", "nome", "slug"]`.
- `ColetivoSerializer` — `ModelSerializer` de `Coletivo`, campos explícitos na ordem da Seção 3.4, com `categorias = CategoriaResumoSerializer(many=True, read_only=True)`.
- Constante de classe com o mapa contato→flag e `to_representation` aplicando a omissão da Seção 4.3.
- Docstring de módulo registrando que **este é o ponto onde a promessa de privacidade é cumprida**.

### 7.2. `rede/pagination.py` (novo)

`PaginacaoPadrao(PageNumberPagination)` com `page_size = 20`, `page_size_query_param = "page_size"` e `max_page_size = 100`. Registrar como `DEFAULT_PAGINATION_CLASS` em `config/settings.py`, substituindo a classe padrão do DRF.

> **Global, não por view:** o contrato de paginação é do projeto inteiro (Seção 9.1 do v4.1). Eventos e Pontos de Interesse herdam o mesmo comportamento sem repetir código — e sem risco de divergirem.

### 7.3. `rede/filters.py` (novo)

`ColetivoFilter(FilterSet)`:

- `categoria = NumberFilter(field_name="categorias__id")` — é o `NumberFilter` que produz o `400` do contrato quando vem texto.
- `bairro = CharFilter(lookup_expr="iexact")`.
- **Não declarar `ativo`** (emenda 10.2).

A busca `q` não é filtro próprio: usa o `SearchFilter` do DRF com `search_fields = ["nome", "descricao"]`, acrescentando `"SEARCH_PARAM": "q"` ao `REST_FRAMEWORK` em `config/settings.py` (o padrão do DRF seria `search`).

### 7.4. `rede/views.py` (novo)

`ColetivoViewSet(ReadOnlyModelViewSet)`:

| Atributo | Valor | Motivo |
|---|---|---|
| `permission_classes` | `[AllowAny]` | Explícito, mesmo o padrão global já permitindo leitura — um endpoint público deve **declarar** que é público |
| `lookup_field` | `"slug"` | Seção 3.2 |
| `queryset` | `Coletivo.objects.filter(ativo=True).prefetch_related("categorias")` | `ativo=True` fixo (emenda 10.2); `prefetch_related` evita o N+1 nas categorias |
| `serializer_class` | `ColetivoSerializer` | |
| `filterset_class` | `ColetivoFilter` | |
| `search_fields` | `["nome", "descricao"]` | |
| `ordering_fields` | `["nome", "criado_em"]` | Seção 3.3 |
| `ordering` | `["nome"]` | Padrão |

O `retrieve()` é sobrescrito para o `301` da Seção 5.4 — resolvendo o histórico **antes** de deixar o DRF levantar `404`, e sempre validando que o coletivo de destino continua visível.

### 7.5. Rotas

`rede/urls.py` (novo) com `DefaultRouter` registrando `ColetivoViewSet` em `coletivos`, `basename="coletivo"`. Em `config/urls.py`, acrescentar `path("api/", include("rede.urls"))`, mantendo `admin/` e `health/`.

### 7.6. O que não tocar

`config/settings.py` recebe **apenas** três alterações: `DEFAULT_PAGINATION_CLASS`, `SEARCH_PARAM` e a remoção do `PAGE_SIZE` agora redundante. Nenhuma dependência nova — tudo já está em `requirements.txt`. `rede/admin.py` continua vazio.

---

## 8. Testes desta fatia (PR F)

`pytest` + `pytest-django`, com nomes e docstrings em português, no estilo de `tests/test_models.py`.

### 8.1. Regressão de LGPD — `tests/test_api_coletivos.py`

Implementa a Seção 7.1 do PRD Backend v1.1 e a Seção 6.3 do v4.1:

1. `test_contatos_sem_consentimento_sao_omitidos` — contatos preenchidos, três flags em `False`: nenhuma das chaves existe. Asserção com `not in`, **nunca** com `is None`.
2. `test_contatos_com_consentimento_aparecem` — flags em `True`: as três chaves existem, com os valores corretos.
3. `test_consentimento_e_por_campo` — só `exibir_email_publicamente=True`: `email` presente, `telefone` e `instagram` ausentes.
4. `test_resposta_tem_exatamente_as_chaves_do_contrato` — compara `set(resposta.keys())` com o conjunto exato da Seção 3.4.
5. `test_endereco_e_dados_cadastrais_nunca_aparecem` — coletivo com `logradouro`, `cep`, `cnpj`, `renda_obtida`, `observacoes` e `situacao` preenchidos: cada chave ausente, na listagem **e** no detalhe.
6. `test_nenhum_dado_de_pessoa_aparece` — Pessoa com nome e CPF vinculada ao coletivo: nem nome nem CPF aparecem em `response.content`.
7. `test_flags_de_consentimento_nao_sao_expostas` — nenhuma chave `exibir_*_publicamente`.

> **O teste 4 é o mais importante do arquivo.** Os demais são listas negras: pegam o vazamento que alguém previu. Comparar o conjunto de chaves é lista branca — pega **o campo que ninguém previu**, incluído por acidente daqui a seis meses. Deve levar comentário explicando isso, para que ninguém "conserte" o teste afrouxando a asserção.

### 8.2. Contrato e comportamento — mesmo arquivo

8. Listagem responde `200` com o envelope `count/next/previous/results`.
9. Coletivo `ativo=False` não aparece na listagem e seu detalhe responde `404`.
10. `q` encontra por trecho do nome e da descrição, ignorando maiúsculas.
11. `categoria=<id>` filtra corretamente; `categoria=texto` responde `400`.
12. `bairro` filtra ignorando maiúsculas/minúsculas.
13. `ordering=-nome` inverte; sem parâmetro, ordena por `nome`.
14. `page_size=1` pagina; `page_size=500` é limitado a 100; `page=999` responde `404`.
15. Detalhe por slug responde `200` com o slug pedido.
16. **Anti-N+1:** listagem com N coletivos e categorias executa número **constante** de queries (`django_assert_num_queries`).

> O item 16 é o que transforma o requisito de desempenho da Seção 7 do v4.1 em garantia. Sem ele, "sem N+1" é promessa que se perde no primeiro refactor.

### 8.3. Histórico de slugs — `tests/test_slug_historico.py`

17. Trocar o slug cria a entrada com o slug antigo.
18. Requisição ao slug antigo responde `301`, com `Location` na URL canônica.
19. Seguir o redirect chega ao coletivo certo com `200`.
20. Slug antigo de coletivo **inativo** responde `404`.
21. Vaivém `a` → `b` → `a`: histórico de `a` limpo, `/api/coletivos/a/` volta a responder `200` sem redirect.
22. Slug nunca usado responde `404`.
23. Criar coletivo não cria histórico; salvar sem mudar o slug também não.

### 8.4. O que NÃO testar aqui

Django Admin, endpoints de Eventos e Pontos de Interesse, upload de imagem e frontend — fatias seguintes. Não antecipar.

### 8.5. CI

O CI existente (`ruff` → `makemigrations --check --dry-run` → `pytest`, em Postgres do runner) já cobre esta suíte sem alteração. A regressão de LGPD é **bloqueante**: PR com teste quebrado não entra em `main` nem em `staging`.

---

## 9. Desempenho

Requisito do v4.1 (Seção 7): listagens abaixo de **500 ms**.

- **Paginação** com teto de 100 itens — já no contrato.
- **Índices** já existentes em `slug` (único), `bairro` e `ativo`; a ordenação padrão é por `nome`.
- **Anti-N+1** com `prefetch_related("categorias")`, verificado pelo teste 8.2.16.
- `select_related` não se aplica: o serializer público não atravessa nenhuma FK.

> Sem sobre-engenharia: nada de cache, índice composto ou desnormalização nesta fatia. A escala real da ES de Niterói não pede — e o v4.1 pede explicitamente que não se antecipe volume que não existe.

---

## 10. Emendas ao PRD Técnico v4.1

Duas divergências conscientes em relação à Seção 9.2 do v4.1. Ambas devem ser **registradas no corpo do PR** e levadas ao documento na próxima revisão.

### 10.1. Detalhe por `slug`, não por `id`

O v4.1 (Seção 9.2) escreve `GET /api/coletivos/{id}/`. Adota-se `GET /api/coletivos/{slug}/`.

**Motivo:** a própria Seção 7 do v4.1 exige URLs públicas por slug para descoberta e SEO, e o slug já é campo único e indexado, criado exatamente para isso. Servir o detalhe por `id` obrigaria o frontend a duas chamadas para abrir um perfil, ou a manter uma rota paralela — duas identidades públicas para o mesmo recurso.

**Observação:** o PRD de Implementação Backend v1.1 (Seção 6.2) **já especifica o detalhe por slug**. A emenda, portanto, apenas alinha o v4.1 ao que a camada de implementação já havia validado.

### 10.2. `ativo` deixa de ser parâmetro de consulta

O v4.1 lista `ativo` como parâmetro de listagem, com default `true`. Ele **não será exposto**: o queryset público fixa `ativo=True`.

**Motivo:** `ativo` é a chave de visibilidade pública — o mecanismo com que a equipe do Centro Público tira um coletivo do ar. Aceitá-lo como parâmetro permitiria a qualquer pessoa listar exatamente os coletivos que a equipe decidiu não exibir, o que contradiz a Seção 3 ("a API pública expõe somente leitura do que é público") e a Seção 7 ("segurança de endpoints"). Um parâmetro que o cliente não pode usar para nada é ruído no contrato; melhor removê-lo do que documentar uma opção falsa.

---

## 11. Checklist de aceite (para marcar no PR)

- [ ] `ColetivoSlugAnterior` criado, com `slug` único e `save()` do Coletivo registrando a troca.
- [ ] Migration `0004` gerada, contendo apenas `CreateModel`, aplicada no Postgres local.
- [ ] `makemigrations --check --dry-run` limpo.
- [ ] Serializer com campos explícitos; sem `__all__` e sem `exclude`.
- [ ] Contatos sem consentimento têm a **chave omitida** (não `null`).
- [ ] Nenhum dado de Pessoa, endereço, dado cadastral ou flag de consentimento na resposta.
- [ ] `GET /api/coletivos/` com `q`, `categoria`, `bairro`, `ordering`, `page`, `page_size` conforme a Seção 3.
- [ ] `categoria=texto` → `400`; `page=999` → `404`.
- [ ] Detalhe por slug → `200`; inativo/inexistente → `404`; slug antigo de coletivo visível → `301`.
- [ ] Paginação registrada globalmente, com teto de 100.
- [ ] Teste anti-N+1 com contagem constante de queries.
- [ ] Suíte de regressão de LGPD passando e bloqueante no CI.
- [ ] `README.md` do backend com a seção "API pública".
- [ ] Emendas 10.1 e 10.2 registradas no corpo do PR.
- [ ] `ruff` verde; CI verde; Conventional Commits; PR revisado para `staging`.

---

## 12. Instruções para o Claude Code (como executar)

1. Trabalhar **dentro de `apps/ecosol-backend`** (é o repositório Git independente).
2. **Antes de tudo**, rodar `git status`: se houver alterações não commitadas na árvore, **parar e avisar** — não commitar trabalho alheio junto, não usar `stash` sem perguntar.
3. Ler `rede/models/coletivo.py`, `rede/models/categoria.py`, `rede/models/pessoa.py`, `config/settings.py`, `config/urls.py` e `tests/test_models.py` **antes** de escrever código. O código existente é a referência de estilo.
4. Seguir a ordem de PRs da Seção 6 (Histórico → Endpoint → Testes). Um PR por branch, saindo de `staging`.
5. **Não** reescrever `config/settings.py` além das três alterações da Seção 7.6. Nenhuma dependência nova.
6. Gerar a migration com `makemigrations rede`. Validar com `docker compose run --rm backend python manage.py migrate` a partir de `infra/` — **nunca** aplicar no Supabase por conta própria; ao final, informar o comando para aplicação manual (`docs/alteração_models.md`).
7. Rodar `ruff check .`, `makemigrations --check --dry-run` e `pytest` a cada commit; só seguir com tudo verde.
8. Registrar no corpo dos PRs as emendas da Seção 10 e a evidência de CI verde.
9. Manter tudo em português (docstrings, comentários, mensagens de commit, descrição de PR) — requisito de Tecnologia Social do projeto.
10. Diante de qualquer ambiguidade de contrato de API ou de exposição de dado que este documento não resolva: **parar e perguntar**. Em hipótese alguma adicionar um campo à resposta pública por conta própria.

---

*Fatia derivada da Seção 11, item 2 do PRD Técnico v4.1 e dos PRs 5–6 do PRD de Implementação Backend v1.1. Registra duas emendas ao v4.1 (Seção 10) e nenhuma alteração de arquitetura. As fatias seguintes: Django Admin (área administrativa), replicação do padrão de endpoint para Eventos e Pontos de Interesse, e frontend Next.js.*
