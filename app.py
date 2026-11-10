import os
import re
import json
import tempfile
from concurrent.futures import ThreadPoolExecutor
import requests
import streamlit as st
import streamlit.components.v1 as components
import yt_dlp
from groq import Groq

st.set_page_config(page_title="Ingeniería Inversa Viral", page_icon="🧠", layout="wide")

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

claves_estado = [
    "texto_original", "texto_traducido", 
    "res_analisis", "res_g1", "res_g2", "res_g3"
]
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
    
    st.subheader("Cookies de Sesión")
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
            "Devuelve únicamente el texto traducido sin notas ni introducciones."
        )
    else:
        instruccion = (
            "Organiza el siguiente texto en párrafos limpios separados por doble salto de línea. "
            "Mantén estrictamente el idioma original de la transcripción, sin traducir palabras. "
            "Devuelve únicamente el texto organizado."
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
    
    prompt = f"""Eres un director creativo y neuroestratega viral de primer nivel.
Analiza la siguiente TRANSCRIPCIÓN de referencia y aplica sus técnicas a la NUEVA IDEA del usuario.

TUS TAREAS:
1. Evalúa el PUNTAJE DE VIRALIDAD (de 0 a 100) explicando los mecanismos psicológicos y gatillos de dopamina.
2. Escribe 3 GUIONES VIRALES COMPLETOS adaptados a la nueva idea, cada uno con un enfoque de Hook diferente.

CADA GUION DEBE ENTREGARSE COMO UNA TABLA MARKDOWN EXACTA DE 3 COLUMNAS:
| Sección | Dirección (Qué hacer) | Qué dice (Guion verbal) |

Filas obligatorias en cada tabla:
- Hook (0-3s)
- Loop de Curiosidad (3-7s)
- Desarrollo (7-20s)
- Recompensa (20-25s)
- Cierre y CTA (25-30s)

En "Dirección": explica qué debe hacer el usuario con su cuerpo, mirada, encuadre o elementos en pantalla.
En "Qué dice": escribe el texto exacto, limpio y persuasivo que debe decir el usuario.

TRANSCRIPCIÓN:
\"{transcripcion}\"

NUEVA IDEA O PRODUCTO DEL USUARIO:
\"{idea_usuario}\"

FORMATO DE ENTREGA OBLIGATORIO:
Usa estrictamente los delimitadores señalados:

<<<ANALISIS>>>
### 📊 Puntaje de Viralidad: [X]/100
- **Mecanismos Psicológicos:** (Sesgos, instintos primarios y gatillos detectados)
- **Estructura de Retención:** (Curva de atención y apertura de bucles)
- **Efectividad del Cierre:** (Estrategia de conversión)

<<<GUION_1>>>
### 📌 Guion 1: Enfoque Dolor / Error Oculto
| Sección | Dirección (Qué hacer) | Qué dice (Guion verbal) |
| :--- | :--- | :--- |
| **Hook (0-3s)** | [Acción visual llamativa] | "Texto hablado" |
| **Loop de Curiosidad (3-7s)** | [Lenguaje corporal/acción] | "Texto hablado" |
| **Desarrollo (7-20s)** | [Indicación de cámara/plano] | "Texto hablado" |
| **Recompensa (20-25s)** | [Demostración/revelación] | "Texto hablado" |
| **Cierre y CTA (25-30s)** | [Gesto final y llamada a acción] | "Texto hablado" |

<<<GUION_2>>>
### 📌 Guion 2: Enfoque Curiosidad Extrema / Secreto Revelado
| Sección | Dirección (Qué hacer) | Qué dice (Guion verbal) |
| :--- | :--- | :--- |
| **Hook (0-3s)** | [Acción visual llamativa] | "Texto hablado" |
| **Loop de Curiosidad (3-7s)** | [Lenguaje corporal/acción] | "Texto hablado" |
| **Desarrollo (7-20s)** | [Indicación de cámara/plano] | "Texto hablado" |
| **Recompensa (20-25s)** | [Demostración/revelación] | "Texto hablado" |
| **Cierre y CTA (25-30s)** | [Gesto final y llamada a acción] | "Texto hablado" |

<<<GUION_3>>>
### 📌 Guion 3: Enfoque Contraintuitivo / Quiebre de Creencia
| Sección | Dirección (Qué hacer) | Qué dice (Guion verbal) |
| :--- | :--- | :--- |
| **Hook (0-3s)** | [Acción visual llamativa] | "Texto hablado" |
| **Loop de Curiosidad (3-7s)** | [Lenguaje corporal/acción] | "Texto hablado" |
| **Desarrollo (7-20s)** | [Indicación de cámara/plano] | "Texto hablado" |
| **Recompensa (20-25s)** | [Demostración/revelación] | "Texto hablado" |
| **Cierre y CTA (25-30s)** | [Gesto final y llamada a acción] | "Texto hablado" |
"""
    res = client.chat.completions.create(
        model=modelo,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    
    texto_completo = res.choices[0].message.content

    def extraer_seccion(etiqueta, siguiente_etiqueta=None):
        patron = rf"<<<{etiqueta}>>>(.*?)(?=<<<{siguiente_etiqueta}>>>|$)" if siguiente_etiqueta else rf"<<<{etiqueta}>>>(.*)"
        coincidencia = re.search(patron, texto_completo, re.DOTALL)
        return coincidencia.group(1).strip() if coincidencia else ""

    analisis = extraer_seccion("ANALISIS", "GUION_1")
    g1 = extraer_seccion("GUION_1", "GUION_2")
    g2 = extraer_seccion("GUION_2", "GUION_3")
    g3 = extraer_seccion("GUION_3")

    if not analisis:
        analisis = texto_completo

    return analisis, g1, g2, g3

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
                    with st.spinner("✨ Estructurando párrafos..."):
                        orig, trad = procesar_transcripcion(texto_crudo, GROQ_API_KEY)
                        st.session_state.texto_original = orig
                        st.session_state.texto_traducido = trad
                        st.session_state.res_analisis = None
                        st.session_state.res_g1 = None
                        st.session_state.res_g2 = None
                        st.session_state.res_g3 = None
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
                with st.spinner("🎙️ Transcribiendo desde memoria..."):
                    buffer_audio = archivo_subido.getvalue()
                    texto_crudo = transcribir_con_groq(buffer_audio, GROQ_API_KEY, nombre_archivo=archivo_subido.name)

                if not texto_crudo.strip():
                    st.warning("No se detectó voz.")
                else:
                    with st.spinner("✨ Estructurando párrafos..."):
                        orig, trad = procesar_transcripcion(texto_crudo, GROQ_API_KEY)
                        st.session_state.texto_original = orig
                        st.session_state.texto_traducido = trad
                        st.session_state.res_analisis = None
                        st.session_state.res_g1 = None
                        st.session_state.res_g2 = None
                        st.session_state.res_g3 = None
                        st.success("¡Transcripción lista!")
            except Exception as e:
                st.error(f"Error: {e}")

# ==============================================================
# SALIDA: TRANSCRIPCIONES + INGENIERÍA INVERSA
# ==============================================================
if st.session_state.texto_original:
    st.markdown("---")
    st.subheader("📝 Transcripción del Video")
    
    tab_es, tab_orig = st.tabs(["🇪🇸 Español Latinoamericano", "🌐 Idioma Original"])
    with tab_es:
        boton_copiar(st.session_state.texto_traducido, id_btn="cp_es")
        st.text_area("Texto en Español", value=st.session_state.texto_traducido, height=200, label_visibility="collapsed")
    with tab_orig:
        boton_copiar(st.session_state.texto_original, id_btn="cp_orig")
        st.text_area("Texto Original", value=st.session_state.texto_original, height=200, label_visibility="collapsed")

    st.markdown("---")
    st.subheader("🔬 Aplicar Ingeniería Inversa a Nueva Idea")
    
    idea_input = st.text_area(
        "Describe tu nueva idea, producto o servicio:",
        placeholder="Ej: Asesoría de visas, Ropa deportiva personalizada, Clases de oratoria...",
        height=75
    )

    if st.button("🚀 Aplicar Ingeniería Inversa", type="primary", use_container_width=True):
        if not idea_input.strip():
            st.warning("Escribe primero tu idea, producto o servicio.")
        else:
            base_texto = st.session_state.texto_traducido or st.session_state.texto_original
            with st.spinner("🧠 Analizando psicología viral y creando guiones de 3 columnas..."):
                try:
                    an, g1, g2, g3 = ejecutar_ingenieria_inversa(base_texto, idea_input.strip(), GROQ_API_KEY)
                    st.session_state.res_analisis = an
                    st.session_state.res_g1 = g1
                    st.session_state.res_g2 = g2
                    st.session_state.res_g3 = g3
                except Exception as e:
                    st.error(f"Error procesando la ingeniería inversa: {e}")

    # RESULTADOS ORDENADOS
    if st.session_state.res_analisis:
        st.markdown("---")
        
        # 1. Análisis Psicológico y Puntaje
        st.subheader("🧠 Análisis Psicológico & Puntaje de Viralidad")
        boton_copiar(st.session_state.res_analisis, id_btn="cp_an")
        st.info(st.session_state.res_analisis)

        # 2. Los 3 Guiones en 3 Pestañas con sus Tablas de 3 Columnas
        st.markdown("### 🎬 3 Guiones Virales Estructurados")
        tab_g1, tab_g2, tab_g3 = st.tabs([
            "📌 Guion 1: Hook de Dolor", 
            "📌 Guion 2: Hook de Curiosidad", 
            "📌 Guion 3: Hook Contraintuitivo"
        ])

        with tab_g1:
            if st.session_state.res_g1:
                boton_copiar(st.session_state.res_g1, id_btn="cp_g1")
                st.markdown(st.session_state.res_g1)

        with tab_g2:
            if st.session_state.res_g2:
                boton_copiar(st.session_state.res_g2, id_btn="cp_g2")
                st.markdown(st.session_state.res_g2)

        with tab_g3:
            if st.session_state.res_g3:
                boton_copiar(st.session_state.res_g3, id_btn="cp_g3")
                st.markdown(st.session_state.res_g3)
