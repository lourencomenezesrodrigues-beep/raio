"""Extrai os edifícios e ruas do concelho do Porto do Overture Maps (S3) para
ficheiros locais embutidos em `dados_pdm/` (EPSG:3763).

A app lê `dados_pdm/edificado.gpkg` e `dados_pdm/ruas.gpkg` para calcular a moda
da cércea e a largura dos arruamentos, sem consultar o S3 em tempo real (lento
e pesado num servidor). Só este script toca no Overture remoto.

Uso (no venv, com ligação à internet):
    python scripts/preparar_dados_overture.py

Actualização: correr de novo quando quiseres um release mais recente do Overture
(define RAIO_OVERTURE_REL) e commit dos dados_pdm/{edificado,ruas}.gpkg.
"""
from __future__ import annotations

import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "motor"))

# bbox do concelho do Porto (WGS84) com margem
BBOX = (-8.710, 41.130, -8.540, 41.190)
DST = os.path.join(RAIZ, "dados_pdm")


def main() -> int:
    # força o caminho S3 (ignora extractos locais, que é o que queremos gerar)
    os.environ.pop("RAIO_PDM_DIR", None)
    import overture
    overture._tem_local = lambda: False  # noqa: SLF001 — gerar a partir do S3

    os.makedirs(DST, exist_ok=True)
    t = time.time()
    print("edifícios (Overture S3)...", flush=True)
    edif = overture.edificado_bbox(BBOX)
    print(f"  {len(edif)} edifícios em {time.time()-t:.0f}s", flush=True)
    edif.to_file(os.path.join(DST, "edificado.gpkg"), layer="edificado", driver="GPKG")

    t = time.time()
    print("ruas (Overture S3)...", flush=True)
    ruas = overture.ruas_bbox(BBOX)
    print(f"  {len(ruas)} segmentos em {time.time()-t:.0f}s", flush=True)
    ruas.to_file(os.path.join(DST, "ruas.gpkg"), layer="ruas", driver="GPKG")

    for f in ("edificado", "ruas"):
        p = os.path.join(DST, f"{f}.gpkg")
        print(f"{f}.gpkg : %.1f MB" % (os.path.getsize(p) / 1e6), flush=True)
    print("OK — commit dos dados_pdm/{edificado,ruas}.gpkg para o deploy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
