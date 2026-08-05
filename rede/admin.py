"""Área administrativa (Django Admin) — o back-office da equipe do Centro Público.

Esta é a Interface 2 do MVP (PRD Técnico 5.2): substitui a planilha de cadastro
por um formulário estruturado. É também o cofre do projeto — reúne todos os
dados pessoais e sensíveis —, então o desenho segue dois cuidados constantes:

* **Ergonomia**: campos organizados em blocos legíveis (`fieldsets`), na mesma
  ordem dos blocos comentados nos models.
* **Privacidade**: cada contato aparece colado à sua flag de consentimento, e
  nenhum atributo sensível de Pessoa entra em listagem ou filtro.

Tudo em português (requisito de Tecnologia Social). O Admin não altera o
esquema: registrar um model aqui nunca gera migration.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db.models import Count

from rede.models import Categoria, Usuario

# --- Identidade da área administrativa -------------------------------------
admin.site.site_header = "Plataforma Ecosol — Rede da Economia Solidária de Niterói"
admin.site.site_title = "Ecosol · Administração"
admin.site.index_title = "Administração"


# --- Usuários (equipe do Centro Público) -----------------------------------
@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    """Contas com acesso ao back-office.

    Herda de `UserAdmin` — e não de `ModelAdmin` — de propósito: é o que
    preserva o formulário de senha com hash, os fieldsets de permissão e o
    "adicionar usuário" em duas etapas. Registrar um usuário customizado com um
    ModelAdmin comum gravaria a senha como texto puro.

    Não há autocadastro: as contas são criadas aqui, pela própria equipe
    (PRD Técnico 3 — papel único de Administrador no MVP).
    """


# --- Categorias / segmentos -------------------------------------------------
@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    """Segmentos que classificam os coletivos (artesanato, alimentação…)."""

    list_display = ("nome", "slug", "num_coletivos")
    search_fields = ("nome",)
    prepopulated_fields = {"slug": ("nome",)}

    def get_queryset(self, request):
        """Conta os coletivos de cada categoria em uma única consulta.

        Sem o `annotate`, a coluna `num_coletivos` dispararia um `COUNT` por
        linha da listagem (N+1) e a tela ficaria lenta conforme o cadastro
        cresce.
        """
        return super().get_queryset(request).annotate(_num_coletivos=Count("coletivos"))

    @admin.display(description="coletivos", ordering="_num_coletivos")
    def num_coletivos(self, obj):
        """Quantos coletivos estão classificados nesta categoria."""
        return obj._num_coletivos
