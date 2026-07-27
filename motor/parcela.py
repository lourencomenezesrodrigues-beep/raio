"""Métricas de uma parcela a partir do seu polígono (EPSG:3763).

Como não há camada de parcelas aberta no Porto, o utilizador fornece o contorno
do terreno (desenhado sobre o mapa ou de levantamento). Deste polígono derivamos
área, frente (largura ao longo da rua) e profundidade (perpendicular à rua),
usando uma bounding box orientada ao eixo da rua fronteira (motor.frente).
"""
from __future__ import annotations

import math
from pathlib import Path
import sys

from shapely import wkt as _wkt
from shapely.geometry.base import BaseGeometry

sys.path.insert(0, str(Path(__file__).resolve().parent))
import frente as _frente  # noqa: E402


def _como_poligono(poligono):
    if isinstance(poligono, str):
        poligono = _wkt.loads(poligono)
    if poligono.geom_type == "MultiPolygon":
        poligono = max(poligono.geoms, key=lambda p: p.area)
    return poligono


def _direcao_eixo(eixo, ponto):
    """Vetor unitário do eixo na projecção do ponto."""
    s = eixo.project(ponto)
    a = eixo.interpolate(max(s - 1.0, 0.0))
    b = eixo.interpolate(min(s + 1.0, eixo.length))
    dx, dy = b.x - a.x, b.y - a.y
    n = math.hypot(dx, dy) or 1.0
    return dx / n, dy / n


def metricas_de_poligono(poligono, *, eixo=None):
    """poligono: shapely (ou WKT) em EPSG:3763.

    Devolve {area_m2, frente_m, profundidade_m, rua}. `eixo` (LineString) pode
    ser injectado (evita a rede em testes); caso contrário deriva-se do centróide.
    """
    poly = _como_poligono(poligono)
    c = poly.centroid
    rua = None
    if eixo is None:
        ei = _frente.eixo_no_ponto(c.x, c.y)
        if ei is None:
            # sem rua: rectângulo mínimo do lote (lado menor = frente, maior = profundidade)
            xy = list(poly.minimum_rotated_rectangle.exterior.coords)
            lados = [math.hypot(xy[i + 1][0] - xy[i][0], xy[i + 1][1] - xy[i][1])
                     for i in range(4)]
            return {"area_m2": round(poly.area, 1),
                    "frente_m": round(min(lados[0], lados[1]), 1),
                    "profundidade_m": round(max(lados[0], lados[1]), 1),
                    "rua": None,
                    "aviso": "sem rua Overture: frente/profundidade estimadas pelo lote"}
        eixo, rua = ei["lanco"], ei["rua"]

    ux, uy = _direcao_eixo(eixo, c)   # ao longo da rua
    nx, ny = -uy, ux                  # perpendicular à rua
    coords = list(poly.exterior.coords)
    ao_longo = [px * ux + py * uy for px, py in coords]
    perp = [px * nx + py * ny for px, py in coords]
    return {
        "area_m2": round(poly.area, 1),
        "frente_m": round(max(ao_longo) - min(ao_longo), 1),
        "profundidade_m": round(max(perp) - min(perp), 1),
        "rua": rua,
    }


def parcela_para_engine(poligono, *, eixo=None, extra=None):
    """Constrói o dict `parcela` que o motor espera, a partir do polígono."""
    m = metricas_de_poligono(poligono, eixo=eixo)
    parcela = {"area_m2": m["area_m2"], "frente_m": m["frente_m"],
               "profundidade_m": m["profundidade_m"]}
    if extra:
        parcela.update(extra)
    return parcela, m
