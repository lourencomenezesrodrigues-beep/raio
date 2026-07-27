"""Moda da cércea da frente urbana a partir de um ponto (EPSG:3763).

Dado um ponto, encontra a rua fronteira no Overture, isola a frente do lado do
ponto (buffer unilateral limitado a uma janela ~ um quarteirão) e calcula a moda
da cércea (motor.cercea), ponderada por extensão de fachada e arredondada a 3 m.

A definição legal de frente urbana é "entre duas vias sucessivas"; aqui a janela
aproxima esse lanço sem detecção explícita de cruzamentos (declarado).
"""
from __future__ import annotations

import math
from pathlib import Path
import sys

import pandas as pd
from pyproj import Transformer
from shapely.geometry import Point
from shapely.ops import linemerge, unary_union, substring

sys.path.insert(0, str(Path(__file__).resolve().parent))
import overture  # noqa: E402
import cercea as C  # noqa: E402

PE_DIREITO = 3.0
_to4326 = Transformer.from_crs("EPSG:3763", "EPSG:4326", always_xy=True)


def _bbox_wgs84(x, y, raio_m):
    lon, lat = _to4326.transform(x, y)
    dlat = raio_m / 111_320.0
    dlon = raio_m / (111_320.0 * math.cos(math.radians(lat)))
    return (lon - dlon, lat - dlat, lon + dlon, lat + dlat)


def _line_parts(g):
    """Extrai recursivamente as componentes LineString de qualquer geometria."""
    t = g.geom_type
    if t == "LineString":
        return [g]
    if t in ("MultiLineString", "GeometryCollection"):
        out = []
        for x in g.geoms:
            out += _line_parts(x)
        return out
    return []


def _lado_sinal(linha, p):
    """+1 se p está à esquerda da direcção da linha, -1 se à direita."""
    s = linha.project(p)
    a = linha.interpolate(max(s - 1.0, 0.0))
    b = linha.interpolate(min(s + 1.0, linha.length))
    dx, dy = b.x - a.x, b.y - a.y
    return 1.0 if (dx * (p.y - a.y) - dy * (p.x - a.x)) >= 0 else -1.0


def eixo_no_ponto(x, y, *, raio_m=70.0, janela_m=80.0):
    """Lanço do eixo da rua fronteira ao ponto (janela ~ quarteirão).

    Devolve {"lanco": LineString, "rua": str|None} ou None se não há ruas.
    Reutilizado pelo cálculo da moda (frente_no_ponto) e das métricas da
    parcela (motor.parcela).
    """
    ruas = overture.ruas_bbox(_bbox_wgs84(x, y, raio_m))
    P = Point(x, y)
    if ruas.empty:
        return None
    ruas = ruas.copy()
    ruas["d"] = ruas.geometry.distance(P)
    perto = ruas.sort_values("d").iloc[0]
    nome = perto["nome"] if isinstance(perto["nome"], str) else None
    grupo = ruas[ruas["nome"] == nome] if nome else ruas.iloc[[ruas["d"].argmin()]]
    partes = _line_parts(unary_union(list(grupo.geometry)))
    if not partes:
        partes = [perto.geometry]
    merged = linemerge(partes) if len(partes) > 1 else partes[0]
    if merged.geom_type == "MultiLineString":
        eixo = min(merged.geoms, key=lambda l: l.distance(P))
    else:
        eixo = merged
    s = eixo.project(P)
    lanco = substring(eixo, max(s - janela_m, 0.0), min(s + janela_m, eixo.length))
    return {"lanco": lanco, "rua": nome}


def frente_no_ponto(x, y, *, raio_m=70.0, janela_m=80.0, buffer_m=12.0):
    """Devolve dict: rua, comprimento_frente_m, n_edificios, fonte_cercea, moda."""
    ei = eixo_no_ponto(x, y, raio_m=raio_m, janela_m=janela_m)
    if ei is None:
        return {"erro": "sem ruas Overture no raio", "moda_cercea_m": None}
    lanco, nome = ei["lanco"], ei["rua"]
    P = Point(x, y)
    edif = overture.edificado_bbox(_bbox_wgs84(x, y, raio_m))
    if edif.empty:
        return {"rua": nome, "moda_cercea_m": None, "erro": "sem edificado"}

    # corredor unilateral para o lado do ponto
    dist = buffer_m * _lado_sinal(lanco, P)
    corredor = lanco.buffer(dist, single_sided=True)
    sel = edif[edif.geometry.intersects(corredor)]

    import lidar
    lidar_ok = lidar.disponivel()
    frentes = []
    n_l = n_h = n_f = 0
    for _, r in sel.iterrows():
        g = r.geometry
        if g.geom_type == "MultiPolygon":
            g = max(g.geoms, key=lambda p: p.area)
        cercea = lidar.altura_no_poligono(g) if lidar_ok else None
        if cercea is not None:
            n_l += 1
        else:  # fallback Overture
            h, nf = r["height"], r["num_floors"]
            if pd.notna(h) and float(h) > 0:
                cercea = float(h); n_h += 1
            elif pd.notna(nf) and float(nf) > 0:
                cercea = float(nf) * PE_DIREITO; n_f += 1
            else:
                continue
        xs = [lanco.project(Point(c)) for c in g.exterior.coords]
        fach = (max(xs) - min(xs)) if xs else 0.0
        if fach > 0:
            frentes.append((cercea, fach))

    res = C.moda_cercea(frentes)
    return {
        "rua": nome,
        "comprimento_frente_m": round(lanco.length, 1),
        "n_edificios": res.n_edificios,
        "fonte_cercea": {"lidar": n_l, "height": n_h, "num_floors": n_f},
        "moda_cercea_m": res.moda_m,
        "distribuicao": res.distribuicao,
        "fracao_moda": round(res.fracao, 2),
    }
