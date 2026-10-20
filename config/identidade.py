"""Cores da Casa Paul Singer na área administrativa.

Os hex são os mesmos do `@theme` de `ecosol-frontend/src/app/globals.css`.
Mudou uma escala lá, muda aqui também (o comentário do globals.css pede o
mesmo no sentido contrário).

Os hex ficam guardados como estão no frontend, para a comparação entre os dois
repositórios ser de texto igual a texto igual. A conversão para `oklch()`, o
formato das cores na documentação do Unfold, acontece na carga das settings.

O Unfold tem duas escalas: `base` (fundos, bordas e texto) e `primary` (botão,
link, item ativo do menu). As duas saem do azul, como no site, que usa
`azul-50` nos fundos de seção, `azul-100`/`azul-200` nas bordas e `azul-900`
no texto de destaque.
"""
import math

# `strict=True` nos `zip` abaixo: escala com degrau a mais ou a menos quebra na
# carga das settings, em vez de deslocar as cores em silêncio.
DEGRAUS = ("50", "100", "200", "300", "400", "500", "600", "700", "800", "900", "950")

# Azul da marca no degrau 800 (#33469B), como no frontend.
AZUL = dict(zip(DEGRAUS, (
    "#F4F7FE", "#E4EAFA", "#CFD9F6", "#B0C1F1", "#869EEB", "#6882DD",
    "#536AC3", "#4359B0", "#33469B", "#2C3C77", "#182143",
), strict=True))

# Degrau do `primary` do Unfold -> degrau do azul do site. O Unfold pinta
# botão, link e item ativo do menu com o 600, e o item ativo fica sobre o
# `base-100` (azul-100). Com a escala do site sem deslocar, seria o azul-600
# sobre o azul-100: 4,1:1, abaixo dos 4,5 do WCAG AA, e um azul mais claro que o
# dos botões do site. Deslocada, o 600 do Unfold é o azul da marca (7,0:1 sobre
# o azul-100, 8,4:1 de texto branco no botão). Os hex não mudam, só o degrau.
DEGRAUS_DO_PRIMARIO = {
    "50": "50", "100": "100", "200": "200", "300": "300", "400": "500",
    "500": "700", "600": "800", "700": "900", "800": "900", "900": "950", "950": "950",
}
PRIMARIO = {unfold: AZUL[site] for unfold, site in DEGRAUS_DO_PRIMARIO.items()}

# Abaixo disto o croma é ruído de arredondamento: a cor é cinza puro e o matiz
# não quer dizer nada.
_CROMA_MINIMO = 0.0005


def _linear(canal: int) -> float:
    """Canal sRGB (0–255) para luz linear (0–1)."""
    c = canal / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_para_oklch(cor: str) -> str:
    """Converte "#RRGGBB" para "oklch(L% C H)", o formato das cores do Unfold.

    sRGB -> linear -> OKLab -> OKLCh, pelas fórmulas públicas de Björn Ottosson
    (https://bottosson.github.io/posts/oklab/). `L` em porcentagem com uma casa,
    `C` com três e `H` com uma. Cor sem croma (branco, preto, cinza) sai com `C`
    e `H` zerados.
    """
    valor = cor.lstrip("#")
    r, g, b = (_linear(int(valor[i:i + 2], 16)) for i in (0, 2, 4))

    l_ = math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
    m_ = math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
    s_ = math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)

    luz = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b_ = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_

    croma = math.hypot(a, b_)
    if croma < _CROMA_MINIMO:
        croma, matiz = 0.0, 0.0
    else:
        matiz = math.degrees(math.atan2(b_, a)) % 360

    return f"oklch({luz * 100:.1f}% {croma:.3f} {matiz:.1f})"


def escala_oklch(escala: dict[str, str]) -> dict[str, str]:
    """A mesma escala, degrau a degrau, em `oklch()`."""
    return {degrau: hex_para_oklch(cor) for degrau, cor in escala.items()}
