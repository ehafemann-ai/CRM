import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import random

# --- CONFIGURACIÓN DE TU EMPRESA ---
# AQUÍ PUEDES CAMBIAR LOS PRECIOS TÚ MISMO SIEMPRE QUE QUIERAS

# 1. PRECIOS DE PRUEBAS (Software)
# Formato: Si compra hasta X cantidad, el precio es Y.
# El último precio (float('inf')) es para cantidades mayores al último tramo.
DB_PRECIOS_PRUEBAS = {
    "OPQ": [
        (50, 22.00), (100, 21.00), (200, 20.00), (300, 19.00), (500, 18.00), (float('inf'), 17.00)
    ],
    "MQ": [
        (50, 17.00), (100, 17.00), (200, 16.00), (300, 15.00), (500, 14.00), (float('inf'), 13.00)
    ],
    "CCSQ": [
        (50, 17.00), (100, 17.00), (200, 16.00), (300, 15.00), (500, 14.00), (float('inf'), 13.00)
    ],
    "Verify Interactive": [
        (50, 19.00), (100, 18.00), (200, 16.00), (300, 14.00), (500, 12.00), (float('inf'), 11.00)
    ],
    "Smart Interview": [
        (50, 24.00), (100, 23.00), (200, 22.00), (300, 21.00), (float('inf'), 19.00)
    ]
}

# 2. PRECIOS DE SERVICIOS (Consultoría)
# Aquí están las columnas: Angelica, Senior, BM, BP
DB_TARIFAS_SERVICIOS = {
    "Assessment Center (Jornada)": {
        "Angelica": 1500.00, "Senior": 1000.00, "BM": 800.00, "BP": 600.00
    },
    "Entrevista por Competencias": {
        "Angelica": 300.00, "Senior": 150.00, "BM": 100.00, "BP": 80.00
    },
    "Feedback Individual": {
        "Angelica": 400.00, "Senior": 200.00, "BM": 150.00, "BP": 100.00
    },
    "Consultoría HR (Hora)": {
        "Angelica": 250.00, "Senior": 120.00, "BM": 90.00, "BP": 70.00
    }
}
# ---------------------------------------------------------

st.set_page_config(page_title="TalentPro Cotizador", layout="wide")

# Inicializar memoria temporal
if 'cotizaciones' not in st.session_state:
    st.session_state['cotizaciones'] = pd.DataFrame([
        {'id': 'TP-101', 'fecha': '2024-10-01', 'empresa': 'Cliente A', 'total': 5000, 'estado': 'Facturada', 'vendedor': 'Comercial 1'},
        {'id': 'TP-102', 'fecha': datetime.now().strftime("%Y-%m-%d"), 'empresa': 'Cliente B', 'total': 1200, 'estado': 'Enviada', 'vendedor': 'Comercial 2'}
    ])
if 'carrito' not in st.session_state: st.session_state['carrito'] = []
if 'metas' not in st.session_state: st.session_state['metas'] = {'Comercial 1': 50000, 'Comercial 2': 40000}

def get_precio_prueba(nombre, cantidad):
    tramos = DB_PRECIOS_PRUEBAS.get(nombre, [])
    for limite, precio in tramos:
        if cantidad <= limite: return precio
    return 0.0

# --- PANTALLAS ---
def cotizador():
    st.title("📝 Crear Cotización")
    c1, c2, c3, c4 = st.columns(4)
    empresa = c1.text_input("Empresa")
    contacto = c2.text_input("Contacto")
    email = c3.text_input("Email")
    vend = c4.selectbox("Vendedor", ["Comercial 1", "Comercial 2", "Gerencia"])
    
    tab1, tab2 = st.tabs(["Pruebas (Volumen)", "Servicios (Consultor)"])
    
    with tab1:
        cc1, cc2, cc3 = st.columns([3,1,1])
        p_sel = cc1.selectbox("Prueba", list(DB_PRECIOS_PRUEBAS.keys()))
        cant = cc2.number_input("Cantidad", 1, 10000, 10)
        unit = get_precio_prueba(p_sel, cant)
        cc3.metric("Precio Unit", f"${unit}")
        if cc3.button("Agregar Prueba"):
            st.session_state['carrito'].append({"Desc": p_sel, "Detalle": f"{cant} un.", "Total": unit*cant})

    with tab2:
        cs1, cs2, cs3 = st.columns([2,2,1])
        s_sel = cs1.selectbox("Servicio", list(DB_TARIFAS_SERVICIOS.keys()))
        rol = cs2.selectbox("Consultor", ["Angelica", "Senior", "BM", "BP"])
        horas = cs3.number_input("Horas/Sesiones", 1, 100, 1)
        tarifa = DB_TARIFAS_SERVICIOS[s_sel].get(rol, 0)
        cs3.metric("Tarifa", f"${tarifa}")
        if cs3.button("Agregar Servicio"):
            st.session_state['carrito'].append({"Desc": s_sel, "Detalle": f"{rol} ({horas}h)", "Total": tarifa*horas})

    if st.session_state['carrito']:
        st.write("---")
        df_c = pd.DataFrame(st.session_state['carrito'])
        st.dataframe(df_c, use_container_width=True)
        total = df_c['Total'].sum() + 30 # +30 banco
        st.subheader(f"Total (+30 banco): ${total:,.2f}")
        if st.button("Guardar Cotización", type="primary"):
            nuevo = {'id': f"TP-{random.randint(100,999)}", 'fecha': datetime.now().strftime("%Y-%m-%d"), 
                     'empresa': empresa, 'total': total, 'estado': 'Enviada', 'vendedor': vend}
            st.session_state['cotizaciones'] = pd.concat([st.session_state['cotizaciones'], pd.DataFrame([nuevo])], ignore_index=True)
            st.session_state['carrito'] = []
            st.success("Guardado!")

def finanzas():
    st.title("💰 Finanzas")
    st.info("Cambia el estado de las cotizaciones aquí.")
    df = st.session_state['cotizaciones']
    edited = st.data_editor(df, column_config={"estado": st.column_config.SelectboxColumn("Estado", options=["Enviada", "Facturada", "Pagada"])}, use_container_width=True)
    if not edited.equals(df): st.session_state['cotizaciones'] = edited

def dashboard():
    st.title("📊 Dashboard")
    df = st.session_state['cotizaciones']
    fact = df[df['estado'].isin(['Facturada', 'Pagada'])]['total'].sum()
    st.metric("Total Facturado", f"${fact:,.0f}")
    
    # Metas
    ventas = df[df['estado'].isin(['Facturada', 'Pagada'])].groupby('vendedor')['total'].sum()
    for v, meta in st.session_state['metas'].items():
        st.progress(min(ventas.get(v,0)/meta, 1.0), text=f"Meta {v}: ${ventas.get(v,0):,.0f} / ${meta:,.0f}")

    # Clientes Inactivos
    st.write("---")
    st.subheader("Clientes Inactivos (>1 año)")
    hoy = datetime.now()
    for emp in df['empresa'].unique():
        fechas = pd.to_datetime(df[df['empresa']==emp]['fecha'])
        if fechas.max() < (hoy - timedelta(days=365)):
            st.error(f"⚠️ {emp} - Última compra: {fechas.max().date()}")

menu = st.sidebar.radio("Ir a:", ["Cotizador", "Finanzas", "Dashboard"])
if menu == "Cotizador": cotizador()
elif menu == "Finanzas": finanzas()
elif menu == "Dashboard": dashboard()
