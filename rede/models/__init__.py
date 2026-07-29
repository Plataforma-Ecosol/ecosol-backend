"""Models do domínio `rede`.

Organizados em pacote (PRD 6.7) e reexportados aqui para que
`from rede.models import X` e as migrations funcionem como se fosse um
único módulo. A ordem segue as dependências: Usuario primeiro (PR A),
depois os models de domínio (PR B).
"""
from rede.models.categoria import Categoria
from rede.models.coletivo import Coletivo, ColetivoSlugAnterior
from rede.models.evento import Evento, ImagemEvento
from rede.models.pessoa import Pessoa
from rede.models.ponto_interesse import PontoDeInteresse
from rede.models.usuario import Usuario

__all__ = [
    "Usuario",
    "Categoria",
    "Coletivo",
    "ColetivoSlugAnterior",
    "Pessoa",
    "Evento",
    "ImagemEvento",
    "PontoDeInteresse",
]
