"""Contexto por sector: noticias (GDELT) y normativa (BOE, legislación consolidada).

Genera site/contexto.json con, para cada división CNAE:
  {"noticias": [[fecha, fuente, titulo, url], ...], "normativa": [[ambito, titulo, url, fecha], ...]}

Se ejecuta en GitHub Actions (allí hay acceso a internet). Uso:
    python -m borme.contexto --out site/contexto.json

PENDIENTE DE VALIDAR con la primera ejecución real:
- La sintaxis exacta del parámetro `query` de la API de legislación consolidada del BOE
  (documentación: https://www.boe.es/datosabiertos/documentos/APIconsolidada.pdf).
- Que los términos de cada sector devuelven resultados pertinentes en GDELT.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import requests

UA = {"User-Agent": "borme-empresas/0.1 (+https://github.com/CROSBOSS/DatosBOE)"}

# Términos de búsqueda por división CNAE (ampliar con los subnichos de cada sector)
TERMINOS = {
    "56": ["hostelería", "restaurantes", "bares"],
    "55": ["hoteles", "alojamiento turístico"],
    "43": ["reformas", "instaladores", "fontanería", "electricistas"],
    "41": ["promoción de viviendas", "construcción de viviendas"],
    "62": ["empresas tecnológicas", "software", "startups"],
    "68": ["vivienda", "inmobiliarias", "alquiler"],
    "47": ["comercio minorista", "pequeño comercio"],
    "46": ["distribución mayorista"],
    "49": ["transporte de mercancías", "camioneros"],
    "29": ["automoción", "Ford Almussafes"],
    "35": ["energía solar", "almacenamiento de energía"],
    "86": ["clínicas", "sanidad privada"],
}


def noticias_gdelt(terminos: list[str], lugar: str = "Valencia", meses: int = 3, maximo: int = 8) -> list:
    """GDELT DOC 2.0: artículos en español de medios españoles que mencionan el sector y el lugar."""
    q = "(" + " OR ".join(f'"{t}"' for t in terminos) + f") {lugar} sourcecountry:SP sourcelang:spanish"
    r = requests.get("https://api.gdeltproject.org/api/v2/doc/doc", headers=UA, timeout=40, params={
        "query": q, "mode": "ArtList", "format": "json", "maxrecords": 50, "timespan": f"{meses}months", "sort": "DateDesc"})
    if r.status_code != 200 or not r.text.strip().startswith("{"):
        return []
    vistos, out = set(), []
    for a in r.json().get("articles", []):
        t = (a.get("title") or "").strip()
        clave = t.lower()[:80]
        if not t or clave in vistos:
            continue
        vistos.add(clave)
        f = a.get("seendate", "")[:8]
        out.append([f"{f[:4]}-{f[4:6]}-{f[6:8]}" if len(f) == 8 else "", a.get("domain", ""), t, a.get("url", "")])
        if len(out) >= maximo:
            break
    return out


def normativa_boe(terminos: list[str], maximo: int = 10) -> list:
    """Legislación consolidada vigente cuyo título contiene alguno de los términos."""
    texto = " OR ".join(terminos)
    consulta = {"query": {"query_string": {"query": f"titulo:({texto})"}}, "sort": [{"fecha_actualizacion": "desc"}]}
    r = requests.get("https://www.boe.es/datosabiertos/api/legislacion-consolidada", headers={**UA, "Accept": "application/json"},
                     timeout=40, params={"query": json.dumps(consulta, ensure_ascii=False), "limit": maximo})
    if r.status_code != 200:
        return []
    data = r.json().get("data", [])
    out = []
    for n in data if isinstance(data, list) else []:
        ambito = (n.get("ambito") or {}).get("texto", "") if isinstance(n.get("ambito"), dict) else n.get("ambito", "")
        vig = n.get("estado_consolidacion") or {}
        if isinstance(vig, dict) and "derog" in str(vig.get("texto", "")).lower():
            continue
        ident = n.get("identificador", "")
        out.append([ambito, n.get("titulo", ""), f"https://www.boe.es/buscar/act.php?id={ident}" if ident else n.get("url_html_consolidada", ""),
                    n.get("fecha_publicacion", "")])
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", default="site/contexto.json", type=Path)
    p.add_argument("--lugar", default="Valencia")
    a = p.parse_args(argv)
    res = {}
    for div, terms in TERMINOS.items():
        try:
            res[div] = {"noticias": noticias_gdelt(terms, a.lugar), "normativa": normativa_boe(terms)}
        except requests.RequestException as e:
            print(f"{div}: error {e}")
            res[div] = {"noticias": [], "normativa": []}
        print(f"{div}: {len(res[div]['noticias'])} noticias, {len(res[div]['normativa'])} normas")
        time.sleep(1.5)  # GDELT limita la frecuencia de consultas
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
