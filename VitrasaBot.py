# -*- coding: utf-8 -*-
from flask import Flask
from flask import request, abort

import telebot
import json
import datetime
from telebot import types
from api import vitrasa


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


@bot.inline_handler(lambda query: True)
def query_text(inline_query):
    print inline_query
    print inline_query.location
    if inline_query.location:
        try:
            try:
                paradas = vitrasa.get_stops_around(inline_query.location.latitude, inline_query.location.longitude)
                paradas = sorted(paradas, key=lambda stop: stop.distance)
                paradas = [stop.to_dict() for stop in paradas]
            except vitrasa.Error as e:
                print e
            print paradas
            inline_stops = []
            for idx, parada in enumerate(paradas):
                if inline_query.query:
                    # Filtramos por nombre de parada o numero
                    if (inline_query.query not in parada['name'].lower()) and (inline_query.query not in str(parada['number'])):
                        continue
                response = types.InlineQueryResultLocation(idx, "Nº" + str(parada['number']) + " " + parada['name'].encode("utf-8") + " - " + format(parada['distance'], '.0f') + "m", parada['location']['lat'], parada['location']['lng'])

                inline_stops.append(response)

            bot.answer_inline_query(inline_query.id, inline_stops, cache_time=2)
        except Exception as e:
            print(e)
    else:
        try:
            r2 = types.InlineQueryResultArticle('1', 'Posición no disponible', types.InputTextMessageContent('/help'))
            bot.answer_inline_query(inline_query.id, [r2], cache_time=2)
        except Exception as e:
            print(e)


# Handler para boton actualizar
@bot.callback_query_handler(func=lambda call: True)
def inline_button_callback(call):
    try:
        print call.data
        parada = json.loads(call.data)
        obtener_parada(call.message, parada["id_parada"])
        bot.answer_callback_query(call.id)
    except Exception as e:
        print e

def obtener_parada(message, id):
    try:
        buses = vitrasa.get_stop_estimates(id)
        buses = sorted(buses, key=lambda bus: bus.minutes)
        buses = [bus.to_dict() for bus in buses]

        parada = vitrasa.get_stop(id).to_dict()
        print parada
        print buses
        texto = "*Parada Nº {} - {}*".format(parada["number"], parada["name"].encode("utf-8"))
        texto += "\n" + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        texto += "\n`{:2} {:2}{:20}\n---------------------------`".format("Min", "L", "Ruta")
        for bus in buses:
            print bus["line"], bus["route"].encode("utf-8"), bus["minutes"]
            texto += "\n`{:2} {:2} {:20}`".format(bus["minutes"], bus["line"], bus["route"].encode("utf-8"))

        markup = types.InlineKeyboardMarkup()
        itembtna = types.InlineKeyboardButton('Actualizar', callback_data='{"id_parada": ' + str(id) + '}')
        itembtnb = types.InlineKeyboardButton('Buscar paradas cercanas', switch_inline_query_current_chat="")
        markup.row(itembtna, itembtnb)

        try:
            bot.edit_message_text(texto, message.chat.id, message.message_id, parse_mode="Markdown", reply_markup=markup)
        except telebot.apihelper.ApiException as e:
            error = json.loads(e.result.text.encode('utf8'))
            error_message = error['description'].encode('utf8')
            print error_message
            if error_message != "Bad Request: message is not modified":
                bot.send_message(message.chat.id, texto, parse_mode="Markdown", reply_markup=markup)


    except vitrasa.Error as e:
        bot.send_message(message.chat.id, "{}".format(e.message))
    except Exception as e:
        print e
        bot.send_message(message.chat.id, "Se ha producido un error al realizar la petición")

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
