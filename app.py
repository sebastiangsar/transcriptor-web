import os
import json
import tempfile
from concurrent.futures import ThreadPoolExecutor
import requests
import streamlit as st
import streamlit.components.v1 as components
import yt_dlp
from groq import Groq

# 1. Configuración de página
st.set_page_config(page_title="Transcriptor & Estrategia Viral", page_icon="🎬", layout="centered")

MODELO_LLM = "llama-3.1-8b-instant"
# 2. Cliente Groq en caché (Ultra-rápido)
@st.cache_resource(show_spinner=False)
def get_groq_client(api_key: str) -> Groq:
    return Groq(api_key=api_key)

# 3. Estado de sesión
claves_estado = [
    "texto_original", "texto_traducido", "guiones_generados", 
    "lead_magnets_generados"
]
for k in claves_estado:
    if k not in st.session_state:
        st.session_state[k] = None

# Lectura segura de secretos
GROQ_API_KEY = ""
try:
    if "GROQ_API_KEY" in st.secrets:
        GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except Exception:
    GROQ_API_KEY = ""

def buscar_archivo_cookies():
    for n in ["cookies.txt", "cookies.txt.txt", "instagram.com_cookies.txt"]:
        if os.path.isfile(n):
            return n
    return None

# ==============================================================
# BARRA LATERAL
# ==============================================================
with st.sidebar:
    st.header("⚙️ Configuración")
    if not GROQ_API_KEY:
        GROQ_API_KEY = st.text_input("Groq API Key:", type="password", placeholder="gsk_...")
    
    st.subheader("Sesión de Redes / Cookies")
    cookie_subida = st.file_uploader("Sube cookies.txt:", type=["txt"], key="up_cookies")
    if cookie_subida is not None:
        try:
            with open("cookies.txt", "wb") as f:
                f.write(cookie_subida.getvalue())
            st.success("¡Cookies guardadas!")
        except Exception:
            pass

    archivo_cookies = buscar_archivo_cookies()
    if archivo_cookies:
        st.success(f"Sesión activa ({archivo_cookies})")
    else:
        st.caption("Sin cookies.")

    st.markdown("---")
    if st.button("Limpiar datos", use_container_width=True):
        for k in claves_estado:
            st.session_state[k] = None
        st.rerun()

st.title("🎬 Transcriptor & Estrategia Viral")
st.caption("Videos Virales, Guiones con IA y Lead Magnets a medida")

# Botón Copiar
def boton_copiar(texto: str, id_btn="copiar"):
    if not texto:
        return
    texto_json = json.dumps(texto)
    html_code = f"""
    <button onclick="copiar_{id_btn}()" style="
        background-color: #10b981; color: white; border: none; padding: 6px 14px;
        border-radius: 6px; font-weight: 600; cursor: pointer; font-size: 13px;
        display: inline-flex; align-items: center; gap: 4px; margin-bottom: 8px;">
        📋 Copiar
    </button>
    <span id="msg_{id_btn}" style="margin-left: 10px; color: #10b981; font-weight: bold; font-size: 13px; display: none;">✅ ¡Copiado!</span>
    <script>
    function copiar_{id_btn}() {{
        const text = {texto_json};
        navigator.clipboard.writeText(text).then(() => {{
            const msg = document.getElementById('msg_{id_btn}');
            msg.style.display = 'inline';
            setTimeout(() => {{ msg.style.display = 'none'; }}, 2000);
        }});
    }}
    </script>
    """
    components.html(html_code, height=42)

# ==============================================================
# PROCESAMIENTO DE AUDIO DE ALTA VELOCIDAD
# ==============================================================
def descargar_tiktok_directo(enlace: str):
    try:
        resp = requests.post("https://www.tikwm.com/api/", data={"url": enlace}, timeout=8)
        data = resp.json()
        if data.get("code") == 0 and "data" in data:
            media_url = data["data"].get("music") or data["data"].get("play")
            if media_url:
                if media_url.startswith("/"):
                    media_url = f"https://www.tikwm.com{media_url}"
                r = requests.get(media_url, timeout=12)
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
                temp_file.write(r.content)
                temp_file.close()
                return temp_file.name
    except Exception:
        pass
    return None

def extraer_audio_rapido(enlace: str) -> str:
    if "tiktok.com" in enlace:
        tk = descargar_tiktok_directo(enlace)
        if tk:
            return tk

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".m4a")
    temp_path = temp_file.name
    temp_file.close()

    opciones = {
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'outtmpl': temp_path,
        'quiet': True,
        'no_warnings': True,
        'overwrites': True,
        'extractor_args': {
            'youtube': {'player_client': ['android', 'web']}
        }
    }

    cookies_file = buscar_archivo_cookies()
    if cookies_file:
        opciones['cookiefile'] = cookies_file

    with yt_dlp.YoutubeDL(opciones) as ydl:
        ydl.download([enlace])

    return temp_path

def transcribir_con_groq(archivo_o_buffer, api_key: str, nombre_archivo="audio.mp3") -> str:
    client = get_groq_client(api_key)
    if isinstance(archivo_o_buffer, str):
        with open(archivo_o_buffer, "rb") as f:
            contenido = f.read()
    else:
        contenido = archivo_o_buffer

    transcription = client.audio.transcriptions.create(
        file=(nombre_archivo, contenido),
        model="whisper-large-v3-turbo",
        response_format="text",
        temperature=0.0
    )
    return transcription

def formatear_o_traducir_texto(texto: str, api_key: str, traducir=False) -> str:
    client = get_groq_client(api_key)
    instruccion = (
        "Traduce el texto al español latino neutro en párrafos limpios y legibles. Devuelve solo el resultado."
        if traducir else
        "Organiza el siguiente texto en párrafos limpios y legibles sin alterar las palabras originales. Devuelve solo el texto."
    )
    try:
        res = client.chat.completions.create(
            model=MODELO_LLM,
            messages=[
                {"role": "system", "content": instruccion},
                {"role": "user", "content": texto}
            ],
            temperature=0.2
        )
        return res.choices[0].message.content.strip()
    except Exception:
        return texto

def procesar_texto_paralelo(texto_crudo: str, traducir: bool, api_key: str):
    if not traducir:
        return formatear_o_traducir_texto(texto_crudo, api_key, traducir=False), None

    with ThreadPoolExecutor(max_workers=2) as executor:
        futuro_orig = executor.submit(formatear_o_traducir_texto, texto_crudo, api_key, False)
        futuro_trad = executor.submit(formatear_o_traducir_texto, texto_crudo, api_key, True)
        return futuro_orig.result(), futuro_trad.result()

def generar_guiones_y_leadmagnets(transcripcion: str, nicho_usuario: str, api_key: str):
    client = get_groq_client(api_key)
    prompt = f"""Eres un estratega de contenido viral, copywriter y arquitecto de embudos de conversión.
Tu misión:
1. Desarmar la fórmula del video de referencia y crear 3 guiones adaptados al tema/nicho del usuario.
2. Diseñar 3 LEAD MAGNETS 100% personalizados y específicos para monetizar ese tema/producto en 3 niveles de valor.

TEMA / PRODUCTO / SERVICIO: \"{nicho_usuario}\"
TRANSCRIPCIÓN DE REFERENCIA: \"{transcripcion}\"

ENTREGA OBLIGATORIA (Usa exactamente "=== DIVISION_LEADS ===" entre los guiones y los lead magnets):

### 🧠 RADIOGRAFÍA DE LA FÓRMULA VIRAL
- **El Gancho (Hook):** Técnica psicológica que usó.
- **Estructura de Retención:** Ritmo y manejo de la tensión.
- **Remate y CTA:** Estrategia de cierre.

---
### 🎬 3 GUIONES VIRALES LISTOS PARA GRABAR

#### 📌 GUION 1 (Enfoque Error o Dolor Oculto):
- **Gancho [0-3s]:** [Acción visual llamativa] "Texto exacto"
- **Desarrollo [3-20s]:** [Indicación visual] "Texto exacto"
- **Cierre y CTA [20-30s]:** "Texto exacto"

#### 📌 GUION 2 (Enfoque Secreto o Curiosidad):
- **Gancho [0-3s]:** [Acción visual llamativa] "Texto exacto"
- **Desarrollo [3-20s]:** [Indicación visual] "Texto exacto"
- **Cierre y CTA [20-30s]:** "Texto exacto"

#### 📌 GUION 3 (Enfoque Hack o Acción Rápida):
- **Gancho [0-3s]:** [Acción visual llamativa] "Texto exacto"
- **Desarrollo [3-20s]:** [Indicación visual] "Texto exacto"
- **Cierre y CTA [20-30s]:** "Texto exacto"

=== DIVISION_LEADS ===

### ⭐ NIVEL 1: ALTO VALOR (IMÁN MASIVO)
- **Nombre Irresistible:** [Título magnético]
- **Promesa Central:** [Gran beneficio]
- **Formato:** (PDF / Bóveda / Notion / Video Masterclass)
- **Contenido del Recurso:** [Índice de 5 puntos clave]

---
### 🎯 NIVEL 2: ESPECÍFICO (SOLUCIÓN TÁCTICA)
- **Nombre de la Herramienta:** [Plantilla, Calculadora, Checklist o Swipe File]
- **Dolor Concreto que Resuelve:** [Qué dolor puntual elimina]
- **Qué incluye exactamente:** [Estructura del recurso]

---
### 👑 NIVEL 3: PERSONALIZADO (VENTA / AUDITORÍA 1 A 1)
- **Nombre de la Oferta:** [Auditoría Express, Diagnóstico, Sesión]
- **Propuesta de Transformación:** [Resultado tangible]
- **Guion de Cierre (CTA):** [Palabras exactas para llamada a la acción]
"""
    res = client.chat.completions.create(
        model=MODELO_LLM,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4
    )
    
    contenido = res.choices[0].message.content
    if "=== DIVISION_LEADS ===" in contenido:
        partes = contenido.split("=== DIVISION_LEADS ===")
        return partes[0].strip(), partes[1].strip()
    return contenido.strip(), "No se pudo formatear por separado."

# ==============================================================
# VISTA PRINCIPAL
# ==============================================================
tab_link, tab_file = st.tabs(["🔗 Enlace de Redes", "📁 Subir Archivo"])

with tab_link:
    url = st.text_input("Enlace de YouTube, TikTok o Instagram:")
    traducir_link = st.checkbox("Traducir al español latino si viene en otro idioma", value=True, key="chk_link")
    
    if st.button("Transcribir", type="primary", key="btn_trans"):
        if not GROQ_API_KEY.strip():
            st.error("Ingresa tu Groq API Key en la barra lateral.")
        elif not url.strip():
            st.warning("Pega un enlace válido.")
        else:
            archivo_temporal = None
            try:
                with st.spinner("⚡ Descargando audio..."):
                    archivo_temporal = extraer_audio_rapido(url.strip())
                with st.spinner("🎙️ Transcribiendo con Whisper Turbo..."):
                    texto_crudo = transcribir_con_groq(archivo_temporal, GROQ_API_KEY)

                if not texto_crudo.strip():
                    st.warning("No se detectó voz audible en el video.")
                else:
                    with st.spinner("✨ Formateando texto..."):
                        orig, trad = procesar_texto_paralelo(texto_crudo, traducir_link, GROQ_API_KEY)
                        st.session_state.texto_original = orig
                        st.session_state.texto_traducido = trad
                        st.session_state.guiones_generados = None
                        st.session_state.lead_magnets_generados = None
            except Exception as e:
                st.error(f"Error: {e}")
            finally:
                if archivo_temporal and os.path.exists(archivo_temporal):
                    try:
                        os.remove(archivo_temporal)
                    except Exception:
                        pass

with tab_file:
    archivo_subido = st.file_uploader("Arrastra tu archivo (.mp3, .mp4, .m4a, .wav):", type=["mp3", "mp4", "m4a", "wav"])
    traducir_f = st.checkbox("Traducir al español latino", value=True, key="chk_f")
    
    if archivo_subido and st.button("Transcribir Archivo", key="btn_sub_file"):
        if not GROQ_API_KEY.strip():
            st.error("Ingresa tu Groq API Key en la barra lateral.")
        else:
            try:
                with st.spinner("🎙️ Transcribiendo desde memoria..."):
                    buffer_audio = archivo_subido.getvalue()
                    texto_crudo = transcribir_con_groq(buffer_audio, GROQ_API_KEY, nombre_archivo=archivo_subido.name)

                if not texto_crudo.strip():
                    st.warning("No se detectó voz.")
                else:
                    with st.spinner("✨ Formateando..."):
                        orig, trad = procesar_texto_paralelo(texto_crudo, traducir_f, GROQ_API_KEY)
                        st.session_state.texto_original = orig
                        st.session_state.texto_traducido = trad
                        st.session_state.guiones_generados = None
                        st.session_state.lead_magnets_generados = None
                        st.success("¡Transcripción completada!")
            except Exception as e:
                st.error(f"Error: {e}")

if st.session_state.texto_original:
    st.markdown("---")
    col_nicho, col_btn_gen = st.columns([3, 1])
    with col_nicho:
        nicho_input = st.text_input(
            "Tu tema, producto o servicio:",
            placeholder="Ej: Asesoría financiera, Café artesanal...",
            label_visibility="collapsed"
        )
    with col_btn_gen:
        btn_generar_estrategia = st.button("Generar Estrategia", type="primary", key="btn_gen_estrategia", use_container_width=True)

    if btn_generar_estrategia:
        if not nicho_input.strip():
            st.warning("Escribe tu tema o servicio para generar la estrategia.")
        else:
            texto_base = st.session_state.texto_traducido or st.session_state.texto_original
            with st.spinner("🧠 Diseñando 3 guiones y 3 lead magnets..."):
                try:
                    guiones, leads = generar_guiones_y_leadmagnets(texto_base, nicho_input.strip(), GROQ_API_KEY)
                    st.session_state.guiones_generados = guiones
                    st.session_state.lead_magnets_generados = leads
                except Exception as e:
                    st.error(f"Error: {e}")

    tab_out_trans, tab_out_guiones, tab_out_leads = st.tabs([
        "📝 Transcripción", 
        "🎬 3 Guiones Virales", 
        "🎁 3 Lead Magnets"
    ])

    with tab_out_trans:
        if st.session_state.texto_traducido:
            sub_es, sub_orig = st.tabs(["🇪🇸 Español Latino", "🌐 Original"])
            with sub_es:
                boton_copiar(st.session_state.texto_traducido, id_btn="cp_es")
                st.text_area("Español", value=st.session_state.texto_traducido, height=250, label_visibility="collapsed")
            with sub_orig:
                boton_copiar(st.session_state.texto_original, id_btn="cp_orig")
                st.text_area("Original", value=st.session_state.texto_original, height=250, label_visibility="collapsed")
        else:
            boton_copiar(st.session_state.texto_original, id_btn="cp_solo")
            st.text_area("Transcripción", value=st.session_state.texto_original, height=250, label_visibility="collapsed")

    with tab_out_guiones:
        if st.session_state.guiones_generados:
            boton_copiar(st.session_state.guiones_generados, id_btn="cp_guiones")
            st.markdown(st.session_state.guiones_generados)
        else:
            st.info("💡 Escribe tu producto o servicio arriba y presiona **Generar Estrategia**.")

    with tab_out_leads:
        if st.session_state.lead_magnets_generados:
            boton_copiar(st.session_state.lead_magnets_generados, id_btn="cp_leads")
            st.markdown(st.session_state.lead_magnets_generados)
        else:
            st.info("💡 Escribe tu producto o servicio arriba y presiona **Generar Estrategia**.")
