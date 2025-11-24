import streamlit as st
import pandas as pd
import random
from datetime import datetime, timedelta

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="TalentPro Cotizador", layout="wide", page_icon="📊")

# Estilos CSS para que se vea limpio
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

# --- 1. BASE DE DATOS DE PRECIOS (TRANSCRITA DE TU IMAGEN) ---
# Tramos: 1-100, 101-200, 201-300, 301-500, 501-1000, 1001+
DB_PRECIOS_PRUEBAS = {
    "OPQ (Individual)": [
        (100, 22.00), (200, 21.00), (300, 20.00), (500, 19.00), (1000, 18.00), (float('inf'), 17.00)
    ],
    "MQ (Individual)": [
        (100, 17.00), (200, 17.00), (300, 16.00), (500, 15.00), (1000, 14.00), (float('inf'), 13.00)
    ],
    "CCSQ (Individual)": [
        (100, 17.00), (200, 17.00), (300, 16.00), (500, 15.00), (1000, 14.00), (float('inf'), 13.00)
    ],
    "OPQ + OPQ Profile Report": [
        (100, 29.00), (200, 28.00), (300, 27.00), (500, 26.00), (1000, 25.00), (float('inf'), 24.00)
    ],
    "OPQ + Universal Competences Report (LA)": [
        (100, 49.00), (200, 45.00), (300, 39.00), (500, 37.00), (1000, 35.00), (float('inf'), 32.00)
    ],
    "OPQ + Universal Competences Report (Intl)": [
        (100, 93.00), (200, 85.00), (300, 78.00), (500, 72.00), (1000, 66.00), (float('inf'), 60.00)
    ],
    "OPQ + Person-Job Match Report (LA)": [
        (100, 74.00), (200, 68.00), (300, 62.00), (500, 56.00), (1000, 50.00), (float('inf'), 45.00)
    ],
    "OPQ + Development Action Planner (LA)": [
        (100, 65.00), (200, 61.00), (300, 57.00), (500, 52.00), (1000, 48.00), (float('inf'), 43.00)
    ],
    "OPQ + Digital Readiness Report": [
        (100, 39.00), (200, 35.00), (300, 33.00), (500, 32.00), (1000, 31.00), (float('inf'), 30.00)
    ],
    "OPQ + Candidate Report": [
        (100, 72.00), (200, 68.00), (300, 64.00), (500, 59.00), (1000, 55.00), (float('inf'), 50.00)
    ],
    "OPQ + Emotional Intelligence Report": [
        (100, 63.00), (200, 59.00), (300, 56.00), (500, 52.00), (1000, 49.00), (float('inf'), 45.00)
    ],
    "OPQ + Manager Plus Report": [
        (100, 104.00), (200, 97.00), (300, 90.00), (500, 85.00), (1000, 79.00), (float('inf'), 74.00)
    ],
    "OPQ + Leadership Report": [
        (100, 254.00), (200, 242.00), (300, 237.00), (500, 223.00), (1000, 215.00), (float('inf'), 195.00)
    ],
    "MQ + MQ Profile Report": [
        (100, 31.00), (200, 29.00), (300, 27.00), (500, 25.00), (1000, 22.00), (float('inf'), 20.00)
    ]
}

# --- 2. TARIFAS SERVICIOS (CONSULTORÍA) ---
DB_TARIFAS_SERVICIOS = {
    "Assessment Center (Jornada)": {"Angelica": 1500.0, "Senior": 1000.0, "BM": 800.0, "BP": 600.0},
    "Entrevista por Competencias": {"Angelica": 300.0, "Senior": 150.0, "BM": 100.0, "BP": 80.0},
    "Feedback Individual": {"Angelica": 400.0, "Senior": 200.0, "BM": 150.0, "BP": 100.0},
    "Consultoría HR (Hora)": {"Angelica": 250.0, "Senior": 120.0, "BM": 90.0, "BP": 70.0}
}

# --- GESTIÓN DE MEMORIA (STATE) ---
if 'cotizaciones' not in st.session_state:
    st.session_state['cotizaciones'] = pd.DataFrame([
        {'id': 'TP-1001', 'fecha': '2024-11-01', 'empresa': 'Cliente Prueba', 'total': 1500, 'estado': 'Facturada', 'vendedor': 'Comercial 1'}
    ])
if 'carrito' not in st.session_state:
    st.session_state['carrito'] = []
if 'metas' not in st.session_state:
    st.session_state['metas'] = {'Comercial 1': 60000, 'Comercial 2': 45000}

# --- FUNCIÓN: BUSCAR PRECIO POR TRAMO ---
def get_precio_prueba(nombre, cantidad):
    tramos = DB_PRECIOS_PRUEBAS.get(nombre, [])
    for limite, precio in tramos:
        if cantidad <= limite:
            return precio
    return 0.0

# --- PANTALLA: COTIZADOR ---
def cotizador():
    st.title("📝 Generador de Cotizaciones")
    st.markdown("---")

    # DATOS CLIENTE
    with st.container():
        st.subheader("1. Información del Cliente")
        c1, c2, c3, c4 = st.columns(4)
        empresa = c1.text_input("Empresa / Razón Social")
        contacto = c2.text_input("Nombre Contacto")
        email = c3.text_input("Email")
        vendedor = c4.selectbox("Comercial", ["Comercial 1", "Comercial 2", "Gerencia"])
        fecha = c1.date_input("Fecha", datetime.now())

    st.markdown("---")

    # SELECCIÓN DE ÍTEMS
    st.subheader("2. Selección de Productos")
    
    tipo = st.radio("Tipo de Ítem:", ["Pruebas (Volumen)", "Servicios (Consultoría)"], horizontal=True)

    col1, col2, col3, col4 = st.columns([3, 2, 2, 1])

    if "Pruebas" in tipo:
        with col1:
            sel_prueba = st.selectbox("Producto (Columna B)", list(DB_PRECIOS_PRUEBAS.keys()))
        with col2:
            cantidad = st.number_input("Cantidad", min_value=1, value=10)
        with col3:
            unitario = get_precio_prueba(sel_prueba, cantidad)
            st.metric("Precio Unitario", f"${unitario:.2f}")
            st.caption(f"Según tramo (ej. 1-100, 101-200...)")
        with col4:
            st.write("Acción")
            if st.button("➕ Agregar", key="add_prueba"):
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
            rol = st.selectbox("Nivel Consultor", ["Angelica", "Senior", "BM", "BP"])
            horas = st.number_input("Horas/Sesiones", min_value=1, value=1)
        with col3:
            tarifa = DB_TARIFAS_SERVICIOS[sel_serv].get(rol, 0)
            st.metric("Tarifa", f"${tarifa:.2f}")
        with col4:
            st.write("Acción")
            if st.button("➕ Agregar", key="add_serv"):
                total = tarifa * horas
                st.session_state['carrito'].append({
                    "Tipo": "Servicio",
                    "Detalle": sel_serv,
                    "Info": f"Consultor: {rol} ({horas}h)",
                    "Unitario": tarifa,
                    "Total": total
                })
                st.rerun()

    # CARRITO Y TOTALES
    if st.session_state['carrito']:
        st.markdown("---")
        st.subheader("🛒 Detalle")
        
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
            
            if st.button("💾 GUARDAR COTIZACIÓN", type="primary"):
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
                    st.success(f"Guardada: {new_id}")
                    st.balloons()
        
        with c_tot1:
            if st.button("Limpiar Carrito"):
                st.session_state['carrito'] = []
                st.rerun()

# --- PANTALLA: DASHBOARD ---
def dashboard():
    st.title("📊 Tablero de Control")
    df = st.session_state['cotizaciones']
    df['fecha'] = pd.to_datetime(df['fecha'])
    
    # KPIs
    k1, k2, k3 = st.columns(3)
    vendido = df[df['estado'].isin(['Facturada', 'Pagada'])]['total'].sum()
    pipeline = df[df['estado'].isin(['Enviada', 'Aprobada'])]['total'].sum()
    
    k1.metric("Ventas Cerradas", f"${vendido:,.0f}")
    k2.metric("Pipeline", f"${pipeline:,.0f}")
    k3.metric("Cotizaciones", len(df))
    
    st.markdown("---")
    
    # Gráficos
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("Avance de Metas")
        ventas_vend = df[df['estado'].isin(['Facturada', 'Pagada'])].groupby('vendedor')['total'].sum()
        for v, meta in st.session_state['metas'].items():
            real = ventas_vend.get(v, 0)
            st.write(f"**{v}**: ${real:,.0f} / ${meta:,.0f}")
            st.progress(min(real/meta, 1.0))
            
    with c2:
        st.subheader("Clientes Inactivos (>1 año)")
        hoy = datetime.now()
        for emp in df['empresa'].unique():
            fechas = df[df['empresa'] == emp]['fecha']
            if fechas.max() < (hoy - timedelta(days=365)):
                st.error(f"⚠️ {emp} (Última: {fechas.max().date()})")

# --- PANTALLA: FINANZAS ---
def finanzas():
    st.title("💰 Finanzas")
    st.info("Doble clic en 'Estado' para actualizar.")
    
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
        st.toast("Cambios guardados")

# --- MENÚ PRINCIPAL ---
with st.sidebar:
    st.title("TalentPro App")
    opcion = st.radio("Menú", ["Cotizador", "Dashboard", "Finanzas"])

if opcion == "Cotizador":
    cotizador()
elif opcion == "Dashboard":
    dashboard()
elif opcion == "Finanzas":
    finanzas()
