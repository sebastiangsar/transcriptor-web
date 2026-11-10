import os
import re
import json
import requests
import streamlit as st
import streamlit.components.v1 as components
import yt_dlp
import static_ffmpeg
from groq import Groq

# Activa FFmpeg automaticamente
static_ffmpeg.add_paths()

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
    st.header("Configuración")
    if not GROQ_API_KEY:
        GROQ_API_KEY = st.text_input("Groq API Key:", type="password", placeholder="gsk_...")
    
    st.subheader("Sesión de Instagram")
    cookie_subida = st.file_uploader("Sube tu archivo cookies.txt aquí:", type=["txt"])
    if cookie_subida:
        with open("cookies.txt", "wb") as f:
            f.write(cookie_subida.getbuffer())
        st.success("¡Archivo guardado!")
        st.rerun()

    archivo_cookies_encontrado = buscar_archivo_cookies()
    if archivo_cookies_encontrado:
        st.success(f"✅ Sesión activa ({archivo_cookies_encontrado})")
    else:
        st.warning("⚠️ Sin archivo de cookies.")

pestaña1, pestaña2 = st.tabs(["🔗 Enlace de Redes", "📁 Subir Archivo"])

def boton_copiar(texto, id_btn="copiar"):
    """Genera un botón de copia rápida al portapapeles"""
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
    """Estructura en párrafos y opcionalmente traduce al español latino"""
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
            boton_copiar(text