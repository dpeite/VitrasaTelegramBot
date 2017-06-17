# VitrasaTelegramBot
Bot de Telegram para consultar el tiempo aproximado de llegada de los autobuses en la ciudad de Vigo.

## Uso:
**Actualmente se encuentra en fase Beta,** la mayoría del tiempo el bot se encontrará desconectado y no responderá a los mensajes o lo hará con bastante retraso.
1. Agregar el bot a Telegram pulsando [aquí](https://telegram.me/vitrasabot).
2. Escribir en el chat el numero de la parada o enviar la ubicación al bot.

## Instalación:
Hace uso de [Requests](http://docs.python-requests.org/en/master/) para las peticiones HTTP, [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/) para parsear la web y [pyTelegramBotAPI](https://github.com/eternnoir/pyTelegramBotAPI) para usar telegram.

```bash
pip install -r requirements.txt
python VitrasaTelegramBot.py
```
