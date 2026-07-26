"""Demonstra engine.analisar_ponto: ponto -> categoria -> regras + condicionantes."""
from __future__ import annotations

import os
import sys

from pyproj import Transformer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "motor"))
import engine  # noqa: E402
import pdm_arcgis as pdm  # noqa: E402

GPKG = os.path.join(os.path.dirname(__file__), "..", "dados", "po_cqs.gpkg")
to3763 = Transformer.from_crs("EPSG:4326", "EPSG:3763", always_xy=True)


def ponto_categoria(label):
    from pyogrio import read_dataframe
    gdf = read_dataframe(GPKG, layer="PO_QSFUNCIONAL_PL")
    p = gdf[gdf["sc_espaco"] == label].geometry.iloc[0].representative_point()
    return p.x, p.y


def mostrar(titulo, r):
    print("=" * 72)
    print(titulo)
    print(f"  categoria : {r['categoria']!r}  slug={r['categoria_slug']!r}")
    print(f"  operativa : {r['operativa']!r}")
    print(f"  estado    : {r['estado']}")
    if r["avisos"]:
        print("  avisos:")
        for a in r["avisos"]:
            print(f"     ! {a}")
    if r["condicionantes_efetivas"]:
        print("  condicionantes efetivas:", [c["camada"] for c in r["condicionantes_efetivas"]])
    cap = r["capacidade"]
    if cap:
        print(f"  >> cércea {cap['cercea_m']} m | {cap['pisos']} pisos | "
              f"implantação {cap['implantacao_m2']} m² | "
              f"ABC {cap['abc_min_m2']}–{cap['abc_max_m2']} m²")
        print(f"     regras base: {cap['regras_base']}")
    print()


def main():
    # 1) Baixa: infra + património -> sem regras, mas avisos
    x, y = to3763.transform(-8.61079, 41.14574)
    mostrar("Praça da Liberdade (Baixa)", engine.analisar_ponto(x, y))

    # 2) FUC-I com parcela sintética
    x, y = ponto_categoria("Área de frente urbana contínua de tipo I")
    parcela = dict(area_m2=300, frente_m=10, profundidade_m=30,
                   moda_cercea_m=16.4, largura_arruamento_m=12,
                   uso_habitacao_coletiva=True)
    mostrar("FUC-I + parcela", engine.analisar_ponto(x, y, parcela))

    # 3) Moradia com parcela sintética
    x, y = ponto_categoria("Área de edifícios de tipo moradia")
    mostrar("Moradia + parcela", engine.analisar_ponto(
        x, y, dict(area_m2=400, frente_m=12, profundidade_m=15)))


if __name__ == "__main__":
    main()
