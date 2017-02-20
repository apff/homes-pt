#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import requests
from bs4 import BeautifulSoup as Soup
import datetime
import json


CASA_SAPO_URL_ROOT = "https://casa.sapo.pt"
CASA_SAPO_URL_BASE = "https://casa.sapo.pt/Venda/Lisboa/?sa=11&gp=%d&lau=%d&mpr=%s&or=10&pn=%d"

default_max_price = 720000
default_min_area = 130
default_min_rooms = 3 # T2
default_max_rooms = 7 # >=T6 (max)



class HouseListing(object):
    def __init__(self, url, date_added, location, price, property_type, rooms, state, useful_area, gross_area=None):
        self.url = url
        self.date_added = date_added
        self.location = location
        self.price = price
        self.property_type = property_type
        self.rooms = rooms
        self.state = state
        self.useful_area = useful_area
        self.gross_area = gross_area if gross_area and gross_area != "-" else useful_area
        self.complete_entry = False
        self.id = "TODO" #TODO

    def __str__(self):
        description =  self.property_type + ' ' + self.rooms \
                    + "\t(" +str(self.date_added) + ")" \
                    + ":\n------------------------------\n" \
                    + "Location: " + self.location +"\n" \
                    + "Area: " + str(self.useful_area) + "m2\n" \
                    + "Price: " + str(self.price / 1000) + "K\n" \
                    + str(self.url)

        return description

    def __eq__(self, other):
        if type(other) == str:
            return self.url == other
        return self.url == other.url


    def fetch_info(self):
        pass
        # res = requests.get(self.url)

        # if res.status_code != requests.codes.ok:
        #   print "ERROR: Failed to fetch house listing defails - ", res.status_code
        #   res.raise_for_status()
        #   return 1
        
        # self.complete_entry = True



HOUSE_SEARCHER_DATA_PATH = "~/.house_searcher_data"

class HouseSearcher(object):
    def __init__(self, max_price=default_max_price, min_area=default_min_area, min_rooms=default_min_rooms, max_rooms=default_max_rooms):
        self.max_price = max_price
        self.min_area = min_area
        self.min_rooms = min_rooms
        self.max_rooms = max_rooms
        self.house_listings = []

        self.load_data()
        # print "Loaded %d listings" % (len(self.house_listings))


    def build_query_url(self, page_number=1, max_price=default_max_price):
        return CASA_SAPO_URL_BASE % (self.max_price, self.min_area, ",".join([str(x) for x in xrange(8)][self.min_rooms:self.max_rooms+1]), page_number)


    def save_data(self):
        all_entries_map = {"entries":[]}
        for entry in self.house_listings:
            entry_map = {
                    "date" : str(entry.date_added),
                    "loc" : entry.location,
                    "p" : entry.price,
                    "t" : entry.property_type,
                    "T" : entry.rooms,
                    "st" : entry.state,
                    "UA" : entry.useful_area,
                    "GA" : entry.gross_area,
                    "url" : entry.url 
            }
            all_entries_map["entries"].append(entry_map)
        
        base_dir = os.path.expanduser(HOUSE_SEARCHER_DATA_PATH)
        save_filepath = os.path.join(base_dir, "listings.json")
        
        if not os.path.isdir(base_dir):
            os.makedirs(base_dir)

        with open(save_filepath, 'w') as savefile:
            savefile.write(json.dumps(all_entries_map))


    def load_data(self):
        base_dir = os.path.expanduser(HOUSE_SEARCHER_DATA_PATH)
        savefiles = [os.path.join(base_dir, f) for f in os.listdir(base_dir)]
        
        for filepath in savefiles:
            with open(filepath) as saved_data_file:
                entries = json.load(saved_data_file)
                
                entries = entries["entries"]

                for entry in entries:
                    loaded_listing = HouseListing(entry["url"], datetime.datetime.strptime(entry["date"], "%Y-%m-%d").date(), entry["loc"], int(entry["p"]), entry["t"], entry["T"], entry["st"], int(entry["UA"]), int(entry["GA"]))

                    self.house_listings.append(loaded_listing)


    def process_casa_sapo_page(self, page_number=1):
        status = 0
        new_entries_count = 0
        last_entry_date = 0

        query_url = self.build_query_url(page_number)
        res = requests.get(query_url)

        if res.status_code != requests.codes.ok:
          print "ERROR: Failed to query casa.sapo - ", res.status_code
          res.raise_for_status()
          return (1,0,0)

        html_content = res.content    
        # with open(os.path.join(os.path.dirname(__file__),'../test-samples/test_sapo.html')) as test_file:
        #     html_content = test_file.read()

        parsed_html = Soup(html_content, "html.parser")

        page_results = parsed_html.select('div[class="searchResultProperty"]')
        # print len(page_results), "results\n"
        for result in page_results:
            try:
                date_added = result.select('div[class="searchPropertyDate"]')[0].getText().split(" ")[-1].strip()
                date_added = date_added.split("/")
                date_added = datetime.date(int(date_added[2]), int(date_added[1]), int(date_added[0]))

                location = result.select('p[class="searchPropertyLocation"]')[0].getText().strip().encode('utf-8')
                location = location.replace("ã", "a").replace("ç","c").replace("õ","o").replace("à","a").replace("á","a").replace("â","a").replace("é","e").replace("í","i").replace("ó","o").replace("ú","u").encode("ascii","replace")

                result_info = result.select('div[class="searchPropertyInfo"]')[0]
                info_divs = result_info.select('div')

                details = {}
                for info in info_divs:
                    info_p = info.select('p')
                    key = info_p[0].getText().lower().encode('utf-8').replace("á","a").replace("ú","u")
                    value = info_p[1].getText()
                    details[key] = value

                state = details['estado']
                useful_area =int(details['area util'].split('m')[0])
                gross_area =int(details['area bruta'].split('m')[0]) if details['area bruta'] != "-" else useful_area

                price = result.select('div[class="searchPropertyPrice"]')[0].select('span')[0].getText().encode("ascii","replace").replace("?","")
                price = int(price)

                property_class = result.select('p[class="searchPropertyTitle"]')[0].select('span')[0].getText()
                property_type, rooms = property_class.split(" ")

                url = CASA_SAPO_URL_ROOT + result.select('a[class="photoLayer"]')[0].get('href').split("?")[0]

                house_listing = HouseListing(url, date_added, location, price, property_type, rooms, state, useful_area, gross_area)
                if not house_listing in self.house_listings:
                    print "NEW!"
                    print house_listing,"\n"
                    new_entries_count +=1
                    # house_listing.fetch_info() #TODO: 
                    self.house_listings.append(house_listing)
            
            except Exception, e:
                print "ERROR: Failed to parse entry", e

        last_entry_date = self.house_listings[-1].date_added
        
        return (status, new_entries_count, last_entry_date)

    def query_casa_sapo(self):
        (status, new_entries_count, last_entry_date) = self.process_casa_sapo_page()

        print (status, new_entries_count, last_entry_date)
        print "total listings:", len(self.house_listings)
        self.save_data()



def main(args) :
    house_searcher = HouseSearcher(max_price=720000, min_area=130)
    house_searcher.query_casa_sapo()


if __name__ == '__main__':
    main(sys.argv)