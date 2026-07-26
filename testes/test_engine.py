import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "motor"))
from engine import capacidade_fuc1, carregar_regras

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

if __name__ == "__main__":
    test_regras_carregam(); test_caso_sintetico(); print("todos os testes passam")
