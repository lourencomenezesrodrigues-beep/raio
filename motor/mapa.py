"""Recortes de mapa para a ficha, a partir da cartografia oficial da CMP.

Base: Cartografia/Mapa_Base_Cache (o mapa base do "Mapas do Porto" da Câmara
Municipal do Porto). Sobreposição: a camada de condicionante do serviço
CCGD_PUBLICACAO. Ambos exportam nativamente em EPSG:3763, pelo que partilham
a mesma bbox e ficam alinhados. Devolvidos como data URIs (base64) para
embeber no HTML self-contained.

A base é igual para todas as condicionantes do mesmo ponto — buscar uma vez.
Fonte dos serviços: fedservergeo.cm-porto.pt/arcgis (portalgeo.cm-porto.pt).
"""
from __future__ import annotations

import base64
from urllib.parse import urlencode
from urllib.request import urlopen, Request

_SRV = "https://fedservergeo.cm-porto.pt/arcgis/rest/services"
_BASE_CMP = f"{_SRV}/Cartografia/Mapa_Base_Cache/MapServer/export"
_CCGD = f"{_SRV}/PDM2021/CCGD_PUBLICACAO/MapServer/export"
_UA = {"User-Agent": "RAIO/0.1 (analise nao vinculativa)"}


def _png_datauri(url: str, params: dict) -> str | None:
    try:
        req = Request(f"{url}?{urlencode(params)}", headers=_UA)
        raw = urlopen(req, timeout=45).read()
    except Exception:
        return None
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


def _bbox(x3763, y3763, raio_m):
    return f"{x3763-raio_m},{y3763-raio_m},{x3763+raio_m},{y3763+raio_m}"


def base(x3763, y3763, *, raio_m=150.0, size=(420, 190)) -> str | None:
    """Recorte da cartografia base da CMP (EPSG:3763)."""
    return _png_datauri(_BASE_CMP, {
        "bbox": _bbox(x3763, y3763, raio_m), "bboxSR": 3763, "imageSR": 3763,
        "size": f"{size[0]},{size[1]}", "format": "png", "f": "image",
    })


def camada(x3763, y3763, layer_id, *, raio_m=150.0, size=(420, 190)) -> str | None:
    """Recorte transparente de uma camada de condicionante (CCGD), EPSG:3763."""
    if layer_id is None:
        return None
    return _png_datauri(_CCGD, {
        "bbox": _bbox(x3763, y3763, raio_m), "bboxSR": 3763, "imageSR": 3763,
        "size": f"{size[0]},{size[1]}", "format": "png32", "transparent": "true",
        "layers": f"show:{layer_id}", "f": "image",
    })
