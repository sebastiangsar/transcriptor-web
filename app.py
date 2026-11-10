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
claves_estado = [
    "texto_original", "texto_traducido", "guiones_generados",
    "letra_esc_orig", "letra_esc_es", "analisis_hawkins", 
    "letra_trans_en", "letra_trans_es"
]
for k in claves_estado:
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
        st.success("¡Guardado!")
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
        st.caption("Estructuras psicológicas que dominan el algoritmo.")
        st.button("Descargar", key="lm1")

    with st.expander("🎯 Nivel 2: Específico (Táctico)"):
        st.markdown("**Kit de 30 Ganchos + Plantilla de Teleprónter**")
        st.caption("Frases de apertura con acotaciones visuales segundo a segundo.")
        st.button("Obtener", key="lm2")

    with st.expander("👑 Nivel 3: Personalizado (1 a 1)"):
        st.markdown("**Auditoría de tu Cuenta + Guion Insignia**")
        st.caption("Analizamos tu perfil y rediseñamos tu video con menor rendimiento.")
        st.text_input("Tu @usuario o enlace:", placeholder="@tucuenta")
        st.button("Solicitar", key="lm3")

def boton_copiar(texto, id_btn="copiar"):
    """Botón de 1 sola palabra para copiar al portapapeles"""
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
# ALQUIMIA LÍRICA (HAWKINS) - ANÁLISIS VIRAL Y TRANSMUTACIÓN
# ==============================================================
def estructurar_letra_musical(letra_cruda, api_key):
    """Estructura la letra en párrafos limpios y genera traducción al español"""
    client = Groq(api_key=api_key)
    modelo = obtener_modelo_texto_activo(client)
    
    instruccion = (
        "Eres un productor y compositor musical experto. Analiza el texto de esta canción "
        "y organízalo en su estructura musical formal con formato impecable.\n\n"
        "REGLAS OBLIGATORIAS:\n"
        "1. Etiqueta claramente cada sección entre corchetes: [Verse 1], [Pre-Chorus], [Chorus], [Verse 2], [Bridge], [Outro].\n"
        "2. Separa cada sección con un salto de línea doble (\\n\\n).\n"
        "3. Cada verso debe ser una línea individual y limpia. No amontones versos.\n"
        "4. Conserva el idioma y rima original. Devuelve únicamente la letra estructurada."
    )
    res_orig = client.chat.completions.create(
        model=modelo,
        messages=[
            {"role": "system", "content": instruccion},
            {"role": "user", "content": letra_cruda}
        ],
        temperature=0.2
    )
    letra_orig = res_orig.choices[0].message.content

    instruccion_es = (
        "Eres un traductor y letrista musical. Traduce la siguiente letra estructurada al español de forma poética y natural.\n"
        "Mantén exactamente las etiquetas [Verso 1], [Pre-Coro], [Coro], [Puente], etc., y los saltos de línea dobles entre secciones. "
        "Devuelve solo la traducción limpia."
    )
    res_es = client.chat.completions.create(
        model=modelo,
        messages=[
            {"role": "system", "content": instruccion_es},
            {"role": "user", "content": letra_orig}
        ],
        temperature=0.2
    )
    return letra_orig, res_es.choices[0].message.content

def calibrar_hawkins_estructurado(letra_texto, api_key):
    """Mide la frecuencia de Hawkins Y el potencial de viralidad/catarsis"""
    client = Groq(api_key=api_key)
    modelo = obtener_modelo_texto_activo(client)
    
    prompt = f"""Eres un analista de psicología musical experto en el Mapa de Conciencia de David R. Hawkins (Power vs. Force) y viralidad emocional.
Analiza la siguiente letra de canción:
\"\"\"{letra_texto}\"\"\"

Determina:
1. Nivel vibracional dominante en la escala Hawkins (ej: Vergüenza 20, Culpa 30, Apatía 50, Pena 75, Miedo 100, Deseo 125, Ira 150, Orgullo 175, Coraje 200, Neutralidad 250, Aceptación 350, Razón 400, Amor 500, Alegría 540, Paz 600).
2. Grado de Viralidad y Conexión Emocional (0 a 100%) y el motivo psicológico (las canciones de baja vibración suelen tener altísima viralidad por catarsis colectiva, despecho, desahogo o validación del dolor).
3. Frecuencia Opuesta de Elevación (el nivel elevado al que debe transmutar).
4. Clave Alquímica (la frase o idea central para transmutar el mensaje).

Responde con líneas que comiencen exactamente con estas etiquetas:
FRECUENCIA: [Emoción y número de puntos]
VIRALIDAD: [Porcentaje 0-100% y explicación breve del fenómeno de conexión/catarsis]
PATRON: [1 frase explicando el apego, dolor o rencor del texto original]
ELEVACION: [Nivel de alta frecuencia hacia donde elevar]
CLAVE: [Concepto central de redención o soberanía]"""

    res = client.chat.completions.create(
        model=modelo,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )
    
    lineas = res.choices[0].message.content.split("\n")
    datos = {
        "frecuencia": "Culpa (30 puntos)",
        "viralidad": "92% - Muy Alta (Conexión por Catarsis y Desahogo Colectivo)",
        "patron": "Carga de victimismo y remordimiento en la narrativa.",
        "elevacion": "Aceptación (350) / Amor Incondicional (500)",
        "clave": "Perdón propio y redención"
    }
    
    for l in lineas:
        if l.startswith("FRECUENCIA:"):
            datos["frecuencia"] = l.replace("FRECUENCIA:", "").strip()
        elif l.startswith("VIRALIDAD:"):
            datos["viralidad"] = l.replace("VIRALIDAD:", "").strip()
        elif l.startswith("PATRON:"):
            datos["patron"] = l.replace("PATRON:", "").strip()
        elif l.startswith("ELEVACION:"):
            datos["elevacion"] = l.replace("ELEVACION:", "").strip()
        elif l.startswith("CLAVE:"):
            datos["clave"] = l.replace("CLAVE:", "").strip()
            
    return datos

def transmutar_letra_modo(letra_estructurada, analisis_h, modo, tema_personalizado, api_key):
    """Reescribe la lírica en alta vibración separada en párrafos limpios (Inglés y Español)"""
    client = Groq(api_key=api_key)
    modelo = obtener_modelo_texto_activo(client)
    
    if modo == "misma":
        guia_modo = (
            "MODO: REESCRIBIR LA MISMA HISTORIA (TRANSMUTACIÓN ELEVADA):\n"
            "- Conserva exactamente la misma situación, historia, personajes y dolor de la canción original.\n"
            "- Transmuta el enfoque: en lugar de quedarse en el rencor, la culpa o la venganza, condúcelo "
            "hacia la sabiduría, el amor propio, la redención, el perdón y el cierre consciente.\n"
            "- Debe sentirse como la misma canción, pero sanada."
        )
    else:
        guia_modo = (
            f"MODO: CREAR NUEVA LETRA CON TEMÁTICA PROPIA:\n"
            f"- Temática elegida: \"{tema_personalizado}\"\n"
            "- Desarrolla este tema en alta vibración manteniendo el mismo ritmo y formato."
        )

    instruccion_en = (
        f"You are a master lyrical alchemist and songwriter. Your mission is to elevate the song into high frequency.\n\n"
        f"{guia_modo}\n\n"
        "STRICT FORMATTING AND RHYTHMIC RULES:\n"
        "1. Structure in clear blocks with labels: [Verse 1], [Pre-Chorus], [Chorus], [Verse 2], [Bridge], [Chorus], [Outro].\n"
        "2. Add double newlines (blank lines) between each section.\n"
        "3. Match the exact syllable counts, cadence, and rhyme scheme so it can be sung on the original musical beat.\n"
        "4. Output must be in ENGLISH, clean, professional, and directly ready to sing."
    )

    prompt = (
        f"ORIGINAL LYRICS:\n\"\"\"{letra_estructurada}\"\"\"\n\n"
        f"HAWKINS ANALYSIS:\n"
        f"- Target Elevation: {analisis_h.get('elevacion')}\n"
        f"- Key Insight: {analisis_h.get('clave')}"
    )

    # 1. Generamos versión en Inglés
    res_en = client.chat.completions.create(
        model=modelo,
        messages=[
            {"role": "system", "content": instruccion_en},
            {"role": "user", "content": prompt}
        ],
        temperature=0.4
    )
    letra_en = res_en.choices[0].message.content

    # 2. Generamos versión poética estructurada en Español
    instruccion_es = (
        "Eres un letrista y compositor experto. Toma la siguiente letra transmutada y adáptala al español latino "
        "con rima natural y cantable. Mantén la misma estructura estricta ([Verso 1], [Coro], etc.) "
        "con saltos de línea dobles entre secciones. Solo entrega la letra."
    )
    res_es = client.chat.completions.create(
        model=modelo,
        messages=[
            {"role": "system", "content": instruccion_es},
            {"role": "user", "content": letra_en}
        ],
        temperature=0.3
    )
    letra_es = res_es.choices[0].message.content

    return letra_en, letra_es

# ==============================================================
# PESTAÑAS PRINCIPALES
# ==============================================================
tab_videos, tab_musica, tab_archivo = st.tabs([
    "🎬 Videos & Guiones",
    "🎵 Alquimia Lírica (Hawkins)",
    "📁 Subir Archivo"
])

# --------------------------------------------------------------
# PESTAÑA 1: VIDEOS Y GUIONES
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
                with st.spinner("1/2 Descargando audio ultra comprimido..."):
                    archivo_temporal = extraer_audio(url.strip())
                with st.spinner("2/2 Transcribiendo con Groq Whisper..."):
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
# PESTAÑA 2: ALQUIMIA LÍRICA (HAWKINS + VIRALIDAD + FORMATO LIMPIO)
# --------------------------------------------------------------
with tab_musica:
    st.subheader("🎵 Alquimia Lírica (Escala de Hawkins)")
    st.caption("Estructura canciones, calibra su resonancia viral y transmuta la letra en alta vibración.")
    
    letra_manual = st.text_area(
        "Pega aquí la letra de la canción:",
        height=180,
        placeholder="Pega aquí los versos o el texto de la canción..."
    )

    # 1. BOTÓN: ESCANEAR
    if st.button("Escanear", type="primary", key="btn_escanear"):
        if not GROQ_API_KEY.strip():
            st.error("Ingresa tu Groq API Key en la barra lateral.")
        elif not letra_manual.strip():
            st.warning("Por favor pega la letra de la canción antes de escanear.")
        else:
            with st.spinner("Estructurando bloques en párrafos limpios y preparando traducción..."):
                try:
                    orig, es = estructurar_letra_musical(letra_manual.strip(), GROQ_API_KEY)
                    st.session_state.letra_esc_orig = orig
                    st.session_state.letra_esc_es = es
                    st.session_state.analisis_hawkins = None
                    st.session_state.letra_trans_en = None
                    st.session_state.letra_trans_es = None
                except Exception as e:
                    st.error(f"Error al estructurar: {e}")

    # Si hay letra escaneada, la mostramos en pestañas
    if st.session_state.letra_esc_orig:
        st.markdown("---")
        st.markdown("#### 🎼 Estructura Musical Detectada")
        
        tab_l_orig, tab_l_es = st.tabs(["🌐 Original", "🇪🇸 Traducción al Español"])
        with tab_l_orig:
            boton_copiar(st.session_state.letra_esc_orig, id_btn="cp_esc_orig")
            st.text_area("Estructura Original", value=st.session_state.letra_esc_orig, height=220)
        with tab_l_es:
            boton_copiar(st.session_state.letra_esc_es, id_btn="cp_esc_es")
            st.text_area("Estructura en Español", value=st.session_state.letra_esc_es, height=220)

        # 2. BOTÓN: CALIBRAR
        st.markdown("---")
        st.markdown("#### 🔮 Calibración de Conciencia & Potencial Viral")
        if st.button("Calibrar", key="btn_calibrar"):
            with st.spinner("Midiendo nivel Hawkins y grado de viralidad psicológica..."):
                try:
                    st.session_state.analisis_hawkins = calibrar_hawkins_estructurado(
                        st.session_state.letra_esc_orig, GROQ_API_KEY
                    )
                except Exception as e:
                    st.error(f"Error al calibrar: {e}")

        # TARJETA VISUAL CON VIRALIDAD
        if st.session_state.analisis_hawkins:
            h = st.session_state.analisis_hawkins
            frec_str = h.get("frecuencia", "")

            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #311042 100%); border-left: 6px solid #f43f5e; padding: 18px 22px; border-radius: 12px; margin: 18px 0; box-shadow: 0 4px 15px rgba(0,0,0,0.3);">
                <h4 style="margin: 0 0 10px 0; color: #fb7185; font-size: 18px;">📊 Frecuencia Hawkins: <span style="color: #ffffff; text-decoration: underline;">{frec_str}</span></h4>
                <p style="margin: 6px 0; color: #38bdf8; font-size: 15px;"><b>🔥 Potencial Viral / Conexión Emocional:</b> <span style="color: #ffffff; font-weight: bold;">{h.get('viralidad')}</span></p>
                <p style="margin: 6px 0; color: #e2e8f0; font-size: 14px;"><b>⚠️ Patrón Psicológico Raíz:</b> {h.get('patron')}</p>
                <p style="margin: 6px 0; color: #34d399; font-size: 15px;"><b>✨ Frecuencia de Elevación recomendada:</b> {h.get('elevacion')}</p>
                <p style="margin: 6px 0; color: #c084fc; font-size: 14px;"><b>🔑 Clave de Transmutación:</b> {h.get('clave')}</p>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("---")
            st.markdown("#### ✨ Modo de Transmutación")
            
            modo_elegido = st.radio(
                "¿Cómo deseas transmutar la lírica?",
                options=["Elevar la misma letra (Misma historia, alta vibración)", "Escribir sobre una nueva temática"],
                index=0
            )

            tema_nuevo = ""
            if "nueva temática" in modo_elegido.lower():
                tema_nuevo = st.text_input(
                    "Escribe la temática para la nueva letra:",
                    placeholder="Ej: Gratitud y abundancia, Paz interior, Triunfo personal..."
                )

            # 3. BOTÓN: TRANSMUTAR
            if st.button("Transmutar", type="primary", key="btn_transmutar"):
                modo_codigo = "misma" if "Misma historia" in modo_elegido else "nueva"
                if modo_codigo == "nueva" and not tema_nuevo.strip():
                    st.warning("Por favor escribe la temática que deseas para la nueva letra.")
                else:
                    with st.spinner("Transmutando lírica en párrafos limpios (Inglés y Español)..."):
                        try:
                            t_en, t_es = transmutar_letra_modo(
                                st.session_state.letra_esc_orig,
                                st.session_state.analisis_hawkins,
                                modo_codigo,
                                tema_nuevo.strip(),
                                GROQ_API_KEY
                            )
                            st.session_state.letra_trans_en = t_en
                            st.session_state.letra_trans_es = t_es
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error durante la transmutación: {e}")

            # Mostramos la letra transmutada en párrafos organizados
            if st.session_state.letra_trans_en:
                st.markdown("""
                <div style="background-color: #064e3b; border-left: 6px solid #10b981; padding: 14px 20px; border-radius: 8px; margin: 18px 0;">
                    <h4 style="margin: 0; color: #a7f3d0;">🎉 ¡Alquimia completada! Letra en alta vibración organizada por párrafos</h4>
                </div>
                """, unsafe_allow_html=True)

                tab_t_en, tab_t_es = st.tabs(["🇺🇸 Versión en Inglés (Clean)", "🇪🇸 Versión en Español"])
                with tab_t_en:
                    boton_copiar(st.session_state.letra_trans_en, id_btn="cp_t_en")
                    st.text_area("Letra Transmutada en Inglés", value=st.session_state.letra_trans_en, height=300)
                with tab_t_es:
                    boton_copiar(st.session_state.letra_trans_es, id_btn="cp_t_es")
                    st.text_area("Letra Transmutada en Español", value=st.session_state.letra_trans_es, height=300)

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
