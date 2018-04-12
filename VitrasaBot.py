# -*- coding: utf-8 -*-

from flask import Flask
from flask import request, abort
import logging
import ConfigParser
import telebot
import json
import datetime
import pytz
from telebot import types
from api import vitrasa
# En caso de querer usar la api http de mlab en vez de usar el driver de pymongo descomentar la linea siguiente
from pymongolab import MongoClient
# from pymongo import MongoClient

config = ConfigParser.ConfigParser()
config.read("conf.ini")

API_TOKEN = config.get("options","bot_token")

WEBHOOK_HOST = config.get("options", "webhook_host")
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

logging.basicConfig(filename='vitrasa.log', format='%(asctime)s %(levelname)s: %(message)s', level=logging.DEBUG)
# No nos interesa el log de DEBUG de suds ni de urllib3
logging.getLogger('suds').setLevel(logging.INFO)
logging.getLogger("urllib3").setLevel(logging.INFO)

logging.info("Inicializando VitrasaBot...")

# connect to MongoDB, change the << MONGODB URL >> to reflect your own connection string
# Si usamos pymongolab la siguiente linea tiene que ser nestra api key
client = MongoClient(config.get("options","mongodb"))
db = client.vitrasabot

bot = telebot.TeleBot(API_TOKEN, threaded=False)
# # Remove webhook, it fails sometimes the set if there is a previous webhook
# bot.remove_webhook()
# logging.debug("Webhook borrado")

# Set webhook
bot.set_webhook(url=WEBHOOK_URL_BASE+WEBHOOK_URL_PATH, certificate=open(WEBHOOK_SSL_CERT, 'r'))
logging.debug("Webhook creado")

app = Flask(__name__)

tz =pytz.timezone("Europe/Madrid")

logging.info("VitrasaBot inicializado correctamente")

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
    logging.debug("Inline query {}".format(inline_query))
    if inline_query.location:
        try:
            try:
                paradas = vitrasa.get_stops_around(inline_query.location.latitude, inline_query.location.longitude)
                paradas = sorted(paradas, key=lambda stop: stop.distance)
                paradas = [stop.to_dict() for stop in paradas]
            except vitrasa.Error as e:
                raise e
            logging.debug("Paradas cercanas {}: ".format(paradas))
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
            logging.error("Se ha producido un error: {}".format(e))
            r2 = types.InlineQueryResultArticle('1', 'Se ha producido un error', types.InputTextMessageContent('/help'), description="Vuelva a intentarlo más tarde")
            bot.answer_inline_query(inline_query.id, [r2], cache_time=2)
    else:
        logging.debug("Posicion no disponible")
        r2 = types.InlineQueryResultArticle('1', 'Posición no disponible', types.InputTextMessageContent('/help'), description="Vuelva a intentarlo más tarde")
        bot.answer_inline_query(inline_query.id, [r2], cache_time=2)

# Handler para boton actualizar
@bot.callback_query_handler(func=lambda call: True)
def inline_button_callback(call):
    logging.debug("Callback botones: {}".format(call.data))
    parada = json.loads(call.data)
    if "id_parada" in parada:
        obtener_parada(call.message, str(parada["id_parada"]))
    elif "paradas_favoritas" in parada:
        obtener_paradas_favoritas(call.message, parada["paradas_favoritas"])
    elif "add_stop" in parada:
        add_stop(call.message, parada["add_stop"])
    elif "del_stop" in parada:
        del_stop(call.message, parada["del_stop"])

    bot.answer_callback_query(call.id)


def obtener_parada(message, id):
    logging.info("Obtenemos informacion de los buses correspondientes a la parada {}".format(str(id)))
    logging.debug("Mensaje recibido de {} - {}".format(message.chat.id, (message.chat.username and message.chat.username.encode("utf-8")) or (message.chat.first_name and message.chat.first_name.encode("utf-8"))))
        
    try:
        buses = vitrasa.get_stop_estimates(id)
        buses = sorted(buses, key=lambda bus: bus.minutes)
        buses = [bus.to_dict() for bus in buses]

        parada = vitrasa.get_stop(id).to_dict()
        logging.debug("Informacion de la parada: {}".format(parada))
        logging.debug("Informacion sobre los buses: {}".format(buses))
        
        texto = "*Parada Nº {} - {}*".format(parada["number"], parada["name"].encode("utf-8"))
        texto += "\n" + datetime.datetime.now(tz=tz).strftime("%Y-%m-%d %H:%M:%S")
        texto += "\n`{:2} {:2}{:20}\n---------------------------`".format("Min", "L", "Ruta")

        for bus in buses:
            # print bus["line"], bus["route"].encode("utf-8"), bus["minutes"]
            texto += "\n`{:2} {:2} {:20}`".format(bus["minutes"], bus["line"], bus["route"].encode("utf-8").strip())

        markup = types.InlineKeyboardMarkup()
        itembtna = types.InlineKeyboardButton('{} Actualizar'.format((u'\U0001F504').encode("utf-8")), callback_data='{"id_parada": ' + str(id) + '}')
        itembtnb = types.InlineKeyboardButton('{} Paradas cercanas'.format((u'\U0001F50E').encode("utf-8")), switch_inline_query_current_chat="")

        # Si usamos pymongolab descomentar esta query y comentar la siguiente
        user_data = db.users.find_one({'_id': message.chat.id,'paradas_favoritas.' + str(id): {'$exists' : 'True'}})
        # user_data = db.users.find_one({'_id': message.chat.id,'paradas_favoritas.' + str(id): {'$exists' : True}})
        db.users.update({"_id": message.chat.id }, {"$set": {"_id": message.chat.id, "username" : message.chat.username or message.chat.first_name, "last_request" : datetime.datetime.now(tz=tz).strftime("%Y-%m-%d %H:%M")}}, upsert=True)
        # db.users.update_one({"_id": message.chat.id }, {"$set": {"_id": message.chat.id, "username" : message.chat.username or message.chat.first_name, "last_request" : datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}}, upsert=True)

        if user_data:
            text2 = '{} Borrar parada'.format((u'\U0000274C').encode("utf-8"))
            itembtnc = types.InlineKeyboardButton(text2, callback_data='{"del_stop": {"user" : ' + str(message.chat.id) + ' , "parada" : ' + str(id) + '}}')
        else:
            text2 = '{} Guardar parada'.format((u'\U0001F4BE').encode("utf-8"))
            itembtnc = types.InlineKeyboardButton(text2, callback_data='{"add_stop": {"user" : ' + str(message.chat.id) + ' , "parada" : ' + str(id) + '}}')

        itembtnd = types.InlineKeyboardButton('{} Paradas favoritas'.format((u'\U00002B50').encode("utf-8")), callback_data='{"paradas_favoritas": {"user" : ' + str(message.chat.id) + '}}')
                
        markup.row(itembtna, itembtnb)
        markup.row(itembtnc, itembtnd)

        try:
            bot.edit_message_text(texto, message.chat.id, message.message_id, parse_mode="Markdown", reply_markup=markup)
        except telebot.apihelper.ApiException as e:
            error = json.loads(e.result.text.encode('utf8'))
            error_message = error['description'].encode('utf8')
            if error_message != "Bad Request: message is not modified":
                bot.send_message(message.chat.id, texto, parse_mode="Markdown", reply_markup=markup)


    except vitrasa.Error as e:
        bot.send_message(message.chat.id, "{}".format(e.message))
    except Exception as e:
        print e
        import sys
        print sys.exc_info()[2].tb_lineno

        bot.send_message(message.chat.id, "Se ha producido un error al realizar la petición")

def del_stop(message, info):
    logging.info("Borrando parada de favoritas")
    logging.debug("Mensaje recibido de {} - {}".format(message.chat.id, (message.chat.username and message.chat.username.encode("utf-8")) or (message.chat.first_name and message.chat.first_name.encode("utf-8"))))

    # Si usamos pymongolab descomentar esta query y comentar la siguiente
    db.users.update({"_id": info["user"] }, {"$unset": {"paradas_favoritas." + str(info["parada"]) : ""}}, upsert=True)
    # db.users.update_one({"_id": info["user"] }, {"$unset": {"paradas_favoritas." + str(info["parada"]) : ""}}, upsert=True)

    logging.debug("Parada {} borrada correctamente de la BD".format(str(info["parada"])))    

    obtener_parada(message, str(info["parada"]))
     
def add_stop(message, info):
    logging.info("Añadiendo parada a favoritas")
    logging.debug("Mensaje recibido de {} - {}".format(message.chat.id, (message.chat.username and message.chat.username.encode("utf-8")) or (message.chat.first_name and message.chat.first_name.encode("utf-8"))))

    user_data = db.users.find_one({'_id': info["user"]})
    paradas_favoritas = {}
    if user_data and "paradas_favoritas" in user_data:
        paradas_favoritas = user_data["paradas_favoritas"]

    parada = vitrasa.get_stop(info["parada"]).to_dict()
    paradas_favoritas[str(info["parada"])] = {"name" : parada["name"].encode("utf-8")}
    
    # Si usamos pymongolab descomentar esta query y comentar la siguiente
    db.users.update({"_id": info["user"] }, {"$set": {"_id": info["user"], "paradas_favoritas" : paradas_favoritas}}, upsert=True)
    # db.users.update_one({"_id": info["user"] }, {"$set": {"_id": info["user"], "paradas_favoritas" : paradas_favoritas}}, upsert=True)

    logging.debug("Parada {} - {} añadida correctamente a la BD".format(str(info["parada"]), parada["name"].encode("utf-8")))
    
    obtener_parada(message, str(info["parada"]))
        
def obtener_paradas_favoritas(message, info):
    logging.info("Obteniendo paradas favoritas")
    logging.debug("Mensaje recibido de {} - {}".format(message.chat.id, (message.chat.username and message.chat.username.encode("utf-8")) or (message.chat.first_name and message.chat.first_name.encode("utf-8"))))
    user_data = db.users.find_one({'_id': info["user"]})
    markup = types.InlineKeyboardMarkup()
    if user_data and "paradas_favoritas" in user_data and user_data["paradas_favoritas"]:
        paradas_favoritas = user_data["paradas_favoritas"]
        logging.debug("Paradas favoritas: {}".format(paradas_favoritas))
        text =  "Estas son tus paradas guardadas:"
        for parada in paradas_favoritas:
            markup.row(types.InlineKeyboardButton('{} - Nº {}'.format(paradas_favoritas[parada]["name"].encode("utf-8"), parada), callback_data='{"id_parada": ' + parada + '}'))
    else:
        text =  "No hay paradas favoritas"
        logging.debug("No hay paradas favoritas guardadas")
        
    itembtna = types.InlineKeyboardButton('{} Paradas cercanas'.format((u'\U0001F50E').encode("utf-8")), switch_inline_query_current_chat="")
    # itembtnb = types.InlineKeyboardButton('{} Paradas favoritas'.format((u'\U0001F50E').encode("utf-8")), callback_data='{"paradas_favoritas": {"user" : ' + str(message.chat.id) + '}}')
    markup.row(itembtna)
    
    bot.send_message(message.chat.id, text, reply_markup=markup)
        
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    logging.info("Comando {}".format(message.text.encode("utf-8")))
    logging.debug("Mensaje recibido de {} - {}".format(message.chat.id, (message.chat.username and message.chat.username.encode("utf-8")) or (message.chat.first_name and message.chat.first_name.encode("utf-8"))))

    markup = types.InlineKeyboardMarkup()
    itembtna = types.InlineKeyboardButton('{} Paradas favoritas'.format((u'\U00002B50').encode("utf-8")), callback_data='{"paradas_favoritas": {"user" : ' + str(message.chat.id) + '}}')
    itembtnb = types.InlineKeyboardButton('{} Paradas cercanas'.format((u'\U0001F50E').encode("utf-8")), switch_inline_query_current_chat="")
    markup.row(itembtna, itembtnb)
    text = "Bienvenido, para consultar los horarios necesito alguna información:\n\n \
    - Puedes enviarme el número de la parada.\n\n \
    - Puedes enviarme tu ubicación y automaticamente te devolveré la información de la parada más próxima.\n\n \
    - Puedes hacer click en el botón 'Paradas cercanas' y te mostraré una lista con las paradas ordenadas por proximidad. _(Puedes filtrar esta lista por el nombre de la calle o el número de la parada)_ \
* La busqueda de paradas cercanas solo funciona desde móviles, es necesario darle permiso al bot para conocer tu ubicación.*"
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(commands=['about'])
def about(message):
    logging.info("Comando about")
    logging.debug("Mensaje recibido de {} - {}".format(message.chat.id, (message.chat.username and message.chat.username.encode("utf-8")) or (message.chat.first_name and message.chat.first_name.encode("utf-8"))))
    bot.send_message(message.chat.id, "No estamos afiliados a Vitrasa\nCopyright 2018.\nCodigo fuente: https://github.com/dpeite/VitrasaTelegramBot", disable_web_page_preview=True)

@bot.message_handler(commands=['status'])
def status(message):
    logging.info("Comando status")
    logging.debug("Mensaje recibido de {} - {}".format(message.chat.id, (message.chat.username and message.chat.username.encode("utf-8")) or (message.chat.first_name and message.chat.first_name.encode("utf-8"))))
    try:
        vitrasa.get_stop(14264)
        bot.send_message(message.chat.id, "{} Bot\n{} Conexión con Vitrasa".format((u'\u2705').encode("utf-8"),(u'\u2705').encode("utf-8")))
    except Exception:
        bot.send_message(message.chat.id, "{} Bot\n{} Conexión con Vitrasa".format((u'\u2705').encode("utf-8"), (u'\u274C').encode("utf-8")))

@bot.message_handler(content_types=['text'])
def id_parada(message):
    logging.info("Recibida parada con id {}".format(message.text.encode("utf-8")))
    logging.debug("Mensaje recibido de {} - {}".format(message.chat.id, (message.chat.username and message.chat.username.encode("utf-8")) or (message.chat.first_name and message.chat.first_name.encode("utf-8"))))
    
    test = db.users.find_one({'_id': message.from_user.id})
    # Si usamos pymongolab descomentar esta query y comentar la siguiente
    db.users.update({"_id": message.from_user.id }, {"$set": {"_id":message.from_user.id, "username" : message.from_user.username}}, upsert=True)
    # db.users.update_one({"_id": message.from_user.id }, {"$set": {"_id":message.from_user.id, "username" : message.from_user.username}}, upsert=True)
    id = message.text
    if not id.isdigit():
        logging.debug("La parada introducida no es un numero")
        markup = types.InlineKeyboardMarkup()
        itembtna = types.InlineKeyboardButton('{} Paradas cercanas'.format((u'\U0001F50E').encode("utf-8")), switch_inline_query_current_chat="")
        itembtnb = types.InlineKeyboardButton('{} Paradas favoritas'.format((u'\U00002B50').encode("utf-8")), callback_data='{"paradas_favoritas": {"user" : ' + str(message.from_user.id) + '}}')
        markup.row(itembtnb, itembtna)
        text = "Introduce un número de parada, envíame tu ubicación o busca las paradas más próximas"
        bot.send_message(message.chat.id, text, reply_markup=markup)
        return
    obtener_parada(message, id)

@bot.message_handler(content_types=['location'])
def coordenadas_parada(message):
    lat =  message.location.latitude
    lon =  message.location.longitude

    logging.info("Recibidas coordenadas lat {}, lon {}".format(lat, lon))
    logging.debug("Mensaje recibido de {} - {}".format(message.chat.id, (message.chat.username and message.chat.username.encode("utf-8")) or (message.chat.first_name and message.chat.first_name.encode("utf-8"))))
    
    try:
        paradas = vitrasa.get_stops_around(lat, lon)
        paradas = sorted(paradas, key=lambda stop: stop.distance)
        paradas = [stop.to_dict() for stop in paradas]
        obtener_parada(message, paradas[0]["number"])
    except vitrasa.Error as e:
         bot.send_message(message.chat.id, "{}".format(e.message))
    except Exception as e:
        bot.send_message(message.chat.id, "Se ha producido un error al comunicarse con Vitrasa")
        logging.error("Exception: {}".format(e.message))
