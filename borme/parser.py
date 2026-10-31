"""Parser de la Sección A del BORME (actos inscritos).

Cada anuncio tiene la forma:
    123456 - NOMBRE EMPRESA SL. Constitución. Comienzo de operaciones: 1.10.26.
    Objeto social: ... Domicilio: C/ ... (VALENCIA). Capital: 3.000,00 Euros.
    Nombramientos. Adm. Unico: APELLIDOS NOMBRE. Datos registrales. T 1234 ,
    F 56, S 8, H V 123456, I/A 1 (20.10.26).

Un anuncio encadena varios actos, así que se usa un escáner por vocabulario
de actos conocido en lugar de regex línea a línea.
"""
from __future__ import annotations

import re
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

# --- Vocabulario de actos (añadir aquí los que aparezcan como 'desconocido') ---
ACTOS = [
    "Constitución", "Nombramientos", "Ceses/Dimisiones", "Revocaciones", "Reelecciones",
    "Cancelaciones de oficio de nombramientos",
    "Ampliación de capital", "Reducción de capital", "Desembolso de dividendos pasivos",
    "Cambio de domicilio social", "Cambio de objeto social", "Cambio de denominación social",
    "Ampliacion del objeto social", "Ampliación del objeto social",
    "Modificaciones estatutarias", "Modificación de poderes",
    "Declaración de unipersonalidad", "Pérdida del caracter de unipersonalidad",
    "Pérdida del carácter de unipersonalidad", "Cambio de identidad del socio único",
    "Sociedad unipersonal", "Disolución", "Extinción", "Situación concursal",
    "Fusión por absorción", "Fusión por unión", "Escisión parcial", "Escisión total",
    "Segregación", "Cesión global de activo y pasivo", "Transformación de sociedad",
    "Otros conceptos", "Datos registrales", "Reapertura hoja registral",
    "Cierre provisional hoja registral por baja en el índice de Entidades Jurídicas",
    "Cierre provisional de la hoja registral por revocación del NIF",
    "Cierre provisional hoja registral por no haber depositado cuentas anuales",
    "Primera inscripción", "Apertura de sucursal", "Cierre de sucursal",
    "Página web de la sociedad", "Emisión de obligaciones", "Depósito de libros",
    "Adaptación Ley 2/95", "Adaptación Ley 44/2015", "Adaptada segun D.T. 2 apartado 2 Ley 2/95",
    "Acuerdo de ampliación de capital social sin ejecutar", "Crédito incobrable",
    "Empresario Individual", "Anotación preventiva. Declaración de concurso",
    "Articulo 378.5 del Reglamento del Registro Mercantil",
    "Fe de erratas", "Reactivación de la sociedad", "Unipersonalidad",
]
_ACTOS_RE = re.compile(
    r"(?:^|(?<=\.\s))(" + "|".join(re.escape(a) for a in sorted(set(ACTOS), key=len, reverse=True)) + r")(?=[.:]\s|[.:]?$)"
)

# Cargos conocidos (para separar "Cargo: Persona;Persona.")
CARGOS = [
    "Adm. Unico", "Adm. Solid.", "Adm. Mancom.", "Adm. Concursal", "Administrador",
    "Apoderado", "Apo.Sol.", "Apo.Man.", "Apo.Manc.", "Apo.Man.Soli", "Apo.Sol.Man",
    "Consejero", "Con.Delegado", "Cons.Del.Man", "Cons.Del.Sol", "Presidente", "Vicepresid.",
    "Secretario", "Vicesecret.", "Liquidador", "Liquidador M", "Liquidador S", "Liquidador Ma",
    "Auditor", "Aud.Supl.", "Aud.C.Con.", "Socio único", "Socio unico", "Repres.143 RRM",
    "Miem.Com.Ej.", "Miem.Con.Rec", "Pres.Com.Ej.", "Entid.Deposit.", "Rep.Permanen",
    "Comisario", "Interventor", "Gerente", "Director", "Mien.Junta.", "Pres.Junta",
    "Sec.Junta", "Tesorero", "Vocal",
]
_CARGOS_RE = re.compile(
    r"(?:^|(?<=\.\s)|(?<=;\s))(" + "|".join(re.escape(c) for c in sorted(set(CARGOS), key=len, reverse=True)) + r"):\s"
)

_CABECERA_RE = re.compile(r"^\s*(\d{3,7})\s*-\s*(.+)$", re.S)
_HOJA_RE = re.compile(r"\bH\s+([A-Z]{1,3})\s*[- ]?\s*(\d+)")
_FECHA_INS_RE = re.compile(r"\((\d{1,2})\.(\d{1,2})\.(\d{2,4})\)")
_CAMPOS_CONST_RE = re.compile(r"(?:^|(?<=\.\s))(Comienzo de operaciones|Objeto social|Domicilio|Capital|Duración):\s")
_ABREV_FINAL_RE = re.compile(r"(?:\b[A-Z]{1,5}\.){2,}$")  # S.L. S.A. S.L.P. S.COOP. ...


def normalizar(nombre: str) -> str:
    s = unicodedata.normalize("NFKD", nombre.upper())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\b(SOCIEDAD LIMITADA|S L|SL|SOCIEDAD ANONIMA|S A|SA|SLU|S L U|SAU|SLP|S L P|EN LIQUIDACION)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def importe(texto: str | None) -> float | None:
    if not texto:
        return None
    m = re.search(r"(\d{1,3}(?:\.\d{3})*(?:,\d+)?|\d+(?:,\d+)?)\s*(Euros|Pesetas)", texto)
    if not m:
        return None
    v = float(m.group(1).replace(".", "").replace(",", "."))
    return round(v / 166.386, 2) if m.group(2) == "Pesetas" else v


@dataclass
class Acto:
    tipo: str
    texto: str
    campos: dict = field(default_factory=dict)


@dataclass
class Anuncio:
    numero: int
    nombre: str
    nombre_norm: str
    actos: list[Acto]
    texto: str
    hoja: str | None = None
    fecha_inscripcion: str | None = None


def _limpiar_nombre(nombre: str) -> str:
    nombre = nombre.strip()
    if nombre.endswith(".."):
        return nombre[:-1]
    if _ABREV_FINAL_RE.search(nombre):
        return nombre  # termina en abreviatura (S.L.), el punto es suyo
    return nombre[:-1] if nombre.endswith(".") else nombre


def _cargos(texto: str) -> list[dict]:
    """'Adm. Solid.: A;B. Apoderado: C.' -> [{cargo, persona}, ...]"""
    out = []
    ms = list(_CARGOS_RE.finditer(texto))
    for i, m in enumerate(ms):
        fin = ms[i + 1].start() if i + 1 < len(ms) else len(texto)
        valor = texto[m.end():fin].strip().rstrip(".").strip()
        for persona in valor.split(";"):
            persona = persona.strip().rstrip(".").strip()
            if persona:
                out.append({"cargo": m.group(1), "persona": persona})
    return out


def _campos_constitucion(texto: str) -> dict:
    ms = list(_CAMPOS_CONST_RE.finditer(texto))
    out = {}
    for i, m in enumerate(ms):
        fin = ms[i + 1].start() if i + 1 < len(ms) else len(texto)
        out[m.group(1)] = texto[m.end():fin].strip().rstrip(".").strip()
    res = {
        "comienzo_operaciones": out.get("Comienzo de operaciones"),
        "objeto_social": out.get("Objeto social"),
        "domicilio": out.get("Domicilio"),
        "capital": importe(out.get("Capital")),
    }
    if res["domicilio"]:
        mm = re.findall(r"\(([^()]+)\)", res["domicilio"])
        res["municipio"] = mm[-1].strip() if mm else None
    return res


def _campos_acto(tipo: str, texto: str) -> dict:
    if tipo == "Constitución":
        return _campos_constitucion(texto)
    if tipo in ("Nombramientos", "Ceses/Dimisiones", "Revocaciones", "Reelecciones",
                "Declaración de unipersonalidad", "Cambio de identidad del socio único",
                "Sociedad unipersonal"):
        return {"cargos": _cargos(texto)}
    if tipo in ("Ampliación de capital", "Reducción de capital", "Desembolso de dividendos pasivos"):
        antes, _, despues = texto.partition("Resultante Suscrito:")
        return {"importe": importe(antes), "capital_resultante": importe(despues) if despues else None}
    if tipo == "Cambio de domicilio social":
        mm = re.findall(r"\(([^()]+)\)", texto)
        return {"domicilio": texto.strip().rstrip("."), "municipio": mm[-1].strip() if mm else None}
    if tipo == "Cambio de denominación social":
        return {"nuevo_nombre": _limpiar_nombre(texto.strip())}
    if tipo in ("Cambio de objeto social", "Ampliación del objeto social", "Ampliacion del objeto social"):
        return {"objeto_social": texto.strip().rstrip(".")}
    if tipo == "Datos registrales":
        h = _HOJA_RE.search(texto)
        f = _FECHA_INS_RE.search(texto)
        fecha = None
        if f:
            d, mth, y = f.groups()
            y = int(y) + (2000 if len(y) == 2 and int(y) < 70 else 1900 if len(y) == 2 else 0)
            fecha = f"{y:04d}-{int(mth):02d}-{int(d):02d}"
        return {"hoja": f"{h.group(1)}-{h.group(2)}" if h else None, "fecha_inscripcion": fecha}
    return {}


def parsear_anuncio(texto: str) -> Anuncio | None:
    texto = re.sub(r"\s+", " ", texto).strip()
    m = _CABECERA_RE.match(texto)
    if not m:
        return None  # p.ej. fe de erratas sin número
    numero, resto = int(m.group(1)), m.group(2)
    ms = list(_ACTOS_RE.finditer(resto))
    if not ms:
        return Anuncio(numero, _limpiar_nombre(resto), normalizar(_limpiar_nombre(resto)), [], texto)
    nombre = _limpiar_nombre(resto[:ms[0].start()])
    actos = []
    for i, a in enumerate(ms):
        fin = ms[i + 1].start() if i + 1 < len(ms) else len(resto)
        cuerpo = resto[a.end():fin].lstrip(".:").strip()
        actos.append(Acto(a.group(1), cuerpo, _campos_acto(a.group(1), cuerpo)))
    an = Anuncio(numero, nombre, normalizar(nombre), actos, texto)
    for a in actos:
        if a.tipo == "Datos registrales":
            an.hoja = a.campos.get("hoja")
            an.fecha_inscripcion = a.campos.get("fecha_inscripcion")
    return an


def _parrafos_xml(contenido: bytes) -> list[str]:
    try:
        root = ET.fromstring(contenido)
    except ET.ParseError:
        txt = re.sub(rb"<[^>]+>", b"\n", contenido).decode("utf-8", "replace")
        return [l for l in txt.splitlines() if l.strip()]
    if root.tag == "error":
        return []
    texto = root.find(".//texto")
    base = texto if texto is not None else root
    ps = ["".join(p.itertext()) for p in base.iter() if p.tag == "p"]
    if not ps:
        ps = ["".join(base.itertext())]
    return [p for p in ps if p.strip()]


def parsear_xml(contenido: bytes) -> list[Anuncio]:
    """Agrupa párrafos en anuncios (un anuncio empieza por 'NNNNNN - ')."""
    bloques: list[str] = []
    for p in _parrafos_xml(contenido):
        p = re.sub(r"\s+", " ", p).strip()
        # si todo el texto viene en un bloque, separar por cabeceras
        partes = re.split(r"(?<=\.)\s+(?=\d{3,7} - [A-ZÁÉÍÓÚÑÜ0-9\"'(])", p)
        for parte in partes:
            if _CABECERA_RE.match(parte) or not bloques:
                bloques.append(parte)
            else:
                bloques[-1] += " " + parte
    return [a for a in (parsear_anuncio(b) for b in bloques) if a]
