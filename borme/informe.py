"""Resumen en Markdown del estado de la base (se usa en el resumen de GitHub Actions)."""
from __future__ import annotations

import argparse
import re

from .db import conectar


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="data/borme.sqlite")
    a = p.parse_args(argv)
    con = conectar(a.db)
    q = lambda sql, *args: con.execute(sql, args).fetchall()

    print("## BORME – resumen\n")
    tot = q("SELECT COUNT(*) n, MIN(fecha) d, MAX(fecha) h FROM documentos")[0]
    print(f"Documentos: **{tot['n']}** ({tot['d']} → {tot['h']}) · "
          f"Empresas: **{q('SELECT COUNT(*) n FROM empresas')[0]['n']}**\n")

    print("### Últimos 5 días de publicación\n")
    print("| Fecha | Anuncios | Constituciones | Extinciones | Concursos |\n|---|---|---|---|---|")
    for r in q("""SELECT d.fecha, SUM(d.n_anuncios) n,
                  (SELECT COUNT(*) FROM actos WHERE fecha=d.fecha AND tipo='Constitución') c,
                  (SELECT COUNT(*) FROM actos WHERE fecha=d.fecha AND tipo='Extinción') e,
                  (SELECT COUNT(*) FROM actos WHERE fecha=d.fecha AND tipo='Situación concursal') s
                  FROM documentos d GROUP BY d.fecha ORDER BY d.fecha DESC LIMIT 5"""):
        print(f"| {r['fecha']} | {r['n']} | {r['c']} | {r['e']} | {r['s']} |")

    print("\n### Calidad del parser\n")
    sin = q("SELECT COUNT(*) n FROM empresas WHERE n_actos=0")[0]["n"]
    sin_hoja = q("SELECT COUNT(*) n FROM empresas WHERE hoja IS NULL")[0]["n"]
    print(f"- Empresas sin ningún acto reconocido: **{sin}**")
    print(f"- Empresas sin hoja registral: **{sin_hoja}**")
    # Posibles actos no reconocidos: frases tipo '. Xxxx xxx.' dentro del texto de otros actos
    sospechas: dict[str, int] = {}
    for r in q("SELECT texto FROM actos WHERE tipo NOT IN ('Constitución','Cambio de objeto social') "
               "AND fecha >= (SELECT MAX(fecha) FROM documentos) LIMIT 5000"):
        for m in re.finditer(r"(?:^|\.\s)([A-ZÁÉÍÓÚ][a-záéíóúñ]+(?: [a-záéíóúñ/]+){0,6})\.(?=\s|$)", r["texto"] or ""):
            if m.group(1) in ("Adm", "Voluntaria", "Apo", "Con", "Cons"):
                continue
            sospechas[m.group(1)] = sospechas.get(m.group(1), 0) + 1
    if sospechas:
        print("- Posibles tipos de acto no reconocidos (revisar y añadir a `ACTOS`):")
        for k, v in sorted(sospechas.items(), key=lambda x: -x[1])[:15]:
            print(f"  - `{k}` ×{v}")


if __name__ == "__main__":
    main()
