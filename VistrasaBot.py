import telebot
from paradas import Paradas
from peticion import peticion

token = "381479716:AAFGhzS1Dh0o7GCmILVeiOPrn-YZ4lTHvg4"
bot = telebot.TeleBot(token)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.send_message(message.chat.id, "Bienvenido, introduce el numero de la parada que quieras consultar")

@bot.message_handler(content_types=['text'])
def send_welcome(message):
    id = message.text
    parada = paradas.get_parada_by_id(id)
    coord = parada[0].split(",")
    lat = coord[1].strip()
    lon = coord[0].strip()
    bot.send_message(message.chat.id, "Consultando al servidor...")
    info = peticion(lat,lon)
    text = parada[1] + "\n"
    for ele in info:
        text +=  ele[0] + " " +  ele[1] + " " + ele[2] + "\n"
    bot.send_message(message.chat.id, text)
    
@bot.message_handler(content_types=['location'])
def send_welcome(message):
    bot.send_message(message.chat.id, "Location ACK")


paradas = Paradas()
bot.polling(none_stop=True)

# while True:
#     try:
#         bot.polling(none_stop=True)
#     except Exception:
#         time.sleep(5)
