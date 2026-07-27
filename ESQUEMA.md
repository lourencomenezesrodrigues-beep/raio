# RAIO — Esquema dos ficheiros de regra

Um ficheiro YAML por norma (nível da alínea). Campos:

- `id`: identificador estável (diploma-artigo.numero.alinea)
- `diploma`: fonte e versão
- `norma`: citação formal
- `categoria`: categoria de solo a que se aplica
- `tema`: o que a regra condiciona
- `texto`: transcrição integral da norma
- `parametros`: valores numéricos e referências extraídos do texto
- `clarificacoes`: newsletters e RPDM comentado ligados à norma
- `computabilidade`: `automatica` (só com a parcela) | `automatica_com_edificado`
  (requer dados de alturas/fachadas) | `semi` (computável mas dependente de
  informação não disponível ou só relevante em fase de projecto) |
  `apreciacao` (discricionária; gera "carece de análise" ou limite superior)
- `entradas`: dados necessários ao cálculo
- `efeito`: como entra no envelope/capacidade
- `papel_no_intervalo`: `base` (limite inferior) | `excepcao_superior` | `nota`

Parâmetros globais assumidos em `parametros_globais.yaml`.
Definições regulamentares em `definicoes.yaml`.
Modelo de cálculo do intervalo em `MODELO_CAPACIDADE.md`.
