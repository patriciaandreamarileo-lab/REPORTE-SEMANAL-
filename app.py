
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import unicodedata
from datetime import datetime
from pathlib import Path

# ==========================================================
# 1. CONFIGURACIÓN GENERAL
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
    "Prillex": "#F4C542",
    "Punta Teatinos": "#16A34A"
}

MESES = {
    1: "Enero", 2: "Febrero", 3: "Marzo",
    4: "Abril", 5: "Mayo", 6: "Junio",
    7: "Julio", 8: "Agosto", 9: "Septiembre",
    10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}

# ==========================================================
# 2. ESTILOS
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

/* Selector de plantas: Río Loa azul */
div[class*="planta_analisis_boton_0"] button,
div[class*="planta_consumo_detalle_boton_0"] button {
    background-color: #3985D6 !important;
    border-color: #3985D6 !important;
    color: white !important;
}

/* Selector de plantas: Prillex amarillo */
div[class*="planta_analisis_boton_1"] button,
div[class*="planta_consumo_detalle_boton_1"] button {
    background-color: #F4C542 !important;
    border-color: #F4C542 !important;
    color: #263238 !important;
}

/* Selector de plantas: Punta Teatinos verde */
div[class*="planta_analisis_boton_2"] button,
div[class*="planta_consumo_detalle_boton_2"] button {
    background-color: #16A34A !important;
    border-color: #16A34A !important;
    color: white !important;
}

/* Panel diferenciado de consumo histórico */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 12px;
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
    return (
        texto.replace(" ", "")
        .replace("_", "")
        .replace(".", "")
    )


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


# ==========================================================
# 4. SELECTOR DE PLANTAS
# ==========================================================

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

    columnas = st.columns(len(opciones))

    for i, opcion in enumerate(opciones):

        with columnas[i]:

            elegido = (
                st.session_state[key] == opcion
            )

            if st.button(
                ("✓ " if elegido else "") + opcion,
                key=f"{key}_boton_{i}",
                use_container_width=True,
                type="primary" if elegido else "secondary"
            ):
                st.session_state[key] = opcion
                st.rerun()

    return st.session_state[key]


# ==========================================================
# 5. BUSCADOR DE MATERIAS PRIMAS
# ==========================================================

def selector_material(df, texto_busqueda, key):

    if df.empty:
        return None

    catalogo = df[
        ["Material", "Descripción"]
    ].fillna("").drop_duplicates().copy()

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
        st.warning(
            "No se encontraron materias primas con esa búsqueda."
        )
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
# 6. PROCESAMIENTO DE CONSUMOS SAP
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

    # Consumo neto: 261 y 262 conservan su efecto mediante el signo SAP.
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
# 7. PROCESAMIENTO DE PRECIOS SAP
# ==========================================================

def preparar_precios(df, planta):

    if df.empty:
        return pd.DataFrame()

    material = buscar_columna(
        df, ["Material"]
    )

    descripcion = buscar_columna(
        df, ["Descripción material"]
    )

    precio = buscar_columna(
        df, ["PRECIO"]
    )

    cantidad = buscar_columna(
        df, ["CANTIDAD"]
    )

    moneda = buscar_columna(
        df, ["MONEDA"]
    )

    fecha = buscar_columna(
        df, ["Fecha contabiliz."]
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

    resultado["Precio unitario"] = np.where(
        resultado["Cantidad precio"].notna()
        & (resultado["Cantidad precio"] > 0),
        resultado["Precio original"]
        / resultado["Cantidad precio"],
        resultado["Precio original"]
    )

    resultado = resultado.dropna(
        subset=["Fecha", "Precio original"]
    )

    resultado = resultado[
        resultado["Precio unitario"].notna()
    ]

    resultado["Año"] = (
        resultado["Fecha"].dt.year
    )

    return resultado


# ==========================================================
# 8. LECTURA DEL REPORTE DE INVENTARIO
# ==========================================================

def leer_mrp(archivo):

    if archivo is None:
        return pd.DataFrame(), pd.DataFrame()

    nombres_hojas = {
        "Prillex": "Prillex",
        "Río Loa": "Rio Loa",
        "Punta Teatinos": "Pta. Teatinos"
    }

    lista = []

    try:

        for planta, hoja in nombres_hojas.items():

            df = pd.read_excel(
                archivo,
                sheet_name=hoja,
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
                continue

            df["Material"] = (
                df["Material"].apply(limpiar_codigo)
            )

            lista.append(df)

        if not lista:
            return pd.DataFrame(), pd.DataFrame()

        ns = pd.concat(
            lista,
            ignore_index=True
        )

        ns = ns.dropna(
            subset=["Centro", "Material"]
        )

        ns = ns[
            ns["Material"].str.fullmatch(
                r"\d+", na=False
            )
        ].copy()

        ns = ns.drop_duplicates(
            subset=["Centro", "Material"],
            keep="first"
        )

        if (
            "NS Corregido" not in ns.columns
            and "NS" in ns.columns
        ):
            ns["NS Corregido"] = (
                ns["NS"].astype(str).str.strip().str.upper()
            )

        if (
            "Cob. [Meses]" not in ns.columns
            and "Cobertura [Meses]" in ns.columns
        ):
            ns["Cob. [Meses]"] = (
                ns["Cobertura [Meses]"]
            )

        return ns, pd.DataFrame()

    except Exception as e:

        st.error(
            f"Error procesando el reporte de inventario: {e}"
        )

        return pd.DataFrame(), pd.DataFrame()


# ==========================================================
# 9. ENCABEZADO Y NAVEGACIÓN
# ==========================================================

st.markdown(
    '<p class="main-title">GESTIÓN DE MATERIAS PRIMAS</p>',
    unsafe_allow_html=True
)

st.markdown(
    '<p class="subtitle">ENAEX CHILE | Panel de control de abastecimiento</p>',
    unsafe_allow_html=True
)

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

ARCHIVO_REPORTE = [
    "REPORTE TESIS.xlsx",
    "reporte_tesis.xlsx"
]


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
# 10. BARRA LATERAL
# ==========================================================

with st.sidebar:

    st.markdown("## 📊 ENAEX")
    st.caption("GESTIÓN DE MATERIAS PRIMAS")

    pagina = st.radio(
        "NAVEGACIÓN",
        [
            "Inventario y cobertura",
            "Resumen general",
            "Análisis por planta",
            "Consumo mensual",
            "Evolución de precios"
        ]
    )

    st.divider()

    st.markdown("### 📁 INFORMACIÓN DEL DASHBOARD")

    st.caption(
        "Los Excel se leen automáticamente desde la carpeta data del repositorio."
    )

    st.caption(
        "Para actualizar la información, reemplaza los archivos en GitHub."
    )

    st.divider()

    st.caption(
        "Prototipo académico | Enaex Chile"
    )


# ==========================================================
# 11. CONSOLIDACIÓN DE ARCHIVOS
# ==========================================================

lista_consumos = []
lista_precios = []
archivos_faltantes = []

for planta, candidatos in ARCHIVOS_CONSUMO.items():

    ruta = localizar_archivo(candidatos)

    if ruta is None:

        archivos_faltantes.append(
            candidatos[0]
        )

        continue

    procesado = preparar_consumo(
        leer_excel_ruta(ruta),
        planta
    )

    if not procesado.empty:
        lista_consumos.append(procesado)


for planta, candidatos in ARCHIVOS_PRECIOS.items():

    ruta = localizar_archivo(candidatos)

    if ruta is None:

        archivos_faltantes.append(
            candidatos[0]
        )

        continue

    procesado = preparar_precios(
        leer_excel_ruta(ruta),
        planta
    )

    if not procesado.empty:
        lista_precios.append(procesado)


consumos = (
    pd.concat(
        lista_consumos,
        ignore_index=True
    )
    if lista_consumos
    else pd.DataFrame()
)

precios = (
    pd.concat(
        lista_precios,
        ignore_index=True
    )
    if lista_precios
    else pd.DataFrame()
)

ruta_reporte = localizar_archivo(
    ARCHIVO_REPORTE
)

datos_ns, datos_mrp = leer_mrp(
    ruta_reporte
)

if archivos_faltantes:

    with st.sidebar:

        with st.expander(
            "Archivos pendientes",
            expanded=True
        ):

            for nombre in archivos_faltantes:
                st.warning(f"Falta: {nombre}")


# ==========================================================
# 12. FILTROS GLOBALES
# ==========================================================

años_disponibles = []

if not consumos.empty:

    años_disponibles += (
        consumos["Año"].dropna().tolist()
    )

if not precios.empty:

    años_disponibles += (
        precios["Año"].dropna().tolist()
    )

años_disponibles = sorted(
    set(años_disponibles)
)

if not años_disponibles:
    años_disponibles = [datetime.now().year]

plantas_disponibles = list(
    PLANTAS.keys()
)

with st.sidebar:

    año_seleccionado = st.selectbox(
        "AÑO DE ANÁLISIS",
        años_disponibles,
        index=len(años_disponibles) - 1
    )

    planta_global = st.selectbox(
        "PLANTA",
        ["Todas"] + plantas_disponibles
    )


consumo_filtrado = consumos.copy()
precio_filtrado = precios.copy()

if not consumo_filtrado.empty:

    consumo_filtrado = consumo_filtrado[
        consumo_filtrado["Año"] == año_seleccionado
    ]

if not precio_filtrado.empty:

    precio_filtrado = precio_filtrado[
        precio_filtrado["Año"] == año_seleccionado
    ]

if planta_global != "Todas":

    consumo_filtrado = consumo_filtrado[
        consumo_filtrado["Planta"] == planta_global
    ]

    precio_filtrado = precio_filtrado[
        precio_filtrado["Planta"] == planta_global
    ]


# ==========================================================
# 13. RESUMEN GENERAL
# ==========================================================

if pagina == "Resumen general":

    st.markdown("## Resumen general")

    a, b, c, d = st.columns(4)

    materiales = (
        consumo_filtrado["Material"].nunique()
        if not consumo_filtrado.empty
        else 0
    )

    registros_consumo = (
        len(consumo_filtrado)
        if not consumo_filtrado.empty
        else 0
    )

    registros_precios = (
        len(precio_filtrado)
        if not precio_filtrado.empty
        else 0
    )

    a.metric(
        "Materias primas",
        formato_numero(materiales)
    )

    b.metric(
        "Registros de consumo",
        formato_numero(registros_consumo)
    )

    c.metric(
        "Registros de precios",
        formato_numero(registros_precios)
    )

    d.metric(
        "Plantas disponibles",
        str(len(plantas_disponibles))
    )

    # No se muestran gráficos en el resumen general.


# ==========================================================
# 14. ANÁLISIS INDIVIDUAL POR PLANTA
# ==========================================================

elif pagina == "Análisis por planta":

    st.markdown(
        "## Análisis individual por planta"
    )

    planta = selector_planta(
        "Seleccionar planta",
        "planta_analisis"
    )

    df_c = (
        consumos[
            (consumos["Planta"] == planta)
            & (consumos["Año"] == año_seleccionado)
        ].copy()
        if not consumos.empty
        else pd.DataFrame()
    )

    df_p = (
        precios[
            (precios["Planta"] == planta)
            & (precios["Año"] == año_seleccionado)
        ].copy()
        if not precios.empty
        else pd.DataFrame()
    )

    cantidad_materiales = (
        df_c["Material"].nunique()
        if not df_c.empty
        else 0
    )

    st.metric(
        "Materias primas",
        formato_numero(cantidad_materiales)
    )

    st.markdown(
        "### Consumo mensual por materia prima"
    )

    if not df_c.empty:

        material = selector_material(
            df_c[["Material", "Descripción"]],
            "Buscar por código o nombre de materia prima",
            "material_consumo_planta"
        )

        if material is not None:

            detalle = df_c[
                df_c["Material"] == material
            ].copy()

            descripcion = (
                detalle["Descripción"].iloc[0]
                if not detalle.empty
                else ""
            )

            st.markdown(
                f"**{material} — {descripcion}**"
            )

            unidades = sorted(
                detalle["Unidad"].dropna().astype(str).unique()
            )

            if unidades:

                unidad = st.selectbox(
                    "Unidad de medida",
                    unidades,
                    key="unidad_planta_detalle"
                )

                grafico = (
                    detalle[
                        detalle["Unidad"] == unidad
                    ]
                    .groupby(
                        ["Año", "Mes"],
                        as_index=False
                    )["Consumo"].sum()
                )

                grafico["Fecha"] = pd.to_datetime(
                    grafico["Año"].astype(str)
                    + "-"
                    + grafico["Mes"].astype(str).str.zfill(2)
                    + "-01"
                )

                grafico = grafico.sort_values(
                    "Fecha"
                )

                grafico["Periodo"] = (
                    grafico["Mes"].map(MESES)
                    + " "
                    + grafico["Año"].astype(str)
                )

                fig = px.bar(
                    grafico,
                    x="Periodo",
                    y="Consumo",
                    color_discrete_sequence=[
                        COLORES[planta]
                    ]
                )

                fig.update_traces(
                    texttemplate="%{y:,.0f}",
                    textposition="outside"
                )

                fig.update_layout(
                    template="plotly_white",
                    yaxis_title=f"Consumo ({unidad})",
                    xaxis_title="Mes"
                )

                st.plotly_chart(
                    fig,
                    use_container_width=True
                )

    else:

        st.info(
            "No hay información de consumo para esta planta y año."
        )

    # ------------------------------------------------------
    # EVOLUCIÓN DE PRECIOS POR PLANTA
    # ------------------------------------------------------

    st.markdown("### Evolución de precios")

    if not df_p.empty:

        material_precio = selector_material(
            df_p[["Material", "Descripción"]],
            "Buscar materia prima para revisar sus precios",
            "material_planta_precio"
        )

        if material_precio is not None:

            seleccionado = df_p[
                df_p["Material"] == material_precio
            ].copy()

            monedas = sorted(
                seleccionado["Moneda"].dropna().unique()
            )

            if monedas:

                moneda = st.selectbox(
                    "Moneda",
                    monedas,
                    key="moneda_planta"
                )

                seleccionado = seleccionado[
                    seleccionado["Moneda"] == moneda
                ].sort_values("Fecha")

                fig = px.line(
                    seleccionado,
                    x="Fecha",
                    y="Precio unitario",
                    markers=True,
                    hover_data=[
                        "Orden de compra",
                        "Posición"
                    ],
                    color_discrete_sequence=[
                        COLORES[planta]
                    ]
                )

                fig.update_layout(
                    template="plotly_white",
                    yaxis_title=f"Precio unitario ({moneda})"
                )

                st.plotly_chart(
                    fig,
                    use_container_width=True
                )

    else:

        st.info(
            "No hay información de precios disponible."
        )


# ==========================================================
# 15. CONSUMO HISTÓRICO DE MATERIAS PRIMAS
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

    with st.container(border=True):

        planta = selector_planta(
            "Seleccionar planta",
            "planta_consumo_detalle"
        )

        consumo_planta = consumos[
            consumos["Planta"] == planta
        ].copy()

        catalogo = consumo_planta[
            ["Material", "Descripción"]
        ].drop_duplicates()

        material = selector_material(
            catalogo,
            "Buscar por código o nombre de materia prima",
            "material_consumo_detalle"
        )

        if material is None:
            st.stop()

        historial = consumo_planta[
            consumo_planta["Material"] == material
        ].copy()

        historial = historial.sort_values(
            "Fecha"
        )

        descripcion = (
            historial["Descripción"].dropna()
        )

        descripcion = (
            descripcion.iloc[0]
            if not descripcion.empty
            else "Sin descripción"
        )

        st.markdown(
            f"### {material} — {descripcion}"
        )

        unidades = sorted(
            historial["Unidad"].dropna().astype(str).unique()
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

        # CONSUMO HISTÓRICO MENSUAL

        mensual = (
            historial.groupby(
                ["Año", "Mes"],
                as_index=False
            )["Consumo"].sum()
        )

        mensual["Fecha"] = pd.to_datetime(
            mensual["Año"].astype(str)
            + "-"
            + mensual["Mes"].astype(str).str.zfill(2)
            + "-01"
        )

        mensual = mensual.sort_values(
            "Fecha"
        )

        mensual["Periodo"] = (
            mensual["Mes"].map(MESES)
            + " "
            + mensual["Año"].astype(str)
        )

        total_consumido = historial["Consumo"].sum()

        meses_con_movimiento = mensual["Consumo"].count()

        promedio_mensual = (
            mensual["Consumo"].mean()
            if not mensual.empty
            else 0
        )

        # INDICADORES

        a, b, c = st.columns(3)

        a.metric(
            "Consumo acumulado",
            f"{formato_numero(total_consumido)} {unidad}"
        )

        b.metric(
            "Promedio mensual",
            f"{formato_numero(promedio_mensual)} {unidad}"
        )

        c.metric(
            "Meses con registros",
            formato_numero(meses_con_movimiento)
        )

        # GRÁFICO HISTÓRICO

        st.markdown(
            "### Evolución mensual del consumo"
        )

        fig = px.bar(
            mensual,
            x="Periodo",
            y="Consumo",
            text="Consumo",
            color_discrete_sequence=[
                COLORES[planta]
            ]
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

        # DETALLE SAP

        st.markdown(
            "### Detalle de movimientos SAP"
        )

        detalle = historial[[
            "Fecha",
            "Material",
            "Descripción",
            "Movimiento",
            "Cantidad original",
            "Consumo",
            "Unidad"
        ]].sort_values(
            "Fecha",
            ascending=False
        ).copy()

        st.dataframe(
            detalle.style.format({
                "Cantidad original": lambda x: formato_numero(x),
                "Consumo": lambda x: formato_numero(x)
            }),
            use_container_width=True,
            hide_index=True
        )


# ==========================================================
# 16. EVOLUCIÓN Y ANÁLISIS DE PRECIOS
# ==========================================================

elif pagina == "Evolución de precios":

    st.markdown(
        "## Evolución y análisis de precios"
    )

    if precios.empty:

        st.warning(
            "No se encontraron archivos de precios SAP."
        )

        st.stop()

    planta_precio = st.selectbox(
        "Seleccionar planta",
        ["Todas"] + list(PLANTAS.keys()),
        key="planta_precios"
    )

    datos = precios.copy()

    if planta_precio != "Todas":

        datos = datos[
            datos["Planta"] == planta_precio
        ]

    datos = datos.dropna(
        subset=[
            "Fecha",
            "Precio unitario",
            "Moneda"
        ]
    )

    # ------------------------------------------------------
    # RANKING DE VARIACIONES
    # ------------------------------------------------------

    st.markdown(
        "### Ranking de variaciones de precios"
    )

    st.caption(
        f"Comparación entre el primer y último precio "
        f"registrado durante {año_seleccionado}."
    )

    ranking_datos = datos[
        datos["Año"] == año_seleccionado
    ].copy()

    resultados = []

    if not ranking_datos.empty:

        grupos = ranking_datos.groupby(
            ["Planta", "Material", "Moneda"]
        )

        for (
            planta_grupo,
            material_grupo,
            moneda_grupo
        ), grupo in grupos:

            grupo = grupo.sort_values(
                "Fecha"
            )

            if len(grupo) < 2:
                continue

            primero = grupo.iloc[0]
            ultimo = grupo.iloc[-1]

            inicial = primero["Precio unitario"]
            final = ultimo["Precio unitario"]

            if pd.isna(inicial) or inicial == 0:
                continue

            variacion = (
                (final - inicial) / abs(inicial)
            ) * 100

            resultados.append({

                "Planta": planta_grupo,
                "Material": material_grupo,
                "Descripción": ultimo["Descripción"],
                "Moneda": moneda_grupo,
                "Precio inicial": inicial,
                "Último precio": final,
                "Variación (%)": variacion,
                "Fecha inicial": primero["Fecha"],
                "Fecha final": ultimo["Fecha"],
                "Registros": len(grupo)

            })

    ranking = pd.DataFrame(
        resultados
    )

    if not ranking.empty:

        aumentos = ranking[
            ranking["Variación (%)"] > 0
        ].sort_values(
            "Variación (%)",
            ascending=False
        ).head(5)

        disminuciones = ranking[
            ranking["Variación (%)"] < 0
        ].sort_values(
            "Variación (%)",
            ascending=True
        ).head(5)

        ca, cb = st.columns(2)

        with ca:

            st.markdown(
                "#### Mayores aumentos"
            )

            if not aumentos.empty:

                st.dataframe(
                    aumentos[[
                        "Planta",
                        "Material",
                        "Descripción",
                        "Moneda",
                        "Precio inicial",
                        "Último precio",
                        "Variación (%)"
                    ]].style.format({

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
                "#### Mayores disminuciones"
            )

            if not disminuciones.empty:

                st.dataframe(
                    disminuciones[[
                        "Planta",
                        "Material",
                        "Descripción",
                        "Moneda",
                        "Precio inicial",
                        "Último precio",
                        "Variación (%)"
                    ]].style.format({

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

        st.markdown(
            "### Comparación de variaciones"
        )

        grafico_ranking = pd.concat(
            [aumentos, disminuciones],
            ignore_index=True
        )

        if not grafico_ranking.empty:

            fig = px.bar(
                grafico_ranking,
                x="Variación (%)",
                y="Material",
                color="Variación (%)",
                orientation="h",
                hover_data=[
                    "Planta",
                    "Descripción",
                    "Moneda",
                    "Precio inicial",
                    "Último precio"
                ],
                color_continuous_scale="RdYlGn_r"
            )

            fig.update_layout(
                template="plotly_white",
                yaxis_title="Material",
                xaxis_title="Variación porcentual"
            )

            st.plotly_chart(
                fig,
                use_container_width=True
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

    st.divider()

    # ------------------------------------------------------
    # ANÁLISIS INDIVIDUAL DE PRECIOS
    # ------------------------------------------------------

    st.markdown(
        "### Análisis individual de precios"
    )

    materiales_precio = sorted(
        datos["Material"].dropna().unique()
    )

    if not materiales_precio:

        st.warning(
            "No hay materiales con precios disponibles."
        )

        st.stop()

    material = st.selectbox(
        "Seleccionar materia prima",
        materiales_precio,
        key="material_precio_individual"
    )

    df = datos[
        datos["Material"] == material
    ].copy()

    descripcion = (
        df["Descripción"].iloc[0]
        if not df.empty
        else ""
    )

    st.markdown(
        f"#### {descripcion}"
    )

    st.caption(
        f"Código de material: {material}"
    )

    monedas = sorted(
        df["Moneda"].dropna().unique()
    )

    moneda = st.selectbox(
        "Moneda",
        monedas,
        key="moneda_precio_individual"
    )

    df = df[
        df["Moneda"] == moneda
    ].sort_values(
        "Fecha"
    )

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
        f"Registros: {len(df)} | "
        f"Período: {df['Fecha'].min():%d-%m-%Y} "
        f"al {df['Fecha'].max():%d-%m-%Y}"
    )

    # ------------------------------------------------------
    # GRÁFICO DE EVOLUCIÓN
    # ------------------------------------------------------

    st.markdown(
        "### Evolución histórica del precio unitario"
    )

    fig = px.line(
        df.sort_values("Fecha"),
        x="Fecha",
        y="Precio unitario",
        markers=True,
        hover_data=[
            "Orden de compra",
            "Posición",
            "Fecha OC",
            "Precio original",
            "Cantidad precio",
            "Unidad"
        ],
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
    # VARIACIÓN ACUMULADA DEBAJO DEL GRÁFICO
    # ------------------------------------------------------

    primer_precio = df.iloc[0]["Precio unitario"]
    ultimo_precio = df.iloc[-1]["Precio unitario"]

    variacion_acumulada = (
        (ultimo_precio - primer_precio)
        / abs(primer_precio) * 100
        if primer_precio != 0
        else 0
    )

    st.markdown(
        "### Variación acumulada del precio"
    )

    k1, k2, k3 = st.columns(3)

    k1.metric(
        "Primer precio registrado",
        f"{formato_numero(primer_precio, 2)} {moneda}"
    )

    k2.metric(
        "Último precio registrado",
        f"{formato_numero(ultimo_precio, 2)} {moneda}"
    )

    k3.metric(
        "Variación acumulada",
        f"{variacion_acumulada:+.2f}%"
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

    historial = df.sort_values(
        "Fecha",
        ascending=False
    ).copy()

    historial = historial[
        columnas_historial
    ].rename(columns={

        "Fecha OC": "FECHA OC",
        "Orden de compra": "Pedido",
        "Posición": "POSICIÓN",
        "Descripción": "Descripción material",
        "Cantidad precio": "CANTIDAD",
        "Unidad": "UNIDAD",
        "Precio original": "PRECIO",
        "Precio unitario": "PRECIO UNITARIO",
        "Moneda": "MONEDA",
        "Fecha": "FECHA CONTABILIZACIÓN"

    })

    st.dataframe(
        historial.style.format({

            "PRECIO": lambda x: formato_numero(x, 2),
            "PRECIO UNITARIO": lambda x: formato_numero(x, 2),
            "CANTIDAD": lambda x: formato_numero(x, 2)

        }),
        use_container_width=True,
        hide_index=True
    )

    # ------------------------------------------------------
    # FECHA OC VERSUS CONTABILIZACIÓN
    # ------------------------------------------------------

    st.markdown(
        "### Fecha de OC versus contabilización"
    )

    fechas = df.dropna(
        subset=["Fecha OC", "Fecha"]
    ).copy()

    if not fechas.empty:

        fechas["Días transcurridos"] = (
            fechas["Fecha"] - fechas["Fecha OC"]
        ).dt.days

        fig = px.scatter(
            fechas,
            x="Fecha OC",
            y="Fecha",
            color="Precio unitario",
            hover_data=[
                "Orden de compra",
                "Posición",
                "Días transcurridos"
            ],
            color_continuous_scale="Blues"
        )

        fig.update_layout(
            template="plotly_white",
            xaxis_title="Fecha de OC",
            yaxis_title="Fecha de contabilización"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

        st.metric(
            "Promedio de días transcurridos",
            f"{fechas['Días transcurridos'].mean():.1f} días"
        )

    else:

        st.info(
            "No existen fechas suficientes para comparar."
        )

    # ------------------------------------------------------
    # DESCARGA DEL HISTORIAL
    # ------------------------------------------------------

    columnas_descarga = [
        "Fecha OC",
        "Fecha",
        "Orden de compra",
        "Posición",
        "Precio original",
        "Cantidad precio",
        "Precio unitario",
        "Moneda",
        "Unidad"
    ]

    historial_descarga = df.sort_values(
        "Fecha",
        ascending=False
    )

    st.markdown(
        "### Historial detallado de órdenes de compra"
    )

    st.dataframe(
        historial_descarga[columnas_descarga].rename(columns={

            "Fecha OC": "Fecha de OC",
            "Fecha": "Fecha contabilización",
            "Precio original": "Precio SAP",
            "Cantidad precio": "Cantidad divisor",
            "Precio unitario": "Precio unitario calculado",
            "Unidad": "Unidad de medida"

        }),
        use_container_width=True,
        hide_index=True
    )

    csv = historial_descarga[
        columnas_descarga
    ].to_csv(
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
# 17. INVENTARIO Y COBERTURA
# ==========================================================

elif pagina == "Inventario y cobertura":

    st.markdown(
        "## Inventario y cobertura"
    )

    if datos_ns.empty:

        st.error(
            "No fue posible procesar las hojas del reporte de inventario."
        )

        st.stop()

    planta = selector_planta(
        "Seleccionar planta",
        "planta_inventario",
        incluir_todas=True
    )

    datos = datos_ns.copy()

    if planta != "Todas":

        datos = datos[
            datos["Centro"] == PLANTAS[planta]
        ]

    datos["Material"] = (
        datos["Material"].apply(limpiar_codigo)
    )

    datos = datos[
        datos["Material"].str.fullmatch(
            r"\d+", na=False
        )
    ].copy()

    datos = datos.drop_duplicates(
        subset=["Centro", "Material"],
        keep="first"
    )

    columnas_necesarias = [
        "Cob. [Meses]",
        "Consumo X̅",
        "NS Corregido",
        "Descripción del material",
        "UM",
        "Stock Actual",
        "Stock Seguridad",
        "Stock Máximo",
        "Comentario MMPP"
    ]

    for columna in columnas_necesarias:

        if columna not in datos.columns:
            datos[columna] = np.nan

    datos["Cob. [Meses]"] = pd.to_numeric(
        datos["Cob. [Meses]"],
        errors="coerce"
    )

    datos["Consumo X̅"] = pd.to_numeric(
        datos["Consumo X̅"],
        errors="coerce"
    )

    datos["NS Corregido"] = (
        datos["NS Corregido"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    # ------------------------------------------------------
    # INDICADORES DE INVENTARIO Y NIVEL DE SERVICIO
    # ------------------------------------------------------

    total = len(datos)

    baja = len(
        datos[
            (datos["Cob. [Meses]"] >= 0)
            & (datos["Cob. [Meses]"] < 1)
        ]
    )

    sin_consumo = len(
        datos[
            datos["Consumo X̅"] == 0
        ]
    )

    eb = (
        datos["NS Corregido"] == "EB"
    ).sum()

    sb = (
        datos["NS Corregido"] == "SB"
    ).sum()

    bb = (
        datos["NS Corregido"] == "BB"
    ).sum()

    total_clasificadas = eb + sb + bb

    pct_eb = (
        eb / total_clasificadas * 100
        if total_clasificadas
        else 0
    )

    pct_sb = (
        sb / total_clasificadas * 100
        if total_clasificadas
        else 0
    )

    pct_bb = (
        bb / total_clasificadas * 100
        if total_clasificadas
        else 0
    )

    a, b, c, d = st.columns(4)

    a.metric(
        "Materias primas",
        formato_numero(total)
    )

    b.metric(
        "Baja cobertura",
        formato_numero(baja)
    )

    c.metric(
        "Sin consumo",
        formato_numero(sin_consumo)
    )

    d.metric(
        "Nivel de servicio EB",
        f"{formato_numero(pct_eb, 1)}%"
    )

    st.caption(
        f"Distribución: EB {formato_numero(pct_eb, 1)}% · "
        f"SB {formato_numero(pct_sb, 1)}% · "
        f"BB {formato_numero(pct_bb, 1)}% "
        f"(base: {total_clasificadas} materiales clasificados)."
    )

    # ------------------------------------------------------
    # CLASIFICACIÓN DEL NIVEL DE SERVICIO
    # ------------------------------------------------------

    st.markdown(
        "### Clasificación del nivel de servicio"
    )

    col1, col2 = st.columns(2)

    with col1:

        clasificacion = pd.DataFrame({

            "Clasificación": ["EB", "SB", "BB"],
            "Cantidad": [eb, sb, bb]

        })

        fig = px.pie(
            clasificacion,
            names="Clasificación",
            values="Cantidad",
            hole=0.60,
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

    with col2:

        distribucion = (
            datos.groupby(
                ["Centro", "NS Corregido"]
            )
            .size()
            .reset_index(name="Cantidad")
        )

        distribucion["Planta"] = (
            distribucion["Centro"].map({
                v: k for k, v in PLANTAS.items()
            })
        )

        if planta != "Todas":

            distribucion = distribucion[
                distribucion["Planta"] == planta
            ]

        fig = px.bar(
            distribucion,
            x="Planta",
            y="Cantidad",
            color="NS Corregido",
            barmode="group",
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

    # ------------------------------------------------------
    # MATERIAS PRIMAS CON BAJA COBERTURA
    # ------------------------------------------------------

    st.markdown(
        "### Top 5 materias primas con baja cobertura"
    )

    baja_df = datos[
        (datos["Cob. [Meses]"] >= 0)
        & (datos["Cob. [Meses]"] < 1)
    ].nsmallest(
        5,
        "Cob. [Meses]"
    )

    columnas_ns = [
        "Centro",
        "Material",
        "Descripción del material",
        "UM",
        "Cob. [Meses]",
        "Consumo X̅",
        "Stock Actual",
        "Comentario MMPP"
    ]

    st.dataframe(
        baja_df[columnas_ns],
        use_container_width=True,
        hide_index=True
    )

    # ------------------------------------------------------
    # MATERIAS PRIMAS SIN CONSUMO
    # ------------------------------------------------------

    st.markdown(
        "### Top 5 materias primas sin consumo"
    )

    sin = datos[
        datos["Consumo X̅"] == 0
    ]

    st.dataframe(
        sin[columnas_ns].head(5),
        use_container_width=True,
        hide_index=True
    )

    # ------------------------------------------------------
    # TABLA GENERAL DE INVENTARIO
    # ------------------------------------------------------

    st.markdown(
        "### Inventario por materia prima"
    )

    columnas_inventario = [
        "Centro",
        "Material",
        "Descripción del material",
        "UM",
        "Stock Actual",
        "Stock Seguridad",
        "Stock Máximo",
        "Cob. [Meses]",
        "NS Corregido"
    ]

    st.dataframe(
        datos[columnas_inventario],
        use_container_width=True,
        hide_index=True
    )


# ==========================================================
# 18. PIE DE PÁGINA
# ==========================================================

st.divider()

st.caption(
    "ENAEX CHILE | Prototipo académico de gestión de materias primas "
    "| Información sujeta a validación con SAP."
)
