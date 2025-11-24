import streamlit as st
import pandas as pd
import random
import requests
from datetime import datetime
from fpdf import FPDF
import base64

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="TalentPro Global", layout="wide", page_icon="🌎")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stMetric {background-color: #f8f9fa; border: 1px solid #dee2e6; padding: 10px; border-radius: 5px;}
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 1. TRADUCCIONES Y ENTIDADES (ESTÁTICO)
# ==============================================================================
TEXTOS = {
    "ES": {
        "title": "Cotizador TalentPro", "client": "Datos Cliente", "items": "Selección",
        "add": "Agregar", "desc": "Descripción", "qty": "Cant", "unit": "Unitario", "total": "Total",
        "subtotal": "Subtotal", "fee": "Fee Admin (10%)", "tax": "Impuestos", "discount": "Descuento",
        "grand_total": "TOTAL A PAGAR", "download": "Descargar PDF", "invoice_to": "Facturar a",
        "quote": "COTIZACIÓN", "date": "Fecha", "validity": "Validez: 30 días"
    },
    "EN": {
        "title": "TalentPro Quote Tool", "client": "Client Details", "items": "Selection",
        "add": "Add", "desc": "Description", "qty": "Qty", "unit": "Unit Price", "total": "Total",
        "subtotal": "Subtotal", "fee": "Admin Fee (10%)", "tax": "Taxes", "discount": "Discount",
        "grand_total": "GRAND TOTAL", "download": "Download PDF", "invoice_to": "Bill to",
        "quote": "QUOTATION", "date": "Date", "validity": "Validity: 30 days"
    },
    "PT": {
        "title": "Cotação TalentPro", "client": "Dados do Cliente", "items": "Seleção",
        "add": "Adicionar", "desc": "Descrição", "qty": "Qtd", "unit": "Unitário", "total": "Total",
        "subtotal": "Subtotal", "fee": "Taxa Admin (10%)", "tax": "Impostos", "discount": "Desconto",
        "grand_total": "TOTAL A PAGAR", "download": "Baixar PDF", "invoice_to": "Faturar para",
        "quote": "COTAÇÃO", "date": "Data", "validity": "Validade: 30 dias"
    }
}

EMPRESAS = {
    "Brasil": {
        "Nombre": "TalentPRO Brasil Consutoria Ltda.",
        "ID": "CNPJ: 49.704.046/0001-80",
        "Dir": "Av. Marcos Penteado de Ulhoa Rodriguez 939, Andar 8, Tamboré",
        "Giro": "Consultoria em gestão empresarial"
    },
    "Peru": {
        "Nombre": "TALENTPRO SOCIEDAD ANÓNIMA CERRADA",
        "ID": "DNI 25489763",
        "Dir": "AVENIDA EL DERBY 254, SANTIAGO DE SURCO, LIMA, PERÚ",
        "Giro": "Servicios de apoyo a las empresas"
    },
    "Chile_Pruebas": {
        "Nombre": "TALENT PRO SPA",
        "ID": "RUT: 76.743.976-8",
        "Dir": "Juan de Valiente 3630, oficina 501, Vitacura, Santiago, Chile",
        "Giro": "Servicios de Reclutamiento y Selección"
    },
    "Chile_Servicios": {
        "Nombre": "TALENTPRO SERVICIOS PROFESIONALES LTDA.",
        "ID": "RUT: 77.704.757-4",
        "Dir": "Juan de Valiente 3630, oficina 501, Vitacura, Santiago, Chile",
        "Giro": "Asesoría en Recursos Humanos"
    },
    "Latam": {
        "Nombre": "TALENTPRO LATAM, S.A.",
        "ID": "RUC: 155723672-2-2022 DV 27",
        "Dir": "CALLE 50, PH GLOBAL PLAZA, OFICINA 6D, BELLA VISTA, PANAMÁ",
        "Giro": "Talent Acquisition Services"
    }
}

# --- 2. CARGA DE DATOS (EXCEL) ---
@st.cache_data(ttl=60)
def cargar_datos():
    try:
        xls = pd.ExcelFile('precios.xlsx')
        # Intentamos cargar las hojas con nombres correctos
        df_p_usd = pd.read_excel(xls, 'Pruebas Int')
        df_s_usd = pd.read_excel(xls, 'Servicios Int')
        df_config = pd.read_excel(xls, 'Config')
        
        # Cargas opcionales (locales)
        df_p_cl = pd.read_excel(xls, 'Pruebas_CL') if 'Pruebas_CL' in xls.sheet_names else pd.DataFrame()
        df_s_cl = pd.read_excel(xls, 'Servicios_CL') if 'Servicios_CL' in xls.sheet_names else pd.DataFrame()
        df_p_br = pd.read_excel(xls, 'Pruebas_BR') if 'Pruebas_BR' in xls.sheet_names else pd.DataFrame()
        df_s_br = pd.read_excel(xls, 'Servicios_BR') if 'Servicios_BR' in xls.sheet_names else pd.DataFrame()

        return df_p_usd, df_s_usd, df_config, df_p_cl, df_s_cl, df_p_br, df_s_br
    except FileNotFoundError:
        return None, None, None, None, None, None, None
    except Exception as e:
        st.error(f"Error leyendo Excel: {e}")
        return None, None, None, None, None, None, None

# Cargar y verificar
data = cargar_datos()
if data[0] is None:
    st.error("⚠️ Error crítico: No se pudo leer 'precios.xlsx'. Revisa que esté en GitHub y tenga las hojas correctas.")
    st.stop()

df_p_usd, df_s_usd, df_config, df_p_cl, df_s_cl, df_p_br, df_s_br = data

# --- CONSTRUIR LISTA DE PAÍSES DESDE EL EXCEL ---
if not df_config.empty and 'Pais' in df_config.columns:
    TODOS_LOS_PAISES = sorted(df_config['Pais'].unique().tolist())
else:
    st.error("⚠️ La hoja 'Config' del Excel está vacía o no tiene la columna 'Pais'.")
    TODOS_LOS_PAISES = ["Chile", "Brasil"] # Fallback

# --- 3. APIS INDICADORES ---
@st.cache_data(ttl=3600)
def obtener_indicadores():
    tasas = {"UF": 38000, "USD_CLP": 980, "USD_BRL": 5.8, "Status": "Offline"}
    try:
        r_cl = requests.get('https://mindicador.cl/api', timeout=5).json()
        tasas['UF'] = r_cl['uf']['valor']
        tasas['USD_CLP'] = r_cl['dolar']['valor']
        r_br = requests.get('https://open.er-api.com/v6/latest/USD', timeout=5).json()
        tasas['USD_BRL'] = r_br['rates']['BRL']
        tasas['Status'] = "Online"
    except: pass
    return tasas

TASAS_DIA = obtener_indicadores()

# --- LÓGICA DE NEGOCIO ---
def obtener_contexto_pais(pais):
    if pais == "Chile": 
        return {"moneda": "UF", "df_p": df_p_cl, "df_s": df_s_cl, "tipo": "Local"}
    elif pais in ["Brasil", "Brazil"]: 
        return {"moneda": "R$", "df_p": df_p_br, "df_s": df_s_br, "tipo": "Local"}
    else:
        # Busca el nivel en el dataframe de Config cargado del Excel
        fila = df_config[df_config['Pais'] == pais]
        nivel = fila.iloc[0]['Nivel'] if not fila.empty else "Medio"
        return {"moneda": "US$", "df_p": df_p_usd, "df_s": df_s_usd, "tipo": "Internacional", "nivel": nivel}

def determinar_empresa_facturadora(pais, items_carrito):
    if pais == "Brasil": return EMPRESAS["Brasil"]
    if pais in ["Perú", "Peru"]: return EMPRESAS["Peru"]
    if pais == "Chile":
        hay_pruebas = any(item['Ítem'] == 'Evaluación' for item in items_carrito)
        return EMPRESAS["Chile_Pruebas"] if hay_pruebas else EMPRESAS["Chile_Servicios"]
    return EMPRESAS["Latam"]

def calcular_impuestos(pais, subtotal, total_pruebas):
    nombre, monto = "", 0.0
    if pais == "Chile":
        nombre = "IVA (19% s/Pruebas)"
        monto = total_pruebas * 0.19
    elif pais in ["Panamá", "Panama"]:
        nombre = "ITBMS (7%)"
        monto = subtotal * 0.07
    elif pais == "Honduras":
        nombre = "Retención (11.11%)"
        monto = subtotal * 0.1111
    return nombre, monto

# --- GENERADOR PDF ---
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 14)
        self.set_text_color(0, 51, 102) # Azul oscuro
        self.cell(0, 10, 'TALENTPRO', 0, 1, 'L')
        self.ln(5)

def generar_pdf(empresa_emisora, cliente, items, calculos, idioma):
    pdf = PDF()
    pdf.add_page()
    t = TEXTOS[idioma]
    
    # Datos Emisor
    pdf.set_font("Arial", 'B', 10)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 5, empresa_emisora['Nombre'], 0, 1)
    pdf.set_font("Arial", '', 9)
    pdf.cell(0, 5, empresa_emisora['ID'], 0, 1)
    pdf.multi_cell(0, 5, empresa_emisora['Dir']) # Multicell para direcciones largas
    pdf.cell(0, 5, empresa_emisora['Giro'], 0, 1)
    pdf.ln(8)
    
    # Datos Cliente
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 6, f"{t['invoice_to']}", 0, 1, 'L', 1)
    pdf.ln(2)
    pdf.set_font("Arial", '', 9)
    pdf.cell(0, 5, f"{t['client']}: {cliente['empresa']}", 0, 1)
    pdf.cell(0, 5, f"At: {cliente['contacto']} ({cliente['email']})", 0, 1)
    pdf.cell(0, 5, f"{t['date']}: {datetime.now().strftime('%d/%m/%Y')}", 0, 1)
    pdf.ln(8)
    
    # Tabla
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(100, 8, t['desc'], 1, 0, 'L', 1)
    pdf.cell(20, 8, t['qty'], 1, 0, 'C', 1)
    pdf.cell(30, 8, t['unit'], 1, 0, 'R', 1)
    pdf.cell(40, 8, t['total'], 1, 1, 'R', 1)
    
    pdf.set_font("Arial", '', 8)
