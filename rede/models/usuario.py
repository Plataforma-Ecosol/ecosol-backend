"""Usuário customizado do back-office."""
from django.contrib.auth.models import AbstractUser


class Usuario(AbstractUser):
    """Usuário do back-office (equipe do Centro Público).

    Customizado desde a primeira migration (PRD Técnico 4.6), para não travar
    o esquema de autenticação depois. Não há autocadastro público: as contas
    com login são as da equipe administrativa (papel Administrador); o
    "Público Geral" não faz login — apenas lê a interface pública.

    Herdar de AbstractUser mantém username/password/permissions do Django,
    prontos para o Django Admin e para o sistema de permissões. Campos de
    perfil administrativo podem entrar aqui no futuro, sem nada especulativo
    agora.
    """

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"

    def __str__(self):
        return self.get_full_name() or self.username
