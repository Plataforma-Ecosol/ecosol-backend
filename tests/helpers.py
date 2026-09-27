"""Constantes compartilhadas pelas suítes de teste.

Fixture e hook moram no `conftest.py`; constante importa-se de um módulo.
"""
import base64

#: PNG 1×1 em memória — o menor arquivo que o `ImageField` aceita. Evita
#: depender de um binário versionado no repositório só para testar upload.
PNG_MINIMO = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGA"
    "hKmMIQAAAABJRU5ErkJggg=="
)
