"""Recortes de mapa para a ficha: base (Esri World Topo) + camada de
condicionante (ArcGIS CCGD_PUBLICACAO), alinhados em EPSG:3857 e devolvidos
como data URIs (base64) para embeber no HTML self-contained.

A base é igual para todas as condicionantes do mesmo ponto — buscar uma vez.
"""
from __future__ import annotations

import base64
from urllib.parse import urlencode
from urllib.request import urlopen, Request

from pyproj import Transformer

_CCGD = ("https://fedservergeo.cm-porto.pt/arcgis/rest/services/"
         "PDM2021/CCGD_PUBLICACAO/MapServer/export")
_ESRI = ("https://server.arcgisonline.com/ArcGIS/rest/services/"
         "World_Topo_Map/MapServer/export")
_UA = {"User-Agent": "CABE/0.1 (analise nao vinculativa)"}
_to3857 = Transformer.from_crs("EPSG:3763", "EPSG:3857", always_xy=True)


def _png_datauri(url: str, params: dict) -> str | None:
    try:
        req = Request(f"{url}?{urlencode(params)}", headers=_UA)
        raw = urlopen(req, timeout=45).read()
    except Exception:
        return None
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


def _bbox3857(x3763, y3763, raio_m):
    xm, ym = _to3857.transform(x3763, y3763)
    r = raio_m * 1.33  # aproxima a distorção do Mercator na latitude do Porto
    return f"{xm-r},{ym-r},{xm+r},{ym+r}"


def base(x3763, y3763, *, raio_m=150.0, size=(420, 190)) -> str | None:
    return _png_datauri(_ESRI, {
        "bbox": _bbox3857(x3763, y3763, raio_m), "bboxSR": 3857, "imageSR": 3857,
        "size": f"{size[0]},{size[1]}", "format": "png", "f": "image",
    })


def camada(x3763, y3763, layer_id, *, raio_m=150.0, size=(420, 190)) -> str | None:
    if layer_id is None:
        return None
    return _png_datauri(_CCGD, {
        "bbox": _bbox3857(x3763, y3763, raio_m), "bboxSR": 3857, "imageSR": 3857,
        "size": f"{size[0]},{size[1]}", "format": "png32", "transparent": "true",
        "layers": f"show:{layer_id}", "f": "image",
    })
