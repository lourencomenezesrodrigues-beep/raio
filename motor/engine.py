"""CABE — motor de cálculo (esqueleto de demonstração).

Carrega as regras YAML e calcula o intervalo de capacidade para inputs
sintéticos. A geometria real (parcelas, frentes urbanas, moda da cércea a
partir do edificado) entra na fase seguinte; aqui fixa-se a mecânica das
regras e a rastreabilidade (cada número sai com os ids das regras).
"""
from pathlib import Path
import sys
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

RAIZ = Path(__file__).resolve().parent.parent
PARAMS = yaml.safe_load((RAIZ / "parametros_globais.yaml").read_text(encoding="utf-8"))
PE_DIREITO = float(PARAMS.get("pe_direito_assumido_m", 3.0))


def carregar_regras(*pastas):
    regras = {}
    for pasta in pastas:
        for f in sorted((RAIZ / "regras" / "porto" / pasta).glob("*.yaml")):
            d = yaml.safe_load(f.read_text(encoding="utf-8"))
            regras[d["id"]] = d
    return regras


def arred_multiplo(valor, passo=3.0):
    return round(valor / passo) * passo


def capacidade_fuc1(parcela):
    """parcela: dict com area_m2, frente_m, profundidade_m, moda_cercea_m,
    largura_arruamento_m, uso_habitacao_coletiva (bool),
    empena_confinante_m (opcional), gaveto (bool)."""
    regras = carregar_regras("fuc-1", "transversais")
    aplicadas, notas = [], []

    # cércea: moda (24.1.e, tolerância declarada) vs 45º (rgeu-59)
    moda = arred_multiplo(parcela["moda_cercea_m"])
    aplicadas.append("rpdm-24.1.e")
    cercea = moda
    if parcela.get("largura_arruamento_m"):
        if parcela["largura_arruamento_m"] < cercea:
            cercea = parcela["largura_arruamento_m"]
            aplicadas.append("rgeu-59")
    pisos = int(cercea // PE_DIREITO)

    # profundidade: 25 m (24.1.d), tardoz dominante (24.1.b) fora deste esqueleto
    prof = min(25.0, parcela["profundidade_m"])
    aplicadas.append("rpdm-24.1.d")
    if parcela.get("uso_habitacao_coletiva"):
        corte = max(6.0, cercea / 2.0)
        prof = min(prof, parcela["profundidade_m"] - corte)
        aplicadas.append("rgeu-62")
        if parcela["frente_m"] * corte < 40.0:
            notas.append("rgeu-62: 40 m² livres a tardoz não garantidos")

    # implantação limitada pela impermeabilização/permeabilidade
    implantacao = min(parcela["frente_m"] * prof, 0.7 * parcela["area_m2"])
    aplicadas.extend(["rpdm-25", "rpdm-24.1.c"])

    abc_min = implantacao * pisos

    # limite superior: colmatação de empena (24.1.g)
    abc_max, sup = abc_min, []
    if parcela.get("empena_confinante_m", 0) > cercea:
        pisos_sup = int(arred_multiplo(parcela["empena_confinante_m"]) // PE_DIREITO)
        abc_max = implantacao * pisos_sup
        sup.append("rpdm-24.1.g")
    if parcela.get("gaveto"):
        sup.append("rpdm-24.1.h")
        notas.append("gaveto: dispensa possível de tardoz/profundidade — carece de análise")

    return {
        "cercea_m": cercea, "pisos": pisos,
        "profundidade_util_m": round(prof, 1),
        "implantacao_m2": round(implantacao, 1),
        "abc_min_m2": round(abc_min), "abc_max_m2": round(abc_max),
        "regras_base": aplicadas, "regras_limite_superior": sup,
        "notas": notas,
        "incerteza": ("Limite inferior: aplicação estrita do RPDM. Limite "
                      "superior: excepções cuja aceitação depende de "
                      "apreciação municipal."),
    }


def capacidade_moradia(parcela):
    """Área de Edifícios de Tipo Moradia (RPDM 29.º-30.º).

    parcela: dict com area_m2, frente_m, profundidade_m,
    colmatacao_consolidado (bool, opcional), moda_cercea_m (opcional, só
    relevante em colmatação), uopg (bool, opcional)."""
    regras = carregar_regras("moradia", "transversais")  # noqa: F841
    aplicadas, sup, notas = [], [], []

    # nota interpretativa fundamental (29.º): morfologia, não uso
    notas.append("rpdm-29: «tipo moradia» é morfológico (até 3 pisos + logradouro "
                 "permeável), não obriga ao uso de moradia — admite-se qualquer "
                 "uso compatível do art. 17.º n.º 2")

    # pisos: máx 3 acima do solo, com tecto absoluto de 11 m de fachada [30.1.c]
    pisos = 3
    cercea = min(pisos * PE_DIREITO, 11.0)
    aplicadas.append("rpdm-30.1.c")
    if pisos * PE_DIREITO > 11.0:
        notas.append("rpdm-30.1.c: altura de fachada limitada a 11 m (Newsletter 04/2026)")

    # implantação: tecto de impermeabilização 0,6 da parcela [30.1.b]
    impermeavel_max = 0.6 * parcela["area_m2"]
    aplicadas.append("rpdm-30.1.b")
    if "frente_m" in parcela and "profundidade_m" in parcela:
        implantacao = min(parcela["frente_m"] * parcela["profundidade_m"], impermeavel_max)
    else:
        implantacao = impermeavel_max
    # afastamento dos pisos superiores ao limite: max(altura/2, 3 m) [30.1.d]
    aplicadas.append("rpdm-30.1.d")
    notas.append("rpdm-30.1.d: pisos superiores recuam >= max(altura/2, 3 m) dos "
                 "limites para além do tardoz dos contíguos — encolhe a implantação "
                 "em altura (não quantificado sem geometria da parcela)")

    # alinhamento frontal [30.1.a], excepto parcela > 2000 m² [30.2]
    if parcela["area_m2"] > 2000:
        aplicadas.append("rpdm-30.2")
        notas.append("rpdm-30.2: parcela > 2000 m² — implantação livre (alinhamento "
                     "frontal dispensado, mantendo 0,6 / 3 pisos / afastamentos)")
    else:
        aplicadas.append("rpdm-30.1.a")

    abc_min = implantacao * pisos

    # limite superior: colmatação de conjunto consolidado -> moda da cércea [30.1.c]
    abc_max = abc_min
    if parcela.get("colmatacao_consolidado") and parcela.get("moda_cercea_m"):
        pisos_sup = int(arred_multiplo(parcela["moda_cercea_m"]) // PE_DIREITO)
        if pisos_sup > pisos:
            abc_max = implantacao * pisos_sup
            sup.append("rpdm-30.1.c (colmatação)")
    # UOPG: tecto de pisos pode ser superior [30.3]
    if parcela.get("uopg"):
        sup.append("rpdm-30.3")
        notas.append("rpdm-30.3: parcela em UOPG — nº de pisos pode ser superior no "
                     "âmbito da sua concretização: carece de análise")
    if parcela["area_m2"] < 100:
        notas.append("rpdm-30.1.b: parcela de dimensões muito reduzidas — excepção ao "
                     "índice 0,6 argumentável (sem limiar quantificado)")

    return {
        "cercea_m": cercea, "pisos": pisos,
        "implantacao_m2": round(implantacao, 1),
        "impermeavel_max_m2": round(impermeavel_max, 1),
        "abc_min_m2": round(abc_min), "abc_max_m2": round(abc_max),
        "regras_base": aplicadas, "regras_limite_superior": sup,
        "notas": notas,
        "incerteza": ("Limite inferior: aplicação estrita do RPDM. Limite "
                      "superior: excepções cuja aceitação depende de "
                      "apreciação municipal."),
    }


# despacho categoria -> função de capacidade
_CAPACIDADE = {
    "frente_urbana_continua_tipo_I": capacidade_fuc1,
    "edificios_tipo_moradia": capacidade_moradia,
}

# condicionantes de âmbito municipal (aparecem em quase todos os pontos)
_COND_AMBITO_MUNICIPAL = {"Área de Intervenção do Plano"}


def _condicionantes_para_avisos(condicionantes):
    efetivas, municipais, avisos = [], [], []
    for c in condicionantes or []:
        camada = c.get("camada") or ""
        item = {"camada": camada, "designacao": c.get("designacao"),
                "legislacao": c.get("legislacao")}
        if camada in _COND_AMBITO_MUNICIPAL:
            municipais.append(item)
            continue
        efetivas.append(item)
        cl = camada.lower()
        if "patrimón" in cl or "patrimon" in cl or "imóveis classificados" in cl:
            avisos.append(f"aviso patrimonial: {camada}"
                          + (f" — {c.get('designacao')}" if c.get("designacao") else ""))
        elif "hídric" in cl or "hidric" in cl or "domínio público" in cl:
            avisos.append(f"servidão/domínio: {camada}")
        elif "servidão" in cl or "servidao" in cl or "non aedificandi" in cl:
            avisos.append(f"servidão: {camada}")
    return efetivas, municipais, avisos


def analisar_ponto(x, y, parcela=None, consulta=None, auto_moda=False):
    """Liga a consulta por ponto (EPSG:3763) ao motor de regras.

    Resolve a categoria de solo, encaminha para as regras dessa categoria e
    devolve o intervalo de capacidade + condicionantes traduzidas em avisos.
    `parcela` fornece as dimensões (área/frente/profundidade/moda) enquanto a
    camada de parcelas não está ligada. `consulta` permite injectar um
    resultado de consultar_ponto já obtido (evita a rede em testes).
    `auto_moda=True` calcula a moda da cércea da frente a partir do Overture
    (motor.frente) e preenche `moda_cercea_m` se a parcela não o trouxer.
    """
    if consulta is None:
        import pdm_arcgis
        consulta = pdm_arcgis.consultar_ponto(x, y)

    slug = consulta.get("categoria_slug")
    cat = consulta.get("categoria") or {}
    efetivas, municipais, avisos = _condicionantes_para_avisos(consulta.get("condicionantes"))

    out = {
        "ponto": {"x": x, "y": y},
        "categoria": cat.get("sc_espaco"),
        "categoria_cod": cat.get("sc_espaco_cod"),
        "categoria_slug": slug,
        "operativa": (consulta.get("operativa") or {}).get("t_espaco"),
        "condicionantes_efetivas": efetivas,
        "condicionantes_ambito_municipal": municipais,
        "avisos": avisos,
        "frente": None,
        "capacidade": None,
        "estado": None,
    }

    fn = _CAPACIDADE.get(slug)
    if fn is None:
        out["estado"] = (f"categoria sem regras CABE implementadas "
                         f"({cat.get('sc_espaco') or 'fora do solo qualificado'})"
                         f" — carece de análise")
        return out
    if parcela is None:
        out["estado"] = ("categoria coberta; forneça a parcela "
                         "(area_m2, frente_m, profundidade_m, moda_cercea_m) "
                         "para calcular o intervalo")
        return out

    if auto_moda:
        import frente as _frente
        finfo = _frente.frente_no_ponto(x, y)
        out["frente"] = finfo
        if finfo.get("moda_cercea_m") and not parcela.get("moda_cercea_m"):
            parcela = {**parcela, "moda_cercea_m": finfo["moda_cercea_m"]}

    out["capacidade"] = fn(parcela)
    out["estado"] = "ok"
    return out


def analisar_parcela(poligono, *, auto_moda=True, extra=None, consulta=None):
    """Análise a partir do polígono da parcela (EPSG:3763, shapely ou WKT).

    Deriva área/frente/profundidade do polígono (motor.parcela), resolve a
    categoria no centróide e calcula o intervalo. `extra` acrescenta campos à
    parcela (ex.: uso_habitacao_coletiva, colmatacao_consolidado, gaveto).
    """
    import parcela as _parcela
    from shapely import wkt as _wkt
    poly = _wkt.loads(poligono) if isinstance(poligono, str) else poligono
    c = poly.centroid
    parcela, metricas = _parcela.parcela_para_engine(poly, extra=extra)
    out = analisar_ponto(c.x, c.y, parcela, consulta=consulta, auto_moda=auto_moda)
    out["parcela_metricas"] = metricas
    return out


if __name__ == "__main__":
    from pprint import pprint
    print("### FUC-I (inputs sintéticos)")
    exemplo = dict(area_m2=300, frente_m=10, profundidade_m=30,
                   moda_cercea_m=16.4, largura_arruamento_m=12,
                   uso_habitacao_coletiva=True, empena_confinante_m=18)
    pprint(capacidade_fuc1(exemplo))
    print("\n### Moradia (inputs sintéticos)")
    pprint(capacidade_moradia(dict(area_m2=400, frente_m=12, profundidade_m=15)))
