import streamlit as st
import pandas as pd
import random
from datetime import datetime, timedelta

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="TalentPro Cotizador", layout="wide", page_icon="📊")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stMetric {
        background-color: #f0f2f6;
        border: 1px solid #dce1e6;
        padding: 10px;
        border-radius: 5px;
    }
    </style>
""", unsafe_allow_html=True)

# --- 1. BASE DE DATOS COMPLETA (SEGÚN TU ARCHIVO EXCEL) ---
# Tramos: 1-100, 101-200, 201-300, 301-500, 501-1000, 1001+
# Precios extraídos de la columna "USD" de tu lista.

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
    
    # --- IDIOMAS Y TÉCNICOS ---
    "Written English / Spanish": [(100, 15), (200, 14), (300, 13), (500, 12), (1000, 11), (float('inf'), 10)],
    "SVAR (Spoken English)": [(100, 24), (200, 23), (300, 22), (500, 21), (1000, 19), (float('inf'), 17)],
    "WriteX (Email Writing)": [(100, 21), (200, 20), (300, 18), (500, 16), (1000, 14), (float('inf'), 13)],
    "MS Office (Excel/Word/PPT)": [(100, 15), (200, 14), (300, 13), (500, 12), (1000, 11), (float('inf'), 10)],
    "Automata": [(100, 23), (200, 22), (300, 21), (500, 20), (1000, 18), (float('inf'), 16)],

    # --- 360 & SMART INTERVIEW ---
    "360 Assessment with OPQ": [(float('inf'), 420)],
    "360 Evaluation without OPQ": [(float('inf'), 210)],
    "Smart Interview Live / Coding": [(100, 24), (200, 23), (300, 22), (500, 21), (1000, 19), (float('inf'), 17)],
    "Smart Interview On Demand": [(100, 15), (200, 14), (300, 13), (500, 12), (1000, 11), (float('inf'), 10)],
}

# --- 2. TARIFAS SERVICIOS (CONSULTORÍA) ---
# Columnas: Angelica, Senior, BM, BP (Precios referenciales, ¡Ajústalos si es necesario!)
DB_TARIFAS_SERVICIOS = {
    "Assessment Center (Jornada)": {
        "Angelica": 1500.0, "Senior": 1000.0, "BM": 800.0, "BP": 600.0
    },
    "Entrevista por Competencias": {
        "Angelica": 300.0, "Senior": 150.0, "BM": 100.0, "BP": 80.0
    },
    "Feedback Individual (1:1)": {
        "Angelica": 400.0, "Senior": 200.0, "BM": 150.0, "BP": 100.0
    },
    "Consultoría HR / Diseño (Hora)": {
        "Angelica": 250.0, "Senior": 120.0, "BM": 90.0, "BP": 70.0
    },
    "Levantamiento de Perfil": {
        "Angelica": 350.0, "Senior": 180.0, "BM": 120.0, "BP": 90.0
    },
    "Taller / Workshop (Sesión)": {
        "Angelica": 2000.0, "Senior": 1200.0, "BM": 900.0, "BP": 700.0
    }
}

# --- GESTIÓN DE MEMORIA ---
if 'cotizaciones' not in st.session_state:
    st.session_state['cotizaciones'] = pd.DataFrame([
        {'id': 'TP-1001', 'fecha': '2024-11-01', 'empresa': 'Cliente Demo', 'total': 1500, 'estado': 'Facturada', 'vendedor': 'Comercial 1'}
    ])
if 'carrito' not in st.session_state:
    st.session_state['carrito'] = []
if 'metas' not in st.session_state:
    st.session_state['metas'] = {'Comercial 1': 60000, 'Comercial 2': 45000}

# --- FUNCIONES ---
def get_precio_prueba(nombre, cantidad):
    tramos = DB_PRECIOS_PRUEBAS.get(nombre, [])
    for limite, precio in tramos:
        if cantidad <= limite:
            return precio
    return 0.0

# --- PANTALLA 1: COTIZADOR ---
def cotizador():
    st.title("📝 Cotizador TalentPro")
    st.markdown("---")

    # DATOS CLIENTE
    with st.container():
        st.subheader("1. Datos Generales")
        c1, c2, c3, c4 = st.columns(4)
        empresa = c1.text_input("Empresa")
        contacto = c2.text_input("Contacto")
        email = c3.text_input("Email")
        vendedor = c4.selectbox("Ejecutivo", ["Comercial 1", "Comercial 2", "Gerencia"])
        fecha = c1.date_input("Fecha", datetime.now())

    st.markdown("---")

    # SELECCIÓN
    st.subheader("2. Selección de Productos/Servicios")
    
    tipo = st.radio("Categoría:", ["Evaluaciones y Licencias", "Servicios de Consultoría"], horizontal=True)

    col1, col2, col3, col4 = st.columns([3, 2, 2, 1])

    if "Evaluaciones" in tipo:
        with col1:
            sel_prueba = st.selectbox("Producto", list(DB_PRECIOS_PRUEBAS.keys()))
        with col2:
            cantidad = st.number_input("Cantidad", min_value=1, value=10)
        with col3:
            unitario = get_precio_prueba(sel_prueba, cantidad)
            st.metric("Precio Unitario", f"${unitario:.2f}")
            st.caption(f"Tramo automático según volumen")
        with col4:
            st.write("Acción")
            if st.button("➕ Agregar", key="add_p"):
                total = unitario * cantidad
                st.session_state['carrito'].append({
                    "Tipo": "Prueba",
                    "Detalle": sel_prueba,
                    "Info": f"Cant: {cantidad}",
                    "Unitario": unitario,
                    "Total": total
                })
                st.rerun()

    else:
        with col1:
            sel_serv = st.selectbox("Servicio", list(DB_TARIFAS_SERVICIOS.keys()))
        with col2:
            rol = st.selectbox("Tarifa / Rol", ["Angelica", "Senior", "BM", "BP"])
            horas = st.number_input("Cantidad (Horas/Sesiones)", min_value=1, value=1)
        with col3:
            tarifa = DB_TARIFAS_SERVICIOS[sel_serv].get(rol, 0)
            st.metric("Tarifa", f"${tarifa:.2f}")
        with col4:
            st.write("Acción")
            if st.button("➕ Agregar", key="add_s"):
                total = tarifa * horas
                st.session_state['carrito'].append({
                    "Tipo": "Servicio",
                    "Detalle": sel_serv,
                    "Info": f"Rol: {rol} ({horas}u)",
                    "Unitario": tarifa,
                    "Total": total
                })
                st.rerun()

    # RESUMEN
    if st.session_state['carrito']:
        st.markdown("---")
        st.subheader("🛒 Detalle Cotización")
        
        df_cart = pd.DataFrame(st.session_state['carrito'])
        st.dataframe(df_cart, use_container_width=True, hide_index=True)

        subtotal = df_cart['Total'].sum()
        
        c_tot1, c_tot2 = st.columns([3, 1])
        with c_tot2:
            st.markdown("### Totales")
            fee_admin = st.checkbox("10% Fee Admin", value=False)
            banco = 30.0
            desc = st.number_input("Descuento ($)", 0.0)
            
            val_fee = subtotal * 0.10 if fee_admin else 0
            final = subtotal + val_fee + banco - desc
            
            st.markdown(f"""
            | Concepto | Valor |
            | :--- | ---: |
            | **Subtotal** | **${subtotal:,.2f}** |
            | Fee 10% | ${val_fee:,.2f} |
            | Banco | ${banco:,.2f} |
            | Descuento | -${desc:,.2f} |
            | **TOTAL** | **${final:,.2f}** |
            """)
            
            if st.button("💾 GUARDAR", type="primary"):
                if not empresa:
                    st.error("Falta nombre empresa")
                else:
                    new_id = f"TP-{random.randint(1000,9999)}"
                    reg = {
                        'id': new_id, 'fecha': fecha.strftime("%Y-%m-%d"),
                        'empresa': empresa, 'total': final,
                        'estado': 'Enviada', 'vendedor': vendedor
                    }
                    st.session_state['cotizaciones'] = pd.concat([st.session_state['cotizaciones'], pd.DataFrame([reg])], ignore_index=True)
                    st.session_state['carrito'] = []
                    st.success(f"Creada: {new_id}")
                    st.balloons()
        
        with c_tot1:
            if st.button("Limpiar Carrito"):
                st.session_state['carrito'] = []
                st.rerun()

# --- PANTALLA 2: DASHBOARD ---
def dashboard():
    st.title("📊 Tablero de Control")
    df = st.session_state['cotizaciones']
    df['fecha'] = pd.to_datetime(df['fecha'])
    
    k1, k2, k3 = st.columns(3)
    vendido = df[df['estado'].isin(['Facturada', 'Pagada'])]['total'].sum()
    pipeline = df[df['estado'].isin(['Enviada', 'Aprobada'])]['total'].sum()
    
    k1.metric("Ventas (Facturado)", f"${vendido:,.0f}")
    k2.metric("Pipeline", f"${pipeline:,.0f}")
    k3.metric("N° Cotizaciones", len(df))
    
    st.markdown("---")
    
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Metas Comerciales")
        ventas_vend = df[df['estado'].isin(['Facturada', 'Pagada'])].groupby('vendedor')['total'].sum()
        for v, meta in st.session_state['metas'].items():
            real = ventas_vend.get(v, 0)
            st.write(f"**{v}**: ${real:,.0f} / ${meta:,.0f}")
            st.progress(min(real/meta, 1.0))
            
    with c2:
        st.subheader("Clientes Inactivos (>1 año)")
        hoy = datetime.now()
        alerta = False
        for emp in df['empresa'].unique():
            fechas = df[df['empresa'] == emp]['fecha']
            if fechas.max() < (hoy - timedelta(days=365)):
                st.error(f"⚠️ {emp} (Última: {fechas.max().date()})")
                alerta = True
        if not alerta:
            st.success("Toda la cartera está activa.")

# --- PANTALLA 3: FINANZAS ---
def finanzas():
    st.title("💰 Finanzas")
    st.info("Gestiona los estados de pago aquí.")
    
    df = st.session_state['cotizaciones']
    
    edited_df = st.data_editor(
        df,
        column_config={
            "estado": st.column_config.SelectboxColumn("Estado", options=["Enviada", "Aprobada", "Facturada", "Pagada", "Rechazada"]),
            "total": st.column_config.NumberColumn(format="$%d")
        },
        disabled=["id", "empresa", "vendedor"],
        hide_index=True,
        use_container_width=True
    )
    
    if not edited_df.equals(df):
        st.session_state['cotizaciones'] = edited_df
        st.toast("Actualizado")

# --- MENÚ ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=100)
    st.title("TalentPro App")
    opcion = st.radio("Ir a:", ["Cotizador", "Dashboard", "Finanzas"])

if opcion == "Cotizador":
    cotizador()
elif opcion == "Dashboard":
    dashboard()
elif opcion == "Finanzas":
    finanzas()
