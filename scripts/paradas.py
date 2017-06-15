# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup
import re

url = "http://rutasgt.intecoingenieria.com/gmaps/107.txt"
response = requests.get(url).content
soup = BeautifulSoup(response, 'html.parser')
paradas_coord = {}
paradas_id = {}
root = soup.find_all("placemark")
cont = 0
for childs in root:
    coord = str(childs.find("coordinates").string.strip().encode("utf8"))
    name = str(childs.find("name").string.strip().encode("utf8"))
    desc = str(childs.find("description").encode("utf8"))
    id_parada =  re.search(r"<description> <\!\[CDATA\[N\&\#186\;: (.*?)\.", desc).group(1)
    paradas_coord[coord] = [id_parada, name]
    paradas_id[id_parada] =[coord, name]
    cont += 1
