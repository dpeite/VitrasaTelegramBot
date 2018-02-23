# -*- coding: utf-8 -*-   
import telebot
from api import vitrasa

token = ""
bot = telebot.TeleBot(token)


def obtener_parada(message, id):
    try:
        buses = vitrasa.get_stop_estimates(id)
        buses = sorted(buses, key=lambda bus: bus.minutes)
        buses = [bus.to_dict() for bus in buses]

        parada = vitrasa.get_stop(id).to_dict()
        print parada
        print buses
        texto = "*Parada Nº {} - {}*".format(parada["number"], parada["name"].encode("utf-8"))
        texto += "\n`{:2} {:2}{:20}\n---------------------------`".format("Min", "L", "Ruta")
        for bus in buses:
            print bus["line"], bus["route"].encode("utf-8"), bus["minutes"]
            texto += "\n`{:2} {:2} {:20}`".format(bus["minutes"], bus["line"], bus["route"].encode("utf-8"))
                                          
        bot.send_message(message.chat.id, texto, parse_mode="Markdown")

        
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
         
bot.polling(none_stop=True)
