"""Materializa a Carta de Condicionantes Geral Dinâmica (CCGD) num gpkg local.

O open data do Porto não publica a CCGD em geopackage (só WFS/WMS), por isso
descarregamo-la do serviço ArcGIS REST e escrevemo-la em dados/po_ccgd.gpkg,
uma camada por condicionante. CRS EPSG:3763.
"""
from __future__ import annotations

import os
import sys

import geopandas as gpd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "motor"))
import pdm_arcgis as pdm  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "dados", "po_ccgd.gpkg")


def _sanit(name: str) -> str:
    keep = "".join(c if c.isalnum() else "_" for c in name)
    return keep.strip("_")[:60].lower()


def main() -> None:
    if os.path.exists(OUT):
        os.remove(OUT)
    layers = pdm.condicionantes_layers()
    print(f"CCGD: {len(layers)} camadas no serviço\n")
    total = 0
    for lid, name in sorted(layers.items()):
        try:
            fc = pdm.query_layer("CCGD_PUBLICACAO", lid)
        except Exception as e:  # camada pode falhar isoladamente
            print(f"  [{lid:>2}] {name[:55]:<55} ERRO: {e}")
            continue
        feats = fc["features"]
        if not feats:
            print(f"  [{lid:>2}] {name[:55]:<55} 0 feats (vazia, ignorada)")
            continue
        gdf = gpd.GeoDataFrame.from_features(feats, crs="EPSG:3763")
        campos = [c for c in gdf.columns if c != "geometry"]
        gdf.to_file(OUT, layer=_sanit(name), driver="GPKG")
        total += len(gdf)
        print(f"  [{lid:>2}] {name[:55]:<55} {len(gdf):>4} feats | campos: {campos}")
    print(f"\nEscrito: {OUT}  ({total} feições no total)")


if __name__ == "__main__":
    main()
