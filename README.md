# CABE.

Ferramenta open source de análise não vinculativa da capacidade construtiva
de terrenos no concelho do Porto. Um projecto Dinosaur Ideas.

## Estrutura

- `regras/` — motor de regras declarativo (YAML, uma norma por ficheiro)
  - `porto/fuc-1/` — Área de Frente Urbana Contínua de tipo I (RPDM 23.º-25.º)
  - `porto/moradia/` — Área de Edifícios de Tipo Moradia (RPDM 29.º-30.º)
  - `porto/transversais/` — RGEU 59.º, 60.º, 62.º, 73.º (cumulativas)
- `motor/` — motor de cálculo (esqueleto)
- `testes/` — casos de teste
- `ESQUEMA.md` — esquema dos ficheiros de regra
- `MODELO_CAPACIDADE.md` — modelo do intervalo
- `definicoes.yaml`, `parametros_globais.yaml`

## Fontes de dados

- opendata.porto.digital — geopackages do PDM 2021 (ODbL 1.0)
- fedservergeo.cm-porto.pt/arcgis/rest/services/PDM2021 — consulta por ponto
- EPSG:3763 (ETRS89/PT-TM06)

## Estado

Regras FUC-I, Moradia e transversais validadas pelo autor (Julho 2026).
Próximo: download dos geopackages, consulta por ponto, moda da cércea real.

Análise não vinculativa. Não substitui pedido de informação prévia nem
consulta dos serviços municipais.
