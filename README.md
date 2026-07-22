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

## Testes e lint

```bash
ruff check .
pytest
```

## Fluxo Git

`main` e `staging` protegidas; trabalho em branches `feat/ fix/ chore/ docs/
refactor/ test/`; Conventional Commits; PR com revisão. CI (GitHub Actions)
roda lint + checagem de migrations + testes em todo PR.
