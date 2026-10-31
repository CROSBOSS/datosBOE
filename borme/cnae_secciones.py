"""Divisiones CNAE-2009 (2 dígitos), su sección y un nombre corto para mostrar."""

NOMBRE_DIVISION = {
    "01": "Agricultura y ganadería", "02": "Silvicultura", "03": "Pesca y acuicultura",
    "05": "Extracción de carbón", "06": "Extracción de petróleo y gas", "07": "Extracción de minerales metálicos",
    "08": "Otras industrias extractivas", "09": "Apoyo a industrias extractivas",
    "10": "Industria alimentaria", "11": "Fabricación de bebidas", "12": "Industria del tabaco",
    "13": "Industria textil", "14": "Confección de ropa", "15": "Cuero y calzado", "16": "Madera y corcho",
    "17": "Papel", "18": "Artes gráficas", "19": "Coquerías y refino", "20": "Industria química",
    "21": "Productos farmacéuticos", "22": "Caucho y plásticos", "23": "Productos minerales no metálicos",
    "24": "Metalurgia", "25": "Productos metálicos", "26": "Productos informáticos y electrónicos",
    "27": "Material y equipo eléctrico", "28": "Maquinaria y equipo", "29": "Vehículos de motor",
    "30": "Otro material de transporte", "31": "Muebles", "32": "Otras manufacturas",
    "33": "Reparación e instalación de maquinaria", "35": "Energía eléctrica, gas y vapor",
    "36": "Captación y distribución de agua", "37": "Saneamiento", "38": "Residuos y reciclaje",
    "39": "Descontaminación", "41": "Construcción de edificios", "42": "Ingeniería civil",
    "43": "Construcción especializada", "45": "Venta y reparación de vehículos", "46": "Comercio mayorista",
    "47": "Comercio minorista", "49": "Transporte terrestre", "50": "Transporte marítimo",
    "51": "Transporte aéreo", "52": "Almacenamiento y logística", "53": "Correos y mensajería",
    "55": "Alojamiento", "56": "Restauración", "58": "Edición", "59": "Cine, vídeo y música",
    "60": "Radio y televisión", "61": "Telecomunicaciones", "62": "Programación y consultoría informática",
    "63": "Servicios de información", "64": "Servicios financieros y holdings", "65": "Seguros",
    "66": "Auxiliares financieros", "68": "Actividades inmobiliarias", "69": "Jurídicas y contabilidad",
    "70": "Consultoría de gestión", "71": "Arquitectura e ingeniería", "72": "Investigación y desarrollo",
    "73": "Publicidad y estudios de mercado", "74": "Otras actividades profesionales", "75": "Veterinaria",
    "77": "Alquiler", "78": "Empleo", "79": "Agencias de viajes", "80": "Seguridad e investigación",
    "81": "Limpieza y jardinería", "82": "Servicios administrativos", "84": "Administración pública",
    "85": "Educación", "86": "Actividades sanitarias", "87": "Asistencia en residencias",
    "88": "Servicios sociales sin alojamiento", "90": "Actividades artísticas", "91": "Bibliotecas y museos",
    "92": "Juegos de azar", "93": "Deportes y ocio", "94": "Asociaciones", "95": "Reparación de ordenadores y enseres",
    "96": "Otros servicios personales", "97": "Hogares empleadores", "98": "Hogares productores",
    "99": "Organismos extraterritoriales",
}

_RANGOS = [("A", 1, 3), ("B", 5, 9), ("C", 10, 33), ("D", 35, 35), ("E", 36, 39), ("F", 41, 43),
           ("G", 45, 47), ("H", 49, 53), ("I", 55, 56), ("J", 58, 63), ("K", 64, 66), ("L", 68, 68),
           ("M", 69, 75), ("N", 77, 82), ("O", 84, 84), ("P", 85, 85), ("Q", 86, 88), ("R", 90, 93),
           ("S", 94, 96), ("T", 97, 98), ("U", 99, 99)]

DIVISION_A_SECCION = {d: s for s, a, b in _RANGOS for d in (f"{n:02d}" for n in range(a, b + 1)) if d in NOMBRE_DIVISION}
