"""Altura do edificado a partir do LiDAR da DGT (nDSM = MDS − MDT).

Lê os GeoTIFF do Modelo Digital de Superfície (MDS) e do Modelo Digital do
Terreno (MDT) do Levantamento LiDAR de Portugal Continental (DGT, PRR), em
EPSG:3763. Para cada implantação amostra o nDSM e devolve a altura (percentil,
para aproximar a cota do beirado/platibanda, robusto a beirais e ruído).

Como a DGT ainda não oferece WCS/API estável, os ficheiros são descarregados
uma vez do centro de dados (cdd.dgterritorio.gov.pt) para `dados/lidar/`:
qualquer ficheiro com "mds" no nome é tratado como superfície e "mdt" como
terreno (resolução 2 m chega para a cércea). Sem esses ficheiros, o motor usa
o fallback do Overture (num_floors × pé-direito).

Override do diretório para testes: variável de ambiente RAIO_LIDAR_DIR.
"""
from __future__ import annotations

import glob
import os

import numpy as np
from shapely.geometry import Point

_DIR = os.environ.get(
    "RAIO_LIDAR_DIR",
    os.path.join(os.path.dirname(__file__), "..", "dados", "lidar"))
_cache: dict = {}


def _acha(padrao: str) -> str | None:
    for f in sorted(glob.glob(os.path.join(_DIR, "*.tif")) +
                    glob.glob(os.path.join(_DIR, "*.tiff"))):
        if padrao in os.path.basename(f).lower():
            return f
    return None


def _abrir():
    """Devolve (mds_ds, mdt_ds) abertos, ou (None, None)."""
    if "ok" not in _cache:
        import rasterio
        mds_p, mdt_p = _acha("mds"), _acha("mdt")
        if mds_p and mdt_p:
            _cache["mds"] = rasterio.open(mds_p)
            _cache["mdt"] = rasterio.open(mdt_p)
            _cache["ok"] = True
        else:
            _cache["ok"] = False
    if not _cache["ok"]:
        return None, None
    return _cache["mds"], _cache["mdt"]


def disponivel() -> bool:
    return _abrir()[0] is not None


def _amostra(ds, pts):
    v = np.array([s[0] for s in ds.sample(pts)], dtype="float64")
    if ds.nodata is not None:
        v[v == ds.nodata] = np.nan
    return v


def altura_no_poligono(poly, *, passo=2.0, percentil=80, min_pts=3):
    """Altura do edificado (m) sob a implantação `poly` (EPSG:3763), ou None."""
    mds, mdt = _abrir()
    if mds is None:
        return None
    minx, miny, maxx, maxy = poly.bounds
    xs = np.arange(minx, maxx + passo, passo)
    ys = np.arange(miny, maxy + passo, passo)
    pts = [(x, y) for x in xs for y in ys if poly.contains(Point(x, y))]
    if not pts:
        c = poly.representative_point()
        pts = [(c.x, c.y)]
    ndsm = _amostra(mds, pts) - _amostra(mdt, pts)
    ndsm = ndsm[np.isfinite(ndsm)]
    ndsm = ndsm[(ndsm >= 0) & (ndsm < 200)]  # descarta ruído e outliers
    if ndsm.size < min_pts:
        return None
    return round(float(np.percentile(ndsm, percentil)), 1)
