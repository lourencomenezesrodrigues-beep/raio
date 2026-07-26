"""Ficha de capacidade construtiva (análise não vinculativa) em Markdown.

Compõe o resultado de engine.analisar_parcela / analisar_ponto num documento
legível. Ordem pedida: identificação, CONDICIONANTES primeiro, capacidade,
regras, e a CONCLUSÃO no fim (com a frase de incerteza obrigatória).
"""
from __future__ import annotations

import html
from pathlib import Path

FRASE_INCERTEZA = (
    "O limite inferior corresponde à aplicação estrita do RPDM; o limite "
    "superior a excepções previstas no regulamento cuja aceitação depende de "
    "apreciação municipal."
)


def _fmt(v, suf=""):
    if v is None:
        return "—"
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return f"{v}{suf}"


def ficha_markdown(res: dict) -> str:
    L = []
    cat = res.get("categoria") or "—"
    cod = res.get("categoria_cod")
    p = res.get("ponto", {})
    met = res.get("parcela_metricas") or {}
    rua = met.get("rua") or (res.get("frente") or {}).get("rua")

    # --- Identificação -----------------------------------------------------
    L.append("# Ficha de capacidade construtiva")
    L.append("_Análise não vinculativa — concelho do Porto (CABE)_\n")
    ident = []
    if rua:
        ident.append(f"**Frente urbana:** {rua}")
    if p:
        ident.append(f"**Ponto (EPSG:3763):** {p.get('x'):.1f}, {p.get('y'):.1f}"
                     if p.get("x") is not None else "")
    ident.append(f"**Categoria de solo:** {cat}" + (f" (`{cod}`)" if cod else ""))
    if res.get("operativa"):
        ident.append(f"**Estado operativo:** {res['operativa']}")
    if met:
        ident.append(f"**Parcela:** {_fmt(met.get('area_m2'),' m²')} · "
                     f"frente {_fmt(met.get('frente_m'),' m')} · "
                     f"profundidade {_fmt(met.get('profundidade_m'),' m')}")
    L.append("  \n".join(x for x in ident if x) + "\n")

    # --- Condicionantes (primeiro) ----------------------------------------
    L.append("## Condicionantes")
    efet = res.get("condicionantes_efetivas") or []
    avisos = res.get("avisos") or []
    munic = res.get("condicionantes_ambito_municipal") or []
    if avisos:
        L.append("**Avisos**")
        for a in avisos:
            L.append(f"- ⚠ {a}")
        L.append("")
    if efet:
        L.append("**Servidões e restrições que impendem sobre o ponto**")
        for c in efet:
            leg = f" — _{c['legislacao']}_" if c.get("legislacao") else ""
            des = f": {c['designacao']}" if c.get("designacao") else ""
            L.append(f"- {c['camada']}{des}{leg}")
        L.append("")
    if not efet and not avisos:
        L.append("_Sem servidões ou restrições registadas no ponto._\n")
    if munic:
        L.append("**De âmbito municipal** (aplicam-se a toda a área do plano)")
        for c in munic:
            L.append(f"- {c['camada']}")
        L.append("")

    # --- Capacidade construtiva -------------------------------------------
    cap = res.get("capacidade")
    L.append("## Capacidade construtiva estimada")
    if cap:
        L.append("| Parâmetro | Limite inferior | Limite superior |")
        L.append("|---|---:|---:|")
        L.append(f"| Cércea | {_fmt(cap.get('cercea_m'),' m')} | — |")
        L.append(f"| Pisos | {_fmt(cap.get('pisos'))} | — |")
        L.append(f"| Implantação | {_fmt(cap.get('implantacao_m2'),' m²')} | — |")
        amax = cap.get("abc_max_m2")
        amin = cap.get("abc_min_m2")
        L.append(f"| ABC | **{_fmt(amin,' m²')}** | "
                 f"**{_fmt(amax,' m²')}**"
                 f"{' _(= inferior)_' if amax == amin else ''} |")
        L.append("")
        fr = res.get("frente") or {}
        if fr.get("moda_cercea_m") is not None:
            fonte = fr.get("fonte_cercea") or {}
            origem = ("medida (Overture)" if fonte.get("height")
                      else "estimada de nº de pisos (Overture)")
            L.append(f"Moda da cércea da frente: **{_fmt(fr['moda_cercea_m'],' m')}** "
                     f"— {origem}, {fr.get('n_edificios','?')} edifícios "
                     f"({fr.get('comprimento_frente_m','?')} m de frente analisada).\n")
    else:
        L.append(f"**{res.get('estado','—')}**\n")

    # --- Regras aplicadas --------------------------------------------------
    if cap:
        L.append("## Regras aplicadas")
        base = cap.get("regras_base") or []
        sup = cap.get("regras_limite_superior") or []
        if base:
            L.append(f"- **Base (limite inferior):** {', '.join(base)}")
        if sup:
            L.append(f"- **Limite superior:** {', '.join(sup)}")
        for n in cap.get("notas") or []:
            L.append(f"- _Nota:_ {n}")
        L.append("")

    # --- Conclusão (no fim) -----------------------------------------------
    L.append("## Conclusão")
    if cap:
        amin, amax = cap.get("abc_min_m2"), cap.get("abc_max_m2")
        intervalo = (f"cerca de **{_fmt(amin,' m²')} de ABC**"
                     if amax == amin else
                     f"entre **{_fmt(amin,' m²')}** e **{_fmt(amax,' m²')} de ABC**")
        L.append(f"Em {cat}, a parcela admite {intervalo} "
                 f"({_fmt(cap.get('pisos'))} pisos, cércea "
                 f"{_fmt(cap.get('cercea_m'),' m')}), na aplicação estrita do RPDM.")
        if avisos:
            L.append(f"\nAtenção às condicionantes assinaladas acima "
                     f"({len(avisos)} aviso(s)), que podem restringir o envelope.")
    else:
        L.append(f"A categoria de solo do ponto ({cat}) não é coberta pelas "
                 f"regras CABE implementadas — **carece de análise**. As "
                 f"condicionantes acima mantêm-se relevantes.")
    L.append(f"\n> {FRASE_INCERTEZA}")
    L.append("\n_Não substitui pedido de informação prévia nem consulta dos "
             "serviços municipais._")

    return "\n".join(L)


# ---------------------------------------------------------------------------
# Render HTML (output desenhado da app) — usa motor/ficha_template.html
# ---------------------------------------------------------------------------
_TEMPLATE = Path(__file__).resolve().parent / "ficha_template.html"


def _e(s) -> str:
    return html.escape(str(s)) if s is not None else ""


def _warn(camada: str) -> bool:
    cl = (camada or "").lower()
    chaves = ("patrimón", "patrimon", "imóveis classificados", "hídric", "hidric",
              "domínio público", "servidão", "servidao", "non aedificandi")
    return any(k in cl for k in chaves)


def _num(v, u=""):
    if v is None:
        return "—"
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    us = f'<span class="u">{u}</span>' if u else ""
    return f"{v}{us}"


def ficha_html(res: dict, *, fragment: bool = False) -> str:
    cat = res.get("categoria") or "—"
    cod = res.get("categoria_cod")
    p = res.get("ponto", {})
    met = res.get("parcela_metricas") or {}
    fr = res.get("frente") or {}
    rua = met.get("rua") or fr.get("rua")
    cap = res.get("capacidade")

    out = []

    # cabeçalho + meta
    out.append('<section>')
    out.append('<div class="eyebrow">Análise não vinculativa · CABE — Porto</div>')
    out.append('<h1>Ficha de capacidade construtiva</h1>')
    sub = rua if rua else "Frente urbana sem designação"
    out.append(f'<p class="lede">{_e(sub)}</p>')
    out.append('<dl class="meta">')
    if p and p.get("x") is not None:
        out.append(f'<dt>Ponto 3763</dt><dd><span class="mono">{p["x"]:.1f}, {p["y"]:.1f}</span></dd>')
    out.append(f'<dt>Categoria</dt><dd>{_e(cat)}'
               + (f' <span class="mono">({_e(cod)})</span>' if cod else '') + '</dd>')
    if res.get("operativa"):
        out.append(f'<dt>Operativa</dt><dd>{_e(res["operativa"])}</dd>')
    if met.get("area_m2") is not None:
        out.append('<dt>Parcela</dt><dd><span class="mono">'
                   f'{_num(met.get("area_m2"),"m²")} · frente {_num(met.get("frente_m"),"m")}'
                   f' · prof. {_num(met.get("profundidade_m"),"m")}</span></dd>')
    out.append('</dl>')
    out.append('</section>')

    # condicionantes (primeiro)
    out.append('<section>')
    out.append('<div class="sec-head"><h2>Condicionantes</h2></div>')
    efet = res.get("condicionantes_efetivas") or []
    munic = res.get("condicionantes_ambito_municipal") or []
    if efet:
        out.append('<div class="cond">')
        for c in efet:
            w = _warn(c.get("camada"))
            badge = '<span class="badge">!</span>' if w else ""
            out.append(f'<div class="row {"warn" if w else ""}">')
            out.append(f'<div class="top">{badge}<span class="layer">{_e(c["camada"])}</span></div>')
            if c.get("designacao"):
                out.append(f'<p class="desc">{_e(c["designacao"])}</p>')
            if c.get("legislacao"):
                out.append(f'<div class="leg">{_e(c["legislacao"])}</div>')
            out.append('</div>')
        out.append('</div>')
    else:
        out.append('<p class="empty">Sem servidões ou restrições registadas no ponto.</p>')
    if munic:
        out.append('<div class="municipal"><div class="lbl">Âmbito municipal</div><ul>')
        for c in munic:
            out.append(f'<li>{_e(c["camada"])}</li>')
        out.append('</ul></div>')
    out.append('</section>')

    # capacidade
    out.append('<section>')
    out.append('<div class="sec-head"><h2>Capacidade construtiva estimada</h2></div>')
    if cap:
        amin, amax = cap.get("abc_min_m2"), cap.get("abc_max_m2")
        if amax == amin:
            valor = f'{_num(amin)}<span class="u">m² ABC</span>'
            nota = "Limite único: sem excepção de limite superior aplicável."
        else:
            valor = (f'{_num(amin)}<span class="sep">–</span>{_num(amax)}'
                     f'<span class="u">m² ABC</span>')
            nota = "Intervalo inferior–superior (RPDM estrito → excepção argumentável)."
        out.append('<div class="hero">')
        out.append(f'<div><div class="k">Área bruta de construção</div>'
                   f'<div class="val">{valor}</div></div>')
        out.append(f'<div class="note">{nota}</div>')
        out.append('</div>')
        out.append('<div class="spec">')
        out.append(f'<div class="cell"><div class="k">Cércea</div>'
                   f'<div class="v">{_num(cap.get("cercea_m"),"m")}</div></div>')
        out.append(f'<div class="cell"><div class="k">Pisos</div>'
                   f'<div class="v">{_num(cap.get("pisos"))}</div></div>')
        out.append(f'<div class="cell"><div class="k">Implantação</div>'
                   f'<div class="v">{_num(cap.get("implantacao_m2"),"m²")}</div></div>')
        out.append('</div>')
        if fr.get("moda_cercea_m") is not None:
            fonte = fr.get("fonte_cercea") or {}
            origem = "medida" if fonte.get("height") else "estimada de nº de pisos"
            out.append(f'<p class="moda-note">Moda da cércea da frente: '
                       f'<b>{_num(fr["moda_cercea_m"],"m")}</b> — {origem} (Overture), '
                       f'{_e(fr.get("n_edificios","?"))} edifícios em '
                       f'{_e(fr.get("comprimento_frente_m","?"))} m de frente.</p>')
    else:
        out.append(f'<div class="status">{_e(res.get("estado","—"))}</div>')
    out.append('</section>')

    # regras
    if cap:
        out.append('<section>')
        out.append('<div class="sec-head"><h2>Regras aplicadas</h2></div>')
        base = cap.get("regras_base") or []
        sup = cap.get("regras_limite_superior") or []
        if base:
            out.append('<div class="rgroup"><div class="lbl">Base — limite inferior</div>'
                       '<div class="chips">'
                       + "".join(f'<span class="chip">{_e(r)}</span>' for r in base)
                       + '</div></div>')
        if sup:
            out.append('<div class="rgroup"><div class="lbl">Limite superior</div>'
                       '<div class="chips">'
                       + "".join(f'<span class="chip sup">{_e(r)}</span>' for r in sup)
                       + '</div></div>')
        notas = cap.get("notas") or []
        if notas:
            out.append('<ul class="notas">'
                       + "".join(f'<li>{_e(n)}</li>' for n in notas) + '</ul>')
        out.append('</section>')

    # conclusão
    out.append('<section>')
    out.append('<div class="sec-head"><h2>Conclusão</h2></div>')
    out.append('<div class="verdict">')
    if cap:
        amin, amax = cap.get("abc_min_m2"), cap.get("abc_max_m2")
        if amax == amin:
            intervalo = f'cerca de <span class="num">{_num(amin)} m²</span> de ABC'
        else:
            intervalo = (f'entre <span class="num">{_num(amin)} m²</span> e '
                         f'<span class="num">{_num(amax)} m²</span> de ABC')
        out.append(f'Em {_e(cat)}, a parcela admite {intervalo} '
                   f'(<b>{_num(cap.get("pisos"))}</b> pisos, cércea '
                   f'<b>{_num(cap.get("cercea_m"),"m")}</b>), em aplicação estrita do RPDM.')
        if efet:
            n_w = sum(1 for c in efet if _warn(c.get("camada")))
            if n_w:
                out.append(f' Atenção às {n_w} condicionante(s) assinaladas, '
                           f'que podem restringir o envelope.')
    else:
        out.append(f'A categoria do ponto ({_e(cat)}) não é coberta pelas regras '
                   f'CABE implementadas — <b>carece de análise</b>. As condicionantes '
                   f'acima mantêm-se relevantes.')
    out.append('</div>')
    out.append(f'<p class="uncert">{_e(FRASE_INCERTEZA)}</p>')
    out.append('<div class="disclaimer">Não substitui pedido de informação prévia '
               'nem consulta dos serviços municipais.</div>')
    out.append('</section>')

    content = "\n".join(out)
    tpl = _TEMPLATE.read_text(encoding="utf-8")
    if fragment:
        i0 = tpl.index("<style>")
        i1 = tpl.index("</style>") + len("</style>")
        estilo = tpl[i0:i1]
        return (f"{estilo}\n"
                '<div class="toolbar"><button class="btn" '
                'onclick="window.print()">Imprimir ficha</button></div>\n'
                f'<main class="sheet">\n{content}\n</main>')
    titulo = f"Ficha CABE — {rua or cat}"
    return tpl.replace("{{TITLE}}", _e(titulo)).replace("{{CONTENT}}", content)
