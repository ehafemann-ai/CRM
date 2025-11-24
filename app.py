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
        st.subheader("
