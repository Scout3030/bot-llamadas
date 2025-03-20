import openai
import speech_recognition as sr
import pyttsx3
import sqlite3
import os
import datetime
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURACIÓN API OPENAI ---
openai.api_key = os.getenv("OPENAI_API_KEY")

# --- CONFIGURACIÓN LOG DE CONVERSACIÓN ---
os.makedirs("logs", exist_ok=True)
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = f"logs/conversacion_{timestamp}.txt"
log_file = open(log_filename, "w")


def log(text):
    log_file.write(text + "\n")
    log_file.flush()


# --- INICIALIZAR MOTOR DE VOZ ---
engine = pyttsx3.init()


def hablar(texto):
    print(f"BOT: {texto}")
    log(f"BOT: {texto}")
    engine.say(texto)
    engine.runAndWait()


def escuchar():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("Escuchando...")
        audio = r.listen(source)
    try:
        texto = r.recognize_google(audio, language='es-PE')
        print(f"Usuario: {texto}")
        log(f"USUARIO: {texto}")
        return texto.lower()
    except sr.UnknownValueError:
        log("USUARIO: [No se entendió]")
        return ""
    except sr.RequestError:
        log("BOT: [Error de conexión con reconocimiento de voz]")
        hablar("Error al conectar con el servicio de voz.")
        return ""


def validar_respuesta_con_gpt(pregunta, respuesta_usuario):
    prompt = f"""
    Estoy desarrollando un agente inmobiliario automatizado. Necesito que evalúes si la respuesta del usuario tiene sentido según la pregunta realizada. Considera que las respuestas pueden ser simples como nombres de lugares (para zonas), números o rangos (para precios), y cantidades (para habitaciones).

    Pregunta del agente: "{pregunta}"
    Respuesta del usuario: "{respuesta_usuario}"

    ¿La respuesta del usuario tiene sentido y es coherente con la pregunta? Devuélveme solo "sí" si es aceptable para continuar, o "no" si debo volver a preguntar.
    """

    try:
        completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        respuesta = completion.choices[0].message.content.lower().strip()
        return respuesta
    except Exception as e:
        print(f"Error al validar con GPT: {e}")
        return "error"


# --- INICIALIZAR BASE DE DATOS ---
conn = sqlite3.connect("clientes.db")
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        zona TEXT,
        precio TEXT,
        habitaciones TEXT,
        conversacion TEXT
    )
''')
conn.commit()


def preguntar_y_validar(pregunta):
    intentos = 0
    while intentos < 3:
        hablar(pregunta)
        respuesta = escuchar()
        if not respuesta:
            hablar("No te entendí, ¿puedes repetir?")
            intentos += 1
            continue

        es_valida = validar_respuesta_con_gpt(pregunta, respuesta)
        if "sí" in es_valida:
            return respuesta
        else:
            # Fallback tolerante según tipo de pregunta
            if "zona" in pregunta.lower() and len(respuesta.strip()) >= 3:
                return respuesta
            elif "precio" in pregunta.lower() and any(char.isdigit() for char in respuesta):
                return respuesta
            elif "habitaciones" in pregunta.lower() and (any(char.isdigit() for char in respuesta) or "una" in respuesta or "dos" in respuesta or "tres" in respuesta):
                return respuesta
        intentos += 1
        if intentos < 3:
            hablar("Esa respuesta no parece responder a mi pregunta. Intentémoslo otra vez.")
        else:
            hablar("No pudimos obtener una respuesta válida. Pasaremos a la siguiente pregunta.")
            return "no válido"


def flujo_agente():
    hablar("Hola, bienvenido a Inmobiliaria Codificable.")
    zona = preguntar_y_validar("¿En qué zona estás buscando alquilar?")
    precio = preguntar_y_validar("¿Cuál es tu rango de precios aproximado?")
    habitaciones = preguntar_y_validar("¿Cuántas habitaciones necesitas?")

    conversacion_completa = open(log_filename).read()
    cursor.execute("INSERT INTO leads (zona, precio, habitaciones, conversacion) VALUES (?, ?, ?, ?)",
                   (zona, precio, habitaciones, conversacion_completa))
    conn.commit()
    hablar("Gracias por tu información. Un asesor te contactará pronto.")


if __name__ == "__main__":
    flujo_agente()
    log("CONVERSACIÓN FINALIZADA")
    log_file.close()