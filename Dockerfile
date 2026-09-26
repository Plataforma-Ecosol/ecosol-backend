FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . .

# Estáticos do Admin empacotados na imagem, servidos pelo WhiteNoise.
# SECRET_KEY de mentira só para o comando carregar as settings: o
# collectstatic não usa banco nem segredo, e a chave de verdade chega em runtime.
RUN DJANGO_SECRET_KEY=somente-build DJANGO_IGNORE_DOTENV=True \
    python manage.py collectstatic --noinput

EXPOSE 8001

# O Render (e a maioria dos PaaS) injeta a porta em $PORT. Fora deles vale a
# 8001 de sempre. Em dev o docker-compose sobrescreve este CMD por runserver.
# --workers 2: a instância Free tem 512 MB de RAM. --timeout 60: o pooler do
# Supabase às vezes demora na primeira conexão depois de o serviço acordar.
CMD ["sh", "-c", "gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8001} --workers 2 --timeout 60"]
