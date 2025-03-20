from utils import log, hablar, validar_respuesta_con_gpt, limpiar_respuesta, log_filename, escuchar
from config import cursor, conn
import re

def preguntar_y_validar(pregunta):
    intentos = 0
    while intentos < 3:
        hablar(pregunta)
        respuesta = escuchar().strip().lower()
        respuesta = limpiar_respuesta(respuesta)
        log(f"USUARIO: {respuesta}")

        if not respuesta:
            hablar("No te entendí, ¿puedes repetir?")
            intentos += 1
            continue

        es_valida = validar_respuesta_con_gpt(pregunta, respuesta)
        if "sí" in es_valida:
            return respuesta
        else:
            if "zona" in pregunta.lower() and len(respuesta) >= 3:
                return respuesta
            elif "precio" in pregunta.lower() and (re.search(r"\d+", respuesta) or "a" in respuesta or "-" in respuesta):
                return respuesta
            elif "habitaciones" in pregunta.lower() and (
                any(c.isdigit() for c in respuesta) or any(p in respuesta for p in ["una", "dos", "tres", "cuatro", "cinco"])
            ):
                return respuesta

        intentos += 1
        if intentos < 3:
            hablar("Esa respuesta no parece responder a mi pregunta. Intentémoslo otra vez.")
        else:
            hablar("No pudimos obtener una respuesta válida. Pasaremos a la siguiente pregunta.")
            return "no válido"
    intentos = 0
    while intentos < 3:
        hablar(pregunta)
        respuesta = escuchar().strip().lower()
        log(f"USUARIO: {respuesta}")

        if not respuesta:
            hablar("No te entendí, ¿puedes repetir?")
            intentos += 1
            continue

        es_valida = validar_respuesta_con_gpt(pregunta, respuesta)
        if "sí" in es_valida:
            return respuesta
        else:
            if "zona" in pregunta.lower() and len(respuesta) >= 3:
                return respuesta
            elif "precio" in pregunta.lower() and any(c.isdigit() for c in respuesta):
                return respuesta
            elif "habitaciones" in pregunta.lower() and (any(c.isdigit() for c in respuesta) or any(p in respuesta for p in ["una", "dos", "tres"])):
                return respuesta

        intentos += 1
        if intentos < 3:
            hablar("Esa respuesta no parece responder a mi pregunta. Intentémoslo otra vez.")
        else:
            hablar("No pudimos obtener una respuesta válida. Pasaremos a la siguiente pregunta.")
            return "no válido"

def flujo_agente_consola():
    hablar("Hola, bienvenido a Inmobiliaria Codificable.")
    zona = preguntar_y_validar("¿En qué zona estás buscando alquilar?")
    precio = preguntar_y_validar("¿Cuál es tu rango de precios aproximado?")
    habitaciones = preguntar_y_validar("¿Cuántas habitaciones necesitas?")

    with open(log_filename) as f:
        conversacion_completa = f.read()

    cursor.execute("INSERT INTO leads (zona, precio, habitaciones, conversacion) VALUES (?, ?, ?, ?)",
                   (zona, precio, habitaciones, conversacion_completa))
    conn.commit()
    hablar("Gracias por tu información. Un asesor te contactará pronto.")

def ejecutar_flujo_agente_consola():
    flujo_agente_consola()

if __name__ == "__main__":
    ejecutar_flujo_agente_consola()