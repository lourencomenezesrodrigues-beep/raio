"""RAIO — motor de cálculo (esqueleto de demonstração).

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


_TODAS_REGRAS = None


def regra(rid):
    """Detalhe de uma norma pelo id (id, norma, diploma, texto, tema) ou None."""
    global _TODAS_REGRAS
    if _TODAS_REGRAS is None:
        _TODAS_REGRAS = {}
        for f in (RAIZ / "regras" / "porto").rglob("*.yaml"):
            d = yaml.safe_load(f.read_text(encoding="utf-8"))
            _TODAS_REGRAS[d["id"]] = d
    return _TODAS_REGRAS.get(rid)


def capacidade_fuc1(parcela):
    """parcela: dict com area_m2, frente_m, profundidade_m, moda_cercea_m,
    largura_arruamento_m, uso_habitacao_coletiva (bool),
    empena_confinante_m (opcional), gaveto (bool)."""
    regras = carregar_regras("fuc-1", "transversais")
    aplicadas, notas = [], []

    # cércea: moda (24.1.e) cortada pela linha dos 45º / largura do arruamento (rgeu-59)
    moda = parcela.get("moda_cercea_m")
    larg = parcela.get("largura_arruamento_m")
    if moda is not None:
        cercea = arred_multiplo(moda)
        aplicadas.append("rpdm-24.1.e")
        if larg and larg < cercea:
            cercea = float(larg)
            aplicadas.append("rgeu-59")
    else:  # sem moda: a largura do arruamento é o tecto (RGEU 59.º / 45.º)
        cercea = float(larg)
        aplicadas.append("rgeu-59")
        notas.append(f"Sem moda da cércea detectada; usada a largura do arruamento "
                     f"({larg:.1f} m) como tecto pela linha dos 45.º (RGEU 59.º).")
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

    # --- ocupação simulada: piso térreo + pisos superiores recuados --------
    area = parcela["area_m2"]
    impermeavel_max = 0.6 * area                          # tecto 0,6 [30.1.b]
    aplicadas.append("rpdm-30.1.b")
    frente = parcela.get("frente_m")
    prof = parcela.get("profundidade_m")
    recuo = max((pisos - 1) * PE_DIREITO / 2.0, 3.0)      # afastamento pisos superiores [30.1.d]
    aplicadas.append("rpdm-30.1.d")

    if frente and prof:
        # piso térreo: faixa frontal; logradouro permeável (>= 0,4) fica a tardoz.
        a_terreo = min(frente * prof * 0.6, impermeavel_max)
        prof_terreo = a_terreo / frente
        # pisos superiores recuam `recuo` dos limites laterais e de tardoz (frente alinhada)
        a_sup = max(frente - 2 * recuo, 0.0) * max(prof_terreo - recuo, 0.0)
        implantacao = a_terreo
        abc_min = a_terreo + a_sup * (pisos - 1)
        notas.append(f"Ocupação simulada: piso térreo {round(a_terreo)} m² à face da rua "
                     f"(impermeabilização 0,6 [30.1.b], logradouro permeável a tardoz); "
                     f"{pisos - 1} pisos superiores recuados {recuo:.0f} m dos limites "
                     f"[30.1.d] = {round(a_sup)} m² cada.")
        # uso de habitação coletiva: a categoria admite-o (29.º) mas os fogos
        # ficam sujeitos ao RGEU art. 62.º — afastamento mínimo ao tardoz
        # (>= metade da cércea, mín. 6 m) para habitabilidade.
        if parcela.get("uso_habitacao_coletiva"):
            aplicadas.append("rgeu-62")
            corte = max(6.0, cercea / 2.0)
            prof_terreo_max = max(prof - corte, 0.0)
            if prof_terreo > prof_terreo_max:
                prof_terreo = prof_terreo_max
                a_terreo = frente * prof_terreo
                implantacao = a_terreo
                a_sup = max(frente - 2 * recuo, 0.0) * max(prof_terreo - recuo, 0.0)
                abc_min = a_terreo + a_sup * (pisos - 1)
                notas.append(f"Uso de habitação coletiva: profundidade do piso térreo "
                             f"limitada a {prof_terreo:.0f} m para garantir {corte:.0f} m de "
                             f"afastamento ao tardoz (RGEU art. 62.º) — implantação e ABC "
                             f"reduzidas em conformidade.")
            else:
                notas.append("Uso de habitação coletiva: admitido (a morfologia «tipo "
                             "moradia» é de forma, não de uso [29.º]); o afastamento ao "
                             "tardoz do RGEU art. 62.º já é satisfeito pela geometria.")
    else:
        implantacao = impermeavel_max
        a_sup = 0.0
        abc_min = impermeavel_max * pisos
        notas.append("Sem geometria da parcela: ABC estimada por 0,6 × área × pisos, "
                     "sem simular os afastamentos.")

    # alinhamento frontal [30.1.a], excepto parcela > 2000 m² [30.2]
    if area > 2000:
        aplicadas.append("rpdm-30.2")
        notas.append("rpdm-30.2: parcela > 2000 m² — implantação livre (alinhamento "
                     "frontal dispensado, mantendo 0,6 / 3 pisos / afastamentos).")
    else:
        aplicadas.append("rpdm-30.1.a")

    # limite superior: colmatação de conjunto consolidado -> moda da cércea [30.1.c]
    abc_max = abc_min
    if parcela.get("colmatacao_consolidado") and parcela.get("moda_cercea_m"):
        pisos_sup = int(arred_multiplo(parcela["moda_cercea_m"]) // PE_DIREITO)
        if pisos_sup > pisos:
            abc_max = implantacao + a_sup * (pisos_sup - 1)
            sup.append("rpdm-30.1.c (colmatação)")
    if parcela.get("uopg"):
        sup.append("rpdm-30.3")
        notas.append("rpdm-30.3: parcela em UOPG — nº de pisos pode ser superior no "
                     "âmbito da sua concretização: carece de análise.")
    if area < 100:
        notas.append("rpdm-30.1.b: parcela de dimensões muito reduzidas — excepção ao "
                     "índice 0,6 argumentável (sem limiar quantificado).")

    return {
        "cercea_m": cercea, "pisos": pisos,
        "implantacao_m2": round(implantacao, 1),
        "area_piso_superior_m2": round(a_sup, 1),
        "impermeavel_max_m2": round(impermeavel_max, 1),
        "abc_min_m2": round(abc_min), "abc_max_m2": round(abc_max),
        "regras_base": aplicadas, "regras_limite_superior": sup,
        "notas": notas,
        "incerteza": ("Limite inferior: aplicação estrita do RPDM (ocupação simulada "
                      "que cumpre impermeabilização, afastamentos e logradouro). Limite "
                      "superior: excepções cuja aceitação depende de apreciação municipal."),
    }


def capacidade_fuc2(parcela):
    """Área de Frente Urbana Contínua de tipo II (RPDM 26.º-28.º).

    Diferenças face à FUC-I: cércea regida pela largura do arruamento [27.1.g]
    com tecto de 21 m se o perfil > 21 m salvo moda superior [27.2.b];
    profundidade máxima de 30 m [27.1.d] (não 25 m); permeabilidade >= 0,3 [28.1].

    parcela: area_m2, frente_m, profundidade_m, largura_arruamento_m (para a
    cércea), moda_cercea_m (opcional, proxy/tecto), uso_habitacao_coletiva,
    empena_confinante_m, gaveto."""
    regras = carregar_regras("fuc-2", "transversais")  # noqa: F841
    aplicadas, sup, notas = [], [], []

    # cércea: largura do arruamento [27.1.g]; tecto 21 m se perfil>21, salvo moda [27.2.b]
    larg = parcela.get("largura_arruamento_m")
    moda = parcela.get("moda_cercea_m")
    if larg is not None:
        cercea = float(larg)
        aplicadas.append("rpdm-27.1.g")
        notas.append(f"Cércea pela largura do arruamento: {larg:.1f} m "
                     f"(perfil transversal medido entre fachadas opostas) [27.1.g].")
        if larg > 21.0:
            cercea = moda if (moda and moda > 21.0) else 21.0
            aplicadas.append("rpdm-27.2.b")
            notas.append("rpdm-27.2.b: arruamento > 21 m — cércea limitada a 21 m "
                         "(salvo moda superior).")
    elif moda is not None:
        cercea = float(moda)
        notas.append("rpdm-27.1.g: sem largura do arruamento medida — usada a moda "
                     "da cércea como proxy da cércea admissível")
    else:
        return {"cercea_m": None, "pisos": None, "abc_min_m2": None, "abc_max_m2": None,
                "regras_base": ["rpdm-27.1.g"], "regras_limite_superior": [],
                "notas": ["cércea indeterminada: falta largura do arruamento ou moda"],
                "incerteza": ""}
    pisos = int(cercea // PE_DIREITO)  # cércea é tecto (<= largura); floor não excede

    # profundidade: 30 m [27.1.d] e tardoz dominante [27.1.b]
    prof = min(30.0, parcela["profundidade_m"])
    aplicadas.extend(["rpdm-27.1.d", "rpdm-27.1.b"])
    if parcela.get("uso_habitacao_coletiva"):
        corte = max(6.0, cercea / 2.0)
        prof = min(prof, parcela["profundidade_m"] - corte)
        aplicadas.append("rgeu-62")

    # implantação: impermeabilização <= 0,7 [27.1.c/d] e permeabilidade >= 0,3 [28.1]
    implantacao = min(parcela["frente_m"] * prof, 0.7 * parcela["area_m2"])
    aplicadas.extend(["rpdm-27.1.c", "rpdm-28.1"])
    abc_min = implantacao * pisos

    # limite superior: colmatação de empena [27.1.g], gaveto [27.1.f]
    abc_max, sup = abc_min, []
    if parcela.get("empena_confinante_m", 0) > cercea:
        pisos_sup = int(arred_multiplo(parcela["empena_confinante_m"]) // PE_DIREITO)
        abc_max = implantacao * pisos_sup
        sup.append("rpdm-27.1.g (colmatação de empena)")
    if parcela.get("gaveto"):
        sup.append("rpdm-27.1.f")
        notas.append("gaveto: dispensa possível de tardoz/cave/profundidade [27.1.f] — carece de análise")
    if parcela["area_m2"] < 100:
        notas.append("rpdm-27.1.e: parcela exígua/irregular — profundidade pelo tardoz "
                     "dominante, argumentável")
    notas.append("rpdm-26/27.4: FUC-II em transformação; podem ser impostas cérceas ou "
                 "planos de fachada diferentes por salvaguarda patrimonial ou integração [27.4]")

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


def _cap_indice(parcela, *, indice, imperm_max, pisos_max, ids_base, sup=None, notas=None):
    """Capacidade por índice de edificação (ABC = índice × área). Usada nas
    categorias económicas, blocos isolados e baixa densidade. Não precisa de
    moda/cércea — a cércea/nº de pisos resultam da integração urbanística."""
    area = parcela["area_m2"]
    return {
        "cercea_m": None, "pisos": pisos_max,
        "indice_edificacao": indice,
        "implantacao_m2": round(imperm_max * area),
        "abc_min_m2": round(indice * area), "abc_max_m2": round(indice * area),
        "regras_base": list(ids_base),
        "regras_limite_superior": list(sup or []),
        "notas": list(notas or []),
        "incerteza": ("Área bruta de construção máxima pela aplicação do índice de "
                      "edificação do RPDM. A cércea e o nº de pisos resultam da "
                      "integração urbanística com a envolvente."),
    }


def capacidade_blocos(parcela):
    """Área de Blocos Isolados de Implantação Livre (RPDM 31.º-33.º)."""
    sup = ["rpdm-32.5 (colmatação de empena)"] if parcela.get("empena_confinante_m") else None
    return _cap_indice(parcela, indice=1.0, imperm_max=0.6, pisos_max=None,
                       ids_base=["rpdm-32.3.a", "rpdm-32.4", "rpdm-33"], sup=sup,
                       notas=["rpdm-32.6: cércea assegura a integração com a envolvente",
                              "rpdm-32.3.b: índice de edificação alterável em UOPG"])


def capacidade_ae1(parcela):
    """Área de Atividades Económicas de Tipo I (RPDM 35.º-36.º)."""
    return _cap_indice(parcela, indice=1.8, imperm_max=0.7, pisos_max=None,
                       ids_base=["rpdm-36.1", "rpdm-36.2"],
                       notas=["rpdm-35.2: habitação só para vigilância/segurança (≤ 5% da edificação)",
                              "rpdm-36.1: índice alterável em UOPG"])


def capacidade_ae2(parcela):
    """Área de Atividades Económicas de Tipo II (RPDM 37.º-38.º)."""
    return _cap_indice(parcela, indice=1.4, imperm_max=0.7, pisos_max=None,
                       ids_base=["rpdm-38.1", "rpdm-38.2"],
                       notas=["rpdm-37.2: habitação admitida se área < área de atividades económicas",
                              "rpdm-38.1: índice alterável em UOPG"])


def capacidade_baixa_densidade(parcela):
    """Espaços Urbanos de Baixa Densidade (RPDM 45.º-48.º)."""
    if parcela["area_m2"] >= 1000:
        return _cap_indice(parcela, indice=0.2, imperm_max=0.3, pisos_max=2,
                           ids_base=["rpdm-47.2", "rpdm-48"],
                           notas=["rpdm-47.4: nº de pisos pode ser superior em UOPG"])
    return {"carece": True,
            "motivo": ("parcela < 1000 m²: sem índice fixo — respeitar volumetria, cércea "
                       "e alinhamentos dominantes, máx. 2 pisos acima do solo [rpdm-47.3]"),
            "regras_base": ["rpdm-47.3", "rpdm-48"]}


# despacho categoria -> função de capacidade (envelope/índice)
_CAPACIDADE = {
    "frente_urbana_continua_tipo_I": capacidade_fuc1,
    "frente_urbana_continua_tipo_II": capacidade_fuc2,
    "edificios_tipo_moradia": capacidade_moradia,
    "blocos_isolados": capacidade_blocos,
    "atividades_economicas_tipo_I": capacidade_ae1,
    "atividades_economicas_tipo_II": capacidade_ae2,
    "baixa_densidade": capacidade_baixa_densidade,
}

# categorias de regime especial (sem envelope de capacidade lote a lote)
_REGIME = {
    "historica": {"edificavel": "apreciação", "artigos": ["rpdm-19", "rpdm-20", "rpdm-21", "rpdm-22"],
        "sintese": "Área histórica: conservação e requalificação do edificado; nova construção só "
                   "para substituir edifícios demolíveis [21.º] ou ocupar parcelas não edificadas, "
                   "respeitando cércea e alinhamentos vizinhos [20.º] — carece de análise patrimonial."},
    "verde_fruicao_coletiva": {"edificavel": "muito limitada", "artigos": ["rpdm-40"],
        "sintese": "Espaço verde de fruição coletiva: não edificável, salvo estruturas de apoio à "
                   "fruição, com impermeabilização máxima de 0,05 da parcela [40.º]."},
    "verde_ludico_produtiva": {"edificavel": "muito limitada", "artigos": ["rpdm-41"],
        "sintese": "Área verde lúdico-produtiva: apenas conservação/ampliação de existentes ou apoios "
                   "às atividades, impermeabilização ≤ 0,05 e máx. 2 pisos [41.º]."},
    "verde_associada_equipamento": {"edificavel": "limitada", "artigos": ["rpdm-42"],
        "sintese": "Área verde associada a equipamento: construção admitida mantendo o coberto "
                   "vegetal, com implantação total das construções ≤ 20% da parcela [42.º]."},
    "verde_protecao_enquadramento": {"edificavel": "interdita", "artigos": ["rpdm-43"],
        "sintese": "Área verde de proteção e enquadramento: construção interdita, salvo intervenções "
                   "ao nível das redes de infraestruturas [43.º]."},
    "frente_atlantica_ribeirinha": {"edificavel": "interdita", "artigos": ["rpdm-44"],
        "sintese": "Frente atlântica e ribeirinha: construção interdita, salvo infraestruturas, "
                   "proteção costeira e equipamentos ligeiros de apoio lúdico/desportivo [44.º]."},
    "equipamentos": {"edificavel": "por programa", "artigos": ["rpdm-49", "rpdm-50", "rpdm-51"],
        "sintese": "Uso especial — equipamentos: edificabilidade essencial à viabilidade do "
                   "equipamento, impermeabilização ≤ 0,65 e correta inserção urbana [51.º]."},
    "infraestruturas": {"edificavel": "por programa", "artigos": ["rpdm-52", "rpdm-53", "rpdm-54"],
        "sintese": "Uso especial — infraestruturas: edificabilidade a necessária à infraestrutura; "
                   "usos complementares até 25% da área da parcela [54.º]."},
}

# condicionantes de âmbito municipal (aparecem em quase todos os pontos)
_COND_AMBITO_MUNICIPAL = {
    "Área de Intervenção do Plano",
    "Aeroportos e aeródromos (zonas de servidão aeronáutica)",
}


def _norm_cond(s):
    """Normaliza o nome de uma camada para comparar entre fontes (serviço
    ArcGIS com rótulos vs. gpkg com underscores/parênteses)."""
    s = (s or "").lower().replace("_", " ")
    s = s.replace("(", " ").replace(")", " ")
    return " ".join(s.split())


_COND_AMBITO_MUNICIPAL_N = {_norm_cond(x) for x in _COND_AMBITO_MUNICIPAL}


def _limpa_designacao(d):
    """Descarta designações que são só um GUID (sem nome útil)."""
    if not d or not isinstance(d, str):
        return None
    s = d.strip()
    if s.startswith("{") and s.endswith("}"):
        return None
    return d


def _condicionantes_para_avisos(condicionantes):
    efetivas, municipais, avisos = [], [], []
    for c in condicionantes or []:
        camada = c.get("camada") or ""
        item = {"camada": camada, "layer_id": c.get("layer_id"),
                "designacao": _limpa_designacao(c.get("designacao")),
                "legislacao": c.get("legislacao")}
        if _norm_cond(camada) in _COND_AMBITO_MUNICIPAL_N:
            municipais.append(item)
            continue
        efetivas.append(item)
        cl = camada.lower()
        if "patrimón" in cl or "patrimon" in cl or "imóveis classificados" in cl:
            avisos.append(f"aviso patrimonial: {camada}"
                          + (f" — {item['designacao']}" if item["designacao"] else ""))
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
        import pdm_local as pdm_arcgis
        consulta = pdm_arcgis.consultar_ponto(x, y)

    slug = consulta.get("categoria_slug")
    cat = consulta.get("categoria") or {}
    efetivas, municipais, avisos = _condicionantes_para_avisos(consulta.get("condicionantes"))

    out = {
        "ponto": {"x": x, "y": y},
        "categoria": cat.get("sc_espaco"),
        "categoria_cod": cat.get("sc_espaco_cod"),
        "categoria_slug": slug,
        "regras_implementadas": slug in _CAPACIDADE or slug in _REGIME,
        "operativa": (consulta.get("operativa") or {}).get("t_espaco"),
        "condicionantes_efetivas": efetivas,
        "condicionantes_ambito_municipal": municipais,
        "avisos": avisos,
        "regime": None,
        "envelope_efeito": None,
        "frente": None,
        "capacidade": None,
        "estado": None,
    }

    # categorias de regime especial (verdes, frente atlântica, uso especial, histórica):
    # não têm envelope lote a lote — devolvem a síntese do regime.
    reg = _REGIME.get(slug)
    if reg is not None:
        out["regime"] = reg
        out["estado"] = reg["sintese"]
        return out

    fn = _CAPACIDADE.get(slug)
    if fn is None:
        out["estado"] = (f"categoria sem regras RAIO implementadas "
                         f"({cat.get('sc_espaco') or 'fora do solo qualificado'})"
                         f" — carece de análise")
        return out
    if parcela is None:
        out["estado"] = ("Categoria coberta pelas regras. Desenha o contorno do terreno "
                         "no mapa (ferramenta de polígono, canto superior esquerdo) para "
                         "calcular a capacidade construtiva.")
        return out

    # A frente (moda da cércea + largura do arruamento) só é precisa nas FUC e
    # na moradia em colmatação; nas restantes evita-se a chamada ao Overture.
    fuc = slug in ("frente_urbana_continua_tipo_I", "frente_urbana_continua_tipo_II")
    falta_moda = not parcela.get("moda_cercea_m")
    falta_larg = not parcela.get("largura_arruamento_m")
    precisa_frente = auto_moda and (
        (fuc and (falta_moda or falta_larg))
        or (slug == "edificios_tipo_moradia" and parcela.get("colmatacao_consolidado") and falta_moda))
    if precisa_frente:
        import frente as _frente
        finfo = _frente.frente_no_ponto(x, y)
        out["frente"] = finfo
        if finfo.get("moda_cercea_m") and falta_moda:
            parcela = {**parcela, "moda_cercea_m": finfo["moda_cercea_m"]}
        # largura do arruamento medida (perfil transversal) alimenta a cércea da FUC
        if finfo.get("largura_arruamento_m") and falta_larg:
            parcela = {**parcela, "largura_arruamento_m": finfo["largura_arruamento_m"]}

    # FUC-I: cércea da moda, ou da largura do arruamento (tecto 45º) se não houver moda
    if slug == "frente_urbana_continua_tipo_I" \
            and not parcela.get("moda_cercea_m") and not parcela.get("largura_arruamento_m"):
        out["estado"] = ("cércea indeterminada (sem edificado na frente nem largura de "
                         "arruamento) — forneça a moda da cércea ou a largura do arruamento")
        return out
    # FUC-II: cércea vem da largura do arruamento ou, na sua falta, da moda
    if slug == "frente_urbana_continua_tipo_II" \
            and not parcela.get("moda_cercea_m") and not parcela.get("largura_arruamento_m"):
        out["estado"] = ("cércea indeterminada (sem edificado na frente nem largura de "
                         "arruamento) — forneça moda_cercea_m ou largura_arruamento_m")
        return out

    cap = fn(parcela)
    if cap.get("carece"):  # ex.: baixa densidade < 1000 m²
        out["estado"] = cap["motivo"]
    else:
        out["capacidade"] = cap
        out["estado"] = "ok"
    _aplicar_condicionantes(out, efetivas)
    return out


def _aplicar_condicionantes(out, efetivas):
    """Liga as condicionantes ao envelope: non aedificandi interdita a construção;
    património/imóveis classificados sujeitam o resultado a apreciação patrimonial.
    (A servidão aeronáutica fica informativa: a camada não traz cota-limite.)"""
    cls = [(c.get("camada") or "").lower() for c in (efetivas or [])]

    def tem(*ks):
        return any(any(k in cl for k in ks) for cl in cls)

    if tem("non aedificandi"):
        out["capacidade"] = None
        out["envelope_efeito"] = "non_aedificandi"
        out["estado"] = ("Zona non aedificandi sobre o ponto — construção interdita pela "
                         "condicionante, independentemente da categoria de solo.")
        return
    if out.get("capacidade") and tem("patrimón", "patrimon", "imóveis classificados",
                                     "imoveis classificados"):
        out["capacidade"].setdefault("notas", []).append(
            "Sujeito a apreciação patrimonial (património edificado / imóvel classificado "
            "ou zona de proteção): os valores são uma referência máxima — cércea, "
            "volumetria e demolição podem ser condicionadas.")
        out["capacidade"]["apreciacao_patrimonial"] = True
        out["envelope_efeito"] = "apreciacao_patrimonial"


def analisar_parcela(poligono, *, auto_moda=True, extra=None, consulta=None):
    """Análise a partir do polígono da parcela (EPSG:3763, shapely ou WKT).

    Deriva área/frente/profundidade do polígono (motor.parcela), resolve a
    categoria no centróide e calcula o intervalo. `extra` acrescenta campos à
    parcela (ex.: uso_habitacao_coletiva, colmatacao_consolidado, gaveto).
    """
    import parcela as _parcela
    import pdm_local as pdm_arcgis
    from shapely import wkt as _wkt
    poly = _wkt.loads(poligono) if isinstance(poligono, str) else poligono
    c = poly.centroid
    parcela, metricas = _parcela.parcela_para_engine(poly, extra=extra)
    if consulta is None:
        consulta = pdm_arcgis.consultar_ponto(c.x, c.y)
        try:  # categoria DOMINANTE por área (corrige centróide em parcela embebida)
            dom = pdm_arcgis.categoria_dominante(poly)
        except Exception:
            dom = None
        if dom and dom.get("sc_espaco_cod") and \
                dom["sc_espaco_cod"] != (consulta.get("categoria") or {}).get("sc_espaco_cod"):
            cat = dict(consulta.get("categoria") or {})
            cat["sc_espaco"], cat["sc_espaco_cod"] = dom["sc_espaco"], dom["sc_espaco_cod"]
            consulta["categoria"] = cat
            consulta["categoria_slug"] = dom["slug"]
    out = analisar_ponto(c.x, c.y, parcela, consulta=consulta, auto_moda=auto_moda)
    out["parcela_metricas"] = metricas
    return out


def analisar_morada(morada, *, parcela=None, auto_moda=False):
    """Pesquisa por texto: geocodifica a morada (motor.geocode) e analisa o ponto.

    Devolve o resultado de analisar_ponto acrescido de `morada`
    (consulta, morada encontrada e coordenadas), ou {erro} se não encontrar.
    """
    import geocode
    g = geocode.geocodificar(morada)
    if g is None:
        return {"erro": f"morada não encontrada no Porto: {morada!r}", "morada_consulta": morada}
    out = analisar_ponto(g["x"], g["y"], parcela, auto_moda=auto_moda)
    out["morada"] = {"consulta": morada, "encontrada": g["label"],
                     "x": g["x"], "y": g["y"]}
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
