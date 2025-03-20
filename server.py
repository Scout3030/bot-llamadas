from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse
import sqlite3
from dotenv import load_dotenv
import os
from utils import log, log_filename
import openai
from openai import OpenAI

load_dotenv()
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:5000")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

app = Flask(__name__)

# Crear base de datos si no existe
conn = sqlite3.connect("clientes.db", check_same_thread=False)
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

def guardar_lead(zona, precio, habitaciones, conversacion=""):
    log(f"[GUARDAR LEAD] Zona: {zona} | Precio: {precio} | Habitaciones: {habitaciones}")
    cursor.execute("INSERT INTO leads (zona, precio, habitaciones, conversacion) VALUES (?, ?, ?, ?)",
                   (zona, precio, habitaciones, conversacion))
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
    log(f"[INPUT DEL USUARIO] {user_input}")

    # Cargar o inicializar conversación
    if not os.path.exists("storage/app/conversacion.tmp"):
        conversacion = [
            {"role": "system", "content": "Eres un agente inmobiliario amable que ayuda a recopilar información para encontrar un alquiler. Haz una pregunta a la vez. Primero pregunta en qué zona desea alquilar, luego el rango de precio, y luego cuántas habitaciones necesita."},
        ]
    else:
        with open("storage/app/conversacion.tmp", "r") as f:
            raw = f.read().strip()
            conversacion = eval(raw) if raw else []

        if user_input:
            conversacion.append({"role": "user", "content": user_input})

    # Generar respuesta
    respuesta = generar_respuesta_chatgpt(conversacion)
    conversacion.append({"role": "assistant", "content": respuesta})

    # Guardar conversación temporal
    with open("storage/app/conversacion.tmp", "w") as f:
        f.write(str(conversacion))

    # Verificar si ya se tienen todos los datos
    zona, precio, habitaciones = "", "", ""
    for msg in conversacion:
        if msg["role"] == "user":
            txt = msg["content"].lower()
            if "zona" in txt and not zona:
                zona = txt
            elif "precio" in txt and not precio:
                precio = txt
            elif "habitaciones" in txt and not habitaciones:
                habitaciones = txt

    if zona and precio and habitaciones:
        conversacion_txt = "\n".join([f"{m['role']}: {m['content']}" for m in conversacion])
        guardar_lead(zona, precio, habitaciones, conversacion_txt)
        os.remove("storage/app/conversacion.tmp")
        final_resp = VoiceResponse()
        final_resp.say("Gracias por tu información. Un asesor se pondrá en contacto contigo.", voice="alice", language="es-ES")
        return Response(str(final_resp), mimetype="application/xml")

    # Continuar conversación
    twiml = VoiceResponse()
    twiml.say(respuesta, voice="alice", language="es-ES")
    twiml.gather(input="speech", timeout=10, action="/voice", method="POST")
    return Response(str(twiml), mimetype="application/xml")

if __name__ == "__main__":
    log(f"[SERVER INICIADO] Flask corriendo en puerto 5000 - BASE_URL = {BASE_URL}")
    app.run(port=5000)