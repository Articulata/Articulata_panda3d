import sys
import logging
from argparse import ArgumentParser

from panda3d.core import *

ConfigVariableString("window-type", "none").setValue("none")
from direct.showbase.ShowBase import ShowBase
from direct.task.TaskManagerGlobal import taskMgr
from direct.distributed.PyDatagramIterator import PyDatagramIterator
from direct.distributed.PyDatagram import PyDatagram
from direct.showbase.DirectObject import DirectObject
from direct.task.Task import Task


__author__ = "Adam Vandervorst"
__email__ = "adam.vandervorst@articulatagame.com"
__status__ = "Internal Alpha"

parser = ArgumentParser()
parser.add_argument("--debug", help="Set debug logging level")
parser.add_argument("--mp", help="Allow Multiplayer", default=False)
args = parser.parse_args()

logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")

base = ShowBase()


def find_player(lst, attr, eq):
    assert lst, "List can not be empty"
    assert hasattr(lst[0], attr), "Instance has no attribute " + attr
    return [cls for cls in lst if cls.__dict__[attr] == eq][0]
        

class Server(QueuedConnectionManager):
    """Handles new connections and the incomming of packages"""
    def __init__(self, p, b):
        self.cManager = QueuedConnectionManager()
        self.cListener = QueuedConnectionListener(self.cManager, 0)
        self.cReader = QueuedConnectionReader(self.cManager, 0)
        self.cWriter = ConnectionWriter(self.cManager, 0)
        self.port = p
        self.backlog = b
        self.socket = self.cManager.openTCPServerRendezvous(self.port, self.backlog)
        self.cListener.addConnection(self.socket)
        self.player_list = []
        self.iterator = None
        self.num_count = self.active_players = self.Δt_update = self.Δt = 0

    def reader_polling_task(self, arg):
        if self.cReader.dataAvailable():
            datagram = NetDatagram()

            if self.cReader.getData(datagram):
                self.process_data(datagram.getConnection(), datagram)

        return Task.cont

    def listener_polling_task(self, arg):
        if self.cListener.newConnectionAvailable():
            rendezvous = PointerToConnection()
            net_address = NetAddress()
            new_connection = PointerToConnection()
            if self.cListener.getNewConnection(rendezvous, net_address, new_connection):
                self.active_players += 1
                new_connection = new_connection.p()
                self.player_list.append(player(self.num_count))
                find_player(self.player_list, "player_id", self.num_count).conn_id = new_connection
                logging.debug(self.active_players)
                self.initialize_player()
                self.num_count += 1
                self.cReader.addConnection(new_connection)  # Begin reading connection
                logging.info('connection received')
        return Task.cont

    def initialize_player(self):
        conn = self.player_list[-1].conn_id

        datagram = PyDatagram()
        datagram.addString("init")
        newest = self.player_list[-1].player_id
        datagram.addUint8(newest)
        logging.debug(f"{self.active_players} players and {newest} is the newest player")
        datagram.addUint8(self.active_players)

        if len(self.player_list) > 1:
            for k in self.player_list:
                datagram.addString(k.username)
                datagram.addFloat64(k.pos_and_or['x'])
                datagram.addFloat64(k.pos_and_or['y'])
                datagram.addFloat64(k.pos_and_or['z'])

        self.cWriter.send(datagram, conn)

    def update_positions(self, data):  # send
        self.Δt = globalClock.getDt()
        self.Δt_update += self.Δt
        if self.Δt_update > 0.05:
            if self.active_players > 1:
                datagram = PyDatagram()
                datagram.addString("update")
                datagram.addInt8(self.active_players)

                for p in self.player_list:
                    datagram.addString(p.username)
                    datagram.addFloat64(p.pos_and_or['x'])
                    datagram.addFloat64(p.pos_and_or['y'])
                    datagram.addFloat64(p.pos_and_or['z'])
                    datagram.addFloat64(p.pos_and_or['h'])
                    datagram.addFloat64(p.pos_and_or['p'])
                    datagram.addFloat64(p.pos_and_or['r'])

                for p in self.player_list:
                    self.cWriter.send(datagram, p.conn_id)
            self.Δt_update = 0
        return Task.cont

    def update_chat(self, msg):
        datagram = PyDatagram()

        datagram.addString("chat")
        datagram.addString(msg)

        logging.info(f"{msg}")  # TODO make this useful
        for p in self.player_list:
            self.cWriter.send(datagram, p.conn_id)

    def process_data(self, connection, datagram):
        self.iterator = PyDatagramIterator(datagram)
        msg_type = self.iterator.getString()

        if msg_type == "position":
            self.process_position(connection)
        elif msg_type == "chat":
            self.update_chat(self.iterator.getString())
        elif msg_type == "introduce":
            username = self.iterator.getString()
            logging.info(f"User {username} introduced himself")
            cls = find_player(self.player_list, "conn_id", connection)
            cls.username = username
        elif msg_type == "quit":
            self.process_quit()

    def process_position(self, connection):
        it = self.iterator
        pos_and_or = find_player(self.player_list, "conn_id", connection).pos_and_or
        pos_and_or['x'] = it.getFloat64()
        pos_and_or['y'] = it.getFloat64()
        pos_and_or['z'] = it.getFloat64()
        pos_and_or['h'] = it.getFloat64()
        pos_and_or['p'] = it.getFloat64()
        pos_and_or['r'] = it.getFloat64()

    def process_quit(self):
        logging.debug("Player has quit")
        self.active_players -= 1

        player_num = self.iterator.getInt8()
        player_cls = find_player(self.player_list, "player_id", player_num)
        player_id = self.player_list.index(player_cls)
        player_name = player_cls.username
        del self.player_list[player_id]

        datagram = PyDatagram()
        datagram.addString("remove")
        datagram.addString(player_name)

        for p in self.player_list:
            self.cWriter.send(datagram, p.conn_id)

        logging.info(f"Player {player_name} has left the game")


class player(DirectObject):
    def __init__(self, player_id):
        self.player_id = player_id
        self.conn_id = 0
        self.username = ""
        self.pos_and_or = {'x': 0, 'y': 0, 'z': 0, 'h': 0, 'p': 0, 'r': 0}
        self.moving = False  # TODO


server = Server(9415, 1000)

taskMgr.add(server.listener_polling_task, "Poll the connection listener")
taskMgr.add(server.reader_polling_task, "Poll the connection reader")
if args.mp:
    taskMgr.add(server.update_positions, "Update Every Player", extraArgs=[None])

logging.info("started")
base.run()
