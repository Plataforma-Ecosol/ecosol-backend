# Invariantes do ecosol-backend

As regras deste repositório, com a citação normativa de cada uma. Todo auditor
`review-*` recebe este arquivo. Uma violação aqui **não é opinião** — é
divergência de contrato escrito, e o comentário cita a fonte.

Fontes: `docs/PRD/PRD_Tecnico_Ecosol_Niteroi_v4.1.md` (referido como "PRD §x"),
`docs/PRD/PRD_Implementacao_Django_Admin_v1.md`, o `README.md` do backend e os
docstrings dos próprios módulos — que neste projeto carregam a norma.

Os PRDs ficam na pasta umbrella (`../../docs/PRD/`), **fora** deste repositório
Git. Se estiverem inacessíveis na sessão, diga que a conferência foi parcial em
vez de supor a regra.

---

## 1. LGPD e blindagem do serializer — 🔴

O cadastro reúne CPF, RG, cor/raça, identidade de gênero, orientação sexual,
deficiência e renda familiar de pessoas reais da rede de Niterói. Esta é a
categoria em que a revisão não transige.

| # | Invariante | Fonte |
|---|---|---|
| 1.1 | Serializer público **nunca** usa `fields = "__all__"` nem `exclude`. Lista explícita, sempre. | PRD §6.1; docstring de `rede/serializers.py` |
| 1.2 | **Não existe serializer de `Pessoa`.** Nenhum dado de Pessoa é público, em nenhuma hipótese. | PRD §4.2, §6.1 |
| 1.3 | Campo novo no `fields` de um serializer público consta na lista de campos públicos do PRD — ou o PRD é emendado no mesmo PR. | PRD §9.2 |
| 1.4 | Contato novo tem entrada em `ColetivoSerializer.CONTATOS_POR_CONSENTIMENTO`. Sem entrada, o campo sairia **sempre**. | docstring de `ColetivoSerializer` |
| 1.5 | Contato sem consentimento tem a **chave removida** do JSON (`dados.pop`), não devolvida como `null` ou `""`. | PRD §6.2 |
| 1.6 | Nunca públicos: `logradouro`, `numero`, `complemento`, `cep`, `cnpj`, `data_inicio`, `responsavel_grupo`, `motivo_criacao`, `renda_obtida`, `historico_editais`, `situacao`, `ativo`, `nome_entrevistador`, `observacoes`, e as flags `exibir_*_publicamente`. | PRD §6.1; docstring de `rede/serializers.py` |
| 1.7 | `bairro` é o **único** dado geográfico público do Coletivo. | PRD §6.1 |
| 1.8 | `latitude`/`longitude` existem só em `PontoDeInteresse` — nunca em `Coletivo`. | PRD §4.5 |
| 1.9 | Campo público novo → asserção nova na suíte de regressão de LGPD. Manter a suíte verde não basta; ela precisa acompanhar o modelo. | PRD §6.3 |
| 1.10 | No Django Admin, dado sensível não vai para `list_display`, `search_fields` nem `list_filter` sem necessidade — minimização vale dentro do cofre também. | PRD Admin §4.3 |

**Sinal de alerta no diff:** qualquer `+` em `rede/serializers.py` que adicione
nome de campo, mude `to_representation`, ou toque `Meta.fields`.

---

## 2. Chave de visibilidade `ativo` — 🔴

`ativo` é o mecanismo com que a equipe do Centro Público tira um coletivo do ar.
Expô-lo como filtro permitiria a qualquer pessoa listar exatamente o que se
decidiu não exibir.

| # | Invariante | Fonte |
|---|---|---|
| 2.1 | `ativo` **não** é parâmetro de consulta: não entra em `ColetivoFilter`, `filterset_fields`, `search_fields` nem `ordering_fields`. | Emenda §10.2; docstring de `rede/filters.py` |
| 2.2 | Todo queryset de view pública começa com `filter(ativo=True)`. | docstring de `ColetivoViewSet` |
| 2.3 | O histórico de slug não fura a visibilidade: `_redirecionar_slug_antigo` filtra `coletivo__ativo=True`; slug antigo de coletivo inativo responde 404, não 301. | docstring de `rede/views.py` |
| 2.4 | O padrão vale para Evento e Ponto de Interesse quando entrarem — os dois já têm `ativo`. | PRD §9.2 (nota final) |

---

## 3. Migrations e esquema — 🔴/🟡

| # | Invariante | Fonte |
|---|---|---|
| 3.1 | Mudança em `rede/models/**` tem migration correspondente **no mesmo PR**. O CI roda `makemigrations --check --dry-run`. | CI `ci.yml`; PRD §10.3 |
| 3.2 | Esquema só muda por migration do Django. **Ninguém edita tabela pelo painel do Supabase.** | PRD §8.2 |
| 3.3 | Prefixo `000N_` da migration nova vem depois da última já em `origin/staging`. Duas branches gerando `0005_` quebram o merge. | prática de migration do Django |
| 3.4 | Migration destrutiva (`RemoveField`, `DeleteModel`, estreitamento de `max_length`/tipo) vem com o que acontece com os registros existentes explicado no PR. | — |
| 3.5 | `RunPython` traz `reverse_code` — migration de dados irreversível trava rollback. | — |
| 3.6 | `null=True` em campo já populado exige default ou migration de dados. | — |
| 3.7 | Não se comenta **estilo** de migration: `ruff` exclui `**/migrations/**` por ser código gerado. Comenta-se **semântica**. | `pyproject.toml` |
| 3.8 | A conexão de migration é a direta (5432, `DJANGO_DB_DIRECT=True`); a do app é o pooler (6543). Mudança nesse arranjo em `config/settings.py` é achado. | PRD §8.2; README |

---

## 4. Desempenho e escala — 🟡

O PRD §7 pede listagem abaixo de 500 ms, com paginação, índices e sem N+1 —
"adotados como boa prática para escalar com folga", não por já haver volume.

| # | Invariante | Fonte |
|---|---|---|
| 4.1 | Relação percorrida na serialização usa `prefetch_related` (M2M / reverse FK) ou `select_related` (FK / OneToOne). Padrão: `Coletivo.objects.filter(ativo=True).prefetch_related("categorias")`. | PRD §2.3, §7 |
| 4.2 | `list_display` do Admin que mostra campo de FK usa `list_select_related` — senão é uma query por linha da listagem. | PRD Admin §9 |
| 4.3 | Paginação é global (`config.settings.REST_FRAMEWORK`). O risco é desfazê-la: `pagination_class = None`, `page_size` grande, `max_page_size` acima de 100. | PRD §9.1; docstring de `rede/pagination.py` |
| 4.4 | Campo novo usado em filtro ou ordenação tem `db_index=True` (como `bairro` e `ativo`). | PRD §7 |
| 4.5 | Nada de query, `save()` ou chamada externa dentro de `for` sobre queryset. | PRD §7 |
| 4.6 | `.all()` sem limite em view, ou `len(queryset)` onde caberia `.count()`. | — |

---

## 5. Contrato da API pública — 🟡

Quebrar contrato quebra o frontend Next.js, construído em paralelo.

| # | Invariante | Fonte |
|---|---|---|
| 5.1 | Chaves em `snake_case`; datas em ISO 8601. | PRD §9.1 |
| 5.2 | Lista usa o envelope do DRF: `count`, `next`, `previous`, `results`. | PRD §9.1 |
| 5.3 | Busca textual é `q` (`SEARCH_PARAM` em settings), não `search`. | PRD §9.2; `config/settings.py` |
| 5.4 | `page_size` padrão 20, máximo 100. | PRD §9.1 |
| 5.5 | Renomear ou remover campo de resposta é breaking change: precisa constar na descrição do PR e no PRD. | PRD §9 |
| 5.6 | Erros seguem a tabela: tipo inválido em parâmetro → 400 (é o que `NumberFilter` produz); inexistente ou página fora da faixa → 404. Um `try/except` novo que engula exceção transforma 400 em 200 com lista vazia. | PRD §9.2 |
| 5.7 | Lookup público de Coletivo é por `slug`, não por `id`. | `ColetivoViewSet.lookup_field` |
| 5.8 | Slug trocado responde **301** (não 302) do endereço antigo para o canônico — é o que consolida a autoridade de SEO. | docstring de `_redirecionar_slug_antigo` |
| 5.9 | Rota nova é documentada no `README.md`, em português. | PRD §7 |

---

## 6. Permissões e segurança — 🔴

| # | Invariante | Fonte |
|---|---|---|
| 6.1 | A API pública é **somente leitura**. Só `ReadOnlyModelViewSet`. `ModelViewSet`, `mixins.Create/Update/DestroyModelMixin` ou `@action(methods=["post"])` em `rede/views.py` é 🔴. Escrita vive no Admin, atrás de sessão. | PRD §3, §7; docstring de `rede/views.py` |
| 6.2 | View pública declara `permission_classes` explicitamente, mesmo com o padrão global já permitindo. | docstring de `ColetivoViewSet` |
| 6.3 | Nenhum segredo no diff: `SECRET_KEY`, senha, URL de banco com credencial, chave da AWS. Se apareceu, a chave precisa ser **rotacionada** — o histórico do Git guarda. | PRD §8.2 |
| 6.4 | `.env` nunca é commitado; só `.env.example`, com placeholders. | `.gitignore` |
| 6.5 | `DJANGO_DEBUG` continua com default `False`; `ALLOWED_HOSTS` não vira `["*"]`. | `config/settings.py` |
| 6.6 | Nada de SQL cru concatenado com entrada do usuário (`.raw()`, `.extra()`, `RawSQL`). | — |
| 6.7 | Isolamento de acesso é pela camada de permissões do Django, **não** por RLS do Supabase (que seria ignorado — o Django conecta com papel privilegiado). Um PR que "adiciona RLS" contraria a decisão §8.2 e cria falsa sensação de proteção. | PRD §8.2 |
| 6.8 | Sem Auth, PostgREST ou Edge Functions do Supabase. Supabase é Postgres gerenciado + Storage, e só. | PRD §8.2 |
| 6.9 | Mídia local (`MEDIA_URL`/`MEDIA_ROOT`) é servida apenas sob `DEBUG`. Em produção o upload vai para o Storage do Supabase. | PRD Admin §5.1, §5.2 |

---

## 7. Testes — 🟡/🟣

| # | Invariante | Fonte |
|---|---|---|
| 7.1 | Comportamento novo tem teste. O núcleo mínimo cobre models, serializers e as rotas principais. | PRD §10.3 |
| 7.2 | Comportamento de **visibilidade** e de **omissão de contato** tem teste negativo — o dado *não* aparece. | PRD §6.3 |
| 7.3 | O teste falharia se o código estivesse errado? Teste que passa com qualquer implementação não testa nada. | — |
| 7.4 | PR com teste quebrado não entra em `main` nem `staging`. | PRD §10.3 |

---

## 8. Convenções — 🟣

| # | Invariante | Fonte |
|---|---|---|
| 8.1 | `ruff check .` limpo: `E`, `F`, `I`, `UP`, `B`, `DJ`, line-length 100, target py312. Não gaste comentário com o que o linter pega. | `pyproject.toml`; CI |
| 8.2 | Docstring explica a **decisão**, não a mecânica. É o padrão desta base e o que torna o projeto reaplicável. | PRD §7 |
| 8.3 | Português em docstring, comentário, `verbose_name` e mensagem de erro. | PRD §7 |
| 8.4 | Conventional Commits (`feat:`, `fix:`, `test:`, `refactor:`, `chore:`, `docs:`); branch com prefixo `feat/ fix/ chore/ docs/ refactor/ test/`. | PRD §10.1, §10.2 |
| 8.5 | Models ficam em pacote (`rede/models/`), um arquivo por entidade, reexportados em `__init__.py` na ordem das dependências. | PRD §6.7; `rede/models/__init__.py` |
| 8.6 | Sem código especulativo — o PRD diz explicitamente "evita-se sobre-engenharia". | PRD §7 |
| 8.7 | Alteração visual (telas do Admin) traz evidência no PR (screenshot). | PRD §10.1 |
| 8.8 | GPLv3: cabeçalho de licença e dependência nova compatível. Dependência nova precisa de justificativa — o projeto evita dependência de fornecedor. | PRD §7 (independência de fornecedor) |

---

## 9. O que **não** revisar

- Estilo que o `ruff` reprova — o CI já barra.
- Estilo dentro de `rede/migrations/` — código gerado, excluído do lint.
- Decisão de arquitetura já registrada no PRD §8 (Django-cêntrico, sessão em vez
  de JWT, Admin em vez de React, Docker). Discordar é conversa de PRD, não thread
  de PR.
- Problema pré-existente que o diff não toca — a menos que uma linha alterada o
  agrave ou o exponha.
- Regra de negócio que o PRD diz explicitamente ser verificação **humana**: o
  mínimo de 3 pessoas e o caráter interfamiliar do coletivo **não** são validados
  pelo software (PRD §4.1). Cobrar isso em código é achado inválido.
