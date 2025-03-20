# IA AGENTE

Activa el VENV

```` bash
source venv/bin/activate
````

Instalar dependencias

```` bash
pip install -r requirements.txt
````

Freezy dependencias

```` bash
pip freeze > requirements.txt
````

Iniciar servidor en local

```` bash
python server.py
````

Iniciar servidor en background

```` bash
python server.py &
````

Test on local

```` bash
curl -X POST http://127.0.0.1:5000/audio
````
