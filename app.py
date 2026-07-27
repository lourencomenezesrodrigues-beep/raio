"""Servidor mínimo do RAIO (stdlib) — mapa + API sobre o motor.

Rotas:
  GET /                       -> web/mapa.html
  GET /web/<ficheiro>         -> estáticos
  GET /api/geocode?q=         -> candidatos de morada (JSON)
  GET /api/analisar?lat=&lon= -> categoria + condicionantes no ponto (JSON)
      (aceita também x=&y= em EPSG:3763)
  GET /api/ficha?lat=&lon=[&area=&frente=&prof=] -> ficha HTML

Correr:  .venv\\Scripts\\python.exe app.py   (abre em http://127.0.0.1:8765)
"""
from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "motor"))
import engine  # noqa: E402
import geocode  # noqa: E402
import ficha as ficha_mod  # noqa: E402
from pyproj import Transformer  # noqa: E402
from shapely.geometry import Polygon  # noqa: E402

RAIZ = os.path.dirname(__file__)
WEB = os.path.join(RAIZ, "web")
PORTA = 8765
_to3763 = Transformer.from_crs("EPSG:4326", "EPSG:3763", always_xy=True)


def _xy(qs):
    """Extrai (x, y) EPSG:3763 de x/y directos ou de lat/lon."""
    if "x" in qs and "y" in qs:
        return float(qs["x"][0]), float(qs["y"][0])
    if "lat" in qs and "lon" in qs:
        return _to3763.transform(float(qs["lon"][0]), float(qs["lat"][0]))
    raise ValueError("faltam coordenadas (x,y ou lat,lon)")


def _poligono(pts):
    """[[lat,lon],...] (WGS84) -> shapely Polygon em EPSG:3763."""
    return Polygon([_to3763.transform(lon, lat) for lat, lon in pts])


def _resumo_ponto(res):
    """Reduz o resultado do motor ao essencial para o frontend."""
    return {
        "ponto": res.get("ponto"),
        "categoria": res.get("categoria"),
        "categoria_cod": res.get("categoria_cod"),
        "categoria_slug": res.get("categoria_slug"),
        "operativa": res.get("operativa"),
        "estado": res.get("estado"),
        "condicionantes_efetivas": res.get("condicionantes_efetivas"),
        "condicionantes_ambito_municipal": res.get("condicionantes_ambito_municipal"),
        "avisos": res.get("avisos"),
        "capacidade": res.get("capacidade"),
        "parcela_metricas": res.get("parcela_metricas"),
        "frente": res.get("frente"),
    }


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False)
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):  # silêncio
        pass

    def do_GET(self):
        u = urlparse(self.path)
        qs = parse_qs(u.query)
        try:
            if u.path in ("/", "/index.html"):
                return self._serve_static("mapa.html")
            if u.path.startswith("/web/"):
                return self._serve_static(os.path.basename(u.path))

            if u.path == "/api/geocode":
                q = (qs.get("q") or [""])[0]
                return self._send(200, {"candidatos": geocode.candidatos(q)})

            if u.path == "/api/analisar":
                x, y = _xy(qs)
                return self._send(200, _resumo_ponto(engine.analisar_ponto(x, y)))

            if u.path == "/api/ficha":
                if "poly" in qs:  # polígono desenhado: "lat,lon;lat,lon;..."
                    pts = [[float(a) for a in par.split(",")]
                           for par in qs["poly"][0].split(";") if par]
                    res = engine.analisar_parcela(_poligono(pts), auto_moda=True)
                else:
                    x, y = _xy(qs)
                    parcela = None
                    if all(k in qs for k in ("area", "frente", "prof")):
                        parcela = dict(area_m2=float(qs["area"][0]),
                                       frente_m=float(qs["frente"][0]),
                                       profundidade_m=float(qs["prof"][0]))
                    res = engine.analisar_ponto(x, y, parcela, auto_moda=parcela is not None)
                return self._send(200, ficha_mod.ficha_html(res, com_mapas=True),
                                  ctype="text/html; charset=utf-8")

            self._send(404, {"erro": "rota desconhecida"})
        except Exception as e:  # noqa: BLE001
            self._send(500, {"erro": str(e)})

    def do_POST(self):
        u = urlparse(self.path)
        try:
            if u.path == "/api/parcela":
                n = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(n) or b"{}")
                pts = body.get("coords") or []
                if len(pts) < 3:
                    return self._send(400, {"erro": "polígono precisa de >= 3 pontos"})
                res = engine.analisar_parcela(_poligono(pts), auto_moda=True)
                return self._send(200, _resumo_ponto(res))
            self._send(404, {"erro": "rota desconhecida"})
        except Exception as e:  # noqa: BLE001
            self._send(500, {"erro": str(e)})

    def _serve_static(self, nome):
        caminho = os.path.join(WEB, nome)
        if not os.path.isfile(caminho):
            return self._send(404, {"erro": f"não encontrado: {nome}"})
        ext = os.path.splitext(nome)[1]
        ctype = {".html": "text/html; charset=utf-8", ".js": "text/javascript",
                 ".css": "text/css"}.get(ext, "application/octet-stream")
        with open(caminho, "rb") as f:
            self._send(200, f.read(), ctype=ctype)


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORTA), Handler)
    print(f"RAIO a correr em http://127.0.0.1:{PORTA}  (Ctrl+C para parar)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
