import streamlit as st
import pandas as pd
import random
from datetime import datetime, timedelta

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="TalentPro Global", layout="wide", page_icon="🌎")

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
# 1. CONFIGURACIÓN DE PAÍSES (NIVELES DE SERVICIO)
# ==============================================================================
PAISES_ALTO = ["Estados Unidos", "Puerto Rico", "Canadá", "Brasil", "España", "Europa"]
PAISES_MEDIO = ["Chile", "México", "Colombia", "Perú", "Panamá", "Uruguay", "Costa Rica"]
PAISES_BAJO = ["Argentina", "Bolivia", "Paraguay", "Ecuador", "Guatemala", "Honduras", "El Salvador", "Nicaragua", "República Dominicana"]

TODOS_LOS_PAISES = sorted(PAISES_ALTO + PAISES_MEDIO + PAISES_BAJO)

def obtener_nivel_pais(pais):
    if pais in PAISES_ALTO: return "Alto"
    if pais in PAISES_MEDIO: return "Medio"
    if pais in PAISES_BAJO: return "Bajo"
    return "Medio"

# ==============================================================================
# 2. BASE DE DATOS COMPLETA DE PRUEBAS (SHL / SOFTWARE)
# ==============================================================================
# Tramos: 1-100, 101-200, 201-300, 301-500, 501-1000, 1001+
DB_PRECIOS_PRUEBAS = {
    # --- PRUEBAS INDIVIDUALES ---
    "OPQ (Personalidad Laboral)": [(100, 22), (200, 21), (300, 20), (500, 19), (1000, 18), (float('inf'), 17)],
    "MQ (Motivación)": [(100, 17), (200, 17), (300, 16), (500, 15), (1000, 14), (float('inf'), 13)],
    "CCSQ (Contacto con Cliente)": [(100, 17), (200, 17), (300, 16), (500, 15), (1000, 14), (float('inf'), 13)],
    
    # --- REPORTES OPQ ---
    "OPQ + Profile Report": [(100, 29), (200, 28), (300, 27), (500, 26), (1000, 25), (float('inf'), 24)],
    "OPQ + Universal Competences (LA Version)": [(100, 49), (200, 45), (300, 39), (500, 37), (1000, 35), (float('inf'), 32)],
    "OPQ + Universal Competences (Intl Version)": [(100, 93), (200, 85), (300, 78), (500, 72), (1000, 66), (float('inf'), 60)],
    "OPQ + Person-Job Match (LA Version)": [(100, 74), (200, 68), (300, 62), (500, 56), (1000, 50), (float('inf'), 45)],
    "OPQ + Person-Job Match (Intl Version)": [(100, 107), (200, 99), (300, 94), (500, 88), (1000, 80), (float('inf'), 73)],
    "OPQ + Development Action Planner (LA)": [(100, 65), (200, 61), (300, 57), (500, 52), (1000, 48), (float('inf'), 43)],
    "OPQ + Development Action Planner (Intl)": [(100, 108), (200, 99), (300, 92), (500, 84), (1000, 78), (float('inf'), 70)],
    "OPQ + Digital Readiness Report": [(100, 39), (200, 35), (300, 33), (500, 32), (1000, 31), (float('inf'), 30)],
    "OPQ + Candidate Report": [(100, 72), (200, 68), (300, 64), (500, 59), (1000, 55), (float('inf'), 50)],
    "OPQ + Emotional Intelligence Report": [(100, 63), (200, 59), (300, 56), (500, 52), (1000, 49), (float('inf'), 45)],
    "OPQ + Manager Plus Report": [(100, 104), (200, 97), (300, 90), (500, 85), (1000, 79), (float('inf'), 74)],
    "OPQ + Team Impact Report": [(100, 75), (200, 69), (300, 62), (500, 56), (1000, 51), (float('inf'), 45)],
    "OPQ + Leadership Report": [(100, 254), (200, 242), (300, 237), (500, 223), (1000, 215), (float('inf'), 195)],
    "OPQ + Enterprise Leadership Report": [(100, 238), (200, 229), (300, 220), (500, 208), (1000, 195), (float('inf'), 180)],
    "OPQ + High Potential Assessment v2.0": [(100, 238), (200, 229), (300, 220), (500, 208), (1000, 195), (float('inf'), 180)],

    # --- MQ & SALES ---
    "MQ + MQ Profile Report": [(100, 31), (200, 29), (300, 27), (500, 25), (1000, 22), (float('inf'), 20)],
    "OPQ MQ + Sales Report (LA Version)": [(100, 83), (200, 79), (300, 74), (500, 68), (1000, 62), (float('inf'), 55)],
    "OPQ MQ + Sales Report (Intl Version)": [(100, 140), (200, 132), (300, 125), (500, 118), (1000, 108), (float('inf'), 100)],

    # --- JOB FOCUSED & ASSESSMENTS ---
    "JFA Entry Level (General)": [(100, 21), (200, 20), (300, 18), (500, 17), (1000, 15), (float('inf'), 13)],
    "JFA Graduate / Technology Prof.": [(100, 22), (200, 15), (300, 20), (500, 18), (1000, 16), (float('inf'), 15)],
    "JFA Professionals": [(100, 73), (200, 68), (300, 62), (500, 56), (1000, 50), (float('inf'), 45)],
    "JFA Manager": [(100, 104), (200, 98), (300, 92), (500, 86), (1000, 81), (float('inf'), 75)],
    "Prueba de Integridad": [(100, 11), (200, 10), (300, 9), (500, 8), (1000, 8), (float('inf'), 7)],

    # --- VERIFY (HABILIDADES) ---
    "Verify Tradicional (Ability/Reasoning)": [(100, 21), (200, 20), (300, 18), (500, 16), (1000, 14), (float('inf'), 13)],
    "Verify Interactive (Gral)": [(100, 19), (200, 18), (300, 16), (500, 14), (1000, 12), (float('inf'), 11)],
    "Verify G+": [(100, 73), (200, 67), (300, 62), (500, 58), (1000, 53), (float('inf'), 47)],
    "Verify Interactive G+": [(100, 52), (200, 48), (300, 44), (500, 41), (1000, 38), (float('inf'), 33)],
    "Verify Ability to Work w/ Info": [(100, 15), (200, 14), (300, 13), (500, 12), (1000, 11), (float('inf'), 10)],
    
    # --- IDIOMAS Y TÉCNICOS ---
    "Written English / Spanish": [(100, 15), (200, 14), (300, 13), (500, 12), (1000, 11), (float('inf'), 10)],
    "SVAR (Spoken English)": [(100, 24), (200, 23), (300, 22), (500, 21), (1000, 19), (float('inf'), 17)],
    "WriteX (Email Writing)": [(100, 21), (200, 20), (300, 18), (500, 16), (1000, 14), (float('inf'), 13)],
    "WriteX (Essay Writing)": [(100, 21), (200, 20), (300, 18), (500, 16), (1000, 14), (float('inf'), 13)],
    "MS Office (Excel/Word/PPT)": [(100, 15), (200, 14), (300, 13), (500, 12), (1000, 11), (float('inf'), 10)],
    "Automata": [(100, 23), (200, 22), (300, 21), (500, 20), (1000, 18), (float('inf'), 16)],

    # --- 360 & SMART INTERVIEW ---
    "360 Assessment with OPQ": [(float('inf'), 420)],
    "360 Evaluation without OPQ": [(float('inf'), 210)],
    "Smart Interview Live / Coding": [(100, 24), (200, 23), (300, 22), (500, 21), (1000, 19), (float('inf'), 17)],
    "Smart Interview On Demand": [(100, 15), (200, 14), (300, 13), (500, 12), (1000, 11), (float('inf'), 10)],
}

# ==============================================================================
# 3. BASE DE DATOS DE SERVICIOS (TP US Alto / Medio / Bajo)
# ==============================================================================
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

    # 1. SELECCIÓN DE PAÍS
    with st.container():
        st.subheader("1. Configuración Regional")
        col_pais1, col_pais2, col_pais3 = st.columns([1, 2, 1])
        
        with col_pais1:
            pais_sel = st.selectbox("🌎 País del Proyecto", TODOS_LOS_PAISES, index=TODOS_LOS_PAISES.index("Chile") if "Chile" in TODOS_LOS_PAISES else 0)
        
        nivel = obtener_nivel_pais(pais_sel)
        
        with col_pais2:
            st.info(f"País **{pais_sel}** -> Tarifa Servicios: **TP US {nivel.upper()}**")

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
