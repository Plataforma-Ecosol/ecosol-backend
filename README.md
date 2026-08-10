# ecosol-backend

Backend da **Plataforma de Rede da Economia Solidária de Niterói**
(Centro Público Casa Paul Singer · ITES / IFRJ). Django + DRF, arquitetura
Django-cêntrica com Supabase apenas como Postgres gerenciado + Storage.

Licença: GPLv3.

## Requisitos

- Python 3.12
- Docker + Docker Compose (caminho recomendado para desenvolvimento)

## Estrutura

```
ecosol-backend/
├── config/     # settings, urls, wsgi/asgi
├── rede/       # o domínio: models, serializers, views, admin
├── tests/      # suíte, bloqueante no CI
├── infra/      # docker-compose do ambiente de desenvolvimento local
└── docs/       # PRDs, guia de revisão de PR e revisões arquivadas
```

`infra/` e `docs/` vivem aqui dentro de propósito: clonar o repositório tem de
bastar para subir o sistema e entender por que ele é como é — é o que a
reaplicabilidade prometida na Seção 7 do PRD Técnico exige. Enquanto estavam
fora de qualquer repositório, essa promessa não se sustentava.

### Documentação

| Documento | O que traz |
|---|---|
| `docs/PRD/PRD_Tecnico_Ecosol_Niteroi_v4.1.md` | Arquitetura, modelo de dados, decisões e status. O documento mestre. |
| `docs/PRD/PRD_Implementacao_*.md` | Especificação de cada fatia entregue (models, endpoint de Coletivos, Django Admin). |
| `docs/GUIA_REVISAO_PR.md` | Como revisar um pull request neste projeto. |
| `docs/revisoes/` | Revisões arquivadas. |

## Dois ambientes, separados de propósito

| | **Local (Docker)** | **Supabase** |
|---|---|---|
| Como sobe | `cd infra && docker compose up` | `python manage.py runserver` na máquina |
| Banco | Postgres 16 em container | Postgres gerenciado do Supabase |
| Imagens | `media/`, na sua pasta | Supabase Storage |
| Configuração | declarada no `docker-compose.yml` | lida do seu `.env` |
| Para quê | desenvolver e testar à vontade | validar contra o ambiente real |

O ambiente local é **fechado**: não toca o Supabase por nenhum caminho, nem
banco nem imagem. Isso vale porque o compose liga `DJANGO_IGNORE_DOTENV=True`,
e aí o `settings.py` não lê o seu `.env`.

Não é preciosismo. O `read_env` do django-environ não sobrescreve o que já
existe no ambiente, mas **preenche as lacunas** — sem essa trava, toda variável
que o compose não declarasse (as credenciais do Storage, por exemplo) viria do
`.env` para dentro do container, e o ambiente "isolado" mandaria os uploads
para o Supabase de produção sem ninguém perceber. Ao acrescentar uma variável
nova ao `settings.py`, declare-a no compose se o ambiente local precisar dela.

### Local (Docker)

O caminho recomendado para o dia a dia. Clonar o repositório já basta — a
orquestração vem junto, em `infra/`:

```bash
git clone <url-do-ecosol-backend>
cd ecosol-backend/infra
docker compose up --build
```

- App: http://127.0.0.1:8001/health/ → `{"status": "ok"}`
- Admin: http://127.0.0.1:8001/admin/ (ver [Área administrativa](#área-administrativa))

### Supabase (sem Docker)

Da raiz do repositório:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
copy .env.example .env   # e preencha os valores
python manage.py migrate
python manage.py runserver
```

Nunca coloque `DJANGO_IGNORE_DOTENV` no seu `.env`: é o compose que a define,
e no `.env` ela se anularia.

## Conexão com o Supabase (duas conexões)

- **App (runtime):** Transaction Pooler, porta **6543** → `DATABASE_URL`.
  Exige os ajustes do pooler (`DJANGO_DB_POOLER=True`): sem server-side
  cursors e sem prepared statements.
- **Migrations:** conexão direta, porta **5432** → `DATABASE_DIRECT_URL`,
  usada com `DJANGO_DB_DIRECT=True`. Se o IPv4 der timeout, troque pela
  Session Pooler (host do pooler, porta 5432).

Rodar migrations contra o Supabase:

```powershell
$env:DJANGO_DB_DIRECT="True"; python manage.py migrate
```

## API pública

Somente leitura (`GET`) e sem autenticação — qualquer método de escrita
responde `405`. Chaves em `snake_case`, datas em ISO 8601 (`AAAA-MM-DD`) e
data-hora em ISO 8601 com fuso (`2026-08-15T18:00:00-03:00`), listas com o
envelope do DRF (`count`, `next`, `previous`, `results`).

| Rota | Descrição |
|---|---|
| `GET /api/coletivos/` | Lista paginada dos coletivos **ativos** |
| `GET /api/coletivos/{slug}/` | Detalhe de um coletivo, buscado pelo slug |
| `GET /api/eventos/` | Lista paginada dos eventos **ativos** |
| `GET /api/eventos/{slug}/` | Detalhe de um evento, buscado pelo slug |

`ativo` **não** é parâmetro em nenhuma rota: é a chave de visibilidade
pública, com que a equipe do Centro Público tira um registro do ar. Aceitá-lo
permitiria listar justamente o que se decidiu não exibir. Desligar `ativo`
some da listagem e faz o detalhe responder `404`.

Parâmetros comuns a todas as listagens: `page` (padrão 1; página fora da
faixa → `404`) e `page_size` (padrão 20, **máximo 100**).

### Coletivos

**Parâmetros da listagem**

| Parâmetro | Tipo | Comportamento |
|---|---|---|
| `q` | string | Busca textual, ignorando maiúsculas, em `nome` e `descricao` |
| `categoria` | int | Filtra pelo id de uma categoria. Valor não numérico → `400` |
| `bairro` | string | Filtra por bairro, ignorando maiúsculas |
| `ordering` | string | `nome`, `-nome`, `criado_em`, `-criado_em`. Padrão: `nome` |

**Campos da resposta:** `id`, `nome`, `slug`, `descricao`, `bairro`, `site`,
`categorias` (lista de `{id, nome, slug}`), `criado_em`, `atualizado_em` — e,
quando houver consentimento, `telefone`, `email` e `instagram`.

**Duas regras de exposição**

1. **Omissão por consentimento.** `telefone`, `email` e `instagram` só entram
   na resposta se a flag correspondente estiver ligada. Sem consentimento a
   **chave é removida** do JSON: não vem `null`, não vem string vazia. No
   cliente, o tipo é `telefone?: string`, e não `string | null`.
2. **`301` de slug antigo.** Trocar o slug de um coletivo não quebra os links
   já publicados: o endereço antigo responde `301` com `Location` na URL
   canônica. Vale só para coletivo ativo — slug antigo de coletivo inativo
   responde `404`, como qualquer slug inexistente.

Nenhum dado de Pessoa, endereço, dado cadastral ou flag de consentimento é
exposto por qualquer caminho. `bairro` é o único dado geográfico público.
Isso é garantido por uma suíte de regressão de LGPD, bloqueante no CI.

### Eventos

**Parâmetros da listagem**

| Parâmetro | Tipo | Comportamento |
|---|---|---|
| `q` | string | Busca textual, ignorando maiúsculas, em `titulo`, `descricao` e `local` |
| `periodo` | string | `proximos`, `passados` ou `todos`. Padrão: `todos`. Valor fora da lista → `400` |
| `de` | data | Eventos cuja **data de início** é a partir deste dia, inclusive |
| `ate` | data | Eventos cuja **data de início** é até este dia, inclusive |
| `bairro` | string | Filtra por bairro, ignorando maiúsculas |
| `ordering` | string | `data_inicio`, `-data_inicio`, `titulo`, `-titulo`. Padrão: `data_inicio` |

`de` e `ate` aceitam **só** `AAAA-MM-DD` — `15/08/2026` responde `400`. Os
dois comparam a **data**, não o instante: `ate=2026-08-15` inclui o evento das
19h do dia 15. Podem ser combinados com `periodo`.

**Campos da resposta:** `id`, `titulo`, `slug`, `descricao`, `data_inicio`,
`data_fim` (`null` quando não houver), `local`, `bairro`, `link`, `imagens`
(lista de `{id, imagem, legenda, ordem}`, ordenada por `ordem`, com URL
absoluta), `criado_em`, `atualizado_em`.

**Duas regras da agenda**

1. **O evento em andamento continua em `proximos`.** O recorte é "ainda não
   terminou": uma feira de três dias não some da agenda no segundo dia.
   `passados` é o complemento exato — todo evento ativo cai em um dos dois,
   nunca em nenhum e nunca nos dois.
2. **A rota nua não recorta o tempo.** Sem `periodo`, vêm todos os eventos
   ativos. A agenda pública pede `?periodo=proximos`; quem monta um histórico
   da rede pede `?periodo=passados&ordering=-data_inicio`. Um recorte
   implícito, que o cliente não pediu e não consegue desligar, faria a rota
   mentir sobre o tamanho da base.

A ordenação padrão é cronológica **crescente** (o próximo evento primeiro), ao
contrário do Admin, que mostra o último cadastro no topo.

Trocar o slug de um evento **quebra** o link antigo: o `301` de slug é
mecanismo do Coletivo, cujo endereço é ativo permanente de visibilidade,
enquanto o link de um evento tem a vida útil do evento.

## Área administrativa

O back-office da equipe do Centro Público, em **http://localhost:8001/admin/**.
Substitui a planilha de cadastro por um formulário estruturado. Tudo em
português; só entra quem tem conta — não há autocadastro.

### Primeiro acesso

Criar a conta inicial (uma vez, com o ambiente no ar):

```bash
cd infra
docker compose exec backend python manage.py createsuperuser
```

As demais contas da equipe são criadas pelo próprio Admin, em **Usuários**. No
MVP há um papel único (Administrador, com acesso completo); a granularidade por
grupo do Django existe e pode ser ligada depois, sem código.

### O que se administra

| Entidade | Destaques da tela |
|---|---|
| **Coletivos** | Campos em blocos; `ativo` editável direto na listagem; categorias por seletor duplo; listas somente leitura de quem compõe o coletivo e dos endereços anteriores |
| **Pessoas** | ~25 campos em blocos; bloco socioeconômico recolhido e rotulado como sensível; coletivo por autocomplete |
| **Categorias** | Slug automático; coluna com o número de coletivos |
| **Eventos** | Galeria de imagens inline com miniatura; navegação por data |
| **Pontos de Interesse** | Latitude/longitude em graus decimais, imagem de capa, vínculo opcional com coletivo |
| **Usuários** | Contas da equipe (formulário padrão do Django, com senha em hash) |

### As regras de visibilidade que o Admin opera

A API pública apenas **obedece** ao que se define aqui:

- **`ativo`** decide se o coletivo existe para o público. Desligar tira da
  listagem e faz o detalhe responder `404`.
- **`situação`** é rótulo cadastral informativo e **independente** de `ativo`:
  um coletivo pode estar "em transição" e continuar visível, ou "regular" e
  fora do ar.
- **`exibir_*_publicamente`** decide, contato a contato, se telefone, e-mail e
  instagram saem no JSON público. Sem consentimento registrado, deixe
  desmarcada — a chave some da resposta. Por isso cada contato aparece
  imediatamente acima da sua flag, no mesmo bloco.
- **Editar o slug** troca o endereço público, mas não quebra links: o endereço
  antigo é registrado sozinho e passa a responder `301` para o novo.

Endereço completo, dados cadastrais e **todos** os dados de Pessoa nunca são
públicos, por nenhum caminho.

> **Dados sensíveis.** O bloco socioeconômico e de identidade de Pessoa
> (cor/raça, sexo, identidade de gênero, orientação sexual, deficiência, renda,
> programas sociais) é editável na ficha, mas **nunca** vira coluna, filtro ou
> busca da listagem — filtrar pessoas por atributo protegido transformaria o
> cadastro em ferramenta de segmentação. Há teste automatizado bloqueando isso.

### Imagens

No ambiente local os uploads vão para `media/` (fora do Git) e são servidos pelo
Django enquanto `DEBUG=True`. Em homologação e produção vão para o Supabase
Storage, ligado por `DJANGO_USE_S3=True` — sem alteração de código.

## Testes e lint

```bash
ruff check .
pytest
```

## Fluxo Git

`main` e `staging` protegidas; trabalho em branches `feat/ fix/ chore/ docs/
refactor/ test/`; Conventional Commits; PR com revisão. CI (GitHub Actions)
roda lint + checagem de migrations + testes em todo PR.
