# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup
import re

class Paradas(object):
    def __init__(self):
        print "Arrancando modulo paradas..."
        self.url = "http://rutasgt.intecoingenieria.com/gmaps/107.txt"
        self.refresh_paradas()
        print "Modulo cargado"
        
    def refresh_paradas(self):
        print "Preguntando al servidor por las paradas..."
        response = requests.get(self.url).content
        soup = BeautifulSoup(response, 'html.parser')
        self.paradas_coord = {}
        self.paradas_id = {}
        self.cont = 0
        root = soup.find_all("placemark")

        for childs in root:
            coord = str(childs.find("coordinates").string.strip().encode("utf8"))
            name = str(childs.find("name").string.strip().encode("utf8"))
            desc = str(childs.find("description").encode("utf8"))
            id_parada =  re.search(r"<description> <\!\[CDATA\[N\&\#186\;: (.*?)\.", desc).group(1)
            self.paradas_coord[coord] = [id_parada, name]
            self.paradas_id[id_parada] =[coord, name]
            self.cont += 1
        print "El servidor ha respondido con las paradas"

    def get_paradas_by_id(self):
        return self.paradas_id

    def get_paradas_by_coord(self):
        return self.paradas_coord

    def get_num_paradas(self):
        return self.cont

    def get_parada_by_id(self, id):
        if id in self.paradas_id:
            return self.paradas_id[id]
        else:
            return "No existe la parada"

    def get_parada_by_coord(self, coord):
        return self.paradas_coord[coord]
