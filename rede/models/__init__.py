"""Models do domínio `rede`.

Organizados em pacote (PRD 6.7) e reexportados aqui para que
`from rede.models import X` e as migrations funcionem como se fosse um
único módulo. A ordem segue as dependências: Usuario primeiro (PR A).
"""
from rede.models.usuario import Usuario

__all__ = ["Usuario"]
