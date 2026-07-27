"""Fonte de dados LOCAL do PDM do Porto.

Lê os geopackages oficiais embutidos (`dados_pdm/`) em vez de consultar o
servidor ArcGIS da CMP em tempo real. Motivo: o geoserver da Câmara recusa
pedidos vindos de gamas de IP de datacenter (devolve HTTP 500), o que impede
o alojamento em qualquer PaaS. Os ficheiros são a mesma cartografia oficial
do opendata.porto.digital (Carta de Qualificação do Solo + Carta de
Condicionantes), extraídos e reempacotados por `scripts/preparar_dados_pdm`.

Expõe `consultar_ponto` e `categoria_dominante` com EXACTAMENTE a mesma forma
de resposta que `pdm_arcgis`, para o motor e a ficha não mudarem.
"""
from __future__ import annotations

import math
import os
from functools import lru_cache

import geopandas as gpd
from shapely.geometry import Point

from pdm_arcgis import slug_categoria  # reutiliza o mapa rótulo/código -> slug

WKID = 3763

_DIR = os.environ.get("RAIO_PDM_DIR") or os.path.join(
    os.path.dirname(__file__), "..", "dados_pdm")
QS = os.path.join(_DIR, "qs.gpkg")
CCGD = os.path.join(_DIR, "ccgd.gpkg")

_FUNCIONAL = "PO_QSFUNCIONAL_PL"
_OPERATIVA = "PO_QSOPERATIVA_PL"


@lru_cache(maxsize=1)
def _ccgd_layers() -> list[str]:
    """Nomes das camadas de condicionantes (uma vez)."""
    try:
        return [l[0] for l in gpd.list_layers(CCGD).itertuples(index=False)]
    except Exception:
        import pyogrio
        return [l[0] for l in pyogrio.list_layers(CCGD)]


def _py(v):
    """Coage escalares numpy / NaN para tipos JSON-serializáveis."""
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if hasattr(v, "item"):
        try:
            return v.item()
        except Exception:
            return v
    return v


def _first(row, *nomes):
    """Primeiro valor não vazio entre as colunas dadas."""
    for n in nomes:
        if n in row.index:
            v = _py(row[n])
            if v not in (None, "", "Null"):
                return v
    return None


def _ler_bbox(path, layer, x, y, r):
    return gpd.read_file(path, layer=layer, bbox=(x - r, y - r, x + r, y + r))


def _no_ponto(path, layer, x, y):
    """Feature que contém o ponto (ou a mais próxima até 1 m)."""
    pt = Point(x, y)
    g = _ler_bbox(path, layer, x, y, 2.0)
    if g.empty:
        return None
    hit = g[g.contains(pt)]
    if hit.empty:
        prox = g[g.distance(pt) < 1.0]
        hit = prox
    return hit.iloc[0] if not hit.empty else None


def consultar_ponto(x: float, y: float, *, tolerancia_m: float = 1.0) -> dict:
    """Consulta por ponto (EPSG:3763): categoria de solo + condicionantes.

    Mesma forma de resposta que pdm_arcgis.consultar_ponto.
    """
    qf = _no_ponto(QS, _FUNCIONAL, x, y)
    qo = _no_ponto(QS, _OPERATIVA, x, y)

    sc = _py(qf["sc_espaco"]) if qf is not None else None
    c = _py(qf["c_espaco"]) if qf is not None else None
    slug = slug_categoria(sc)

    categoria = None
    if qf is not None:
        # o gpkg traz rótulos em texto (sem códigos separados): cod == rótulo
        categoria = {"c_espaco_cod": c, "c_espaco": c,
                     "sc_espaco_cod": sc, "sc_espaco": sc}

    operativa = None
    if qo is not None:
        t = _py(qo["t_espaco"])
        operativa = {"t_espaco_cod": t, "t_espaco": t}

    cond = _condicionantes(x, y, max(tolerancia_m, 1.0))

    return {
        "x": x, "y": y,
        "categoria": categoria,
        "operativa": operativa,
        "categoria_slug": slug,
        "regras_aplicaveis": slug is not None,
        "condicionantes": cond,
    }


def _condicionantes(x: float, y: float, r: float) -> list[dict]:
    pt = Point(x, y).buffer(r)
    out = []
    for layer in _ccgd_layers():
        try:
            g = _ler_bbox(CCGD, layer, x, y, r)
        except Exception:
            continue
        if g.empty:
            continue
        geomcol = g.geometry.name
        inter = g[g.intersects(pt)]
        for _, row in inter.iterrows():
            valores = {k: _py(row[k]) for k in row.index if k != geomcol}
            out.append({
                "camada": layer.replace("_", " "),
                "layer_id": None,
                "designacao": _first(row, "designacao", "identifica"),
                "legislacao": _first(row, "legislacao_aplicavel", "legislacao"),
                "valores": valores,
            })
    return out


def categoria_dominante(poly) -> dict | None:
    """Categoria de solo DOMINANTE (por área) sob um polígono (EPSG:3763)."""
    minx, miny, maxx, maxy = poly.bounds
    try:
        g = gpd.read_file(QS, layer=_FUNCIONAL, bbox=(minx, miny, maxx, maxy))
    except Exception:
        return None
    if g.empty:
        return None
    areas: dict[str, float] = {}
    for _, row in g.iterrows():
        sc = _py(row["sc_espaco"])
        if not sc:
            continue
        try:
            a = poly.intersection(row.geometry).area
        except Exception:
            a = 0.0
        areas[sc] = areas.get(sc, 0.0) + a
    if not areas:
        return None
    dom = max(areas, key=areas.get)
    return {"sc_espaco_cod": dom, "sc_espaco": dom, "slug": slug_categoria(dom),
            "fracao": round(areas[dom] / (poly.area or 1), 2)}
