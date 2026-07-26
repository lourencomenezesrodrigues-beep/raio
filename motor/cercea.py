"""Moda da cércea de uma frente urbana.

Definição (definicoes.yaml): a cércea que apresenta maior extensão ao longo
de uma frente urbana edificada — ponderação por extensão de fachada, não por
número de edifícios. Resultado arredondado ao múltiplo de 3 m (parametros_globais).

A função é agnóstica quanto à origem dos dados: recebe pares (cércea_m, fachada_m).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

PASSO_M = 3.0  # múltiplo de arredondamento (pé-direito assumido)


def bin_cercea(cercea_m: float, passo: float = PASSO_M) -> float:
    """Arredonda uma cércea ao múltiplo de `passo` mais próximo."""
    return round(cercea_m / passo) * passo


@dataclass
class ResultadoModa:
    moda_m: float | None                 # cércea dominante, múltiplo de 3 m
    fachada_moda_m: float                # extensão de fachada nesse valor
    fachada_total_m: float               # extensão total considerada
    fracao: float                        # fachada_moda / fachada_total
    distribuicao: list[tuple[float, float]]  # [(cercea_bin, fachada_m)] desc
    n_edificios: int


def moda_cercea(
    frentes: list[tuple[float, float]],
    passo: float = PASSO_M,
) -> ResultadoModa:
    """frentes: lista de (cércea_m, extensão_de_fachada_m).

    Soma a extensão de fachada por cércea arredondada ao múltiplo de `passo`
    e devolve o valor dominante.
    """
    acc: dict[float, float] = defaultdict(float)
    total = 0.0
    n = 0
    for cercea_m, fachada_m in frentes:
        if cercea_m is None or fachada_m is None or fachada_m <= 0 or cercea_m <= 0:
            continue
        acc[bin_cercea(cercea_m, passo)] += fachada_m
        total += fachada_m
        n += 1
    if not acc:
        return ResultadoModa(None, 0.0, 0.0, 0.0, [], 0)
    dist = sorted(acc.items(), key=lambda kv: kv[1], reverse=True)
    moda, fach_moda = dist[0]
    return ResultadoModa(
        moda_m=moda,
        fachada_moda_m=fach_moda,
        fachada_total_m=total,
        fracao=fach_moda / total if total else 0.0,
        distribuicao=dist,
        n_edificios=n,
    )
