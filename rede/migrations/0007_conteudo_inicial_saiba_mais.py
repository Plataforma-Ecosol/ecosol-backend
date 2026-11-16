"""Carga inicial das seções do "Saiba mais" (PRD Saiba mais: seções por subgrupo).

Os dois primeiros textos são os que estão no ar desde 13/10, copiados de
`ecosol-frontend/src/lib/casa.ts`. O da ITES foi escrito pelo time e vai para a
Casa revisar pelo Admin. Os textos ficam escritos aqui, e não importados de
lugar nenhum: a migration precisa continuar igual mesmo que o `casa.ts` mude.
"""
from django.db import migrations

SECOES = [
    {
        "slug": "quem-somos",
        "subgrupo": "casa-azul",
        "titulo": "Quem somos",
        "texto": (
            "A Casa da Economia Solidária Paul Singer é o Centro Público de "
            "Referência em Economia Solidária de Niterói. É aqui que coletivos, "
            "feiras e empreendimentos da economia solidária da cidade encontram "
            "apoio, formação e espaço para se organizar.\n\n"
            "A Casa mantém esta plataforma para que qualquer pessoa conheça os "
            "coletivos da rede, acompanhe a agenda de eventos e saiba onde "
            "encontrar a economia solidária em Niterói."
        ),
    },
    {
        "slug": "rede-de-economia-solidaria",
        "subgrupo": "economia-solidaria",
        "titulo": "A Rede de Economia Solidária de Niterói",
        "texto": (
            "A Rede de Economia Solidária de Niterói reúne coletivos que trabalham "
            "de forma autogestionária, com decisões compartilhadas e renda "
            "dividida de forma justa. Nesta plataforma você encontra esses "
            "coletivos, a agenda de feiras e eventos e os pontos da economia "
            "solidária na cidade."
        ),
    },
    {
        "slug": "a-ites",
        "subgrupo": "ites-ifrj",
        "titulo": "A ITES",
        "texto": (
            "A ITES é a Incubadora Tecnológica de Empreendimentos Solidários do "
            "IFRJ Campus Niterói. Ela apoia a criação e o fortalecimento de "
            "empreendimentos da economia solidária e desenvolve esta plataforma "
            "junto com a Casa da Economia Solidária Paul Singer, com apoio do "
            "CNPq pelo programa PIBITI."
        ),
    },
]


def criar(apps, schema_editor):
    """Cria as seções que faltam. Seção já existente fica como está.

    `get_or_create` pelo slug: rodar de novo não duplica nada e não sobrescreve
    um texto que a equipe já tenha editado no Admin.
    """
    SecaoSaibaMais = apps.get_model("rede", "SecaoSaibaMais")
    for secao in SECOES:
        dados = {chave: valor for chave, valor in secao.items() if chave != "slug"}
        SecaoSaibaMais.objects.get_or_create(
            slug=secao["slug"],
            defaults={**dados, "ordem": 1, "publicado": True},
        )


def remover(apps, schema_editor):
    """Volta da carga: apaga as três seções pelo slug. Uso no ambiente local."""
    SecaoSaibaMais = apps.get_model("rede", "SecaoSaibaMais")
    SecaoSaibaMais.objects.filter(
        slug__in=[secao["slug"] for secao in SECOES]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("rede", "0006_secaosaibamais"),
    ]

    operations = [
        migrations.RunPython(criar, remover),
    ]
