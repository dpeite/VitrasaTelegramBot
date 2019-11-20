# -*- coding: utf-8 -*-
import logging
import configparser
import telebot
import json
import datetime
import pytz
import hashlib
import sched
import time
from telebot import types
from api import vitrasa_new as vitrasa
# En caso de querer usar la api http de mlab en vez de usar el driver de pymongo descomentar la linea siguiente
# from pymongolab import MongoClient
from pymongo import MongoClient

logging.basicConfig(filename='vitrasa.log', format='%(asctime)s %(levelname)s: %(message)s', level=logging.DEBUG)
# No nos interesa el log de DEBUG de suds ni de urllib3
logging.getLogger('suds').setLevel(logging.INFO)
logging.getLogger("urllib3").setLevel(logging.INFO)

logging.info("Inicializando VitrasaBot...")

config = configparser.ConfigParser()
config.read("conf.ini")

token = config.get("options","bot_token")
bot = telebot.TeleBot(token)
# connect to MongoDB, change the << MONGODB URL >> to reflect your own connection string
# Si usamos pymongolab la siguiente linea tiene que ser nestra api key
client = MongoClient(config.get("options","mongodb"), retryWrites=False)
db = client.vitrasabot

tz =pytz.timezone("Europe/Madrid")

logging.info("VitrasaBot inicializado correctamente")

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
                response = types.InlineQueryResultLocation(idx, "Nº" + str(parada['number']) + " " + parada['name'] + " - " + format(parada['distance'], '.0f') + "m", parada['location']['lat'], parada['location']['lng'])

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
        obtener_parada(call.message, int(parada["id_parada"]))
    elif "paradas_favoritas" in parada:
        obtener_paradas_favoritas(call.message, parada["paradas_favoritas"])
    elif "add_stop" in parada:
        add_stop(call.message, parada["add_stop"])
    elif "del_stop" in parada:
        del_stop(call.message, parada["del_stop"])
    elif "menu_nuevo_aviso" in parada:
        crear_menu_nuevo_aviso(call.message, parada["menu_nuevo_aviso"])
    elif "menu_aviso_tiempo" in parada:
        crear_menu_aviso_tiempo(call.message, parada["menu_aviso_tiempo"])
    elif "crear_aviso" in parada:
        crear_aviso(call.message, parada["crear_aviso"])
    elif "mostrar_aviso" in parada:
        mostrar_info_aviso(call.message, parada["mostrar_aviso"])
    elif "mostrar_avisos" in parada:
        avisos(call.message)
    elif "borrar_aviso" in parada:
        borrar_aviso(call.message, parada["borrar_aviso"])
    elif "borrar_mensaje" in parada:
        borrar_mensaje(call.message)

    bot.answer_callback_query(call.id)


def obtener_parada(message, id):
    logging.info("Obtenemos informacion de los buses correspondientes a la parada {}".format(str(id)))
    logging.debug("Mensaje recibido de {} - {}".format(message.chat.id, (message.chat.username and message.chat.username) or (message.chat.first_name and message.chat.first_name)))
        
    try:
        buses = vitrasa.get_stop_estimates(id)
        buses = sorted(buses, key=lambda bus: bus.minutes)
        buses = [bus.to_dict() for bus in buses]

        parada = vitrasa.get_stop(id).to_dict()
        logging.debug("Informacion de la parada: {}".format(parada))
        logging.debug("Informacion sobre los buses: {}".format(buses))
        
        texto = "*Parada Nº {} - {}*".format(parada["number"], parada["name"])
        texto += "\n" + datetime.datetime.now(tz=tz).strftime("%Y-%m-%d %H:%M:%S")
        texto += "\n`{:2} {:2}{:20}\n---------------------------`".format("Min", "L", "Ruta")

        for bus in buses:
            # print(bus["line"], bus["route"], bus["minutes"])
            texto += "\n`{:2} {:2} {:20}`".format(bus["minutes"], bus["line"], bus["route"].strip())

        markup = types.InlineKeyboardMarkup()
        itembtna = types.InlineKeyboardButton('{} Actualizar'.format((u'\U0001F504')), callback_data='{"id_parada": ' + str(id) + '}')
        itembtnb = types.InlineKeyboardButton('{} Paradas cercanas'.format((u'\U0001F50E')), switch_inline_query_current_chat="")

        # Si usamos pymongolab descomentar esta query y comentar la siguiente
        # user_data = db.users.find_one({'_id': message.chat.id,'paradas_favoritas.' + str(id): {'$exists' : 'True'}})
        user_data = db.users.find_one({'_id': message.chat.id,'paradas_favoritas.' + str(id): {'$exists' : True}})
        db.users.update_one({"_id": message.chat.id }, {"$set": {"_id": message.chat.id, "username" : message.chat.username or message.chat.first_name, "last_request" : datetime.datetime.now(tz=tz).strftime("%Y-%m-%d %H:%M")}}, upsert=True)
        if user_data:
            text2 = '{} Borrar parada'.format((u'\U0000274C'))
            itembtnc = types.InlineKeyboardButton(text2, callback_data='{"del_stop": {"user" : ' + str(message.chat.id) + ' , "parada" : ' + str(id) + '}}')
        else:
            text2 = '{} Guardar parada'.format((u'\U0001F4BE'))
            itembtnc = types.InlineKeyboardButton(text2, callback_data='{"add_stop": {"user" : ' + str(message.chat.id) + ' , "parada" : ' + str(id) + '}}')

        itembtnd = types.InlineKeyboardButton('{} Paradas favoritas'.format((u'\U00002B50')), callback_data='{"paradas_favoritas": {"user" : ' + str(message.chat.id) + '}}')
        itembtne = types.InlineKeyboardButton('{} Avisame (Beta)'.format((u'\U0001F6CE')), callback_data='{"menu_nuevo_aviso": {"user" : ' + str(message.chat.id) + ', "parada" : ' + str(id) + '}}')

        markup.row(itembtna, itembtnb)
        markup.row(itembtnc, itembtnd)
        markup.row(itembtne)

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
        print(e)
        import sys
        print(sys.exc_info()[2].tb_lineno)

        bot.send_message(message.chat.id, "Se ha producido un error al realizar la petición")

def del_stop(message, info):
    logging.info("Borrando parada de favoritas")
    logging.debug("Mensaje recibido de {} - {}".format(message.chat.id, (message.chat.username and message.chat.username) or (message.chat.first_name and message.chat.first_name)))

    # Si usamos pymongolab descomentar esta query y comentar la siguiente
    # db.users.update({"_id": info["user"] }, {"$unset": {"paradas_favoritas." + str(info["parada"]) : ""}}, upsert=True)
    db.users.update_one({"_id": info["user"] }, {"$unset": {"paradas_favoritas." + str(info["parada"]) : ""}}, upsert=True)

    logging.debug("Parada {} borrada correctamente de la BD".format(str(info["parada"])))    

    obtener_parada(message, int(info["parada"]))
     
def add_stop(message, info):
    logging.info("Añadiendo parada a favoritas")
    logging.debug("Mensaje recibido de {} - {}".format(message.chat.id, (message.chat.username and message.chat.username) or (message.chat.first_name and message.chat.first_name)))

    user_data = db.users.find_one({'_id': info["user"]})
    paradas_favoritas = {}
    if user_data and "paradas_favoritas" in user_data:
        paradas_favoritas = user_data["paradas_favoritas"]

    parada = vitrasa.get_stop(info["parada"]).to_dict()
    paradas_favoritas[str(info["parada"])] = {"name" : parada["name"]}
    
    # Si usamos pymongolab descomentar esta query y comentar la siguiente
    # db.users.update({"_id": info["user"] }, {"$set": {"_id": info["user"], "paradas_favoritas" : paradas_favoritas}}, upsert=True)
    db.users.update_one({"_id": info["user"] }, {"$set": {"_id": info["user"], "paradas_favoritas" : paradas_favoritas}}, upsert=True)

    logging.debug("Parada {} - {} añadida correctamente a la BD".format(str(info["parada"]), parada["name"]))
    
    obtener_parada(message, int(info["parada"]))
        
def obtener_paradas_favoritas(message, info):
    logging.info("Obteniendo paradas favoritas")
    logging.debug("Mensaje recibido de {} - {}".format(message.chat.id, (message.chat.username and message.chat.username) or (message.chat.first_name and message.chat.first_name)))
    user_data = db.users.find_one({'_id': info["user"]})
    markup = types.InlineKeyboardMarkup()
    if user_data and "paradas_favoritas" in user_data and user_data["paradas_favoritas"]:
        paradas_favoritas = user_data["paradas_favoritas"]
        logging.debug("Paradas favoritas: {}".format(paradas_favoritas))
        text =  "Estas son tus paradas guardadas:"
        for parada in paradas_favoritas:
            markup.row(types.InlineKeyboardButton('{} - Nº {}'.format(paradas_favoritas[parada]["name"], parada), callback_data='{"id_parada": ' + parada + '}'))
    else:
        text = "No hay paradas favoritas"
        logging.debug("No hay paradas favoritas guardadas")
        
    itembtna = types.InlineKeyboardButton('{} Paradas cercanas'.format((u'\U0001F50E')), switch_inline_query_current_chat="")
    # itembtnb = types.InlineKeyboardButton('{} Paradas favoritas'.format((u'\U0001F50E')), callback_data='{"paradas_favoritas": {"user" : ' + str(message.chat.id) + '}}')
    markup.row(itembtna)
    
    bot.send_message(message.chat.id, text, reply_markup=markup)

def crear_menu_nuevo_aviso(message, info):
    logging.info("Crear aviso 0: Seleccionar linea")
    logging.debug("Mensaje recibido de {} - {}".format(message.chat.id, (message.chat.username and message.chat.username) or (message.chat.first_name and message.chat.first_name)))
                  
    buses = vitrasa.get_stop_estimates(info["parada"])

    seen = dict()
    [x for x in buses if x.line+x.route not in seen.keys() and not seen.update({x.line+x.route: x.to_dict()})]
    buses = seen.values()

    buses = sorted(buses, key=lambda bus: bus.get('minutes'))

    markup = types.InlineKeyboardMarkup()
    for bus in buses:
        m = hashlib.md5()
        m.update(bus["line"].encode("utf-8") + bus["route"].encode("utf-8"))
        markup.row(types.InlineKeyboardButton('{} {}'.format(bus["line"], bus["route"]), callback_data='{"menu_aviso_tiempo":{"stop":' + str(info["parada"]) + ',"info":"'+m.hexdigest()[:5]+'"}}'))

    markup.row(types.InlineKeyboardButton('Salir', callback_data='{"borrar_mensaje": {"user" : ' + str(message.chat.id) + '}}'))
    bot.send_message(message.chat.id, "Estas son las lineas correspondientes a la parada "+str(info["parada"]), reply_markup=markup)

def crear_menu_aviso_tiempo(message, info):
    logging.info("Crear aviso 1: Seleccionar tiempo")
    logging.debug("Mensaje recibido de {} - {}".format(message.chat.id, (message.chat.username and message.chat.username) or (message.chat.first_name and message.chat.first_name)))
                  
    borrar_mensaje(message)

    # Si han pasado más de 2 min desde el mensaje anterior y este cancelamos la creación
    if message.date + 120 < int(datetime.datetime.now(tz=tz).strftime('%s')):
        logging.debug("Han pasado mas de 2 min desde el mensaje anterior, cancelamos creacion de aviso")
        bot.send_message(message.chat.id, "Han pasado más de 2 minutos desde que comenzaste el proceso de creación de un aviso. Vuelve a empezar de nuevo")
        return

    line_info = get_line_info_from_hash(info["stop"], info["info"])
    if line_info:
        logging.debug("Hemos encontrado la linea pedida por el usuario, calculamos las tiempos disponibles para el aviso")
        markup = types.InlineKeyboardMarkup()
        if line_info["minutes"] >= 3:
            markup.row(types.InlineKeyboardButton('3 min', callback_data='{"crear_aviso":{"stop":' + str(info["stop"]) + ',"info":"'+info["info"]+'", "time" : 3}}'))
        if line_info["minutes"] >= 7:
            markup.row(types.InlineKeyboardButton('7 min', callback_data='{"crear_aviso":{"stop":' + str(info["stop"]) + ',"info":"'+info["info"]+'", "time" : 7}}'))
        if line_info["minutes"] >= 10:
            markup.row(types.InlineKeyboardButton('10 min', callback_data='{"crear_aviso":{"stop":' + str(info["stop"]) + ',"info":"'+info["info"]+'", "time" : 10}}'))
        if line_info["minutes"] >= 15:
            markup.row(types.InlineKeyboardButton('15 min', callback_data='{"crear_aviso":{"stop":' + str(info["stop"]) + ',"info":"'+info["info"]+'", "time" : 15}}'))
        if line_info["minutes"] >= 30:
            markup.row(types.InlineKeyboardButton('30 min', callback_data='{"crear_aviso":{"stop":' + str(info["stop"]) + ',"info":"'+info["info"]+'", "time" : 30}}'))
            
        markup.row(types.InlineKeyboardButton('Salir', callback_data='{"borrar_mensaje": {"user" : ' + str(message.chat.id) + '}}'))
        bot.send_message(message.chat.id, "Selecciona cuanto tiempo antes quieres ser avisado para la linea: "+
                         line_info["line"] + " - " + line_info["route"], reply_markup=markup)

    else:
        logging.debug("No hemos encontrado la linea, o bien ya no aparece en la parada o no tenemos conexion con Vitrasa")

scheduler = sched.scheduler(time.time, time.sleep)

def crear_aviso(message, info, scheduled=False):
    logging.info("Crear aviso 2: Añadir aviso a scheduler y base de datos")
    logging.debug("Mensaje recibido de {} - {}".format(message.chat.id, (message.chat.username and message.chat.username) or (message.chat.first_name and message.chat.first_name)))

    #### TODO
    # -Revisar posibles excepciones
    # -Revisar si se cae la conexión con vitrasa

    # Si han pasado más de 2 min desde el mensaje anterior y este cancelamos la creación
    if not scheduled and message.date + 120 < int(datetime.datetime.now(tz=tz).strftime('%s')):
        logging.debug("Han pasado mas de 2 min desde el mensaje anterior, cancelamos creacion de aviso")
        borrar_mensaje(message)
        bot.send_message(message.chat.id, "Han pasado más de 2 minutos desde que comenzaste el proceso de creación de un aviso. Vuelve a empezar de nuevo")
        return

    line_info = get_line_info_from_hash(info["stop"], info["info"])

    if line_info:
        if line_info["minutes"] <= info["time"]:
            logging.debug("Faltan menos de {} minutos, avisamos al usuario".format(info["time"]))
            bot.send_message(message.chat.id, "Faltan menos de {} minutos".format(info["time"]))
            m = hashlib.md5()
            m.update(info["info"].encode("utf-8") + str(info['stop']).encode("utf-8") + str(info['time']).encode("utf-8"))
            line_hash = m.hexdigest()[:5]
            borrar_aviso(message, {'id': line_hash}, False)
        else:
            time_delta = int(line_info["minutes"])- int(info["time"])
            if time_delta <= 2:
                logging.debug("Quedan menos de 2 minutos para que avisemos, comprobamos cada 30s")
                timeout = 30
            elif time_delta <= 7:
                logging.debug("Quedan menos de 7 minutos para que avisemos, comprobamos cada 2 minutos")
                timeout = 120
            elif time_delta <= 12:
                logging.debug("Quedan menos de 12 minutos para que avisemos, comprobamos cada 4 minutos")
                timeout = 240
            else:
                logging.debug("Quedan mas de 15 minutos, comprobamos cada 8 minutos")
                timeout = 480


            user_data = db.users.find_one({'_id': message.chat.id})
            avisos = {}
            if user_data and "avisos" in user_data:
                avisos = user_data["avisos"]

            if not scheduled:
                logging.debug("Lanzada por usuario para crear aviso")
                aviso_en_bd = False
                aviso_en_sched = False
                
                parada = vitrasa.get_stop(info["stop"]).to_dict()

                aviso_en_bd = info["info"] in avisos and \
                   str(info["stop"]) in avisos[info["info"]] and \
                   str(info["time"]) in avisos[info["info"]][str(info["stop"])]

                for sched in scheduler.queue:
                    sched_params = sched[3][1]
                    
                    if sched_params["info"] == info["info"] and sched_params["stop"] == info["stop"] and sched_params["time"] == info["time"]:
                        logging.debug("Ya existe este aviso en el scheduler")
                        aviso_en_sched = True
                        break
                        
                if not aviso_en_sched and not aviso_en_bd:
                    logging.debug("Creamos el aviso en el scheduler y en la base de datos")
                    event = scheduler.enter(timeout, 1, crear_aviso, (message, info, True))
                    if not info["info"] in avisos:
                        avisos[info["info"]] = {}
                    if not str(info["stop"]) in avisos[info["info"]]:
                        avisos[info["info"]] = {str(info["stop"]) : {}}
                    if not str(info["time"]) in avisos[info["info"]][str(info["stop"])]:
                        avisos[info["info"]][str(info["stop"])][str(info["time"])] = {}
                    avisos[info["info"]][str(info["stop"])][str(info["time"])] = {"parada_name" : parada["name"], "linea" : line_info["line"], "ruta" : line_info["route"],
                                                                                    "time_created" : datetime.datetime.now(tz=tz).strftime("%Y-%m-%d %H:%M")}
                    # Si usamos pymongolab descomentar esta query y comentar la siguiente
                    # db.users.update({"_id": message.chat.id }, {"$set": {"_id": message.chat.id, "avisos" : avisos}}, upsert=True)
                    db.users.update_one({"_id": message.chat.id }, {"$set": {"_id": message.chat.id, "avisos" : avisos}}, upsert=True)

                if not aviso_en_sched and aviso_en_bd:
                    logging.debug("Ya existe un aviso en la base de datos, lo creamos tambien para el scheduler")
                    event = scheduler.enter(15, 1, crear_aviso, (message, info, True))

                if aviso_en_sched and aviso_en_bd:
                    logging.debug("Ya existen ambos avisos, así que no hacemos nada")

                logging.debug("Aviso creado correctamente, avisamos al usuario")
                borrar_mensaje(message)
                bot.send_message(message.chat.id, "Aviso creado, para gestionar los avisos guardados utiliza el comando /avisos")


            else:
                logging.debug("Lanzado por el bot, faltan mas de {} minutos, volvemos a encolar por {}s".format(time_delta, timeout))
                aviso_en_bd = info["info"] in avisos and \
                   str(info["stop"]) in avisos[info["info"]] and \
                   str(info["time"]) in avisos[info["info"]][str(info["stop"])]

                if aviso_en_bd:
                    logging.debug("El aviso existe en la base de datos, por lo tanto lo volvemos a añadir al scheduler")
                    event = scheduler.enter(15, 1, crear_aviso, (message, info, True))
                else:
                    logging.debug("No volvemos a añadir el aviso al sched porque ya no existe en la BD")
                
            # FIXME Si hacemos run en cada aviso se bloquea el bot.
            if len(scheduler.queue) == 1:
                logging.debug("Tenemos un aviso en el scheduler, lanzamos scheduler")
                scheduler.run()
            
def mostrar_info_aviso(message, info):
    logging.info("Mostrar informacion sobre aviso")
    logging.debug("Mensaje recibido de {} - {}".format(message.chat.id, (message.chat.username and message.chat.username) or (message.chat.first_name and message.chat.first_name)))
    
    user_data = db.users.find_one({'_id': message.chat.id})
    avisos = {}
    if user_data and "avisos" in user_data:
        avisos = user_data["avisos"]
    
    for linea in avisos:
        for parada in  avisos[linea]:
            for aviso in avisos[linea][parada]:
                info_aviso = avisos[linea][parada][aviso]
                m = hashlib.md5()
                m.update(linea.encode("utf-8")+parada.encode("utf-8")+aviso.encode("utf-8"))
                digest = m.hexdigest()[:5]
                if info["id"] == digest:
                    buses = vitrasa.get_stop_estimates(parada)
                    buses = sorted(buses, key=lambda bus: bus.minutes)
                    buses = [bus.to_dict() for bus in buses]
                    
                    line_info = None
                    for bus in buses:
                        m = hashlib.md5()
                        m.update(bus["line"].encode("utf-8") + bus["route"].encode("utf-8"))
                        line_hash = m.hexdigest()[:5]
                        if line_hash == linea:
                            line_info = bus
                            break;

                    if line_info:
                        text = "*Parada:* {} - {} \n\
*Ruta:* {} {} \n\
*Minutos restantes:* {}min \n\
*Avisar a:* {}min\n\
*Fecha de creación del aviso:* {}".format(parada, info_aviso["parada_name"], info_aviso["linea"], info_aviso["ruta"], line_info["minutes"], aviso, info_aviso["time_created"])
                        markup = types.InlineKeyboardMarkup()
                        itembtna = types.InlineKeyboardButton('{} Borrar aviso'.format((u'\U0000274C')), callback_data='{"borrar_aviso": {"id" : "' + info["id"] + '"}}')
                        itembtnb = types.InlineKeyboardButton('{} Mostrar avisos'.format((u'\U00002B50')), callback_data='{"mostrar_avisos": {}}')
                        markup.row(itembtna, itembtnb)
                        bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)
                    else:
                        logging.debug("No se ha encontrado información sobre el bus para este aviso. Así que no es posible realizar dicho aviso")
                        text = "*Parada:* {} - {} \n\
*Ruta:* {} {} \n\
*Avisar a:* {}min\n\
*Fecha de creación del aviso:* {}\n\
*No se ha encontrado ningún bus en esta parada que coincida con los datos del aviso guardado*".format(parada, info_aviso["parada_name"], info_aviso["linea"], info_aviso["ruta"], aviso, info_aviso["time_created"])
                        bot.send_message(message.chat.id, text, parse_mode="Markdown")

def borrar_aviso(message, info, send_message = True):
    logging.info("Borrar aviso")
    logging.debug("Mensaje recibido de {} - {}".format(message.chat.id, (message.chat.username and message.chat.username) or (message.chat.first_name and message.chat.first_name)))
    
    user_data = db.users.find_one({'_id': message.chat.id})
    avisos = {}
    if user_data and "avisos" in user_data:
        avisos = user_data["avisos"]

    for linea in avisos:
        for parada in  avisos[linea]:
            for aviso in avisos[linea][parada]:
                info_aviso = avisos[linea][parada][aviso]
                m = hashlib.md5()
                m.update(linea.encode("utf-8")+parada.encode("utf-8")+aviso.encode("utf-8"))
                digest = m.hexdigest()[:5]
                if info["id"] == digest:
                    logging.debug("Borramos de la base de datos el aviso")
                    del  avisos[linea][parada][aviso]
                    # Si usamos pymongolab descomentar esta query y comentar la siguiente
                    # db.users.update({"_id": info["user"] }, {"$set": {"_id": info["user"], "avisos" : avisos}}, upsert=True)
                    db.users.update_one({"_id": message.chat.id }, {"$set": {"_id": message.chat.id, "avisos" : avisos}}, upsert=True)
                    for sched in scheduler.queue:
                        sched_params = sched[3][1]
                        if sched_params["info"] == linea and sched_params["stop"] == int(parada) and sched_params["time"] == int(aviso):
                            logging.debug("Borramos del scheduler el aviso")
                            scheduler.cancel(sched)
                        break
                    break
    logging.debug("Aviso borrado correctamente")
    if send_message:
        bot.send_message(message.chat.id, "Aviso eliminado")
                    
def borrar_mensaje(message):
    logging.info("Borramos mensaje")
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception as e:
        logging.info("No se ha podido borrar el mensaje")

def get_line_info_from_hash(stop, search_hash):
    buses = vitrasa.get_stop_estimates(stop)
    seen = dict()
    [x for x in buses if x.line+x.route not in seen.keys() and not seen.update({x.line+x.route: x.to_dict()})]
    buses = seen.values()

    line_info = None
    for bus in buses:
        m = hashlib.md5()
        m.update(bus["line"].encode("utf-8") + bus["route"].encode("utf-8"))
        line_hash = m.hexdigest()[:5]
        if line_hash == search_hash:
            line_info = bus
            break;
        
    return line_info
        
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    logging.info("Comando {}".format(message.text))
    logging.debug("Mensaje recibido de {} - {}".format(message.chat.id, (message.chat.username and message.chat.username) or (message.chat.first_name and message.chat.first_name)))

    markup = types.InlineKeyboardMarkup()
    itembtna = types.InlineKeyboardButton('{} Paradas favoritas'.format((u'\U00002B50')), callback_data='{"paradas_favoritas": {"user" : ' + str(message.chat.id) + '}}')
    itembtnb = types.InlineKeyboardButton('{} Paradas cercanas'.format((u'\U0001F50E')), switch_inline_query_current_chat="")
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
    logging.debug("Mensaje recibido de {} - {}".format(message.chat.id, (message.chat.username and message.chat.username) or (message.chat.first_name and message.chat.first_name)))
    bot.send_message(message.chat.id, "No estamos afiliados a Vitrasa\nCopyright 2019.\nCodigo fuente: https://github.com/dpeite/VitrasaTelegramBot", disable_web_page_preview=True)

@bot.message_handler(commands=['status'])
def status(message):
    logging.info("Comando status")
    logging.debug("Mensaje recibido de {} - {}".format(message.chat.id, (message.chat.username and message.chat.username) or (message.chat.first_name and message.chat.first_name)))
    try:
        vitrasa.get_stop(14264)
        bot.send_message(message.chat.id, "{} Bot\n{} Conexión con Vitrasa".format((u'\u2705'),(u'\u2705')))
    except Exception:
        bot.send_message(message.chat.id, "{} Bot\n{} Conexión con Vitrasa".format((u'\u2705'), (u'\u274C')))

@bot.message_handler(commands=['avisos'])
def avisos(message):
    logging.info("Comando avisos")
    logging.debug("Mensaje recibido de {} - {}".format(message.chat.id, (message.chat.username and message.chat.username) or (message.chat.first_name and message.chat.first_name)))

    #TODO Borrar avisos si ha pasado mas de 2 horas desde su creación
    user_data = db.users.find_one({'_id': message.chat.id})
    avisos = {}
    if user_data and "avisos" in user_data:
        avisos = user_data["avisos"]

    markup = types.InlineKeyboardMarkup()
    update_db = False
    for linea in avisos.keys():
        for parada in  avisos[linea].keys():
            for aviso in avisos[linea][parada].keys():
                info_aviso = avisos[linea][parada][aviso]
                time_created = datetime.datetime.strptime(info_aviso["time_created"], '%Y-%m-%d %H:%M')
                # Si han pasado más de dos horas no mostramos los avisos
                if (datetime.datetime.now(tz=tz) - datetime.timedelta(hours=2)) < tz.localize(time_created):
                    m = hashlib.md5()
                    m.update(linea.encode("utf-8")+parada.encode("utf-8")+aviso.encode("utf-8"))
                    
                    itembtna = types.InlineKeyboardButton('{} min - {} {} - {}'.format( aviso, info_aviso["linea"], info_aviso["ruta"], info_aviso["parada_name"]), callback_data='{"mostrar_aviso": {"id" : "' + m.hexdigest()[:5] + '"}}')
                    markup.row(itembtna)
                else:
                    logging.debug("Han pasado mas de dos horas, asi que no mostramos este aviso")
                    del  avisos[linea][parada][aviso]
                    update_db = True

    if update_db:
        # Si usamos pymongolab descomentar esta query y comentar la siguiente
        # db.users.update({"_id": info["user"] }, {"$set": {"_id": info["user"], "avisos" : avisos}}, upsert=True)
        db.users.update_one({"_id": message.chat.id }, {"$set": {"_id": message.chat.id, "avisos" : avisos}}, upsert=True)

            
    bot.send_message(message.chat.id, "Estos son los avisos que tienes guardados", reply_markup=markup)
        
@bot.message_handler(content_types=['text'])
def id_parada(message):
    logging.info("Recibida parada con id {}".format(message.text))
    logging.debug("Mensaje recibido de {} - {}".format(message.chat.id, (message.chat.username and message.chat.username) or (message.chat.first_name and message.chat.first_name)))
    
    test = db.users.find_one({'_id': message.from_user.id})
    # Si usamos pymongolab descomentar esta query y comentar la siguiente
    # db.users.update({"_id": message.from_user.id }, {"$set": {"_id":message.from_user.id, "username" : message.from_user.username}}, upsert=True)
    # db.users.update_one({"_id": message.from_user.id }, {"$set": {"_id":message.from_user.id, "username" : message.from_user.username}}, upsert=True)
    id = message.text
    if not id.isdigit():
        logging.debug("La parada introducida no es un numero")
        markup = types.InlineKeyboardMarkup()
        itembtna = types.InlineKeyboardButton('{} Paradas cercanas'.format((u'\U0001F50E')), switch_inline_query_current_chat="")
        itembtnb = types.InlineKeyboardButton('{} Paradas favoritas'.format((u'\U00002B50')), callback_data='{"paradas_favoritas": {"user" : ' + str(message.from_user.id) + '}}')
        markup.row(itembtnb, itembtna)
        text = "Introduce un número de parada, envíame tu ubicación o busca las paradas más próximas"
        bot.send_message(message.chat.id, text, reply_markup=markup)
        return
    obtener_parada(message, int(id))

@bot.message_handler(content_types=['location'])
def coordenadas_parada(message):
    lat =  message.location.latitude
    lon =  message.location.longitude

    logging.info("Recibidas coordenadas lat {}, lon {}".format(lat, lon))
    logging.debug("Mensaje recibido de {} - {}".format(message.chat.id, (message.chat.username and message.chat.username) or (message.chat.first_name and message.chat.first_name)))
    
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
        
bot.polling(none_stop=True)
