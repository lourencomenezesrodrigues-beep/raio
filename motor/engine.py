"""CABE — motor de cálculo (esqueleto de demonstração).

Carrega as regras YAML e calcula o intervalo de capacidade para inputs
sintéticos. A geometria real (parcelas, frentes urbanas, moda da cércea a
partir do edificado) entra na fase seguinte; aqui fixa-se a mecânica das
regras e a rastreabilidade (cada número sai com os ids das regras).
"""
from pathlib import Path
import math
import yaml

RAIZ = Path(__file__).resolve().parent.parent
PARAMS = yaml.safe_load((RAIZ / "parametros_globais.yaml").read_text())
PE_DIREITO = float(PARAMS.get("pe_direito_assumido_m", 3.0))


def carregar_regras(*pastas):
    regras = {}
    for pasta in pastas:
        for f in sorted((RAIZ / "regras" / "porto" / pasta).glob("*.yaml")):
            d = yaml.safe_load(f.read_text())
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


if __name__ == "__main__":
    exemplo = dict(area_m2=300, frente_m=10, profundidade_m=30,
                   moda_cercea_m=16.4, largura_arruamento_m=12,
                   uso_habitacao_coletiva=True, empena_confinante_m=18)
    from pprint import pprint
    pprint(capacidade_fuc1(exemplo))
