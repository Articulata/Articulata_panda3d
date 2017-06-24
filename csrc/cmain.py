from time import time
import sys
import logging
from argparse import ArgumentParser
import atexit

from direct.task import Task
from direct.showbase.ShowBase import ShowBase
from panda3d.core import *
from direct.showbase.DirectObject import DirectObject
from direct.distributed.PyDatagram import PyDatagram
from direct.distributed.PyDatagramIterator import PyDatagramIterator
from direct.actor.Actor import Actor
from direct.task.Task import Task
from direct.task.TaskManagerGlobal import taskMgr
from direct.gui.DirectGui import *

from assets import map_objects
from helper import iter_class_attr

__author__ = "Adam Vandervorst"
__email__ = "adam.vandervorst@articulatagame.com"
__status__ = "Internal Alpha"

parser = ArgumentParser()
parser.add_argument("--debug", help="Set debug logging level")
parser.add_argument("--ip", help="Server ip", default="localhost")
parser.add_argument("--port", help="Server port", default=9415)
args = parser.parse_args()

logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")

base = ShowBase()


class Client(DirectObject):
    """Handles connection and routes new datagrams"""
    def __init__(self, p, i):
        self.cManager = QueuedConnectionManager()  # Manages connections
        self.cReader = QueuedConnectionReader(self.cManager, 0)  # Reads incoming Data
        self.cWriter = ConnectionWriter(self.cManager, 0)  # Sends Data
        self.port = p  # Server's port
        self.ip = i  # server's ip
        self.conn = self.cManager.openTCPClientConnection(self.ip, self.port, 3000)
        if self.conn:
            self.cReader.addConnection(self.conn)  # receive messages from server
        else:
            logging.warning('connection failed')

    def data_available(self, arg):
        # this function checks to see if there is any data from the server
        if self.cReader.dataAvailable():
            datagram = NetDatagram()  # catch the incoming data in this instance
            # Check the return value; if we were threaded, someone else could have
            # snagged this data before we did
            if self.cReader.getData(datagram):
                player_reg.process_data(datagram)
                datagram.clear()
        return Task.cont


class Terrain(GeoMipTerrain):
    """Very temporary class, just so we have something below our feet"""
    def __init__(self):
        self.terrain = GeoMipTerrain("assets/mySimpleTerrain")
        self.terrain.setHeightfield(Filename("assets/Heightmap.png"))
        self.terrain.setColorMap(Filename("assets/terrain.bmp"))
        # myTexture = loader.loadTexture("terrain.bmp") #pjb UNcomment this line out if you want to set texture directly
        self.terrain.setBlockSize(32)
        self.terrain.setBruteforce(True)
        # self.terrain.setNear(40)
        # self.terrain.setFar(100)
        self.terrain.setFocalPoint(base.camera)
        self.terrain.getRoot().setSz(100)
        self.time = 0
        self.Dt = 0
        self.terrain.getRoot().reparentTo(base.render)
        self.terrain.generate()
        # self.terrain.getRoot().setTexture(myTexture) #pjb UNcomment this line out if you want to set texture directly
        # taskMgr.doMethodLater(5, self.updateTerrain, 'Update the Terrain')
        # taskMgr.add(self.updateTerrain, "update")

    def updateTerrain(self, task):
        self.Dt = globalClock.getDt()
        self.time += self.Dt
        if (self.time > 5):
            self.terrain.update()
            self.time = 0
        return Task.again


class PlayerReg(DirectObject):
    """Regulate player positions"""
    def __init__(self):
        self.player_dict = {}
        self.players = []
        self.num_players = 0
        self.type = ""

    def process_data(self, datagram):
        # process received data
        iterator = PyDatagramIterator(datagram)
        self.type = iterator.getString()

        if self.type == "init":
            logging.info("initializing")
            me.player_id = iterator.getUint8()
            self.num_players = iterator.getUint8()

            if self.num_players > 1:
                for _ in range(self.num_players):
                    username = iterator.getString()

                    self.player_dict[username] = Player()
                    self.player_dict[username].username = username
                    self.player_dict[username].load()
                    self.player_dict[username].position['x'] = iterator.getFloat64()
                    self.player_dict[username].position['y'] = iterator.getFloat64()
                    self.player_dict[username].position['z'] = iterator.getFloat64()
                    logging.info(f"player '{username}' initialized")
            datagram = PyDatagram()
            datagram.addString("introduce")
            datagram.addString(me.username)
            world_client.cWriter.send(datagram, world_client.conn)
            logging.debug("Send introduction")

        elif self.type == "update":
            self.num_players = iterator.getInt8()

            for _ in range(self.num_players):
                username = iterator.getString()

                if username == me.username:
                    for i in range(6):
                        iterator.getFloat64()  # TODO: Implement check
                    continue

                if username not in self.player_dict.keys():
                    self.player_dict[username] = Player(username)
                    self.player_dict[username].load()

                self.player_dict[username].position['x'] = iterator.getFloat64()
                self.player_dict[username].position['y'] = iterator.getFloat64()
                self.player_dict[username].position['z'] = iterator.getFloat64()
                self.player_dict[username].position['h'] = iterator.getFloat64()
                self.player_dict[username].position['p'] = iterator.getFloat64()
                self.player_dict[username].position['r'] = iterator.getFloat64()

        elif self.type == "remove":
            username = iterator.getString()
            self.player_dict[username].model.removeNode()
            del self.player_dict[username]

        elif self.type == "chat":
            self.text = iterator.getString()
            chat_reg.setText(self.text)

    def update_players(self, arg):
        if self.num_players != 0:
            for k in self.player_dict.keys():
                # As long as the player is not the client put it where the server says
                if k != me.username:
                    self.player_dict[k].model.setPosHpr(self.player_dict[k].position['x'],
                                                        self.player_dict[k].position['y'],
                                                        self.player_dict[k].position['z'],
                                                        self.player_dict[k].position['h'],
                                                        self.player_dict[k].position['p'],
                                                        self.player_dict[k].position['r'])
        return Task.cont


class Me(DirectObject):
    """Testing self controlled player, can be build upon"""
    def __init__(self):
        self.model = Actor("assets/models/ninja", {"walk": "assets/models/ninja"})
        self.actorHead = self.model.exposeJoint(None, 'modelRoot', 'Joint8')
        # self.model.setScale(4)
        self.username = input("Input username: \n")
        self.player_id = None
        self.Dt_update = self.Dt = 0
        self.model.reparentTo(base.render)
        self.model.setScale(0.5)
        self.moving = False
        self.AnimControl = self.model.getAnimControl('walk')
        self.AnimControl.setPlayRate(0.05)
        self.model.setBlend(frameBlend=1)
        self.model.setPos(244, 188, 0)
        # STORE TERRAIN SCALE FOR LATER USE#
        self.terrainScale = terrain.terrain.getRoot().getSz()
        base.camera.reparentTo(self.model)
        self.camDummy = self.model.attachNewNode("camDummy")
        self.camDummy.setZ(5)

    def move(self, arg):
        # self.meTerrainHeight = terrainClass.terrain.getElevation(self.model.getX(),self.model.getY()) * self.terrainScale
        # self.camTerrainHeight = terrainClass.terrain.getElevation(camera.getX(),camera.getY()) * self.terrainScale
        self.Dt = globalClock.getDt()
        # base.camera.lookAt(self.actorHead)
        if keys.keyMap["left"] != 0:
            self.model.setH(self.model.getH() + self.Dt * 300)
            logging.debug(f"{self.model.getY()}, {self.model.getX()}")
        if keys.keyMap["right"] != 0:
            self.model.setH(self.model.getH() - self.Dt * 300)
        if keys.keyMap["forward"] != 0:
            self.model.setY(self.model, (self.Dt * 40))
        if keys.keyMap["back"] != 0:
            self.model.setY(self.model, -(self.Dt * 40))

        if (keys.keyMap["forward"] != 0) or \
                (keys.keyMap["left"] != 0) or \
                (keys.keyMap["right"] != 0):
            if self.moving is False:
                self.model.loop("walk", fromFrame=1, toFrame=11)
                self.moving = True
        else:
            if self.moving:
                self.model.stop()
                self.model.pose("walk", 5)
                self.moving = False

        self.meTerrainHeight = terrain.terrain.getElevation(self.model.getX(),
                                                            self.model.getY()) * self.terrainScale
        self.model.setZ(self.meTerrainHeight)

        # base.camera.reparentTo(self.model)
        base.camera.lookAt(self.camDummy)
        base.camLens.setNear(.1)

        if keys.keyMap["cam"] == 1:
            # base.camera.setZ(5)
            # base.camera.setY(1)
            base.disableMouse()
            base.camera.setPosHpr(0, 2, 5, 0, 0, 0)

        elif keys.keyMap["cam"] == 2:
            # base.camera.setPosHpr(0,-30,10,0,0,0)
            base.enableMouse()
        else:
            base.disableMouse()
            base.camera.setPosHpr(0, -30, 10, 0, 0, 0)
            # base.camera.setZ(10)
            # base.camera.setY(-30)
        return Task.cont


class World(DirectObject):
    """Let them know where you stand! Seriously, world-updates"""
    def __init__(self):
        self.Dt_update = self.Dt = 0

    def update_world(self, arg):
        self.Dt = globalClock.getDt()
        self.Dt_update += self.Dt
        if self.Dt_update > 0.05:
            datagram = PyDatagram()
            datagram.addString("position")
            datagram.addFloat64(me.model.getX())
            datagram.addFloat64(me.model.getY())
            datagram.addFloat64(me.model.getZ())
            datagram.addFloat64(me.model.getH())
            datagram.addFloat64(me.model.getP())
            datagram.addFloat64(me.model.getR())
            try:
                world_client.cWriter.send(datagram, world_client.conn)
            except:
                logging.info("No connection to the server. You are in stand alone mode.")
                return Task.done
            self.Dt_update = 0
        return Task.cont


class Keys(DirectObject):
    """Key binding construct"""
    def __init__(self):
        self.isTyping = False
        self.keyMap = {"left": 0, "right": 0, "forward": 0, "back": 0, "cam": 0, "autoRun": 0}
        self.accept("escape", sys.exit)
        self.accept("arrow_left", self.setKey, ["left", 1])
        self.accept("arrow_right", self.setKey, ["right", 1])
        self.accept("arrow_up", self.setKey, ["forward", 1])
        self.accept("arrow_down", self.setKey, ["back", 1])
        self.accept("arrow_left-up", self.setKey, ["left", 0])
        self.accept("arrow_right-up", self.setKey, ["right", 0])
        self.accept("arrow_up-up", self.setKey, ["forward", 0])
        self.accept("arrow_down-up", self.setKey, ["back", 0])
        self.accept("c", self.toggleCam)
        self.accept(".", self.autoRun)
        # self.accept("a", base.oobe)

    def setKey(self, key, value):
        if not self.isTyping:
            self.keyMap[key] = value

    def autoRun(self):
        if not self.keyMap["autoRun"]:
            self.setKey("autoRun", 1)
            self.setKey("forward", 1)
        else:
            self.setKey("autoRun", 0)
            self.setKey("forward", 0)

    def toggleCam(self):
        if self.keyMap["cam"] == 1:
            self.setKey("cam", 2)
        elif self.keyMap["cam"] == 0:
            self.setKey("cam", 1)
        else:
            self.setKey("cam", 0)


class Player(DirectObject):
    """Player base class for networking and rendering muliplayer"""
    def __init__(self, username=""):
        self.position = {'x': 244, 'y': 188, 'z': 0, 'h': 0, 'p': 0,
                           'r': 0}  # stores rotation too
        self.moving = False
        self.username = username
        self.model = self.animation_control = None

    def load(self):
        self.model = Actor("assets/models/ninja", {"walk": "assets/models/ninja"})
        self.model.reparentTo(base.render)
        self.model.setScale(0.5)
        self.moving = False
        self.animation_control = self.model.getAnimControl('walk')
        self.animation_control.setPlayRate(0.05)
        self.model.setBlend(frameBlend=1)


class ChatReg(DirectObject):
    """Chat regulator, handles everything about chat"""
    def __init__(self):
        self.max_messages = 14
        self.message_list = []
        # for gui debug
        self.accept("p", self.getWidgetTransformsF)
        # Create GUI
        # self.frame =
        self.chatInput = DirectEntry(initialText="Press 't' or click here to chat",
                                     cursorKeys=1,
                                     numLines=1,
                                     command=self.send,
                                     focusInCommand=self.handleTpress,
                                     focusOutCommand=self.resetText,
                                     focus=0,
                                     width=20)
        # self.chatInput.setPos(-1.31667,0,-0.97)
        self.chatInput.setScale(0.05)
        self.chatInput.reparentTo(base.a2dBottomLeft)
        self.chatInput.setPos(.05, 0, .05)

        self.messages = []
        self.txt = []
        for k in range(14):
            self.txt.append(OnscreenText(mayChange=1))
            self.messages.append(DirectLabel(activeState=1, text="hi"))
            # self.messages[k].setScale(0.0498732)
            # self.messages[k].setPos(-1.31667,0,-0.9)
        self.accept("t", self.handleTpress)
        self.accept("control-t", self.resetText)
        self.calls = 0

    def handleTpress(self):
        if not keys.isTyping:
            self.clearText()

    def clearText(self):
        self.chatInput.enterText('')
        keys.isTyping = True
        self.chatInput["focus"] = True

    def resetText(self):
        self.chatInput.enterText('')
        keys.isTyping = False

    # def leaveText(self):
    #  self.keys.isTyping = False
    def send(self, text):
        self.datagram = PyDatagram()
        self.datagram.addString("chat")
        self.datagram.addString(text)
        world_client.cWriter.send(self.datagram, world_client.conn)

    def setText(self, text):
        self.index = 0
        # put the messages on screen
        self.message_list.append(text)
        if len(self.message_list) > 14:
            self.message_list.reverse()
            del self.message_list[14]
            self.message_list.reverse()
        for k in self.message_list:
            self.text(k, (-.95, (-.8 + (.06 * self.index))), self.index)
            self.index += 1

    def getWidgetTransformsF(self):
        for child in base.aspect2d.getChildren():
            logging.info(child, "  position = ", child.getPos())
            logging.info(child, "  scale = ", child.getScale())

    def text(self, msg, position, index):
        self.txt[index].destroy()
        self.txt[index] = OnscreenText(text=msg, pos=position, fg=(1, 1, 1, 1),
                                       align=TextNode.ALeft, scale=.05, mayChange=1)
        self.txt[index].reparentTo(base.a2dBottomLeft)
        self.txt[index].setPos(.05, .15 + .05 * index)


# Just some groundwork

base.disableMouse()
base.camera.setPos(0, 2, 10)
# establish connection > send/receive updates > update world
world_client = Client(args.port, args.ip)
terrain = Terrain()
player_reg = PlayerReg()
me = Me()
keys = Keys()
world = World()
chat_reg = ChatReg()

taskMgr.add(player_reg.update_players, "keep every player where they are supposed to be")
taskMgr.add(me.move, "move our penguin")
taskMgr.add(world_client.data_available, "Poll the connection reader")
taskMgr.add(world.update_world, "keep the world up to date")


def quit_on_death():
    logging.critical("Shutting down")
    datagram = PyDatagram()
    datagram.addString("quit")
    datagram.addInt8(me.player_id)
    world_client.cWriter.send(datagram, world_client.conn)


atexit.register(quit_on_death)

# test code for lighting, normal mapping, etc...#
# ambient light
alight = AmbientLight('alight')
alight.setColor(Vec4(0.2, 0.2, 0.2, 1))
alnp = base.render.attachNewNode(alight)
base.render.setLight(alnp)
me.model.setShaderAuto()
# me.model.setNormalMap("assets/models/nskinrd-normal.jpg")

lightpivot = base.render.attachNewNode("lightpivot")
lightpivot.setPos(0, 0, 25)
plight = PointLight('plight')
plight.setColor(Vec4(1, 1, 1, 1))
plnp = lightpivot.attachNewNode(plight)
base.render.setLight(plnp)
me.model.setShaderInput("light", plnp)
# Castle = Castle(Vec3(288.96,294.45,30.17), Vec3(119.05,270,0),0.08)

base.run()
