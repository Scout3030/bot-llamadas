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

# Crear base de datos y asegurar columnas
conn = sqlite3.connect("clientes.db", check_same_thread=False)
cursor = conn.cursor()

# Crear tabla si no existe
cursor.execute('''
    CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT
    )
''')

# Agregar columnas si faltan
columnas = {
    "operacion": "TEXT",
    "zona": "TEXT",
    "precio": "TEXT",
    "habitaciones": "TEXT",
    "fecha": "TEXT",
    "conversacion": "TEXT"
}

for columna, tipo in columnas.items():
    try:
        cursor.execute(f"ALTER TABLE leads ADD COLUMN {columna} {tipo}")
    except sqlite3.OperationalError:
        pass  # La columna ya existe

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

@app.route("/voice", methods=['POST'])
def voice():
    user_input = request.form.get("SpeechResult", "").strip()
    call_sid = request.form.get("CallSid")
    conversacion_file = f"storage/app/conversacion_{call_sid}.tmp"
    log(f"[INPUT DEL USUARIO] {user_input}")

    # Estructura de flujo de preguntas
    preguntas = [
        {"clave": "operacion", "texto": "¿Qué tipo de operación deseas? ¿Compra o venta?"},
        {"clave": "zona", "texto": "¿En qué zona deseas buscar la propiedad?"},
        {"clave": "precio", "texto": "¿Cuál es tu presupuesto aproximado?"},
        {"clave": "habitaciones", "texto": "¿Cuántas habitaciones necesitas?"},
        {"clave": "fecha", "texto": "¿Para qué fecha deseas mudarte o cerrar la compra?"}
    ]

    # Cargar estado anterior
    if os.path.exists(conversacion_file):
        with open(conversacion_file, "r") as f:
            estado = eval(f.read().strip())
    else:
        estado = {
            "pregunta_actual": 0,
            "intentos": 0,
            "respuestas": {},
            "historial": []
        }

    # Validación de respuesta con GPT (solo si hay input del usuario)
    if user_input:
        pregunta_actual = preguntas[estado["pregunta_actual"]]
        prompt_validacion = [
            {"role": "system", "content": f"Actúa como un asistente inmobiliario. Evalúa si la respuesta del usuario responde correctamente a la pregunta '{pregunta_actual['texto']}'. Si responde correctamente, di solo 'válida'. Si no responde a lo que se pregunta, di solo 'inválida'."},
            {"role": "user", "content": user_input}
        ]
        validacion = generar_respuesta_chatgpt(prompt_validacion).lower()
        log(f"[VALIDACIÓN GPT] {validacion}")

        if "válida" in validacion:
            estado["respuestas"][pregunta_actual["clave"]] = user_input
            estado["pregunta_actual"] += 1
            estado["intentos"] = 0
        else:
            estado["intentos"] += 1
            if estado["intentos"] >= 3:
                estado["pregunta_actual"] += 1
                estado["intentos"] = 0
            else:
                respuesta = f"Lo siento, no comprendí eso. ¿Podrías repetirlo? {pregunta_actual['texto']}"
                estado["historial"].append({"role": "assistant", "content": respuesta})
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
                with open(conversacion_file, "w") as f:
                    f.write(str(estado))
                return Response(str(twiml), mimetype="application/xml")

    # Verificar si ya se completaron todas las preguntas
    if estado["pregunta_actual"] >= len(preguntas):
        conversacion_txt = "\n".join(
            [f"{msg['role']}: {msg['content']}" for msg in estado.get("historial", [])]
        )
        guardar_lead(
            estado["respuestas"].get("operacion", ""),
            estado["respuestas"].get("zona", ""),
            estado["respuestas"].get("precio", ""),
            estado["respuestas"].get("habitaciones", ""),
            estado["respuestas"].get("fecha", ""),
            conversacion_txt
        )
        os.remove(conversacion_file)
        final_resp = VoiceResponse()
        final_resp.say("Gracias por tu información. Un asesor se pondrá en contacto contigo.", voice="alice", language="es-ES")
        return Response(str(final_resp), mimetype="application/xml")

    # Pregunta siguiente
    siguiente_pregunta = preguntas[estado["pregunta_actual"]]["texto"]
    estado["historial"].append({"role": "assistant", "content": siguiente_pregunta})

    # Guardar estado actualizado
    os.makedirs("storage/app", exist_ok=True)
    with open(conversacion_file, "w") as f:
        f.write(str(estado))

    twiml = VoiceResponse()
    gather = twiml.gather(
        input="speech",
        speechTimeout="auto",
        language="es-ES",
        hints="comprar, alquilar, vivienda, casa, euros, zona, centro, habitaciones, una, dos, tres",
        action="/voice",
        method="POST"
    )
    if estado["pregunta_actual"] == 0 and not user_input:
        saludo = "Hola, soy Cielo, el asistente de Inmobiliaria BuenasPropiedades. " + siguiente_pregunta
        gather.say(saludo, voice="alice", language="es-ES")
    else:
        gather.say(siguiente_pregunta, voice="alice", language="es-ES")
    return Response(str(twiml), mimetype="application/xml")

if __name__ == "__main__":
    log(f"[SERVER INICIADO] Flask corriendo en puerto 5000 - BASE_URL = {BASE_URL}")
    app.run(port=5000)