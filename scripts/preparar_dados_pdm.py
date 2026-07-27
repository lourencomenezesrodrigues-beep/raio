"""Reempacota os geopackages do PDM do Porto para a pasta embutida `dados_pdm/`.

A app lê `dados_pdm/qs.gpkg` (Qualificação do Solo — camadas funcional e
operativa) e `dados_pdm/ccgd.gpkg` (Carta de Condicionantes) em vez de
consultar o servidor da CMP em tempo real. Os originais completos (grandes,
não versionados) vivem em `dados/`.

Uso (no venv):
    python scripts/preparar_dados_pdm.py

Fontes originais (opendata.porto.digital):
    dados/po_cqs.gpkg   — Carta de Qualificação do Solo
    dados/po_ccgd.gpkg  — Carta de Condicionantes Geral Dinâmica

Para atualizar quando o PDM mudar: voltar a descarregar os dois ficheiros para
`dados/` e correr este script; depois commit dos `dados_pdm/*.gpkg`.
"""
from __future__ import annotations

import os
import shutil
import sys
import warnings

import geopandas as gpd

warnings.filterwarnings("ignore")

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_QS = os.path.join(RAIZ, "dados", "po_cqs.gpkg")
SRC_CCGD = os.path.join(RAIZ, "dados", "po_ccgd.gpkg")
DST_DIR = os.path.join(RAIZ, "dados_pdm")
DST_QS = os.path.join(DST_DIR, "qs.gpkg")
DST_CCGD = os.path.join(DST_DIR, "ccgd.gpkg")

# só as camadas usadas pela consulta, sem colunas supérfluas
CAMADAS_QS = {
    "PO_QSFUNCIONAL_PL": ["c_espaco", "sc_espaco"],
    "PO_QSOPERATIVA_PL": ["t_espaco"],
}


def main() -> int:
    if not (os.path.exists(SRC_QS) and os.path.exists(SRC_CCGD)):
        print("Faltam os originais em dados/ (po_cqs.gpkg / po_ccgd.gpkg).")
        return 1
    os.makedirs(DST_DIR, exist_ok=True)

    if os.path.exists(DST_QS):
        os.remove(DST_QS)
    for lyr, cols in CAMADAS_QS.items():
        g = gpd.read_file(SRC_QS, layer=lyr)
        g = g[[c for c in cols if c in g.columns] + ["geometry"]]
        g.to_file(DST_QS, layer=lyr, driver="GPKG")
        print(f"  {lyr}: {len(g)} feições")

    shutil.copyfile(SRC_CCGD, DST_CCGD)
    print("qs.gpkg   : %.2f MB" % (os.path.getsize(DST_QS) / 1e6))
    print("ccgd.gpkg : %.2f MB" % (os.path.getsize(DST_CCGD) / 1e6))
    print("OK — commit dos dados_pdm/*.gpkg para o deploy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
