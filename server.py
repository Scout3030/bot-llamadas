from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse

app = Flask(__name__)

@app.route("/voice", methods=['POST'])
def voice():
    resp = VoiceResponse()
    resp.say("Hola, bienvenido a Inmobiliaria Codificable. Por favor, diga en qué zona desea alquilar después del tono.", voice='alice', language='es-ES')
    resp.record(timeout=5, maxLength=10, transcribe=True, transcribeCallback="/transcripcion")
    return Response(str(resp), mimetype="application/xml")

@app.route("/transcripcion", methods=['POST'])
def transcripcion():
    texto = request.form.get("TranscriptionText")
    print(f"Transcripción recibida: {texto}")
    # Aquí puedes enviar texto a tu bot actual o guardarlo
    return ("", 200)

if __name__ == "__main__":
    app.run(port=5000)