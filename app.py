import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import unicodedata
from datetime import datetime
from pathlib import Path

# ==========================================================
# 1. CONFIGURACION GENERAL
# ==========================================================

st.set_page_config(
    page_title="Gestión de Materias Primas | Enaex",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

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

ARCHIVOS = {
    "consumo": {
        "Río Loa": "consumo rio loa.xlsx",
        "Prillex": "consumo prillex(1).xlsx",
        "Punta Teatinos": "consumo teatitos(1).xlsx"
    },
    "precios": {
        "Río Loa": "precios rio loa.xlsx",
        "Prillex": "PRECIOS PRILLEX.xlsx",
        "Punta Teatinos": "PRECIOS TEATINOS.xlsx"
    },
    "reporte": "REPORTE TESIS.xlsx"
}


# ==========================================================
# 2. ESTILO VISUAL
# ==========================================================

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

.planta-card {
    background: white;
    border-radius: 12px;
    padding: 18px;
    border: 1px solid #E2E8F0;
    min-height: 150px;
}

</style>
""", unsafe_allow_html=True)


# ==========================================================
# 3. FUNCIONES GENERALES
# ==========================================================

def normalizar(texto):
    texto = str(texto).strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(
        c for c in texto
        if not unicodedata.combining(c)
    )
    return texto.replace(" ", "").replace("_", "").replace(".", "")


def buscar_columna(df, alternativas):

    columnas = {
        normalizar(col): col
        for col in df.columns
    }

    for alternativa in alternativas:
        clave = normalizar(alternativa)

        if clave in columnas:
            return columnas[clave]

    for clave, original in columnas.items():
        for alternativa in alternativas:
            if normalizar(alternativa) in clave:
                return original

    return None


def limpiar_codigo(valor):
    if pd.isna(valor):
        return ""
    return str(valor).strip().replace(".0", "")


def numero(valor):
    return pd.to_numeric(
        pd.Series([valor]),
        errors="coerce"
    ).iloc[0]


def fecha_excel(serie):
    return pd.to_datetime(
        serie,
        errors="coerce",
        dayfirst=True
    )


def formato_numero(valor, decimales=0):
    valor = numero(valor)

    if pd.isna(valor):
        return "0"

    return (
        f"{valor:,.{decimales}f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def leer_excel(ruta, hoja=0, encabezado=0):

    if not ruta.exists():
        st.error(f"No se encontró el archivo: {ruta.name}")
        return pd.DataFrame()

    try:
        return pd.read_excel(
            ruta,
            sheet_name=hoja,
            header=encabezado,
            engine="openpyxl"
        )

    except Exception as e:
        st.error(f"Error leyendo {ruta.name}: {e}")
        return pd.DataFrame()


def selector_planta(titulo, key, incluir_todas=False):

    opciones = (
        ["Todas"] if incluir_todas else []
    ) + list(PLANTAS.keys())

    if key not in st.session_state or st.session_state[key] not in opciones:
        st.session_state[key] = opciones[0]

    st.markdown(f"**{titulo}**")

    columnas = st.columns(len(opciones))

    for i, opcion in enumerate(opciones):

        with columnas[i]:

            elegido = st.session_state[key] == opcion

            if st.button(
                ("✓ " if elegido else "") + opcion,
                key=f"{key}_boton_{i}",
                use_container_width=True,
                type="primary" if elegido else "secondary"
            ):
                st.session_state[key] = opcion
                st.rerun()

    return st.session_state[key]


def selector_material(df, texto_busqueda, key):

    if df.empty:
        return None

    catalogo = (
        df[["Material", "Descripción"]]
        .fillna("")
        .drop_duplicates()
        .copy()
    )

    catalogo["Material"] = catalogo["Material"].astype(str)
    catalogo["Descripción"] = catalogo["Descripción"].astype(str)

    catalogo = catalogo[
        catalogo["Material"].str.strip() != ""
    ]

    busqueda = st.text_input(
        texto_busqueda,
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
        st.warning("No se encontraron materias primas con esa búsqueda.")
        return None

    opciones = {
        f"{r['Material']} — {r['Descripción']}".strip(" —"): r["Material"]
        for _, r in catalogo.iterrows()
    }

    etiqueta = st.selectbox(
        "Seleccionar materia prima (código — nombre)",
        list(opciones.keys()),
        key=f"{key}_seleccion"
    )

    return opciones[etiqueta]


# ==========================================================
# 4. PROCESAMIENTO DE CONSUMOS SAP
# ==========================================================

def preparar_consumo(df, planta):

    if df.empty:
        return pd.DataFrame()

    material = buscar_columna(df, ["Material"])
    descripcion = buscar_columna(df, ["Descripción material"])
    cantidad = buscar_columna(df, ["Ctd.en UM entrada", "Cantidad"])
    fecha = buscar_columna(
        df, ["Fecha contabiliz.", "Fecha contabilizacion"]
    )
    movimiento = buscar_columna(df, ["Clase de movimiento"])
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

    resultado["Material"] = df[material].apply(limpiar_codigo)

    resultado["Descripción"] = (
        df[descripcion].fillna("").astype(str)
        if descripcion else ""
    )

    resultado["Cantidad original"] = pd.to_numeric(
        df[cantidad],
        errors="coerce"
    ).fillna(0)

    resultado["Movimiento"] = (
        df[movimiento]
        .astype(str)
        .str.replace(".0", "", regex=False)
        .str.strip()
    )

    resultado["Fecha"] = fecha_excel(df[fecha])

    resultado["Unidad"] = (
        df[unidad].fillna("").astype(str)
        if unidad else ""
    )

    resultado["Planta"] = planta

    resultado = resultado.dropna(subset=["Fecha"])

    resultado = resultado[
        resultado["Movimiento"].isin(["261", "262"])
    ].copy()

    # Consumo neto presentado positivo:
    # movimiento 261 negativo y 262 positivo en SAP.
    resultado["Consumo"] = -resultado["Cantidad original"]

    resultado["Año"] = resultado["Fecha"].dt.year
    resultado["Mes"] = resultado["Fecha"].dt.month

    return resultado


# ==========================================================
# 5. PROCESAMIENTO DE PRECIOS SAP
# ==========================================================

def preparar_precios(df, planta):

    if df.empty:
        return pd.DataFrame()

    material = buscar_columna(df, ["Material"])
    descripcion = buscar_columna(df, ["Descripción material"])
    precio = buscar_columna(df, ["PRECIO"])
    cantidad = buscar_columna(df, ["CANTIDAD"])
    moneda = buscar_columna(df, ["MONEDA"])
    fecha = buscar_columna(df, ["Fecha contabiliz."])
    fecha_oc = buscar_columna(df, ["FECHA OC"])
    oc = buscar_columna(df, ["Pedido", "OC"])
    posicion = buscar_columna(df, ["POSICIÓN", "POSICION"])
    unidad = buscar_columna(
        df, ["UNIDAD DE MEDIDA", "Un.medida de entrada"]
    )

    if material is None or precio is None:
        st.error(
            f"Faltan columnas necesarias en precios {planta}."
        )
        return pd.DataFrame()

    resultado = pd.DataFrame()

    resultado["Material"] = df[material].apply(limpiar_codigo)

    resultado["Descripción"] = (
        df[descripcion].fillna("").astype(str)
        if descripcion else ""
    )

    resultado["Precio original"] = pd.to_numeric(
        df[precio],
        errors="coerce"
    )

    resultado["Cantidad precio"] = (
        pd.to_numeric(df[cantidad], errors="coerce")
        if cantidad else np.nan
    )

    resultado["Moneda"] = (
        df[moneda].fillna("").astype(str).str.upper()
        if moneda else ""
    )

    resultado["Fecha"] = (
        fecha_excel(df[fecha]) if fecha else pd.NaT
    )

    resultado["Fecha OC"] = (
        fecha_excel(df[fecha_oc]) if fecha_oc else pd.NaT
    )

    resultado["Orden de compra"] = (
        df[oc].fillna("").astype(str)
        if oc else ""
    )

    resultado["Posición"] = (
        df[posicion].fillna("").astype(str)
        if posicion else ""
    )

    resultado["Posición"] = (
        resultado["Posición"]
        .str.strip()
        .replace("", "10")
        .replace("nan", "10")
    )

    resultado["Unidad"] = (
        df[unidad].fillna("").astype(str)
        if unidad else ""
    )

    resultado["Planta"] = planta

    resultado["Precio unitario"] = np.where(
        resultado["Cantidad precio"].notna()
        & (resultado["Cantidad precio"] > 0),
        resultado["Precio original"] / resultado["Cantidad precio"],
        resultado["Precio original"]
    )

    resultado = resultado.dropna(
        subset=["Precio original"]
    )

    resultado = resultado[
        resultado["Precio unitario"].notna()
    ]

    resultado["Año"] = resultado["Fecha"].dt.year

    return resultado
