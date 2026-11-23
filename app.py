import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import unicodedata
from datetime import datetime

# ==========================================================
# CONFIGURACION GENERAL
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
    "Río Loa": "#3B82F6",
    "Prillex": "#16A34A",
    "Punta Teatinos": "#F59E0B"
}

# ==========================================================
# ESTILO VISUAL
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

    .kpi-card {
        background-color: white;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #E2E8F0;
        min-height: 112px;
    }

    .kpi-label {
        color: #64748B;
        font-size: 13px;
    }

    .kpi-value {
        color: #14264E;
        font-size: 28px;
        font-weight: 750;
    }

    .section-title {
        color: #14264E;
        font-size: 20px;
        font-weight: 700;
        margin-top: 20px;
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
# FUNCIONES DE LIMPIEZA
# ==========================================================

def normalizar(texto):
    texto = str(texto).strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(
        c for c in texto if not unicodedata.combining(c)
    )
    return texto.replace(" ", "").replace("_", "").replace(".", "")


def buscar_columna(df, alternativas):
    columnas = {
        normalizar(col): col for col in df.columns
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


def leer_excel(archivo):
    if archivo is None:
        return pd.DataFrame()

    try:
        return pd.read_excel(archivo, engine="openpyxl")
    except Exception as e:
        st.error(f"No se pudo leer {archivo.name}: {e}")
        return pd.DataFrame()


def preparar_consumo(df, planta):
    if df.empty:
        return pd.DataFrame()

    material = buscar_columna(df, ["Material"])
    descripcion = buscar_columna(
        df, ["Descripción material", "Descripcion material"]
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
    centro = buscar_columna(df, ["Centro"])
    unidad = buscar_columna(
        df, ["Un.medida de entrada", "Unidad de medida"]
    )

    requeridas = [material, cantidad, fecha, movimiento]

    if any(c is None for c in requeridas):
        return pd.DataFrame()

    resultado = pd.DataFrame()

    resultado["Material"] = df[material].astype(str).str.strip()
    resultado["Descripción"] = (
        df[descripcion].fillna("").astype(str)
        if descripcion else ""
    )
    resultado["Cantidad original"] = pd.to_numeric(
        df[cantidad], errors="coerce"
    ).fillna(0)

    resultado["Movimiento"] = (
        df[movimiento].astype(str).str.replace(".0", "", regex=False)
    )

    resultado["Fecha"] = pd.to_datetime(
        df[fecha], errors="coerce", dayfirst=True
    )

    resultado["Unidad"] = (
        df[unidad].fillna("").astype(str)
        if unidad else ""
    )

    resultado["Planta"] = planta

    if centro:
        resultado["Centro"] = df[centro].astype(str)

    resultado = resultado.dropna(subset=["Fecha"])

    # 261: consumo; 262: reversa del consumo.
    # Se conservan los signos originales de SAP.
    resultado = resultado[
        resultado["Movimiento"].isin(["261", "262"])
    ].copy()

    # Las salidas 261 vienen negativas y las anulaciones 262 positivas.
    resultado["Consumo"] = -resultado["Cantidad original"]

    resultado["Año"] = resultado["Fecha"].dt.year
    resultado["Mes"] = resultado["Fecha"].dt.month
    resultado["Mes nombre"] = resultado["Fecha"].dt.strftime("%b")

    return resultado


def preparar_precios(df, planta):
    if df.empty:
        return pd.DataFrame()

    material = buscar_columna(df, ["Material"])
    descripcion = buscar_columna(
        df, ["Descripción material", "Descripcion material"]
    )
    precio = buscar_columna(df, ["PRECIO", "Precio"])
    cantidad = buscar_columna(df, ["CANTIDAD", "Cantidad"])
    moneda = buscar_columna(df, ["MONEDA", "Moneda"])
    fecha = buscar_columna(
        df, ["Fecha contabiliz.", "Fecha contabilizacion"]
    )
    fecha_oc = buscar_columna(df, ["FECHA OC", "Fecha OC"])
    oc = buscar_columna(df, ["Pedido", "OC"])
    posicion = buscar_columna(df, ["POSICIÓN", "POSICION"])
    unidad = buscar_columna(
        df, ["UNIDAD DE MEDIDA", "Un.medida de entrada"]
    )

    if material is None or precio is None:
        return pd.DataFrame()

    resultado = pd.DataFrame()

    resultado["Material"] = df[material].astype(str).str.strip()
    resultado["Descripción"] = (
        df[descripcion].fillna("").astype(str)
        if descripcion else ""
    )

    resultado["Precio original"] = pd.to_numeric(
        df[precio], errors="coerce"
    )

    resultado["Cantidad precio"] = (
        pd.to_numeric(df[cantidad], errors="coerce")
        if cantidad else np.nan
    )

    resultado["Moneda"] = (
        df[moneda].fillna("").astype(str).str.upper()
        if moneda else ""
    )

    resultado["Fecha"] = pd.to_datetime(
        df[fecha], errors="coerce", dayfirst=True
    ) if fecha else pd.NaT

    if fecha_oc:
        fecha_compra = pd.to_datetime(
            df[fecha_oc], errors="coerce", dayfirst=True
        )
        resultado["Fecha OC"] = fecha_compra
    else:
        resultado["Fecha OC"] = pd.NaT

    resultado["Orden de compra"] = (
        df[oc].astype(str) if oc else ""
    )

    resultado["Posición"] = (
        df[posicion].fillna("").astype(str)
        if posicion else ""
    )

    resultado["Unidad"] = (
        df[unidad].fillna("").astype(str)
        if unidad else ""
    )

    resultado["Planta"] = planta

    # Precio unitario según precio / cantidad.
    resultado["Precio unitario"] = np.where(
        resultado["Cantidad precio"] > 0,
        resultado["Precio original"] /
        resultado["Cantidad precio"],
        resultado["Precio original"]
    )

    resultado = resultado.dropna(subset=["Fecha", "Precio original"])
    resultado["Año"] = resultado["Fecha"].dt.year

    return resultado


# ==========================================================
# ENCABEZADO
# ==========================================================

st.markdown(
    '<p class="main-title">GESTIÓN DE MATERIAS PRIMAS</p>',
    unsafe_allow_html=True
)

st.markdown(
    '<p class="subtitle">ENAEX CHILE | Panel de control de abastecimiento</p>',
    unsafe_allow_html=True
)


# ==========================================================
# CARGA DE ARCHIVOS
# ==========================================================

with st.sidebar:

    st.markdown("## 📊 ENAEX")
    st.caption("GESTIÓN DE MATERIAS PRIMAS")

    pagina = st.radio(
        "NAVEGACIÓN",
        [
            "Resumen general",
            "Análisis por planta",
            "Consumo mensual",
            "Evolución de precios",
            "Inventario y cobertura"
        ]
    )

    st.divider()

    st.markdown("### 📁 Carga de información")

    with st.expander("Consumos SAP", expanded=True):

        consumo_rl = st.file_uploader(
            "Consumo Río Loa",
            type=["xlsx", "xlsm"],
            key="consumo_rl"
        )

        consumo_pr = st.file_uploader(
            "Consumo Prillex",
            type=["xlsx", "xlsm"],
            key="consumo_pr"
        )

        consumo_pt = st.file_uploader(
            "Consumo Punta Teatinos",
            type=["xlsx", "xlsm"],
            key="consumo_pt"
        )

    with st.expander("Precios SAP"):

        precios_rl = st.file_uploader(
            "Precios Río Loa",
            type=["xlsx", "xlsm"],
            key="precios_rl"
        )

        precios_pr = st.file_uploader(
            "Precios Prillex",
            type=["xlsx", "xlsm"],
            key="precios_pr"
        )

        precios_pt = st.file_uploader(
            "Precios Punta Teatinos",
            type=["xlsx", "xlsm"],
            key="precios_pt"
        )

    with st.expander("Planificación MRP"):

        archivo_mrp = st.file_uploader(
            "Excel de planificación MRP",
            type=["xlsx", "xlsm"],
            key="mrp"
        )

    st.divider()

    st.caption("Prototipo académico | Enaex Chile")


# ==========================================================
# PROCESAMIENTO DE ARCHIVOS
# ==========================================================

archivos_consumo = {
    "Río Loa": consumo_rl,
    "Prillex": consumo_pr,
    "Punta Teatinos": consumo_pt
}

archivos_precios = {
    "Río Loa": precios_rl,
    "Prillex": precios_pr,
    "Punta Teatinos": precios_pt
}

lista_consumos = []
lista_precios = []

for planta, archivo in archivos_consumo.items():
    if archivo is not None:
        df = leer_excel(archivo)
        procesado = preparar_consumo(df, planta)

        if not procesado.empty:
            lista_consumos.append(procesado)

for planta, archivo in archivos_precios.items():
    if archivo is not None:
        df = leer_excel(archivo)
        procesado = preparar_precios(df, planta)

        if not procesado.empty:
            lista_precios.append(procesado)

consumos = (
    pd.concat(lista_consumos, ignore_index=True)
    if lista_consumos else pd.DataFrame()
)

precios = (
    pd.concat(lista_precios, ignore_index=True)
    if lista_precios else pd.DataFrame()
)


# ==========================================================
# FUNCIONES DE VISUALIZACIÓN
# ==========================================================

def mostrar_kpi(titulo, valor, ayuda=None):
    st.metric(titulo, valor, help=ayuda)


def grafico_consumo(df, titulo="Consumo mensual"):
    if df.empty:
        st.info("No hay datos de consumo disponibles.")
        return

    mensual = (
        df.groupby(["Año", "Mes"], as_index=False)["Consumo"]
        .sum()
    )

    mensual["Periodo"] = (
        mensual["Año"].astype(str) + "-" +
        mensual["Mes"].astype(str).str.zfill(2)
    )

    fig = px.bar(
        mensual,
        x="Periodo",
        y="Consumo",
        title=titulo,
        text_auto=".3s",
        color_discrete_sequence=["#3985D6"]
    )

    fig.update_layout(
        template="plotly_white",
        xaxis_title="Mes",
        yaxis_title="Consumo neto",
        hovermode="x unified"
    )

    st.plotly_chart(fig, use_container_width=True)


def grafico_precios(df):
    if df.empty:
        st.info("No hay datos de precios disponibles.")
        return

    df = df.copy()
    df["Periodo"] = df["Fecha"].dt.strftime("%Y-%m")

    for moneda in sorted(df["Moneda"].dropna().unique()):
        if not moneda:
            continue

        datos = df[df["Moneda"] == moneda]

        mensual = (
            datos.groupby("Periodo", as_index=False)
            ["Precio unitario"].mean()
        )

        fig = px.line(
            mensual,
            x="Periodo",
            y="Precio unitario",
            markers=True,
            title=f"Evolución del precio unitario ({moneda})",
            color_discrete_sequence=["#16A34A"]
        )

        fig.update_layout(
            template="plotly_white",
            xaxis_title="Período",
            yaxis_title=f"Precio unitario ({moneda})"
        )

        st.plotly_chart(fig, use_container_width=True)


# ==========================================================
# FILTROS GENERALES
# ==========================================================

if consumos.empty and precios.empty and archivo_mrp is None:

    st.info(
        "👈 Para comenzar, carga los archivos Excel desde el menú lateral."
    )

    st.markdown("### Información que podrás visualizar")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("#### 🏭 Plantas")
        st.write("Río Loa, Prillex y Punta Teatinos.")

    with c2:
        st.markdown("#### 📈 Consumo")
        st.write("Evolución mensual e histórica por materia prima.")

    with c3:
        st.markdown("#### 💰 Precios")
        st.write("Evolución de precios por material y moneda.")

    st.stop()


if not consumos.empty:
    años = sorted(consumos["Año"].dropna().unique().tolist())
elif not precios.empty:
    años = sorted(precios["Año"].dropna().unique().tolist())
else:
    años = [datetime.now().year]

with st.sidebar:
    año_seleccionado = st.selectbox(
        "AÑO DE ANÁLISIS",
        años,
        index=len(años) - 1
    )

    plantas_disponibles = [
        p for p in PLANTAS
        if (
            not consumos.empty and p in consumos["Planta"].unique()
        ) or (
            not precios.empty and p in precios["Planta"].unique()
        )
    ]

    planta_seleccionada = st.selectbox(
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

if planta_seleccionada != "Todas":
    consumo_filtrado = consumo_filtrado[
        consumo_filtrado["Planta"] == planta_seleccionada
    ]

    precio_filtrado = precio_filtrado[
        precio_filtrado["Planta"] == planta_seleccionada
    ]


# ==========================================================
# 1. RESUMEN GENERAL
# ==========================================================

if pagina == "Resumen general":

    st.markdown("## Resumen general")

    a, b, c, d = st.columns(4)

    consumo_total = (
        consumo_filtrado["Consumo"].sum()
        if not consumo_filtrado.empty else 0
    )

    materiales = (
        consumo_filtrado["Material"].nunique()
        if not consumo_filtrado.empty else 0
    )

    registros_precios = (
        len(precio_filtrado)
        if not precio_filtrado.empty else 0
    )

    with a:
        mostrar_kpi("Consumo neto", f"{consumo_total:,.2f}")

    with b:
        mostrar_kpi("Materias primas", f"{materiales:,}")

    with c:
        mostrar_kpi("Registros de precios", f"{registros_precios:,}")

    with d:
        mostrar_kpi(
            "Plantas con información",
            str(len(plantas_disponibles))
        )

    st.markdown("### Consumo mensual")

    if not consumo_filtrado.empty:
        mensual = (
            consumo_filtrado.groupby(
                ["Planta", "Año", "Mes"], as_index=False
            )["Consumo"].sum()
        )

        mensual["Periodo"] = (
            mensual["Año"].astype(str) + "-" +
            mensual["Mes"].astype(str).str.zfill(2)
        )

        fig = px.line(
            mensual,
            x="Periodo",
            y="Consumo",
            color="Planta",
            markers=True,
            color_discrete_map=COLORES
        )

        fig.update_layout(
            template="plotly_white",
            xaxis_title="Período",
            yaxis_title="Consumo neto"
        )

        st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("Carga archivos de consumo para visualizar el gráfico.")

    st.markdown("### Consumo por planta")

    if not consumo_filtrado.empty:
        por_planta = (
            consumo_filtrado.groupby("Planta", as_index=False)
            ["Consumo"].sum()
        )

        fig = px.bar(
            por_planta,
            x="Planta",
            y="Consumo",
            color="Planta",
            color_discrete_map=COLORES
        )

        fig.update_layout(template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)


# ==========================================================
# 2. ANALISIS POR PLANTA
# ==========================================================

elif pagina == "Análisis por planta":

    st.markdown("## Análisis individual por planta")

    planta = st.selectbox(
        "Seleccionar planta",
        list(PLANTAS.keys())
    )

    df_c = consumos[
        (consumos["Planta"] == planta) &
        (consumos["Año"] == año_seleccionado)
    ] if not consumos.empty else pd.DataFrame()

    df_p = precios[
        (precios["Planta"] == planta) &
        (precios["Año"] == año_seleccionado)
    ] if not precios.empty else pd.DataFrame()

    st.markdown(f"### {planta}")

    x, y, z = st.columns(3)

    with x:
        mostrar_kpi(
            "Consumo neto",
            f"{df_c['Consumo'].sum():,.2f}" if not df_c.empty else "—"
        )

    with y:
        mostrar_kpi(
            "Materias primas",
            str(df_c["Material"].nunique()) if not df_c.empty else "—"
        )

    with z:
        mostrar_kpi(
            "Órdenes con precio",
            str(df_p["Orden de compra"].nunique())
            if not df_p.empty else "—"
        )

    st.markdown("### Consumo mensual")
    grafico_consumo(df_c)

    st.markdown("### Evolución de precios")
    grafico_precios(df_p)


# ==========================================================
# 3. CONSUMO MENSUAL
# ==========================================================

elif pagina == "Consumo mensual":

    st.markdown("## Análisis de consumo mensual")

    if consumo_filtrado.empty:
        st.warning("No hay información de consumo para los filtros elegidos.")
        st.stop()

    materiales_lista = sorted(
        consumo_filtrado["Material"].dropna().unique()
    )

    material = st.selectbox(
        "Seleccionar materia prima",
        materiales_lista
    )

    df_material = consumo_filtrado[
        consumo_filtrado["Material"] == material
    ]

    descripcion = df_material["Descripción"].iloc[0]

    st.markdown(f"### {descripcion}")

    mostrar_kpi(
        "Consumo neto del año",
        f"{df_material['Consumo'].sum():,.2f}"
    )

    grafico_consumo(df_material)

    st.markdown("### Detalle mensual")

    detalle = (
        df_material.groupby(
            ["Año", "Mes", "Unidad"], as_index=False
        )["Consumo"].sum()
    )

    detalle["Mes"] = detalle["Mes"].map({
        1: "Enero", 2: "Febrero", 3: "Marzo",
        4: "Abril", 5: "Mayo", 6: "Junio",
        7: "Julio", 8: "Agosto", 9: "Septiembre",
        10: "Octubre", 11: "Noviembre", 12: "Diciembre"
    })

    st.dataframe(detalle, use_container_width=True, hide_index=True)


# ==========================================================
# 4. EVOLUCION DE PRECIOS
# ==========================================================

elif pagina == "Evolución de precios":

    st.markdown("## Evolución de precios")

    if precio_filtrado.empty:
        st.warning("No hay información de precios para los filtros elegidos.")
        st.stop()

    materiales_lista = sorted(
        precio_filtrado["Material"].dropna().unique()
    )

    material = st.selectbox(
        "Seleccionar materia prima",
        materiales_lista
    )

    df_material = precio_filtrado[
        precio_filtrado["Material"] == material
    ].copy()

    st.markdown(
        f"### {df_material['Descripción'].iloc[0]}"
    )

    monedas = sorted(
        df_material["Moneda"].dropna().unique()
    )

    moneda = st.selectbox("Moneda", monedas)

    df_material = df_material[
        df_material["Moneda"] == moneda
    ]

    fig = px.line(
        df_material.sort_values("Fecha"),
        x="Fecha",
        y="Precio unitario",
        markers=True,
        hover_data=[
            "Orden de compra",
            "Posición",
            "Precio original",
            "Cantidad precio"
        ],
        title=f"Historial de precios - {moneda}",
        color_discrete_sequence=["#2563EB"]
    )

    fig.update_layout(
        template="plotly_white",
        xaxis_title="Fecha de contabilización",
        yaxis_title=f"Precio unitario ({moneda})"
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Historial de órdenes de compra")

    columnas = [
        "Fecha", "Orden de compra", "Posición",
        "Precio original", "Cantidad precio",
        "Precio unitario", "Moneda", "Unidad"
    ]

    st.dataframe(
        df_material[columnas].sort_values("Fecha", ascending=False),
        use_container_width=True,
        hide_index=True
    )



# ==========================================================
# 5. INVENTARIO, NIVEL DE SERVICIO Y COBERTURA
# ==========================================================

elif pagina == "Inventario y cobertura":

    st.markdown("## Inventario y cobertura")
    st.caption("Indicadores de planificación y disponibilidad de materias primas")

    if archivo_mrp is None:
        st.warning("Carga el archivo Planificación MRP desde el menú lateral.")
        st.stop()

    try:
        archivo_mrp.seek(0)
        ns = pd.read_excel(
            archivo_mrp,
            sheet_name="NS",
            header=9,
            engine="openpyxl"
        )

        archivo_mrp.seek(0)
        mrp = pd.read_excel(
            archivo_mrp,
            sheet_name="MRP",
            header=7,
            engine="openpyxl"
        )

        ns = ns.dropna(subset=["Centro", "Material"])
        mrp = mrp.dropna(subset=["Centro", "Material"])

        equivalencias = {
            "E024": "Río Loa",
            "E002": "Prillex",
            "E026": "Punta Teatinos"
        }

        ns["Centro"] = ns["Centro"].astype(str).str.strip()
        mrp["Centro"] = mrp["Centro"].astype(str).str.strip()

        ns["Planta"] = ns["Centro"].map(equivalencias)
        mrp["Planta"] = mrp["Centro"].map(equivalencias)

        ns["Material"] = ns["Material"].astype(str).str.replace(r"\.0$", "", regex=True)

        # Filtros
        plantas_mrp = ["Todas"] + [
            p for p in equivalencias.values()
            if p in ns["Planta"].dropna().unique()
        ]

        planta_mrp = st.selectbox(
            "Seleccionar planta",
            plantas_mrp,
            key="planta_inventario"
        )

        datos = ns.copy()

        if planta_mrp != "Todas":
            datos = datos[datos["Planta"] == planta_mrp]

        # Indicadores
        total_materiales = len(datos)

        baja_cobertura = len(
            datos[pd.to_numeric(datos["Cob. [Meses]"], errors="coerce") < 1]
        )

        sin_consumo = len(
            datos[pd.to_numeric(datos["Consumo X̅"], errors="coerce") == 0]
        )

        eb = (datos["NS Corregido"] == "EB").sum()
        sb = (datos["NS Corregido"] == "SB").sum()
        bb = (datos["NS Corregido"] == "BB").sum()

        st.markdown("### Indicadores principales")

        a, b, c, d = st.columns(4)

        a.metric("Materias primas", f"{total_materiales:,}")
        b.metric("Baja cobertura", f"{baja_cobertura:,}")
        c.metric("Sin consumo", f"{sin_consumo:,}")
        d.metric("Clasificadas EB", f"{eb:,}")

        st.markdown("### Clasificación del nivel de servicio")

        col1, col2 = st.columns([1, 1])

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
                template="plotly_white",
                title="Materias primas por clasificación"
            )

            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.markdown("#### Distribución por planta")

            distribucion = (
                ns.groupby(["Planta", "NS Corregido"])
                .size()
                .reset_index(name="Cantidad")
            )

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

            fig.update_layout(template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("### Top 5 MMPP con baja cobertura")

        baja = datos.copy()
        baja["Cob. [Meses]"] = pd.to_numeric(
            baja["Cob. [Meses]"], errors="coerce"
        )

        baja = baja[
            (baja["Cob. [Meses]"] >= 0) &
            (baja["Cob. [Meses]"] < 1)
        ].nsmallest(5, "Cob. [Meses]")

        columnas = [
            "Centro",
            "Material",
            "Descripción del material",
            "Cob. [Meses]",
            "Consumo X̅",
            "Stock Actual",
            "Comentario MMPP"
        ]

        st.dataframe(
            baja[columnas],
            use_container_width=True,
            hide_index=True
        )

        st.markdown("### Top 5 MMPP sin consumo")

        sin = datos[
            pd.to_numeric(datos["Consumo X̅"], errors="coerce") == 0
        ].copy()

        st.dataframe(
            sin[columnas].head(5),
            use_container_width=True,
            hide_index=True
        )

        st.markdown("### Inventario por materia prima")

        materiales = datos[
            [
                "Material",
                "Descripción del material",
                "UM",
                "Stock Actual",
                "Stock Seguridad",
                "Stock Máximo",
                "Cob. [Meses]",
                "NS Corregido"
            ]
        ].copy()

        st.dataframe(
            materiales,
            use_container_width=True,
            hide_index=True
        )

        st.markdown("### Planificación MRP")

        columnas_mrp = [
            "Centro",
            "Material",
            "Descripción del material",
            "UM",
            "Stock Seguridad",
            "Stock Máximo",
            "Stock Actual",
            "Consumo Proyectado",
            "Stock Óptimo",
            "Cobertura\n[Meses]"
        ]

        columnas_disponibles = [
            c for c in columnas_mrp if c in mrp.columns
        ]

        mrp_filtrado = mrp.copy()

        if planta_mrp != "Todas":
            mrp_filtrado = mrp_filtrado[
                mrp_filtrado["Planta"] == planta_mrp
            ]

        # Evitar filas auxiliares de comentarios y equivalencias
        if "Concat" in mrp_filtrado.columns:
            codigo = (
                mrp_filtrado["Centro"].astype(str) +
                mrp_filtrado["Material"].astype(str).str.replace(
                    r"\.0$", "", regex=True
                )
            )

            mrp_filtrado = mrp_filtrado[
                mrp_filtrado["Concat"].astype(str) == codigo
            ]

        st.dataframe(
            mrp_filtrado[columnas_disponibles],
            use_container_width=True,
            hide_index=True
        )

        st.success("Información MRP cargada correctamente.")

    except Exception as e:
        st.error(f"Error al procesar el archivo MRP: {e}")


# ==========================================================
# PIE DE PAGINA
# ==========================================================

st.divider()

st.caption(
    "ENAEX CHILE | Prototipo académico de gestión de materias primas | "
    "Información sujeta a validación con SAP."
)

