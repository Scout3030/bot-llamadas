import speech_recognition as sr
import pyttsx3
import sqlite3
import re
import os
import datetime

os.makedirs("logs", exist_ok=True)
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = f"logs/conversacion_{timestamp}.txt"
log_file = open(log_filename, "w")

def log(text):
    log_file.write(text + "\n")
    log_file.flush()

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
        hablar("Hubo un error al conectar con el servicio de voz.")
        return ""

def validar_precio(texto):
    return bool(re.search(r'\d+', texto))

def validar_zona(texto):
    return len(texto.strip()) >= 3

def validar_habitaciones(texto):
    return bool(re.search(r'\d+', texto)) or "una" in texto or "dos" in texto or "tres" in texto

# Inicializa la base de datos
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

def preguntar_y_validar(pregunta, funcion_validadora):
    intentos = 0
    while True:
        hablar(pregunta)
        respuesta = escuchar()
        if funcion_validadora(respuesta):
            return respuesta
        else:
            intentos += 1
            if intentos < 3:
                hablar("Esa respuesta no parece correcta. Intentémoslo otra vez.")
            else:
                hablar("Lo siento, no pude entender tu respuesta. Pasaremos a la siguiente pregunta.")
                return "no válido"

def flujo_agente():
    hablar("Hola, bienvenido a Inmobiliaria Codificable.")
    zona = preguntar_y_validar("¿En qué zona estás buscando alquilar?", validar_zona)
    precio = preguntar_y_validar("¿Cuál es tu rango de precios aproximado?", validar_precio)
    habitaciones = preguntar_y_validar("¿Cuántas habitaciones necesitas?", validar_habitaciones)

    conversacion_completa = open(log_filename).read()
    cursor.execute("INSERT INTO leads (zona, precio, habitaciones, conversacion) VALUES (?, ?, ?, ?)", (zona, precio, habitaciones, conversacion_completa))
    conn.commit()
    hablar("Gracias por tu información. Un asesor te contactará pronto.")

if __name__ == "__main__":
    flujo_agente()
    log("CONVERSACIÓN FINALIZADA")
    log_file.close()