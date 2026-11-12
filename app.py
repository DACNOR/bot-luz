import streamlit as st
import pdfplumber
import re

# Configuración de la página
st.set_page_config(
    page_title="Auditor de Facturas de la Luz",
    page_icon="⚡",
    layout="centered"
)

# --- ESTILOS CSS PERSONALIZADOS ---
st.markdown("""
<style>
/* 1. Ocultar barra superior de Streamlit (Share, estrella, GitHub, menú) */
header[data-testid="stHeader"] {
    display: none !important;
}
#MainMenu {
    visibility: hidden !important;
}
footer {
    visibility: hidden !important;
}
.stDeployButton {
    display: none !important;
}
div[data-testid="stToolbar"] {
    display: none !important;
}

/* 2. Aumentar tamaño de textos descriptivos y etiquetas */
.subtitulo-grande {
    font-size: 1.25rem !important;
    line-height: 1.5 !important;
    color: #E0E0E0 !important;
    margin-bottom: 1.5rem !important;
}
div[data-testid="stFileUploader"] label p {
    font-size: 1.2rem !important;
    font-weight: 600 !important;
    color: #FFFFFF !important;
    margin-bottom: 0.6rem !important;
}
div[data-testid="stNumberInput"] label p,
div[data-testid="stTextInput"] label p,
div[data-testid="stCheckbox"] label p {
    font-size: 1.05rem !important;
}

/* 3. Cápsula grande, centrada y proporcional */
div[data-testid="stFileUploader"] section {
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    justify-content: center !important;
    gap: 1rem !important;
    padding: 2.5rem 2rem !important;
    min-height: 170px !important;
    border: 2px dashed #4DA6FF !important;
    border-radius: 16px !important;
    background-color: rgba(77, 166, 255, 0.08) !important;
    transition: all 0.2s ease-in-out;
}
div[data-testid="stFileUploader"] section:hover {
    border-color: #FFD700 !important;
    background-color: rgba(255, 215, 0, 0.10) !important;
}

/* Botón Upload más grande y destacado */
div[data-testid="stFileUploader"] button {
    font-size: 1.35rem !important;
    padding: 0.85rem 2.2rem !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
    border: 1px solid #4DA6FF !important;
}
div[data-testid="stFileUploader"] button svg {
    width: 1.4rem !important;
    height: 1.4rem !important;
}

/* Texto "200MB per file • PDF" más grande y legible */
div[data-testid="stFileUploader"] section small,
div[data-testid="stFileUploader"] section span {
    font-size: 1.1rem !important;
    color: #CCCCCC !important;
}
</style>
""", unsafe_allow_html=True)

# --- FUNCIONES DE EXTRACCIÓN ---
def extraer_texto_pdf(archivo_pdf):
    texto_completo = ""
    try:
        with pdfplumber.open(archivo_pdf) as pdf:
            for pagina in pdf.pages:
                texto = pagina.extract_text()
                if texto:
                    texto_completo += texto + "\n"
    except Exception as e:
        st.error(f"Error al leer el PDF: {e}")
    return texto_completo

def analizar_datos_factura(texto):
    datos = {
        "cups": "",
        "potencia": 5.0,
        "precio_kwh": 0.14,
        "consumo_kwh": 250,
        "servicios_detectados": []
    }
    
    if not texto:
        return datos

    # 1. Detectar CUPS (Formato ES + 16 dígitos + 2-4 caracteres)
    match_cups = re.search(r'\bES\d{16}[A-Z0-9]{2,4}\b', texto.replace(" ", ""))
    if match_cups:
        datos["cups"] = match_cups.group(0)

    # 2. Detectar Potencia contratada (kW)
    matches_potencia = re.findall(r'(?:potencia|p1|p2|contratada)[^\d\n]{0,25}(\d{1,2}[,\.]\d{1,3})\s*kw\b', texto, re.IGNORECASE)
    if matches_potencia:
        valores_p = [float(p.replace(',', '.')) for p in matches_potencia if 1.0 <= float(p.replace(',', '.')) <= 15.0]
        if valores_p:
            datos["potencia"] = max(valores_p)

    # 3. Detectar Precio de la Energía (€/kWh)
    matches_precio = re.findall(r'(0[,\.]\d{3,6})\s*(?:€/kwh|eur/kwh)', texto, re.IGNORECASE)
    if not matches_precio:
        matches_precio = re.findall(r'kwh\s*[x\*]\s*(0[,\.]\d{3,6})', texto, re.IGNORECASE)
    if matches_precio:
        precios = [float(p.replace(',', '.')) for p in matches_precio if 0.05 <= float(p.replace(',', '.')) <= 0.60]
        if precios:
            datos["precio_kwh"] = round(sum(precios) / len(precios), 4)

    # 4. Detectar Consumo mensual aproximado (kWh)
    matches_consumo = re.findall(r'(?:consumo|energía activa)[^\d\n]{0,25}(\d{2,4})\s*kwh\b', texto, re.IGNORECASE)
    if matches_consumo:
        consumos = [int(c) for c in matches_consumo if 20 <= int(c) <= 3000]
        if consumos:
            datos["consumo_kwh"] = max(consumos)

    # 5. Detectar servicios extra / mantenimientos ocultos
    palabras_clave_extras = [
        "facilita", "mantenimiento", "protección", "seguro", "asistencia",
        "okluz", "servielectric", "urgencias eléctricas", "reparaciones"
    ]
    texto_lower = texto.lower()
    for palabra in palabras_clave_extras:
        if palabra in texto_lower:
            datos["servicios_detectados"].append(palabra.capitalize())

    return datos

# --- INTERFAZ DE USUARIO ---
st.title("⚡ Auditor de Facturas Eléctricas")
st.markdown(
    '<p class="subtitulo-grande">Sube tu factura en PDF para detectar sobrecostes ocultos en el precio del kWh, exceso de potencia o servicios de mantenimiento innecesarios.</p>',
    unsafe_allow_html=True
)

archivo_subido = st.file_uploader(
    "📄 Arrastra aquí o selecciona tu factura de la luz (Endesa, Iberdrola, TotalEnergies, Nufri, Repsol...)",
    type=["pdf"]
)

datos_iniciales = {
    "cups": "",
    "potencia": 5.0,
    "precio_kwh": 0.14,
    "consumo_kwh": 250,
    "servicios_detectados": []
}

texto_extraido = ""
if archivo_subido is not None:
    with st.spinner("Analizando el PDF..."):
        texto_extraido = extraer_texto_pdf(archivo_subido)
        datos_iniciales = analizar_datos_factura(texto_extraido)
        if texto_extraido.strip():
            st.success("✅ PDF leído. Verifica que los datos extraídos coincidan con tu factura:")
        else:
            st.warning("⚠️ El PDF parece ser una imagen escaneada. Introduce los datos manualmente en las casillas.")

# --- FORMULARIO EDITABLE ---
st.subheader("1. Datos de tu suministro")
col1, col2 = st.columns(2)

with col1:
    cups_input = st.text_input("Código CUPS (Opcional)", value=datos_iniciales["cups"], placeholder="ES0021...")
    potencia_input = st.number_input(
        "Potencia contratada (kW)",
        min_value=1.0,
        max_value=20.0,
        value=float(datos_iniciales["potencia"]),
        step=0.1,
        format="%.2f"
    )

with col2:
    precio_kwh_input = st.number_input(
        "Precio de la energía (€/kWh)",
        min_value=0.01,
        max_value=1.00,
        value=float(datos_iniciales["precio_kwh"]),
        step=0.005,
        format="%.4f"
    )
    consumo_input = st.number_input(
        "Consumo mensual medio (kWh/mes)",
        min_value=10,
        max_value=5000,
        value=int(datos_iniciales["consumo_kwh"]),
        step=10
    )

tiene_extras = st.checkbox(
    "Tengo servicios de mantenimiento / seguros extra en la factura",
    value=len(datos_iniciales["servicios_detectados"]) > 0
)

if datos_iniciales["servicios_detectados"]:
    st.info(f"🔎 Palabras clave detectadas en el PDF: **{', '.join(set(datos_iniciales['servicios_detectados']))}**")

st.divider()

# --- CÁLCULOS Y SEMÁFORO DE DIAGNÓSTICO ---
st.subheader("2. Resultado de la Auditoría")

PRECIO_REF = 0.1200       # €/kWh competitivo actual
POTENCIA_REF = 5.0        # kW estándar vivienda electrificada
COSTE_KW_ANUAL = 38.0     # Aprox. €/kW·año (peajes + cargos + margen)
COSTE_EXTRAS_ANUAL = 72.0 # ~6 €/mes promedio en mantenimientos

consumo_anual = consumo_input * 12
sobrecoste_energia = max(0.0, (precio_kwh_input - PRECIO_REF) * consumo_anual)
sobrecoste_potencia = max(0.0, (potencia_input - POTENCIA_REF) * COSTE_KW_ANUAL)
sobrecoste_extras = COSTE_EXTRAS_ANUAL if tiene_extras else 0.0

ahorro_total_anual = sobrecoste_energia + sobrecoste_potencia + sobrecoste_extras

if precio_kwh_input > 0.16:
    st.error("🔴 **CAMBIAR URGENTE: Estás pagando un precio muy inflado por la energía.**")
elif precio_kwh_input > 0.13 or potencia_input > 5.5 or tiene_extras:
    st.warning("🟡 **REVISABLE: Tu tarifa es aceptable, pero tienes margen claro de optimización.**")
else:
    st.success("🟢 **TARIFA ÓPTIMA: Tienes un precio competitivo y una potencia bien ajustada.**")

m1, m2, m3 = st.columns(3)
m1.metric("Tu precio kWh", f"{precio_kwh_input:.4f} €", f"{precio_kwh_input - PRECIO_REF:+.4f} € vs ref.", delta_color="inverse")
m2.metric("Tu potencia", f"{potencia_input:.2f} kW", f"{potencia_input - POTENCIA_REF:+.2f} kW vs ref.", delta_color="inverse")
m3.metric("Ahorro anual estimado", f"{ahorro_total_anual:.0f} €/año")

st.markdown("### Desglose del diagnóstico:")

if sobrecoste_energia > 0:
    st.write(f"- **Término de Energía:** Estás pagando **{precio_kwh_input:.4f} €/kWh** frente a una tarifa competitiva de **0,1200 €/kWh**. Solo en consumo ahorrarías unos **{sobrecoste_energia:.0f} € al año**.")
else:
    st.write("- **Término de Energía:** Tu precio del kWh está en línea con las mejores ofertas del mercado libre.")

if potencia_input > 5.5:
    st.write(f"- **Exceso de Potencia:** Tienes **{potencia_input:.2f} kW**. Para una vivienda estándar (incluso 100% eléctrica), bajar a **5,00 kW** evita que salte el ICP y te ahorra unos **{sobrecoste_potencia:.0f} € al año** en costes fijos.")
else:
    st.write(f"- **Potencia Contratada:** Tus **{potencia_input:.2f} kW** están dentro del rango recomendado (≤ 5,5 kW).")

if tiene_extras:
    st.write(f"- **Servicios Añadidos:** Se han marcado servicios de mantenimiento o seguros extra. Darlos de baja suele suponer un ahorro directo de unos **{COSTE_EXTRAS_ANUAL:.0f} € al año**.")

if texto_extraido:
    with st.expander("Ver texto extraído del PDF (Depuración)"):
        st.text(texto_extraido[:3000])
