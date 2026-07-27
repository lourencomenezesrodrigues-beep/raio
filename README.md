# RAIO.

**RAIO** — Regulamentos, Análise, Índices e Ocupação.

Ferramenta open source de análise não vinculativa da capacidade construtiva
de terrenos no concelho do Porto. Um projecto Dinosaur Ideas.

## Estrutura

- `regras/` — motor de regras declarativo (YAML, uma norma por ficheiro)
  - `porto/fuc-1/` — Área de Frente Urbana Contínua de tipo I (RPDM 23.º-25.º)
  - `porto/moradia/` — Área de Edifícios de Tipo Moradia (RPDM 29.º-30.º)
  - `porto/transversais/` — RGEU 59.º, 60.º, 62.º, 73.º (cumulativas)
- `motor/` — motor de cálculo
  - `pdm_arcgis.py` — consulta por ponto ao PDM (categoria + condicionantes)
  - `cercea.py`, `overture.py`, `frente.py` — moda da cércea da frente (Overture)
  - `parcela.py` — métricas a partir do polígono da parcela
  - `engine.py` — despacho ponto/parcela → regras → intervalo de capacidade
  - `ficha.py` + `ficha_template.html`, `mapa.py` — ficha de output (MD/HTML)
- `scripts/` — pipelines (download CCGD, geração de fichas, testes por ponto)
- `testes/` — casos de teste
- `ESQUEMA.md` — esquema dos ficheiros de regra
- `MODELO_CAPACIDADE.md` — modelo do intervalo
- `definicoes.yaml`, `parametros_globais.yaml`
- `dados/`, `saidas/` — dados e fichas geradas (fora do git)

## Fontes de dados

- opendata.porto.digital — geopackages do PDM 2021 (ODbL 1.0)
- fedservergeo.cm-porto.pt/arcgis — consulta por ponto (PDM2021) e cartografia
  base do «Mapas do Porto» (Cartografia/Mapa_Base_Cache)
- Overture Maps — edificado (implantação; altura/nº de pisos de fallback)
- DGT — Levantamento LiDAR de Portugal Continental (MDT+MDS, cdd.dgterritorio.gov.pt):
  altura real do edificado = MDS − MDT; ficheiros em `dados/lidar/` (ver LEIA-ME)
- EPSG:3763 (ETRS89/PT-TM06)

## Ambiente

Python 3.12 num venv do repo (`.venv`). Instalar: `pip install -r requirements.txt`.

## Estado

Regras FUC-I, Moradia e transversais validadas pelo autor (Julho 2026).
Feito: consulta por ponto, moda da cércea (Overture), métricas da parcela,
motor de capacidade (FUC-I e Moradia) e ficha de output com recortes de mapa.
Próximo: camada de pesquisa/mapa (morada/clique/desenho → análise). Não há
dado aberto de parcelas no Porto — a geometria da parcela vem do utilizador.

Análise não vinculativa. Não substitui pedido de informação prévia nem
consulta dos serviços municipais.
