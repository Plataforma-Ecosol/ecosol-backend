"""Pessoa — quem compõe o coletivo. Nunca exposta publicamente."""
from django.db import models


class Pessoa(models.Model):
    """Pessoa integrante de um Coletivo.

    NENHUM dado de Pessoa é exposto na interface pública, em nenhuma hipótese.
    Toda Pessoa pertence a um Coletivo (FK obrigatória). O bloco socioeconômico
    e de identidade contém DADOS SENSÍVEIS que existem apenas no back-office e
    nunca serão declarados em serializer público (garantia da fatia seguinte).

    "Empreendimento individual" é atributo da pessoa, não entidade própria.
    "Família" também não é entidade: a validação de coletivo interfamiliar é
    humana (PRD 6).
    """

    # `PROTECT`: não apagar pessoas por acidente ao remover um coletivo (PRD 6.3).
    coletivo = models.ForeignKey(
        "rede.Coletivo", on_delete=models.PROTECT, related_name="pessoas",
        verbose_name="coletivo",
    )

    # --- Identificação -----------------------------------------------------
    nome = models.CharField("nome", max_length=200)
    nome_social = models.CharField("nome social", max_length=200, blank=True)
    data_nascimento = models.DateField("data de nascimento", null=True, blank=True)
    cpf = models.CharField("CPF", max_length=14, blank=True)
    rg = models.CharField("RG", max_length=20, blank=True)
    rne_crnm = models.CharField("RNE / CRNM", max_length=30, blank=True)
    naturalidade = models.CharField("naturalidade", max_length=120, blank=True)
    estado_civil = models.CharField("estado civil", max_length=40, blank=True)

    # --- Contato -----------------------------------------------------------
    email = models.EmailField("e-mail", blank=True)
    instagram = models.CharField("instagram", max_length=120, blank=True)
    facebook = models.CharField("facebook", max_length=120, blank=True)
    site = models.URLField("site", blank=True)
    telefone = models.CharField(
        "telefone", max_length=40, blank=True,
        help_text="Preferência WhatsApp.",
    )

    # --- Endereço ----------------------------------------------------------
    cep = models.CharField("CEP", max_length=9, blank=True)
    logradouro = models.CharField("logradouro", max_length=200, blank=True)
    bairro = models.CharField("bairro", max_length=120, blank=True)
    municipio = models.CharField("município", max_length=120, blank=True)
    estado = models.CharField("estado", max_length=40, blank=True)

    # --- Escolaridade ------------------------------------------------------
    escolaridade = models.CharField("escolaridade", max_length=120, blank=True)

    # --- Empreendimento individual (quando houver) -------------------------
    empreendimento_individual = models.TextField(
        "empreendimento individual", blank=True,
    )

    # --- Bloco socioeconômico e de identidade (SENSÍVEL — só back-office) ---
    cor_raca = models.CharField(
        "cor/raça (autodeclaração)", max_length=60, blank=True,
    )
    sexo = models.CharField("sexo", max_length=40, blank=True)
    identidade_genero = models.CharField(
        "identidade de gênero", max_length=60, blank=True,
    )
    orientacao_sexual = models.CharField(
        "orientação sexual", max_length=60, blank=True,
    )
    pessoa_com_deficiencia = models.BooleanField(
        "pessoa com deficiência", default=False,
    )
    qual_deficiencia = models.CharField(
        "qual deficiência", max_length=200, blank=True,
    )
    renda_familiar = models.CharField("renda familiar", max_length=120, blank=True)
    rede_protecao_social = models.CharField(
        "rede de proteção social", max_length=200, blank=True,
    )
    participacao_programas_sociais = models.CharField(
        "participação em programas sociais", max_length=200, blank=True,
    )

    # --- Metadados ---------------------------------------------------------
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "pessoa"
        verbose_name_plural = "pessoas"
        ordering = ["nome"]

    def __str__(self):
        return self.nome_social or self.nome
