"""Acesso ao Overture Maps.

Por omissão lê extractos LOCAIS do Porto (edifícios + ruas) embutidos em
`dados_pdm/` — rápido, sem rede, e alojável em qualquer host. Se esses
ficheiros não existirem, recorre ao Overture no S3 via DuckDB (usado só para
gerar os extractos com `scripts/preparar_dados_overture.py`).

Devolve GeoDataFrames já em EPSG:3763. Usado pelo cálculo da moda da cércea.
"""
from __future__ import annotations

import os

import geopandas as gpd
from shapely import wkt

# Release do Overture. Actualizável sem tocar no código via RAIO_OVERTURE_REL,
# porque os releases antigos acabam por ser removidos do bucket.
REL = os.environ.get("RAIO_OVERTURE_REL", "2026-07-22.0")
_BLD = f"s3://overturemaps-us-west-2/release/{REL}/theme=buildings/type=building/*.parquet"
_SEG = f"s3://overturemaps-us-west-2/release/{REL}/theme=transportation/type=segment/*.parquet"

# Extractos locais do Porto (em EPSG:3763). Preferidos quando presentes.
_DIR = os.environ.get("RAIO_PDM_DIR") or os.path.join(
    os.path.dirname(__file__), "..", "dados_pdm")
_EDIF_LOCAL = os.path.join(_DIR, "edificado.gpkg")
_RUAS_LOCAL = os.path.join(_DIR, "ruas.gpkg")


def _tem_local() -> bool:
    return os.path.exists(_EDIF_LOCAL) and os.path.exists(_RUAS_LOCAL)


def _bbox_3763(bbox):
    """Converte uma bbox WGS84 (lon/lat) para EPSG:3763 (para filtrar os gpkg)."""
    from pyproj import Transformer
    t = Transformer.from_crs(4326, 3763, always_xy=True)
    xmin, ymin, xmax, ymax = bbox
    xs, ys = [], []
    for lon, lat in [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)]:
        x, y = t.transform(lon, lat)
        xs.append(x); ys.append(y)
    return (min(xs), min(ys), max(xs), max(ys))


_con_cache = {}


def _con():
    if "c" not in _con_cache:
        import duckdb
        c = duckdb.connect()
        c.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;")
        c.execute("SET s3_region='us-west-2';")
        _con_cache["c"] = c
    return _con_cache["c"]


def _bb(bbox):
    xmin, ymin, xmax, ymax = bbox
    return (f"bbox.xmin BETWEEN {xmin} AND {xmax} AND "
            f"bbox.ymin BETWEEN {ymin} AND {ymax}")


def _to_gdf(df):
    df = df[df["wkt"].notna()].copy()
    if df.empty:
        return gpd.GeoDataFrame(df.drop(columns="wkt", errors="ignore"),
                                geometry=[], crs="EPSG:3763")
    df["geometry"] = df["wkt"].map(wkt.loads)
    return (gpd.GeoDataFrame(df.drop(columns="wkt"), geometry="geometry",
                             crs="EPSG:4326").to_crs(3763))


def ruas_bbox(bbox, nome: str | None = None) -> gpd.GeoDataFrame:
    """Segmentos rodoviários (transportation) na bbox WGS84; opcional filtro por nome."""
    if _tem_local():
        g = gpd.read_file(_RUAS_LOCAL, layer="ruas", bbox=_bbox_3763(bbox))
        if nome and not g.empty and "nome" in g.columns:
            g = g[g["nome"] == nome]
        return g
    cond = _bb(bbox) + " AND subtype='road'"
    if nome:
        cond += f" AND names.primary = '{nome}'"
    df = _con().execute(f"""
        SELECT names.primary AS nome, class, ST_AsText(geometry) AS wkt
        FROM read_parquet('{_SEG}') WHERE {cond}
    """).fetchdf()
    return _to_gdf(df)


def edificado_bbox(bbox) -> gpd.GeoDataFrame:
    """Edifícios (buildings) na bbox WGS84, com height e num_floors."""
    if _tem_local():
        return gpd.read_file(_EDIF_LOCAL, layer="edificado", bbox=_bbox_3763(bbox))
    df = _con().execute(f"""
        SELECT id, height, num_floors, ST_AsText(geometry) AS wkt
        FROM read_parquet('{_BLD}') WHERE {_bb(bbox)}
    """).fetchdf()
    return _to_gdf(df)
