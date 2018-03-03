# -*- coding: utf-8 -*-
import telebot
import json
import datetime
from telebot import types
from api import vitrasa
from pymongo import MongoClient

token = ""
bot = telebot.TeleBot(token)
# connect to MongoDB, change the << MONGODB URL >> to reflect your own connection string
client = MongoClient("<< MONGODB URL >>")
db = client.vitrasabot


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
    print call.data
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
        itembtna = types.InlineKeyboardButton('{} Actualizar'.format((u'\U0001F504').encode("utf-8")), callback_data='{"id_parada": ' + str(id) + '}')
        itembtnb = types.InlineKeyboardButton('{} Paradas cercanas'.format((u'\U0001F50E').encode("utf-8")), switch_inline_query_current_chat="")

        user_data = db.users.find_one({'_id': message.chat.id,'paradas_favoritas.' + str(id): {'$exists' : True}})
        print "-*---------------"
        print user_data
        print message.from_user.id
        print id
        print "*****************"
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
     db.users.update_one({"_id": info["user"] }, {"$unset": {"paradas_favoritas." + str(info["parada"]) : ""}}, upsert=True)
     obtener_parada(message, str(info["parada"]))
     
def add_stop(message, info):
    user_data = db.users.find_one({'_id': info["user"]})
    paradas_favoritas = {}
    if user_data and "paradas_favoritas" in user_data:
        paradas_favoritas = user_data["paradas_favoritas"]
    print "añadimos parada a la lista"
    parada = vitrasa.get_stop(info["parada"]).to_dict()
    paradas_favoritas[str(info["parada"])] = {"name" : parada["name"].encode("utf-8")}
    print paradas_favoritas
    db.users.update_one({"_id": info["user"] }, {"$set": {"_id": info["user"], "paradas_favoritas" : paradas_favoritas}}, upsert=True)
    obtener_parada(message, str(info["parada"]))
        
def obtener_paradas_favoritas(message, info):
    user_data = db.users.find_one({'_id': info["user"]})
    markup = types.InlineKeyboardMarkup()
    if user_data and "paradas_favoritas" in user_data and user_data["paradas_favoritas"]:
        paradas_favoritas = user_data["paradas_favoritas"]
        text =  "Estas son tus paradas guardadas:"
        for parada in paradas_favoritas:
            markup.row(types.InlineKeyboardButton('{} - Nº {}'.format(paradas_favoritas[parada]["name"].encode("utf-8"), parada), callback_data='{"id_parada": ' + parada + '}'))
    else:
        text =  "No hay paradas favoritas"
        
    itembtna = types.InlineKeyboardButton('{} Paradas cercanas'.format((u'\U0001F50E').encode("utf-8")), switch_inline_query_current_chat="")
    # itembtnb = types.InlineKeyboardButton('{} Paradas favoritas'.format((u'\U0001F50E').encode("utf-8")), callback_data='{"paradas_favoritas": {"user" : ' + str(message.chat.id) + '}}')
    markup.row(itembtna)
    
    bot.send_message(message.chat.id, text, reply_markup=markup)
        
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    markup = types.InlineKeyboardMarkup()
    itembtna = types.InlineKeyboardButton('{} Paradas favoritas'.format((u'\U00002B50').encode("utf-8")), callback_data='{"paradas_favoritas": {"user" : ' + str(message.chat.id) + '}}')
    itembtnb = types.InlineKeyboardButton('{} Paradas cercanas'.format((u'\U0001F50E').encode("utf-8")), switch_inline_query_current_chat="")
    markup.row(itembtna, itembtnb)
    text = "Bienvenido, para consultar los horarios necesito alguna información:\n\n \
    - Puedes enviarme el número de la parada.\n\n \
    - Puedes enviarme tu ubicación y automaticamente te devolveré la información de la parada más próxima.\n\n \
    - Puedes hacer click en el botón 'Paradas cercanas' y te mostraré una lista con las paradas ordenadas por proximidad. _(Puedes filtrar esta lista por el nombre de la calle o el número de la parada)_"
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(commands=['about'])
def about(message):
    bot.send_message(message.chat.id, "No estamos afiliados a Vitrasa\nCopyright 2018.\nCodigo fuente: https://github.com/dpeite/VitrasaTelegramBot", disable_web_page_preview=True)

@bot.message_handler(commands=['status'])
def status(message):
    try:
        vitrasa.get_stop(14264)
        bot.send_message(message.chat.id, "{} Bot\n{} Conexión con Vitrasa".format((u'\u2705').encode("utf-8"),(u'\u2705').encode("utf-8")))
    except Exception:
        bot.send_message(message.chat.id, "{} Bot\n{} Conexión con Vitrasa".format((u'\u2705').encode("utf-8"), (u'\u274C').encode("utf-8")))

@bot.message_handler(content_types=['text'])
def id_parada(message):
    print message.from_user
    test = db.users.find_one({'_id': message.from_user.id})
    print test
    db.users.update_one({"_id": message.from_user.id }, {"$set": {"_id":message.from_user.id, "username" : message.from_user.username}}, upsert=True)
    id = message.text
    if not id.isdigit():
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

    try:
        paradas = vitrasa.get_stops_around(lat, lon)
        paradas = sorted(paradas, key=lambda stop: stop.distance)
        paradas = [stop.to_dict() for stop in paradas]
        obtener_parada(message, paradas[0]["number"])
    except vitrasa.Error as e:
         bot.send_message(message.chat.id, "{}".format(e.message))
    except Exception:
        bot.send_message(message.chat.id, "Se ha producido un error al comunicarse con Vitrasa")

bot.polling(none_stop=True)
