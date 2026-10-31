# borme-empresas — MVP

Base de datos de empresas a partir de la Sección A del BORME (actos inscritos):
constituciones, cambios (domicilio, objeto, capital, denominación) y bajas
(disolución, extinción, concurso).

## Puesta en marcha

```bash
pip install -r requirements.txt
python -m pytest -q                                   # tests del parser

# 1) Descargar 12 meses de Valencia (código INE 46). ~1 petición/seg -> unos 10 min
python -m borme.ingest --desde 2025-11-01 --provincia 46

# 2) Parsear y cargar en SQLite (data/borme.sqlite)
python -m borme.db

# 3) Dashboard
streamlit run dashboard.py

# 4) Alertas
python -m borme.alertas --dias 7 --palabras fotovolt,almacenamiento,baterías
python -m borme.alertas --dias 30 --vigilar clientes.txt --csv cambios.csv
```

Varias provincias: repite `--provincia` (`--provincia 46 --provincia 03 --provincia 12`).
Sin `--provincia` descarga toda España (~50 XML por día).

Edita el `User-Agent` de `borme/ingest.py` con tu email de contacto.

## Estructura

| Fichero | Qué hace |
|---|---|
| `borme/ingest.py` | Sumario diario (API datos abiertos BOE) -> XML provinciales en `data/raw/` |
| `borme/parser.py` | Anuncio -> empresa + lista de actos con campos (escáner por vocabulario) |
| `borme/db.py` | Carga en SQLite: `empresas`, `actos`, `documentos`; calcula el estado |
| `borme/alertas.py` | Constituciones por palabras clave/municipio y cambios en empresas vigiladas |
| `dashboard.py` | KPIs, altas/bajas por semana, municipios, tabla exportable |

## Identidad de empresa
Clave = provincia + hoja registral (`46:V-223344`). Si un anuncio no trae hoja,
se usa el nombre normalizado y se fusiona cuando aparece la hoja.

## Primera validación con datos reales (importante)
El parser se ha probado con anuncios sintéticos en el formato oficial; no con XML
reales. Tras la primera descarga:
1. Revisa actos sin clasificar:
   `sqlite3 data/borme.sqlite "SELECT nombre, n_actos FROM empresas WHERE n_actos=0 LIMIT 20"`
2. Si aparecen tipos de acto nuevos, añádelos a `ACTOS` en `parser.py`
   (y cargos a `CARGOS`). Borra `data/borme.sqlite` y vuelve a cargar: los XML
   en bruto se conservan.
3. Compara 50 anuncios con el PDF del BORME de ese día.

## Automatización (GitHub Actions)
El workflow `.github/workflows/borme-diario.yml` se ejecuta de lunes a viernes, descarga los últimos 5 días de Valencia, carga la base y hace commit de `data/`. Para el histórico: pestaña Actions → "BORME diario" → Run workflow, con `desde`.

## Web
`site/index.html` es una web estática (sin servidor) que lee `site/data.json`.
El workflow lo regenera en cada ejecución y lo publica en GitHub Pages.
Activar una vez: Settings → Pages → Source: **GitHub Actions**.
En local: `python -m borme.exportar && python -m http.server -d site`.

## Siguientes pasos
- Envío de alertas por email/Teams (cron diario tras la publicación, ~7:30).
- Histórico desde 2009 y todas las provincias -> pasar a PostgreSQL.
- Tabla `personas`/`cargos` para el grafo de administradores.
- Enriquecer con CNAE (a partir del objeto social) y geocodificar domicilios.
