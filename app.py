import streamlit as st
import pdfplumber
import numpy as np
from PIL import Image
from rapidocr_onnxruntime import RapidOCR
import re

# Configuració de la pàgina
st.set_page_config(
    page_title="Auditor de Factures de la Llum",
    page_icon="⚡",
    layout="centered"
)

# --- ESTILS CSS PERSONALITZATS ---
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

/* 2. Augmentar mida de textos descriptius i etiquetes */
.subtitulo-grande {
    font-size: 1.25rem !important;
    line-height: 1.5 !important;
    color: #E0E0E0 !important;
    margin-bottom: 0.8rem !important;
}
.nota-privacidad {
    font-size: 1.0rem !important;
    color: #9EE09E !important;
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

/* 3. Càpsula gran, centrada i proporcional */
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

/* Botó Upload més gran i destacat */
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

/* Text de límit d'arxius més gran i llegible */
div[data-testid="stFileUploader"] section small,
div[data-testid="stFileUploader"] section span {
    font-size: 1.1rem !important;
    color: #CCCCCC !important;
}
</style>
""", unsafe_allow_html=True)

# --- MOTOR OCR PER A CAPTURES I PDF ESCANEJATS ---
@st.cache_resource
def cargar_ocr():
    return RapidOCR()

def extraer_texto_imagen(imagen_pil):
    ocr = cargar_ocr()
    img_array = np.array(imagen_pil.convert("RGB"))
    resultado, _ = ocr(img_array)
    if not resultado:
        return ""
    return "\n".join([linea[1] for linea in resultado])

def extraer_texto_archivo(archivo):
    texto_completo = ""
    nombre = archivo.name.lower()
    try:
        if nombre.endswith(".pdf"):
            with pdfplumber.open(archivo) as pdf:
                for pagina in pdf.pages:
                    texto = pagina.extract_text()
                    if texto:
                        texto_completo += texto + "\n"
            # Si el PDF és una imatge escanejada sense text seleccionable, aplicar OCR
            if not texto_completo.strip():
                archivo.seek(0)
                with pdfplumber.open(archivo) as pdf:
                    for pagina in pdf.pages[:3]:
                        img = pagina.to_image(resolution=200).original
                        texto_completo += extraer_texto_imagen(img) + "\n"
        else:
            imagen = Image.open(archivo)
            texto_completo = extraer_texto_imagen(imagen)
    except Exception as e:
        st.error(f"Error en llegir l'arxiu: {e}")
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

    # 1. Detectar CUPS (Format ES + 16 dígits + 2-4 caràcters)
    match_cups = re.search(r'\bES\d{16}[A-Z0-9]{2,4}\b', texto.replace(" ", ""))
    if match_cups:
        datos["cups"] = match_cups.group(0)

    # 2. Detectar Potència contractada (kW) - Multiidioma (CAT / ES / EN)
    matches_potencia = re.findall(
        r'(?:potència|potencia|power|p1|p2|contractada|contratada)[^\d\n]{0,25}(\d{1,2}[,\.]\d{1,3})\s*kw\b',
        texto,
        re.IGNORECASE
    )
    if matches_potencia:
        valores_p = [float(p.replace(',', '.')) for p in matches_potencia if 1.0 <= float(p.replace(',', '.')) <= 15.0]
        if valores_p:
            datos["potencia"] = max(valores_p)

    # 3. Detectar Preu de l'Energia (€/kWh) - Multiidioma i OCR
    matches_precio = re.findall(r'(0[,\.]\d{3,6})\s*(?:€/kwh|eur/kwh|e/kwh)', texto, re.IGNORECASE)
    if not matches_precio:
        matches_precio = re.findall(r'kwh\s*[x\*×]\s*(0[,\.]\d{3,6})', texto, re.IGNORECASE)
    if matches_precio:
        precios = [float(p.replace(',', '.')) for p in matches_precio if 0.05 <= float(p.replace(',', '.')) <= 0.60]
        if precios:
            datos["precio_kwh"] = round(sum(precios) / len(precios), 4)

    # 4. Detectar Consum mensual aproximat (kWh) - Multiidioma (CAT / ES / EN)
    matches_consumo = re.findall(
        r'(?:consum|consumo|consumption|energia activa|energía activa|active energy)[^\d\n]{0,25}(\d{2,4})\s*kwh\b',
        texto,
        re.IGNORECASE
    )
    if matches_consumo:
        consumos = [int(c) for c in matches_consumo if 20 <= int(c) <= 3000]
        if consumos:
            datos["consumo_kwh"] = max(consumos)

    # 5. Detectar serveis extra / manteniments ocults - Multiidioma
    palabras_clave_extras = [
        "facilita", "manteniment", "mantenimiento", "maintenance",
        "protecció", "protección", "protection",
        "assegurança", "seguro", "insurance",
        "assistència", "asistencia", "assistance",
        "okluz", "servielectric", "urgències", "urgencias", "reparacions", "reparaciones"
    ]
    texto_lower = texto.lower()
    for palabra in palabras_clave_extras:
        if palabra in texto_lower:
            datos["servicios_detectados"].append(palabra.capitalize())

    return datos

# --- INTERFÍCIE D'USUARI ---
st.title("⚡ Auditor de Factures Elèctriques")
st.markdown(
    '<p class="subtitulo-grande">Puja la teva factura en PDF o una captura de pantalla per detectar sobrecostos ocults en el preu del kWh, excés de potència o serveis de manteniment innecessaris.</p>',
    unsafe_allow_html=True
)
st.markdown(
    '<p class="nota-privacidad">🔒 100% privat: la factura s\'analitza al moment i no es desa enlloc.</p>',
    unsafe_allow_html=True
)

archivo_subido = st.file_uploader(
    "📄 Arrossega aquí o selecciona la teva factura en PDF o captura (PNG, JPG)",
    type=["pdf", "png", "jpg", "jpeg", "webp"]
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
    with st.spinner("Llegint la factura (PDF o captura)..."):
        texto_extraido = extraer_texto_archivo(archivo_subido)
        datos_iniciales = analizar_datos_factura(texto_extraido)
        if texto_extraido.strip():
            st.success("✅ Factura llegida correctament! Les dades s'han emplenat soles (revisa que coincideixin amb la teva factura):")
        else:
            st.warning("⚠️ No s'ha pogut llegir el text de la imatge. Assegura't que es vegi nítida o introdueix les dades manualment.")

# --- FORMULARI EDITABLE ---
st.subheader("1. Dades del teu subministrament")
col1, col2 = st.columns(2)

with col1:
    cups_input = st.text_input("Codi CUPS (Opcional)", value=datos_iniciales["cups"], placeholder="ES0021...")
    potencia_input = st.number_input(
        "Potència contractada (kW)",
        min_value=1.0,
        max_value=20.0,
        value=float(datos_iniciales["potencia"]),
        step=0.1,
        format="%.2f"
    )

with col2:
    precio_kwh_input = st.number_input(
        "Preu de l'energia (€/kWh)",
        min_value=0.01,
        max_value=1.00,
        value=float(datos_iniciales["precio_kwh"]),
        step=0.005,
        format="%.4f"
    )
    consumo_input = st.number_input(
        "Consum mensual mitjà (kWh/mes)",
        min_value=10,
        max_value=5000,
        value=int(datos_iniciales["consumo_kwh"]),
        step=10
    )

tiene_extras = st.checkbox(
    "Tinc serveis de manteniment / assegurances extra a la factura",
    value=len(datos_iniciales["servicios_detectados"]) > 0
)

if datos_iniciales["servicios_detectados"]:
    st.info(f"🔎 Paraules clau detectades a la factura: **{', '.join(set(datos_iniciales['servicios_detectados']))}**")

st.divider()

# --- CÀLCULS I SEMÀFOR DE DIAGNÒSTIC ---
st.subheader("2. Resultat de l'Auditoria")

PRECIO_REF = 0.1200       # €/kWh competitiu actual
POTENCIA_REF = 5.0        # kW estàndard habitatge electrificat
COSTE_KW_ANUAL = 38.0     # Aprox. €/kW·any (peatges + càrrecs + marge)
COSTE_EXTRAS_ANUAL = 72.0 # ~6 €/mes mitjana en manteniments

consumo_anual = consumo_input * 12
sobrecoste_energia = max(0.0, (precio_kwh_input - PRECIO_REF) * consumo_anual)
sobrecoste_potencia = max(0.0, (potencia_input - POTENCIA_REF) * COSTE_KW_ANUAL)
sobrecoste_extras = COSTE_EXTRAS_ANUAL if tiene_extras else 0.0

ahorro_total_anual = sobrecoste_energia + sobrecoste_potencia + sobrecoste_extras

if precio_kwh_input > 0.16:
    st.error("🔴 **CANVIAR URGENT: Estàs pagant un preu molt inflat per l'energia.**")
elif precio_kwh_input > 0.13 or potencia_input > 5.5 or tiene_extras:
    st.warning("🟡 **REVISABLE: La teva tarifa és acceptable, però tens marge clar d'optimització.**")
else:
    st.success("🟢 **TARIFA ÒPTIMA: Tens un preu competitiu i una potència ben ajustada.**")

m1, m2, m3 = st.columns(3)
m1.metric("El teu preu kWh", f"{precio_kwh_input:.4f} €", f"{precio_kwh_input - PRECIO_REF:+.4f} € vs ref.", delta_color="inverse")
m2.metric("La teva potència", f"{potencia_input:.2f} kW", f"{potencia_input - POTENCIA_REF:+.2f} kW vs ref.", delta_color="inverse")
m3.metric("Estalvi anual estimat", f"{ahorro_total_anual:.0f} €/any")

st.markdown("### Desglossament del diagnòstic:")

if sobrecoste_energia > 0:
    st.write(f"- **Terme d'Energia:** Estàs pagant **{precio_kwh_input:.4f} €/kWh** davant d'una tarifa competitiva de **0,1200 €/kWh**. Només en consum estalviaries uns **{sobrecoste_energia:.0f} € a l'any**.")
else:
    st.write("- **Terme d'Energia:** El teu preu del kWh està en línia amb les millors ofertes del mercat lliure.")

if potencia_input > 5.5:
    st.write(f"- **Excés de Potència:** Tens **{potencia_input:.2f} kW**. Per a un habitatge estàndard (fins i tot 100% elèctric), baixar a **5,00 kW** evita que salti l'ICP i t'estalvia uns **{sobrecoste_potencia:.0f} € a l'any** en costos fixos.")
else:
    st.write(f"- **Potència Contractada:** Els teus **{potencia_input:.2f} kW** estan dins del rang recomanat (≤ 5,5 kW).")

if tiene_extras:
    st.write(f"- **Serveis Afegits:** S'han marcat serveis de manteniment o assegurances extra. Donar-los de baixa acostuma a suposar un estalvi directe d'uns **{COSTE_EXTRAS_ANUAL:.0f} € a l'any**.")

if texto_extraido:
    with st.expander("Veure text extret de la factura (Depuració)"):
        st.text(texto_extraido[:3000])
