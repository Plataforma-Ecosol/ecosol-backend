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
- Admin: http://localhost:8001/admin/ (ver [Área administrativa](#área-administrativa))

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
