"""Acesso ao Overture Maps via DuckDB (parquet no S3), filtrado por bbox.

Devolve GeoDataFrames já reprojectados para EPSG:3763. Usado pelo cálculo da
moda da cércea (frente urbana) e pelos scripts.
"""
from __future__ import annotations

import geopandas as gpd
from shapely import wkt

import os
# Release do Overture. Actualizável sem tocar no código via RAIO_OVERTURE_REL,
# porque os releases antigos acabam por ser removidos do bucket.
REL = os.environ.get("RAIO_OVERTURE_REL", "2026-07-22.0")
_BLD = f"s3://overturemaps-us-west-2/release/{REL}/theme=buildings/type=building/*.parquet"
_SEG = f"s3://overturemaps-us-west-2/release/{REL}/theme=transportation/type=segment/*.parquet"

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
    df = _con().execute(f"""
        SELECT id, height, num_floors, ST_AsText(geometry) AS wkt
        FROM read_parquet('{_BLD}') WHERE {_bb(bbox)}
    """).fetchdf()
    return _to_gdf(df)
