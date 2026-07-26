"""Testa consultar_ponto() (EPSG:3763) com pontos no Porto.

- Baixa (Praça da Liberdade), a partir de WGS84.
- Um ponto representativo de FUC-I e outro de Moradia, extraídos do gpkg da
  Qualificação do Solo, para demonstrar o mapeamento categoria -> slug de regras.
"""
from __future__ import annotations

import os
import sys

from pyproj import Transformer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "motor"))
import pdm_arcgis as pdm  # noqa: E402

GPKG = os.path.join(os.path.dirname(__file__), "..", "dados", "po_cqs.gpkg")
to3763 = Transformer.from_crs("EPSG:4326", "EPSG:3763", always_xy=True)


def ponto_categoria(label: str) -> tuple[float, float]:
    """Ponto interior de um polígono com sc_espaco == label (no gpkg)."""
    from pyogrio import read_dataframe
    gdf = read_dataframe(GPKG, layer="PO_QSFUNCIONAL_PL")
    sel = gdf[gdf["sc_espaco"] == label]
    p = sel.geometry.iloc[0].representative_point()
    return p.x, p.y


def mostrar(nome: str, x: float, y: float) -> None:
    print("=" * 72)
    print(f"{nome}   (x={x:.2f}, y={y:.2f} EPSG:3763)")
    r = pdm.consultar_ponto(x, y)
    cat = r["categoria"] or {}
    op = r["operativa"] or {}
    print(f"  categoria (c_espaco) : {cat.get('c_espaco')!r}  [{cat.get('c_espaco_cod')}]")
    print(f"  subcategoria (sc)    : {cat.get('sc_espaco')!r}  [{cat.get('sc_espaco_cod')}]")
    print(f"  operativa (t_espaco) : {op.get('t_espaco')!r}")
    print(f"  -> categoria_slug    : {r['categoria_slug']!r}")
    print(f"  -> regras_aplicaveis : {r['regras_aplicaveis']}")
    print(f"  condicionantes ({len(r['condicionantes'])}):")
    for c in r["condicionantes"]:
        d = f" — {c['designacao']}" if c["designacao"] else ""
        leg = f"  [{c['legislacao']}]" if c["legislacao"] else ""
        print(f"     · {c['camada']}{d}{leg}")
    if not r["condicionantes"]:
        print("     (nenhuma)")
    print()


def main() -> None:
    # 1) Baixa a partir de WGS84
    x, y = to3763.transform(-8.61079, 41.14574)
    mostrar("Praça da Liberdade (Baixa)", x, y)

    # 2) FUC-I e Moradia a partir do gpkg
    for nome, label in [
        ("Ponto em FUC tipo I", "Área de frente urbana contínua de tipo I"),
        ("Ponto em Moradia", "Área de edifícios de tipo moradia"),
    ]:
        x, y = ponto_categoria(label)
        mostrar(nome, x, y)


if __name__ == "__main__":
    main()
