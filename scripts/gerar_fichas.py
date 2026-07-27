"""Gera fichas de exemplo (Markdown + HTML com mapas) para saidas/.

- FUC-I: parcela sintética sobre um ponto FUC-I (com cálculo de capacidade).
- Baixa: ponto na Praça da Liberdade (categoria sem regras, rico em condicionantes).
Também monta saidas/ficha_showcase.html (os dois exemplos numa página).
"""
from __future__ import annotations

import os
import sys

from pyproj import Transformer
from pyogrio import read_dataframe
from shapely.geometry import box

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "motor"))
import engine  # noqa: E402
import ficha  # noqa: E402

RAIZ = os.path.join(os.path.dirname(__file__), "..")
SAIDAS = os.path.join(RAIZ, "saidas")
GPKG = os.path.join(RAIZ, "dados", "po_cqs.gpkg")
os.makedirs(SAIDAS, exist_ok=True)


def gerar():
    g = read_dataframe(GPKG, layer="PO_QSFUNCIONAL_PL")
    c = g[g["sc_espaco"] == "Área de frente urbana contínua de tipo I"] \
        .geometry.iloc[0].representative_point()
    poly = box(c.x - 6, c.y - 12, c.x + 6, c.y + 12)
    fuc1 = engine.analisar_parcela(
        poly, extra=dict(uso_habitacao_coletiva=True, empena_confinante_m=18), auto_moda=True)

    x, y = Transformer.from_crs(4326, 3763, always_xy=True).transform(-8.61079, 41.14574)
    baixa = engine.analisar_ponto(x, y)

    for nome, res in (("fuc1", fuc1), ("baixa", baixa)):
        html = ficha.ficha_html(res, com_mapas=True)
        open(os.path.join(SAIDAS, f"ficha_{nome}.html"), "w", encoding="utf-8").write(html)
        md = ficha.ficha_markdown(res)
        open(os.path.join(SAIDAS, f"ficha_{nome}.md"), "w", encoding="utf-8").write(md)
        print(f"ficha_{nome}: {len(html)} bytes html")

    # showcase (dois exemplos, estilo incluído uma vez)
    frag1 = ficha.ficha_html(fuc1, fragment=True, com_mapas=True)
    estilo = frag1[:frag1.index("</style>") + len("</style>")]
    main1 = frag1[frag1.index("<main"):]
    main2 = ficha.ficha_html(baixa, fragment=True, com_mapas=True)
    main2 = main2[main2.index("<main"):]
    intro = '''
<style>
 .showcase-head{max-width:760px;margin:8px auto 4px;}
 .showcase-head .t{font-family:var(--font-mono);font-weight:700;text-transform:uppercase;font-size:20px;letter-spacing:.02em;color:var(--ink);margin:2px 0 2px;}
 .showcase-head .d{color:var(--muted);font-size:13px;max-width:60ch;}
 .ex-label{max-width:760px;margin:44px auto 10px;display:flex;align-items:center;gap:12px;}
 .ex-label .pill{font-family:var(--font-mono);font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--accent);border:1px solid var(--accent);border-radius:2px;padding:3px 9px;}
 .ex-label .h{height:1px;background:var(--line);flex:1;}
</style>
<div class="showcase-head">
 <div class="eyebrow">CABE · desenho do output</div>
 <div class="t">Ficha de capacidade construtiva</div>
 <div class="d">Dois exemplos reais gerados pelo motor. Capa, condicionantes (com recorte de mapa), capacidade e conclusão.</div>
</div>
'''
    lab1 = '<div class="ex-label"><span class="pill">Exemplo 1 — FUC tipo I</span><span class="h"></span></div>'
    lab2 = '<div class="ex-label"><span class="pill">Exemplo 2 — Baixa · carece de análise</span><span class="h"></span></div>'
    page = estilo + intro + lab1 + main1 + lab2 + main2
    open(os.path.join(SAIDAS, "ficha_showcase.html"), "w", encoding="utf-8").write(page)
    print(f"showcase: {len(page)} bytes")


if __name__ == "__main__":
    gerar()
