from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse
import sqlite3
import os

BASE_URL = os.environ.get("BASE_URL")

app = Flask(__name__)

# Create database if it doesn't exist
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
    cursor.execute("INSERT INTO leads (zona, precio, habitaciones, conversacion) VALUES (?, ?, ?, ?)",
                   (zona, precio, habitaciones, conversacion))
    conn.commit()

def siguiente_pregunta(callback_path, texto):
    resp = VoiceResponse()
    resp.say(texto, voice='alice', language='es-ES')
    resp.record(timeout=10, maxLength=15, transcribe=True, transcribeCallback=f"{BASE_URL}/transcripcion/{callback_path}")
    return Response(str(resp), mimetype="application/xml")

@app.route("/voice", methods=['POST'])
def voice():
    resp = VoiceResponse()
    resp.say("Hola, bienvenido a Inmobiliaria Codificable.", voice='alice', language='es-ES')
    resp.say("Por favor, diga en qué zona desea alquilar después del tono.", voice='alice', language='es-ES')
    resp.record(timeout=10, maxLength=15, transcribe=True, transcribeCallback=f"{BASE_URL}/transcripcion/zona")
    return Response(str(resp), mimetype="application/xml")

@app.route("/transcripcion/zona", methods=['POST'])
def transcripcion_zona():
    texto = request.form.get("TranscriptionText", "").strip()
    with open("zona.tmp", "w") as f:
        f.write(texto)
    return siguiente_pregunta("precio", "Gracias. Ahora, ¿cuál es tu rango de precios aproximado?")

@app.route("/transcripcion/precio", methods=['POST'])
def transcripcion_precio():
    texto = request.form.get("TranscriptionText", "").strip()
    with open("precio.tmp", "w") as f:
        f.write(texto)
    return siguiente_pregunta("habitaciones", "Gracias. ¿Cuántas habitaciones necesitas?")

@app.route("/transcripcion/habitaciones", methods=['POST'])
def transcripcion_habitaciones():
    texto = request.form.get("TranscriptionText", "").strip()
    with open("habitaciones.tmp", "w") as f:
        f.write(texto)

    zona = open("zona.tmp").read().strip() if os.path.exists("zona.tmp") else ""
    precio = open("precio.tmp").read().strip() if os.path.exists("precio.tmp") else ""
    habitaciones = texto

    conversacion = f"ZONA: {zona}\nPRECIO: {precio}\nHABITACIONES: {habitaciones}"
    guardar_lead(zona, precio, habitaciones, conversacion)

    resp = VoiceResponse()
    resp.say("Gracias por tu información. Un asesor te contactará pronto.", voice='alice', language='es-ES')
    return Response(str(resp), mimetype="application/xml")

if __name__ == "__main__":
    app.run(port=5000)