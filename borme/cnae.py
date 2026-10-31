"""Clasificación de empresas por actividad (CNAE, nivel división = 2 dígitos).

Dos pasos, sin coste ni servicios externos:
1. Extracción explícita: muchos objetos sociales incluyen el código CNAE
   ("CNAE 43.22", "Actividad principal: 81.22"...).
2. Para el resto, un modelo TF-IDF + regresión logística entrenado con los
   ejemplos del paso 1 (autoetiquetado). Se reentrena solo cada vez que se ejecuta.

Uso:
    python -m borme.cnae --db data/borme.sqlite            # clasifica y guarda
    python -m borme.cnae --db data/borme.sqlite --evaluar  # mide el acierto
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import unicodedata

from .cnae_secciones import DIVISION_A_SECCION, NOMBRE_DIVISION

_CLAVE = re.compile(
    r"(CNAE|C\.N\.A\.E|Actividad(?:es)? principal|Clasificaci[oó]n Nacional de Actividades Econ[oó]micas|"
    r"c[oó]digo de actividad|epígrafe)", re.I)
_CODIGO = re.compile(r"(?<![\d.,])(\d{2})(?:[.,]?(\d{1,2}))?(?![\d])")
_ANIOS = {"1993", "2009", "2025"}


def extraer_explicito(objeto: str | None) -> str | None:
    """Devuelve la división CNAE (2 dígitos) si el texto la declara."""
    if not objeto:
        return None
    for k in _CLAVE.finditer(objeto):
        ventana = objeto[k.end(): k.end() + 120]
        for m in _CODIGO.finditer(ventana):
            dos, resto = m.group(1), m.group(2) or ""
            if dos + resto in _ANIOS:
                continue  # "CNAE 2009" / "2025" es el año de la clasificación, no el código
            if dos in DIVISION_A_SECCION:
                return dos
    return None


def limpiar(objeto: str) -> str:
    """Texto para el modelo: sin códigos ni menciones a la CNAE (para no 'hacer trampa')."""
    s = unicodedata.normalize("NFKD", objeto.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"c\.?n\.?a\.?e\.?|clasificacion nacional de actividades economicas|codigo de actividad", " ", s)
    s = re.sub(r"\d+", " ", s)
    return re.sub(r"\W+", " ", s).strip()


def _modelo():
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    return make_pipeline(
        TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=200_000, sublinear_tf=True),
        LogisticRegression(max_iter=2000, C=4.0),
    )


def _datos(con):
    filas = con.execute("SELECT id, objeto_social FROM empresas WHERE objeto_social IS NOT NULL").fetchall()
    etiquetadas, sin = [], []
    for id_, obj in filas:
        d = extraer_explicito(obj)
        (etiquetadas if d else sin).append((id_, obj, d))
    return etiquetadas, sin


def evaluar(con) -> dict:
    from sklearn.model_selection import train_test_split
    etiquetadas, sin = _datos(con)
    X = [limpiar(o) for _, o, _ in etiquetadas]
    y = [d for *_, d in etiquetadas]
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=0)
    m = _modelo().fit(Xtr, ytr)
    pred = m.predict(Xte)
    proba = m.predict_proba(Xte).max(axis=1)
    acierto_div = sum(p == t for p, t in zip(pred, yte)) / len(yte)
    acierto_sec = sum(DIVISION_A_SECCION[p] == DIVISION_A_SECCION[t] for p, t in zip(pred, yte)) / len(yte)
    seguros = [(p, t) for p, t, c in zip(pred, yte, proba) if c >= 0.5]
    return {
        "etiquetadas": len(etiquetadas), "sin_codigo": len(sin),
        "acierto_division": round(acierto_div, 3), "acierto_seccion": round(acierto_sec, 3),
        "cobertura_confianza_50": round(len(seguros) / len(yte), 3),
        "acierto_division_confianza_50": round(sum(p == t for p, t in seguros) / max(1, len(seguros)), 3),
    }


def clasificar(con, umbral: float = 0.5) -> dict:
    con.execute("CREATE TABLE IF NOT EXISTS clasificacion (empresa_id INTEGER PRIMARY KEY, division TEXT, "
                "seccion TEXT, origen TEXT, confianza REAL)")
    etiquetadas, sin = _datos(con)
    con.execute("DELETE FROM clasificacion")
    con.executemany("INSERT INTO clasificacion VALUES (?,?,?,?,?)",
                    [(i, d, DIVISION_A_SECCION[d], "explicito", 1.0) for i, _, d in etiquetadas])
    n_modelo = 0
    if len(etiquetadas) >= 200 and sin:
        m = _modelo().fit([limpiar(o) for _, o, _ in etiquetadas], [d for *_, d in etiquetadas])
        proba = m.predict_proba([limpiar(o) for _, o, _ in sin])
        clases = m.classes_
        filas = []
        for (i, _, _), p in zip(sin, proba):
            j = p.argmax()
            if p[j] >= umbral:
                d = clases[j]
                filas.append((i, d, DIVISION_A_SECCION[d], "modelo", round(float(p[j]), 3)))
        con.executemany("INSERT INTO clasificacion VALUES (?,?,?,?,?)", filas)
        n_modelo = len(filas)
    con.commit()
    total = len(etiquetadas) + len(sin)
    return {"con_objeto": total, "explicito": len(etiquetadas), "modelo": n_modelo,
            "sin_clasificar": total - len(etiquetadas) - n_modelo}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", default="data/borme.sqlite")
    p.add_argument("--evaluar", action="store_true")
    a = p.parse_args(argv)
    con = sqlite3.connect(a.db)
    print(evaluar(con) if a.evaluar else clasificar(con))


if __name__ == "__main__":
    main()
