import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import unicodedata
from datetime import datetime
from io import BytesIO
from pathlib import Path

# ==========================================================
# 1. CONFIGURACION
# ==========================================================

st.set_page_config(
    page_title="Gestión de Materias Primas | Enaex",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

PLANTAS = {
    "Río Loa": "E024",
    "Prillex": "E002",
    "Punta Teatinos": "E026"
}

COLORES = {
    "Río Loa": "#3985D6",
    "Prillex": "#16A34A",
    "Punta Teatinos": "#F59E0B"
}

MESES = {
    1: "Enero", 2: "Febrero", 3: "Marzo",
    4: "Abril", 5: "Mayo", 6: "Junio",
    7: "Julio", 8: "Agosto", 9: "Septiembre",
    10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}

st.markdown("""
<style>
.stApp {
    background-color: #F5F7FA;
}
[data-testid="stSidebar"] {
    background-color: #10234D;
}
[data-testid="stSidebar"] * {
    color: white !important;
}
.main-title {
    font-size: 30px;
    font-weight: 750;
    color: #14264E;
    margin-bottom: 0;
}
.subtitle {
    color: #64748B;
    font-size: 14px;
    margin-bottom: 25px;
}
div[data-testid="stMetric"] {
    background: white;
    padding: 15px;
    border-radius: 10px;
    border: 1px solid #E2E8F0;
}
</style>
""", unsafe_allow_html=True)


# ==========================================================
# 2. FUNCIONES GENERALES
# ==========================================================

def normalizar(texto):
    texto = str(texto).strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(
        c for c in texto
        if not unicodedata.combining(c)
    )
    return (
        texto.replace(" ", "")
        .replace("_", "")
        .replace(".", "")
        .replace("\n", "")
    )


def buscar_columna(df, alternativas):
    mapa = {
        normalizar(c): c
        for c in df.columns
    }

    for alt in alternativas:
        clave = normalizar(alt)
        if clave in mapa:
            return mapa[clave]

    for clave, original in mapa.items():
        for alt in alternativas:
            if normalizar(alt) in clave:
                return original

    return None


def limpiar_codigo(valor):
    if pd.isna(valor):
        return ""

    texto = str(valor).strip()

    if texto.endswith(".0"):
        texto = texto[:-2]

    return texto


def numero(valor):
    return pd.to_numeric(
        pd.Series([valor]),
        errors="coerce"
    ).iloc[0]


def formato_numero(valor, decimales=0):
    valor = numero(valor)

    if pd.isna(valor):
        return "—"

    return (
        f"{valor:,.{decimales}f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def fecha_excel(serie):
    return pd.to_datetime(
        serie,
        errors="coerce",
        dayfirst=True
    )


def selector_planta(titulo, key, incluir_todas=False):
    opciones = (
        ["Todas"] if incluir_todas else []
    ) + list(PLANTAS.keys())

    if (
        key not in st.session_state
        or st.session_state[key] not in opciones
    ):
        st.session_state[key] = opciones[0]

    st.markdown(f"**{titulo}**")

    cols = st.columns(len(opciones))

    for i, opcion in enumerate(opciones):
        with cols[i]:
            activo = st.session_state[key] == opcion

            if st.button(
                ("✓ " if activo else "") + opcion,
                key=f"{key}_btn_{i}",
                use_container_width=True,
                type="primary" if activo else "secondary"
            ):
                st.session_state[key] = opcion
                st.rerun()

    return st.session_state[key]


def selector_material(df, texto, key):
    if df.empty:
        return None

    catalogo = (
        df[["Material", "Descripción"]]
        .fillna("")
        .drop_duplicates()
        .copy()
    )

    catalogo["Material"] = (
        catalogo["Material"].astype(str)
    )

    catalogo["Descripción"] = (
        catalogo["Descripción"].astype(str)
    )

    catalogo = catalogo[
        catalogo["Material"].str.strip() != ""
    ]

    busqueda = st.text_input(
        texto,
        placeholder="Escribe el código o nombre de la materia prima...",
        key=f"{key}_busqueda"
    ).strip().lower()

    if busqueda:
        catalogo = catalogo[
            catalogo["Material"].str.lower().str.contains(
                busqueda, na=False
            )
            |
            catalogo["Descripción"].str.lower().str.contains(
                busqueda, na=False
            )
        ]

    if catalogo.empty:
        st.warning(
            "No se encontraron materias primas con esa búsqueda."
        )
        return None

    opciones = {
        f"{r['Material']} — {r['Descripción']}".strip(" —"):
        r["Material"]
        for _, r in catalogo.iterrows()
    }

    etiqueta = st.selectbox(
        "Seleccionar materia prima (código — nombre)",
        list(opciones.keys()),
        key=f"{key}_seleccion"
    )

    return opciones[etiqueta]


def leer_excel_bytes(archivo, sheet_name=0, header=0):
    if archivo is None:
        return pd.DataFrame()

    try:
        archivo.seek(0)

        return pd.read_excel(
            BytesIO(archivo.getvalue()),
            sheet_name=sheet_name,
            header=header,
            engine="openpyxl"
        )

    except Exception as e:
        st.error(
            f"No se pudo leer {archivo.name}: {e}"
        )
        return pd.DataFrame()


# ==========================================================
# 3. PROCESAMIENTO DEL REPORTE DE INVENTARIO Y NS
# ==========================================================

def preparar_reporte_inventario(archivo):

    if archivo is None:
        return pd.DataFrame()

    hojas = {
        "Prillex": "Prillex",
        "Rio Loa": "Río Loa",
        "Pta. Teatinos": "Punta Teatinos"
    }

    lista = []

    try:
        excel = pd.ExcelFile(
            BytesIO(archivo.getvalue()),
            engine="openpyxl"
        )

        for hoja, planta in hojas.items():

            if hoja not in excel.sheet_names:
                st.warning(
                    f"No se encontró la hoja '{hoja}' en el reporte."
                )
                continue

            df = pd.read_excel(
                BytesIO(archivo.getvalue()),
                sheet_name=hoja,
                header=0,
                engine="openpyxl"
            )

            if df.empty:
                continue

            df.columns = [
                str(c).replace("\n", " ").strip()
                for c in df.columns
            ]

            df["Planta"] = planta

            if "Centro" not in df.columns:
                df["Centro"] = PLANTAS[planta]

            df["Centro"] = (
                df["Centro"].astype(str).str.strip()
            )

            if "Material" not in df.columns:
                st.error(
                    f"La hoja {hoja} no contiene la columna Material."
                )
                continue

            df["Material"] = (
                df["Material"].apply(limpiar_codigo)
            )

            df = df[
                df["Material"].str.fullmatch(
                    r"\d+", na=False
                )
            ].copy()

            lista.append(df)

        if not lista:
            return pd.DataFrame()

        datos = pd.concat(
            lista,
            ignore_index=True
        )

        datos = datos.drop_duplicates(
            subset=["Centro", "Material"],
            keep="first"
        )

        columnas_numericas = [
            "Consumo X̅",
            "Stock Actual",
            "Stock Óptimo",
            "Stock Seguridad",
            "Stock Máximo",
            "Cob. [Meses]"
        ]

        for col in columnas_numericas:
            if col in datos.columns:
                datos[col] = pd.to_numeric(
                    datos[col],
                    errors="coerce"
                )

        if "NS" in datos.columns:
            datos["NS"] = (
                datos["NS"]
                .astype(str)
                .str.strip()
                .str.upper()
            )
        else:
            datos["NS"] = ""

        if "Cob. [Meses]" in datos.columns:
            datos["Cobertura días"] = (
                datos["Cob. [Meses]"] * 30
            )
        else:
            datos["Cobertura días"] = np.nan

        return datos

    except Exception as e:
        st.error(
            f"Error procesando el reporte de inventario: {e}"
        )
        return pd.DataFrame()


# ==========================================================
# 4. PROCESAMIENTO DE CONSUMOS SAP
# ==========================================================

def preparar_consumo(df, planta):

    if df.empty:
        return pd.DataFrame()

    material = buscar_columna(
        df, ["Material"]
    )

    descripcion = buscar_columna(
        df, ["Descripción material"]
    )

    cantidad = buscar_columna(
        df, ["Ctd.en UM entrada", "Cantidad"]
    )

    fecha = buscar_columna(
        df, ["Fecha contabiliz.", "Fecha contabilizacion"]
    )

    movimiento = buscar_columna(
        df, ["Clase de movimiento"]
    )

    unidad = buscar_columna(
        df, ["Un.medida de entrada", "Unidad de medida"]
    )

    if any(
        c is None
        for c in [material, cantidad, fecha, movimiento]
    ):
        st.error(
            f"Faltan columnas necesarias en consumo {planta}."
        )
        return pd.DataFrame()

    resultado = pd.DataFrame()

    resultado["Material"] = (
        df[material].apply(limpiar_codigo)
    )

    resultado["Descripción"] = (
        df[descripcion].fillna("").astype(str)
        if descripcion else ""
    )

    resultado["Cantidad original"] = (
        pd.to_numeric(
            df[cantidad],
            errors="coerce"
        ).fillna(0)
    )

    resultado["Movimiento"] = (
        df[movimiento]
        .astype(str)
        .str.replace(".0", "", regex=False)
        .str.strip()
    )

    resultado["Fecha"] = fecha_excel(
        df[fecha]
    )

    resultado["Unidad"] = (
        df[unidad].fillna("").astype(str)
        if unidad else ""
    )

    resultado["Planta"] = planta

    resultado = resultado.dropna(
        subset=["Fecha"]
    )

    resultado = resultado[
        resultado["Movimiento"].isin(["261", "262"])
    ].copy()

    # 261 corresponde al consumo y 262 a su reversa.
    # Se invierte el signo para presentar el consumo neto positivo.
    resultado["Consumo"] = (
        -resultado["Cantidad original"]
    )

    resultado["Año"] = (
        resultado["Fecha"].dt.year
    )

    resultado["Mes"] = (
        resultado["Fecha"].dt.month
    )

    return resultado
