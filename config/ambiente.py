"""Regras de configuração que dependem do ambiente de deploy.

Ficam fora do `settings.py` para poderem ser testadas como funções comuns: o
módulo de settings é lido uma vez só, e recarregá-lo num teste mudaria a
configuração de toda a suíte.
"""
from urllib.parse import urlsplit


def hosts_permitidos(declarados, host_render=""):
    """`ALLOWED_HOSTS` com o host que o Render injeta, se houver.

    O Render define `RENDER_EXTERNAL_HOSTNAME` em toda instância. Somá-lo evita
    depender de alguém digitar o endereço certo no painel: um host errado
    derruba o health check com 400, e a mensagem não menciona ALLOWED_HOSTS.
    """
    hosts = list(declarados)
    host_render = host_render.strip()
    if host_render and host_render not in hosts:
        hosts.append(host_render)
    return hosts


def dominio_publico_supabase(endpoint_s3, bucket):
    """Onde o navegador lê os arquivos de um bucket público do Supabase.

    O endpoint S3 (`https://<ref>.supabase.co/storage/v1/s3`) é por onde o
    Django GRAVA, e exige assinatura: sem `AWS_S3_CUSTOM_DOMAIN`, o
    django-storages monta a URL da imagem a partir dele, e o navegador leva
    403. A leitura pública mora em `/storage/v1/object/public/<bucket>`.

    O painel às vezes mostra o endpoint no subdomínio `<ref>.storage.supabase.co`.
    O domínio devolvido é sempre o `<ref>.supabase.co`, que é o que o
    `next.config.ts` do frontend libera para imagens (`*.supabase.co` casa um
    nível de subdomínio só).

    Devolve None fora do Supabase: aí vale o comportamento padrão do backend.
    """
    partes = urlsplit(endpoint_s3.strip())
    host = partes.hostname or ""
    if not host.endswith(".supabase.co") or not partes.path.startswith("/storage/v1/s3"):
        return None
    ref = host.split(".", 1)[0]
    return f"{ref}.supabase.co/storage/v1/object/public/{bucket}"
