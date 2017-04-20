#!/usr/bin/env python3

import argparse
import configparser
from datetime import datetime
import logging

from telegram.ext import Updater, CommandHandler
from pyhessian.client import HessianProxy


logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO, filename="bot.log")
logger = logging.getLogger(__name__)


def read_config(filename):
    """
    Liest eine Konfigurationsdatei ein und gibt Token und Abfahrtsorte zurück.

    Parameters
    ----------
    filename: str
        Dateiname der Konfigurationsdatei


    Returns
    -------
    token: str
        Telegram Token für den Bot

    """
    cp = configparser.ConfigParser()
    cp.read(filename)
    token = cp["AUTHENTICATION"]["token"]
    ids = [int(id) for id in cp["AUTHENTICATION"]["allowed_ids"].split(",")]

    locations = cp["LOCATIONS"]
    workplace, direction_workplace = locations["workplace"], locations["direction_workplace"]
    home, direction_home = locations["home"], locations["direction_home"]

    return dict(token=token, home=home, direction_home=direction_home.split(","),
                workplace=workplace, direction_workplace=direction_workplace.split(","),
                ids=ids)


def check_id(func):
    def new_func(self, bot, update):
        requesting_id = update.message.chat_id
        if self.allowed_ids and requesting_id in self.allowed_ids:
            logger.debug("Found ID in ID_LIST")
            func(self, bot, update)
        else:
            chat = update.message.chat
            logger.warning("User {} {} with id {} not in id list".format(chat.first_name,
                                                                         chat.last_name,
                                                                         requesting_id))
    return new_func


class HavagBot:
    def __init__(self,
                 home_address,
                 direction_home,
                 workplace,
                 direction_workplace,
                 allowed_ids=None):
        """
        Parameters
        ----------
        home_address: str
            Die Heimathaltestelle
        direction_home: str
            Die Endhaltestellen der Linien Richtung Heimat
        workplace: str
            Die Arbeitshaltestelle
        direction_workplace: str
            Die Endhaltestellen der Linien Richtung Arbeit
        allowed_ids:
            Telegram IDs, denen geantwortet werden soll
        """
        self.home_address = home_address
        self.direction_home = direction_home
        self.workplace = workplace
        self.direction_workplace = direction_workplace
        havag_url = "http://83.221.237.42:20010/init/rtpi"
        self.hess_prox = HessianProxy(havag_url)
        self.allowed_ids = allowed_ids

    def get_connections(self, start, direction):
        now = datetime.now()
        connections = []
        for tram, destination, time, *rest in self.hess_prox.getDeparturesForStop(start):
            time = datetime.strptime(time, "%Y.%m.%d.%H:%M:%S")
            delta = divmod((time - now).seconds, 60)
            timestr = time.strftime("%H:%M")
            if destination  in direction:
                connections.append(dict(tram=tram, destination=destination,
                                        time=timestr, delta=delta))
        return connections

    def get_next_connection(self, connections):
        return min(connections, key=lambda x: x["delta"])

    def return_connection_str(self, connection):
        if connection["delta"][0] < 1:
            connection["delta"] = "< 1"
        else:
            connection["delta"] = connection["delta"][0]
        return "{tram:} -> {destination:} @ {time:} ({delta:} Min.)".format(**connection)


    @check_id
    def start(self, bot, update):
        bot.sendMessage(chat_id=update.message.chat_id, text="Hello")

    @check_id
    def home(self, bot, update):
        connections = self.get_connections(self.workplace, self.direction_home)
        try:
            next_connection = self.get_next_connection(connections)
        except ValueError:
            msg = "Keine Verbindung gefunden."
        else:
            msg = self.return_connection_str(next_connection)
        bot.sendMessage(chat_id=update.message.chat_id, text=msg)

    @check_id
    def work(self, bot, update):
        connections = self.get_connections(self.home_address, self.direction_workplace)
        try:
            next_connection = self.get_next_connection(connections)
        except ValueError:
            msg = "Keine Verbindung gefunden."
        else:
            msg = self.return_connection_str(next_connection)
        bot.sendMessage(chat_id=update.message.chat_id, text=msg)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("configfile", help="Name des ConfigFiles")
    args = parser.parse_args()

    config = read_config(args.configfile)
    havagbot = HavagBot(
        config["home"],
        config["direction_home"],
        config["workplace"],
        config["direction_workplace"],
        allowed_ids=config["ids"])

    updater = Updater(token=config["token"])
    dispatcher = updater.dispatcher

    start_handler = CommandHandler("start", havagbot.start)
    dispatcher.add_handler(start_handler)

    home_handler = CommandHandler("home", havagbot.home)
    dispatcher.add_handler(home_handler)

    work_handler = CommandHandler("work", havagbot.work)
    dispatcher.add_handler(work_handler)

    updater.start_polling()


if __name__ == "__main__":
    main()
