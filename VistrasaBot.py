# -*- coding: utf-8 -*-   
import telebot
from paradas import Paradas
from peticion import peticion

token = ""
bot = telebot.TeleBot(token)

def consultar_info_parada(parada, message):
    if not parada:
        bot.send_message(message.chat.id, "La parada no existe")
        return
    coord = parada[0]
    lat = coord[1].strip()
    lon = coord[0].strip()
    bot.send_message(message.chat.id, "Consultando al servidor...")
    info = peticion(lat,lon)
    text = "Parada {} - ".format(parada[2]) + parada[1]+ "\n"
    for ele in info:
        if len(ele) == 1:
            text = ele[0] + " en esta parada"
        else:
            text +=  ele[0] + " " +  ele[1] + " " + ele[2] + "\n"
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.send_message(message.chat.id, "Bienvenido, introduce el numero de la parada que quieras consultar o envia tu ubicacion para localizar la parada más proxima\n" \
                     "Actualmente hay {} paradas en el sistema".format(paradas.get_num_paradas()))

@bot.message_handler(content_types=['text'])
def id_parada(message):
    id = message.text
    parada = paradas.get_parada_by_id(id)
    consultar_info_parada(parada, message)
    
@bot.message_handler(content_types=['location'])
def coordenadas_parada(message):
    lat =  message.location.latitude
    lon =  message.location.longitude
    parada = paradas.get_parada_by_coord(lat, lon)
    consultar_info_parada(parada, message)    
    
paradas = Paradas()
bot.polling(none_stop=True)
    
# while True:
#     try:
#         bot.polling(none_stop=True)
#     except Exception:
#         time.sleep(5)
