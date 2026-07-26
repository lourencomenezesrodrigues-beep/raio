"""Moda da cércea de uma frente urbana no Porto, a partir do Overture Maps.

Passos:
  1. Descarrega do Overture (via DuckDB/S3) o eixo da rua escolhida e o
     edificado numa bbox.
  2. Isola UMA frente (um lado da rua) com um buffer unilateral do eixo.
  3. Para cada edifício: extensão de fachada = projeção da implantação no eixo;
     cércea = height (se existir) senão num_floors x pé-direito (3 m).
  4. Aplica motor.cercea.moda_cercea (ponderação por fachada, passo 3 m).

Uso: python scripts/moda_cercea.py
Escreve dados/frente_<rua>.geojson para inspeção visual.
"""
from __future__ import annotations

import os
import sys

import duckdb
import geopandas as gpd
import pandas as pd
from shapely import wkt
from shapely.geometry import LineString, Point
from shapely.ops import linemerge, unary_union

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "motor"))
import cercea as C  # noqa: E402

REL = "2026-07-22.0"
PE_DIREITO = 3.0

# --- frente escolhida -------------------------------------------------------
RUA = "Rua de Santa Catarina"
BBOX = (-8.6086, 41.1452, -8.6066, 41.1492)  # xmin, ymin, xmax, ymax (WGS84)
LADO = "esquerdo"   # 'esquerdo' (buffer +) ou 'direito' (buffer -) na direção do eixo
BUFFER_M = 12.0     # profundidade do corredor de seleção da frente

BLD = f"s3://overturemaps-us-west-2/release/{REL}/theme=buildings/type=building/*.parquet"
SEG = f"s3://overturemaps-us-west-2/release/{REL}/theme=transportation/type=segment/*.parquet"


def _con():
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;")
    con.execute("SET s3_region='us-west-2';")
    return con


def carregar(con, bbox):
    xmin, ymin, xmax, ymax = bbox
    bb = (f"bbox.xmin BETWEEN {xmin} AND {xmax} AND "
          f"bbox.ymin BETWEEN {ymin} AND {ymax}")

    seg = con.execute(f"""
        SELECT names.primary AS nome, class,
               ST_AsText(geometry) AS wkt
        FROM read_parquet('{SEG}')
        WHERE {bb} AND subtype='road' AND names.primary = '{RUA}'
    """).fetchdf()

    bld = con.execute(f"""
        SELECT id, height, num_floors,
               ST_AsText(geometry) AS wkt
        FROM read_parquet('{BLD}')
        WHERE {bb}
    """).fetchdf()
    return seg, bld


def to_gdf(df):
    df = df[df["wkt"].notna()].copy()
    df["geometry"] = df["wkt"].map(wkt.loads)
    return gpd.GeoDataFrame(df.drop(columns="wkt"), geometry="geometry", crs="EPSG:4326").to_crs(3763)


def frontage_no_eixo(eixo: LineString, geom) -> float:
    """Extensão da fachada = amplitude da projeção da implantação no eixo."""
    if geom.geom_type == "MultiPolygon":
        geom = max(geom.geoms, key=lambda p: p.area)
    xs = [eixo.project(Point(c)) for c in geom.exterior.coords]
    return max(xs) - min(xs) if xs else 0.0


def main():
    con = _con()
    print(f"Frente: {RUA}  | release Overture {REL}")
    seg, bld = carregar(con, BBOX)
    print(f"  segmentos do eixo: {len(seg)} | edifícios na bbox: {len(bld)}")
    if seg.empty:
        print("  !! rua não encontrada no Overture para esta bbox — ajustar RUA/BBOX")
        return

    gseg = to_gdf(seg)
    gbld = to_gdf(bld)

    eixo = linemerge(unary_union(list(gseg.geometry)))
    if eixo.geom_type == "MultiLineString":
        eixo = max(eixo.geoms, key=lambda l: l.length)
    print(f"  comprimento do eixo (um lanço): {eixo.length:.1f} m")

    # corredor unilateral -> uma frente
    dist = BUFFER_M if LADO == "esquerdo" else -BUFFER_M
    corredor = eixo.buffer(dist, single_sided=True)
    sel = gbld[gbld.geometry.intersects(corredor)].copy()
    print(f"  edifícios na frente ({LADO}): {len(sel)}")

    # cércea + fachada por edifício
    frentes = []
    bins_col, fonte_col = [], []
    n_h, n_f, n_nada = 0, 0, 0
    for _, r in sel.iterrows():
        h = r["height"]
        nf = r["num_floors"]
        if pd.notna(h) and float(h) > 0:
            cercea, fonte = float(h), "height"
            n_h += 1
        elif pd.notna(nf) and float(nf) > 0:
            cercea, fonte = float(nf) * PE_DIREITO, "num_floors*3"
            n_f += 1
        else:
            bins_col.append(None); fonte_col.append(None); n_nada += 1
            continue
        fach = frontage_no_eixo(eixo, r.geometry)
        bins_col.append(C.bin_cercea(cercea)); fonte_col.append(fonte)
        if fach > 0:
            frentes.append((cercea, fach))

    print(f"  fonte da cércea: {n_h} por height, {n_f} por num_floors, {n_nada} sem dados (excluídos)")

    res = C.moda_cercea(frentes)
    print("\n  Distribuição (cércea 3 m -> fachada somada):")
    for b, f in res.distribuicao:
        marca = "  <== MODA" if b == res.moda_m else ""
        print(f"     {b:>5.0f} m : {f:7.1f} m de fachada{marca}")
    print(f"\n  >>> MODA DA CÉRCEA = {res.moda_m:.0f} m"
          f"  ({res.fachada_moda_m:.0f} de {res.fachada_total_m:.0f} m de fachada,"
          f" {res.fracao*100:.0f}%; {res.n_edificios} edifícios)")

    # contraste: moda por CONTAGEM de edifícios (o que a definição NÃO quer)
    from collections import Counter
    cont = Counter(b for b in bins_col if b is not None)
    if cont:
        moda_cont = cont.most_common(1)[0]
        if moda_cont[0] != res.moda_m:
            print(f"  (nota: por nº de edifícios a moda seria {moda_cont[0]:.0f} m "
                  f"[{moda_cont[1]} edifícios] — a ponderação por fachada é o critério legal)")

    # inspeção visual
    out = os.path.join(os.path.dirname(__file__), "..", "dados", "frente_santa_catarina.geojson")
    sel_out = sel.copy()
    sel_out["cercea_bin"] = bins_col
    sel_out["fonte_cercea"] = fonte_col
    sel_out.to_crs(4326).to_file(out, driver="GeoJSON")
    print(f"\n  frente exportada para {os.path.relpath(out)}")


if __name__ == "__main__":
    main()
