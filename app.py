import streamlit as st
import pandas as pd
import io

st.title("🛠️ Generador de Archivo de Precios")
st.info("Haz clic en el botón para descargar la plantilla Excel correcta.")

# --- 1. CONFIGURACIÓN (PAÍSES) ---
df_config = pd.DataFrame({
    'Pais': [
        "Estados Unidos", "Puerto Rico", "Canadá", "Brasil", "España", "Europa", "Reino Unido", # Alto
        "Chile", "México", "Colombia", "Perú", "Panamá", "Uruguay", "Costa Rica", # Medio
        "Argentina", "Bolivia", "Paraguay", "Ecuador", "Guatemala", "Honduras", "El Salvador", "Nicaragua", "República Dominicana" # Bajo
    ],
    'Nivel': [
        "Alto", "Alto", "Alto", "Alto", "Alto", "Alto", "Alto",
        "Medio", "Medio", "Medio", "Medio", "Medio", "Medio", "Medio",
        "Bajo", "Bajo", "Bajo", "Bajo", "Bajo", "Bajo", "Bajo", "Bajo", "Bajo"
    ]
})

# --- 2. PRUEBAS GLOBAL (USD) ---
df_pruebas = pd.DataFrame([
    {"Producto": "OPQ (Personalidad Laboral)", 100: 22, 200: 21, 300: 20, 500: 19, 1000: 18, "Infinito": 17},
    {"Producto": "MQ (Motivación)", 100: 17, 200: 17, 300: 16, 500: 15, 1000: 14, "Infinito": 13},
    {"Producto": "CCSQ (Contacto con Cliente)", 100: 17, 200: 17, 300: 16, 500: 15, 1000: 14, "Infinito": 13},
    {"Producto": "Verify Interactive", 100: 19, 200: 18, 300: 16, 500: 14, 1000: 12, "Infinito": 11},
    {"Producto": "Smart Interview", 100: 24, 200: 23, 300: 22, 500: 21, 1000: 19, "Infinito": 17},
    {"Producto": "360 Assessment with OPQ", 100: 420, 200: 420, 300: 420, 500: 420, 1000: 420, "Infinito": 420},
])

# --- 3. SERVICIOS GLOBAL (USD - Niveles) ---
# Creamos una lista base y la expandimos por niveles
servicios_base = [
    ("Assessment Center (Jornada)", 1800, 1500, 1200),
    ("Entrevista por Competencias", 450, 300, 220),
    ("Feedback Individual", 550, 400, 300),
    ("Consultoría HR (Hora)", 350, 250, 180),
    ("Workshop / Taller", 2500, 2000, 1500),
    ("Entrevista Compromiso", 450, 300, 220),
    ("Ficha Resumen", 200, 150, 120),
    ("Hunting", 5000, 4000, 3000)
]

data_servicios = []
for serv, p_alto, p_medio, p_bajo in servicios_base:
    # Alto
    data_servicios.append({"Servicio": serv, "Nivel": "Alto", "Angelica": p_alto, "Senior": p_alto*0.7, "BM": p_alto*0.6, "BP": p_alto*0.5})
    # Medio
    data_servicios.append({"Servicio": serv, "Nivel": "Medio", "Angelica": p_medio, "Senior": p_medio*0.7, "BM": p_medio*0.6, "BP": p_medio*0.5})
    # Bajo
    data_servicios.append({"Servicio": serv, "Nivel": "Bajo", "Angelica": p_bajo, "Senior": p_bajo*0.7, "BM": p_bajo*0.6, "BP": p_bajo*0.5})

df_servicios = pd.DataFrame(data_servicios)

# --- 4. CHILE (UF) ---
df_p_cl = df_pruebas.copy()
# Simulamos precios en UF (Dividiendo por ~38.000 y ajustando)
for col in [100, 200, 300, 500, 1000, "Infinito"]:
    df_p_cl[col] = df_p_cl[col].apply(lambda x: round(x / 35, 2)) # Ejemplo simple conversión

df_s_cl = pd.DataFrame([
    {"Servicio": "Assessment Center (Jornada)", "Angelica": 45, "Senior": 30, "BM": 25, "BP": 15},
    {"Servicio": "Entrevista por Competencias", "Angelica": 5.5, "Senior": 3.5, "BM": 2.5, "BP": 1.5},
    {"Servicio": "Feedback Individual", "Angelica": 8, "Senior": 5, "BM": 3, "BP": 2},
    {"Servicio": "Consultoría HR (Hora)", "Angelica": 6, "Senior": 4, "BM": 3, "BP": 2},
    {"Servicio": "Taller TalentPro", "Angelica": 60, "Senior": 40, "BM": 30, "BP": 20},
])

# --- 5. BRASIL (R$) ---
df_p_br = df_pruebas.copy()
# Simulamos precios en Reales (Multiplicando por ~5)
for col in [100, 200, 300, 500, 1000, "Infinito"]:
    df_p_br[col] = df_p_br[col].apply(lambda x: x * 5.5)

df_s_br = pd.DataFrame([
    {"Servicio": "Assessment Center (Jornada)", "Angelica": 8000, "Senior": 5000, "BM": 4000, "BP": 3000},
    {"Servicio": "Entrevista por Competencias", "Angelica": 1500, "Senior": 800, "BM": 600, "BP": 400},
    {"Servicio": "Feedback Individual", "Angelica": 2000, "Senior": 1000, "BM": 800, "BP": 500},
    {"Servicio": "Consultoría HR (Hora)", "Angelica": 1200, "Senior": 600, "BM": 400, "BP": 300},
])

# --- GENERAR EXCEL ---
buffer = io.BytesIO()
with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
    df_pruebas.to_excel(writer, sheet_name='Pruebas', index=False)
    df_servicios.to_excel(writer, sheet_name='Servicios', index=False)
    df_config.to_excel(writer, sheet_name='Config', index=False)
    df_p_cl.to_excel(writer, sheet_name='Pruebas_CL', index=False)
    df_s_cl.to_excel(writer, sheet_name='Servicios_CL', index=False)
    df_p_br.to_excel(writer, sheet_name='Pruebas_BR', index=False)
    df_s_br.to_excel(writer, sheet_name='Servicios_BR', index=False)

st.download_button(
    label="📥 DESCARGAR PRECIOS.XLSX",
    data=buffer,
    file_name="precios.xlsx",
    mime="application/vnd.ms-excel"
)
