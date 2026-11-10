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
    "letra_trans_orig", "letra_trans_es"
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
# ALQUIMIA LÍRICA (HAWKINS) - FUNCIONES MEJORADAS
# ==============================================================
def estructurar_letra_musical(letra_cruda, api_key):
    """Estructura la letra en sus bloques y genera también su versión al español"""
    client = Groq(api_key=api_key)
    modelo = obtener_modelo_texto_activo(client)
    
    instruccion = (
        "Eres un productor y compositor musical experto. Analiza el texto de esta canción "
        "y organízalo en su estructura musical formal, etiquetando claramente cada bloque entre corchetes: "
        "[Verso 1], [Pre-Coro], [Coro], [Verso 2], [Puente], [Coro Final], [Outro]. "
        "Conserva la métrica y rimas del idioma original. Solo devuelve la letra estructurada."
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

    # Generamos la traducción poética al español manteniendo los corchetes
    instruccion_es = (
        "Eres un traductor y letrista musical. Traduce la siguiente letra estructurada al español de forma natural, "
        "manteniendo exactamente las etiquetas entre corchetes ([Verso 1], [Coro], etc.). Solo devuelve la traducción."
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
    """Devuelve el análisis calibrado con nivel y polaridad emocional"""
    client = Groq(api_key=api_key)
    modelo = obtener_modelo_texto_activo(client)
    
    instruccion = (
        "Eres un maestro del Mapa de Conciencia de David R. Hawkins (Power vs. Force). "
        "Evalúa la vibración emocional dominante de esta letra.\n"
        "Escala Hawkins: Vergüenza (20), Culpa (30), Apatía (50), Pena (75), Miedo (100), "
        "Deseo (125), Ira (150), Orgullo (175), Coraje (200), Neutralidad (250), "
        "Voluntad (310), Aceptación (350), Razón (400), Amor (500), Alegría (540), Paz (600).\n\n"
        "Devuelve ÚNICAMENTE un objeto JSON válido con estas 4 claves exactas:\n"
        "{\n"
        "  \"frecuencia\": \"Culpa (30 puntos)\",\n"
        "  \"patron\": \"Breve explicación del apego, rencor o victimismo del texto\",\n"
        "  \"elevacion\": \"Aceptación (350) o Amor Incondicional (500)\",\n"
        "  \"clave\": \"Concepto central para transmutar el mensaje\"\n"
        "}"
    )
    res = client.chat.completions.create(
        model=modelo,
        messages=[
            {"role": "system", "content": instruccion},
            {"role": "user", "content": letra_texto}
        ],
        temperature=0.1,
        response_format={"type": "json_object"}
    )
    try:
        return json.loads(res.choices[0].message.content)
    except Exception:
        return {
            "frecuencia": "Baja Frecuencia (<200)",
            "patron": "Carga emocional no resuelta en la lírica.",
            "elevacion": "Aceptación (350) / Amor (500)",
            "clave": "Perdón y Soberanía personal"
        }

def transmutar_letra_modo(letra_estructurada, analisis_h, modo, tema_personalizado, api_key):
    """Reescribe la letra elevando la vibración: misma historia O nueva temática"""
    client = Groq(api_key=api_key)
    modelo = obtener_modelo_texto_activo(client)
    
    if modo == "misma":
        guia_modo = (
            "REESCRIBIR LA MISMA LETRA (ELEVACIÓN DE CONCIENCIA):\n"
            "- NO cambies la historia, situación ni personajes de la canción original.\n"
            "- Transmuta la perspectiva: cambia el rencor, victimismo, desamor o culpa hacia "
            "la redención, la comprensión, la paz interior y el amor propio.\n"
            "- Conserva el mismo significado básico pero narrado desde un estado elevado de conciencia."
        )
    else:
        guia_modo = (
            f"CREAR NUEVA LETRA CON NUEVA TEMÁTICA:\n"
            f"- Temática elegida: \"{tema_personalizado}\"\n"
            "- Adapta el mensaje completamente a este nuevo tema en alta vibración."
        )

    instruccion = (
        f"Eres un alquimista lírico y compositor maestro. Tu misión es transmutar la canción hacia la alta frecuencia.\n\n"
        f"{guia_modo}\n\n"
        "REGLAS TÉCNICAS OBLIGATORIAS:\n"
        "1. Mantén la misma estructura métrica y bloques ([Verso 1], [Pre-Coro], [Coro], [Puente], etc.).\n"
        "2. Mantén el conteo silábico, acentuación y rimas para que se pueda cantar exactamente "
        "sobre la misma pista musical (karaoke o beat) original.\n"
        "3. Devuelve únicamente la letra transmutada."
    )

    prompt = (
        f"LETRA ORIGINAL:\n\"\"\"{letra_estructurada}\"\"\"\n\n"
        f"DATOS HAWKINS:\nFrecuencia detectada: {analisis_h.get('frecuencia')}\n"
        f"Elevar hacia: {analisis_h.get('elevacion')}\n"
        f"Clave: {analisis_h.get('clave')}"
    )

    res_trans = client.chat.completions.create(
        model=modelo,
        messages=[
            {"role": "system", "content": instruccion},
            {"role": "user", "content": prompt}
        ],
        temperature=0.4
    )
    letra_trans_res = res_trans.choices[0].message.content

    # Traducimos la transmutada al español si no está en español
    instruccion_trad = (
        "Eres un letrista musical. Traduce la siguiente letra transmutada al español latino natural, "
        "manteniendo las etiquetas entre corchetes ([Verso 1], [Coro], etc.). Devuelve solo el texto."
    )
    res_tr_es = client.chat.completions.create(
        model=modelo,
        messages=[
            {"role": "system", "content": instruccion_trad},
            {"role": "user", "content": letra_trans_res}
        ],
        temperature=0.2
    )

    return letra_trans_res, res_tr_es.choices[0].message.content

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
# PESTAÑA 2: ALQUIMIA LÍRICA (SIN LINK, MÁS VISUAL Y SIN OBLIGAR TEMA)
# --------------------------------------------------------------
with tab_musica:
    st.subheader("🎵 Alquimia Lírica (Escala de Hawkins)")
    st.caption("Pega la letra de cualquier canción para estructurarla, calibrar su vibración y elevarla.")
    
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
            with st.spinner("Estructurando bloques ([Verso], [Coro]) y preparando traducción..."):
                orig, es = estructurar_letra_musical(letra_manual.strip(), GROQ_API_KEY)
                st.session_state.letra_esc_orig = orig
                st.session_state.letra_esc_es = es
                st.session_state.analisis_hawkins = None
                st.session_state.letra_trans_orig = None
                st.session_state.letra_trans_es = None

    # Si hay letra escaneada, la mostramos con pestañas de traducción
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
        st.markdown("#### 🔮 Calibración en el Mapa de Conciencia")
        if st.button("Calibrar", key="btn_calibrar"):
            with st.spinner("Midiendo nivel vibracional con la escala de David R. Hawkins..."):
                st.session_state.analisis_hawkins = calibrar_hawkins_estructurado(
                    st.session_state.letra_esc_orig, GROQ_API_KEY
                )

        # TARJETA VISUAL CON COLOR
        if st.session_state.analisis_hawkins:
            h = st.session_state.analisis_hawkins
            frec_str = h.get("frecuencia", "")

            # Tarjeta visual coloreada
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #1e1b4b 0%, #311042 100%); border-left: 6px solid #f43f5e; padding: 16px 20px; border-radius: 10px; margin: 15px 0;">
                <h4 style="margin: 0 0 8px 0; color: #fb7185;">📊 Frecuencia Detectada: <span style="color: #ffffff; text-decoration: underline;">{frec_str}</span></h4>
                <p style="margin: 4px 0; color: #e2e8f0; font-size: 14px;"><b>⚠️ Patrón emocional:</b> {h.get('patron')}</p>
                <p style="margin: 4px 0; color: #34d399; font-size: 15px;"><b>✨ Frecuencia de Elevación recomendada:</b> {h.get('elevacion')}</p>
                <p style="margin: 4px 0; color: #a78bfa; font-size: 14px;"><b>🔑 Clave de Alquimia:</b> {h.get('clave')}</p>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("---")
            st.markdown("#### ✨ Modo de Transmutación")
            
            # Selector de modo: Misma letra O Nueva temática
            modo_elegido = st.radio(
                "¿Cómo deseas transmutar la canción?",
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
                    with st.spinner("Transmutando la lírica manteniendo métrica y ritmo para cantar sobre la pista..."):
                        t_orig, t_es = transmutar_letra_modo(
                            st.session_state.letra_esc_orig,
                            st.session_state.analisis_hawkins,
                            modo_codigo,
                            tema_nuevo.strip(),
                            GROQ_API_KEY
                        )
                        st.session_state.letra_trans_orig = t_orig
                        st.session_state.letra_trans_es = t_es

            # Mostramos la letra transmutada en pestañas con sus botones Copiar
            if st.session_state.letra_trans_orig:
                st.markdown("""
                <div style="background-color: #064e3b; border-left: 6px solid #10b981; padding: 12px 18px; border-radius: 8px; margin: 15px 0;">
                    <h4 style="margin: 0; color: #a7f3d0;">🎉 ¡Alquimia completada! Letra lista para cantar sobre el beat original</h4>
                </div>
                """, unsafe_allow_html=True)

                tab_t_orig, tab_t_es = st.tabs(["🌐 Versión Original / Transmutada", "🇪🇸 Traducción al Español"])
                with tab_t_orig:
                    boton_copiar(st.session_state.letra_trans_orig, id_btn="cp_t_orig")
                    st.text_area("Letra Transmutada", value=st.session_state.letra_trans_orig, height=260)
                with tab_t_es:
                    boton_copiar(st.session_state.letra_trans_es, id_btn="cp_t_es")
                    st.text_area("Traducción al Español", value=st.session_state.letra_trans_es, height=260)

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
