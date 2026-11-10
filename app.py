import os
import re
import json
import requests
import streamlit as st
import streamlit.components.v1 as components
import yt_dlp
from groq import Groq

# 1. Configuración de página primero para evitar pantallas en blanco
st.set_page_config(page_title="Suite Creativa & Alquimia Lírica", page_icon="⚡", layout="centered")

# Activa FFmpeg: en la nube usa el de packages.txt; en local usa static_ffmpeg
try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except Exception:
    pass

st.title("⚡ Suite Creativa & Alquimia Lírica")
st.caption("Videos Virales, Guiones con IA y Transmutación Musical Hawkins")

# Memoria de sesión limpia y segura
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

# ==============================================================
# MAPA COMPLETO DE HAWKINS: VIRALIDAD + TEMAS BAJOS Y ALTOS
# ==============================================================
HAWKINS_SCALE = {
    20: {
        "nombre": "Vergüenza (20)",
        "emocion": "Humillación / Desprecio",
        "viralidad": "84%",
        "tipo_viral": "Exposición, vulnerabilidad extrema ('Storytime de lo peor que me pasó').",
        "color": "#7f1d1d",
        "temas_baja": ["El secreto que me avergüenza y nadie sabe", "Sintiéndome la burla de todos", "Escondiéndome del mundo"],
        "temas_alta": ["Perdonarme por haberme fallado", "La humillación que forjó mi carácter", "Digno de existir sin pedir permiso"]
    },
    30: {
        "nombre": "Culpa (30)",
        "emocion": "Remordimiento / Castigo",
        "viralidad": "89%",
        "tipo_viral": "Baladas desgarradoras de arrepentimiento y deudas morales.",
        "color": "#991b1b",
        "temas_baja": ["Fui yo quien arruinó todo", "Cargando con la culpa que me asfixia", "Demasiado tarde para pedir perdón"],
        "temas_alta": ["Soltar la cruz que no me corresponde", "Me perdono por no haber sabido más", "De la culpa nace mi redención"]
    },
    50: {
        "nombre": "Apatía (50)",
        "emocion": "Desesperanza / Indiferencia",
        "viralidad": "80%",
        "tipo_viral": "Canciones 'sad', nihilismo adolescente y vacío existencial compartido.",
        "color": "#9a3412",
        "temas_baja": ["Ya nada me importa ni me duele", "El cansancio crónico de existir", "Viendo los días pasar sin sentido"],
        "temas_alta": ["Una chispa en medio de la niebla", "Elegir sentir aunque dé miedo", "Despertar del coma emocional"]
    },
    75: {
        "nombre": "Pena / Duelo (75)",
        "emocion": "Tristeza / Pérdida",
        "viralidad": "94%",
        "tipo_viral": "Duelo compartido, despedidas inevitables (Efecto Adele / Sam Smith).",
        "color": "#c2410c",
        "temas_baja": ["Extrañarte me está matando", "Nuestra casa vacía sin tu voz", "Llorando en la madrugada por ti"],
        "temas_alta": ["Aprender a honrar lo que fue", "Agradecerte el tiempo compartido", "Llevarte en el alma sin dolor"]
    },
    100: {
        "nombre": "Miedo (100)",
        "emocion": "Ansiedad / Amenaza",
        "viralidad": "91%",
        "tipo_viral": "Paranoia, miedo al rechazo, temor a quedarse solo.",
        "color": "#b45309",
        "temas_baja": ["Pánico a que me dejes solo", "La ansiedad que me paraliza el pecho", "Corriendo de mis propios demonios"],
        "temas_alta": ["Abrazar el miedo y avanzar temblando", "La tormenta no me puede quebrar", "Confiar en lo desconocido"]
    },
    125: {
        "nombre": "Deseo / Apego (125)",
        "emocion": "Anhelo / Lujuria / Obsesión",
        "viralidad": "97%",
        "tipo_viral": "Reggaeton, sensualidad insaciable, amor prohibido, ambición (Trap/Urbano).",
        "color": "#a16207",
        "temas_baja": ["Obsesión carnal que me domina", "Tenerte aunque seas un veneno", "Quererlo todo y nunca estar lleno"],
        "temas_alta": ["Atracción consciente y magnética", "Canalizar la pasión en creación pura", "Amor que nutre sin encadenar"]
    },
    150: {
        "nombre": "Ira / Rabia (150)",
        "emocion": "Resentimiento / Venganza",
        "viralidad": "99%",
        "tipo_viral": "Tiraderas brutales, despecho furioso, sed de venganza (Efecto Shakira / BZRP).",
        "color": "#dc2626",
        "temas_baja": ["Tiradera sin piedad contra mi ex", "Que te duela el doble de lo que me dolió", "Ardiendo de furia contra la traición"],
        "temas_alta": ["Convertir la rabia en disciplina de fuego", "Mi mejor venganza es mi éxito rotundo", "Poner límites inquebrantables"]
    },
    175: {
        "nombre": "Orgullo (175)",
        "emocion": "Superioridad / Egolatría",
        "viralidad": "95%",
        "tipo_viral": "Flexing, presumir riqueza y fama, 'nadie creía en mí' (Hip Hop / Corridos).",
        "color": "#e11d48",
        "temas_baja": ["Mírame en la cima y tú abajo", "No necesito de nadie para ganar", "Soy mejor que todos ustedes"],
        "temas_alta": ["Orgullo sano de mis raíces", "Honrar las cicatrices de la victoria", "Celebrar el triunfo con humildad"]
    },
    200: {
        "nombre": "Coraje (200) [Umbral]",
        "emocion": "Valentía / Determinación",
        "viralidad": "93%",
        "tipo_viral": "Himnos de batalla deportiva, levantarse de las cenizas (Efecto Rocky).",
        "color": "#16a34a",
        "temas_baja": ["Gritar aunque me tiemble la voz", "Luchar acorralado contra el mundo", "Dejar la sangre en el intento"],
        "temas_alta": ["Me caigo diez veces y me paro once", "El momento exacto de dar el salto", "Arquitecto de mi propio destino"]
    },
    250: {
        "nombre": "Neutralidad (250)",
        "emocion": "Confianza / Desapego",
        "viralidad": "82%",
        "tipo_viral": "Filosofía 'cero drama', fluir con lo que venga, desapego tranquilo.",
        "color": "#0d9488",
        "temas_baja": ["Me cansé de pelear por tonterías", "Que cada quien haga lo suyo", "Poco me importa lo que opinen"],
        "temas_alta": ["La dulce calma de no reaccionar", "Fluyendo en armonía con el río", "Tranquilidad por encima de la razón"]
    },
    310: {
        "nombre": "Voluntad (310)",
        "emocion": "Optimismo / Disciplina",
        "viralidad": "88%",
        "tipo_viral": "Motivación imparable, disciplina de hierro, mentalidad de crecimiento.",
        "color": "#0284c7",
        "temas_baja": ["Forzar la máquina hasta el límite", "No dormir hasta conseguir la meta", "La obsesión de ganar a toda costa"],
        "temas_alta": ["Disciplina diaria con amor al arte", "Construyendo un legado paso a paso", "Optimismo inquebrantable ante el reto"]
    },
    350: {
        "nombre": "Aceptación (350)",
        "emocion": "Perdón / Trascendencia",
        "viralidad": "92%",
        "tipo_viral": "Cierre de ciclos en paz, reconciliación profunda, sanar el pasado.",
        "color": "#2563eb",
        "temas_baja": ["Aceptar la derrota y soltar", "Reconocer que se terminó el juego", "Firmar la tregua con mi dolor"],
        "temas_alta": ["Te perdono y me libero para siempre", "Cerrar la puerta con gratitud genuina", "Aceptar quién fui para amar quién soy"]
    },
    400: {
        "nombre": "Razón / Sabiduría (400)",
        "emocion": "Claridad / Discernimiento",
        "viralidad": "85%",
        "tipo_viral": "Rap consciente, metáforas filosóficas, juegos de palabras profundos.",
        "color": "#4f46e5",
        "temas_baja": ["Diseccionando la falsedad de la sociedad", "La trampa mental de las masas", "Análisis frío del desamor"],
        "temas_alta": ["Comprender el orden oculto del caos", "Sabiduría destilada en rima pura", "La mente serena que todo lo ve"]
    },
    500: {
        "nombre": "Amor Incondicional (500)",
        "emocion": "Compasión / Reverencia",
        "viralidad": "96%",
        "tipo_viral": "Himnos eternos de amor que erizan la piel (Coldplay, Bob Marley).",
        "color": "#7c3aed",
        "temas_baja": ["Amor que duele de tan inmenso", "Darlo todo sin esperar rescate", "Amar en medio de la tormenta"],
        "temas_alta": ["Amor que no pide nada a cambio", "Sanar al mundo con la mirada", "Encontrarte en los ojos de todos"]
    },
    540: {
        "nombre": "Alegría Serena (540)",
        "emocion": "Éxtasis / Celebración",
        "viralidad": "97%",
        "tipo_viral": "Fiesta contagiosa, felicidad pura de vivir ('Happy', funk, baile sin motivo).",
        "color": "#c026d3",
        "temas_baja": ["Bailar para olvidar las penas", "Locura de euforia desmedida", "Gritar hasta que se vaya el dolor"],
        "temas_alta": ["El milagro glorioso de estar vivos", "Bailar bajo la lluvia sin motivo", "La risa que despierta corazones"]
    },
    600: {
        "nombre": "Paz / Unidad (600)",
        "emocion": "Serenidad / Trascendencia",
        "viralidad": "78%",
        "tipo_viral": "Música contemplativa, silencio sonoro, trance pacífico.",
        "color": "#059669",
        "temas_baja": ["El silencio después de la catástrofe", "Aislarse del ruido del mundo", "La calma de la rendición"],
        "temas_alta": ["El océano de paz dentro del pecho", "Ser uno con el latido cósmico", "La luz infinita que nunca se apaga"]
    }
}

def buscar_archivo_cookies():
    nombres = ["cookies.txt", "cookies.txt.txt", "instagram.com_cookies.txt"]
    for n in nombres:
        if os.path.exists(n):
            return n
    return None

# ==============================================================
# BARRA LATERAL
# ==============================================================
with st.sidebar:
    st.header("⚙️ Configuración")
    if not GROQ_API_KEY:
        GROQ_API_KEY = st.text_input("Groq API Key:", type="password", placeholder="gsk_...")
    
    st.subheader("Sesión de Instagram")
    cookie_subida = st.file_uploader("Sube cookies.txt aquí:", type=["txt"], key="uploader_cookies")
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
    if traducir:
        instruccion = "Traduce el texto al español latino neutro en párrafos limpios separados por salto doble. Devuelve solo el texto."
    else:
        instruccion = "Organiza el texto en párrafos limpios separados por doble salto de línea. Devuelve solo el texto."

    res = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": instruccion},
            {"role": "user", "content": texto}
        ],
        temperature=0.3
    )
    return res.choices[0].message.content

def generar_ideas_y_guiones(transcripcion, nicho_usuario, api_key):
    client = Groq(api_key=api_key)
    prompt_sistema = (
        "Eres un estratega de contenido viral. Desarma la fórmula del video y genera 3 ideas con sus guiones adaptados.\n"
        "Estructura: 1. Radiografía viral, 2. Banco de 3 ideas, 3. Guiones con acotaciones visuales [0-3s], [3-20s], [20-30s]."
    )
    res = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": f"REFERENCIA:\n{transcripcion}\n\nNICHO:\n{nicho_usuario}"}
        ],
        temperature=0.4
    )
    return res.choices[0].message.content

# ==============================================================
# ALQUIMIA LÍRICA: MOTOR DE LLAMADA DIRECTA (100% GARANTIZADO)
# ==============================================================
def estructurar_letra_musical(letra_cruda, api_key):
    client = Groq(api_key=api_key)
    instruccion = (
        "Eres un productor musical. Organiza este texto en bloques musicales con corchetes: "
        "[Verse 1], [Pre-Chorus], [Chorus], [Verse 2], [Bridge], [Chorus], [Outro]. "
        "Separa cada bloque con doble salto de línea (\\n\\n). Cada verso en una línea individual."
    )
    res_orig = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": instruccion},
            {"role": "user", "content": letra_cruda}
        ],
        temperature=0.2
    )
    letra_orig = res_orig.choices[0].message.content

    instruccion_es = "Traduce al español manteniendo exactamente las etiquetas [Verso 1], [Coro], etc. y los dobles saltos de línea."
    res_es = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": instruccion_es},
            {"role": "user", "content": letra_orig}
        ],
        temperature=0.2
    )
    return letra_orig, res_es.choices[0].message.content

def calibrar_hawkins_estructurado(letra_texto, api_key):
    client = Groq(api_key=api_key)
    prompt = f"""Analiza la siguiente letra según la Escala de Hawkins (20 a 600 puntos):
\"\"\"{letra_texto}\"\"\"

Responde exactamente con estas líneas:
FRECUENCIA: [Emoción y puntos]
ELEVACION: [Frecuencia opuesta sugerida]
CLAVE: [Concepto clave de transformación]"""

    res = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )
    lineas = res.choices[0].message.content.split("\n")
    datos = {"frecuencia": "Culpa (30 puntos)", "elevacion": "Aceptación (350)", "clave": "Perdón y redención"}
    for l in lineas:
        if l.startswith("FRECUENCIA:"):
            datos["frecuencia"] = l.replace("FRECUENCIA:", "").strip()
        elif l.startswith("ELEVACION:"):
            datos["elevacion"] = l.replace("ELEVACION:", "").strip()
        elif l.startswith("CLAVE:"):
            datos["clave"] = l.replace("CLAVE:", "").strip()
    return datos

def transmutar_letra_directa(letra_base, frec_num, rima_tipo, modo, tema, api_key):
    """Llamada ultra rápida garantizada que genera Español e Inglés con párrafos limpios"""
    client = Groq(api_key=api_key)
    frec_info = HAWKINS_SCALE.get(frec_num, HAWKINS_SCALE[500])

    if modo == "misma":
        enfoque_prompt = (
            "ENFOQUE: REESCRIBIR LA MISMA HISTORIA EN ESTA FRECUENCIA.\n"
            "- Mantén los mismos personajes, dolor o situación original.\n"
            f"- Reescribe el mensaje desde la frecuencia: {frec_info['nombre']} ({frec_info['emocion']})."
        )
    else:
        enfoque_prompt = (
            f"ENFOQUE: CREAR CANCIÓN SOBRE ESTA TEMÁTICA: \"{tema}\".\n"
            f"- Desarrolla esta temática vibrando en: {frec_info['nombre']} ({frec_info['emocion']})."
        )

    prompt = f"""Eres un letrista y compositor maestro. Tu tarea es componer la letra de la canción.

{enfoque_prompt}

REGLAS DE MÉTRICA Y RIMA:
1. Esquema de rima obligatorio en todas las estrofas: {rima_tipo}.
2. Estructura formal obligatoria: [Verso 1], [Pre-Coro], [Coro], [Verso 2], [Puente], [Coro Final], [Outro].
3. Formato: Separa cada bloque musical con un salto de línea doble (\\n\\n). Cada verso en una línea limpia y cantable.

LETRA DE REFERENCIA:
{letra_base}

ENTREGA OBLIGATORIA:
Entrega primero la versión en ESPAÑOL, luego exactamente la línea de separación "=== DIVISION_IDIOMA ===", y después la versión en INGLÉS adaptada.
"""

    res = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4
    )

    contenido = res.choices[0].message.content
    if "=== DIVISION_IDIOMA ===" in contenido:
        partes = contenido.split("=== DIVISION_IDIOMA ===")
        return partes[0].strip(), partes[1].strip()
    else:
        return contenido.strip(), contenido.strip()

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
# PESTAÑA 2: ALQUIMIA LÍRICA (MOTOR DIRECTO Y SEGURO)
# --------------------------------------------------------------
with tab_musica:
    st.subheader("🎵 Alquimia Lírica (Escala de Hawkins)")
    st.caption("Pega cualquier letra, analiza su resonancia viral y transmútala.")
    
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
            st.warning("Pega la letra de la canción antes de escanear.")
        else:
            with st.spinner("Estructurando bloques en párrafos limpios..."):
                try:
                    orig, es = estructurar_letra_musical(letra_manual.strip(), GROQ_API_KEY)
                    st.session_state.letra_esc_orig = orig
                    st.session_state.letra_esc_es = es
                except Exception as e:
                    st.error(f"Error al estructurar: {e}")

    # Si hay letra escaneada, la mostramos
    if st.session_state.letra_esc_orig:
        st.markdown("#### 🎼 Letra Estructurada")
        tab_l_orig, tab_l_es = st.tabs(["🌐 Original", "🇪🇸 Traducción al Español"])
        with tab_l_orig:
            boton_copiar(st.session_state.letra_esc_orig, id_btn="cp_esc_orig")
            st.text_area("Original", value=st.session_state.letra_esc_orig, height=180)
        with tab_l_es:
            boton_copiar(st.session_state.letra_esc_es, id_btn="cp_esc_es")
            st.text_area("Español", value=st.session_state.letra_esc_es, height=180)

        # 2. BOTÓN: CALIBRAR
        if st.button("Calibrar", key="btn_calibrar"):
            with st.spinner("Midiendo frecuencia..."):
                try:
                    st.session_state.analisis_hawkins = calibrar_hawkins_estructurado(
                        st.session_state.letra_esc_orig, GROQ_API_KEY
                    )
                except Exception as e:
                    st.error(f"Error al calibrar: {e}")

        if st.session_state.analisis_hawkins:
            h = st.session_state.analisis_hawkins
            st.info(f"📊 **Frecuencia Detectada:** {h.get('frecuencia')} | **Elevación:** {h.get('elevacion')} | **Clave:** {h.get('clave')}")

    # ==============================================================
    # SLIDER HAWKINS + VIRALIDAD + TEMAS BAJOS Y ALTOS
    # ==============================================================
    st.markdown("---")
    st.markdown("### 🎚️ Escala de Vibración & Conexión Viral")
    st.caption("Desliza para explorar la resonancia viral y los temas en cada nivel:")

    frec_seleccionada = st.select_slider(
        "Nivel de Frecuencia Hawkins:",
        options=list(HAWKINS_SCALE.keys()),
        value=500,
        format_func=lambda x: HAWKINS_SCALE[x]["nombre"]
    )

    info_frec = HAWKINS_SCALE[frec_seleccionada]

    # Tarjeta de Viralidad y Temas (Bajos y Altos)
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #090d16 0%, #111827 100%); border-left: 6px solid {info_frec['color']}; padding: 18px 22px; border-radius: 12px; margin: 15px 0;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <h3 style="margin: 0; color: #ffffff;">{info_frec['nombre']}</h3>
            <span style="background-color: {info_frec['color']}; color: white; padding: 4px 12px; border-radius: 20px; font-weight: bold; font-size: 14px;">🔥 Viralidad: {info_frec['viralidad']}</span>
        </div>
        <p style="margin: 8px 0 4px 0; color: #94a3b8; font-size: 14px;"><b>Campo Emocional:</b> <span style="color: #f1f5f9;">{info_frec['emocion']}</span></p>
        <p style="margin: 4px 0 12px 0; color: #94a3b8; font-size: 14px;"><b>Psicología de Conexión:</b> <span style="color: #38bdf8;">{info_frec['tipo_viral']}</span></p>
        
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 10px;">
            <div style="background-color: rgba(220, 38, 38, 0.12); border: 1px solid rgba(220, 38, 38, 0.3); padding: 10px; border-radius: 8px;">
                <span style="color: #f87171; font-weight: bold; font-size: 13px;">🔥 3 Temas de Baja Vibración (Catarsis / Despecho):</span>
                <ul style="margin: 6px 0 0 0; padding-left: 18px; color: #fecaca; font-size: 12px;">
                    <li>{info_frec['temas_baja'][0]}</li>
                    <li>{info_frec['temas_baja'][1]}</li>
                    <li>{info_frec['temas_baja'][2]}</li>
                </ul>
            </div>
            <div style="background-color: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.3); padding: 10px; border-radius: 8px;">
                <span style="color: #34d399; font-weight: bold; font-size: 13px;">✨ 3 Temas de Alta Vibración (Elevación / Poder):</span>
                <ul style="margin: 6px 0 0 0; padding-left: 18px; color: #a7f3d0; font-size: 12px;">
                    <li>{info_frec['temas_alta'][0]}</li>
                    <li>{info_frec['temas_alta'][1]}</li>
                    <li>{info_frec['temas_alta'][2]}</li>
                </ul>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ==============================================================
    # CONFIGURACIÓN Y TRANSMUTACIÓN DIRECTA
    # ==============================================================
    st.markdown("---")
    st.markdown("### ✨ Configurar y Componer Letra")

    col_rima, col_modo = st.columns([1, 1])

    with col_rima:
        tipo_rima_elegida = st.selectbox(
            "Estructura de Rima:",
            options=["AABB (Pareado clásico)", "ABAB (Alterna pop)", "AAAA (Monorrima contundente)", "ABCB (Balada tradicional)"],
            index=1
        )

    with col_modo:
        modo_elegido = st.radio(
            "Enfoque de Composición:",
            options=[
                "Elevar la misma historia original",
                "Elegir tema de Baja Vibración (Catarsis)",
                "Elegir tema de Alta Vibración (Elevación)",
                "Tema libre personalizado"
            ],
            index=0
        )

    tema_para_enviar = ""
    if modo_elegido == "Elegir tema de Baja Vibración (Catarsis)":
        tema_para_enviar = st.selectbox("Selecciona el tema de baja vibración:", options=info_frec['temas_baja'])
    elif modo_elegido == "Elegir tema de Alta Vibración (Elevación)":
        tema_para_enviar = st.selectbox("Selecciona el tema de alta vibración:", options=info_frec['temas_alta'])
    elif modo_elegido == "Tema libre personalizado":
        tema_para_enviar = st.text_input("Escribe tu temática:", placeholder="Ej: Triunfo personal, Paz mental, Un amor sano...")

    # CONTENEDOR VISUAL DIRECTAMENTE DEBAJO DEL BOTÓN TRANSMUTAR
    st.markdown(" ")
    
    # 3. BOTÓN: TRANSMUTAR
    if st.button("Transmutar", type="primary", key="btn_transmutar"):
        if not GROQ_API_KEY.strip():
            st.error("Por favor ingresa tu Groq API Key en la barra lateral.")
        else:
            letra_base = st.session_state.letra_esc_orig or letra_manual.strip()
            
            if not letra_base:
                st.warning("Por favor pega la letra de la canción arriba en el recuadro antes de transmutar.")
            elif modo_elegido == "Tema libre personalizado" and not tema_para_enviar.strip():
                st.warning("Por favor escribe la temática que deseas.")
            else:
                modo_codigo = "misma" if modo_elegido == "Elevar la misma historia original" else "nuevo"
                
                with st.spinner("Componiendo letra rítmica en párrafos limpios (Español e Inglés)..."):
                    try:
                        es_txt, en_txt = transmutar_letra_directa(
                            letra_base=letra_base,
                            frec_num=frec_seleccionada,
                            rima_tipo=tipo_rima_elegida,
                            modo=modo_codigo,
                            tema=tema_para_enviar.strip(),
                            api_key=GROQ_API_KEY
                        )
                        st.session_state.letra_trans_es = es_txt
                        st.session_state.letra_trans_en = en_txt
                    except Exception as e:
                        st.error(f"Error de conexión con Groq: {e}")

    # CUADRO QUE SE ABRE INMEDIATAMENTE DEBAJO DEL BOTÓN CON LA NUEVA LETRA
    if st.session_state.letra_trans_es:
        st.markdown("---")
        st.markdown(f"""
        <div style="background-color: #064e3b; border-left: 6px solid #10b981; padding: 14px 20px; border-radius: 8px; margin: 15px 0;">
            <h4 style="margin: 0; color: #a7f3d0;">🎉 ¡Letra compuesta con éxito! Lista para cantar sobre la pista</h4>
        </div>
        """, unsafe_allow_html=True)

        tab_t_es, tab_t_en = st.tabs(["🇪🇸 Letra en Español", "🇺🇸 Letra en Inglés"])
        with tab_t_es:
            boton_copiar(st.session_state.letra_trans_es, id_btn="cp_t_es")
            st.text_area("Español (Párrafos limpios)", value=st.session_state.letra_trans_es, height=350)
        with tab_t_en:
            boton_copiar(st.session_state.letra_trans_en, id_btn="cp_t_en")
            st.text_area("Inglés (Clean Stanzas)", value=st.session_state.letra_trans_en, height=350)

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
