
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import unicodedata
from datetime import datetime

# ==========================================================
# 1. CONFIGURACION GENERAL
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


def leer_excel(archivo):

    if archivo is None:
        return pd.DataFrame()

    try:
        archivo.seek(0)

        return pd.read_excel(
            archivo,
            engine="openpyxl"
        )

    except Exception as e:

        st.error(
            f"Error leyendo {archivo.name}: {e}"
        )

        return pd.DataFrame()


def fecha_excel(serie):

    return pd.to_datetime(
        serie,
        errors="coerce",
        dayfirst=True
    )


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

    resultado = resultado.dropna(
        subset=["Fecha"]
    )

    # Movimientos de consumo y anulaciones.
    resultado = resultado[
        resultado["Movimiento"].isin(["261", "262"])
    ].copy()

    # SAP: 261 normalmente negativo y 262 positivo.
    # Se invierte el signo para presentar el consumo neto positivo.
    resultado["Consumo"] = (
        -resultado["Cantidad original"]
    )

    resultado["Año"] = resultado["Fecha"].dt.year
    resultado["Mes"] = resultado["Fecha"].dt.month

    return resultado


# ==========================================================
# 5. PROCESAMIENTO DE PRECIOS SAP
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
        df, [
            "UNIDAD DE MEDIDA",
            "Un.medida de entrada"
        ]
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
        pd.to_numeric(
            df[cantidad],
            errors="coerce"
        )
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
    )

    resultado["Unidad"] = (
        df[unidad].fillna("").astype(str)
        if unidad else ""
    )

    resultado["Planta"] = planta

    # Precio unitario = PRECIO / CANTIDAD.
    # Cuando no existe divisor válido, se conserva PRECIO.
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

    resultado["Año"] = resultado["Fecha"].dt.year

    return resultado


# ==========================================================
# 6. PROCESAMIENTO DEL MRP
# ==========================================================

def leer_mrp(archivo):

    if archivo is None:
        return pd.DataFrame(), pd.DataFrame()

    try:

        archivo.seek(0)

        ns = pd.read_excel(
            archivo,
            sheet_name="NS",
            header=9,
            engine="openpyxl"
        )

        archivo.seek(0)

        mrp = pd.read_excel(
            archivo,
            sheet_name="MRP",
            header=7,
            engine="openpyxl"
        )

        ns = ns.dropna(
            subset=["Centro", "Material"]
        ).copy()

        mrp = mrp.dropna(
            subset=["Centro"]
        ).copy()

        ns["Centro"] = ns["Centro"].astype(str).str.strip()
        mrp["Centro"] = mrp["Centro"].astype(str).str.strip()

        ns["Material"] = ns["Material"].apply(limpiar_codigo)
        mrp["Material"] = mrp["Material"].apply(limpiar_codigo)

        if "Concat" in mrp.columns:

            mrp["Concat"] = (
                mrp["Concat"]
                .astype(str)
                .str.replace(r"\.0$", "", regex=True)
                .str.strip()
            )

        return ns, mrp

    except Exception as e:

        st.error(f"Error procesando MRP: {e}")

        return pd.DataFrame(), pd.DataFrame()


# ==========================================================
# 7. ENCABEZADO
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


# ==========================================================
# 8. MENU LATERAL
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

    st.markdown("### 📁 CARGA DE INFORMACIÓN")

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
# 9. CONSOLIDACION DE ARCHIVOS
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

        procesado = preparar_consumo(
            df, planta
        )

        if not procesado.empty:
            lista_consumos.append(procesado)


for planta, archivo in archivos_precios.items():

    if archivo is not None:

        df = leer_excel(archivo)

        procesado = preparar_precios(
            df, planta
        )

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

datos_ns, datos_mrp = leer_mrp(archivo_mrp)


# ==========================================================
# 10. FILTROS GLOBALES
# ==========================================================

años_disponibles = []

if not consumos.empty:
    años_disponibles += consumos["Año"].dropna().tolist()

if not precios.empty:
    años_disponibles += precios["Año"].dropna().tolist()

if not datos_mrp.empty:

    columnas_fecha = [
        c for c in datos_mrp.columns
        if isinstance(c, (datetime, pd.Timestamp))
    ]

    años_disponibles += [
        pd.Timestamp(c).year
        for c in columnas_fecha
    ]

años_disponibles = sorted(
    set(años_disponibles)
)

if not años_disponibles:
    años_disponibles = [datetime.now().year]


plantas_disponibles = list(PLANTAS.keys())

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
# 11. RESUMEN GENERAL
# ==========================================================

if pagina == "Resumen general":

    st.markdown("## Resumen general")

    a, b, c, d = st.columns(4)

    materiales = (
        consumo_filtrado["Material"].nunique()
        if not consumo_filtrado.empty else 0
    )

    registros = (
        len(precio_filtrado)
        if not precio_filtrado.empty else 0
    )

    a.metric(
        "Materias primas",
        f"{materiales:,}"
    )

    b.metric(
        "Registros de consumo",
        f"{len(consumo_filtrado):,}"
    )

    c.metric(
        "Registros de precios",
        f"{registros:,}"
    )

    d.metric(
        "Plantas disponibles",
        str(len(plantas_disponibles))
    )

    st.markdown("### Consumo mensual por planta")

    if not consumo_filtrado.empty:

        mensual = (
            consumo_filtrado.groupby(
                ["Planta", "Año", "Mes", "Unidad"],
                as_index=False
            )["Consumo"].sum()
        )

        mensual["Periodo"] = (
            mensual["Año"].astype(str) + "-" +
            mensual["Mes"].astype(str).str.zfill(2)
        )

        # No sumar unidades distintas en un solo gráfico.
        unidad_grafico = st.selectbox(
            "Unidad de medida",
            sorted(mensual["Unidad"].dropna().unique()),
            key="unidad_resumen"
        )

        mensual = mensual[
            mensual["Unidad"] == unidad_grafico
        ]

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
            yaxis_title=f"Consumo ({unidad_grafico})"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    else:

        st.info("Carga los archivos de consumo SAP.")

    st.markdown("### Consumo por planta")

    if not consumo_filtrado.empty:

        unidad_comparacion = st.selectbox(
            "Unidad para comparar plantas",
            sorted(
                consumo_filtrado["Unidad"].dropna().unique()
            ),
            key="unidad_planta"
        )

        por_planta = (
            consumo_filtrado[
                consumo_filtrado["Unidad"] == unidad_comparacion
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
            yaxis_title=f"Consumo ({unidad_comparacion})"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )


# ==========================================================
# 12. ANALISIS POR PLANTA
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

    a, b, c = st.columns(3)

    a.metric(
        "Registros de consumo",
        f"{len(df_c):,}"
    )

    b.metric(
        "Materias primas consumidas",
        str(df_c["Material"].nunique())
        if not df_c.empty else "0"
    )

    c.metric(
        "Órdenes con precio",
        str(df_p["Orden de compra"].nunique())
        if not df_p.empty else "0"
    )

    st.markdown("### Consumo mensual")

    if not df_c.empty:

        unidad = st.selectbox(
            "Unidad de medida",
            sorted(df_c["Unidad"].dropna().unique()),
            key="unidad_planta_detalle"
        )

        grafico = (
            df_c[df_c["Unidad"] == unidad]
            .groupby(["Año", "Mes"], as_index=False)["Consumo"]
            .sum()
        )

        grafico["Periodo"] = (
            grafico["Año"].astype(str) + "-" +
            grafico["Mes"].astype(str).str.zfill(2)
        )

        fig = px.bar(
            grafico,
            x="Periodo",
            y="Consumo",
            color_discrete_sequence=[COLORES[planta]]
        )

        fig.update_layout(
            template="plotly_white",
            yaxis_title=f"Consumo ({unidad})"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    st.markdown("### Evolución de precios")

    if not df_p.empty:

        material = st.selectbox(
            "Materia prima",
            sorted(df_p["Material"].unique()),
            key="material_planta_precio"
        )

        seleccionado = df_p[
            df_p["Material"] == material
        ]

        moneda = st.selectbox(
            "Moneda",
            sorted(seleccionado["Moneda"].dropna().unique()),
            key="moneda_planta"
        )

        seleccionado = seleccionado[
            seleccionado["Moneda"] == moneda
        ]

        fig = px.line(
            seleccionado.sort_values("Fecha"),
            x="Fecha",
            y="Precio unitario",
            markers=True
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

        st.info("No hay información de precios disponible.")


# ==========================================================
# 13. CONSUMO HISTORICO Y PLANIFICACION MRP
# ==========================================================

elif pagina == "Consumo mensual":

    st.markdown("## Análisis de consumo de materias primas")

    st.caption(
        "Consumo histórico SAP y planificación futura MRP"
    )

    if archivo_mrp is None:

        st.warning("Carga el archivo MRP.")
        st.stop()

    if consumos.empty:

        st.warning("Carga los archivos de consumo SAP.")
        st.stop()

    planta = st.selectbox(
        "Seleccionar planta",
        list(PLANTAS.keys()),
        key="planta_consumo_detalle"
    )

    centro = PLANTAS[planta]

    consumo_planta = consumos[
        consumos["Planta"] == planta
    ].copy()

    mrp_planta = datos_mrp[
        datos_mrp["Centro"] == centro
    ].copy() if not datos_mrp.empty else pd.DataFrame()

    ns_planta = datos_ns[
        datos_ns["Centro"] == centro
    ].copy() if not datos_ns.empty else pd.DataFrame()

    materiales = sorted(
        set(consumo_planta["Material"].tolist()) |
        set(mrp_planta["Material"].tolist())
    )

    if not materiales:

        st.warning("No hay materiales disponibles.")
        st.stop()

    material = st.selectbox(
        "Buscar materia prima",
        materiales
    )

    historial = consumo_planta[
        consumo_planta["Material"] == material
    ].copy()

    plan_material = mrp_planta[
        mrp_planta["Material"] == material
    ].copy()

    registro_mrp = plan_material[
        plan_material["Concat"] == centro + material
    ] if not plan_material.empty else pd.DataFrame()

    registro_ns = ns_planta[
        ns_planta["Material"] == material
    ].copy()

    if not registro_mrp.empty:

        fila = registro_mrp.iloc[0]

    else:

        fila = None

    descripcion = ""

    if not historial.empty:
        descripcion = historial["Descripción"].iloc[0]

    elif not registro_ns.empty:
        descripcion = registro_ns["Descripción del material"].iloc[0]

    elif fila is not None:
        descripcion = fila["Descripción del material"]

    st.markdown(f"### {descripcion}")
    st.caption(f"Material SAP: {material} | {planta}")

    # ------------------------------------------------------
    # INDICADORES
    # ------------------------------------------------------

    st.markdown("### Estado actual")

    if fila is not None:

        stock = numero(fila["Stock Actual"])
        seguridad = numero(fila["Stock Seguridad"])
        maximo = numero(fila["Stock Máximo"])
        cobertura = numero(fila["Cobertura\n[Meses]"])
        unidad = fila["UM"]

        stock = 0 if pd.isna(stock) else stock
        seguridad = 0 if pd.isna(seguridad) else seguridad
        maximo = 0 if pd.isna(maximo) else maximo
        cobertura = 0 if pd.isna(cobertura) else cobertura

        a, b, c, d = st.columns(4)

        a.metric("Stock actual", f"{stock:,.2f} {unidad}")
        b.metric("Stock seguridad", f"{seguridad:,.2f} {unidad}")
        c.metric("Stock máximo", f"{maximo:,.2f} {unidad}")
        d.metric("Cobertura", f"{cobertura:,.2f} meses")

        if not registro_ns.empty:

            clasificacion = registro_ns.iloc[0]["NS Corregido"]

            st.info(
                f"Clasificación de nivel de servicio: {clasificacion}"
            )

    else:

        unidad = (
            historial["Unidad"].iloc[0]
            if not historial.empty else ""
        )

        st.warning("No existe registro MRP para este material.")

    # ------------------------------------------------------
    # CONSUMO HISTORICO
    # ------------------------------------------------------

    st.markdown("### 1. Evolución del consumo histórico")

    if not historial.empty:

        mensual = (
            historial.groupby(
                ["Año", "Mes"], as_index=False
            )["Consumo"].sum()
        )

        mensual["Fecha"] = pd.to_datetime(
            mensual["Año"].astype(str) + "-" +
            mensual["Mes"].astype(str).str.zfill(2) + "-01"
        )

        fig = px.bar(
            mensual.sort_values("Fecha"),
            x="Fecha",
            y="Consumo",
            text_auto=".3s",
            color_discrete_sequence=["#3985D6"]
        )

        fig.update_layout(
            template="plotly_white",
            yaxis_title=f"Consumo ({unidad})"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

        st.metric(
            "Consumo acumulado",
            f"{historial['Consumo'].sum():,.2f} {unidad}"
        )

    else:

        st.info("No hay movimientos históricos disponibles.")

    # ------------------------------------------------------
    # PROYECCION MRP
    # ------------------------------------------------------

    st.markdown("### 2. Consumo proyectado según MRP")

    proyecciones = []

    if fila is not None:

        columnas_fecha = [
            col for col in datos_mrp.columns
            if isinstance(col, (datetime, pd.Timestamp))
        ]

        for col in columnas_fecha:

            valor = numero(fila[col])

            if pd.notna(valor):

                proyecciones.append({
                    "Fecha": pd.Timestamp(col),
                    "Consumo proyectado": valor
                })

    if proyecciones:

        proyeccion_df = pd.DataFrame(proyecciones)

        fig = px.line(
            proyeccion_df,
            x="Fecha",
            y="Consumo proyectado",
            markers=True,
            color_discrete_sequence=["#16A34A"]
        )

        fig.update_layout(
            template="plotly_white",
            yaxis_title=f"Consumo proyectado ({unidad})"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

        st.dataframe(
            proyeccion_df,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info("No existen valores proyectados disponibles.")

    # ------------------------------------------------------
    # COMPARACION
    # ------------------------------------------------------

    st.markdown("### 3. Comparación de consumo real y proyectado")

    if not historial.empty and proyecciones:

        real = (
            historial.groupby(
                ["Año", "Mes"], as_index=False
            )["Consumo"].sum()
        )

        real["Fecha"] = pd.to_datetime(
            real["Año"].astype(str) + "-" +
            real["Mes"].astype(str).str.zfill(2) + "-01"
        )

        real = real[
            ["Fecha", "Consumo"]
        ].rename(
            columns={"Consumo": "Consumo real SAP"}
        )

        comparacion = pd.merge(
            real,
            proyeccion_df,
            on="Fecha",
            how="outer"
        ).sort_values("Fecha")

        comparacion_larga = comparacion.melt(
            id_vars="Fecha",
            value_vars=[
                "Consumo real SAP",
                "Consumo proyectado"
            ],
            var_name="Tipo",
            value_name="Cantidad"
        )

        fig = px.line(
            comparacion_larga,
            x="Fecha",
            y="Cantidad",
            color="Tipo",
            markers=True,
            color_discrete_map={
                "Consumo real SAP": "#3985D6",
                "Consumo proyectado": "#16A34A"
            }
        )

        fig.update_layout(
            template="plotly_white",
            yaxis_title=f"Cantidad ({unidad})"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    else:

        st.info(
            "Se necesitan datos históricos y proyecciones "
            "para realizar esta comparación."
        )

    # ------------------------------------------------------
    # DETALLE SAP
    # ------------------------------------------------------

    with st.expander("Detalle de movimientos SAP"):

        if not historial.empty:

            st.dataframe(
                historial[[
                    "Fecha",
                    "Material",
                    "Descripción",
                    "Movimiento",
                    "Cantidad original",
                    "Consumo",
                    "Unidad"
                ]].sort_values(
                    "Fecha", ascending=False
                ),
                use_container_width=True,
                hide_index=True
            )

        else:

            st.info("No existen movimientos disponibles.")


# ==========================================================
# 14. EVOLUCION DE PRECIOS Y RANKING
# ==========================================================

elif pagina == "Evolución de precios":

    st.markdown("## Evolución y análisis de precios")

    if precios.empty:

        st.warning("Carga los archivos de precios SAP.")
        st.stop()

    # ------------------------------------------------------
    # FILTRO DE PLANTA
    # ------------------------------------------------------

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
        subset=["Fecha", "Precio unitario", "Moneda"]
    )

    # ------------------------------------------------------
    # RANKING DE VARIACIONES
    # ------------------------------------------------------

    st.markdown("### Ranking de variaciones de precios")

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

        for (planta, material, moneda), grupo in grupos:

            grupo = grupo.sort_values("Fecha")

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

                "Planta": planta,
                "Material": material,
                "Descripción": ultimo["Descripción"],
                "Moneda": moneda,
                "Precio inicial": inicial,
                "Último precio": final,
                "Variación (%)": variacion,
                "Fecha inicial": primero["Fecha"],
                "Fecha final": ultimo["Fecha"],
                "Registros": len(grupo)

            })

    ranking = pd.DataFrame(resultados)

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

            st.markdown("#### 🔴 Mayores aumentos")

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

                        "Precio inicial": "{:,.4f}",
                        "Último precio": "{:,.4f}",
                        "Variación (%)": "{:+.2f}%"

                    }),
                    use_container_width=True,
                    hide_index=True
                )

            else:

                st.info("No hay aumentos registrados.")

        with cb:

            st.markdown("#### 🟢 Mayores disminuciones")

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

                        "Precio inicial": "{:,.4f}",
                        "Último precio": "{:,.4f}",
                        "Variación (%)": "{:+.2f}%"

                    }),
                    use_container_width=True,
                    hide_index=True
                )

            else:

                st.info("No hay disminuciones registradas.")

        st.markdown("### Comparación de variaciones")

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

        with st.expander("Consultar ranking completo"):

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
    # ANALISIS INDIVIDUAL DE PRECIOS
    # ------------------------------------------------------

    st.markdown("### Análisis individual de precios")

    materiales = sorted(
        datos["Material"].dropna().unique()
    )

    material = st.selectbox(
        "Seleccionar materia prima",
        materiales,
        key="material_precio_individual"
    )

    df = datos[
        datos["Material"] == material
    ].copy()

    descripcion = df["Descripción"].iloc[0]

    st.markdown(f"#### {descripcion}")
    st.caption(f"Código de material: {material}")

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
    ].sort_values("Fecha")

    if df.empty:

        st.warning("No hay registros para esta moneda.")
        st.stop()

    # ------------------------------------------------------
    # INDICADORES DE PRECIO
    # ------------------------------------------------------

    inicial = df.iloc[0]["Precio unitario"]
    final = df.iloc[-1]["Precio unitario"]

    promedio = df["Precio unitario"].mean()

    variacion = (
        (final - inicial) / abs(inicial) * 100
        if inicial != 0 else 0
    )

    a, b, c, d = st.columns(4)

    a.metric(
        "Precio inicial",
        f"{inicial:,.4f} {moneda}"
    )

    b.metric(
        "Último precio",
        f"{final:,.4f} {moneda}"
    )

    c.metric(
        "Variación",
        f"{variacion:+.2f}%"
    )

    d.metric(
        "Precio promedio",
        f"{promedio:,.4f} {moneda}"
    )

    st.caption(
        f"Registros: {len(df)} | "
        f"Período: {df['Fecha'].min():%d-%m-%Y} "
        f"al {df['Fecha'].max():%d-%m-%Y}"
    )

    # ------------------------------------------------------
    # GRAFICO DE PRECIOS
    # ------------------------------------------------------

    st.markdown("### 1. Evolución histórica del precio unitario")

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
    # FECHA OC VS CONTABILIZACION
    # ------------------------------------------------------

    st.markdown("### 2. Fecha de OC versus contabilización")

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

        st.info("No existen fechas suficientes para comparar.")

    # ------------------------------------------------------
    # HISTORIAL DE OC
    # ------------------------------------------------------

    st.markdown("### 3. Historial de órdenes de compra")

    columnas = [
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

    historial = df.sort_values(
        "Fecha",
        ascending=False
    )

    st.dataframe(
        historial[columnas].rename(columns={

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

    # ------------------------------------------------------
    # DESCARGAR HISTORIAL
    # ------------------------------------------------------

    csv = historial[columnas].to_csv(
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
# 15. INVENTARIO Y COBERTURA
# ==========================================================

elif pagina == "Inventario y cobertura":

    st.markdown("## Inventario y cobertura")

    if archivo_mrp is None:

        st.warning("Carga el archivo MRP.")
        st.stop()

    if datos_ns.empty or datos_mrp.empty:

        st.error("No fue posible procesar las hojas NS y MRP.")
        st.stop()

    planta = st.selectbox(
        "Seleccionar planta",
        ["Todas"] + list(PLANTAS.keys()),
        key="planta_inventario"
    )

    datos = datos_ns.copy()

    if planta != "Todas":

        centro = PLANTAS[planta]

        datos = datos[
            datos["Centro"] == centro
        ]

    datos["Cob. [Meses]"] = pd.to_numeric(
        datos["Cob. [Meses]"],
        errors="coerce"
    )

    datos["Consumo X̅"] = pd.to_numeric(
        datos["Consumo X̅"],
        errors="coerce"
    )

    # ------------------------------------------------------
    # INDICADORES
    # ------------------------------------------------------

    total = len(datos)

    baja = len(
        datos[
            (datos["Cob. [Meses]"] >= 0) &
            (datos["Cob. [Meses]"] < 1)
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

    a, b, c, d = st.columns(4)

    a.metric("Materias primas", f"{total:,}")
    b.metric("Baja cobertura", f"{baja:,}")
    c.metric("Sin consumo", f"{sin_consumo:,}")
    d.metric("Clasificadas EB", f"{eb:,}")

    # ------------------------------------------------------
    # CLASIFICACION
    # ------------------------------------------------------

    st.markdown("### Clasificación del nivel de servicio")

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
            datos_ns.groupby(
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
    # BAJA COBERTURA
    # ------------------------------------------------------

    st.markdown("### Top 5 materias primas con baja cobertura")

    baja_df = datos[
        (datos["Cob. [Meses]"] >= 0) &
        (datos["Cob. [Meses]"] < 1)
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
    # SIN CONSUMO
    # ------------------------------------------------------

    st.markdown("### Top 5 materias primas sin consumo")

    sin = datos[
        datos["Consumo X̅"] == 0
    ]

    st.dataframe(
        sin[columnas_ns].head(5),
        use_container_width=True,
        hide_index=True
    )

    # ------------------------------------------------------
    # INVENTARIO
    # ------------------------------------------------------

    st.markdown("### Inventario por materia prima")

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

    # ------------------------------------------------------
    # PLANIFICACION MRP
    # ------------------------------------------------------

    st.markdown("### Planificación MRP")

    mrp = datos_mrp.copy()

    if planta != "Todas":

        mrp = mrp[
            mrp["Centro"] == PLANTAS[planta]
        ]

    # Mostrar solamente filas principales de materiales.
    mrp = mrp[
        mrp["Material"].str.fullmatch(
            r"\d+",
            na=False
        )
    ]

    mrp = mrp[
        mrp["Concat"] ==
        mrp["Centro"] + mrp["Material"]
    ]

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
        c for c in columnas_mrp
        if c in mrp.columns
    ]

    st.dataframe(
        mrp[columnas_disponibles],
        use_container_width=True,
        hide_index=True
    )


# ==========================================================
# 16. PIE DE PAGINA
# ==========================================================

st.divider()

st.caption(
    "ENAEX CHILE | Prototipo académico de gestión de materias primas "
    "| Información sujeta a validación con SAP."
)

