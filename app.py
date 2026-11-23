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


def formato_numero(valor, decimales=0):
    valor = numero(valor)
    if pd.isna(valor):
        return "0"
    return f"{valor:,.{decimales}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def selector_planta(titulo, key, incluir_todas=False):
    opciones = (["Todas"] if incluir_todas else []) + list(PLANTAS.keys())
    if key not in st.session_state or st.session_state[key] not in opciones:
        st.session_state[key] = opciones[0]
    st.markdown(f"**{titulo}**")
    columnas = st.columns(len(opciones))
    for i, opcion in enumerate(opciones):
        with columnas[i]:
            elegido = st.session_state[key] == opcion
            if st.button(("✓ " if elegido else "") + opcion, key=f"{key}_boton_{i}",
                         use_container_width=True,
                         type="primary" if elegido else "secondary"):
                st.session_state[key] = opcion
                st.rerun()
    return st.session_state[key]


def selector_material(df, texto_busqueda, key):
    if df.empty:
        return None
    catalogo = df[["Material", "Descripción"]].fillna("").drop_duplicates().copy()
    catalogo["Material"] = catalogo["Material"].astype(str)
    catalogo["Descripción"] = catalogo["Descripción"].astype(str)
    catalogo = catalogo[catalogo["Material"].str.strip() != ""]
    busqueda = st.text_input(texto_busqueda,
        placeholder="Escribe el código o nombre de la materia prima...",
        key=f"{key}_busqueda").strip().lower()
    if busqueda:
        catalogo = catalogo[
            catalogo["Material"].str.lower().str.contains(busqueda, na=False)
            | catalogo["Descripción"].str.lower().str.contains(busqueda, na=False)
        ]
    if catalogo.empty:
        st.warning("No se encontraron materias primas con esa búsqueda.")
        return None
    opciones = {f"{r['Material']} — {r['Descripción']}".strip(" —"): r["Material"]
                for _, r in catalogo.iterrows()}
    etiqueta = st.selectbox("Seleccionar materia prima (código — nombre)",
                            list(opciones.keys()), key=f"{key}_seleccion")
    return opciones[etiqueta]


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
            "Inventario y cobertura",
            "Resumen general",
            "Análisis por planta",
            "Consumo mensual",
            "Evolución de precios"
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
    planta = selector_planta("Seleccionar planta", "planta_analisis")

    df_c = consumos[(consumos["Planta"] == planta) &
                    (consumos["Año"] == año_seleccionado)].copy() if not consumos.empty else pd.DataFrame()
    df_p = precios[(precios["Planta"] == planta) &
                   (precios["Año"] == año_seleccionado)].copy() if not precios.empty else pd.DataFrame()

    cantidad_materiales = df_c["Material"].nunique() if not df_c.empty else 0
    st.metric("Materias primas", formato_numero(cantidad_materiales))

    st.markdown("### Consumo mensual por materia prima")
    if not df_c.empty:
        material = selector_material(df_c[["Material", "Descripción"]],
            "Buscar por código o nombre de materia prima", "material_consumo_planta")
        if material is not None:
            detalle = df_c[df_c["Material"] == material].copy()
            descripcion = detalle["Descripción"].iloc[0] if not detalle.empty else ""
            st.markdown(f"**{material} — {descripcion}**")
            unidad = st.selectbox("Unidad de medida",
                sorted(detalle["Unidad"].dropna().unique()), key="unidad_planta_detalle")
            grafico = detalle[detalle["Unidad"] == unidad].groupby(
                ["Año", "Mes"], as_index=False)["Consumo"].sum()
            grafico["Periodo"] = grafico["Mes"].map(MESES) + " " + grafico["Año"].astype(str)
            fig = px.bar(grafico, x="Periodo", y="Consumo",
                         color_discrete_sequence=[COLORES[planta]])
            fig.update_traces(texttemplate="%{y:,.0f}", textposition="outside")
            fig.update_layout(template="plotly_white",
                              yaxis_title=f"Consumo ({unidad})", xaxis_title="Mes")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay información de consumo para esta planta y año.")

    st.markdown("### Evolución de precios")
    if not df_p.empty:
        material_precio = selector_material(df_p[["Material", "Descripción"]],
            "Buscar materia prima para revisar sus precios", "material_planta_precio")
        if material_precio is not None:
            seleccionado = df_p[df_p["Material"] == material_precio].copy()
            monedas = sorted(seleccionado["Moneda"].dropna().unique())
            if monedas:
                moneda = st.selectbox("Moneda", monedas, key="moneda_planta")
                seleccionado = seleccionado[seleccionado["Moneda"] == moneda].sort_values("Fecha")
                fig = px.line(seleccionado, x="Fecha", y="Precio unitario", markers=True,
                    hover_data=["Orden de compra", "Posición"],
                    color_discrete_sequence=[COLORES[planta]])
                fig.update_layout(template="plotly_white",
                                  yaxis_title=f"Precio unitario ({moneda})")
                st.plotly_chart(fig, use_container_width=True)
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

    planta = selector_planta("Seleccionar planta", "planta_consumo_detalle")

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

    catalogo_consumo = consumo_planta[["Material", "Descripción"]].drop_duplicates()
    catalogo_mrp = (mrp_planta[["Material", "Descripción del material"]]
        .rename(columns={"Descripción del material": "Descripción"}).drop_duplicates()
        if not mrp_planta.empty else pd.DataFrame(columns=["Material", "Descripción"]))
    catalogo_materiales = pd.concat([catalogo_consumo, catalogo_mrp],
                                    ignore_index=True).drop_duplicates()
    material = selector_material(catalogo_materiales,
        "Buscar por código o nombre de materia prima", "material_consumo_detalle")
    if material is None:
        st.stop()

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

        a.metric("Stock actual", f"{formato_numero(stock)} {unidad}")
        b.metric("Stock seguridad", f"{formato_numero(seguridad)} {unidad}")
        c.metric("Stock máximo", f"{formato_numero(maximo)} {unidad}")
        d.metric("Cobertura", f"{formato_numero(cobertura, 2)} meses")

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
            f"{formato_numero(historial['Consumo'].sum())} {unidad}"
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
