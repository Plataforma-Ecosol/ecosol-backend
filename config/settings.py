"""
Configurações do Django — Plataforma Ecosol (backend).

Arquitetura Django-cêntrica (PRD Técnico, decisão 8.2): o Django é dono do
esquema, da autenticação e das permissões. O Supabase entra apenas como
Postgres gerenciado + Storage — sem Auth, RLS ou APIs automáticas.

Tudo que muda entre ambientes (dev / homologação / produção) vem de variáveis
de ambiente lidas do arquivo .env. Nenhum segredo é escrito neste arquivo.
"""
from pathlib import Path

import environ

# .../apps/ecosol-backend
BASE_DIR = Path(__file__).resolve().parent.parent

# --- Ambiente (.env) -------------------------------------------------------
env = environ.Env(DJANGO_DEBUG=(bool, False))
env_file = BASE_DIR / ".env"

# O .env é a configuração da MÁQUINA do desenvolvedor e aponta para o Supabase
# real. No docker-compose local o ambiente já vem inteiro pelas variáveis do
# container, e ler o .env por cima abriria um vazamento silencioso: `read_env`
# não sobrescreve o que já existe, mas *preenche as lacunas* — então toda
# variável que o compose não declarasse (credenciais do Storage, por exemplo)
# passaria a vir do Supabase, e o ambiente "isolado" deixaria de ser isolado.
#
# Por isso o compose liga DJANGO_IGNORE_DOTENV: o isolamento vira propriedade
# do ambiente, e não uma lista de variáveis a manter em sincronia com o .env.
IGNORE_DOTENV = env.bool("DJANGO_IGNORE_DOTENV", default=False)
if env_file.exists() and not IGNORE_DOTENV:
    environ.Env.read_env(env_file)

SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-inseguro-troque-no-env")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# --- Aplicações ------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Terceiros
    "rest_framework",
    "django_filters",
    # Domínio
    "rede",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --- Banco de dados --------------------------------------------------------
# Duas conexões (PRD 3.1):
#   * App em runtime  -> Transaction Pooler (porta 6543). O pooler tem atrito
#     com prepared statements/server-side cursors do Django, então desativamos
#     ambos quando DJANGO_DB_POOLER=True.
#   * Migrations      -> conexão direta (porta 5432), em DATABASE_DIRECT_URL,
#     usada quando DJANGO_DB_DIRECT=True.
# No docker-compose local (Postgres em container) as duas flags ficam
# desligadas e usamos a DATABASE_URL do compose.
USE_DIRECT_DB = env.bool("DJANGO_DB_DIRECT", default=False)
DB_IS_POOLER = env.bool("DJANGO_DB_POOLER", default=False)

_db_url = (
    env("DATABASE_DIRECT_URL", default="")
    if USE_DIRECT_DB
    else env("DATABASE_URL", default="")
)

if _db_url:
    DATABASES = {"default": env.db_url_config(_db_url)}
    # Ajustes exigidos pelo pooler em modo transação (só ao falar com o pooler).
    if DB_IS_POOLER and not USE_DIRECT_DB:
        DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True
        DATABASES["default"].setdefault("OPTIONS", {})
        DATABASES["default"]["OPTIONS"]["prepare_threshold"] = None
else:
    # Fallback local (sem .env): Postgres do docker-compose.
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("POSTGRES_DB", default="ecosol"),
            "USER": env("POSTGRES_USER", default="ecosol"),
            "PASSWORD": env("POSTGRES_PASSWORD", default="ecosol"),
            "HOST": env("POSTGRES_HOST", default="db"),
            "PORT": env("POSTGRES_PORT", default="5432"),
        }
    }

# --- Validação de senha ----------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Internacionalização ---------------------------------------------------
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

# --- Arquivos estáticos ----------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# --- Arquivos de mídia (uploads) -------------------------------------------
# Em produção/homologação o upload vai para o Supabase Storage (bloco S3
# abaixo, DJANGO_USE_S3=True). No ambiente local do docker-compose (sem S3) os
# arquivos vão para o sistema de arquivos e são servidos só em DEBUG (ver
# config/urls.py). Sem isto, salvar uma imagem no Admin quebra localmente.
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# --- Storage de imagens (Supabase Storage, S3-compatível) — PRD 3.3 --------
# Já configurado nesta fase; passa a ser usado por imagens de Evento e capa de
# Ponto de Interesse a partir do PR 3/4. Só ativa se DJANGO_USE_S3=True.
if env.bool("DJANGO_USE_S3", default=False):
    STORAGES = {
        "default": {"BACKEND": "storages.backends.s3.S3Storage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
    AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL")
    AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default="sa-east-1")
    AWS_QUERYSTRING_AUTH = False  # imagens de divulgação são públicas
    AWS_DEFAULT_ACL = None

# --- Django REST Framework -------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly"
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    # Paginação global (PRD 9.1): `page_size` 20, teto de 100 — o `PAGE_SIZE`
    # do DRF fica na própria classe, e não aqui.
    "DEFAULT_PAGINATION_CLASS": "rede.pagination.PaginacaoPadrao",
    # O contrato público chama a busca textual de `q` (o padrão do DRF é
    # `search`).
    "SEARCH_PARAM": "q",
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# AUTH_USER_MODEL (usuário customizado): primeira migration do app `rede`,
# antes de qualquer outro model, para não travar o esquema depois (PRD 5).
AUTH_USER_MODEL = "rede.Usuario"
