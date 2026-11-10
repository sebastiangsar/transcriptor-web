import os
import json
import tempfile
from concurrent.futures import ThreadPoolExecutor
import requests
import streamlit as st
import streamlit.components.v1 as components
import yt_dlp
from groq import Groq

st.set_page_config(page_title="Ingeniería Inversa de Videos Virales", page_icon="🧠", layout="wide")

@st.cache_resource(show_spinner=False)
def get_groq_client(api_key: str) -> Groq:
    return Groq(api_key=api_key)

@st.cache_data(show_spinner=False)
def obtener_modelo_activo(api_key: str) -> str:
    try:
        client = Groq(api_key=api_key)
        modelos_api = [m.id for m in client.models.list().data]
        chat_models = [
            m for m in modelos_api 
            if not any(x in m.lower() for x in ["whisper", "guard", "audio", "orpheus", "embed", "tts", "stt", "safeguard"])
        ]
        prioridad = [
            "openai/gpt-oss-120b", "openai/gpt-oss-20b",
            "qwen/qwen3.8-27b", "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant"
        ]
        for p in prioridad:
            if p in chat_models:
                return p
        if chat_models:
            return chat_models[0]
    except Exception:
        pass
    return "openai/gpt-oss-20b"

claves_estado = ["texto_original", "texto_traducido", "analisis_col1", "analisis_col2", "analisis_col3"]
for k in claves_estado:
    if k not in st.session_state:
        st.session_state[k] = None

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

with st.sidebar:
    st.header("⚙️ Configuración")
    if not GROQ_API_KEY:
        GROQ_API_KEY = st.text_input("Groq API Key:", type="password", placeholder="gsk_...")
    
    st.subheader("Cookies (Instagram/TikTok)")
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
    if st.button("Limpiar todo", use_container_width=True):
        for k in claves_estado:
            st.session_state[k] = None
        st.rerun()

st.title("🧠 Transcriptor & Ingeniería Inversa Viral")
st.caption("Decodifica la psicología de videos virales y replícala en cualquier producto o servicio.")

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
    modelo = obtener_modelo_activo(api_key)
    
    if traducir:
        instruccion = (
            "Traduce el siguiente texto al español latinoamericano neutro. "
            "Organízalo en párrafos claros y legibles separados por doble salto de línea. "
            "Devuelve únicamente el texto traducido sin introducciones ni notas."
        )
    else:
        instruccion = (
            "Organiza el siguiente texto en párrafos limpios y legibles separados por doble salto de línea. "
            "Conserva estrictamente el idioma original sin traducir ninguna palabra. "
            "Devuelve únicamente el texto estructurado."
        )

    try:
        res = client.chat.completions.create(
            model=modelo,
            messages=[
                {"role": "system", "content": instruccion},
                {"role": "user", "content": texto}
            ],
            temperature=0.2
        )
        return res.choices[0].message.content.strip()
    except Exception:
        return texto

def procesar_transcripcion(texto_crudo: str, api_key: str):
    with ThreadPoolExecutor(max_workers=2) as executor:
        f_orig = executor.submit(formatear_o_traducir_texto, texto_crudo, api_key, False)
        f_trad = executor.submit(formatear_o_traducir_texto, texto_crudo, api_key, True)
        return f_orig.result(), f_trad.result()

def ejecutar_ingenieria_inversa(transcripcion: str, idea_usuario: str, api_key: str):
    client = get_groq_client(api_key)
    modelo = obtener_modelo_activo(api_key)
    
    prompt = f"""Eres un neurocientífico aplicado al marketing, estratega de contenido viral y copywriter de clase mundial.
Analiza la siguiente TRANSCRIPCIÓN VIRAL con ingeniería inversa profunda para identificar:
- Mecanismos psicológicos exactos (sesgos, disparadores de dopamina, quiebres de patrón).
- Estructura de retención y curvas de curiosidad.
- El entendimiento de la naturaleza humana que hace que la gente no pueda dejar de mirar.

Luego, APLICA EXACTAMENTE ESA MISMA FÓRMULA a la NUEVA IDEA del usuario (puede ser producto físico, digital, servicio, marca personal, etc.).

TRANSCRIPCIÓN ORIGINAL:
\"{transcripcion}\"

NUEVA IDEA / PRODUCTO / SERVICIO DEL USUARIO:
\"{idea_usuario}\"

ENTREGA TU RESPUESTA OBLIGATORIAMENTE EN 3 BLOQUES SEPARADOS POR "=== DIVISION ===":

BLOQUE 1: DESGLOSE DE INGENIERÍA INVERSA
- **El Gancho Psicológico:** Qué sesgo o instinto primario activa en los primeros 3 segundos.
- **Estructura de Retención:** Cómo mantiene la tensión y abre bucles de curiosidad.
- **Palancas de Naturaleza Humana:** Miedo, estatus, atajo, validación o curiosidad morbosa usada.
- **Mecánica del Cierre:** Por qué la llamada a la acción funciona.

=== DIVISION ===

BLOQUE 2: NUEVO GUION VIRAL ADAPTADO
- **Gancho (Hook) [0-3s]:** "Texto exacto de alto impacto visual y verbal adaptado a {idea_usuario}"
- **Desarrollo (Retención) [3-25s]:** "Texto exacto del cuerpo manteniendo la fórmula psicológica del original"
- **Llamada a la Acción (CTA) [25-30s]:** "Texto exacto para convertir la atención en comentarios, seguidores o clientes"

=== DIVISION ===

BLOQUE 3: DIRECCIÓN DE ATENCIÓN Y EDICIÓN
- **Disruptor Visual Inicial:** Qué debe verse en pantalla exactamente en el segundo 0 para detener el scroll.
- **Ritmo y Lenguaje Corporal:** Tono de voz, micro-gestos y energía requerida.
- **Edición y Quiebres de Patrón:** Cambios de plano, sonidos y textos en pantalla necesarios para que nadie se vaya.
"""
    res = client.chat.completions.create(
        model=modelo,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    
    contenido = res.choices[0].message.content
    partes = contenido.split("=== DIVISION ===")
    if len(partes) >= 3:
        return partes[0].strip(), partes[1].strip(), partes[2].strip()
    return contenido.strip(), "Error al dividir columnas", "Error al dividir columnas"

# ==============================================================
# ENTRADA
# ==============================================================
tab_link, tab_file = st.tabs(["🔗 Enlace de Redes", "📁 Subir Archivo"])

with tab_link:
    url = st.text_input("Enlace de YouTube, TikTok o Instagram:")
    if st.button("Transcribir Video", type="primary", key="btn_trans"):
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
                    st.warning("No se detectó voz audible.")
                else:
                    with st.spinner("✨ Procesando idiomas y párrafos..."):
                        orig, trad = procesar_transcripcion(texto_crudo, GROQ_API_KEY)
                        st.session_state.texto_original = orig
                        st.session_state.texto_traducido = trad
                        st.session_state.analisis_col1 = None
                        st.session_state.analisis_col2 = None
                        st.session_state.analisis_col3 = None
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
    if archivo_subido and st.button("Transcribir Archivo Subido", key="btn_sub_file"):
        if not GROQ_API_KEY.strip():
            st.error("Ingresa tu Groq API Key en la barra lateral.")
        else:
            try:
                with st.spinner("🎙️ Transcribiendo audio en memoria..."):
                    buffer_audio = archivo_subido.getvalue()
                    texto_crudo = transcribir_con_groq(buffer_audio, GROQ_API_KEY, nombre_archivo=archivo_subido.name)

                if not texto_crudo.strip():
                    st.warning("No se detectó voz.")
                else:
                    with st.spinner("✨ Estructurando idiomas y párrafos..."):
                        orig, trad = procesar_transcripcion(texto_crudo, GROQ_API_KEY)
                        st.session_state.texto_original = orig
                        st.session_state.texto_traducido = trad
                        st.session_state.analisis_col1 = None
                        st.session_state.analisis_col2 = None
                        st.session_state.analisis_col3 = None
                        st.success("¡Transcripción completada!")
            except Exception as e:
                st.error(f"Error: {e}")

# ==============================================================
# SALIDA: TRANSCRIPCIONES + INGENIERÍA INVERSA
# ==============================================================
if st.session_state.texto_original:
    st.markdown("---")
    st.subheader("📝 Transcripción del Video")
    
    # 2 PESTAÑAS: Español Latinoamericano e Idioma Original
    tab_es, tab_orig = st.tabs(["🇪🇸 Español Latinoamericano", "🌐 Idioma Original"])
    
    with tab_es:
        boton_copiar(st.session_state.texto_traducido, id_btn="cp_es")
        st.text_area("Texto en Español", value=st.session_state.texto_traducido, height=220, label_visibility="collapsed")
        
    with tab_orig:
        boton_copiar(st.session_state.texto_original, id_btn="cp_orig")
        st.text_area("Texto Original", value=st.session_state.texto_original, height=220, label_visibility="collapsed")

    # ==============================================================
    # SECCIÓN: APLICAR INGENIERÍA INVERSA A UNA NUEVA IDEA
    # ==============================================================
    st.markdown("---")
    st.subheader("🔬 Ingeniería Inversa Viral")
    st.caption("Extrae los métodos psicológicos del video y aplícalos a cualquier producto, servicio o idea.")

    idea_input = st.text_area(
        "Describe tu nueva idea, producto o servicio:",
        placeholder="Ej: Curso de finanzas personales, Venta de café orgánico por suscripción, Consultoría SEO, Agencia de diseño...",
        height=80
    )

    if st.button("🚀 Aplicar Ingeniería Inversa", type="primary", use_container_width=True):
        if not idea_input.strip():
            st.warning("Escribe primero tu idea, producto o servicio.")
        else:
            base_texto = st.session_state.texto_traducido or st.session_state.texto_original
            with st.spinner("🧠 Decodificando técnicas psicológicas y adaptando la fórmula..."):
                try:
                    c1, c2, c3 = ejecutar_ingenieria_inversa(base_texto, idea_input.strip(), GROQ_API_KEY)
                    st.session_state.analisis_col1 = c1
                    st.session_state.analisis_col2 = c2
                    st.session_state.analisis_col3 = c3
                except Exception as e:
                    st.error(f"Error procesando la ingeniería inversa: {e}")

    # CUADRO DE 3 COLUMNAS
    if st.session_state.analisis_col1:
        st.markdown("### 📊 Resultado de la Ingeniería Inversa")
        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("#### 🧠 1. Métodos y Psicología")
            boton_copiar(st.session_state.analisis_col1, id_btn="cp_col1")
            st.info(st.session_state.analisis_col1)

        with col2:
            st.markdown("#### 🎬 2. Nuevo Guion Viral")
            boton_copiar(st.session_state.analisis_col2, id_btn="cp_col2")
            st.success(st.session_state.analisis_col2)

        with col3:
            st.markdown("#### 👁️ 3. Retención y Edición")
            boton_copiar(st.session_state.analisis_col3, id_btn="cp_col3")
            st.warning(st.session_state.analisis_col3)
