1. Gerar a migration (não precisa de banco):
cd C:\ecosol-fullstack\apps\ecosol-backend
.\.venv\Scripts\python.exe manage.py makemigrations rede
Confira que o nome sai como 000numero_... e as operações são de acordo com o alterado anteriormente.

2. Validar o esquema localmente (container isolado, não toca o Supabase):
cd C:/ecosol-fullstack/infra
docker compose run --rm backend python manage.py migrate
docker compose run --rm backend python manage.py makemigrations --check --dry-run   # "No changes detected"
docker compose run --rm --no-deps backend ruff check .                              # "All checks passed!"
docker compose run --rm backend pytest                                             # deve continuar verde

3. Aplicar no Supabase real (Session Pooler 5432, como antes):
cd C:\ecosol-fullstack\apps\ecosol-backend
$env:DJANGO_DB_DIRECT="True"
.\.venv\Scripts\python.exe manage.py migrate
Remove-Item Env:\DJANGO_DB_DIRECT