# -*- coding: utf-8 -*-
from flask import Flask
from flask import request, abort
from api import vitrasa

import telebot


API_TOKEN = ''

WEBHOOK_HOST = '.appspot.com'
WEBHOOK_PORT = 443  # 443, 80, 88 or 8443 (port need to be 'open')

WEBHOOK_SSL_CERT = './webhook_cert.pem'  # Path to the ssl certificate
WEBHOOK_SSL_PRIV = './webhook_pkey.pem'  # Path to the ssl private key

# Quick'n'dirty SSL certificate generation:
#
# openssl genrsa -out webhook_pkey.pem 2048
# openssl req -new -x509 -days 3650 -key webhook_pkey.pem -out webhook_cert.pem
#
# When asked for "Common Name (e.g. server FQDN or YOUR name)" you should reply
# with the same value in you put in WEBHOOK_HOST

WEBHOOK_URL_BASE = "https://%s:%s" % (WEBHOOK_HOST, WEBHOOK_PORT)
WEBHOOK_URL_PATH = "/%s/" % (API_TOKEN)

bot = telebot.TeleBot(API_TOKEN, threaded=False)
# Remove webhook, it fails sometimes the set if there is a previous webhook
bot.remove_webhook()

# Set webhook
bot.set_webhook(url=WEBHOOK_URL_BASE+WEBHOOK_URL_PATH, certificate=open(WEBHOOK_SSL_CERT, 'r'))

app = Flask(__name__)

@app.route('/')
def home():
    return 'Hello world!'


# Process webhook calls
@app.route(WEBHOOK_URL_PATH, methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        abort(403)


def obtener_parada(message, id):
    try:
        buses = vitrasa.get_stop_estimates(id)
        buses = sorted(buses, key=lambda bus: bus.minutes)
        buses = [bus.to_dict() for bus in buses]

        parada = vitrasa.get_stop(id).to_dict()
        print parada
        print buses
        texto = "*Parada Nº {} - {}*".format(parada["number"], parada["name"])
        texto += "\n`{:2} {:2}{:20}\n---------------------------`".format("Min", "L", "Ruta")
        for bus in buses:
            print bus["line"], bus["route"].encode("utf-8"), bus["minutes"]
            texto += "\n`{:2} {:2} {:20}`".format(bus["minutes"], bus["line"], bus["route"].encode("utf-8"))
                                          
        bot.send_message(message.chat.id, texto, parse_mode="Markdown")

        
    except vitrasa.Error as e:
        bot.send_message(message.chat.id, "{}".format(e.message))
    except Exception:
        bot.send_message(message.chat.id, "Se ha producido un error al comunicarse con Vitrasa")

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.send_message(message.chat.id, "Bienvenido, introduce el numero de la parada que quieras consultar o envía tu ubicacion para localizar la parada más próxima\n")

@bot.message_handler(commands=['about'])
def about(message):
    bot.send_message(message.chat.id, "No estamos afiliados a Vitrasa\nCopyright 2017.\nCodigo fuente: https://github.com/dpeite/VitrasaTelegramBot", disable_web_page_preview=True)

@bot.message_handler(commands=['status'])
def status(message):
    try:
        vitrasa.get_stop(14264)
        bot.send_message(message.chat.id, "{} Bot\n{} Servidores de Vitrasa".format((u'\u2705').encode("utf-8"),(u'\u2705').encode("utf-8")))
    except Exception:
        bot.send_message(message.chat.id, "{} Bot\n{} Servidores de Vitrasa".format((u'\u2705').encode("utf-8"), (u'\u274C').encode("utf-8")))
    
@bot.message_handler(content_types=['text'])
def id_parada(message):
    id = message.text
    if not id.isdigit():
        bot.send_message(message.chat.id, "Introduce un numero de parada")
        return
    obtener_parada(message, id)

@bot.message_handler(content_types=['location'])
def coordenadas_parada(message):
    lat =  message.location.latitude
    lon =  message.location.longitude

    try:
        paradas = vitrasa.get_stops_around(lat, lon)
        paradas = sorted(paradas, key=lambda stop: stop.distance)
        paradas = [stop.to_dict() for stop in paradas]
        obtener_parada(message, paradas[0]["number"])
    except vitrasa.Error as e:
         bot.send_message(message.chat.id, "{}".format(e.message))
    except Exception:
        bot.send_message(message.chat.id, "Se ha producido un error al comunicarse con Vitrasa")

