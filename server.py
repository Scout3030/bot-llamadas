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
                operacion = "compra" if re.search(r"\b(compra|comprar)\b", txt) else "venta"
            if not zona and re.search(r"(zona|distrito|barrio|centro|norte|sur|este|oeste)", txt):
                zona = txt
            if not precio and re.search(r"(precio|presupuesto|\d+\s?(mil|euros|\€))", txt):
                precio = txt
            if not habitaciones and re.search(r"\b(\d+|una|dos|tres|cuatro|cinco)\s+habitaciones?\b", txt):
                habitaciones = txt
            if not fecha and re.search(r"\b(hoy|mañana|\d{1,2}/\d{1,2}|\d{1,2}-\d{1,2}|enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\b", txt):
                fecha = txt
    return operacion, zona, precio, habitaciones, fecha

def siguiente_pregunta_por_dato_faltante(operacion, zona, precio, habitaciones, fecha):
    if not operacion:
        return "Pregunta al usuario qué tipo de operación desea realizar, si compra o venta."
    elif not zona:
        return "Ya sabemos que quiere comprar o vender. Pregunta ahora en qué zona desea buscar la propiedad."
    elif not precio:
        return "Ya sabemos zona y operación. Pregunta ahora cuál es su presupuesto aproximado."
    elif not habitaciones:
        return "Pregunta cuántas habitaciones necesita la propiedad."
    elif not fecha:
        return "Pregunta para qué fecha desea mudarse o cerrar la compra."
    else:
        return None

@app.route("/voice", methods=['POST'])
def voice():
    user_input = request.form.get("SpeechResult", "").strip()
    log(f"[INPUT DEL USUARIO] {user_input}")

    if not os.path.exists("storage/app/conversacion.tmp"):
        conversacion = [{
            "role": "system",
            "content": (
                "Eres un asistente inmobiliario telefónico que conversa únicamente en español. Tu tarea es recopilar de forma conversacional los siguientes datos, uno por uno: "
                "1) tipo de operación (compra o venta), 2) zona de interés, 3) rango de precio, 4) número de habitaciones, y 5) fecha de entrada deseada. "
                "Haz una pregunta a la vez, escucha atentamente las respuestas, responde con frases naturales y amables en español. No hables inglés. Si la respuesta no se entiende, pide amablemente que la repita o aclare."
            )
        }]
    else:
        with open("storage/app/conversacion.tmp", "r") as f:
            raw = f.read().strip()
            conversacion = eval(raw) if raw else []

    if not user_input:
        log("[SIN RESPUESTA] El usuario no respondió. Iniciamos conversación con la primera pregunta.")
        respuesta = "Hola, soy tu asistente inmobiliario. ¿Qué tipo de operación deseas? ¿Compra o venta?"
        conversacion.append({"role": "assistant", "content": respuesta})
        twiml = VoiceResponse()
        gather = twiml.gather(
            input="speech",
            speechTimeout="auto",
            language="es-ES",
            hints="comprar, alquilar, vivienda, casa, euros, zona, centro, habitaciones, una, dos, tres",
            action="/voice",
            method="POST"
        )
        gather.say(respuesta, voice="alice", language="es-ES")
        return Response(str(twiml), mimetype="application/xml")

    if user_input:
        conversacion.append({"role": "user", "content": user_input})

    # Verificar si ya se tienen suficientes datos para guardar el lead
    operacion, zona, precio, habitaciones, fecha = extraer_datos(conversacion)

    # Forzar el flujo paso a paso
    instruccion = siguiente_pregunta_por_dato_faltante(operacion, zona, precio, habitaciones, fecha)

    if instruccion:
        prompt = [
            {"role": "system", "content": "Eres un asistente inmobiliario amable y conversacional. Habla solo en español y haz una sola pregunta clara a la vez."},
            {"role": "user", "content": instruccion}
        ]
        respuesta = generar_respuesta_chatgpt(prompt)
        log(f"[PREGUNTA DEL AGENTE] {respuesta}")
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
    gather = twiml.gather(
        input="speech",
        speechTimeout="auto",
        language="es-ES",
        hints="comprar, alquilar, vivienda, casa, euros, zona, centro, habitaciones, una, dos, tres",
        action="/voice",
        method="POST"
    )
    gather.say(respuesta, voice="alice", language="es-ES")
    return Response(str(twiml), mimetype="application/xml")

if __name__ == "__main__":
    log(f"[SERVER INICIADO] Flask corriendo en puerto 5000 - BASE_URL = {BASE_URL}")
    app.run(port=5000)