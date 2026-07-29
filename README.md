# ecosol-backend

Backend da **Plataforma de Rede da Economia Solidária de Niterói**
(Centro Público Casa Paul Singer · ITES / IFRJ). Django + DRF, arquitetura
Django-cêntrica com Supabase apenas como Postgres gerenciado + Storage.

Licença: GPLv3.

## Requisitos

- Python 3.12
- Docker + Docker Compose (caminho recomendado para desenvolvimento)

## Subir o ambiente local (Docker)

O jeito mais simples — Postgres isolado em container, sem tocar o Supabase.
A partir da raiz da umbrella:

```bash
cd infra
docker compose up --build
```

- App: http://localhost:8001/health/ → `{"status": "ok"}`
- Admin: http://localhost:8001/admin/ (o superusuário entra no PR 2/4)

## Rodar sem Docker (opcional)

```powershell
cd apps\ecosol-backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
copy .env.example .env   # e preencha os valores
python manage.py migrate
python manage.py runserver
```

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

Somente leitura (`GET`) e sem autenticação. Chaves em `snake_case`, datas em
ISO 8601, listas com o envelope do DRF (`count`, `next`, `previous`,
`results`).

| Rota | Descrição |
|---|---|
| `GET /api/coletivos/` | Lista paginada dos coletivos **ativos** |
| `GET /api/coletivos/{slug}/` | Detalhe de um coletivo, buscado pelo slug |

### Parâmetros da listagem

| Parâmetro | Tipo | Comportamento |
|---|---|---|
| `q` | string | Busca textual, ignorando maiúsculas, em `nome` e `descricao` |
| `categoria` | int | Filtra pelo id de uma categoria. Valor não numérico → `400` |
| `bairro` | string | Filtra por bairro, ignorando maiúsculas |
| `ordering` | string | `nome`, `-nome`, `criado_em`, `-criado_em`. Padrão: `nome` |
| `page` | int | Número da página (padrão 1). Página fora da faixa → `404` |
| `page_size` | int | Itens por página (padrão 20, **máximo 100**) |

`ativo` **não** é parâmetro: é a chave de visibilidade pública, com que a
equipe do Centro Público tira um coletivo do ar. Aceitá-lo permitiria listar
justamente o que se decidiu não exibir.

### Campos da resposta

`id`, `nome`, `slug`, `descricao`, `bairro`, `site`, `categorias`
(lista de `{id, nome, slug}`), `criado_em`, `atualizado_em` — e, quando houver
consentimento, `telefone`, `email` e `instagram`.

### Duas regras de exposição

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

## Testes e lint

```bash
ruff check .
pytest
```

## Fluxo Git

`main` e `staging` protegidas; trabalho em branches `feat/ fix/ chore/ docs/
refactor/ test/`; Conventional Commits; PR com revisão. CI (GitHub Actions)
roda lint + checagem de migrations + testes em todo PR.
