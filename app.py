import os
import re
import json
import requests
import streamlit as st
import streamlit.components.v1 as components
import yt_dlp
from groq import Groq

# 1. Configuración de página primero
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

# BASE DE DATOS DE LA ESCALA DE DAVID R. HAWKINS
HAWKINS_SCALE = {
    20: {
        "nombre": "Vergüenza (20)",
        "emocion": "Humillación / Desprecio",
        "viralidad": "82%",
        "tipo_viral": "Vulnerabilidad extrema ('Storytime de lo peor que me pasó').",
        "color": "#991b1b",
        "temas": ["Mi mayor fracaso y lo que aprendí", "El secreto que nadie se atreve a contar", "Superando la humillación pública"]
    },
    30: {
        "nombre": "Culpa (30)",
        "emocion": "Remordimiento / Castigo",
        "viralidad": "89%",
        "tipo_viral": "Baladas de perdón, desahogo de errores pasados, redención.",
        "color": "#b91c1c",
        "temas": ["Pedir perdón antes de que sea tarde", "El error que casi me destruye", "Sanando con mi pasado"]
    },
    50: {
        "nombre": "Apatía (50)",
        "emocion": "Desesperanza / Indiferencia",
        "viralidad": "78%",
        "tipo_viral": "Nihilismo, canciones 'sad' y vacío existencial compartido.",
        "color": "#c2410c",
        "temas": ["Cuando ya no sientes nada", "El cansancio de intentarlo siempre", "Despertar del vacío"]
    },
    75: {
        "nombre": "Pena / Duelo (75)",
        "emocion": "Tristeza / Pérdida",
        "viralidad": "93%",
        "tipo_viral": "Duelo compartido, despedidas, rupturas dolorosas (Efecto Adele).",
        "color": "#ea580c",
        "temas": ["Dejar ir a quien amabas", "El dolor de los recuerdos", "Aprender a vivir con tu ausencia"]
    },
    100: {
        "nombre": "Miedo (100)",
        "emocion": "Ansiedad / Amenaza",
        "viralidad": "90%",
        "tipo_viral": "Temor a perder a alguien, paranoia, vulnerabilidad íntima.",
        "color": "#d97706",
        "temas": ["Miedo a quedarme solo", "La ansiedad que no me deja dormir", "Venciendo el pánico a fracasar"]
    },
    125: {
        "nombre": "Deseo / Apego (125)",
        "emocion": "Anhelo / Lujuria / Obsesión",
        "viralidad": "96%",
        "tipo_viral": "Reggaeton, sensualidad, anhelo de lo prohibido, ambición (Efecto Trap).",
        "color": "#ca8a04",
        "temas": ["Obsesión por tenerte cerca", "Hambre insaciable de éxito y dinero", "Una noche inolvidable"]
    },
    150: {
        "nombre": "Ira / Rabia (150)",
        "emocion": "Resentimiento / Venganza",
        "viralidad": "98%",
        "tipo_viral": "Despecho brutal, tiraderas, catarsis de rabia (Efecto Shakira / Eminem).",
        "color": "#dc2626",
        "temas": ["Tiradera y ajuste de cuentas con un ex", "Rebeldía furiosa contra el sistema", "No me vuelves a ver la cara"]
    },
    175: {
        "nombre": "Orgullo (175)",
        "emocion": "Superioridad / Egolatría",
        "viralidad": "94%",
        "tipo_viral": "Flexing, presumir logros, 'ahora mírame triunfar', empoderamiento de ego.",
        "color": "#e11d48",
        "temas": ["Nadie creía en mí y ahora brillo", "Tengo lo que siempre soñé", "Soy intocable y estoy en la cima"]
    },
    200: {
        "nombre": "Coraje (200) [Umbral de Poder]",
        "emocion": "Valentía / Determinación",
        "viralidad": "92%",
        "tipo_viral": "Himnos de batalla, levantarse tras la caída (Efecto Rocky).",
        "color": "#16a34a",
        "temas": ["Me caí diez veces y me levanto once", "El momento de dar el paso", "Sin miedo a empezar de cero"]
    },
    250: {
        "nombre": "Neutralidad (250)",
        "emocion": "Confianza / Desapego",
        "viralidad": "81%",
        "tipo_viral": "Filosofía 'me da igual lo que digan', fluir con la vida, relax total.",
        "color": "#0d9488",
        "temas": ["Ya nada me quita la tranquilidad", "Vivir sin drama ni ataduras", "Dejar que todo fluya a su tiempo"]
    },
    310: {
        "nombre": "Voluntad (310)",
        "emocion": "Optimismo / Disciplina",
        "viralidad": "87%",
        "tipo_viral": "Motivación de gimnasio, disciplina inquebrantable, superación constante.",
        "color": "#0284c7",
        "temas": ["Disciplina sobre motivación", "Construyendo mi propio destino", "Cada día un 1% mejor"]
    },
    350: {
        "nombre": "Aceptación (350)",
        "emocion": "Perdón / Trascendencia",
        "viralidad": "91%",
        "tipo_viral": "Cierre de ciclos con paz, perdonar al pasado, sanar sin rencor.",
        "color": "#2563eb",
        "temas": ["Te perdono no por ti, sino por mí", "Cerrar la puerta con gratitud", "Aceptar quién fui para amar quién soy"]
    },
    400: {
        "nombre": "Razón / Sabiduría (400)",
        "emocion": "Claridad / Discernimiento",
        "viralidad": "84%",
        "tipo_viral": "Letras con juegos mentales, metáforas profundas, rap consciente.",
        "color": "#4f46e5",
        "temas": ["Entender las leyes del juego", "La mente sobre la emoción", "Desenmascarando la ilusión"]
    },
    500: {
        "nombre": "Amor Incondicional (500)",
        "emocion": "Compasión / Reverencia",
        "viralidad": "95%",
        "tipo_viral": "Himnos atemporales de amor puro y conexión universal (Coldplay, Marley).",
        "color": "#7c3aed",
        "temas": ["Amor que no pide nada a cambio", "Sanar al mundo con bondad", "Encontrarte en los ojos de todos"]
    },
    540: {
        "nombre": "Alegría Serena (540)",
        "emocion": "Éxtasis / Celebración",
        "viralidad": "96%",
        "tipo_viral": "Canciones de felicidad contagiosa ('Happy', funk, baile sin motivo).",
        "color": "#c026d3",
        "temas": ["Celebrar el simple milagro de respirar", "Bailar bajo la lluvia", "La risa que contagia a todos"]
    },
    600: {
        "nombre": "Paz / Unidad (600)",
        "emocion": "Serenidad / Trascendencia",
        "viralidad": "76%",
        "tipo_viral": "Música contemplativa profunda, calma inquebrantable.",
        "color": "#059669",
        "temas": ["El silencio donde habita todo", "Ser uno con el universo", "La calma inquebrantable del alma"]
    }
}

def buscar_archivo_cookies():
    nombres = ["cookies.txt", "cookies.txt.txt", "instagram.com_cookies.txt"]
    for n in nombres:
        if os.path.exists(n):
            return n
    return None

# ==============================================================
# BARRA LATERAL: CONFIGURACIÓN + LEAD MAGNETS
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
    """Botón de 1 sola palabra para copiar al portapapeles con guardas seguras"""
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
# ALQUIMIA LÍRICA (HAWKINS) - MOTOR ROBUSTO Y SEGURO
# ==============================================================
def estructurar_letra_musical(letra_cruda, api_key):
    """Estructura la letra en párrafos limpios y genera traducción al español"""
    client = Groq(api_key=api_key)
    modelo = obtener_modelo_texto_activo(client)
    
    instruccion = (
        "Eres un productor y compositor musical experto. Analiza el texto de esta canción "
        "y organízalo en su estructura musical formal con formato impecable.\n\n"
        "REGLAS:\n"
        "1. Etiqueta claramente cada sección entre corchetes: [Verse 1], [Pre-Chorus], [Chorus], [Verse 2], [Bridge], [Outro].\n"
        "2. Separa cada sección con un salto de línea doble (\\n\\n).\n"
        "3. Cada verso debe ser una línea individual y limpia.\n"
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
    """Mide la frecuencia de Hawkins"""
    client = Groq(api_key=api_key)
    modelo = obtener_modelo_texto_activo(client)
    
    prompt = f"""Eres un analista de psicología musical experto en el Mapa de Conciencia de David R. Hawkins (Power vs. Force).
Analiza la siguiente letra:
\"\"\"{letra_texto}\"\"\"

Determina:
1. Frecuencia y número de puntos dominante (ej: Culpa 30, Ira 150, Deseo 125, etc.).
2. Frecuencia Opuesta de Elevación.
3. Clave Alquímica (concepto central de transformación).

Responde con líneas que comiencen exactamente con estas etiquetas:
FRECUENCIA: [Emoción y número de puntos]
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
        "elevacion": "Aceptación (350) / Amor Incondicional (500)",
        "clave": "Perdón propio y redención"
    }
    
    for l in lineas:
        if l.startswith("FRECUENCIA:"):
            datos["frecuencia"] = l.replace("FRECUENCIA:", "").strip()
        elif l.startswith("ELEVACION:"):
            datos["elevacion"] = l.replace("ELEVACION:", "").strip()
        elif l.startswith("CLAVE:"):
            datos["clave"] = l.replace("CLAVE:", "").strip()
            
    return datos

def transmutar_letra_motor_unificado(letra_base, frec_target, rima_tipo, modo, tema_personalizado, api_key):
    """Genera las letras en Inglés y Español en una SOLA llamada rápida sin fallos de cuota"""
    client = Groq(api_key=api_key)
    modelo = obtener_modelo_texto_activo(client)
    
    frec_data = HAWKINS_SCALE.get(frec_target, HAWKINS_SCALE[500])
    
    if modo == "misma":
        guia_modo = (
            "MODO: ELEVAR LA MISMA HISTORIA:\n"
            "- Conserva los mismos personajes, dolor o vivencia de la canción original.\n"
            "- Eleva la perspectiva: en lugar de rencor o culpa, llévalo hacia la sabiduría, el amor propio y el perdón.\n"
            "- Mantén la misma historia pero sanada en alta frecuencia."
        )
    else:
        guia_modo = (
            f"MODO: CREAR NUEVA LETRA CON TEMÁTICA:\n"
            f"- Temática elegida: \"{tema_personalizado}\"\n"
            "- Desarrolla esta temática adaptada a la frecuencia indicada."
        )

    prompt = f"""You are a master lyrical alchemist and songwriter.
Elevate the lyrics into the target Hawkins vibrational state: {frec_data['nombre']} ({frec_data['emocion']}).

RHYME AND METRIC CONSTRAINTS:
- Mandatory Rhyme Scheme: {rima_tipo} (Apply this exact rhyme pattern consistently to every stanza).
- Structure: Clear blocks with labels: [Verse 1], [Pre-Chorus], [Chorus], [Verse 2], [Bridge], [Chorus], [Outro].
- Spacing: Add double newlines (\\n\\n) between every block.
- Cadence: Maintain the rhythmic syllable count so it can be sung over the original music beat.

{guia_modo}

ORIGINAL LYRICS:
\"\"\"{letra_base}\"\"\"

OUTPUT FORMAT (STRICT):
Output the ENGLISH lyrics first, followed immediately by the separator "=== DIVISION_IDIOMA ===", and then the SPANISH version adapted with natural poetic flow and the same rhyme scheme.
Example:
[Verse 1]
...

[Chorus]
...

=== DIVISION_IDIOMA ===

[Verso 1]
...

[Coro]
...
"""

    res = client.chat.completions.create(
        model=modelo,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4
    )
    
    texto_completo = res.choices[0].message.content
    partes = texto_completo.split("=== DIVISION_IDIOMA ===")
    
    if len(partes) >= 2:
        t_en = partes[0].strip()
        t_es = partes[1].strip()
    else:
        t_en = texto_completo.strip()
        t_es = texto_completo.strip()
        
    return t_en, t_es

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
# PESTAÑA 2: ALQUIMIA LÍRICA (SLIDER HAWKINS + VIRALIDAD + RIMA + TRANSMUTACIÓN)
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
            st.text_area("Estructura Original", value=st.session_state.letra_esc_orig, height=200)
        with tab_l_es:
            boton_copiar(st.session_state.letra_esc_es, id_btn="cp_esc_es")
            st.text_area("Estructura en Español", value=st.session_state.letra_esc_es, height=200)

        # 2. BOTÓN: CALIBRAR
        st.markdown("---")
        st.markdown("#### 🔮 Calibración del Texto Original")
        if st.button("Calibrar", key="btn_calibrar"):
            with st.spinner("Midiendo frecuencia de la canción original..."):
                try:
                    st.session_state.analisis_hawkins = calibrar_hawkins_estructurado(
                        st.session_state.letra_esc_orig, GROQ_API_KEY
                    )
                except Exception as e:
                    st.error(f"Error al calibrar: {e}")

        if st.session_state.analisis_hawkins:
            h = st.session_state.analisis_hawkins
            st.info(f"📊 **Frecuencia Original Detectada:** {h.get('frecuencia')} | **Sugerencia:** {h.get('elevacion')} | **Clave:** {h.get('clave')}")

    # ==============================================================
    # PANEL INTERACTIVO DE FRECUENCIA & VIRALIDAD (SLIDER HAWKINS)
    # ==============================================================
    st.markdown("---")
    st.markdown("### 🎚️ Escala de Vibración & Conexión Viral (Hawkins)")
    st.caption("Desliza por la escala para descubrir el potencial de viralidad y los 3 temas más potentes de cada frecuencia:")

    # Slider interactivo instantáneo
    frec_seleccionada = st.select_slider(
        "Selecciona el Nivel de Frecuencia:",
        options=list(HAWKINS_SCALE.keys()),
        value=500,
        format_func=lambda x: HAWKINS_SCALE[x]["nombre"]
    )

    info_frec = HAWKINS_SCALE[frec_seleccionada]

    # Tarjeta visual interactiva
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #090d16 0%, #111827 100%); border-left: 6px solid {info_frec['color']}; padding: 18px 22px; border-radius: 12px; margin: 15px 0; box-shadow: 0 4px 15px rgba(0,0,0,0.4);">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <h3 style="margin: 0; color: #ffffff;">{info_frec['nombre']}</h3>
            <span style="background-color: {info_frec['color']}; color: white; padding: 4px 12px; border-radius: 20px; font-weight: bold; font-size: 14px;">🔥 Viralidad: {info_frec['viralidad']}</span>
        </div>
        <p style="margin: 8px 0 4px 0; color: #94a3b8; font-size: 14px;"><b>Campo Emocional:</b> <span style="color: #f1f5f9;">{info_frec['emocion']}</span></p>
        <p style="margin: 4px 0 10px 0; color: #94a3b8; font-size: 14px;"><b>Psicología de Conexión:</b> <span style="color: #38bdf8;">{info_frec['tipo_viral']}</span></p>
        <div style="background-color: rgba(255,255,255,0.05); padding: 10px 14px; border-radius: 8px; margin-top: 10px;">
            <span style="color: #34d399; font-weight: bold; font-size: 13px;">💡 3 Temas de Alta Viralidad en esta Frecuencia:</span>
            <ul style="margin: 6px 0 0 0; padding-left: 20px; color: #e2e8f0; font-size: 13px;">
                <li>{info_frec['temas'][0]}</li>
                <li>{info_frec['temas'][1]}</li>
                <li>{info_frec['temas'][2]}</li>
            </ul>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ==============================================================
    # CONFIGURACIÓN DE TRANSMUTACIÓN (RIMA Y MODO)
    # ==============================================================
    st.markdown("---")
    st.markdown("### ✨ Configurar Transmutación")

    col_rima, col_modo = st.columns([1, 1])

    with col_rima:
        tipo_rima_elegida = st.selectbox(
            "Estructura de Rima:",
            options=["AABB (Pareado clásico)", "ABAB (Alterna pop)", "AAAA (Monorrima contundente)", "ABCB (Balada tradicional)"],
            index=1
        )

    with col_modo:
        modo_elegido = st.radio(
            "Enfoque de la letra:",
            options=["Elevar la misma historia", "Usar tema de la lista", "Tema propio"],
            index=0
        )

    tema_personalizado = ""
    if modo_elegido == "Usar tema de la lista":
        tema_personalizado = st.selectbox("Selecciona uno de los 3 temas virales:", options=info_frec['temas'])
    elif modo_elegido == "Tema propio":
        tema_personalizado = st.text_input("Escribe tu temática:", placeholder="Ej: Triunfo personal, Paz mental...")

    # 3. BOTÓN: TRANSMUTAR (MOTOR ROBUSTO UNIFICADO)
    if st.button("Transmutar", type="primary", key="btn_transmutar"):
        if not GROQ_API_KEY.strip():
            st.error("Ingresa tu Groq API Key en la barra lateral.")
        else:
            # Determinamos la letra base (escaneada o directa)
            letra_base_final = st.session_state.letra_esc_orig if st.session_state.letra_esc_orig else letra_manual.strip()
            
            if not letra_base_final:
                st.warning("Pega la letra de la canción arriba antes de transmutar.")
            elif modo_elegido == "Tema propio" and not tema_personalizado.strip():
                st.warning("Escribe la temática que deseas para la nueva letra.")
            else:
                modo_cod = "misma" if modo_elegido == "Elevar la misma historia" else "nueva"
                with st.spinner("Transmutando lírica con rima precisa en alta velocidad..."):
                    try:
                        t_en, t_es = transmutar_letra_motor_unificado(
                            letra_base=letra_base_final,
                            frec_target=frec_seleccionada,
                            rima_tipo=tipo_rima_elegida,
                            modo=modo_cod,
                            tema_personalizado=tema_personalizado.strip(),
                            api_key=GROQ_API_KEY
                        )
                        st.session_state.letra_trans_en = t_en
                        st.session_state.letra_trans_es = t_es
                    except Exception as e:
                        st.error(f"Error durante la transmutación: {e}")

    # Muestra los resultados transmutados inmediatamente
    if st.session_state.letra_trans_en:
        st.markdown("---")
        st.markdown("""
        <div style="background-color: #064e3b; border-left: 6px solid #10b981; padding: 14px 20px; border-radius: 8px; margin: 15px 0;">
            <h4 style="margin: 0; color: #a7f3d0;">🎉 ¡Alquimia completada con éxito! Letras organizadas en párrafos limpios</h4>
        </div>
        """, unsafe_allow_html=True)

        tab_t_en, tab_t_es = st.tabs(["🇺🇸 Versión en Inglés (Clean)", "🇪🇸 Versión en Español"])
        with tab_t_en:
            boton_copiar(st.session_state.letra_trans_en, id_btn="cp_t_en")
            st.text_area("Letra Transmutada en Inglés", value=st.session_state.letra_trans_en, height=320)
        with tab_t_es:
            boton_copiar(st.session_state.letra_trans_es, id_btn="cp_t_es")
            st.text_area("Letra Transmutada en Español", value=st.session_state.letra_trans_es, height=320)

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
