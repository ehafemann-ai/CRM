import streamlit as st
import pandas as pd
import random
from datetime import datetime, timedelta

# --- CONFIGURACIÓN DE PÁGINA Y ESTILO ---
st.set_page_config(page_title="TalentPro System", layout="wide", page_icon="💼")

# CSS para ocultar marcas de agua y mejorar estilo
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stMetric {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        padding: 10px;
        border-radius: 5px;
    }
    </style>
""", unsafe_allow_html=True)

# --- BASE DE DATOS DE PRECIOS ---

# 1. PRUEBAS (Descuento por volumen)
DB_PRECIOS_PRUEBAS = {
    "OPQ (Personalidad)": [(50, 22.00), (100, 21.00), (200, 20.00), (300, 19.00), (500, 18.00), (float('inf'), 17.00)],
    "MQ (Motivación)": [(50, 17.00), (100, 17.00), (200, 16.00), (300, 15.00), (500, 14.00), (float('inf'), 13.00)],
    "Verify Interactive": [(50, 19.00), (100, 18.00), (200, 16.00), (300, 14.00), (500, 12.00), (float('inf'), 11.00)],
    "Smart Interview": [(50, 24.00), (100, 23.00), (200, 22.00), (300, 21.00), (float('inf'), 19.00)],
    "360 Assessment": [(float('inf'), 420.00)]
}

# 2. SERVICIOS (Tarifa por seniority)
DB_TARIFAS_SERVICIOS = {
    "Assessment Center": {"Angelica": 1500.0, "Senior": 1000.0, "BM": 800.0, "BP": 600.0},
    "Entrevista Competencias": {"Angelica": 300.0, "Senior": 150.0, "BM": 100.0, "BP": 80.0},
    "Feedback Individual": {"Angelica": 400.0, "Senior": 200.0, "BM": 150.0, "BP": 100.0},
    "Consultoría HR (Hora)": {"Angelica": 250.0, "Senior": 120.0, "BM": 90.0, "BP": 70.0}
}

# --- GESTIÓN DE ESTADO (MEMORIA) ---
if 'cotizaciones' not in st.session_state:
    st.session_state['cotizaciones'] = pd.DataFrame([
        {'id': 'TP-1001', 'fecha': '2024-11-01', 'empresa': 'Cliente Ejemplo', 'total': 1500, 'estado': 'Facturada', 'vendedor': 'Comercial 1'}
    ])
if 'carrito' not in st.session_state:
    st.session_state['carrito'] = []
if 'metas' not in st.session_state:
    st.session_state['metas'] = {'Comercial 1': 60000, 'Comercial 2': 45000}

# --- FUNCIONES AUXILIARES ---
def get_precio_prueba(nombre, cantidad):
    tramos = DB_PRECIOS_PRUEBAS.get(nombre, [])
    for limite, precio in tramos:
        if cantidad <= limite: return precio
    return 0.0

# --- MÓDULO: COTIZADOR PROFESIONAL ---
def cotizador():
    st.title("📝 Generador de Cotizaciones")
    st.markdown("---")

    # 1. DATOS DEL CLIENTE
    with st.container():
        st.subheader("1. Datos del Cliente")
        c1, c2, c3, c4 = st.columns(4)
        empresa = c1.text_input("Razón Social / Empresa")
        contacto = c2.text_input("Persona de Contacto")
        email = c3.text_input("Correo Electrónico")
        vendedor = c4.selectbox("Ejecutivo Responsable", ["Comercial 1", "Comercial 2", "Gerencia"])
        fecha = c1.date_input("Fecha de Emisión", datetime.now())

    st.markdown("---")

    # 2. AGREGADOR DE ÍTEMS (LA MEJORA CLAVE)
    st.subheader("2. Selección de Ítems")
    
    # Selector de tipo para limpiar la interfaz
    tipo_item = st.radio("¿Qué deseas agregar?", ["Licencia / Prueba (Volumen)", "Servicio Consultoría (Por Hora/Sesión)"], horizontal=True)

    col_input1, col_input2, col_input3, col_input4 = st.columns([3, 2, 2, 1])

    if "Prueba" in tipo_item:
        # Lógica para PRUEBAS
        with col_input1:
            item_sel = st.selectbox("Seleccionar Prueba", list(DB_PRECIOS_PRUEBAS.keys()))
        with col_input2:
            cantidad = st.number_input("Cantidad de Evaluaciones", min_value=1, value=10, step=1)
        with col_input3:
            # Cálculo en tiempo real
            precio_u = get_precio_prueba(item_sel, cantidad)
            st.metric("Precio Unitario (Tramo)", f"${precio_u:.2f}")
        with col_input4:
            st.write("Acción")
            if st.button("➕ Agregar", key="btn_add_prueba"):
                total_linea = precio_u * cantidad
                st.session_state['carrito'].append({
                    "Tipo": "Prueba",
                    "Descripción": item_sel,
                    "Detalle": f"Pack x{cantidad}",
                    "Cantidad": cantidad,
                    "Unitario": precio_u,
                    "Total": total_linea
                })
                st.rerun()

    else:
        # Lógica para SERVICIOS
        with col_input1:
            serv_sel = st.selectbox("Tipo de Servicio", list(DB_TARIFAS_SERVICIOS.keys()))
        with col_input2:
            nivel = st.selectbox("Seniority Consultor", ["Angelica", "Senior", "BM", "BP"])
            horas = st.number_input("N° Horas / Sesiones", min_value=1, value=1)
        with col_input3:
            tarifa = DB_TARIFAS_SERVICIOS[serv_sel].get(nivel, 0)
            st.metric("Tarifa por Hora", f"${tarifa:.2f}")
        with col_input4:
            st.write("Acción")
            if st.button("➕ Agregar", key="btn_add_serv"):
                total_linea = tarifa * horas
                st.session_state['carrito'].append({
                    "Tipo": "Servicio",
                    "Descripción": serv_sel,
                    "Detalle": f"Consultor: {nivel}",
                    "Cantidad": horas,
                    "Unitario": tarifa,
                    "Total": total_linea
                })
                st.rerun()

    # 3. TABLA RESUMEN (CARRITO)
    st.markdown("---")
    st.subheader("🛒 Detalle de la Cotización")

    if len(st.session_state['carrito']) > 0:
        # Convertir a DataFrame para mostrar bonito
        df_cart = pd.DataFrame(st.session_state['carrito'])
        
        # Mostrar tabla
        st.dataframe(
            df_cart,
            column_config={
                "Unitario": st.column_config.NumberColumn(format="$%.2f"),
                "Total": st.column_config.NumberColumn(format="$%.2f"),
            },
            use_container_width=True,
            hide_index=True
        )

        # Cálculos finales
        subtotal = df_cart['Total'].sum()
        
        col_res1, col_res2 = st.columns([3, 1])
        with col_res2:
            st.markdown("### Totales")
            admin_fee = st.checkbox("10% Fee Administrativo", value=False)
            banco_fee = 30.0
            descuento = st.number_input("Descuento ($)", min_value=0.0, value=0.0)

            val_admin = subtotal * 0.10 if admin_fee else 0.0
            total_final = subtotal + val_admin + banco_
