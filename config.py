import os
import sqlite3
from dotenv import load_dotenv

load_dotenv()

openai_api_key = os.getenv("OPENAI_API_KEY")

# DB Connection
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