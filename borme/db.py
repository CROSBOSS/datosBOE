"""Carga de los XML descargados en una base SQLite de empresas y actos.

Uso:
    python -m borme.db --raw data/raw --db data/borme.sqlite
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import asdict
from pathlib import Path

from .parser import parsear_xml

ESQUEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS documentos (
    id TEXT PRIMARY KEY, fecha TEXT, provincia_cod TEXT, provincia TEXT,
    n_anuncios INTEGER, procesado_en TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS empresas (
    id INTEGER PRIMARY KEY,
    clave TEXT UNIQUE,              -- provincia+hoja registral, o nombre normalizado
    nombre TEXT, nombre_norm TEXT, provincia_cod TEXT, provincia TEXT, hoja TEXT,
    estado TEXT DEFAULT 'activa',   -- activa | inactiva | concurso | disuelta | extinguida
    fecha_constitucion TEXT, objeto_social TEXT, domicilio TEXT, municipio TEXT,
    capital REAL, primera_aparicion TEXT, ultima_aparicion TEXT, n_actos INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_emp_norm ON empresas(nombre_norm);
CREATE INDEX IF NOT EXISTS ix_emp_mun ON empresas(municipio);
CREATE TABLE IF NOT EXISTS actos (
    id INTEGER PRIMARY KEY, empresa_id INTEGER REFERENCES empresas(id),
    documento_id TEXT, fecha TEXT, numero_anuncio INTEGER,
    tipo TEXT, texto TEXT, campos TEXT,
    UNIQUE(documento_id, numero_anuncio, tipo)
);
CREATE INDEX IF NOT EXISTS ix_actos_tipo_fecha ON actos(tipo, fecha);
CREATE INDEX IF NOT EXISTS ix_actos_emp ON actos(empresa_id);
"""

ESTADO_POR_ACTO = {
    "Extinción": "extinguida",
    "Disolución": "disuelta",
    "Situación concursal": "concurso",
    "Anotación preventiva. Declaración de concurso": "concurso",
    "Reapertura hoja registral": "activa",
    "Cierre provisional hoja registral por baja en el índice de Entidades Jurídicas": "inactiva",
    "Cierre provisional de la hoja registral por revocación del NIF": "inactiva",
    "Cierre provisional hoja registral por no haber depositado cuentas anuales": "inactiva",
    "Reactivación de la sociedad": "activa",
}
PRIORIDAD = {"activa": 0, "inactiva": 1, "concurso": 2, "disuelta": 3, "extinguida": 4}


def conectar(ruta: str | Path) -> sqlite3.Connection:
    con = sqlite3.connect(ruta)
    con.row_factory = sqlite3.Row
    con.executescript(ESQUEMA)
    return con


def _empresa(con, an, meta) -> int:
    clave = f"{meta['provincia_cod']}:{an.hoja}" if an.hoja else f"N:{an.nombre_norm}"
    row = con.execute("SELECT id FROM empresas WHERE clave=?", (clave,)).fetchone()
    if row is None and an.hoja:
        # empresa vista antes sin hoja -> adoptar la clave buena
        row = con.execute("SELECT id FROM empresas WHERE clave=?", (f"N:{an.nombre_norm}",)).fetchone()
        if row:
            con.execute("UPDATE empresas SET clave=?, hoja=? WHERE id=?", (clave, an.hoja, row["id"]))
    if row:
        return row["id"]
    cur = con.execute(
        "INSERT INTO empresas(clave,nombre,nombre_norm,provincia_cod,provincia,hoja,primera_aparicion,ultima_aparicion)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (clave, an.nombre, an.nombre_norm, meta["provincia_cod"], meta["provincia"], an.hoja,
         meta["fecha_iso"], meta["fecha_iso"]),
    )
    return cur.lastrowid


def _aplicar(con, emp_id: int, an, fecha: str):
    e = con.execute("SELECT * FROM empresas WHERE id=?", (emp_id,)).fetchone()
    upd = {"ultima_aparicion": max(e["ultima_aparicion"] or fecha, fecha), "nombre": e["nombre"]}
    estado = e["estado"]
    for a in an.actos:
        c = a.campos
        if a.tipo == "Constitución":
            upd.update(fecha_constitucion=an.fecha_inscripcion or fecha, objeto_social=c.get("objeto_social"),
                       domicilio=c.get("domicilio"), municipio=c.get("municipio"), capital=c.get("capital"))
        elif a.tipo == "Cambio de domicilio social":
            upd.update(domicilio=c.get("domicilio"), municipio=c.get("municipio") or e["municipio"])
        elif a.tipo in ("Cambio de objeto social", "Ampliación del objeto social", "Ampliacion del objeto social"):
            upd["objeto_social"] = c.get("objeto_social")
        elif a.tipo in ("Ampliación de capital", "Reducción de capital") and c.get("capital_resultante"):
            upd["capital"] = c["capital_resultante"]
        elif a.tipo == "Cambio de denominación social" and c.get("nuevo_nombre"):
            upd["nombre"] = c["nuevo_nombre"]
        nuevo = ESTADO_POR_ACTO.get(a.tipo)
        if nuevo and (nuevo == "activa" or PRIORIDAD[nuevo] >= PRIORIDAD.get(estado, 0)):
            estado = nuevo
    upd["estado"] = estado
    sets = ", ".join(f"{k}=?" for k in upd)
    con.execute(f"UPDATE empresas SET {sets}, n_actos=n_actos+? WHERE id=?",
                (*upd.values(), len(an.actos), emp_id))


def cargar_documento(con, xml_path: Path) -> int:
    meta = json.loads(xml_path.with_suffix(".json").read_text())
    f = meta["fecha"]
    meta["fecha_iso"] = f"{f[:4]}-{f[4:6]}-{f[6:]}"
    if con.execute("SELECT 1 FROM documentos WHERE id=?", (meta["identificador"],)).fetchone():
        return 0
    anuncios = parsear_xml(xml_path.read_bytes())
    for an in anuncios:
        emp_id = _empresa(con, an, meta)
        for a in an.actos:
            con.execute(
                "INSERT OR IGNORE INTO actos(empresa_id,documento_id,fecha,numero_anuncio,tipo,texto,campos)"
                " VALUES (?,?,?,?,?,?,?)",
                (emp_id, meta["identificador"], meta["fecha_iso"], an.numero, a.tipo, a.texto,
                 json.dumps(a.campos, ensure_ascii=False)),
            )
        _aplicar(con, emp_id, an, meta["fecha_iso"])
    con.execute("INSERT INTO documentos(id,fecha,provincia_cod,provincia,n_anuncios) VALUES (?,?,?,?,?)",
                (meta["identificador"], meta["fecha_iso"], meta["provincia_cod"], meta["provincia"], len(anuncios)))
    con.commit()
    return len(anuncios)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--raw", default="data/raw", type=Path)
    p.add_argument("--db", default="data/borme.sqlite", type=Path)
    a = p.parse_args(argv)
    a.db.parent.mkdir(parents=True, exist_ok=True)
    con = conectar(a.db)
    # orden cronológico: el estado de cada empresa depende del orden de los actos
    def orden(x: Path):
        partes = x.stem.split("-")  # BORME-A-AAAA-NNN-PP
        num = int(partes[3]) if len(partes) > 3 and partes[3].isdigit() else 0
        return (partes[2] if len(partes) > 2 else "", num, x.name)

    ficheros = sorted(a.raw.rglob("*.xml"), key=orden)
    total = 0
    for x in ficheros:
        n = cargar_documento(con, x)
        if n:
            print(f"{x.name}: {n} anuncios")
        total += n
    print(f"Anuncios cargados: {total}")
    for r in con.execute("SELECT estado, COUNT(*) n FROM empresas GROUP BY estado"):
        print(f"  {r['estado']}: {r['n']}")


if __name__ == "__main__":
    main()
