import streamlit as st
import pandas as pd
import random
from datetime import datetime, timedelta

# --- CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="TalentPro Cotizador", layout="wide", page_icon="🌎")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stMetric {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        padding: 10px;
        border-radius: 5px;
    }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 1. CONFIGURACIÓN DE PAÍSES (Desde Fila 29 de tu Excel)
# ==============================================================================
# COPIA Y PEGA AQUÍ LOS PAÍSES QUE APARECEN EN TU EXCEL DEBAJO DE LA FILA 29
# PARA CADA CATEGORÍA (ALTO, MEDIO, BAJO).

PAISES_ALTO = [
    "Estados Unidos", "Puerto Rico", "Canadá", "Brasil", "España", "Europa"
]

PAISES_MEDIO = [
    "Chile", "México", "Colombia", "Perú", "Panamá", "Uruguay", "Costa Rica"
]

PAISES_BAJO = [
    "Argentina", "Bolivia", "Paraguay", "Ecuador", "Guatemala", 
    "Honduras", "El Salvador", "Nicaragua", "República Dominicana"
]

# Unimos todo para el menú desplegable
TODOS_LOS_PAISES = sorted(PAISES_ALTO + PAISES_MEDIO + PAISES_BAJO)

def obtener_nivel_pais(pais):
    if pais in PAISES_ALTO: return "Alto"
    if pais in PAISES_MEDIO: return "Medio"
    if pais in PAISES_BAJO: return "Bajo"
    return "Medio" # Por defecto si no se encuentra

# ==============================================================================
# 2. PRECIOS DE SERVICIOS (TP US Alto / Medio / Bajo)
# ==============================================================================
# Aquí están las tarifas. El sistema elegirá la columna correcta según el país.

DB_TARIFAS_SERVICIOS = {
    "Assessment Center (Jornada)": {
        "Alto":  {"Angelica": 1800, "Senior": 1200, "BM": 1000, "BP": 800},
        "Medio": {"Angelica": 1500, "Senior": 1000, "BM": 800, "BP": 600},
        "Bajo":  {"Angelica": 1200, "Senior": 800,  "BM": 600, "BP": 450},
    },
    "Entrevista por Competencias": {
        "Alto":  {"Angelica": 450, "Senior": 250, "BM": 180, "BP": 120},
        "Medio": {"Angelica": 300, "Senior": 150, "BM": 100, "BP": 80},
        "Bajo":  {"Angelica": 220, "Senior": 120, "BM": 80,  "BP": 60},
    },
    "Feedback Individual (1:1)": {
        "Alto":  {"Angelica": 550, "Senior": 300, "BM": 220, "BP": 150},
        "Medio": {"Angelica": 400, "Senior": 200, "BM": 150, "BP": 100},
        "Bajo":  {"Angelica": 300, "Senior": 150, "BM": 100, "BP": 80},
    },
    "Consultoría HR / Diseño (Hora)": {
        "Alto":  {"Angelica": 350, "Senior": 200, "BM": 150, "BP": 100},
        "Medio": {"Angelica": 250, "Senior": 120, "BM": 90,  "BP": 70},
        "Bajo":  {"Angelica": 180, "Senior": 90,  "BM": 70,  "BP": 50},
    },
    "Workshop / Taller (Sesión)": {
        "Alto":  {"Angelica": 2500, "Senior": 1800, "BM": 1200, "BP": 1000},
        "Medio": {"Angelica": 2000, "Senior": 1200, "BM": 900,  "BP": 700},
        "Bajo":  {"Angelica": 1500, "Senior": 900,  "BM": 700,  "BP": 500},
    }
}

# ==============================================================================
# 3. PRECIOS DE PRUEBAS (SHL / Evaluaciones)
# ==============================================================================
# Estos precios suelen ser internacionales, pero puedes ajustarlos si es necesario.

DB_PRECIOS_PRUEBAS = {
    "OPQ (Personalidad Laboral)": [(100, 22), (200, 21), (300, 20), (500, 19), (1000, 18), (float('inf'), 17)],
    "MQ (Motivación)": [(100, 17), (200, 17), (300, 16), (500, 15), (1000, 14), (float('inf'), 13)],
    "CCSQ (Contacto Cliente)": [(100, 17), (200, 17), (300, 16), (500, 15), (1000, 14), (float('inf'), 13)],
    "Verify Interactive": [(100, 19), (200, 18), (300, 16), (500, 14), (1000, 12), (float('inf'), 11)],
    "Smart Interview": [(100, 24), (200, 23), (300, 22), (500, 21), (1000, 19), (float('inf'), 17)],
    "360 Assessment": [(float('inf'), 420)],
    "SVAR (Inglés)": [(100, 24), (200, 23), (300, 22), (500, 21), (1000, 19), (float('inf'), 17)]
}

# --- ESTADO DE LA APLICACIÓN ---
if 'cotizaciones' not in st.session_state:
    st.session_state['cotizaciones'] = pd.DataFrame([
        {'id': 'TP-1001', 'fecha': '2024-11-01', 'empresa': 'Cliente USA', 'pais': 'Estados Unidos', 'total': 2500, 'estado': 'Facturada', 'vendedor': 'Comercial 1'},
        {'id': 'TP-1002', 'fecha': '2024-11-05', 'empresa': 'Cliente Chile', 'pais': 'Chile', 'total': 1500, 'estado': 'Enviada', 'vendedor': 'Comercial 2'}
    ])
if 'carrito' not in st.session_state: st.session_state['carrito'] = []
if 'metas' not in st.session_state: st.session_state['metas'] = {'Comercial 1': 60000, 'Comercial 2': 45000}

# --- LÓGICA DE PRECIOS ---
def get_precio_prueba(nombre, cantidad):
    tramos = DB_PRECIOS_PRUEBAS.get(nombre, [])
    for limite, precio in tramos:
        if cantidad <= limite: return precio
    return 0.0

# --- PANTALLA 1: COTIZADOR ---
def cotizador():
    st.title("📝 Cotizador Internacional TalentPro")
    st.markdown("---")

    # 1. SELECCIÓN DE PAÍS (CRÍTICO)
    with st.container():
        st.subheader("1. Configuración Regional")
        col_pais1, col_pais2, col_pais3 = st.columns([1, 2, 1])
        
        with col_pais1:
            pais_sel = st.selectbox("🌎 País del Proyecto", TODOS_LOS_PAISES, index=TODOS_LOS_PAISES.index("Chile") if "Chile" in TODOS_LOS_PAISES else 0)
        
        # Determinar nivel automáticamente
        nivel = obtener_nivel_pais(pais_sel)
        
        with col_pais2:
            st.info(f"El país **{pais_sel}** corresponde a la tarifa: **TP US {nivel.upper()}**")

    # 2. DATOS CLIENTE
    st.markdown("---")
    c1, c2, c3, c4 = st.columns(4)
    empresa = c1.text_input("Nombre Empresa")
    contacto = c2.text_input("Contacto")
    email = c3.text_input("Email")
    vendedor = c4.selectbox("Ejecutivo", ["Comercial 1", "Comercial 2", "Gerencia"])
    fecha = c1.date_input("Fecha", datetime.now())

    # 3. AGREGAR PRODUCTOS
    st.markdown("---")
    st.subheader("2. Servicios y Evaluaciones")
    
    tab_pruebas, tab_servicios = st.tabs(["🧩 Evaluaciones (Volumen)", "💼 Servicios (Consultoría)"])

    # --- PRUEBAS ---
    with tab_pruebas:
        kp1, kp2, kp3, kp4 = st.columns([3, 1, 1, 1])
        sel_p = kp1.selectbox("Prueba / Licencia", list(DB_PRECIOS_PRUEBAS.keys()))
        cant_p = kp2.number_input("Cantidad", min_value=1, value=10)
        
        precio_p = get_precio_prueba(sel_p, cant_p)
        kp3.metric("Precio Unitario", f"${precio_p:.2f}")
        
        if kp4.button("Agregar", key="btn_p"):
            total = precio_p * cant_p
            st.session_state['carrito'].append({
                "Ítem": "Evaluación",
                "Descripción": sel_p,
                "Detalle": f"Volumen: {cant_p}",
                "Tarifa Aplicada": "Global",
                "Unitario": precio_p,
                "Total": total
            })
            st.rerun()

    # --- SERVICIOS (Lógica País) ---
    with tab_servicios:
        ks1, ks2, ks3, ks4 = st.columns([3, 2, 1, 1])
        sel_s = ks1.selectbox("Servicio Consultoría", list(DB_TARIFAS_SERVICIOS.keys()))
        
        col_rol, col_horas = ks2.columns(2)
        rol = col_rol.selectbox("Rol", ["Angelica", "Senior", "BM", "BP"])
        horas = col_horas.number_input("Horas", min_value=1, value=1)
        
        # Obtener precio dinámico según el Nivel del País
        try:
            tarifa = DB_TARIFAS_SERVICIOS[sel_s][nivel][rol]
            ks3.metric(f"Tarifa ({nivel})", f"${tarifa:.2f}")
            
            if ks4.button("Agregar", key="btn_s"):
                total_s = tarifa * horas
                st.session_state['carrito'].append({
                    "Ítem": "Servicio",
                    "Descripción": sel_s,
                    "Detalle": f"{rol} ({horas}h)",
                    "Tarifa Aplicada": f"{pais_sel} ({nivel})",
                    "Unitario": tarifa,
                    "Total": total_s
                })
                st.rerun()
        except:
            ks3.error("No disponible")

    # 4. CARRITO
    if st.session_state['carrito']:
        st.markdown("---")
        st.subheader("🛒 Resumen")
        
        df_c = pd.DataFrame(st.session_state['carrito'])
        st.dataframe(df_c, use_container_width=True, hide_index=True)
        
        subtotal = df_c['Total'].sum()
        
        ce1, ce2 = st.columns([3, 1])
        with ce2:
            st.markdown("### Totales")
            fee = st.checkbox("Fee Admin (10%)", value=False)
            comision = 30.0
            desc = st.number_input("Descuento ($)", 0.0)
            
            val_fee = subtotal * 0.10 if fee else 0
            final = subtotal + val_fee + comision - desc
            
            st.markdown(f"""
            | Concepto | Monto |
            | :--- | ---: |
            | **Subtotal** | **${subtotal:,.2f}** |
            | Fee 10% | ${val_fee:,.2f} |
            | Comisión | ${comision:,.2f} |
            | Descuento | -${desc:,.2f} |
            | **TOTAL** | **${final:,.2f}** |
            """)
            
            if st.button("💾 CONFIRMAR", type="primary"):
                if not empresa:
                    st.error("Falta Empresa")
                else:
                    new_id = f"TP-{random.randint(1000,9999)}"
                    reg = {
                        'id': new_id, 'fecha': fecha.strftime("%Y-%m-%d"),
                        'empresa': empresa, 'pais': pais_sel, 'total': final,
                        'estado': 'Enviada', 'vendedor': vendedor
                    }
                    st.session_state['cotizaciones'] = pd.concat([st.session_state['cotizaciones'], pd.DataFrame([reg])], ignore_index=True)
                    st.session_state['carrito'] = []
                    st.success(f"Creada: {new_id}")
                    st.balloons()
        
        with ce1:
            if st.button("Borrar Todo"):
                st.session_state['carrito'] = []
                st.rerun()

# --- PANTALLA 2: DASHBOARD ---
def dashboard():
    st.title("📊 Dashboard")
    df = st.session_state['cotizaciones']
    df['fecha'] = pd.to_datetime(df['fecha'])
    
    # KPIs
    k1, k2, k3 = st.columns(3)
    k1.metric("Ventas (Facturadas)", f"${df[df['estado'].isin(['Facturada','Pagada'])]['total'].sum():,.0f}")
    k2.metric("Pipeline", f"${df[df['estado'].isin(['Enviada','Aprobada'])]['total'].sum():,.0f}")
    k3.metric("Cotizaciones", len(df))
    
    st.markdown("---")
    
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Ventas por País")
        if 'pais' in df.columns:
            data_pais = df[df['estado']=='Facturada'].groupby('pais')['total'].sum()
            st.bar_chart(data_pais)
            
    with c2:
        st.subheader("Metas")
        ventas_v = df[df['estado'].isin(['Facturada', 'Pagada'])].groupby('vendedor')['total'].sum()
        for v, meta in st.session_state['metas'].items():
            real = ventas_v.get(v, 0)
            st.write(f"**{v}**: ${real:,.0f} / ${meta:,.0f}")
            st.progress(min(real/meta, 1.0))
            
    # Alerta Inactivos
    st.markdown("---")
    st.subheader("Alertas")
    hoy = datetime.now()
    alerta = False
    for emp in df['empresa'].unique():
        fechas = df[df['empresa']==emp]['fecha']
        if fechas.max() < (hoy - timedelta(days=365)):
            st.error(f"⚠️ {emp} (Última: {fechas.max().date()})")
            alerta = True
    if not alerta: st.success("Cartera saludable")

# --- PANTALLA 3: FINANZAS ---
def finanzas():
    st.title("💰 Finanzas")
    df = st.session_state['cotizaciones']
    
    edited = st.data_editor(
        df,
        column_config={
            "estado": st.column_config.SelectboxColumn("Estado", options=["Enviada", "Aprobada", "Facturada", "Pagada", "Rechazada"]),
            "total": st.column_config.NumberColumn(format="$%d"),
            "pais": st.column_config.TextColumn("País")
        },
        disabled=["id", "empresa", "vendedor"],
        hide_index=True,
        use_container_width=True
    )
    if not edited.equals(df):
        st.session_state['cotizaciones'] = edited
        st.toast("Guardado")

# --- MENÚ ---
with st.sidebar:
    st.title("TalentPro App")
    opcion = st.radio("Menú", ["Cotizador", "Dashboard", "Finanzas"])

if opcion == "Cotizador": cotizador()
elif opcion == "Dashboard": dashboard()
elif opcion == "Finanzas": finanzas()
