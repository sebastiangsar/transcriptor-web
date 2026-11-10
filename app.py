import os
import re
import json
import requests
import streamlit as st
import streamlit.components.v1 as components
import yt_dlp
from groq import Groq

# Activa FFmpeg: en la nube usa el de packages.txt; en local usa static_ffmpeg
try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except Exception:
    pass

st.set_page_config(page_title="Transcriptor & Creador de Guiones", page_icon="🎬", layout="centered")

st.title("🎬 Transcriptor & Creador de Guiones Virales")
st.caption("Ingeniería inversa de videos para generar ideas y guiones listos para grabar")

# Memoria de sesión para que no se borre la transcripción al hacer clic en otros botones
if "texto_original" not in st.session_state:
    st.session_state.texto_original = None
if "texto_traducido" not in st.session_state:
    st.session_state.texto_traducido = None
if "guiones_generados" not in st.session_state:
    st.session_state.guiones_generados = None

# Manejo seguro de la API Key
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

def generar_ideas_y_guiones(transcripcion, nicho_usuario, api_key):
    """Hace ingeniería inversa al video y genera 3 ideas con sus guiones adaptados"""
    client = Groq(api_key=api_key)
    modelo = obtener_modelo_texto_activo(client)
    
    prompt_sistema = (
        "Eres un estratega de contenido viral y director de guiones experto en videos cortos (Reels, TikTok, Shorts). "
        "Tu habilidad consiste en desarmar un video viral exitoso, extraer su fórmula psicológica y aplicarla a cualquier nicho.\n\n"
        "ESTRUCTURA DE RESPUESTA OBLIGATORIA (Usa Markdown claro):\n\n"
        "### 🧠 1. RADIOGRAFÍA DE LA FÓRMULA VIRAL\n"
        "- **El Gancho (Hook):** Técnica psicológica que usó (dolor, curiosidad, error común) y por qué detiene el scroll.\n"
        "- **Estructura de Retención:** Cómo mantuvo la atención a la mitad del video.\n"
        "- **Remate y CTA:** Estrategia de llamado a la acción.\n\n"
        "---\n\n"
        "### 💡 2. BANCO DE 3 IDEAS PARA TU NICHO\n"
        "- **Idea 1 (Enfoque Error/Dolor):** Concepto concreto.\n"
        "- **Idea 2 (Enfoque Secreto/Curiosidad):** Concepto concreto.\n"
        "- **Idea 3 (Enfoque Hack/Acción Rápida):** Concepto concreto.\n\n"
        "---\n\n"
        "### 🎬 3. GUIONES COMPLETOS LISTOS PARA GRABAR\n\n"
        "#### 📌 GUION 1 (Basado en Idea 1):\n"
        "- **Gancho (0-3s):** [Acción/gesto visual] \"Texto exacto a decir\"\n"
        "- **Desarrollo (3-20s):** [Indicación visual] \"Texto exacto a decir\"\n"
        "- **Cierre y CTA (20-30s):** \"Texto exacto a decir\"\n\n"
        "#### 📌 GUION 2 (Basado en Idea 2):\n"
        "- **Gancho (0-3s):** [Acción/gesto visual] \"Texto exacto a decir\"\n"
        "- **Desarrollo (3-20s):** [Indicación visual] \"Texto exacto a decir\"\n"
        "- **Cierre y CTA (20-30s):** \"Texto exacto a decir\"\n\n"
        "#### 📌 GUION 3 (Basado en Idea 3):\n"
        "- **Gancho (0-3s):** [Acción/gesto visual] \"Texto exacto a decir\"\n"
        "- **Desarrollo (3-20s):** [Indicación visual] \"Texto exacto a decir\"\n"
        "- **Cierre y CTA (20-30s):** \"Texto exacto a decir\""
    )

    prompt_usuario = (
        f"TRANSCRIPCIÓN DEL VIDEO DE REFERENCIA:\n\"\"\"{transcripcion}\"\"\"\n\n"
        f"MI NICHO / TEMA / PRODUCTO:\n\"\"\"{nicho_usuario}\"\"\"\n\n"
        "Analiza la referencia y crea las 3 ideas con sus guiones completos aplicados a mi tema."
    )

    res = client.chat.completions.create(
        model=modelo,
        messages=[
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": prompt_usuario}
        ],
        temperature=0.4
    )
    return res.choices[0].message.content

# ==============================================================
# PESTAÑAS DE ENTRADA (LINK O ARCHIVO)
# ==============================================================
pestana1, pestana2 = st.tabs(["🔗 Enlace de Redes", "📁 Subir Archivo"])

with pestana1:
    url = st.text_input("Pega el enlace de YouTube, TikTok o Instagram:")
    traducir_link = st.checkbox("Traducir al español latino si viene en otro idioma", value=True, key="chk_link")
    
    if st.button("Transcribir Video", type="primary"):
        if not GROQ_API_KEY.strip():
            st.error("Por favor ingresa tu Groq API Key en la barra lateral izquierda.")
        elif not url.strip():
            st.warning("Ingresa un enlace válido.")
        else:
            archivo_temporal = None
            try:
                with st.spinner("1/2 Descargando audio..."):
                    archivo_temporal = extraer_audio(url.strip())

                with st.spinner("2/2 Transcribiendo con IA (Whisper)..."):
                    texto_crudo = transcribir_con_groq(archivo_temporal, GROQ_API_KEY)

                if not texto_crudo:
                    st.warning("No se detectó voz en el video.")
                else:
                    st.session_state.texto_original = formatear_y_traducir(texto_crudo, GROQ_API_KEY, traducir=False)
                    if traducir_link:
                        st.session_state.texto_traducido = formatear_y_traducir(texto_crudo, GROQ_API_KEY, traducir=True)
                    else:
                        st.session_state.texto_traducido = None
                    # Reiniciamos guiones si se procesa un nuevo video
                    st.session_state.guiones_generados = None
            except Exception as e:
                st.error(f"Error al procesar el video: {e}")
            finally:
                if archivo_temporal and os.path.exists(archivo_temporal):
                    try:
                        os.remove(archivo_temporal)
                    except Exception:
                        pass

with pestana2:
    archivo_subido = st.file_uploader("Arrastra tu video o audio aquí:", type=["mp3", "mp4", "m4a", "wav"])
    traducir_file = st.checkbox("Traducir al español latino si viene en otro idioma", value=True, key="chk_file")
    
    if archivo_subido and st.button("Transcribir Archivo Subido", type="primary"):
        if not GROQ_API_KEY.strip():
            st.error("Por favor ingresa tu Groq API Key en la barra lateral izquierda.")
        else:
            nombre_temp = f"temp_subido_{archivo_subido.name}"
            try:
                with open(nombre_temp, "wb") as f:
                    f.write(archivo_subido.getbuffer())

                with st.spinner("Transcribiendo archivo con IA..."):
                    texto_crudo = transcribir_con_groq(nombre_temp, GROQ_API_KEY)

                st.session_state.texto_original = formatear_y_traducir(texto_crudo, GROQ_API_KEY, traducir=False)
                if traducir_file:
                    st.session_state.texto_traducido = formatear_y_traducir(texto_crudo, GROQ_API_KEY, traducir=True)
                else:
                    st.session_state.texto_traducido = None
                st.session_state.guiones_generados = None
            except Exception as e:
                st.error(f"Error: {e}")
            finally:
                if os.path.exists(nombre_temp):
                    try:
                        os.remove(nombre_temp)
                    except Exception:
                        pass

# ==============================================================
# VISTA DE RESULTADOS Y GENERADOR DE GUIONES
# ==============================================================
if st.session_state.texto_original:
    st.markdown("---")
    st.subheader("📝 Transcripción del Video de Referencia")
    
    if st.session_state.texto_traducido:
        tab_es, tab_orig = st.tabs(["🇪🇸 Traducción al Español Latino", "🌐 Idioma Original"])
        with tab_es:
            boton_copiar(st.session_state.texto_traducido, id_btn="btn_es")
            st.text_area("Español Latinoamericano", value=st.session_state.texto_traducido, height=220)
        with tab_orig:
            boton_copiar(st.session_state.texto_original, id_btn="btn_orig")
            st.text_area("Texto Original", value=st.session_state.texto_original, height=220)
    else:
        boton_copiar(st.session_state.texto_original, id_btn="btn_solo_orig")
        st.text_area("Transcripción", value=st.session_state.texto_original, height=220)

    # ----------------------------------------------------------
    # SECCIÓN: CLONADOR Y GENERADOR DE GUIONES
    # ----------------------------------------------------------
    st.markdown("---")
    st.header("🎯 Laboratorio de Guiones (Ingeniería Inversa)")
    st.write("Usa la fórmula de este video para crear tus propios guiones:")
    
    nicho_input = st.text_input(
        "¿De qué trata tu tema, producto o nicho?",
        placeholder="Ej: Finanzas personales para jóvenes, Tienda de ropa deportiva, Clases de inglés..."
    )
    
    if st.button("💡 Analizar Fórmula y Crear 3 Ideas con Guiones", type="primary"):
        if not nicho_input.strip():
            st.warning("Escribe de qué trata tu tema o nicho para poder generar las ideas y los guiones.")
        else:
            # Usamos el texto en español si existe, o el original
            texto_base = st.session_state.texto_traducido if st.session_state.texto_traducido else st.session_state.texto_original
            try:
                with st.spinner("Desarmando la fórmula viral y escribiendo los 3 guiones..."):
                    st.session_state.guiones_generados = generar_ideas_y_guiones(texto_base, nicho_input.strip(), GROQ_API_KEY)
            except Exception as e:
                st.error(f"Error generando guiones: {e}")

    # Si los guiones ya se generaron, los mostramos
    if st.session_state.guiones_generados:
        st.success("¡Ideas y Guiones generados exitosamente!")
        boton_copiar(st.session_state.guiones_generados, id_btn="btn_copiar_guiones")
        
        st.markdown(st.session_state.guiones_generados)
        
        st.download_button(
            label="📥 Descargar Paquete de Guiones (.txt)",
            data=st.session_state.guiones_generados,
            file_name="guiones_adaptados.txt",
            mime="text/plain"
        )
