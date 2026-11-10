import os
import re
import json
import requests
import streamlit as st
import streamlit.components.v1 as components
import yt_dlp
from groq import Groq

# Activa FFmpeg: en la nube usa el instalado por packages.txt; en Windows usa static_ffmpeg
try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except Exception:
    pass

st.set_page_config(page_title="Transcriptor Universal", page_icon="🎙️", layout="centered")

st.title("🎙️ Transcriptor Universal")
st.caption("YouTube, TikTok e Instagram — Whisper y Llama en Groq")

# Manejo seguro de la API Key (Secrets de Streamlit o barra lateral)
GROQ_API_KEY = ""
try:
    if "GROQ_API_KEY" in st.secrets:
        GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except Exception:
    pass

def buscar_archivo_cookies():
    nombres = ["cookies.txt", "cookies.txt.txt", "instagram.com_cookies.txt"]
    for n in nombres:
        if os.path.exists(n):
            return n
    return None

with st.sidebar:
    st.header("Configuracion")
    if not GROQ_API_KEY:
        GROQ_API_KEY = st.text_input("Groq API Key:", type="password", placeholder="gsk_...")
    
    st.subheader("Sesion de Instagram")
    cookie_subida = st.file_uploader("Sube tu archivo cookies.txt aqui:", type=["txt"])
    if cookie_subida:
        with open("cookies.txt", "wb") as f:
            f.write(cookie_subida.getbuffer())
        st.success("Archivo guardado!")
        st.rerun()

    archivo_cookies_encontrado = buscar_archivo_cookies()
    if archivo_cookies_encontrado:
        st.success(f"Sesion activa ({archivo_cookies_encontrado})")
    else:
        st.warning("Sin archivo de cookies.")

pestana1, pestana2 = st.tabs(["🔗 Enlace de Redes", "📁 Subir Archivo"])

def boton_copiar(texto, id_btn="copiar"):
    """Genera un boton de copia rapida al portapapeles"""
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
    ">📋 Copiar Texto</button>
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
        'format': 'm4a/bestaudio/best',
        'outtmpl': 'temp_audio.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
        }],
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

def obtener_modelo_texto_activo(client):
    preferidos = [
        "openai/gpt-oss-120b",
        "qwen/qwen3.8-27b",
        "llama-3.1-8b-instant",
        "llama3-8b-8192",
        "gemma2-9b-it"
    ]
    try:
        disponibles = [m.id for m in client.models.list().data]
        for p in preferidos:
            if p in disponibles:
                return p
        for m in disponibles:
            if "whisper" not in m.lower():
                return m
    except Exception:
        pass
    return "llama-3.1-8b-instant"

def formatear_y_traducir(texto, api_key, traducir=True):
    client = Groq(api_key=api_key)
    modelo = obtener_modelo_texto_activo(client)
    
    if traducir:
        instruccion = (
            "Eres un traductor y editor profesional. Traduce el texto al español de Latinoamérica neutro. "
            "Divide el texto en parrafos coherentes y comodos de leer, separados por saltos de linea dobles. "
            "Corrige la puntuacion. No agregues introducciones, titulos ni notas; devuelve solo el texto final."
        )
    else:
        instruccion = (
            "Eres un editor profesional. Organiza el texto en parrafos coherentes separados por saltos de linea dobles. "
            "Corrige la puntuacion basica sin cambiar palabras ni idioma. "
            "No agregues notas ni saludos; devuelve solo el texto formateado."
        )

    res = client.chat.completions.create(
        model=modelo,
        messages=[
            {"role": "system", "content": instruccion},
            {"role": "user", "content": texto}
        ],
        temperature=0.3
    )
    return res.choices[0].message.content

def mostrar_resultados(texto_original, quiere_traducir):
    st.success("¡Transcripción procesada con éxito!")
    
    texto_orig_formateado = texto_original
    texto_traducido = None

    try:
        with st.spinner("Organizando original en párrafos..."):
            texto_orig_formateado = formatear_y_traducir(texto_original, GROQ_API_KEY, traducir=False)
    except Exception:
        texto_orig_formateado = texto_original

    if quiere_traducir:
        try:
            with st.spinner("Traduciendo y organizando en párrafos al español latino..."):
                texto_traducido = formatear_y_traducir(texto_original, GROQ_API_KEY, traducir=True)
        except Exception as e:
            st.warning(f"No se pudo completar la traducción: {e}")

    if texto_traducido:
        tab_es, tab_orig = st.tabs(["🇪🇸 Traducción al Español Latino", "🌐 Idioma Original"])
        with tab_es:
            boton_copiar(texto_traducido, id_btn="btn_es")
            st.text_area("Español Latinoamericano", value=texto_traducido, height=320)
            st.download_button("📥 Descargar traducción (.txt)", data=texto_traducido, file_name="traduccion_espanol.txt", mime="text/plain")
        with tab_orig:
            boton_copiar(texto_orig_formateado, id_btn="btn_orig")
            st.text_area("Texto Original", value=texto_orig_formateado, height=320)
            st.download_button("📥 Descargar original (.txt)", data=texto_orig_formateado, file_name="original.txt", mime="text/plain")
    else:
        boton_copiar(texto_orig_formateado, id_btn="btn_solo_orig")
        st.text_area("Transcripción en párrafos", value=texto_orig_formateado, height=320)
        st.download_button("📥 Descargar (.txt)", data=texto_orig_formateado, file_name="transcripcion.txt", mime="text/plain")

# --- PESTAÑA 1: POR ENLACE ---
with pestana1:
    url = st.text_input("Pega el enlace de YouTube, TikTok o Instagram:")
    traducir_link = st.checkbox("Traducir automáticamente al español de Latinoamérica", value=True, key="chk_link")
    
    if st.button("Transcribir y Organizar", type="primary"):
        if not GROQ_API_KEY.strip():
            st.error("Por favor ingresa tu Groq API Key en la barra lateral izquierda.")
        elif not url.strip():
            st.warning("Ingresa un enlace válido.")
        else:
            archivo_temporal = None
            try:
                with st.spinner("1/3 Descargando audio por detrás..."):
                    archivo_temporal = extraer_audio(url.strip())

                with st.spinner("2/3 Transcribiendo con IA (Whisper)..."):
                    texto = transcribir_con_groq(archivo_temporal, GROQ_API_KEY)

                if not texto:
                    st.warning("No se detectó voz en el video.")
                else:
                    mostrar_resultados(texto, traducir_link)

            except Exception as e:
                st.error(f"Error al procesar el video: {e}")
            finally:
                if archivo_temporal and os.path.exists(archivo_temporal):
                    try:
                        os.remove(archivo_temporal)
                    except Exception:
                        pass

# --- PESTAÑA 2: SUBIR ARCHIVO ---
with pestana2:
    archivo_subido = st.file_uploader("Arrastra tu video o audio aquí:", type=["mp3", "mp4", "m4a", "wav"])
    traducir_file = st.checkbox("Traducir automáticamente al español de Latinoamérica", value=True, key="chk_file")
    
    if archivo_subido and st.button("Transcribir y Organizar archivo", type="primary"):
        if not GROQ_API_KEY.strip():
            st.error("Por favor ingresa tu Groq API Key en la barra lateral izquierda.")
        else:
            nombre_temp = f"temp_subido_{archivo_subido.name}"
            try:
                with open(nombre_temp, "wb") as f:
                    f.write(archivo_subido.getbuffer())

                with st.spinner("Transcribiendo archivo con IA..."):
                    texto = transcribir_con_groq(nombre_temp, GROQ_API_KEY)

                mostrar_resultados(texto, traducir_file)
            except Exception as e:
                st.error(f"Error: {e}")
            finally:
                if os.path.exists(nombre_temp):
                    try:
                        os.remove(nombre_temp)
                    except Exception:
                        pass
