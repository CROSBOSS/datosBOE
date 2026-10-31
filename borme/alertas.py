"""Alertas de empresas: nuevas constituciones y cambios de estado.

Ejemplos:
    # Empresas constituidas en los últimos 7 días cuyo objeto social mencione estas palabras
    python -m borme.alertas --dias 7 --palabras fotovoltaica,baterías,instalaciones eléctricas

    # Cambios de estado (disolución, extinción, concurso) de una lista de empresas vigiladas
    python -m borme.alertas --dias 30 --vigilar clientes.txt --csv cambios.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
import unicodedata
from datetime import date, timedelta
from pathlib import Path

from .db import conectar
from .parser import normalizar


def _sin_tildes(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if not unicodedata.combining(c))


def constituciones(con, desde: str, palabras: list[str], municipio: str | None):
    filas = con.execute(
        "SELECT e.nombre, e.municipio, e.capital, e.objeto_social, a.fecha FROM actos a "
        "JOIN empresas e ON e.id=a.empresa_id WHERE a.tipo='Constitución' AND a.fecha>=? ORDER BY a.fecha DESC",
        (desde,),
    ).fetchall()
    pals = [_sin_tildes(p.strip()) for p in palabras if p.strip()]
    out = []
    for f in filas:
        obj = _sin_tildes(f["objeto_social"] or "")
        if pals and not any(p in obj for p in pals):
            continue
        if municipio and _sin_tildes(municipio) not in _sin_tildes(f["municipio"] or ""):
            continue
        out.append(dict(f))
    return out


def cambios_vigiladas(con, desde: str, nombres: list[str]):
    norms = {normalizar(n) for n in nombres if n.strip()}
    filas = con.execute(
        "SELECT e.nombre, e.nombre_norm, a.fecha, a.tipo, a.texto FROM actos a JOIN empresas e ON e.id=a.empresa_id "
        "WHERE a.fecha>=? AND a.tipo NOT IN ('Datos registrales') ORDER BY a.fecha DESC",
        (desde,),
    ).fetchall()
    return [{k: f[k] for k in ("fecha", "nombre", "tipo", "texto")} for f in filas if f["nombre_norm"] in norms]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", default="data/borme.sqlite")
    p.add_argument("--dias", type=int, default=7)
    p.add_argument("--palabras", default="", help="Lista separada por comas (busca en el objeto social)")
    p.add_argument("--municipio")
    p.add_argument("--vigilar", type=Path, help="Fichero con un nombre de empresa por línea")
    p.add_argument("--csv", type=Path)
    a = p.parse_args(argv)

    con = conectar(a.db)
    desde = (date.today() - timedelta(days=a.dias)).isoformat()
    if a.vigilar:
        filas = cambios_vigiladas(con, desde, a.vigilar.read_text(encoding="utf-8").splitlines())
    else:
        filas = constituciones(con, desde, a.palabras.split(","), a.municipio)

    print(f"{len(filas)} resultado(s) desde {desde}", file=sys.stderr)
    if not filas:
        return
    destino = a.csv.open("w", newline="", encoding="utf-8") if a.csv else sys.stdout
    w = csv.DictWriter(destino, fieldnames=list(filas[0].keys()))
    w.writeheader()
    w.writerows(filas)


if __name__ == "__main__":
    main()
