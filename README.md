# borme-empresas — MVP

Base de datos de empresas a partir de la Sección A del BORME (actos inscritos):
constituciones, cambios (domicilio, objeto, capital, denominación) y bajas
(disolución, extinción, concurso).

## Puesta en marcha

```bash
pip install -r requirements.txt            # pipeline
pip install -r requirements-dashboard.txt  # solo para el dashboard Streamlit
python -m pytest -q                                   # tests del parser

# 1) Descargar 12 meses de Valencia (código INE 46). ~1 petición/seg -> unos 10 min
python -m borme.ingest --desde 2025-11-01 --provincia 46

# 2) Parsear y cargar en SQLite (data/borme.sqlite) y clasificar por actividad
python -m borme.db
python -m borme.cnae            # --evaluar para medir el acierto

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

## Clasificación por actividad (CNAE)
`borme/cnae.py` asigna a cada empresa una división CNAE (2 dígitos), sin coste:
1. Si el objeto social declara el código ("CNAE 43.22", "Actividad principal: 81.22"), se usa ese (~45% de las constituciones recientes).
2. Para el resto, un modelo TF-IDF + regresión logística entrenado con esos ejemplos. Solo se guarda si la confianza es >= 0,5.
Medido con 12 meses de Valencia: 79% de acierto en la división, ~90% con confianza alta.

## Dónde están los datos
La base (`borme.sqlite.gz`), el `data.json` de la web y los XML por año (`raw-AAAA.tar.gz`) se guardan en la release **datos** del repo, no en git (la base supera el límite de 100 MB de GitHub). Para trabajar en local:
`gh release download datos -p borme.sqlite.gz -D data && gunzip data/borme.sqlite.gz`.
Tras cambiar el parser: Run workflow con **reprocesar** marcado.

## Automatización (GitHub Actions)
El workflow `.github/workflows/borme-diario.yml` se ejecuta de lunes a viernes, descarga los últimos 5 días de Valencia, carga la base clasifica por CNAE y guarda todo en la release `datos`. Para el histórico: pestaña Actions → "BORME diario" → Run workflow, con `desde`.

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
