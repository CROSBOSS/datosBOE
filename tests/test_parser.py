"""Tests con anuncios sintéticos en el formato textual oficial de la Sección A.
IMPORTANTE: validar también contra XML reales descargados (ver README)."""
import json
from pathlib import Path

from borme.db import conectar, cargar_documento
from borme.parser import parsear_anuncio, parsear_xml, normalizar

CONST = ("412345 - ENERGIAS LEVANTE INNOVA SL. Constitución. Comienzo de operaciones: 1.10.26. "
         "Objeto social: Instalación de sistemas fotovoltaicos y almacenamiento. Domicilio: C/ COLON 5 "
         "(VALENCIA). Capital: 3.000,00 Euros. Nombramientos. Adm. Solid.: GARCIA PEREZ JUAN;LOPEZ "
         "MARTI ANA. Datos registrales. T 11234 , F 56, S 8, H V 223344, I/A 1 (20.10.26).")
CADENA = ("412346 - TALLERES RUZAFA S.L.. Ceses/Dimisiones. Adm. Unico: MARTINEZ SOLER PEDRO. "
          "Nombramientos. Liquidador: MARTINEZ SOLER PEDRO. Disolución. Voluntaria. Extinción. "
          "Datos registrales. T 9000 , F 12, S 8, H V 100200, I/A 9 (21.10.26).")
CAPITAL = ("412347 - ENERGIAS LEVANTE INNOVA SL. Ampliación de capital. Capital: 10.000,00 Euros. "
           "Resultante Suscrito: 13.000,00 Euros. Cambio de domicilio social. AV DEL PUERTO 100 "
           "(PATERNA). Datos registrales. T 11234 , F 60, S 8, H V 223344, I/A 2 (28.10.26).")


def test_constitucion():
    a = parsear_anuncio(CONST)
    assert a.numero == 412345 and a.nombre == "ENERGIAS LEVANTE INNOVA SL"
    assert [x.tipo for x in a.actos] == ["Constitución", "Nombramientos", "Datos registrales"]
    c = a.actos[0].campos
    assert c["capital"] == 3000.0 and c["municipio"] == "VALENCIA"
    assert c["objeto_social"].startswith("Instalación de sistemas")
    assert a.actos[1].campos["cargos"] == [
        {"cargo": "Adm. Solid.", "persona": "GARCIA PEREZ JUAN"},
        {"cargo": "Adm. Solid.", "persona": "LOPEZ MARTI ANA"},
    ]
    assert a.hoja == "V-223344" and a.fecha_inscripcion == "2026-10-20"


def test_actos_encadenados_y_nombre_con_abreviatura():
    a = parsear_anuncio(CADENA)
    assert a.nombre == "TALLERES RUZAFA S.L."
    assert [x.tipo for x in a.actos] == ["Ceses/Dimisiones", "Nombramientos", "Disolución",
                                         "Extinción", "Datos registrales"]
    assert a.actos[1].campos["cargos"][0]["cargo"] == "Liquidador"


def test_errata_sin_numero_se_ignora():
    assert parsear_anuncio("Fe de erratas. En el BORME número 100...") is None


def test_normalizar():
    assert normalizar("Talleres Ruzafa, S.L.") == normalizar("TALLERES RUZAFA SL") == "TALLERES RUZAFA"


def _xml(*anuncios, partido=False):
    ps = []
    for an in anuncios:
        if partido:  # anuncio repartido en dos <p>
            i = an.index(" Datos registrales")
            ps += [f"<p>{an[:i]}</p>", f"<p>{an[i + 1:]}</p>"]
        else:
            ps.append(f"<p>{an}</p>")
    return f'<?xml version="1.0" encoding="UTF-8"?><documento><texto>{"".join(ps)}</texto></documento>'.encode()


def test_xml_agrupa_parrafos():
    out = parsear_xml(_xml(CONST, CADENA, partido=True))
    assert [a.numero for a in out] == [412345, 412346]
    assert out[0].hoja == "V-223344"


def test_xml_bloque_unico():
    xml = f"<documento><texto>{CONST} {CADENA}</texto></documento>".encode()
    assert [a.numero for a in parsear_xml(xml)] == [412345, 412346]


def test_xml_error():
    assert parsear_xml(b"<error><descripcion>No existe</descripcion></error>") == []


def test_carga_bd(tmp_path: Path):
    for ident, fecha, cuerpo in [("BORME-A-2026-200-46", "20261021", _xml(CONST, CADENA)),
                                 ("BORME-A-2026-205-46", "20261028", _xml(CAPITAL))]:
        x = tmp_path / f"{ident}.xml"
        x.write_bytes(cuerpo)
        x.with_suffix(".json").write_text(json.dumps(
            {"identificador": ident, "fecha": fecha, "provincia": "VALENCIA", "provincia_cod": "46"}))
        con = conectar(tmp_path / "t.sqlite")
        cargar_documento(con, x)
    emp = {r["nombre"]: r for r in con.execute("SELECT * FROM empresas")}
    e = emp["ENERGIAS LEVANTE INNOVA SL"]
    assert e["capital"] == 13000.0 and e["municipio"] == "PATERNA" and e["estado"] == "activa"
    assert e["fecha_constitucion"] == "2026-10-20" and e["n_actos"] == 6
    assert emp["TALLERES RUZAFA S.L."]["estado"] == "extinguida"
    assert len(emp) == 2


# --- Casos detectados con XML reales (texto sintético con la misma estructura) ---
from borme.parser import municipio


def test_municipio_con_articulo():
    assert municipio("C/ MAYOR 1 (ELIANA (L'))") == "L'ELIANA"
    assert municipio("AV SUR 3 (POBLA DE VALLBONA (LA))") == "LA POBLA DE VALLBONA"
    assert municipio("C/ COLON 5 (VALENCIA).") == "VALENCIA"


def test_separador_guion():
    a = parsear_anuncio("412348 - BODEGAS EJEMPLO SL. MODIFICACION DE ESTATUTOS.- Datos registrales. "
                        "S 8 , H V 15190, I/A 14 (28.10.25).")
    assert a.hoja == "V-15190"


def test_clases_articulo_parrafo_con_cnae_en_objeto():
    xml = ('<documento><texto><p class="articulo">412349 - EDITORIAL EJEMPLO SL.</p>'
           '<p class="parrafo">Constitución. Objeto social: Actividades:</p>'
           '<p class="parrafo">5811 - Edición de libros</p>'
           '<p class="parrafo">Domicilio: C/ PAZ 1 (VALENCIA). Capital: 3.000,00 Euros. Datos registrales. '
           'S 8 , H V 300, I/A 1 (1.10.26).</p>'
           '<p class="articulo">412350 - OTRA EMPRESA SL.</p><p class="parrafo">Extinción. Datos registrales. '
           'S 8 , H V 301, I/A 3 (1.10.26).</p></texto></documento>').encode()
    out = parsear_xml(xml)
    assert [a.numero for a in out] == [412349, 412350]
    assert out[0].actos[0].campos["municipio"] == "VALENCIA"
    assert "Edición de libros" in out[0].actos[0].campos["objeto_social"]


def test_cnae_explicito():
    from borme.cnae import extraer_explicito
    assert extraer_explicito("Actividad principal: 81.22 / Limpieza industrial") == "81"
    assert extraer_explicito('Tendrá por objeto: "CNAE 64.21.-Actividades de holding"') == "64"
    assert extraer_explicito("Restaurantes (Clasificación Nacional de Actividades Económicas 2025: 56.11)") == "56"
    assert extraer_explicito("Compraventa de inmuebles") is None
