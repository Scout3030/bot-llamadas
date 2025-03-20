import os
import datetime
import pyttsx3
import openai
from config import openai_api_key
import re

openai.api_key = openai_api_key

os.makedirs("storage/app", exist_ok=True)
open("storage/app/conversacion.tmp", "a").close()

# Voice engine
engine = pyttsx3.init()

# Logging
os.makedirs("logs", exist_ok=True)
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = f"storage/logs/python.log"
log_file = open(log_filename, "w")

def log(text):
    log_file.write(text + "\n")
    log_file.flush()

def hablar(texto):
    print(f"BOT: {texto}")
    log(f"BOT: {texto}")
    engine.say(texto)
    engine.runAndWait()

import speech_recognition as sr

def limpiar_respuesta(respuesta):
    respuesta = respuesta.lower().strip()
    respuesta = re.sub(r"(\b\w+) \1", r"\1", respuesta)  # elimina repeticiones tipo 'dos dos'
    return respuesta

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
        return completion.choices[0].message.content.lower().strip()
    except Exception as e:
        print(f"[GPT ERROR] {e}")
        return "error"