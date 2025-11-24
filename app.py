import streamlit as st
import pandas as pd
import random
import requests
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="TalentPro System", layout="wide", page_icon="🌎")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stMetric {background-color: #f8f9fa; border: 1px solid #dee2e6; padding: 10px; border-radius: 5px;}
    </style>
""", unsafe_allow_html=True)

# --- 1. OBTENER INDICADORES (API) ---
@st.cache_data(ttl=3600)
def obtener_indicadores():
    tasas = {"UF": 38000, "USD_CLP": 980, "USD_BRL": 5.8, "Status": "Offline"}
    try:
        # Chile
        resp_cl = requests.get('https://mindicador.cl/api').json()
        tasas['UF'] = resp_cl['uf']['valor']
        tasas['USD_CLP'] = resp_cl['dolar']['valor']
        # Brasil
        resp_br = requests.get('https://open.er-api.com/v6/latest/USD').json()
        tasas['USD_BRL'] = resp_br['rates']['BRL']
        tasas['Status'] = "Online"
    except:
        pass
    return tasas

TASAS_DIA = obtener_indicadores()

# --- 2. CARGAR EXCEL (CON TUS NOMBRES EXACTOS) ---
@st.cache_data(ttl=60)
def cargar_datos():
    try:
        xls = pd.ExcelFile('precios.xlsx')
        
        # AQUI ESTA EL CAMBIO DE NOMBRES DE PESTAÑAS
        df_p_usd = pd.read_excel(xls, 'Pruebas Int')     # Antes 'Pruebas'
        df_s_usd = pd.read_excel(xls, 'Servicios Int')   # Antes 'Servicios'
        df_config = pd.read_excel(xls, 'Config')
        
        try: df_p_cl = pd.read_excel(xls, 'Pruebas_CL')
        except: df_p_cl = pd.DataFrame()
        try: df_s_cl = pd.read_excel(xls, 'Servicios_CL')
        except: df_s_cl = pd.DataFrame()
        try: df_p_br = pd.read_excel(xls, 'Pruebas_BR')
        except: df_p_br = pd.DataFrame()
        try: df_s_br = pd.read_excel(xls, 'Servicios_BR')
        except: df_s_br = pd.DataFrame()

        return df_p_usd, df_s_usd, df_config, df_p_cl, df_s_cl, df_p_br, df_s_br
    except FileNotFoundError:
        return None, None, None, None, None, None, None

data = cargar_datos()
if data[0] is None:
    st.error("⚠️ Error: No encuentro 'precios.xlsx' en GitHub.")
    st.stop()

df_p_usd, df_s_usd, df_config, df_p_cl, df_s_cl, df_p_br, df_s_br = data
LISTA_PAISES = df_config['Pais'].unique().tolist()
ROLES = ['Angelica', 'Senior', 'BM', 'BP']

# --- STATE ---
if 'cotizaciones' not in st.session_state:
    st.session_state['cotizaciones'] = pd.DataFrame(columns=['id', 'fecha', 'empresa', 'pais', 'total', 'moneda', 'estado', 'vendedor'])
if 'carrito' not in st.session_state: st.session_state['carrito'] = []

# --- LÓGICA DE CONTEXTO ---
def obtener_contexto_pais(pais):
    if pais == "Chile":
        return {"moneda": "UF", "df_pruebas": df_p_cl, "df_servicios": df_s_cl, "tipo": "Local"}
    elif pais in ["Brasil", "Brazil"]:
        return {"moneda": "R$", "df_pruebas": df_p_br, "df_servicios": df_s_br, "tipo": "Local"}
    else:
        nivel = df_config[df_config['Pais'] == pais].iloc[0]['Nivel'] if not df_config[df_config['Pais'] == pais].empty else "Medio"
        return {"moneda": "US$", "df_pruebas": df_p_usd, "df_servicios": df_s_usd, "tipo": "Internacional", "nivel": nivel}

# --- CÁLCULOS ---

def calcular_paa(cantidad, moneda_destino):
    # Lógica: 1-2: $1500, 3-5: $1200, 6+: $1100 (Base USD)
    if cantidad <= 2: base_usd = 1500
    elif cantidad <= 5: base_usd = 1200
    else: base_usd = 1100
    
    if moneda_destino == "US$":
        return base_usd, f"Tramo USD: ${base_usd}"
    elif moneda_destino == "UF":
        # (USD * Dolar) / UF
        valor_clp = base_usd * TASAS_DIA['USD_CLP']
        valor_uf = valor_clp / TASAS_DIA['UF']
        return valor_uf, f"(USD {base_usd} * ${TASAS_DIA['USD_CLP']}) / UF"
    elif moneda_destino == "R$":
        valor_brl = base_usd * TASAS_DIA['USD_BRL']
        return valor_brl, f"USD {base_usd} * {TASAS_DIA['USD_BRL']:.2f}"
    return 0.0, "Error"

def calcular_prueba_excel(df, producto, cantidad, es_local):
    if df.empty: return 0.0
    fila = df[df['Producto'] == producto]
    if fila.empty: return 0.0
    
    # AQUÍ ESTÁ EL CAMBIO DE LOS 50
    if es_local:
        # Chile y Brasil parten en 50
        tramos = [50, 100, 200, 300, 500, 1000, 'Infinito']
    else:
        # Internacional parte en 100
        tramos = [100, 200, 300, 500, 1000, 'Infinito']
    
    for tramo in tramos:
        limite = float('inf') if tramo == 'Infinito' else tramo
        if cantidad <= limite:
            # Busca la columna (convierte a string o int para coincidir con excel)
            try: return float(fila.iloc[0][tramo])
            except: 
                try: return float(fila.iloc[0][str(tramo)]) # Intenta como texto
                except: return 0.0
    return 0.0

def calcular_servicio(df, servicio, rol, contexto):
    if df.empty: return 0.0
    
    if contexto['tipo'] == "Internacional":
        fila = df[(df['Servicio'] == servicio) & (df['Nivel'] == contexto['nivel'])]
    else:
        fila = df[df['Servicio'] == servicio]

    if fila.empty: return 0.0
    try: return float(fila.iloc[0][rol])
    except: return 0.0

# --- PANTALLAS ---

def cotizador():
    st.title("📝 Cotizador TalentPro")
    
    # INDICADORES
    k1, k2, k3, k4 = st.columns(4)
    if TASAS_DIA['Status'] == "Online":
        k1.success(f"Dólar: ${TASAS_DIA['USD_CLP']:,.0f}")
        k2.success(f"UF: ${TASAS_DIA['UF']:,.0f}")
        k3.success(f"Real: {TASAS_DIA['USD_BRL']:.2f}")
    else:
        st.warning("⚠️ API Offline (Usando valores ref)")

    st.markdown("---")

    # 1. PAÍS
    with st.container():
        c1, c2 = st.columns([1, 2])
        idx_cl = LISTA_PAISES.index("Chile") if "Chile" in LISTA_PAISES else 0
        pais_sel = c1.selectbox("🌎 País", LISTA_PAISES, index=idx_cl)
        
        ctx = obtener_contexto_pais(pais_sel)
        moneda = ctx['moneda']
        msg = f"Moneda: **{moneda}**"
        if ctx['tipo'] == "Internacional": msg += f" | Tarifa: **{ctx['nivel']}**"
        c2.info(msg)

    # 2. CLIENTE
    st.markdown("---")
    cc1, cc2, cc3, cc4 = st.columns(4)
    empresa = cc1.text_input("Empresa")
    contacto = cc2.text_input("Contacto")
    email = cc3.text_input("Email")
    vendedor = cc4.selectbox("Ejecutivo", ["Comercial 1", "Comercial 2", "Gerencia"])
    fecha = cc1.date_input("Fecha", datetime.now())

    # 3. ÍTEMS
    st.markdown("---")
    st.subheader("2. Selección")
    
    tab_p, tab_s = st.tabs(["🧩 Pruebas", "💼 Servicios"])

    # --- PESTAÑA PRUEBAS ---
    with tab_p:
        cp1, cp2, cp3, cp4 = st.columns([3, 1, 1, 1])
        
        lista_excel = ctx['df_pruebas']['Producto'].unique().tolist() if not ctx['df_pruebas'].empty else []
        lista_completa = ["Certificación PAA (Transversal)"] + lista_excel
        
        if lista_completa:
            sel_p = cp1.selectbox("Producto", lista_completa)
            cant_p = cp2.number_input("Cantidad", 1, 10000, 10)
            
           # CALCULO
            nota = ""
            if sel_p == "Certificación PAA (Transversal)":
                unit_p, nota = calcular_paa(cant_p, moneda)
            else:
                es_local = (ctx['tipo'] == 'Local')
                unit_p = calcular_prueba_excel(ctx['df_pruebas'], sel_p, cant_p, es_local)
                if es_local: nota = "Tramo Local (inicia en 50)"
            
            cp3.metric(f"Unitario ({moneda})", f"{unit_p:,.2f}")
            if nota: cp3.caption(nota)
            
            if cp4.button("Agregar", key="add_p"):
                st.session_state['carrito'].append({
                    "Ítem": "Evaluación", "Desc": sel_p, "Det": f"x{cant_p}",
                    "Moneda": moneda, "Unit": unit_p, "Total": unit_p * cant_p
                })
                st.rerun()

    # --- PESTAÑA SERVICIOS ---
    with tab_s:
        cs1, cs2, cs3, cs4 = st.columns([3, 2, 1, 1])
        lista_servicios = ctx['df_servicios']['Servicio'].unique().tolist() if not ctx['df_servicios'].empty else []
        
        if lista_servicios:
            sel_s = cs1.selectbox("Servicio", lista_servicios)
            c_rol, c_hora = cs2.columns(2)
            rol = c_rol.selectbox("Rol", ROLES)
            horas = c_hora.number_input("Horas", 1, 1000, 1)
            
            unit_s = calcular_servicio(ctx['df_servicios'], sel_s, rol, ctx)
            
            cs3.metric(f"Tarifa ({moneda})", f"{unit_s:,.2f}")
            if cs4.button("Agregar", key="add_s"):
                st.session_state['carrito'].append({
                    "Ítem": "Servicio", "Desc": sel_s, "Det": f"{rol} ({horas}h)",
                    "Moneda": moneda, "Unit": unit_s, "Total": unit_s * horas
                })
                st.rerun()

    # 4. CARRITO
    if st.session_state['carrito']:
        st.markdown("---")
        df_c = pd.DataFrame(st.session_state['carrito'])
        
        monedas_cart = df_c['Moneda'].unique()
        if len(monedas_cart) > 1:
            st.error(f"⚠️ Error: Mezcla de monedas ({monedas_cart}). Vacía carrito.")
        else:
            mon_act = monedas_cart[0]
            st.dataframe(df_c, use_container_width=True, hide_index=True)
            
            subtotal = df_c['Total'].sum()
            tot_eval = df_c[df_c['Ítem'] == 'Evaluación']['Total'].sum()
            
            c_f1, c_f2 = st.columns([3, 1])
            with c_f2:
                st.markdown("### Totales")
                fee = st.checkbox("Fee 10% (Solo Pruebas)", value=False)
                comision = st.number_input("Comisión Banco", 0.0, value=30.0 if mon_act == "US$" else 0.0)
                desc = st.number_input("Descuento", 0.0)
                
                val_fee = tot_eval * 0.10 if fee else 0.0
                final = subtotal + val_fee + comision - desc
                
                st.markdown(f"""
                | Concepto | Monto |
                | :--- | ---: |
                | **Subtotal** | **{mon_act} {subtotal:,.2f}** |
                | Fee Admin | {mon_act} {val_fee:,.2f} |
                | Banco | {mon_act} {comision:,.2f} |
                | Descuento | - {mon_act} {desc:,.2f} |
                | **TOTAL** | **{mon_act} {final:,.2f}** |
                """)
                
                if st.button("💾 CONFIRMAR", type="primary"):
                    if not empresa: st.error("Falta Empresa")
                    else:
                        new_id = f"TP-{random.randint(1000,9999)}"
                        reg = {
                            'id': new_id, 'fecha': fecha.strftime("%Y-%m-%d"),
                            'empresa': empresa, 'pais': pais_sel, 'moneda': mon_act,
                            'total': final, 'estado': 'Enviada', 'vendedor': vendedor
                        }
                        st.session_state['cotizaciones'] = pd.concat([st.session_state['cotizaciones'], pd.DataFrame([reg])], ignore_index=True)
                        st.session_state['carrito'] = []
                        st.success(f"Guardado: {new_id}")
                        st.balloons()
            with c_f1:
                if st.button("Vaciar Carrito"):
                    st.session_state['carrito'] = []
                    st.rerun()

def dashboard():
    st.title("📊 Dashboard")
    df = st.session_state['cotizaciones']
    if df.empty:
        st.info("Sin datos.")
        return
    k1, k2, k3 = st.columns(3)
    k1.write("Ventas por Moneda")
    k1.dataframe(df[df['estado'].isin(['Facturada','Pagada'])].groupby('moneda')['total'].sum())
    k2.metric("Pipeline", len(df[df['estado'].isin(['Enviada','Aprobada'])]))
    k3.metric("Cotizaciones", len(df))

def finanzas():
    st.title("💰 Finanzas")
    df = st.session_state['cotizaciones']
    if df.empty: return
    edited = st.data_editor(
        df,
        column_config={"estado": st.column_config.SelectboxColumn("Estado", options=["Enviada", "Aprobada", "Facturada", "Pagada", "Rechazada"]), "total": st.column_config.NumberColumn(format="%.2f")},
        disabled=["id", "empresa", "vendedor", "pais"],
        hide_index=True,
        use_container_width=True
    )
    if not edited.equals(df):
        st.session_state['cotizaciones'] = edited
        st.toast("Guardado")

with st.sidebar:
    st.title("TalentPro")
    opcion = st.radio("Menú", ["Cotizador", "Dashboard", "Finanzas"])

if opcion == "Cotizador": cotizador()
elif opcion == "Dashboard": dashboard()
elif opcion == "Finanzas": finanzas()
