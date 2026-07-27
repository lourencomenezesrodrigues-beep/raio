"""Geocodificação de moradas → ponto EPSG:3763, via Nominatim (OpenStreetMap).

Limitado ao concelho do Porto (bounding box + countrycodes=pt). Devolve
candidatos ordenados; `geocodificar` devolve o melhor. Uso de baixo volume,
com User-Agent identificado, conforme a política do Nominatim.

Não há locator aberto da CMP; se um dia existir, acrescentar aqui como fonte
primária e manter o Nominatim como fallback.
"""
from __future__ import annotations

import json
import time
from urllib.parse import urlencode
from urllib.request import urlopen, Request

from pyproj import Transformer

_URL = "https://nominatim.openstreetmap.org/search"
_UA = {"User-Agent": "RAIO/0.1 (analise nao vinculativa; Dinosaur Ideas)"}
# bounding box do concelho do Porto (WGS84): lon_min, lat_min, lon_max, lat_max
_PORTO = (-8.702, 41.138, -8.552, 41.186)
_to3763 = Transformer.from_crs("EPSG:4326", "EPSG:3763", always_xy=True)
_ultimo = [0.0]  # timestamp da última chamada (rate-limit cortês)


def _throttle():
    dt = time.monotonic() - _ultimo[0]
    if dt < 1.0:
        time.sleep(1.0 - dt)
    _ultimo[0] = time.monotonic()


def candidatos(morada: str, *, limite: int = 5) -> list[dict]:
    """Devolve candidatos {x, y, lat, lon, label, tipo} em EPSG:3763."""
    if not morada or not morada.strip():
        return []
    lonmin, latmin, lonmax, latmax = _PORTO
    params = {
        "q": morada.strip(),
        "format": "jsonv2",
        "countrycodes": "pt",
        "limit": limite,
        "addressdetails": 1,
        "viewbox": f"{lonmin},{latmin},{lonmax},{latmax}",
        "bounded": 1,
    }
    _throttle()
    req = Request(f"{_URL}?{urlencode(params)}", headers=_UA)
    try:
        with urlopen(req, timeout=30) as r:
            dados = json.load(r)
    except Exception:
        return []
    out = []
    for d in dados:
        lat, lon = float(d["lat"]), float(d["lon"])
        x, y = _to3763.transform(lon, lat)
        out.append({
            "x": round(x, 2), "y": round(y, 2), "lat": lat, "lon": lon,
            "label": d.get("display_name"),
            "tipo": d.get("type"),
            "importancia": d.get("importance"),
        })
    return out


def geocodificar(morada: str) -> dict | None:
    """Melhor candidato para uma morada (ou None)."""
    c = candidatos(morada, limite=1)
    return c[0] if c else None


if __name__ == "__main__":
    for m in ["Praça da Liberdade, Porto", "Rua de Santa Catarina 200, Porto",
              "Câmara Municipal do Porto"]:
        r = geocodificar(m)
        print(f"{m!r:45} -> "
              + (f"{r['x']:.1f}, {r['y']:.1f}  ({r['label'][:50]}…)" if r else "sem resultado"))
