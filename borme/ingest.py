"""Descarga de sumarios y XML provinciales de la Sección A del BORME.

Uso:
    python -m borme.ingest --desde 2025-11-01 --hasta 2026-10-30 --provincia 46

Guarda cada XML en bruto en data/raw/AAAA/MM/<identificador>.xml para poder
re-parsear sin volver a descargar.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

API_SUMARIO = "https://www.boe.es/datosabiertos/api/borme/sumario/{fecha}"
URL_XML_FALLBACK = "https://www.boe.es/diario_borme/xml.php?id={id}"
HEADERS = {
    "User-Agent": "borme-empresas/0.1 (+https://github.com/CROSBOSS/DatosBOE)",
    "Accept": "application/json",
}
PAUSA_S = 1.0  # máx. ~1 petición/segundo


def _lista(x):
    """La API devuelve dict cuando hay un solo elemento y list cuando hay varios."""
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def _url(v):
    if isinstance(v, dict):
        return v.get("texto") or v.get("#text")
    return v


def _get(session: requests.Session, url: str, accept: str, intentos: int = 4):
    for i in range(intentos):
        try:
            r = session.get(url, headers={**HEADERS, "Accept": accept}, timeout=30)
            time.sleep(PAUSA_S)
            if r.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"HTTP {r.status_code}")
            return r
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError):
            if i == intentos - 1:
                raise
            time.sleep(2 ** (i + 1))


def items_seccion_a(sumario_json: dict) -> list[dict]:
    """Devuelve los items (uno por provincia) de la Sección A de un sumario."""
    data = sumario_json.get("data", sumario_json)
    sumario = data.get("sumario", data)
    items = []
    for diario in _lista(sumario.get("diario")):
        for seccion in _lista(diario.get("seccion")):
            if str(seccion.get("codigo", "")).upper() != "A":
                continue
            for it in _lista(seccion.get("item")):
                ident = it.get("identificador", "")
                items.append({
                    "identificador": ident,
                    "provincia": (it.get("titulo") or "").strip(),
                    "provincia_cod": ident.rsplit("-", 1)[-1] if ident else "",
                    "url_xml": _url(it.get("url_xml")) or URL_XML_FALLBACK.format(id=ident),
                })
    return items


def descargar_dia(session, d: date, raw_dir: Path, provincias: set[str] | None) -> int:
    fecha = d.strftime("%Y%m%d")
    r = _get(session, API_SUMARIO.format(fecha=fecha), "application/json")
    # Días sin publicación: 404 (a veces con cuerpo XML aunque pidas JSON)
    if r.status_code == 404:
        return 0
    r.raise_for_status()
    try:
        sumario = r.json()
    except ValueError:
        print(f"  {fecha}: respuesta no JSON, se omite")
        return 0

    n = 0
    for it in items_seccion_a(sumario):
        if provincias and it["provincia_cod"] not in provincias:
            continue
        destino = raw_dir / fecha[:4] / fecha[4:6] / f"{it['identificador']}.xml"
        if destino.exists():
            continue
        rx = _get(session, it["url_xml"], "application/xml")
        body = rx.content
        # Provincia sin documento: HTTP 200 con <error> dentro -> no cachear
        if rx.status_code != 200 or b"<error" in body[:500]:
            print(f"  {it['identificador']}: sin documento ({rx.status_code})")
            continue
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(body)
        meta = {**it, "fecha": fecha}
        destino.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False))
        n += 1
    return n


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--desde", required=True, type=lambda s: datetime.strptime(s, "%Y-%m-%d").date())
    p.add_argument("--hasta", type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(), default=date.today())
    p.add_argument("--provincia", action="append",
                   help="Código INE de 2 dígitos (46=Valencia). Repetible. Sin él: todas.")
    p.add_argument("--raw", default="data/raw", type=Path)
    a = p.parse_args(argv)

    provincias = {c.zfill(2) for c in a.provincia} if a.provincia else None
    s = requests.Session()
    d, total = a.desde, 0
    while d <= a.hasta:
        if d.weekday() < 5:  # el BORME se publica en días hábiles
            n = descargar_dia(s, d, a.raw, provincias)
            total += n
            if n:
                print(f"{d}: {n} documento(s)")
        d += timedelta(days=1)
    print(f"Total descargado: {total}")


if __name__ == "__main__":
    main()
