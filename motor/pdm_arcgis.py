"""Cliente para os serviços ArcGIS REST do PDM 2021 do Porto.

Base: https://fedservergeo.cm-porto.pt/arcgis/rest/services/PDM2021
CRS de trabalho: EPSG:3763 (ETRS89 / PT-TM06).

Dois usos:
  - consulta por ponto (categoria de solo + condicionantes)   -> consultar_ponto()
  - descarga de uma camada inteira para GeoJSON/gpkg           -> query_layer()

Sem dependência de geopandas: devolve GeoJSON cru (dicts). A escrita para
gpkg fica a cargo de quem chama (ver scripts/baixar_ccgd.py).
"""
from __future__ import annotations

import time
from typing import Any, Iterator
from urllib.parse import urlencode
from urllib.request import urlopen, Request
import json

BASE = "https://fedservergeo.cm-porto.pt/arcgis/rest/services/PDM2021"
WKID = 3763  # ETRS89 / PT-TM06
_UA = {"User-Agent": "RAIO/0.1 (analise nao vinculativa; opendata.porto.digital)"}


def _get(url: str, params: dict[str, Any], timeout: int = 60) -> dict:
    q = urlencode({**params, "f": "json"})
    req = Request(f"{url}?{q}", headers=_UA)
    with urlopen(req, timeout=timeout) as r:
        data = json.load(r)
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(f"ArcGIS erro: {data['error']}")
    return data


def service_url(service: str, layer_id: int) -> str:
    return f"{BASE}/{service}/MapServer/{layer_id}"


def layer_info(service: str, layer_id: int) -> dict:
    """Metadados da camada (nome, campos, tipo de geometria)."""
    return _get(service_url(service, layer_id), {})


def query_layer(
    service: str,
    layer_id: int,
    *,
    where: str = "1=1",
    geometry: dict | None = None,
    geometry_type: str = "esriGeometryPoint",
    out_fields: str = "*",
    return_geometry: bool = True,
    page: int = 1000,
) -> dict:
    """Consulta uma camada, paginada. Devolve um FeatureCollection GeoJSON.

    `geometry` em coordenadas EPSG:3763. Para ponto: {"x": .., "y": ..}.
    """
    features: list[dict] = []
    offset = 0
    base_params: dict[str, Any] = {
        "where": where,
        "outFields": out_fields,
        "returnGeometry": str(return_geometry).lower(),
        "outSR": WKID,
        "inSR": WKID,
        "f": "geojson",
    }
    if geometry is not None:
        base_params.update(
            geometry=json.dumps(geometry),
            geometryType=geometry_type,
            spatialRel="esriSpatialRelIntersects",
        )
    url = f"{service_url(service, layer_id)}/query"
    while True:
        params = {**base_params, "resultOffset": offset, "resultRecordCount": page}
        q = urlencode(params)
        req = Request(f"{url}?{q}", headers=_UA)
        with urlopen(req, timeout=120) as r:
            fc = json.load(r)
        if fc.get("error"):
            raise RuntimeError(f"ArcGIS erro (layer {layer_id}): {fc['error']}")
        batch = fc.get("features", [])
        features.extend(batch)
        if len(batch) < page:  # última página
            break
        offset += page
        time.sleep(0.1)
    return {"type": "FeatureCollection", "features": features}


def _point_query(service: str, layer_id: int, x: float, y: float) -> list[dict]:
    fc = query_layer(
        service,
        layer_id,
        geometry={"x": x, "y": y},
        geometry_type="esriGeometryPoint",
    )
    return [f.get("properties", {}) for f in fc["features"]]


def identify(service: str, x: float, y: float, *, tolerancia_m: float = 1.0,
             layers: str = "all") -> list[dict]:
    """Operação `identify` do MapServer: devolve tudo o que existe no ponto,
    em todas as camadas, numa só chamada. `tolerancia_m` em metros."""
    meia = 100.0  # meia-largura do mapExtent, em metros
    px = 401
    tol_px = max(1, round(tolerancia_m / (2 * meia / px)))
    params = {
        "geometry": json.dumps({"x": x, "y": y}),
        "geometryType": "esriGeometryPoint",
        "sr": WKID,
        "tolerance": tol_px,
        "mapExtent": f"{x-meia},{y-meia},{x+meia},{y+meia}",
        "imageDisplay": f"{px},{px},96",
        "layers": layers,
        "returnGeometry": "false",
    }
    data = _get(f"{BASE}/{service}/MapServer/identify", params)
    return data.get("results", [])


# ---------------------------------------------------------------------------
# Ponte categoria de solo (gpkg/serviço) -> slug das regras RAIO
# ---------------------------------------------------------------------------
import unicodedata


def _norm(s: str) -> str:
    """casefold + sem acentos + espaços colapsados, para casar strings."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.split()).casefold()


# Código do domínio sc_espaco (estável) -> slug de regras RAIO. Autoritativo.
_CODE_PARA_SLUG = {
    "TE2AH": "historica",
    "TE2AFUCT1": "frente_urbana_continua_tipo_I",
    "TE2AFUCT2": "frente_urbana_continua_tipo_II",
    "TE2AETM": "edificios_tipo_moradia",
    "TE2ABIIL": "blocos_isolados",
    "TE2AAET1": "atividades_economicas_tipo_I",
    "TE2AAET2": "atividades_economicas_tipo_II",
    "TE2AVFC": "verde_fruicao_coletiva",
    "TE2AVLP": "verde_ludico_produtiva",
    "TE2AVAE": "verde_associada_equipamento",
    "TE2AVPE": "verde_protecao_enquadramento",
    "TE2AFAR": "frente_atlantica_ribeirinha",
    "TE2EUBD": "baixa_densidade",
    "TE2AE": "equipamentos",
    "TE2AI": "infraestruturas",
}

# Fallback por rótulo (para dados já decodificados, ex. o gpkg).
# Igualdade exacta sobre string normalizada — nunca substring ("tipo i" ⊂ "tipo ii").
_LABEL_PARA_SLUG = {
    _norm("Área histórica"): "historica",
    _norm("Área de frente urbana contínua de tipo I"): "frente_urbana_continua_tipo_I",
    _norm("Área de frente urbana contínua de tipo II"): "frente_urbana_continua_tipo_II",
    _norm("Área de edifícios de tipo moradia"): "edificios_tipo_moradia",
    _norm("Área de blocos isolados de implantação livre"): "blocos_isolados",
    _norm("Área de atividades económicas de tipo I"): "atividades_economicas_tipo_I",
    _norm("Área de atividades económicas de tipo II"): "atividades_economicas_tipo_II",
    _norm("Área verde de fruição coletiva"): "verde_fruicao_coletiva",
    _norm("Área verde lúdico-produtiva"): "verde_ludico_produtiva",
    _norm("Área verde associada a equipamento"): "verde_associada_equipamento",
    _norm("Área verde de proteção e enquadramento"): "verde_protecao_enquadramento",
    _norm("Área de frente atlântica e ribeirinha"): "frente_atlantica_ribeirinha",
    _norm("Espaços urbanos de baixa densidade"): "baixa_densidade",
    _norm("Área de equipamentos"): "equipamentos",
    _norm("Área de infraestruturas"): "infraestruturas",
}


def slug_categoria(sc_espaco: str | None) -> str | None:
    """sc_espaco (código do domínio OU rótulo) -> slug de regras RAIO, ou None."""
    if not sc_espaco:
        return None
    if sc_espaco in _CODE_PARA_SLUG:            # veio o código do REST
        return _CODE_PARA_SLUG[sc_espaco]
    return _LABEL_PARA_SLUG.get(_norm(sc_espaco))  # veio o rótulo (gpkg)


# --- decodificação de domínios coded-value (cache por camada) ---------------
_DOMAIN_CACHE: dict[tuple[str, int], dict[str, dict[str, str]]] = {}


def _domains(service: str, layer_id: int) -> dict[str, dict[str, str]]:
    key = (service, layer_id)
    if key not in _DOMAIN_CACHE:
        info = layer_info(service, layer_id)
        m: dict[str, dict[str, str]] = {}
        for f in info.get("fields", []):
            dom = f.get("domain")
            if dom and dom.get("type") == "codedValue":
                m[f["name"]] = {cv["code"]: cv["name"] for cv in dom["codedValues"]}
        _DOMAIN_CACHE[key] = m
    return _DOMAIN_CACHE[key]


def _decode(service: str, layer_id: int, props: dict, field: str) -> str | None:
    """Rótulo legível de um campo com domínio; devolve o valor cru se sem domínio."""
    raw = (props or {}).get(field)
    if raw is None:
        return None
    return _domains(service, layer_id).get(field, {}).get(raw, raw)


def _attr(attrs: dict, *nomes: str):
    """Vai buscar um valor por nome normalizado (identify devolve aliases)."""
    idx = {_norm(k): v for k, v in (attrs or {}).items()}
    for n in nomes:
        v = idx.get(_norm(n))
        if v not in (None, "", "Null"):
            return v
    return None


def categoria_dominante(poly) -> dict | None:
    """Categoria de solo DOMINANTE (por área) sob um polígono (shapely, EPSG:3763).

    Corrige o viés do centróide: um terreno desenhado que cruze uma parcela de
    equipamento embebida num bairro é classificado pela subcategoria que ocupa
    maior área do polígono, não pelo ponto central.
    """
    from shapely.geometry import shape
    ext = [[float(x), float(y)] for x, y in poly.exterior.coords]
    geom = {"rings": [ext], "spatialReference": {"wkid": WKID}}
    fc = query_layer("PO1A_QS", 8, geometry=geom, geometry_type="esriGeometryPolygon",
                     out_fields="sc_espaco")
    areas: dict[str, float] = {}
    for f in fc["features"]:
        cod = (f.get("properties") or {}).get("sc_espaco")
        if not cod:
            continue
        try:
            inter = poly.intersection(shape(f["geometry"])).area
        except Exception:
            inter = 0.0
        areas[cod] = areas.get(cod, 0.0) + inter
    if not areas:
        return None
    dom = max(areas, key=areas.get)
    label = _domains("PO1A_QS", 8).get("sc_espaco", {}).get(dom, dom)
    return {"sc_espaco_cod": dom, "sc_espaco": label, "slug": slug_categoria(dom),
            "fracao": round(areas[dom] / (poly.area or 1), 2)}


def consultar_ponto(x: float, y: float, *, tolerancia_m: float = 1.0) -> dict:
    """Consulta por ponto (EPSG:3763): categoria de solo + condicionantes.

    Devolve:
      x, y
      qualificacao_funcional: {c_espaco, sc_espaco, ...} | None
      qualificacao_operativa: {t_espaco, ...} | None
      categoria_slug: slug de regras RAIO (ou None)
      regras_aplicaveis: bool
      condicionantes: [ {camada, designacao, legislacao, valores} ... ]
    """
    func = _point_query("PO1A_QS", 8, x, y)  # Qualificação do solo funcional
    oper = _point_query("PO1A_QS", 7, x, y)  # Qualificação do solo operativa
    qf = func[0] if func else None
    qo = oper[0] if oper else None

    sc_cod = (qf or {}).get("sc_espaco")
    c_cod = (qf or {}).get("c_espaco")
    slug = slug_categoria(sc_cod)

    categoria = None
    if qf is not None:
        categoria = {
            "c_espaco_cod": c_cod,
            "c_espaco": _decode("PO1A_QS", 8, qf, "c_espaco"),
            "sc_espaco_cod": sc_cod,
            "sc_espaco": _decode("PO1A_QS", 8, qf, "sc_espaco"),
        }

    operativa = None
    if qo is not None:
        operativa = {
            "t_espaco_cod": qo.get("t_espaco"),
            "t_espaco": _decode("PO1A_QS", 7, qo, "t_espaco"),
        }

    cond = []
    for r in identify("CCGD_PUBLICACAO", x, y, tolerancia_m=tolerancia_m):
        attrs = r.get("attributes", {})
        cond.append({
            "camada": r.get("layerName"),
            "layer_id": r.get("layerId"),
            "designacao": _attr(attrs, "designacao", "identifica"),
            "legislacao": _attr(attrs, "legislacao_aplicavel", "legislacao"),
            "valores": attrs,
        })

    return {
        "x": x, "y": y,
        "categoria": categoria,
        "operativa": operativa,
        "categoria_slug": slug,
        "regras_aplicaveis": slug is not None,
        "condicionantes": cond,
    }


# Mapa das camadas de condicionantes (CCGD_PUBLICACAO) por id -> nome.
# Preenchido on-demand para não fixar o catálogo no código.
def condicionantes_layers() -> dict[int, str]:
    meta = _get(f"{BASE}/CCGD_PUBLICACAO/MapServer", {})
    return {l["id"]: l["name"] for l in meta.get("layers", [])}


if __name__ == "__main__":
    # smoke test rápido
    print("Camadas CCGD:", len(condicionantes_layers()))
