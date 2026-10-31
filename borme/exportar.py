"""Exporta la base SQLite a site/data.json para la web estática.

Solo exporta datos de empresas y tipos de acto: no incluye nombres de
administradores ni el texto de los anuncios.

Uso:  python -m borme.exportar --db data/borme.sqlite --out site/data.json
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .cnae_secciones import NOMBRE_DIVISION
from .db import conectar

TIPOS_EVENTO = ("Constitución", "Extinción", "Disolución", "Situación concursal",
                "Ampliación de capital", "Reducción de capital", "Cambio de domicilio social",
                "Cambio de denominación social", "Cambio de objeto social", "Fusión por absorción",
                "Transformación de sociedad", "Reapertura hoja registral")


def exportar(con) -> dict:
    q = lambda sql, *a: [dict(r) for r in con.execute(sql, a).fetchall()]
    ultima = (q("SELECT MAX(fecha) f FROM documentos")[0]["f"]) or datetime.now().date().isoformat()

    tiene_cnae = con.execute("SELECT 1 FROM sqlite_master WHERE name='clasificacion'").fetchone()
    cnae_col = "(SELECT division FROM clasificacion WHERE empresa_id=empresas.id)" if tiene_cnae else "NULL"
    empresas = q(f"""
        SELECT id, nombre n, provincia_cod p, municipio m, estado s, fecha_constitucion fc,
               capital c, objeto_social o, ultima_aparicion u, n_actos k, {cnae_col} d,
               (SELECT MAX(fecha) FROM actos WHERE empresa_id=empresas.id AND tipo='Extinción') fx,
               (SELECT MAX(fecha) FROM actos WHERE empresa_id=empresas.id AND tipo IN
                   ('Situación concursal','Anotación preventiva. Declaración de concurso')) fk
        FROM empresas WHERE ultima_aparicion >= date(?, '-400 days')
        ORDER BY COALESCE(fecha_constitucion, '') DESC, ultima_aparicion DESC LIMIT 30000""", ultima)
    for e in empresas:
        if e["o"] and len(e["o"]) > 400:
            e["o"] = e["o"][:400] + "…"

    marcadores = ",".join("?" * len(TIPOS_EVENTO))
    eventos = q(f"""
        SELECT a.fecha f, a.empresa_id id, a.tipo t FROM actos a
        WHERE a.fecha >= date(?, '-90 days') AND a.tipo IN ({marcadores})
        ORDER BY a.fecha DESC, a.id DESC LIMIT 8000""", ultima, *TIPOS_EVENTO)

    provincias = q("SELECT DISTINCT provincia_cod cod, provincia nombre FROM documentos ORDER BY nombre")

    return {
        "generado": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "ultima_publicacion": ultima,
        "documentos": q("SELECT COUNT(*) n FROM documentos")[0]["n"],
        "provincias": provincias,
        "divisiones": NOMBRE_DIVISION,
        "empresas": empresas,
        "eventos": eventos,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default="data/borme.sqlite")
    p.add_argument("--out", default="site/data.json", type=Path)
    a = p.parse_args(argv)
    datos = exportar(conectar(a.db))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(datos, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{a.out}: {len(datos['empresas'])} empresas, {len(datos['eventos'])} eventos")


if __name__ == "__main__":
    main()
