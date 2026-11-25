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
    "texto_original", "texto_traducido", "tipo_contenido", "descripcion_tipo", "rol_sugerido",
    "orden_agente", "res_analisis", "res_g1", "res_g2", "res_g3"
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
    for n in ["cookies.txt", "cookies.txt.txt", "instagram.com_cookies.txt", "youtube.com_cookies.txt"]:
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
st.caption("Decodifica la psicología de videos virales y crea órdenes listas para Agentes IA.")

def boton_copiar(texto: str, id_btn="copiar", label="📋 Copiar solo lo que se dice", confirm="✅ ¡Copiado!"):
    if not texto:
        return
    texto_json = json.dumps(texto)
    html_code = f"""
    <button onclick="copiar_{id_btn}()" style="
        background-color: #10b981; color: white; border: none; padding: 6px 14px;
        border-radius: 6px; font-weight: 600; cursor: pointer; font-size: 13px;
        display: inline-flex; align-items: center; gap: 4px; margin-bottom: 8px;">
        {label}
    </button>
    <span id="msg_{id_btn}" style="margin-left: 10px; color: #10b981; font-weight: bold; font-size: 13px; display: none;">{confirm}</span>
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

def extraer_solo_guion_hablado(texto_markdown: str) -> str:
    lineas = texto_markdown.strip().split("\n")
    frases = []
    for linea in lineas:
        if "|" in linea:
            columnas = [col.strip() for col in linea.split("|")]
            if len(columnas) >= 4:
                header = columnas[1].lower()
                if any(h in header for h in ["sección", "seccion", "---", ":---"]) or "---" in columnas[2]:
                    continue
                dialogo = columnas[3].strip()
                if (dialogo.startswith('"') and dialogo.endswith('"')) or (dialogo.startswith("“") and dialogo.endswith("”")):
                    dialogo = dialogo[1:-1].strip()
                if dialogo and not dialogo.startswith("---"):
                    frases.append(dialogo)
    return "\n\n".join(frases) if frases else texto_markdown

# EXTRACCIÓN DIRECTA DE SUBTÍTULOS / TRANSCRIPCIÓN OFICIAL (0% ERROR 403)
def obtener_subtitulos_youtube(enlace: str, cookies_file=None):
    try:
        opciones = {
            'skip_download': True,
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
        }
        if cookies_file:
            opciones['cookiefile'] = cookies_file

        with yt_dlp.YoutubeDL(opciones) as ydl:
            info = ydl.extract_info(enlace, download=False)

        if not info:
            return None

        subs = info.get('subtitles') or {}
        auto_subs = info.get('automatic_captions') or {}
        prioridad_idiomas = ['es', 'es-419', 'es-ES', 'es-US', 'en']

        sub_tracks = None
        for lang in prioridad_idiomas:
            for k in subs:
                if k.lower().startswith(lang):
                    sub_tracks = subs[k]
                    break
            if sub_tracks:
                break

        if not sub_tracks:
            for lang in prioridad_idiomas:
                for k in auto_subs:
                    if k.lower().startswith(lang):
                        sub_tracks = auto_subs[k]
                        break
                if sub_tracks:
                    break

        if not sub_tracks:
            if subs:
                sub_tracks = list(subs.values())[0]
            elif auto_subs:
                sub_tracks = list(auto_subs.values())[0]

        if not sub_tracks:
            return None

        sub_url = None
        for track in sub_tracks:
            if track.get('ext') == 'json3':
                sub_url = track.get('url')
                break
        if not sub_url:
            for track in sub_tracks:
                if track.get('ext') in ['vtt', 'srv1', 'srv2', 'srv3']:
                    sub_url = track.get('url')
                    break
        if not sub_url and sub_tracks:
            sub_url = sub_tracks[0].get('url')

        if not sub_url:
            return None

        r = requests.get(sub_url, timeout=10)
        if r.status_code != 200:
            return None

        # Parseo formato json3
        try:
            data = r.json()
            partes = []
            for ev in data.get('events', []):
                for seg in ev.get('segs', []):
                    t = seg.get('utf8', '')
                    if t and t != '\n':
                        partes.append(t)
            if partes:
                texto_unido = "".join(partes)
                return re.sub(r'\s+', ' ', texto_unido).strip()
        except Exception:
            pass

        # Parseo formato VTT / XML
        texto_crudo = r.text
        texto_limpio = re.sub(r'<[^>]+>', '', texto_crudo)
        texto_limpio = re.sub(r'\d{1,2}:\d{2}(?::\d{2})?[.,]\d{3}\s*-->\s*\d{1,2}:\d{2}(?::\d{2})?[.,]\d{3}', '', texto_limpio)
        texto_limpio = re.sub(r'WEBVTT|Kind:.*|Language:.*', '', texto_limpio, flags=re.IGNORECASE)
        lineas = [l.strip() for l in texto_limpio.splitlines() if l.strip()]
        
        dedup = []
        for l in lineas:
            if not dedup or dedup[-1] != l:
                dedup.append(l)

        return ' '.join(dedup).strip() if dedup else None
    except Exception:
        return None

# DESCARGA DE AUDIO (Para TikTok, Instagram o videos de YouTube sin subtítulos)
def extraer_audio_rapido(enlace: str) -> str:
    temp_dir = tempfile.gettempdir()
    out_base = os.path.join(temp_dir, f"audio_{os.getpid()}")
    es_youtube = any(y in enlace.lower() for y in ["youtube.com", "youtu.be"])

    opciones = {
        'format': 'ba[protocol=m3u8]/ba/b' if es_youtube else 'best[vcodec!=none][acodec!=none]/best/ba/b',
        'outtmpl': f"{out_base}.%(ext)s",
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '64',
        }],
        'quiet': True,
        'no_warnings': True,
        'overwrites': True,
        'nocheckcertificate': True,
    }

    if es_youtube:
        opciones['extractor_args'] = {
            'youtube': {'player_client': ['web_embedded', 'android', 'ios']}
        }

    cookies_file = buscar_archivo_cookies()
    if cookies_file:
        opciones['cookiefile'] = cookies_file

    with yt_dlp.YoutubeDL(opciones) as ydl:
        ydl.download([enlace])

    return f"{out_base}.mp3"

def transcribir_con_groq(archivo_o_buffer, api_key: str, nombre_archivo=None) -> str:
    client = get_groq_client(api_key)
    if isinstance(archivo_o_buffer, str):
        nombre_final = os.path.basename(archivo_o_buffer)
        with open(archivo_o_buffer, "rb") as f:
            contenido = f.read()
    else:
        nombre_final = nombre_archivo or "audio.mp3"
        contenido = archivo_o_buffer

    transcription = client.audio.transcriptions.create(
        file=(nombre_final, contenido),
        model="whisper-large-v3-turbo",
        response_format="text",
        temperature=0.0,
        prompt="Transcripción de la voz de la persona hablando en el video sobre negocios, ventas o tecnología."
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
            temperature=0.2,
            max_tokens=2048
        )
        return res.choices[0].message.content.strip()
    except Exception:
        return texto

def clasificar_tipo_contenido(texto: str, api_key: str):
    client = get_groq_client(api_key)
    modelo = obtener_modelo_activo(api_key)
    prompt = f"""Analiza la siguiente transcripción y clasifícala estrictamente en una de dos categorías:
1. EDUCATIVO / MARKETING (Tutorial, negocio, ventas, consejos, marca personal, hack)
2. MINIDRAMA / FICCIÓN / STORYTELLING (Sketch, actuación entre personajes, cine, historia actuada, telenovela corta)

TRANSCRIPCIÓN:
\"{texto[:1500]}\"

RESPONDE OBLIGATORIAMENTE EN ESTE FORMATO:
TIPO: [EDUCATIVO / MARKETING o MINIDRAMA / FICCIÓN]
DESCRIPCIÓN: [Si es educativo: "Aplica la fórmula habitual (dolor, curiosidad, solución, venta)." Si es minidrama: "Extrae el arco dramático (arquetipos de personajes, conflicto, tensión de estatus/venganza/traición, giro inesperado y cliffhanger final), transformando tu nueva idea en un sketch narrativo o minidrama actuado."]
"""
    try:
        res = client.chat.completions.create(
            model=modelo,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=300
        )
        resp = res.choices[0].message.content.strip()
        tipo = "EDUCATIVO / MARKETING"
        desc = "Aplica la fórmula habitual (dolor, curiosidad, solución, venta)."
        rol = "Copywriter de Respuesta Directa y Neuroestratega Viral"
        if "MINIDRAMA" in resp.upper():
            tipo = "MINIDRAMA / FICCIÓN / STORYTELLING"
            desc = "Extrae el arco dramático (arquetipos de personajes, conflicto, tensión de estatus/venganza/traición, giro inesperado y cliffhanger final), transformando tu nueva idea en un sketch narrativo o minidrama actuado."
            rol = "Guionista de Ficción, Cine y Tensión Dramática"
        return tipo, desc, rol
    except Exception:
        return "GENERAL / PERSUASIVO", "Aplica la fórmula de retención y ganchos de alto impacto.", "Estratega de Contenido Viral"

def procesar_transcripcion(texto_crudo: str, api_key: str):
    with ThreadPoolExecutor(max_workers=3) as executor:
        f_orig = executor.submit(formatear_o_traducir_texto, texto_crudo, api_key, False)
        f_trad = executor.submit(formatear_o_traducir_texto, texto_crudo, api_key, True)
        f_tipo = executor.submit(clasificar_tipo_contenido, texto_crudo, api_key)
        
        orig = f_orig.result()
        trad = f_trad.result()
        tipo, desc, rol = f_tipo.result()
        return orig, trad, tipo, desc, rol

def generar_orden_agente_ia(transcripcion: str, tipo_contenido: str, rol_elegido: str, api_key: str) -> str:
    client = get_groq_client(api_key)
    modelo = obtener_modelo_activo(api_key)
    
    prompt = f"""Eres un ingeniero de prompts senior especializado en agentes autónomos de IA y flujos como n8n y LangChain.
Convierte la siguiente TRANSCRIPCIÓN analizada en un MEGA-PROMPT / ORDEN DE SISTEMA altamente específica bajo el estándar RTCE.

PARÁMETROS DE ENTRADA:
- ROL ASIGNADO AL AGENTE: {rol_elegido}
- TIPO DE CONTENIDO: {tipo_contenido}
- TRANSCRIPCIÓN DE REFERENCIA:
\"{transcripcion}\"

TU MISIÓN: Redactar la orden de sistema completa que se le dará a un agente IA para que clone esta fórmula en cualquier nuevo producto o idea.
La orden generada debe contener:
1. Rol e Identidad exacta del Agente.
2. Desglose de la Fórmula Detectada (tipo de hook 0-3s, gatillos de dopamina, curva de retención, técnica de cierre).
3. Parámetros y Variables de Entrada requeridos: [PRODUCTO_O_IDEA], [PÚBLICO_OBJETIVO], [DURACIÓN].
4. Reglas Negativas y Restricciones estrictas (lo que tiene terminantemente prohibido hacer).
5. Estructura de Salida Obligatoria (formato de entrega sin divagaciones).

Devuelve ÚNICAMENTE la orden lista para copiar y pegar."""

    try:
        res = client.chat.completions.create(
            model=modelo,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=2500
        )
        return res.choices[0].message.content.strip()
    except Exception as e:
        return f"Error generando la orden: {e}"

def ejecutar_ingenieria_inversa(transcripcion: str, idea_usuario: str, duracion: str, api_key: str):
    client = get_groq_client(api_key)
    modelo = obtener_modelo_activo(api_key)
    
    if "15-30s" in duracion:
        regla_volumen = """
- REGLA DE DURACIÓN CORTO (15-30 SEGUNDOS):
  * CONTEO TOTAL EN "Qué dice": ENTRE 40 Y 70 PALABRAS.
  * Estructura: Frases rápidas, directas y telegráficas.
"""
    elif "60-90s" in duracion:
        regla_volumen = """
- REGLA DE DURACIÓN LARGO (60-90+ SEGUNDOS):
  * CONTEO TOTAL EN "Qué dice": MÍNIMO 190 PALABRAS, MÁXIMO 260 PALABRAS.
  * OBLIGATORIO: Redacta oraciones largas, explicaciones completas, giros y diálogos profundos para llenar los 60 a 90 segundos.
"""
    else:
        regla_volumen = """
- REGLA DE DURACIÓN ESTÁNDAR (30-60 SEGUNDOS):
  * CONTEO TOTAL EN "Qué dice": ENTRE 100 Y 145 PALABRAS.
  * Estructura: Ritmo equilibrado con ejemplos y desarrollo claro.
"""

    prompt = f"""Eres un director creativo, guionista y neuroestratega viral de primer nivel.
Analiza la siguiente TRANSCRIPCIÓN y aplica sus técnicas a la NUEVA IDEA o HISTORIA del usuario.

REGLA DE FORMATO:
- Si la referencia es EDUCATIVA / VENTA: Aplica la estructura habitual de problema, curiosidad, solución y llamado a la acción comercial.
- Si la referencia es MINIDRAMA / FICCIÓN / HISTORIA: Extrae el arco dramático (tensión de personajes, conflicto, traición, revelación y cliffhanger). Adapta la idea del usuario como un guion narrativo o sketch de varios diálogos.

{regla_volumen}

TUS TAREAS:
1. Evalúa el PUNTAJE DE VIRALIDAD (de 0 a 100) explicando los mecanismos psicológicos y gatillos de dopamina.
2. Escribe 3 GUIONES COMPLETOS adaptados a la nueva idea, cumpliendo con la duración ({duracion}).

CADA GUION DEBE ENTREGARSE COMO UNA TABLA MARKDOWN EXACTA DE 3 COLUMNAS:
| Sección | Dirección (Qué hacer) | Qué dice (Guion verbal) |

- En "Sección": Escribe la fase del guion.
- En "Dirección (Qué hacer)": Indicaciones de cámara, acciones físicas, tono emocional o encuadre.
- En "Qué dice (Guion verbal)": El texto hablado exacto que debe alcanzar el volumen de palabras exigido para llenar los {duracion}.

TRANSCRIPCIÓN:
\"{transcripcion}\"

NUEVA IDEA O HISTORIA DEL USUARIO:
\"{idea_usuario}\"

FORMATO DE ENTREGA OBLIGATORIO:
Usa estrictamente los delimitadores señalados:

<<<ANALISIS>>>
### 📊 Puntaje de Viralidad: [X]/100
- **Mecanismos Psicológicos y Dramáticos:** (Sesgos, instintos o conflicto detectado)
- **Estructura de Retención:** (Curva de atención y apertura de bucles)
- **Efectividad del Cierre:** (Estrategia de conversión o remate emocional)

<<<GUION_1>>>
### 📌 Opción 1: Enfoque Dolor / Conflicto Oculto ({duracion})
| Sección | Dirección (Qué hacer) | Qué dice (Guion verbal) |
| :--- | :--- | :--- |
| **Hook** | [Acción visual] | "Texto hablado" |
| **Conflicto / Curiosidad** | [Lenguaje corporal/acción] | "Texto hablado" |
| **Desarrollo / Giro** | [Indicación de cámara] | "Texto hablado extendido para cumplir el tiempo" |
| **Clímax / Revelación** | [Acción/gesto] | "Texto hablado" |
| **Cierre / CTA** | [Gesto final] | "Texto hablado" |

<<<GUION_2>>>
### 📌 Opción 2: Enfoque Secreto / Misterio Dramático ({duracion})
| Sección | Dirección (Qué hacer) | Qué dice (Guion verbal) |
| :--- | :--- | :--- |
| **Hook** | [Acción visual] | "Texto hablado" |
| **Conflicto / Curiosidad** | [Lenguaje corporal/acción] | "Texto hablado" |
| **Desarrollo / Giro** | [Indicación de cámara] | "Texto hablado extendido para cumplir el tiempo" |
| **Clímax / Revelación** | [Acción/gesto] | "Texto hablado" |
| **Cierre / CTA** | [Gesto final] | "Texto hablado" |

<<<GUION_3>>>
### 📌 Opción 3: Enfoque Shock / Traición o Quiebre Inesperado ({duracion})
| Sección | Dirección (Qué hacer) | Qué dice (Guion verbal) |
| :--- | :--- | :--- |
| **Hook** | [Acción visual] | "Texto hablado" |
| **Conflicto / Curiosidad** | [Lenguaje corporal/acción] | "Texto hablado" |
| **Desarrollo / Giro** | [Indicación de cámara] | "Texto hablado extendido para cumplir el tiempo" |
| **Clímax / Revelación** | [Acción/gesto] | "Texto hablado" |
| **Cierre / CTA** | [Gesto final] | "Texto hablado" |
"""
    res = client.chat.completions.create(
        model=modelo,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=4096
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
            texto_crudo = None
            url_limpia = url.strip()
            cookies_file = buscar_archivo_cookies()

            try:
                # 1. Si es YouTube, extraer transcripción oficial directa (Sin descargas binarias, Cero 403)
                if any(y in url_limpia.lower() for y in ["youtube.com", "youtu.be"]):
                    with st.spinner("⚡ Extrayendo transcripción oficial de YouTube..."):
                        texto_crudo = obtener_subtitulos_youtube(url_limpia, cookies_file)

                # 2. Si no es YouTube o no tenía subtítulos, descargar audio y usar Groq Whisper
                if not texto_crudo:
                    with st.spinner("⚡ Descargando audio del video..."):
                        archivo_temporal = extraer_audio_rapido(url_limpia)
                    with st.spinner("🎙️ Transcribiendo con Whisper Turbo..."):
                        texto_crudo = transcribir_con_groq(archivo_temporal, GROQ_API_KEY)

                if not texto_crudo or not texto_crudo.strip():
                    st.warning("No se detectó voz audible en el video.")
                else:
                    with st.spinner("✨ Analizando contenido, clasificando y estructurando..."):
                        orig, trad, tipo, desc, rol = procesar_transcripcion(texto_crudo, GROQ_API_KEY)
                        st.session_state.texto_original = orig
                        st.session_state.texto_traducido = trad
                        st.session_state.tipo_contenido = tipo
                        st.session_state.descripcion_contenido = desc
                        st.session_state.rol_sugerido = rol
                        st.session_state.orden_agente = None
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
                    with st.spinner("✨ Analizando contenido, clasificando y estructurando..."):
                        orig, trad, tipo, desc, rol = procesar_transcripcion(texto_crudo, GROQ_API_KEY)
                        st.session_state.texto_original = orig
                        st.session_state.texto_traducido = trad
                        st.session_state.tipo_contenido = tipo
                        st.session_state.descripcion_contenido = desc
                        st.session_state.rol_sugerido = rol
                        st.session_state.orden_agente = None
                        st.session_state.res_analisis = None
                        st.session_state.res_g1 = None
                        st.session_state.res_g2 = None
                        st.session_state.res_g3 = None
                        st.success("¡Transcripción lista!")
            except Exception as e:
                st.error(f"Error: {e}")

# ==============================================================
# SALIDA
# ==============================================================
if st.session_state.texto_original:
    st.markdown("---")
    
    if st.session_state.tipo_contenido:
        st.info(f"🏷️ **Tipo de Guion Detectado:** `{st.session_state.tipo_contenido}`\n\n📌 **Estrategia a aplicar:** {st.session_state.descripcion_contenido}")

    st.subheader("📝 Transcripción del Video")
    tab_es, tab_orig = st.tabs(["🇪🇸 Español Latinoamericano", "🌐 Idioma Original"])
    with tab_es:
        boton_copiar(st.session_state.texto_traducido, id_btn="cp_es", label="📋 Copiar Transcripción")
        st.text_area("Texto en Español", value=st.session_state.texto_traducido, height=200, label_visibility="collapsed")
    with tab_orig:
        boton_copiar(st.session_state.texto_original, id_btn="cp_orig", label="📋 Copiar Transcripción")
        st.text_area("Texto Original", value=st.session_state.texto_original, height=200, label_visibility="collapsed")

    # SECCIÓN: ORDEN PARA AGENTE IA
    st.markdown("---")
    st.subheader("🤖 Generar Orden para Agente IA (n8n / ChatGPT / Claude)")
    st.caption("Crea una orden de sistema altamente específica con la fórmula de este video para automatizaciones.")

    col_rol, col_btn_orden = st.columns([3, 1])
    with col_rol:
        rol_usuario = st.text_input(
            "Rol del Agente (Auto-detectado, puedes editarlo):",
            value=st.session_state.rol_sugerido or "Copywriter de Respuesta Directa y Neuroestratega Viral"
        )
    with col_btn_orden:
        st.write("")
        st.write("")
        btn_crear_orden = st.button("⚡ Crear Orden IA", type="secondary", use_container_width=True)

    if btn_crear_orden:
        texto_ref = st.session_state.texto_traducido or st.session_state.texto_original
        with st.spinner("🤖 Diseñando orden estructurada para Agente IA..."):
            orden_generada = generar_orden_agente_ia(
                texto_ref, 
                st.session_state.tipo_contenido or "GENERAL", 
                rol_usuario.strip(), 
                GROQ_API_KEY
            )
            st.session_state.orden_agente = orden_generada

    if st.session_state.orden_agente:
        boton_copiar(st.session_state.orden_agente, id_btn="cp_orden", label="📋 Copiar Orden para Agente IA", confirm="✅ ¡Orden copiada!")
        st.text_area("Orden para el Agente:", value=st.session_state.orden_agente, height=250, label_visibility="collapsed")

    # SECCIÓN: INGENIERÍA INVERSA
    st.markdown("---")
    st.subheader("🔬 Aplicar Ingeniería Inversa a Nueva Idea o Historia")
    
    idea_input = st.text_area(
        "Describe tu idea, producto, servicio o historia a recrear:",
        placeholder=(
            "Ejemplos:\n"
            "• Venta/Educativo: Asesoría de visas, Ropa deportiva personalizada, Clases de oratoria...\n"
            "• Minidrama/Historia: Un cliente humilla a una cajera sin saber que es la dueña / Vender seguros simulando una traición familiar..."
        ),
        height=95
    )

    duracion_opcion = st.radio(
        "⏱️ Duración deseada de los guiones (ajusta el volumen real de palabras habladas):",
        ["Corto (15-30s)", "Estándar (30-60s)", "Largo / Storytelling (60-90s+)"],
        index=1,
        horizontal=True
    )

    if st.button("🚀 Aplicar Ingeniería Inversa", type="primary", use_container_width=True):
        if not idea_input.strip():
            st.warning("Escribe primero tu idea o historia.")
        else:
            base_texto = st.session_state.texto_traducido or st.session_state.texto_original
            with st.spinner(f"🧠 Generando guiones completos sin recortes ({duracion_opcion})..."):
                try:
                    an, g1, g2, g3 = ejecutar_ingenieria_inversa(base_texto, idea_input.strip(), duracion_opcion, GROQ_API_KEY)
                    st.session_state.res_analisis = an
                    st.session_state.res_g1 = g1
                    st.session_state.res_g2 = g2
                    st.session_state.res_g3 = g3
                except Exception as e:
                    st.error(f"Error procesando la ingeniería inversa: {e}")

    if st.session_state.res_analisis:
        st.markdown("---")
        
        st.subheader("🧠 Análisis Psicológico / Dramático & Puntaje")
        st.info(st.session_state.res_analisis)

        st.markdown(f"### 🎬 3 Guiones Adaptados ({duracion_opcion})")
        tab_g1, tab_g2, tab_g3 = st.tabs([
            "📌 Opción 1 (Dolor / Conflicto)", 
            "📌 Opción 2 (Misterio / Secreto)", 
            "📌 Opción 3 (Shock / Traición)"
        ])

        with tab_g1:
            if st.session_state.res_g1:
                solo_hablado_1 = extraer_solo_guion_hablado(st.session_state.res_g1)
                boton_copiar(solo_hablado_1, id_btn="cp_g1")
                st.markdown(st.session_state.res_g1)

        with tab_g2:
            if st.session_state.res_g2:
                solo_hablado_2 = extraer_solo_guion_hablado(st.session_state.res_g2)
                boton_copiar(solo_hablado_2, id_btn="cp_g2")
                st.markdown(st.session_state.res_g2)

        with tab_g3:
            if st.session_state.res_g3:
                solo_hablado_3 = extraer_solo_guion_hablado(st.session_state.res_g3)
                boton_copiar(solo_hablado_3, id_btn="cp_g3")
                st.markdown(st.session_state.res_g3)
