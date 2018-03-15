# Vitrasa Telegram Bot

Es un bot de Telegram en el que consultar el tiempo aproximado de llegada de los autobuses en la ciudad de Vigo, puedes añadir el bot a telegram a traves de este enlace [VitrasaBot](http://t.me/vitrasabot)

Su funcionamiento es sencillo, solo tendremos que indicarle el numero de parada o buscar  entre las paradas más proximas. Además también es posible enviar una ubicación para obtener los horarios de la parada más cercana.

Por otro lado también es posible guardar las paradas favoritas para poder acceder de forma mas sencilla a ellas.

### Capturas de pantalla
![](https://i.imgur.com/qsQnmaL.png)
![](https://i.imgur.com/KF1XGqB.png)

## Instalación

El bot está programado en python y utiliza MongoDB como base de datos, hace uso de las siguientes librerias [pyTelegramBotAPI](https://github.com/eternnoir/pyTelegramBotAPI), [Time for Vbus APITime for Vbus API](https://github.com/dpeite/time-for-vbus-api/tree/updates_for_telegram) [pymongo](https://api.mongodb.com/python/current/), y [Suds](https://bitbucket.org/jurko/suds)

Existen dos variantes del bot, una versión normal usando pyTelegramBotAPI y pymongo. Y otra versión pensada para usar en Google App Engine, que usa una versión modificada de pyTelegramBotAPI y de este propio bot, webhooks y pymongolab debido a las limitaciones de GAE.

Para cada variante existe una rama, [master](https://github.com/dpeite/VitrasaTelegramBot/tree/master) es la version normal. Mientras que [master_appengine](https://github.com/dpeite/VitrasaTelegramBot/tree/master_appengine) es la version para Google App Engine.

### Versión normal

Para poder ejecutar esta versión es necesario realizar los siguientes pasos:
```bash
git clone https://github.com/dpeite/VitrasaTelegramBot.git
cd VitrasaTelegramBot
git submodule init
git submodule update --remote
cd api
sudo pip install -r requirements.txt
cd ..
sudo pip install -r requirements.txt
```

Una vez hecho los pasos anteriores debemos añadir en el codigo nuestro token de autenticación y la ruta de nuestro mongo en el fichero `Vitrasa.py`:

```python
token = "Añadir aquí el token que nos proporciona BotFather"
...
client = MongoClient("mongodb://url_mongo")
```

Ahora ya estamos listos para lanzar nuestro bot:
```bash
python Vitrasa.py
```

### Versión para Google App Engine

Esta versión tiene unos cuantos tweaks para poder funcionar correctamente sobre la nube de Google. Para ello hemos tenido que modificar [pyTelegramBotAPI](https://github.com/dpeite/pyTelegramBotAPI-for-Google-App-Engine) para que no use la libreria requets, en la liberia [Time for Vbus API](https://github.com/dpeite/time-for-vbus-api/tree/updates_for_telegram_appengine) hemos tenido que desactivar la cache, y por ultimo en vez de utilizar pymongo usamos pymongolab ya que es casi obligatorio usar mongo hosteado desde [mlab](https://mlab.com).

Para poder ejecutar esta versión es necesario realizar los siguientes pasos:
1. Clonar e inicializar el proyecto
```bash
git clone https://github.com/dpeite/VitrasaTelegramBot.git
cd VitrasaTelegramBot
git checkout master_appengine
git submodule init
git submodule update --remote
```
2. Descargar las librerias necesarias a la carpeta `lib`
```bash
sudo pip install -r requirements.txt -t lib
```
3. Generar los certificados necesarios. (Mas info en el fichero `Vitrasa.py`)
4. Subir la app a Google App Engine
5. Una vez subida la app ir a la url del proyecto, de esta forma activamos el webhook. Ej: https://vbot.appspot.com/
