"""Regras de configuração que dependem do ambiente de deploy.

Ficam fora do `settings.py` para poderem ser testadas como funções comuns: o
módulo de settings é lido uma vez só, e recarregá-lo num teste mudaria a
configuração de toda a suíte.
"""


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
