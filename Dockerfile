# RAIO — imagem de produção (leve: não inclui os geopackages, que não são
# usados em runtime; a análise vive dos serviços REST + Overture + regras YAML).
FROM python:3.12-slim

WORKDIR /app

# dependências Python (as wheels de geopandas/pyogrio/rasterio/duckdb trazem
# GDAL/GEOS/PROJ embutidos, logo não é preciso apt).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# código e dados de runtime (regras, definições, web, cartografia PDM embutida)
COPY app.py definicoes.yaml parametros_globais.yaml ./
COPY motor/ motor/
COPY regras/ regras/
COPY web/ web/
COPY dados_pdm/ dados_pdm/

ENV RAIO_HOST=0.0.0.0
EXPOSE 8765
# o host pode sobrepor a porta via $PORT (Render, Cloud Run, etc.)
CMD ["python", "app.py"]
