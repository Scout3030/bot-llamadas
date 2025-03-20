from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse
import sqlite3
from dotenv import load_dotenv
import os
from utils import log, log_filename
import openai
from openai import OpenAI
import re

load_dotenv()
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:5000")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

app = Flask(__name__)

# Crear base de datos
conn = sqlite3.connect("clientes.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        operacion TEXT,
        zona TEXT,
        precio TEXT,
        habitaciones TEXT,
        fecha TEXT,
        conversacion TEXT
    )
''')
conn.commit()

def guardar_lead(operacion, zona, precio, habitaciones, fecha, conversacion=""):
    log(f"[GUARDAR LEAD] Operación: {operacion} | Zona: {zona} | Precio: {precio} | Habitaciones: {habitaciones} | Fecha: {fecha}")
    cursor.execute('''
        INSERT INTO leads (operacion, zona, precio, habitaciones, fecha, conversacion)
        VALUES (?, ?, ?, ?, ?, ?)''', (operacion, zona, precio, habitaciones, fecha, conversacion))
    conn.commit()

client = OpenAI(api_key=OPENAI_API_KEY)

def generar_respuesta_chatgpt(conversacion):
    log(f"[CHATGPT] Enviando contexto:\n{conversacion}")
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=conversacion,
        temperature=0.7,
        max_tokens=100
    )
    return response.choices[0].message.content.strip()

def extraer_datos(conversacion):
    operacion = zona = precio = habitaciones = fecha = ""
    for msg in conversacion:
        if msg["role"] == "user":
            txt = msg["content"].lower()
            if not operacion and re.search(r"\b(compra|comprar|venta|vender)\b", txt):
                operacion = "compra" if "compra" in txt or "comprar" in txt else "venta"
            if not zona and "zona" in txt:
                zona = txt
            if not precio and ("precio" in txt or "euros" in txt or "mil" in txt):
                precio = txt
            if not habitaciones and re.search(r"\bhabitaciones?\b", txt):
                habitaciones = txt
            if not fecha and re.search(r"\b(hoy|mañana|\d{1,2}/\d{1,2}|\babril|\bmayo|\bjunio|\bjulio|\bagosto)", txt):
                fecha = txt
    return operacion, zona, precio, habitaciones, fecha

@app.route("/voice", methods=['POST'])
def voice():
    user_input = request.form.get("SpeechResult", "").strip()
    log(f"[INPUT DEL USUARIO] {user_input}")

    if not user_input:
        log("[SIN RESPUESTA] El usuario no respondió. Repetimos la última pregunta.")
        twiml = VoiceResponse()
        gather = twiml.gather(input="speech", timeout=10, action="/voice", method="POST")
        ultima_pregunta = next((msg["content"] for msg in reversed(conversacion) if msg["role"] == "assistant"), "¿Podrías repetir por favor?")
        gather.say(ultima_pregunta, voice="alice", language="es-ES")
        return Response(str(twiml), mimetype="application/xml")

    # Cargar o inicializar conversación
    if not os.path.exists("storage/app/conversacion.tmp"):
        conversacion = []
    else:
        with open("storage/app/conversacion.tmp", "r") as f:
            raw = f.read().strip()
            conversacion = eval(raw) if raw else []

    # Agregar prompt inicial si no existe
    if not any(m for m in conversacion if m["role"] == "system"):
        conversacion.insert(0, {
            "role": "system",
            "content": (
                "Eres un asistente inmobiliario telefónico. Tu tarea es obtener los siguientes datos, uno por uno: "
                "1) tipo de operación (compra o venta), 2) zona de interés, 3) rango de precio, 4) número de habitaciones, y 5) fecha de entrada deseada. "
                "Haz una pregunta a la vez y espera respuesta antes de continuar. Sé amable y claro."
            )
        })

    if user_input:
        conversacion.append({"role": "user", "content": user_input})

    # Extraer datos actuales
    operacion, zona, precio, habitaciones, fecha = extraer_datos(conversacion)

    # Determinar siguiente pregunta basada en flujo guiado
    def determinar_pregunta_siguiente(operacion, zona, precio, habitaciones, fecha):
        if not operacion:
            return "¿Qué tipo de operación deseas? ¿Compra o venta?"
        if not zona:
            return "¿En qué zona estás buscando?"
        if not precio:
            return "¿Cuál es tu presupuesto aproximado?"
        if not habitaciones:
            return "¿Cuántas habitaciones necesitas?"
        if not fecha:
            return "¿Para qué fecha deseas mudarte?"
        return None

    pregunta_siguiente = determinar_pregunta_siguiente(operacion, zona, precio, habitaciones, fecha)
    if pregunta_siguiente:
        respuesta = pregunta_siguiente
        conversacion.append({"role": "assistant", "content": respuesta})
    else:
        conversacion_txt = "\n".join([f"{m['role']}: {m['content']}" for m in conversacion])
        guardar_lead(operacion, zona, precio, habitaciones, fecha, conversacion_txt)
        os.remove("storage/app/conversacion.tmp")
        final_resp = VoiceResponse()
        final_resp.say("Gracias por tu información. Un asesor se pondrá en contacto contigo.", voice="alice", language="es-ES")
        return Response(str(final_resp), mimetype="application/xml")

    # Continuar conversación
    twiml = VoiceResponse()
    gather = twiml.gather(input="speech", timeout=10, action="/voice", method="POST")
    gather.say(respuesta, voice="alice", language="es-ES")
    return Response(str(twiml), mimetype="application/xml")

if __name__ == "__main__":
    log(f"[SERVER INICIADO] Flask corriendo en puerto 5000 - BASE_URL = {BASE_URL}")
    app.run(port=5000)