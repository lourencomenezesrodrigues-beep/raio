import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "motor"))
from engine import (capacidade_fuc1, capacidade_fuc2, capacidade_moradia,
                    carregar_regras, analisar_ponto)

def test_regras_carregam():
    r = carregar_regras("fuc-1", "moradia", "transversais")
    assert len(r) == 24, f"esperava 24 regras, encontrei {len(r)}"

def test_caso_sintetico():
    r = capacidade_fuc1(dict(area_m2=300, frente_m=10, profundidade_m=30,
        moda_cercea_m=16.4, largura_arruamento_m=12,
        uso_habitacao_coletiva=True, empena_confinante_m=18))
    assert r["cercea_m"] == 12          # 45º corta a moda (15) para 12
    assert r["pisos"] == 4
    assert r["profundidade_util_m"] == 24.0  # 30 - max(6, 12/2)
    assert r["implantacao_m2"] == 210.0      # 0,7 × 300 corta os 240
    assert r["abc_min_m2"] == 840
    assert r["abc_max_m2"] == 1260           # empena 18 → 6 pisos
    assert "rgeu-59" in r["regras_base"] and "rgeu-62" in r["regras_base"]

def test_moradia_sintetico():
    r = capacidade_moradia(dict(area_m2=400, frente_m=12, profundidade_m=15))
    assert r["pisos"] == 3                    # 30.1.c
    assert r["cercea_m"] == 9.0               # 3 × 3 m, abaixo do tecto de 11 m
    assert r["impermeavel_max_m2"] == 240.0   # 0,6 × 400 [30.1.b]
    assert r["implantacao_m2"] == 180         # 12 × 15 < 240
    assert r["abc_min_m2"] == 540
    assert "rpdm-30.1.b" in r["regras_base"] and "rpdm-30.1.c" in r["regras_base"]

def test_moradia_parcela_grande():
    r = capacidade_moradia(dict(area_m2=2500, frente_m=20, profundidade_m=20))
    assert "rpdm-30.2" in r["regras_base"]    # > 2000 m² -> implantação livre

def test_analisar_ponto_despacho_fuc1():
    # consulta injectada (sem rede)
    consulta = {"categoria_slug": "frente_urbana_continua_tipo_I",
                "categoria": {"sc_espaco": "Área de frente urbana contínua de tipo I",
                              "sc_espaco_cod": "TE2AFUCT1"},
                "operativa": {"t_espaco": "Espaço consolidado"},
                "condicionantes": []}
    parcela = dict(area_m2=300, frente_m=10, profundidade_m=30,
                   moda_cercea_m=16.4, largura_arruamento_m=12)
    r = analisar_ponto(0, 0, parcela, consulta=consulta)
    assert r["estado"] == "ok"
    assert r["capacidade"]["pisos"] == 4

def test_analisar_ponto_sem_regras_com_aviso():
    consulta = {"categoria_slug": None,
                "categoria": {"sc_espaco": "Área de infraestruturas"},
                "operativa": {},
                "condicionantes": [
                    {"camada": "Património edificado", "designacao": "Centro Histórico",
                     "legislacao": "Lei 107/2001"},
                    {"camada": "Área de Intervenção do Plano", "designacao": None,
                     "legislacao": None}]}
    r = analisar_ponto(0, 0, None, consulta=consulta)
    assert "carece de análise" in r["estado"]
    assert any("patrimonial" in a for a in r["avisos"])
    # a condicionante de âmbito municipal não polui as efetivas
    assert [c["camada"] for c in r["condicionantes_efetivas"]] == ["Património edificado"]

def test_fuc2_regras_carregam():
    r = carregar_regras("fuc-2")
    assert len(r) == 15, f"esperava 15 regras FUC-II, encontrei {len(r)}"
    assert r["rpdm-27.1.d"]["parametros"]["profundidade_max_m"] == 30
    assert r["rpdm-27.2.b"]["parametros"]["cercea_max_m"] == 21

def test_fuc2_arruamento_estreito():
    r = capacidade_fuc2(dict(area_m2=400, frente_m=12, profundidade_m=35,
        largura_arruamento_m=15, uso_habitacao_coletiva=True))
    assert r["cercea_m"] == 15            # <= 21: cércea = largura [27.1.g]
    assert r["pisos"] == 5                # 15 // 3
    assert r["profundidade_util_m"] == 27.5  # 35 - max(6, 15/2)
    assert r["implantacao_m2"] == 280.0   # 0,7 × 400 corta 12×27.5
    assert r["abc_min_m2"] == 1400
    assert "rpdm-27.1.g" in r["regras_base"] and "rpdm-28.1" in r["regras_base"]

def test_fuc2_arruamento_largo_teto_21():
    r = capacidade_fuc2(dict(area_m2=500, frente_m=15, profundidade_m=40,
        largura_arruamento_m=30))            # perfil > 21 e sem moda -> tecto 21 m
    assert r["cercea_m"] == 21.0
    assert "rpdm-27.2.b" in r["regras_base"]

def test_fuc2_moda_supera_teto():
    r = capacidade_fuc2(dict(area_m2=500, frente_m=15, profundidade_m=40,
        largura_arruamento_m=30, moda_cercea_m=24))  # moda > 21 -> respeita moda
    assert r["cercea_m"] == 24

def test_metricas_parcela_alinhada():
    import parcela
    from shapely.geometry import LineString, Polygon
    eixo = LineString([(0, 0), (100, 0)])          # rua ao longo de x
    # parcela: frente 10 m (x 40..50), profundidade 20 m (y 5..25)
    poly = Polygon([(40, 5), (50, 5), (50, 25), (40, 25)])
    m = parcela.metricas_de_poligono(poly, eixo=eixo)
    assert m["area_m2"] == 200.0
    assert m["frente_m"] == 10.0
    assert m["profundidade_m"] == 20.0

def test_metricas_parcela_rodada():
    import parcela, math
    from shapely.geometry import LineString, Polygon
    from shapely.affinity import rotate
    eixo = LineString([(0, 0), (100, 100)])        # rua a 45°
    poly = rotate(Polygon([(40, 5), (50, 5), (50, 25), (40, 25)]),
                  45, origin=(0, 0))               # parcela rodada igual
    m = parcela.metricas_de_poligono(poly, eixo=eixo)
    assert m["area_m2"] == 200.0
    assert abs(m["frente_m"] - 10.0) < 0.1
    assert abs(m["profundidade_m"] - 20.0) < 0.1

if __name__ == "__main__":
    test_regras_carregam(); test_caso_sintetico()
    test_moradia_sintetico(); test_moradia_parcela_grande()
    test_analisar_ponto_despacho_fuc1(); test_analisar_ponto_sem_regras_com_aviso()
    test_fuc2_regras_carregam(); test_fuc2_arruamento_estreito()
    test_fuc2_arruamento_largo_teto_21(); test_fuc2_moda_supera_teto()
    test_metricas_parcela_alinhada(); test_metricas_parcela_rodada()
    print("todos os testes passam")
