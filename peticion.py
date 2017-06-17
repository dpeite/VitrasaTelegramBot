# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
import re


def peticion(lat, lon):
    url = "http://rutas.vitrasa.es/DisplayParadas.aspx?LatitudParada="+lat+"&LongitudParada="+lon
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}

    s = requests.Session()
    s.get("http://rutas.vitrasa.es/lineas.aspx", headers=headers)
    response = s.get(url, headers=headers)
    data =  response.content
    data2 = re.search(r"infoWindowParada.setContent\('(.*?)'\);", data).group(1)
    soup = BeautifulSoup(data2, 'html.parser')
    table_body = soup.find("table")
    rows = table_body.find_all("tr")
    data = []

    for row in rows:
        cols = row.find_all("td")
        cols = [ele.text.strip() for ele in cols]
        data.append([ele for ele in cols if ele])

    return data
