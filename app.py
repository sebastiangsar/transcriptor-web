import os
import re
import json
import requests
import streamlit as st
import streamlit.components.v1 as components
import yt_dlp
from groq import Groq

# 1. Configuración de página
st.set_page_config(page_title="Transcriptor & Creador de Guiones", page_icon="🎬", layout="centered")

# Activa FFmpeg: en la nube usa packages.txt; en local usa static_ffmpeg
try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except Exception:
    pass

st.title("🎬 Transcriptor & Creador de Guiones Virales")
st.caption("YouTube, TikTok e Instagram — Whisper y Llama en Groq")

# Memoria de sesión
for k in ["texto_original", "texto_traducido", "guiones_generados", "groq_chat_model"]:
    if k not in st.session_state:
        st.session_state[k] = None

# Manejo seguro de la API Key
GROQ_API_KEY = ""
try:
    if "GROQ_API_KEY" in st.secrets:
        GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except Exception:
    pass

def buscar_archivo_cookies():
    for n in ["cookies.txt", "cookies.txt.txt", "instagram.com_cookies.txt"]:
        if os.path.exists(n):
            return n
    return None

def obtener_modelo_activo(client):
    """Detecta el modelo de texto activo en tu cuenta para evitar errores 404"""
    if st.session_state.groq_chat_model:
        return st.session_state.groq_chat_model

    modelo_detectado = None
    try:
        modelos_api = [m.id for m in client.models.list().data]
        chat_models = [
            m for m in modelos_api 
            if not any(x in m.lower() for x in ["whisper", "guard", "audio", "orpheus", "embed", "tts", "stt"])
        ]
        prioridad = [
            "openai/gpt-oss-120b", "openai/gpt-oss-20b",
            "qwen/qwen3.8-27b", "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant"
        ]
        for p in prioridad:
            if p in chat_models:
                modelo_detectado = p
                break
        if not modelo_detectado and chat_models:
            modelo_detectado = chat_models[0]
    except Exception:
        pass

    if not modelo_detectado:
        modelo_detectado = "openai/gpt-oss-120b"

    st.session_state.groq_chat_model = modelo_detectado
    return modelo_detectado

# ==============================================================
# BARRA LATERAL: CONFIGURACIÓN + LEAD MAGNETS
# ==============================================================
with st.sidebar:
    st.header("⚙️ Configuración")
    if not GROQ_API_KEY:
        GROQ_API_KEY = st.text_input("Groq API Key:", type="password", placeholder="gsk_...")
    
    st.subheader("Sesión de Instagram")
    cookie_subida = st.file_uploader("Sube cookies.txt aquí:", type=["txt"], key="up_cookies")
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
        st.warning("Sin cookies.")

    st.markdown("---")
    st.header("🎁 Recursos Gratuitos")
    with st.expander("⭐ Nivel 1: Alto Valor"):
        st.markdown("**La Bóveda de las 50 Fórmulas Virales**")
        st.button("Descargar", key="lm1")
    with st.expander("🎯 Nivel 2: Específico"):
        st.markdown("**Kit de 30 Ganchos + Plantilla**")
        st.button("Obtener", key="lm2")
    with st.expander("👑 Nivel 3: Personalizado"):
        st.markdown("**Auditoría 1 a 1 de tu Cuenta**")
        st.text_input("Tu @usuario:", placeholder="@tucuenta")
        st.button("Solicitar", key="lm3")

def boton_copiar(texto, id_btn="copiar"):
    if not texto:
        return
    texto_json = json.dumps(texto)
    html_code = f"""
    <button id="{id_btn}" onclick="copiar_{id_btn}()" style="
        background-color: #10b981;
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 6px;
        font-weight: 600;
        cursor: pointer;
        font-size: 14px;
        display: inline-flex;
        align-items: center;
        gap: 6px;
    ">📋 Copiar</button>
    <span id="msg_{id_btn}" style="margin-left: 10px; color: #10b981; font-weight: bold; display: none;">✅ ¡Copiado!</span>

    <script>
    function copiar_{id_btn}() {{
        const text = {texto_json};
        navigator.clipboard.writeText(text).then(() => {{
            const msg = document.getElementById('msg_{id_btn}');
            msg.style.display = 'inline';
            setTimeout(() => {{ msg.style.display = 'none'; }}, 2500);
        }}).catch(err => {{
            alert('Error al copiar: ' + err);
        }});
    }}
    </script>
    """
    components.html(html_code, height=45)

def descargar_tiktok_directo(enlace):
    try:
        resp = requests.post("https://www.tikwm.com/api/", data={"url": enlace}, timeout=20)
        data = resp.json()
        if data.get("code") == 0 and "data" in data:
            media_url = data["data"].get("music") or data["data"].get("play")
            if media_url:
                if media_url.startswith("/"):
                    media_url = f"https://www.tikwm.com{media_url}"
                r = requests.get(media_url, timeout=40)
                ruta = "temp_audio.mp3"
                with open(ruta, "wb") as f:
                    f.write(r.content)
                return ruta
    except Exception:
        pass
    return None

def extraer_audio(enlace):
    if "tiktok.com" in enlace:
        tk = descargar_tiktok_directo(enlace)
        if tk:
            return tk

    opciones = {
        'format': 'ba/b',
        'outtmpl': 'temp_audio.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '32',
        }],
        'extractor_args': {
            'youtube': {'player_client': ['android', 'ios', 'web_creator']}
        },
        'quiet': True,
        'no_warnings': True,
    }

    cookies_file = buscar_archivo_cookies()
    if cookies_file:
        opciones['cookiefile'] = cookies_file

    with yt_dlp.YoutubeDL(opciones) as ydl:
        ydl.download([enlace])

    return "temp_audio.mp3"

def transcribir_con_groq(ruta_archivo, api_key):
    client = Groq(api_key=api_key)
    with open(ruta_archivo, "rb") as file:
        transcription = client.audio.transcriptions.create(
            file=(ruta_archivo, file.read()),
            model="whisper-large-v3-turbo",
            response_format="text",
            temperature=0.0
        )
    return transcription

def formatear_y_traducir(texto, api_key, traducir=True):
    client = Groq(api_key=api_key)
    modelo = obtener_modelo_activo(client)
    
    if traducir:
        instruccion = "Traduce el texto al español latino neutro en párrafos limpios separados por salto doble. Devuelve solo el texto."
    else:
        instruccion = "Organiza el texto en párrafos limpios separados por doble salto de línea. Devuelve solo el texto."

    try:
        res = client.chat.completions.create(
            model=modelo,
            messages=[
                {"role": "system", "content": instruccion},
                {"role": "user", "content": texto}
            ],
            temperature=0.3
        )
        return res.choices[0].message.content
    except Exception:
        return texto

def generar_ideas_y_guiones(transcripcion, nicho_usuario, api_key):
    client = Groq(api_key=api_key)
    modelo = obtener_modelo_activo(client)
    
    prompt_sistema = (
        "Eres un estratega de contenido viral. Desarma la fórmula psicológica del video y genera 3 ideas con sus guiones adaptados al nicho.\n\n"
        "ESTRUCTURA DE RESPUESTA:\n"
        "### 🧠 1. RADIOGRAFÍA DE LA FÓRMULA VIRAL\n"
        "- **El Gancho (Hook):** Técnica psicológica que usó y por qué retiene.\n"
        "- **Estructura de Retención:** Ritmo y manejo de tensión.\n"
        "- **Remate y CTA:** Estrategia de cierre.\n\n"
        "---\n"
        "### 💡 2. BANCO DE 3 IDEAS PARA TU NICHO\n"
        "- **Idea 1 (Error/Dolor):** Concepto claro.\n"
        "- **Idea 2 (Secreto/Curiosidad):** Concepto claro.\n"
        "- **Idea 3 (Hack/Acción Rápida):** Concepto claro.\n\n"
        "---\n"
        "### 🎬 3. GUIONES COMPLETOS LISTOS PARA GRABAR\n\n"
        "#### 📌 GUION 1 (Basado en Idea 1):\n"
        "- **Gancho (0-3s):** [Acción visual] \"Texto exacto\"\n"
        "- **Desarrollo (3-20s):** [Acción visual] \"Texto exacto\"\n"
        "- **Cierre y CTA (20-30s):** \"Texto exacto\"\n\n"
        "#### 📌 GUION 2 (Basado en Idea 2):\n"
        "- **Gancho (0-3s):** [Acción visual] \"Texto exacto\"\n"
        "- **Desarrollo (3-20s):** [Acción visual] \"Texto exacto\"\n"
        "- **Cierre y CTA (20-30s):** \"Texto exacto\"\n\n"
        "#### 📌 GUION 3 (Basado en Idea 3):\n"
        "- **Gancho (0-3s):** [Acción visual] \"Texto exacto\"\n"
        "- **Desarrollo (3-20s):** [Acción visual] \"Texto exacto\"\n"
        "- **Cierre y CTA (20-30s):** \"Texto exacto\""
    )
    res = client.chat.completions.create(
        model=modelo,
        messages=[
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": f"REFERENCIA:\n{transcripcion}\n\nNICHO:\n{nicho_usuario}"}
        ],
        temperature=0.4
    )
    return res.choices[0].message.content

# ==============================================================
# PESTAÑAS: ENLACE O ARCHIVO
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
                with st.spinner("Descargando audio..."):
                    archivo_temporal = extraer_audio(url.strip())
                with st.spinner("Transcribiendo con Groq Whisper..."):
                    texto_crudo = transcribir_con_groq(archivo_temporal, GROQ_API_KEY)

                if not texto_crudo:
                    st.warning("No se detectó voz.")
                else:
                    st.session_state.texto_original = formatear_y_traducir(texto_crudo, GROQ_API_KEY, traducir=False)
                    if traducir_link:
                        st.session_state.texto_traducido = formatear_y_traducir(texto_crudo, GROQ_API_KEY, traducir=True)
                    else:
                        st.session_state.texto_traducido = None
                    st.session_state.guiones_generados = None
            except Exception as e:
                st.error(f"{e}")
            finally:
                if archivo_temporal and os.path.exists(archivo_temporal):
                    try:
                        os.remove(archivo_temporal)
                    except Exception:
                        pass

with tab_file:
    archivo_subido = st.file_uploader("Arrastra tu archivo aquí (.mp3, .mp4, etc.):", type=["mp3", "mp4", "m4a", "wav"])
    traducir_f = st.checkbox("Traducir al español latino", value=True, key="chk_f")
    
    if archivo_subido and st.button("Transcribir", key="btn_sub_file"):
        if not GROQ_API_KEY.strip():
            st.error("Ingresa tu Groq API Key en la barra lateral.")
        else:
            nombre_temp = f"temp_subido_{archivo_subido.name}"
            try:
                with open(nombre_temp, "wb") as f:
                    f.write(archivo_subido.getbuffer())
                with st.spinner("Transcribiendo audio..."):
                    texto_crudo = transcribir_con_groq(nombre_temp, GROQ_API_KEY)
                st.session_state.texto_original = formatear_y_traducir(texto_crudo, GROQ_API_KEY, traducir=False)
                if traducir_f:
                    st.session_state.texto_traducido = formatear_y_traducir(texto_crudo, GROQ_API_KEY, traducir=True)
                else:
                    st.session_state.texto_traducido = None
                st.success("¡Transcripción lista!")
            except Exception as e:
                st.error(f"Error: {e}")
            finally:
                if os.path.exists(nombre_temp):
                    try:
                        os.remove(nombre_temp)
                    except Exception:
                        pass

# ==============================================================
# RESULTADOS Y LABORATORIO DE GUIONES
# ==============================================================
if st.session_state.texto_original:
    st.markdown("---")
    st.subheader("📝 Transcripción del Video")
    if st.session_state.texto_traducido:
        tab_es, tab_orig = st.tabs(["🇪🇸 Español Latino", "🌐 Original"])
        with tab_es:
            boton_copiar(st.session_state.texto_traducido, id_btn="cp_es")
            st.text_area("Español", value=st.session_state.texto_traducido, height=200)
        with tab_orig:
            boton_copiar(st.session_state.texto_original, id_btn="cp_orig")
            st.text_area("Original", value=st.session_state.texto_original, height=200)
    else:
        boton_copiar(st.session_state.texto_original, id_btn="cp_solo")
        st.text_area("Transcripción", value=st.session_state.texto_original, height=200)

    st.markdown("---")
    st.subheader("🎯 Laboratorio de Guiones (Ingeniería Inversa)")
    nicho_input = st.text_input("Tu tema, producto o nicho:", placeholder="Ej: Negocios digitales, Nutrición...")
    
    if st.button("Generar", type="primary", key="btn_gen_guiones"):
        if not nicho_input.strip():
            st.warning("Indica tu tema o nicho.")
        else:
            texto_base = st.session_state.texto_traducido or st.session_state.texto_original
            try:
                with st.spinner("Desarmando fórmula y redactando 3 guiones..."):
                    st.session_state.guiones_generados = generar_ideas_y_guiones(texto_base, nicho_input.strip(), GROQ_API_KEY)
            except Exception as e:
                st.error(f"Error: {e}")

    if st.session_state.guiones_generados:
        st.success("¡Guiones generados!")
        boton_copiar(st.session_state.guiones_generados, id_btn="cp_guiones")
        st.markdown(st.session_state.guiones_generados)
