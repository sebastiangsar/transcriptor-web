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

st.set_page_config(page_title="Suite Creativa & Alquimia Lírica", page_icon="⚡", layout="centered")

st.title("⚡ Suite Creativa & Alquimia Lírica")
st.caption("Videos Virales, Guiones con IA y Transmutación Musical Hawkins")

# Memoria de sesión para persistencia de datos
for key in [
    "texto_original", "texto_traducido", "guiones_generados",
    "letra_escaneada", "analisis_hawkins", "letra_transmutada"
]:
    if key not in st.session_state:
        st.session_state[key] = None

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

# ==============================================================
# BARRA LATERAL: CONFIGURACIÓN + LEAD MAGNETS (3 NIVELES)
# ==============================================================
with st.sidebar:
    st.header("⚙️ Configuración")
    if not GROQ_API_KEY:
        GROQ_API_KEY = st.text_input("Groq API Key:", type="password", placeholder="gsk_...")
    
    st.subheader("Sesión de Instagram")
    cookie_subida = st.file_uploader("Sube cookies.txt aquí:", type=["txt"])
    if cookie_subida:
        with open("cookies.txt", "wb") as f:
            f.write(cookie_subida.getbuffer())
        st.success("Guardado!")
        st.rerun()

    archivo_cookies = buscar_archivo_cookies()
    if archivo_cookies:
        st.success(f"Sesión activa ({archivo_cookies})")
    else:
        st.warning("Sin cookies.")

    st.markdown("---")
    st.header("🎁 Recursos Gratuitos")
    
    with st.expander("⭐ Nivel 1: Alto Valor (Masivo)"):
        st.markdown("**La Bóveda de las 50 Fórmulas Virales**")
        st.caption("Las 50 estructuras psicológicas que dominan el algoritmo de TikTok y Reels.")
        st.button("Descargar", key="lm1")

    with st.expander("🎯 Nivel 2: Específico (Táctico)"):
        st.markdown("**Kit de 30 Ganchos + Plantilla de Teleprónter**")
        st.caption("Frases de apertura anti-scroll con acotaciones visuales segundo a segundo.")
        st.button("Obtener", key="lm2")

    with st.expander("👑 Nivel 3: Personalizado (1 a 1)"):
        st.markdown("**Auditoría de tu Cuenta + Guion Insignia**")
        st.caption("Analizamos tu perfil y rediseñamos tu video con menor rendimiento.")
        st.text_input("Tu @usuario o enlace:", placeholder="@tucuenta")
        st.button("Solicitar", key="lm3")

def boton_copiar(texto, id_btn="copiar"):
    """Boton de 1 sola palabra para copiar al portapapeles"""
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
            alert('Error: ' + err);
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
        "openai/gpt-oss-120b", "qwen/qwen3.8-27b",
        "llama-3.1-8b-instant", "llama3-8b-8192", "gemma2-9b-it"
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
            "Divide el texto en párrafos coherentes y cómodos de leer, separados por saltos de línea dobles. "
            "Corrige la puntuación. No agregues notas; devuelve solo el texto final."
        )
    else:
        instruccion = (
            "Eres un editor profesional. Organiza el texto en párrafos coherentes separados por saltos de línea dobles. "
            "Corrige la puntuación básica sin cambiar palabras ni idioma. "
            "No agregues notas; devuelve solo el texto formateado."
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
    client = Groq(api_key=api_key)
    modelo = obtener_modelo_texto_activo(client)
    
    prompt_sistema = (
        "Eres un estratega de contenido viral y director de guiones experto en videos cortos (Reels, TikTok, Shorts). "
        "Desarma la fórmula psicológica del video de referencia y genera 3 ideas con sus guiones adaptados al nicho del usuario.\n\n"
        "ESTRUCTURA DE RESPUESTA:\n"
        "### 🧠 1. RADIOGRAFÍA DE LA FÓRMULA VIRAL\n"
        "- **El Gancho (Hook):** Técnica psicológica que usó y por qué retiene.\n"
        "- **Estructura de Retención:** Manejo del ritmo y tensión.\n"
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

    prompt_usuario = (
        f"REFERENCIA:\n\"\"\"{transcripcion}\"\"\"\n\n"
        f"MI NICHO / TEMA:\n\"\"\"{nicho_usuario}\"\"\""
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
# FUNCIONES: ALQUIMIA LÍRICA (MAPA DE HAWKINS)
# ==============================================================
def estructurar_letra_musical(letra_cruda, api_key):
    """Detecta y etiqueta la estructura musical estricta"""
    client = Groq(api_key=api_key)
    modelo = obtener_modelo_texto_activo(client)
    
    instruccion = (
        "Eres un productor y compositor musical experto. Analiza el siguiente texto de canción "
        "y organízalo en su estructura musical formal, etiquetando claramente cada bloque entre corchetes: "
        "[Verso 1], [Pre-Coro], [Coro], [Verso 2], [Puente], [Coro Final], [Outro]. "
        "Conserva la métrica y rimas originales. Solo devuelve la letra estructurada."
    )
    res = client.chat.completions.create(
        model=modelo,
        messages=[
            {"role": "system", "content": instruccion},
            {"role": "user", "content": letra_cruda}
        ],
        temperature=0.2
    )
    return res.choices[0].message.content

def calibrar_hawkins(letra_estructurada, api_key):
    """Mide la frecuencia vibracional según el Mapa de Conciencia de David R. Hawkins"""
    client = Groq(api_key=api_key)
    modelo = obtener_modelo_texto_activo(client)
    
    instruccion = (
        "Eres un experto en el Mapa de Conciencia de David R. Hawkins (Power vs. Force). "
        "Analiza la letra musical y determina su calibración vibracional dominante:\n"
        "Escala de referencia: Vergüenza (20), Culpa (30), Apatía (50), Pena (75), Miedo (100), "
        "Deseo/Apego (125), Ira (150), Orgullo (175), Coraje (200), Neutralidad (250), "
        "Voluntad (310), Aceptación (350), Razón (400), Amor (500), Alegría (540), Paz (600).\n\n"
        "Devuelve exactamente esta ficha concisa en Markdown:\n"
        "- **Frecuencia Detectada:** [Emoción y número Hz/pts, ej: Culpa (30)]\n"
        "- **Patrón Psicológico:** [1 frase explicando el apego/dolor del texto]\n"
        "- **Frecuencia Opuesta de Elevación:** [El nivel elevado al que debe transmutar, ej: Aceptación (350) o Amor (500)]\n"
        "- **Clave de Transmutación:** [Concepto central para elevar el mensaje]"
    )
    res = client.chat.completions.create(
        model=modelo,
        messages=[
            {"role": "system", "content": instruccion},
            {"role": "user", "content": letra_estructurada}
        ],
        temperature=0.2
    )
    return res.choices[0].message.content

def transmutar_letra(letra_estructurada, analisis_h, tema_nuevo, api_key):
    """Reescribe la canción en alta vibración manteniendo métrica y rima para cantar sobre la pista"""
    client = Groq(api_key=api_key)
    modelo = obtener_modelo_texto_activo(client)
    
    instruccion = (
        "Eres un alquimista lírico y compositor maestro. Tu tarea es reescribir la canción transmutándola "
        "hacia la Frecuencia Opuesta de Elevación según el análisis de Hawkins provisto.\n\n"
        "REGLAS TÉCNICAS OBLIGATORIAS:\n"
        "1. Mantén la misma estructura de bloques ([Verso 1], [Pre-Coro], [Coro], [Puente], etc.).\n"
        "2. Mantén el conteo silábico, ritmo y esquema de rima para que la nueva letra se pueda cantar "
        "exactamente sobre la misma pista musical (karaoke o beat) original.\n"
        "3. Eleva el estado emocional y adáptalo a la nueva temática del usuario.\n"
        "4. Devuelve únicamente la nueva letra estructurada."
    )
    prompt = (
        f"LETRA ORIGINAL ESTRUCTURADA:\n\"\"\"{letra_estructurada}\"\"\"\n\n"
        f"DIAGNÓSTICO HAWKINS:\n\"\"\"{analisis_h}\"\"\"\n\n"
        f"NUEVA TEMÁTICA ELEGIDA:\n\"\"\"{tema_nuevo}\"\"\""
    )
    res = client.chat.completions.create(
        model=modelo,
        messages=[
            {"role": "system", "content": instruccion},
            {"role": "user", "content": prompt}
        ],
        temperature=0.4
    )
    return res.choices[0].message.content

# ==============================================================
# PESTAÑAS PRINCIPALES DE LA APLICACIÓN
# ==============================================================
tab_videos, tab_musica, tab_archivo = st.tabs([
    "🎬 Videos & Guiones",
    "🎵 Alquimia Lírica (Hawkins)",
    "📁 Subir Archivo"
])

# --------------------------------------------------------------
# PESTAÑA 1: VIDEOS Y GENERADOR DE GUIONES
# --------------------------------------------------------------
with tab_videos:
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
                with st.spinner("Transcribiendo con IA (Whisper)..."):
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
                st.error(f"Error: {e}")
            finally:
                if archivo_temporal and os.path.exists(archivo_temporal):
                    try:
                        os.remove(archivo_temporal)
                    except Exception:
                        pass

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

# --------------------------------------------------------------
# PESTAÑA 2: ALQUIMIA LÍRICA (DAVID R. HAWKINS)
# --------------------------------------------------------------
with tab_musica:
    st.subheader("🎵 Alquimia Lírica y Transmutación de Frecuencia")
    st.caption("Extrae letras, mide su vibración en la escala de Hawkins y elévalas manteniendo la rima musical.")
    
    musica_url = st.text_input("Enlace de YouTube de la canción (o pega la letra abajo):")
    letra_manual = st.text_area("O pega la letra aquí directamente:", height=100)

    # 1. BOTÓN: ESCANEAR
    if st.button("Escanear", type="primary", key="btn_escanear"):
        if not GROQ_API_KEY.strip():
            st.error("Ingresa tu Groq API Key en la barra lateral.")
        elif not musica_url.strip() and not letra_manual.strip():
            st.warning("Pega un enlace de YouTube o ingresa la letra.")
        else:
            letra_base = ""
            if letra_manual.strip():
                letra_base = letra_manual.strip()
            else:
                archivo_temp = None
                try:
                    with st.spinner("Descargando canción de YouTube..."):
                        archivo_temp = extraer_audio(musica_url.strip())
                    with st.spinner("Extrayendo letra con Whisper..."):
                        letra_base = transcribir_con_groq(archivo_temp, GROQ_API_KEY)
                except Exception as e:
                    st.error(f"Error descargando audio: {e}")
                finally:
                    if archivo_temp and os.path.exists(archivo_temp):
                        try:
                            os.remove(archivo_temp)
                        except Exception:
                            pass
            
            if letra_base:
                with st.spinner("Estructurando en Versos, Coros y Puente..."):
                    st.session_state.letra_escaneada = estructurar_letra_musical(letra_base, GROQ_API_KEY)
                    st.session_state.analisis_hawkins = None
                    st.session_state.letra_transmutada = None

    # Muestra la letra escaneada
    if st.session_state.letra_escaneada:
        st.markdown("#### 🎼 Estructura Musical Detectada")
        boton_copiar(st.session_state.letra_escaneada, id_btn="cp_letra_esc")
        st.text_area("Estructura Musical", value=st.session_state.letra_escaneada, height=220)

        # 2. BOTÓN: CALIBRAR
        st.markdown("---")
        st.markdown("#### 🔮 Calibración en la Escala de Hawkins")
        if st.button("Calibrar", key="btn_calibrar"):
            with st.spinner("Calculando frecuencia vibracional..."):
                st.session_state.analisis_hawkins = calibrar_hawkins(st.session_state.letra_escaneada, GROQ_API_KEY)

        if st.session_state.analisis_hawkins:
            st.info(st.session_state.analisis_hawkins)
            
            # 3. BOTÓN: TRANSMUTAR
            st.markdown("---")
            st.markdown("#### ✨ Transmutación a Frecuencia Alta")
            tema_transmutar = st.text_input(
                "Temática de tu nueva letra:",
                placeholder="Ej: Empoderamiento y gratitud, Paz mental, Triunfo personal..."
            )
            
            if st.button("Transmutar", type="primary", key="btn_transmutar"):
                if not tema_transmutar.strip():
                    st.warning("Escribe la temática para la nueva letra.")
                else:
                    with st.spinner("Reescribiendo letra rítmica en alta frecuencia..."):
                        st.session_state.letra_transmutada = transmutar_letra(
                            st.session_state.letra_escaneada,
                            st.session_state.analisis_hawkins,
                            tema_transmutar.strip(),
                            GROQ_API_KEY
                        )

            if st.session_state.letra_transmutada:
                st.success("¡Letra transmutada lista para cantar sobre el beat original!")
                # 4. BOTÓN: COPIAR
                boton_copiar(st.session_state.letra_transmutada, id_btn="cp_transmutada")
                st.text_area("Nueva Letra Elevada", value=st.session_state.letra_transmutada, height=260)

# --------------------------------------------------------------
# PESTAÑA 3: SUBIR ARCHIVO LOCAL
# --------------------------------------------------------------
with tab_archivo:
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
                with st.spinner("Procesando archivo..."):
                    texto_crudo = transcribir_con_groq(nombre_temp, GROQ_API_KEY)
                st.session_state.texto_original = formatear_y_traducir(texto_crudo, GROQ_API_KEY, traducir=False)
                if traducir_f:
                    st.session_state.texto_traducido = formatear_y_traducir(texto_crudo, GROQ_API_KEY, traducir=True)
                else:
                    st.session_state.texto_traducido = None
                st.success("¡Completado! Revisa la pestaña de Videos & Guiones para ver el texto.")
            except Exception as e:
                st.error(f"Error: {e}")
            finally:
                if os.path.exists(nombre_temp):
                    try:
                        os.remove(nombre_temp)
                    except Exception:
                        pass
