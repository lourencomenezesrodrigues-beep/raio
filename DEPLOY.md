# Deploy do RAIO

A app é um servidor Python (stdlib) sobre os serviços abertos do PDM do Porto,
Overture Maps e as regras YAML. **Não precisa dos geopackages** (dados/) em
runtime — a imagem é leve.

## Variáveis de ambiente
- `PORT` — porta (a maioria dos PaaS define-a; a app usa-a). Localmente: 8765.
- `RAIO_HOST` — `0.0.0.0` em produção (a imagem já o define). Local: 127.0.0.1.
- `RAIO_OVERTURE_REL` — release do Overture (opcional; default no código). Actualizar
  quando o release antigo sair do bucket.
- `RAIO_LIDAR_DIR` — pasta com os GeoTIFF MDT/MDS da DGT (opcional; sem eles usa o
  fallback do Overture).

## Container
```bash
docker build -t raio .
docker run -p 8765:8765 raio            # abre em http://localhost:8765
```

## Hosts recomendados
- **Fly.io / Render** — deploy por container, TLS automático, simples.
  - Render: novo Web Service a partir do repo, runtime Docker; define o domínio depois.
  - Fly: `fly launch` (detecta o Dockerfile), `fly deploy`.
- **VPS (Hetzner ~4 €/mês)** — `docker run` + um reverse-proxy (Caddy) para TLS:
  Caddy trata do certificado Let's Encrypt automaticamente a partir do domínio.

## Domínio (DNS)
Depois de comprar o domínio (Namecheap / Cloudflare / DNS.pt), aponta-o ao host:
- PaaS: adiciona o domínio no painel do serviço e cria o registo **CNAME** que ele indicar.
- VPS: cria um registo **A** para o IP do servidor (e AAAA se IPv6).

## Antes de abrir ao público
- **TLS/HTTPS** — garantido pelo PaaS ou pelo Caddy no VPS (não servir HTTP puro).
- **Geocoder** — o Nominatim (OSM) tem política de uso justo; para volume real,
  usar uma instância dedicada ou um geocoder pago.
- **Rate-limiting** — cada pedido chama serviços externos (CMP/Overture); pôr um
  limite por IP no reverse-proxy evita abuso.
- **Disclaimer** — a app já indica "análise não vinculativa"; manter visível.
