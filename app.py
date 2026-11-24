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

    colores = {
        "Río Loa": "#3985D6",
        "Prillex": "#16A34A",
        "Punta Teatinos": "#F59E0B",
        "Todas": "#64748B"
    }

    if (
        key not in st.session_state
        or st.session_state[key] not in opciones
    ):
        st.session_state[key] = opciones[0]

    # Estilos de las cajitas de selección.
    st.markdown(
        f"""
        <style>
        .st-key-{key}_colores div[data-testid="column"]:nth-child(1)
        button {{
            background-color: {colores[opciones[0]]};
            color: white;
            border: 2px solid {colores[opciones[0]]};
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

    # Aplicar el color correspondiente a cada planta.
    with st.container(key=f"{key}_colores"):

        st.markdown(f"**{titulo}**")

        cols = st.columns(len(opciones))

        for i, opcion in enumerate(opciones):

            with cols[i]:

                activo = (
                    st.session_state[key] == opcion
                )

                color = colores[opcion]

                st.markdown(
                    f"""
                    <style>
                    .st-key-{key}_colores
                    div[data-testid="column"]:nth-child({i+1})
                    button {{
                        background-color: {color};
                        color: white;
                        border: 2px solid {color};
                        font-weight: 600;
                    }}
                    .st-key-{key}_colores
                    div[data-testid="column"]:nth-child({i+1})
                    button:hover {{
                        filter: brightness(0.90);
                        color: white;
                        border-color: {color};
                    }}
                    </style>
                    """,
                    unsafe_allow_html=True
                )

                if st.button(
                    ("✓ " if activo else "") + opcion,
                    key=f"{key}_btn_{i}",
                    use_container_width=True
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

# ==========================================================
# 5. PROCESAMIENTO DE PRECIOS SAP
# ==========================================================

def preparar_precios(df, planta):

    if df.empty:
        return pd.DataFrame()

    material = buscar_columna(df, ["Material"])
    descripcion = buscar_columna(
        df, ["Descripción material"]
    )
    precio = buscar_columna(df, ["PRECIO"])
    cantidad = buscar_columna(df, ["CANTIDAD"])
    moneda = buscar_columna(df, ["MONEDA"])

    fecha = buscar_columna(
        df, ["Fecha contabiliz.", "Fecha contabilizacion"]
    )

    fecha_oc = buscar_columna(
        df, ["FECHA OC"]
    )

    oc = buscar_columna(
        df, ["Pedido", "OC"]
    )

    posicion = buscar_columna(
        df, ["POSICIÓN", "POSICION"]
    )

    unidad = buscar_columna(
        df, ["UNIDAD DE MEDIDA", "Un.medida de entrada"]
    )

    if material is None or precio is None:
        st.error(
            f"Faltan columnas necesarias en precios {planta}."
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

    resultado["Precio original"] = (
        pd.to_numeric(df[precio], errors="coerce")
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
        fecha_excel(df[fecha])
        if fecha else pd.NaT
    )

    resultado["Fecha OC"] = (
        fecha_excel(df[fecha_oc])
        if fecha_oc else pd.NaT
    )

    resultado["Orden de compra"] = (
        df[oc].fillna("").astype(str)
        if oc else ""
    )

    resultado["Posición"] = (
        df[posicion].fillna("").astype(str)
        if posicion else ""
    )

    # Si la posición viene vacía, corresponde a la posición 10.
    resultado["Posición"] = (
        resultado["Posición"]
        .str.strip()
        .replace("", "10")
        .replace("nan", "10")
        .str.replace(r"\.0$", "", regex=True)
    )

    resultado["Unidad"] = (
        df[unidad].fillna("").astype(str)
        if unidad else ""
    )

    resultado["Planta"] = planta

    # Precio unitario = PRECIO / CANTIDAD.
    resultado["Precio unitario"] = np.where(
        resultado["Cantidad precio"].notna()
        & (resultado["Cantidad precio"] > 0),
        resultado["Precio original"]
        / resultado["Cantidad precio"],
        resultado["Precio original"]
    )

    resultado = resultado.dropna(
        subset=["Fecha", "Precio original", "Precio unitario"]
    )

    resultado["Año"] = (
        resultado["Fecha"].dt.year
    )

    return resultado


# ==========================================================
# 6. ARCHIVOS BASE Y CARGA DESDE STREAMLIT
# ==========================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

ARCHIVOS_CONSUMO = {
    "Río Loa": [
        "consumo_rio_loa.xlsx",
        "consumo rio loa.xlsx"
    ],
    "Prillex": [
        "consumo_prillex.xlsx",
        "consumo prillex(1).xlsx",
        "consumo prillex.xlsx"
    ],
    "Punta Teatinos": [
        "consumo_punta_teatinos.xlsx",
        "consumo teatitos(1).xlsx",
        "consumo teatitos.xlsx"
    ]
}

ARCHIVOS_PRECIOS = {
    "Río Loa": [
        "precios_rio_loa.xlsx",
        "precios rio loa.xlsx"
    ],
    "Prillex": [
        "precios_prillex.xlsx",
        "PRECIOS PRILLEX.xlsx"
    ],
    "Punta Teatinos": [
        "precios_punta_teatinos.xlsx",
        "PRECIOS TEATINOS.xlsx"
    ]
}


def localizar_archivo(candidatos):

    for carpeta in (DATA_DIR, BASE_DIR):

        for nombre in candidatos:

            ruta = carpeta / nombre

            if ruta.exists():
                return ruta

    return None


def leer_excel_ruta(ruta):

    if ruta is None:
        return pd.DataFrame()

    try:
        return pd.read_excel(
            ruta,
            engine="openpyxl"
        )

    except Exception as e:
        st.error(
            f"No se pudo leer {ruta.name}: {e}"
        )
        return pd.DataFrame()


# ==========================================================
# 7. ENCABEZADO Y BARRA LATERAL
# ==========================================================

st.markdown(
    '<p class="main-title">GESTIÓN DE MATERIAS PRIMAS</p>',
    unsafe_allow_html=True
)

st.markdown(
    '<p class="subtitle">'
    'ENAEX CHILE | Panel de control de abastecimiento'
    '</p>',
    unsafe_allow_html=True
)

with st.sidebar:

    st.markdown("## 📊 ENAEX")
    st.caption("GESTIÓN DE MATERIAS PRIMAS")

    pagina = st.radio(
        "NAVEGACIÓN",
        [
            "Resumen general",
            "Análisis por planta",
            "Consumo mensual",
            "Evolución de precios"
        ]
    )

    st.divider()

    st.markdown("### 📤 ACTUALIZAR INVENTARIO")

    st.caption(
        "Carga aquí el reporte Excel para actualizar "
        "inventario y nivel de servicio."
    )

    archivo_reporte = st.file_uploader(
        "Seleccionar REPORTE TESIS.xlsx",
        type=["xlsx"],
        key="carga_reporte_inventario"
    )

    if archivo_reporte is not None:

        st.success(
            f"Archivo recibido: {archivo_reporte.name}"
        )

        st.caption(
            "El archivo se está utilizando en esta sesión."
        )

    else:

        st.info(
            "Carga el reporte para visualizar "
            "el análisis de inventario."
        )

    st.divider()
    st.caption("Prototipo académico | Enaex Chile")


# Procesar el archivo cargado desde Streamlit.
datos_inventario = preparar_reporte_inventario(
    archivo_reporte
)


# ==========================================================
# 8. CONSOLIDACIÓN AUTOMÁTICA DE CONSUMOS Y PRECIOS
# ==========================================================

lista_consumos = []
lista_precios = []
archivos_faltantes = []

for planta, candidatos in ARCHIVOS_CONSUMO.items():

    ruta = localizar_archivo(candidatos)

    if ruta is None:
        archivos_faltantes.append(candidatos[0])
        continue

    df = leer_excel_ruta(ruta)

    procesado = preparar_consumo(
        df,
        planta
    )

    if not procesado.empty:
        lista_consumos.append(procesado)


for planta, candidatos in ARCHIVOS_PRECIOS.items():

    ruta = localizar_archivo(candidatos)

    if ruta is None:
        archivos_faltantes.append(candidatos[0])
        continue

    df = leer_excel_ruta(ruta)

    procesado = preparar_precios(
        df,
        planta
    )

    if not procesado.empty:
        lista_precios.append(procesado)


consumos = (
    pd.concat(lista_consumos, ignore_index=True)
    if lista_consumos
    else pd.DataFrame()
)

precios = (
    pd.concat(lista_precios, ignore_index=True)
    if lista_precios
    else pd.DataFrame()
)


if archivos_faltantes:

    with st.sidebar:

        with st.expander(
            "Archivos SAP pendientes",
            expanded=False
        ):

            for nombre in archivos_faltantes:
                st.warning(
                    f"Falta en data/: {nombre}"
                )


# ==========================================================
# 9. FILTROS GLOBALES
# ==========================================================

anios = []

if not consumos.empty:
    anios += (
        consumos["Año"]
        .dropna()
        .astype(int)
        .tolist()
    )

if not precios.empty:
    anios += (
        precios["Año"]
        .dropna()
        .astype(int)
        .tolist()
    )

anios = sorted(set(anios))

if not anios:
    anios = [datetime.now().year]


with st.sidebar:

    anio_seleccionado = st.selectbox(
        "AÑO DE ANÁLISIS",
        anios,
        index=len(anios) - 1
    )

    planta_global = st.selectbox(
        "PLANTA",
        ["Todas"] + list(PLANTAS.keys())
    )


consumo_filtrado = consumos.copy()
precio_filtrado = precios.copy()


if not consumo_filtrado.empty:

    consumo_filtrado = consumo_filtrado[
        consumo_filtrado["Año"] == anio_seleccionado
    ]


if not precio_filtrado.empty:

    precio_filtrado = precio_filtrado[
        precio_filtrado["Año"] == anio_seleccionado
    ]


if planta_global != "Todas":

    if not consumo_filtrado.empty:

        consumo_filtrado = consumo_filtrado[
            consumo_filtrado["Planta"] == planta_global
        ]

    if not precio_filtrado.empty:

        precio_filtrado = precio_filtrado[
            precio_filtrado["Planta"] == planta_global
        ]

# ==========================================================
# 10. RESUMEN GENERAL
# ==========================================================

if pagina == "Resumen general":

    st.markdown("## Resumen general")

    materiales = (
        consumo_filtrado["Material"].nunique()
        if not consumo_filtrado.empty
        else 0
    )

    a, b, c, d = st.columns(4)

    a.metric(
        "Materias primas con consumo",
        formato_numero(materiales)
    )

    b.metric(
        "Registros de consumo",
        formato_numero(len(consumo_filtrado))
    )

    c.metric(
        "Registros de precios",
        formato_numero(len(precio_filtrado))
    )

    d.metric(
        "Plantas disponibles",
        str(len(PLANTAS))
    )

    st.markdown("### Consumo mensual por planta")

    if not consumo_filtrado.empty:

        mensual = (
            consumo_filtrado
            .groupby(
                ["Planta", "Año", "Mes", "Unidad"],
                as_index=False
            )["Consumo"]
            .sum()
        )

        mensual["Periodo"] = (
            mensual["Mes"].map(MESES)
            + " "
            + mensual["Año"].astype(str)
        )

        unidades = sorted(
            mensual["Unidad"].dropna().astype(str).unique()
        )

        if unidades:

            unidad = st.selectbox(
                "Unidad de medida",
                unidades,
                key="unidad_resumen"
            )

            graf = mensual[
                mensual["Unidad"].astype(str) == unidad
            ].copy()

            graf["Orden"] = (
                graf["Año"] * 100 + graf["Mes"]
            )

            graf = graf.sort_values("Orden")

            fig = px.line(
                graf,
                x="Periodo",
                y="Consumo",
                color="Planta",
                markers=True,
                color_discrete_map=COLORES
            )

            fig.update_layout(
                template="plotly_white",
                xaxis_title="Mes",
                yaxis_title=f"Consumo ({unidad})"
            )

            st.plotly_chart(
                fig,
                use_container_width=True
            )

        else:
            st.info(
                "Los registros de consumo no tienen unidad de medida."
            )

    else:
        st.info(
            "No hay datos de consumo para los filtros seleccionados."
        )


    st.markdown("### Consumo total por planta")

    if not consumo_filtrado.empty:

        unidades = sorted(
            consumo_filtrado["Unidad"]
            .dropna()
            .astype(str)
            .unique()
        )

        if unidades:

            unidad_comp = st.selectbox(
                "Unidad para comparar plantas",
                unidades,
                key="unidad_comparacion"
            )

            por_planta = (
                consumo_filtrado[
                    consumo_filtrado["Unidad"].astype(str)
                    == unidad_comp
                ]
                .groupby("Planta", as_index=False)["Consumo"]
                .sum()
            )

            fig = px.bar(
                por_planta,
                x="Planta",
                y="Consumo",
                color="Planta",
                color_discrete_map=COLORES
            )

            fig.update_layout(
                template="plotly_white",
                yaxis_title=f"Consumo ({unidad_comp})"
            )

            st.plotly_chart(
                fig,
                use_container_width=True
            )


# ==========================================================
# 11. ANÁLISIS POR PLANTA
# ==========================================================

elif pagina == "Análisis por planta":

    st.markdown("## Análisis individual por planta")

    planta = selector_planta(
        "Seleccionar planta",
        "planta_analisis"
    )

    if datos_inventario.empty:

        st.warning(
            "Para ver inventario, nivel de servicio y alertas, "
            "carga REPORTE TESIS.xlsx desde el menú lateral."
        )

    else:

        datos = datos_inventario[
            datos_inventario["Planta"] == planta
        ].copy()

        if datos.empty:

            st.warning(
                "No hay registros de inventario para esta planta."
            )

        else:

            # ----------------------------------------------
            # NIVEL DE SERVICIO
            # ----------------------------------------------

            ns = (
                datos["NS"]
                .astype(str)
                .str.strip()
                .str.upper()
            )

            eb = int((ns == "EB").sum())
            sb = int((ns == "SB").sum())
            bb = int((ns == "BB").sum())

            total_ns = eb + sb + bb

            pct_eb = (
                eb / total_ns * 100
                if total_ns
                else 0
            )

            a, b, c, d = st.columns(4)

            a.metric(
                "Nivel de servicio EB",
                f"{formato_numero(pct_eb, 1)}%"
            )

            b.metric(
                "Materiales EB",
                formato_numero(eb)
            )

            c.metric(
                "Materiales SB",
                formato_numero(sb)
            )

            d.metric(
                "Materiales BB",
                formato_numero(bb)
            )

            st.caption(
                f"Cálculo: {eb} materiales EB / {total_ns} "
                "materiales clasificados (EB + SB + BB)."
            )


# ==================================================
# ALERTAS DESTACADAS DE COBERTURA
# ==================================================

st.markdown(
    "### Alertas de cobertura inferior a 10 días"
)

if "Cobertura días" in datos.columns:

    alertas = datos[
        datos["Cobertura días"].notna()
        & (datos["Cobertura días"] >= 0)
        & (datos["Cobertura días"] < 10)
    ].sort_values("Cobertura días")

    if not alertas.empty:

        st.markdown(
            f"""
            <div style="
                background-color: #FCE8E8;
                border-left: 6px solid #D97777;
                border-radius: 9px;
                padding: 15px 18px;
                margin: 8px 0 15px 0;
            ">
                <div style="
                    color: #9F3333;
                    font-size: 18px;
                    font-weight: 700;
                ">
                    ⚠️ Atención: {len(alertas)} materias primas
                </div>
                <div style="
                    color: #873B3B;
                    font-size: 14px;
                    margin-top: 5px;
                ">
                    Se identificaron materiales con menos de
                    10 días de cobertura. Se recomienda revisar
                    su planificación y abastecimiento.
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        cols_alerta = [
            "Material",
            "Descripción del material",
            "UM",
            "Stock Actual",
            "Cobertura días",
            "NS",
            "Comentario MMPP"
        ]

        cols_alerta = [
            x for x in cols_alerta
            if x in alertas.columns
        ]

        tabla_alertas = alertas[cols_alerta].rename(
            columns={
                "Material": "Código",
                "Descripción del material": "Descripción",
                "UM": "Unidad",
                "Cobertura días": "Cobertura (días)",
                "NS": "Nivel de servicio",
                "Comentario MMPP": "Comentario"
            }
        )

        st.dataframe(
            tabla_alertas.style.format({
                "Stock Actual": lambda x: formato_numero(x),
                "Cobertura (días)": lambda x: formato_numero(x, 1)
            }),
            use_container_width=True,
            hide_index=True
        )

    else:

        st.success(
            "No hay materias primas con menos de 10 días de cobertura."
        )

else:

    st.info(
        "No se pudo calcular la cobertura en días."
    )

st.divider()

         
# ----------------------------------------------
# DISTRIBUCIÓN Y RESUMEN DE INVENTARIO
# ----------------------------------------------

col1, col2 = st.columns(2)

with col1:

    st.markdown(
       "### Distribución del nivel de servicio"
                )

    if total_ns:

        clasificacion = pd.DataFrame({
         "Clasificación": ["EB", "SB", "BB"],
            "Cantidad": [eb, sb, bb]
                 })

    fig = px.pie(
     clasificacion,
     names="Clasificación",
     values="Cantidad",
     hole=0.58,
     color="Clasificación",
     color_discrete_map={
  "EB": "#16A34A",
  "SB": "#3B82F6",
  "BB": "#DC4545"
 }
 )

 fig.update_layout(
  template="plotly_white"
 )

  st.plotly_chart(
 fig,
  use_container_width=True
  )

else:

 st.info(
 "No hay materiales clasificados EB, SB o BB."
  )

 with col2:

  st.markdown(
  "### Resumen de inventario"
 )

 st.metric(
    "Materias primas",
  formato_numero(len(datos))
)

 st.metric(
 "Stock total registrado",
 formato_numero(
 datos["Stock Actual"].sum()
  )
 if "Stock Actual" in datos.columns
  else "—"
 )

  st.metric(
  "Materiales con cobertura menor a 10 días",
   formato_numero(
 (datos["Cobertura días"] < 10).sum()
   )
 if "Cobertura días" in datos.columns
 else "—"
)
# ----------------------------------------------
# 5 MATERIAS PRIMAS CON MENOR STOCK
# ----------------------------------------------

          st.markdown(
                "### 5 materias primas con menor stock actual"
            )

            if "Stock Actual" in datos.columns:

                menor_stock = (
                    datos.dropna(subset=["Stock Actual"])
                    .nsmallest(5, "Stock Actual")
                )

                columnas = [
                    "Material",
                    "Descripción del material",
                    "UM",
                    "Stock Actual",
                    "Cob. [Meses]"
                ]

                columnas = [
                    x for x in columnas
                    if x in menor_stock.columns
                ]

                if not menor_stock.empty:

                    tabla = menor_stock[columnas].rename(
                        columns={
                            "Material": "Código",
                            "Descripción del material": "Descripción",
                            "UM": "Unidad",
                            "Cob. [Meses]": "Cobertura (meses)"
                        }
                    )

                    st.dataframe(
                        tabla.style.format({
                            "Stock Actual": lambda x: formato_numero(x),
                            "Cobertura (meses)": lambda x: formato_numero(x, 2)
                        }),
                        use_container_width=True,
                        hide_index=True
                    )

                else:

                    st.info(
                        "No hay datos de stock actual."
                    )

            else:

                st.warning(
                    "El reporte no contiene la columna Stock Actual."
                )


            # ----------------------------------------------
            # MENOR CONSUMO PROMEDIO Y MAYOR STOCK
            # ----------------------------------------------

            st.markdown(
                "### 5 materias primas con menor consumo promedio "
                "y mayor stock"
            )

            if {
                "Consumo X̅",
                "Stock Actual"
            }.issubset(datos.columns):

                menor_consumo_mayor_stock = (
                    datos.dropna(
                        subset=["Consumo X̅", "Stock Actual"]
                    )
                    .sort_values(
                        ["Consumo X̅", "Stock Actual"],
                        ascending=[True, False]
                    )
                    .head(5)
                )

                columnas = [
                    "Material",
                    "Descripción del material",
                    "UM",
                    "Consumo X̅",
                    "Stock Actual",
                    "Cob. [Meses]"
                ]

                columnas = [
                    x for x in columnas
                    if x in menor_consumo_mayor_stock.columns
                ]

                tabla = menor_consumo_mayor_stock[columnas].rename(
                    columns={
                        "Material": "Código",
                        "Descripción del material": "Descripción",
                        "UM": "Unidad",
                        "Consumo X̅": "Consumo promedio",
                        "Cob. [Meses]": "Cobertura (meses)"
                    }
                )

                st.dataframe(
                    tabla.style.format({
                        "Consumo promedio": lambda x: formato_numero(x),
                        "Stock Actual": lambda x: formato_numero(x),
                        "Cobertura (meses)": lambda x: formato_numero(x, 2)
                    }),
                    use_container_width=True,
                    hide_index=True
                )

                st.caption(
                    "Criterio de ordenamiento: menor consumo promedio "
                    "primero; si hay empate, mayor stock actual primero."
                )

            else:

                st.warning(
                    "Faltan las columnas Consumo X̅ o Stock Actual."
                )


            # ----------------------------------------------
            # ALERTAS DE COBERTURA INFERIOR A 10 DÍAS
            # ----------------------------------------------

            st.markdown(
                "### Alertas de cobertura inferior a 10 días"
            )

            if "Cobertura días" in datos.columns:

                alertas = datos[
                    datos["Cobertura días"].notna()
                    & (datos["Cobertura días"] >= 0)
                    & (datos["Cobertura días"] < 10)
                ].sort_values("Cobertura días")

                if not alertas.empty:

                    st.warning(
                        f"Se identificaron {len(alertas)} materias primas "
                        "con menos de 10 días de cobertura."
                    )

                    cols = [
                        "Material",
                        "Descripción del material",
                        "UM",
                        "Stock Actual",
                        "Cobertura días",
                        "NS",
                        "Comentario MMPP"
                    ]

                    cols = [
                        x for x in cols
                        if x in alertas.columns
                    ]

                    tabla = alertas[cols].rename(
                        columns={
                            "Material": "Código",
                            "Descripción del material": "Descripción",
                            "UM": "Unidad",
                            "Cobertura días": "Cobertura (días)",
                            "NS": "Nivel de servicio",
                            "Comentario MMPP": "Comentario"
                        }
                    )

                    st.dataframe(
                        tabla.style.format({
                            "Stock Actual": lambda x: formato_numero(x),
                            "Cobertura (días)": lambda x: formato_numero(x, 1)
                        }),
                        use_container_width=True,
                        hide_index=True
                    )

                else:

                    st.success(
                        "No hay materiales con cobertura inferior a 10 días."
                    )

            else:

                st.info(
                    "No se pudo calcular la cobertura en días."
                )


            # ----------------------------------------------
            # INVENTARIO COMPLETO
            # ----------------------------------------------

            with st.expander(
                "Ver inventario completo de la planta"
            ):

                columnas = [
                    "Centro",
                    "Material",
                    "Descripción del material",
                    "UM",
                    "Stock Actual",
                    "Stock Seguridad",
                    "Stock Óptimo",
                    "Stock Máximo",
                    "Cob. [Meses]",
                    "NS",
                    "Comentario MMPP"
                ]

                columnas = [
                    x for x in columnas
                    if x in datos.columns
                ]

                tabla = datos[columnas].rename(
                    columns={
                        "Material": "Código",
                        "Descripción del material": "Descripción",
                        "UM": "Unidad",
                        "Cob. [Meses]": "Cobertura (meses)"
                    }
                )

                st.dataframe(
                    tabla,
                    use_container_width=True,
                    hide_index=True
                )


# ==========================================================
# 12. CONSUMO MENSUAL
# ==========================================================

elif pagina == "Consumo mensual":

    st.markdown(
        "## Consumo histórico de materias primas"
    )

    st.caption(
        "Movimientos reales registrados en SAP"
    )

    if consumos.empty:

        st.warning(
            "No se encontraron archivos de consumo en la carpeta data."
        )

        st.stop()

    planta = selector_planta(
        "Seleccionar planta",
        "planta_consumo_detalle"
    )

    consumo_planta = consumos[
        consumos["Planta"] == planta
    ].copy()

    material = selector_material(
        consumo_planta[["Material", "Descripción"]],
        "Buscar materia prima por código o nombre",
        "material_consumo_detalle"
    )

    if material is None:
        st.stop()

    historial = consumo_planta[
        consumo_planta["Material"] == material
    ].copy().sort_values("Fecha")

    descripcion = (
        historial["Descripción"].dropna().iloc[0]
        if not historial["Descripción"].dropna().empty
        else "Sin descripción"
    )

    st.markdown(
        f"### {material} — {descripcion}"
    )

    unidades = sorted(
        historial["Unidad"]
        .dropna()
        .astype(str)
        .unique()
    )

    if not unidades:

        st.info(
            "El material no tiene unidad de medida informada."
        )

        st.stop()

    unidad = st.selectbox(
        "Unidad de medida",
        unidades,
        key="unidad_consumo_historico"
    )

    historial = historial[
        historial["Unidad"].astype(str) == unidad
    ].copy()

    mensual = (
        historial
        .groupby(
            ["Año", "Mes"],
            as_index=False
        )["Consumo"]
        .sum()
    )

    mensual["Fecha mes"] = pd.to_datetime(
        mensual["Año"].astype(str)
        + "-"
        + mensual["Mes"].astype(str).str.zfill(2)
        + "-01"
    )

    mensual = mensual.sort_values("Fecha mes")

    mensual["Periodo"] = (
        mensual["Mes"].map(MESES)
        + " "
        + mensual["Año"].astype(str)
    )

    total = historial["Consumo"].sum()

    promedio = (
        mensual["Consumo"].mean()
        if not mensual.empty
        else 0
    )

    a, b, c = st.columns(3)

    a.metric(
        "Consumo acumulado",
        f"{formato_numero(total)} {unidad}"
    )

    b.metric(
        "Promedio mensual",
        f"{formato_numero(promedio)} {unidad}"
    )

    c.metric(
        "Meses con registros",
        formato_numero(len(mensual))
    )

    st.markdown(
        "### Evolución mensual del consumo"
    )

    fig = px.bar(
        mensual,
        x="Periodo",
        y="Consumo",
        text="Consumo",
        color_discrete_sequence=[COLORES[planta]]
    )

    fig.update_traces(
        texttemplate="%{y:,.0f}",
        textposition="outside",
        hovertemplate=(
            "%{x}<br>Consumo: %{y:,.0f} "
            + unidad
            + "<extra></extra>"
        )
    )

    fig.update_layout(
        template="plotly_white",
        xaxis_title="Mes",
        yaxis_title=f"Consumo ({unidad})",
        showlegend=False
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

    st.markdown(
        "### Detalle de movimientos SAP"
    )

    detalle = historial[
        [
            "Fecha",
            "Material",
            "Descripción",
            "Movimiento",
            "Cantidad original",
            "Consumo",
            "Unidad"
        ]
    ].sort_values(
        "Fecha",
        ascending=False
    )

    st.dataframe(
        detalle.style.format({
            "Cantidad original": lambda x: formato_numero(x),
            "Consumo": lambda x: formato_numero(x)
        }),
        use_container_width=True,
        hide_index=True
    )


# ==========================================================
# 13. EVOLUCIÓN DE PRECIOS
# ==========================================================

elif pagina == "Evolución de precios":

    st.markdown(
        "## Evolución y análisis de precios"
    )

    if precios.empty:

        st.warning(
            "No se encontraron archivos de precios SAP en data/."
        )

        st.stop()

planta_precio = selector_planta(
    "Seleccionar planta",
    "planta_precios",
    incluir_todas=True
)

    datos = precios.copy()

    if planta_precio != "Todas":

        datos = datos[
            datos["Planta"] == planta_precio
        ].copy()

    datos = datos.dropna(
        subset=["Fecha", "Precio unitario", "Moneda"]
    )

    datos = datos[
        datos["Precio unitario"].notna()
    ].copy()


    # ------------------------------------------------------
    # RANKING DE VARIACIONES
    # ------------------------------------------------------

    st.markdown(
        "### Ranking de variaciones de precios"
    )

    st.caption(
        f"Comparación entre el primer y último precio "
        f"contabilizado durante {anio_seleccionado}, "
        "por material, planta y moneda."
    )

    ranking_datos = datos[
        datos["Año"] == anio_seleccionado
    ].copy()

    resultados = []

    if not ranking_datos.empty:

        for (
            planta_g,
            material_g,
            moneda_g
        ), grupo in ranking_datos.groupby(
            ["Planta", "Material", "Moneda"]
        ):

            grupo = grupo.sort_values("Fecha")

            if len(grupo) < 2:
                continue

            primero = grupo.iloc[0]
            ultimo = grupo.iloc[-1]

            inicial = primero["Precio unitario"]
            final = ultimo["Precio unitario"]

            if (
                pd.isna(inicial)
                or inicial == 0
                or pd.isna(final)
            ):
                continue

            resultados.append({
                "Planta": planta_g,
                "Material": material_g,
                "Descripción": ultimo["Descripción"],
                "Moneda": moneda_g,
                "Precio inicial": inicial,
                "Último precio": final,
                "Variación (%)": (
                    (final - inicial)
                    / abs(inicial)
                    * 100
                ),
                "Fecha inicial": primero["Fecha"],
                "Fecha final": ultimo["Fecha"],
                "Registros": len(grupo)
            })


    ranking = pd.DataFrame(resultados)

    if not ranking.empty:

        aumentos = ranking[
            ranking["Variación (%)"] > 0
        ].nlargest(
            5,
            "Variación (%)"
        )

        disminuciones = ranking[
            ranking["Variación (%)"] < 0
        ].nsmallest(
            5,
            "Variación (%)"
        )

        ca, cb = st.columns(2)

        with ca:

            st.markdown(
                "#### 🔴 Mayores aumentos"
            )

            if not aumentos.empty:

                st.dataframe(
                    aumentos[
                        [
                            "Planta",
                            "Material",
                            "Descripción",
                            "Moneda",
                            "Precio inicial",
                            "Último precio",
                            "Variación (%)"
                        ]
                    ].style.format({
                        "Precio inicial": lambda x: formato_numero(x, 2),
                        "Último precio": lambda x: formato_numero(x, 2),
                        "Variación (%)": "{:+.2f}%"
                    }),
                    use_container_width=True,
                    hide_index=True
                )

            else:

                st.info(
                    "No hay aumentos registrados."
                )


        with cb:

            st.markdown(
                "#### 🟢 Mayores disminuciones"
            )

            if not disminuciones.empty:

                st.dataframe(
                    disminuciones[
                        [
                            "Planta",
                            "Material",
                            "Descripción",
                            "Moneda",
                            "Precio inicial",
                            "Último precio",
                            "Variación (%)"
                        ]
                    ].style.format({
                        "Precio inicial": lambda x: formato_numero(x, 2),
                        "Último precio": lambda x: formato_numero(x, 2),
                        "Variación (%)": "{:+.2f}%"
                    }),
                    use_container_width=True,
                    hide_index=True
                )

            else:

                st.info(
                    "No hay disminuciones registradas."
                )


        with st.expander(
            "Consultar ranking completo"
        ):

            st.dataframe(
                ranking.sort_values(
                    "Variación (%)",
                    ascending=False
                ),
                use_container_width=True,
                hide_index=True
            )

    else:

        st.info(
            "No existen suficientes registros para calcular variaciones."
        )


    # ------------------------------------------------------
    # ANÁLISIS INDIVIDUAL DE PRECIOS
    # ------------------------------------------------------

    st.divider()

    st.markdown(
        "### Análisis individual de precios"
    )

    materiales = sorted(
        datos["Material"]
        .dropna()
        .astype(str)
        .unique()
    )

    if not materiales:

        st.info(
            "No hay materiales con precios disponibles."
        )

        st.stop()

    material = st.selectbox(
        "Seleccionar materia prima",
        materiales,
        key="material_precio_individual"
    )

    df = datos[
        datos["Material"] == material
    ].copy()

    descripcion = (
        df["Descripción"].dropna().iloc[0]
        if not df["Descripción"].dropna().empty
        else ""
    )

    st.markdown(
        f"#### {descripcion}"
    )

    st.caption(
        f"Código de material: {material}"
    )

    monedas = sorted(
        df["Moneda"]
        .dropna()
        .astype(str)
        .unique()
    )

    moneda = st.selectbox(
        "Moneda",
        monedas,
        key="moneda_precio_individual"
    )

    df = df[
        df["Moneda"] == moneda
    ].sort_values("Fecha").copy()

    if df.empty:

        st.warning(
            "No hay registros para esta moneda."
        )

        st.stop()


    inicial = df.iloc[0]["Precio unitario"]
    final = df.iloc[-1]["Precio unitario"]
    promedio = df["Precio unitario"].mean()

    variacion = (
        (final - inicial) / abs(inicial) * 100
        if inicial != 0
        else 0
    )

    a, b, c, d = st.columns(4)

    a.metric(
        "Precio inicial",
        f"{formato_numero(inicial, 2)} {moneda}"
    )

    b.metric(
        "Último precio",
        f"{formato_numero(final, 2)} {moneda}"
    )

    c.metric(
        "Variación",
        f"{variacion:+.2f}%"
    )

    d.metric(
        "Precio promedio",
        f"{formato_numero(promedio, 2)} {moneda}"
    )

    st.caption(
        f"Registros: {len(df)} | Período: "
        f"{df['Fecha'].min():%d-%m-%Y} al "
        f"{df['Fecha'].max():%d-%m-%Y}"
    )


    # ------------------------------------------------------
    # GRÁFICO DE EVOLUCIÓN
    # ------------------------------------------------------

    st.markdown(
        "### Evolución histórica del precio unitario"
    )

    hover = [
        c for c in [
            "Orden de compra",
            "Posición",
            "Fecha OC",
            "Precio original",
            "Cantidad precio",
            "Unidad"
        ]
        if c in df.columns
    ]

    fig = px.line(
        df,
        x="Fecha",
        y="Precio unitario",
        markers=True,
        hover_data=hover,
        color_discrete_sequence=["#2563EB"]
    )

    fig.update_layout(
        template="plotly_white",
        xaxis_title="Fecha de contabilización",
        yaxis_title=f"Precio unitario ({moneda})",
        hovermode="closest"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )


    # ------------------------------------------------------
    # VARIACIÓN ACUMULADA
    # ------------------------------------------------------

    st.markdown(
        "### Variación acumulada del precio"
    )

    k1, k2, k3 = st.columns(3)

    k1.metric(
        "Primer precio registrado",
        f"{formato_numero(inicial, 2)} {moneda}"
    )

    k2.metric(
        "Último precio registrado",
        f"{formato_numero(final, 2)} {moneda}"
    )

    k3.metric(
        "Variación acumulada",
        f"{variacion:+.2f}%"
    )


    # ------------------------------------------------------
    # HISTORIAL DE ÓRDENES DE COMPRA
    # ------------------------------------------------------

    st.markdown(
        "### Historial de órdenes de compra"
    )

    columnas_historial = [
        "Fecha OC",
        "Orden de compra",
        "Posición",
        "Material",
        "Descripción",
        "Cantidad precio",
        "Unidad",
        "Precio original",
        "Precio unitario",
        "Moneda",
        "Fecha"
    ]

    historial = (
        df.sort_values(
            "Fecha",
            ascending=False
        )[columnas_historial]
        .copy()
    )

    historial = historial.rename(
        columns={
            "Fecha OC": "FECHA OC",
            "Orden de compra": "Pedido",
            "Posición": "POSICIÓN",
            "Descripción": "Descripción material",
            "Cantidad precio": "CANTIDAD",
            "Unidad": "UNIDAD",
            "Precio original": "PRECIO SAP",
            "Precio unitario": "PRECIO UNITARIO",
            "Moneda": "MONEDA",
            "Fecha": "FECHA CONTABILIZACIÓN"
        }
    )

    st.dataframe(
        historial.style.format({
            "PRECIO SAP": lambda x: formato_numero(x, 2),
            "PRECIO UNITARIO": lambda x: formato_numero(x, 2),
            "CANTIDAD": lambda x: formato_numero(x, 2)
        }),
        use_container_width=True,
        hide_index=True
    )

    csv = historial.to_csv(
        index=False,
        sep=";",
        decimal=",",
        encoding="utf-8-sig"
    )

    st.download_button(
        "Descargar historial de precios",
        data=csv,
        file_name=f"historial_precios_{material}.csv",
        mime="text/csv"
    )


# ==========================================================
# 14. PIE DE PÁGINA
# ==========================================================

st.divider()

st.caption(
    "ENAEX CHILE | Prototipo académico de gestión de materias primas "
    "| Información sujeta a validación con SAP."
)

