"""Dashboard MVP de empresas BORME.  Ejecutar:  streamlit run dashboard.py"""
import sqlite3

import pandas as pd
import streamlit as st

DB = "data/borme.sqlite"
st.set_page_config(page_title="Empresas BORME", layout="wide")


@st.cache_data(ttl=600)
def cargar():
    con = sqlite3.connect(DB)
    emp = pd.read_sql("SELECT * FROM empresas", con)
    actos = pd.read_sql("SELECT empresa_id, fecha, tipo FROM actos", con, parse_dates=["fecha"])
    return emp, actos


emp, actos = cargar()
st.title("Empresas en el BORME")

with st.sidebar:
    provs = sorted(emp["provincia"].dropna().unique())
    prov = st.multiselect("Provincia", provs, default=provs)
    texto = st.text_input("Objeto social contiene", "")
    muni = st.text_input("Municipio contiene", "")

f = emp[emp["provincia"].isin(prov)]
if texto:
    f = f[f["objeto_social"].fillna("").str.contains(texto, case=False, regex=False)]
if muni:
    f = f[f["municipio"].fillna("").str.contains(muni, case=False, regex=False)]
a = actos[actos["empresa_id"].isin(f["id"])]

ult30 = a[a["fecha"] >= a["fecha"].max() - pd.Timedelta(days=30)] if len(a) else a
c1, c2, c3, c4 = st.columns(4)
c1.metric("Empresas", f"{len(f):,}".replace(",", "."))
c2.metric("Constituciones (30 días)", int((ult30["tipo"] == "Constitución").sum()))
c3.metric("Extinciones (30 días)", int((ult30["tipo"] == "Extinción").sum()))
c4.metric("Concursos (30 días)", int((ult30["tipo"] == "Situación concursal").sum()))

st.subheader("Altas y bajas por semana")
sem = (a[a["tipo"].isin(["Constitución", "Extinción"])]
       .assign(semana=lambda d: d["fecha"].dt.to_period("W").dt.start_time)
       .pivot_table(index="semana", columns="tipo", values="empresa_id", aggfunc="count", fill_value=0))
st.bar_chart(sem, stack=False)

col1, col2 = st.columns(2)
with col1:
    st.subheader("Municipios con más constituciones")
    nuevas = f[f["fecha_constitucion"].notna()]
    st.bar_chart(nuevas["municipio"].value_counts().head(15), horizontal=True)
with col2:
    st.subheader("Estado")
    st.dataframe(f["estado"].value_counts().rename("empresas"), width="stretch")

st.subheader("Últimas constituciones")
tabla = (f[f["fecha_constitucion"].notna()]
         .sort_values("fecha_constitucion", ascending=False)
         [["fecha_constitucion", "nombre", "municipio", "capital", "objeto_social"]])
st.dataframe(tabla, width="stretch", hide_index=True)
st.download_button("Descargar CSV", tabla.to_csv(index=False).encode("utf-8"), "constituciones.csv")
