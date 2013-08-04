################################################################
# File: ch.py
# Title: Chatango Library
# Author: Lumirayz/Lumz <lumirayz@gmail.com>
# Version: 1.33
# Description:
#  An event-based library for connecting to one or multiple Chatango rooms, has
#  support for several things including: messaging, message font,
#  name color, deleting, banning, recent history, 2 userlist modes,
#  flagging, avoiding flood bans, detecting flags.
################################################################

################################################################
# License
################################################################
# Copyright 2011 Lumirayz
# This program is distributed under the terms of the GNU GPL.

################################################################
# Imports
################################################################
import socket
import threading
import time
import random
import re
import sys
import select


################################################################
# Python 2 compatibility
################################################################
if sys.version_info[0] < 3:
  class urllib:
    parse = __import__("urllib")
    request = __import__("urllib2")
  input = raw_input
  import codecs
else:
  import urllib.request
  import urllib.parse

################################################################
# Constants
################################################################
Userlist_Recent = 0
Userlist_All    = 1

BigMessage_Multiple = 0
BigMessage_Cut      = 1

################################################################
# Struct class
################################################################
class Struct:
  def __init__(self, **entries):
    self.__dict__.update(entries)

################################################################
# Tagserver stuff
################################################################
specials = {'mitvcanal': 56, 'magicc666': 22, 'livenfree': 18, 'eplsiite': 56, 'soccerjumbo2': 21, 'bguk': 22, 'animachat20': 34, 'pokemonepisodeorg': 55, 'sport24lt': 56, 'mywowpinoy': 5, 'phnoytalk': 21, 'flowhot-chat-online': 12, 'watchanimeonn': 26, 'cricvid-hitcric-': 51, 'fullsportshd2': 18, 'chia-anime': 12, 'narutochatt': 52, 'ttvsports': 56, 'futboldirectochat': 22, 'portalsports': 18, 'stream2watch3': 56, 'proudlypinoychat': 51, 'ver-anime': 34, 'iluvpinas': 53, 'vipstand': 21, 'eafangames': 56, 'worldfootballusch2': 18, 'soccerjumbo': 21, 'myfoxdfw': 22, 'animelinkz': 20, 'rgsmotrisport': 51, 'bateriafina-8': 8, 'as-chatroom': 10, 'dbzepisodeorg': 12, 'tvanimefreak': 54, 'watch-dragonball': 19, 'narutowire': 10, 'leeplarp': 27}
tsweights = [['5', 61], ['6', 61], ['7', 61], ['8', 61], ['16', 61], ['17', 61], ['9', 90], ['11', 90], ['13', 90], ['14', 90], ['15', 90], ['23', 110], ['24', 110], ['25', 110], ['28', 104], ['29', 104], ['30', 104], ['31', 104], ['32', 104], ['33', 104], ['35', 101], ['36', 101], ['37', 101], ['38', 101], ['39', 101], ['40', 101], ['41', 101], ['42', 101], ['43', 101], ['44', 101], ['45', 101], ['46', 101], ['47', 101], ['48', 101], ['49', 101], ['50', 101], ['57', 110], ['58', 110], ['59', 110], ['60', 110], ['61', 110], ['62', 110], ['63', 110], ['64', 110], ['65', 110], ['66', 110]]

def getServer(group):
  """
  Get the server host for a certain room.
  
  @type group: str
  @param group: room name
  
  @rtype: str
  @return: the server's hostname
  """
  try:
    sn = specials[group]
  except KeyError:
    group = group.replace("_", "q")
    group = group.replace("-", "q")
    fnv = float(int(group[0:min(5, len(group))], 36))
    lnv = group[6: (6 + min(3, len(group) - 5))]
    if(lnv):
      lnv = float(int(lnv, 36))
      lnv = max(lnv,1000)
    else:
      lnv = 1000
    num = (fnv % lnv) / lnv
    maxnum = sum(map(lambda x: x[1], tsweights))
    cumfreq = 0
    sn = 0
    for wgt in tsweights:
      cumfreq += float(wgt[1]) / maxnum
      if(num <= cumfreq):
        sn = int(wgt[0])
        break
  return "s" + str(sn) + ".chatango.com"

################################################################
# Uid
################################################################
def genUid():
  return str(random.randrange(10 ** 15, 10 ** 16))

################################################################
# Message stuff
################################################################
if sys.version_info[0] < 3:
  def BOMdefuser(content):
    return content.encode("ascii","ignore").decode("ascii")

def clean_message(msg):
  """
  Clean a message and return the message, n tag and f tag.
  
  @type msg: str
  @param msg: the message
  
  @rtype: str, str, str
  @returns: cleaned message, n tag contents, f tag contents
  """
  n = re.search("<n(.*?)/>", msg)
  if n: n = n.group(1)
  f = re.search("<f(.*?)>", msg)
  if f: f = f.group(1)
  msg = re.sub("<n.*?/>", "", msg)
  msg = re.sub("<f.*?>", "", msg)
  msg = strip_html(msg)
  msg = msg.replace("&lt;", "<")
  msg = msg.replace("&gt;", ">")
  msg = msg.replace("&quot;", "\"")
  msg = msg.replace("&apos;", "'")
  msg = msg.replace("&amp;", "&")
  return msg, n, f

def strip_html(msg):
  """Strip HTML."""
  li = msg.split("<")
  if len(li) == 1:
    return li[0]
  else:
    ret = list()
    for data in li:
      data = data.split(">", 1)
      if len(data) == 1:
        ret.append(data[0])
      elif len(data) == 2:
        ret.append(data[1])
    return "".join(ret)

def parseNameColor(n):
  """This just returns its argument, should return the name color."""
  #probably is already the name
  return n

def parseFont(f):
  """Parses the contents of a f tag and returns color, face and size."""
  #' xSZCOL="FONT"'
  try: #TODO: remove quick hack
    sizecolor, fontface = f.split("=", 1)
    sizecolor = sizecolor.strip()
    size = int(sizecolor[1:3])
    col = sizecolor[3:6]
    if col == "": col = None
    face = f.split("\"", 2)[1]
    return col, face, size
  except:
    return None, None, None

################################################################
# Anon id
################################################################
def getAnonId(n, ssid):
  """Gets the anon's id."""
  if n == None: n = "5504"
  try:
    return "".join(list(
      map(lambda x: str(x[0] + x[1])[-1], list(zip(
        list(map(lambda x: int(x), n)),
        list(map(lambda x: int(x), ssid[4:]))
      )))
    ))
  except ValueError:
    return "NNNN"

################################################################
# PM Auth
################################################################
auth_re = re.compile(r"auth\.chatango\.com ?= ?([^;]*)", re.IGNORECASE)

def _getAuth(name, password):
  """
  Request an auid using name and password.
  
  @type name: str
  @param name: name
  @type password: str
  @param password: password
  
  @rtype: str
  @return: auid
  """
  data = urllib.parse.urlencode({
    "user_id": name,
    "password": password,
    "storecookie": "on",
    "checkerrors": "yes"
  }).encode()
  try:
    resp = urllib.request.urlopen("http://chatango.com/login", data)
    headers = resp.headers
  except Exception:
    return None
  for header, value in headers.items():
    if header.lower() == "set-cookie":
      m = auth_re.search(value)
      if m:
        auth = m.group(1)
        if auth == "":
          return None
        return auth
  return None

################################################################
# PM class
################################################################
class PM:
  """Manages a connection with Chatango PM."""
  ####
  # Init
  ####
  def __init__(self, mgr):
    self._connected = False
    self._mgr = mgr
    self._auid = None
    self._blocklist = set()
    self._contacts = set()
    self._wlock = False
    self._firstCommand = True
    self._wbuf = b""
    self._wlockbuf = b""
    self._rbuf = b""
    self._pingTask = None
    self._connect()
  
  ####
  # Connections
  ####
  def _connect(self):
    self._wbuf = b""
    self._sock = socket.socket()
    self._sock.connect((self._mgr._PMHost, self._mgr._PMPort))
    self._sock.setblocking(False)
    self._firstCommand = True
    if not self._auth(): return
    self._pingTask = self.mgr.setInterval(self._mgr._pingDelay, self.ping)
    self._connected = True
  
  def _auth(self):
    self._auid = _getAuth(self._mgr.name, self._mgr.password)
    if self._auid == None:
      self._sock.close()
      self._callEvent("onLoginFail")
      self._sock = None
      return False
    self._sendCommand("tlogin", self._auid, "2")
    self._setWriteLock(True)
    return True
  
  def disconnect(self):
    self._disconnect()
    self._callEvent("onPMDisconnect")
  
  def _disconnect(self):
    self._connected = False
    self._sock.close()
    self._sock = None
  
  ####
  # Feed
  ####
  def _feed(self, data):
    """
    Feed data to the connection.
    
    @type data: bytes
    @param data: data to be fed
    """
    self._rbuf += data
    while self._rbuf.find(b"\x00") != -1:
      data = self._rbuf.split(b"\x00")
      for food in data[:-1]:
        if sys.version_info[0] < 3:
          self._process(food.decode(errors="replace").rstrip("\r\n")) #numnumz ;3
        else:
          self._process(food.decode().rstrip("\r\n")) #numnumz ;3
      self._rbuf = data[-1]
  
  def _process(self, data):
    """
    Process a command string.
    
    @type data: str
    @param data: the command string
    """
    self._callEvent("onRaw", data)
    data = data.split(":")
    cmd, args = data[0], data[1:]
    func = "rcmd_" + cmd
    if hasattr(self, func):
      getattr(self, func)(args)
  
  ####
  # Properties
  ####
  def getManager(self): return self._mgr
  def getContacts(self): return self._contacts
  def getBlocklist(self): return self._blocklist
  
  mgr = property(getManager)
  contacts = property(getContacts)
  blocklist = property(getBlocklist)
  
  ####
  # Received Commands
  ####
  def rcmd_OK(self, args):
    self._setWriteLock(False)
    self._sendCommand("wl")
    self._sendCommand("getblock")
    self._callEvent("onPMConnect")
  
  def rcmd_wl(self, args):
    self._contacts = set()
    for i in range(len(args) // 4):
      name, last_on, is_on, idle = args[i * 4: i * 4 + 4]
      user = User(name)
      self._contacts.add(user)
    self._callEvent("onPMContactlistReceive")
  
  def rcmd_block_list(self, args):
    self._blocklist = set()
    for name in args:
      if name == "": continue
      self._blocklist.add(User(name))
  
  def rcmd_DENIED(self, args):
    self._disconnect()
    self._callEvent("onLoginFail")
  
  def rcmd_msg(self, args):
    user = User(args[0])
    body = strip_html(":".join(args[5:]))
    self._callEvent("onPMMessage", user, body)
  
  def rcmd_msgoff(self, args):
    user = User(args[0])
    body = strip_html(":".join(args[5:]))
    self._callEvent("onPMOfflineMessage", user, body)
  
  def rcmd_wlonline(self, args):
    self._callEvent("onPMContactOnline", User(args[0]))
  
  def rcmd_wloffline(self, args):
    self._callEvent("onPMContactOffline", User(args[0]))
  
  def rcmd_kickingoff(self, args):
    self.disconnect()
  
  ####
  # Commands
  ####
  def ping(self):
    self._sendCommand("")
    self._callEvent("onPMPing")
  
  def message(self, user, msg):
    if msg!=None:
      self._sendCommand("msg", user.name, msg)
  
  def addContact(self, user):
    if user not in self._contacts:
      self._sendCommand("wladd", user.name)
      self._contacts.add(user)
      self._callEvent("onPMContactAdd", user)
  
  def removeContact(self, user):
    if user in self._contacts:
      self._sendCommand("wldelete", user.name)
      self._contacts.remove(user)
      self._callEvent("onPMContactRemove", user)
  
  def block(self, user):
    if user not in self._blocklist:
      self._sendCommand("block", user.name)
      self._block.remove(user)
      self._callEvent("onPMBlock", user)
  
  def unblock(self, user):
    if user in self._blocklist:
      self._sendCommand("unblock", user.name)
      self._block.remove(user)
      self._callEvent("onPMUnblock", user)
  
  ####
  # Util
  ####
  def _callEvent(self, evt, *args, **kw):
    getattr(self.mgr, evt)(self, *args, **kw)
    self.mgr.onEventCalled(self, evt, *args, **kw)
  
  def _write(self, data):
    if self._wlock:
      self._wlockbuf += data
    else:
      self.mgr._write(self, data)
  
  def _setWriteLock(self, lock):
    self._wlock = lock
    if self._wlock == False:
      self._write(self._wlockbuf)
      self._wlockbuf = b""
  
  def _sendCommand(self, *args):
    """
    Send a command.
    
    @type args: [str, str, ...]
    @param args: command and list of arguments
    """
    if self._firstCommand:
      terminator = b"\x00"
      self._firstCommand = False
    else:
      terminator = b"\r\n\x00"
    self._write(":".join(args).encode() + terminator)

################################################################
# Room class
################################################################
class Room:
  """Manages a connection with a Chatango room."""
  ####
  # Init
  ####
  def __init__(self, room, uid = None, server = None, port = None, mgr = None):
    # Basic stuff
    self._name = room
    self._server = server or getServer(room)
    self._port = port or 443
    self._mgr = mgr
    
    # Under the hood
    self._connected = False
    self._reconnecting = False
    self._uid = uid or genUid()
    self._rbuf = b""
    self._wbuf = b""
    self._wlockbuf = b""
    self._owner = None
    self._mods = set()
    self._mqueue = dict()
    self._history = list()
    self._userlist = list()
    self._firstCommand = True
    self._connectAmmount = 0
    self._premium = False
    self._userCount = 0
    self._pingTask = None
    self._users = dict()
    self._msgs = dict()
    self._wlock = False
    self._silent = False
    self._banlist = list()
    
    # Inited vars
    if self._mgr: self._connect()
  
  ####
  # User and Message management
  ####
  def getMessage(self, mid):
    return self._msgs.get(mid)
  
  def createMessage(self, msgid, **kw):
    if msgid not in self._msgs:
      msg = Message(msgid = msgid, **kw)
      self._msgs[msgid] = msg
    else:
      msg = self._msgs[msgid]
    return msg
  
  ####
  # Connect/disconnect
  ####
  def _connect(self):
    """Connect to the server."""
    self._sock = socket.socket()
    self._sock.connect((self._server, self._port))
    self._sock.setblocking(False)
    self._firstCommand = True
    self._wbuf = b""
    self._auth()
    self._pingTask = self.mgr.setInterval(self.mgr._pingDelay, self.ping)
    if not self._reconnecting: self.connected = True
  
  def reconnect(self):
    """Reconnect."""
    self._reconnect()
  
  def _reconnect(self):
    """Reconnect."""
    self._reconnecting = True
    if self.connected:
      self._disconnect()
    self._uid = genUid()
    self._connect()
    self._reconnecting = False
  
  def disconnect(self):
    """Disconnect."""
    self._disconnect()
    self._callEvent("onDisconnect")
  
  def _disconnect(self):
    """Disconnect from the server."""
    if not self._reconnecting: self.connected = False
    for user in self._userlist:
      user.clearSessionIds(self)
    self._userlist = list()
    self._pingTask.cancel()
    self._sock.close()
    if not self._reconnecting: del self.mgr._rooms[self.name]
  
  def _auth(self):
    """Authenticate."""
    # login as name with password
    if self.mgr.name and self.mgr.password:
      self._sendCommand("bauth", self.name, self._uid, self.mgr.name, self.mgr.password)                
    # login as anon
    else:
      self._sendCommand("bauth", self.name)

    self._setWriteLock(True)
  
  ####
  # Properties
  ####
  def getName(self): return self._name
  def getManager(self): return self._mgr
  def getUserlist(self, mode = None, unique = None, memory = None):
    ul = None
    if mode == None: mode = self.mgr._userlistMode
    if unique == None: unique = self.mgr._userlistUnique
    if memory == None: memory = self.mgr._userlistMemory
    if mode == Userlist_Recent:
      ul = map(lambda x: x.user, self._history[-memory:])
    elif mode == Userlist_All:
      ul = self._userlist
    if unique:
      return list(set(ul))
    else:
      return ul
  def getUserNames(self):
    ul = self.userlist
    return list(map(lambda x: x.name, ul))
  def getUser(self): return self.mgr.user
  def getOwner(self): return self._owner
  def getOwnerName(self): return self._owner.name
  def getMods(self):
    newset = set()
    for mod in self._mods:
      newset.add(mod)
    return newset
  def getModNames(self):
    mods = self.getMods()
    return [x.name for x in mods]
  def getUserCount(self): return self._userCount
  def getSilent(self): return self._silent
  def setSilent(self, val): self._silent = val
  def getBanlist(self): return [record[2] for record in self._banlist]
    
  name = property(getName)
  mgr = property(getManager)
  userlist = property(getUserlist)
  usernames = property(getUserNames)
  user = property(getUser)
  owner = property(getOwner)
  ownername = property(getOwnerName)
  mods = property(getMods)
  modnames = property(getModNames)
  usercount = property(getUserCount)
  silent = property(getSilent, setSilent)
  banlist = property(getBanlist)
  
  ####
  # Feed/process
  ####
  def _feed(self, data):
    """
    Feed data to the connection.
    
    @type data: bytes
    @param data: data to be fed
    """
    self._rbuf += data
    while self._rbuf.find(b"\x00") != -1:
      data = self._rbuf.split(b"\x00")
      for food in data[:-1]:
        if sys.version_info[0] < 3:
          self._process(food.decode(errors="replace").rstrip("\r\n")) #numnumx ;3
        else:
          self._process(food.decode().rstrip("\r\n")) #numnumz ;3
      self._rbuf = data[-1]
  
  def _process(self, data):
    """
    Process a command string.
    
    @type data: str
    @param data: the command string
    """
    self._callEvent("onRaw", data)
    data = data.split(":")
    cmd, args = data[0], data[1:]
    func = "rcmd_" + cmd
    if hasattr(self, func):
      getattr(self, func)(args)
  
  ####
  # Received Commands
  ####
  def rcmd_ok(self, args):
    # if no name, join room as anon and no password
    if args[2] == "N" and self.mgr.password == None and self.mgr.name == None: pass
    # if got name, join room as name and no password
    elif args[2] == "N" and self.mgr.password == None:
      self._sendCommand("blogin", self.mgr.name)
    # if got password but fail to login
    elif args[2] != "M": #unsuccesful login
      self._callEvent("onLoginFail")
      self.disconnect()
    self._owner = User(args[0])
    self._uid = args[1]
    self._aid = args[1][4:8]
    self._mods = set(map(lambda x: User(x), args[6].split(";")))
    self._i_log = list()
  
  def rcmd_denied(self, args):
    self._disconnect()
    self._callEvent("onConnectFail")
  
  def rcmd_inited(self, args):
    self._sendCommand("g_participants", "start")
    self._sendCommand("getpremium", "1")
    self.requestBanlist()
    if self._connectAmmount == 0:
      self._callEvent("onConnect")
      for msg in reversed(self._i_log):
        user = msg.user
        self._callEvent("onHistoryMessage", user, msg)
        self._addHistory(msg)
      del self._i_log
    else:
      self._callEvent("onReconnect")
    self._connectAmmount += 1
    self._setWriteLock(False)
  
  def rcmd_premium(self, args):
    if float(args[1]) > time.time():
      self._premium = True
      if self.user._mbg: self.setBgMode(1)
      if self.user._mrec: self.setRecordingMode(1)
    else:
      self._premium = False
  
  def rcmd_mods(self, args):
    modnames = args
    mods = set(map(lambda x: User(x), modnames))
    premods = self._mods
    for user in mods - premods: #modded
      self._mods.add(user)
      self._callEvent("onModAdd", user)
    for user in premods - mods: #demodded
      self._mods.remove(user)
      self._callEvent("onModRemove", user)
    self._callEvent("onModChange")
  
  def rcmd_b(self, args):
    mtime = float(args[0])
    puid = args[3]
    ip = args[6]
    name = args[1]
    rawmsg = ":".join(args[8:])
    msg, n, f = clean_message(rawmsg)
    if name == "":
      nameColor = None
      name = "#" + args[2]
      if name == "#":
        name = "!anon" + getAnonId(n, puid)
    else:
      if n: nameColor = parseNameColor(n)
      else: nameColor = None
    i = args[5]
    unid = args[4]
    #Create an anonymous message and queue it because msgid is unknown.
    if f: fontColor, fontFace, fontSize = parseFont(f)
    else: fontColor, fontFace, fontSize = None, None, None
    if sys.version_info[0] < 3:
      msg = Message(
        time = mtime,
        user = User(name),
        body = BOMdefuser(msg).encode("ASCII").decode("ASCII","replace")[1:],
        raw = BOMdefuser(rawmsg).encode("ASCII").decode("ASCII","replace")[1:],
        ip = ip,
        nameColor = nameColor,
        fontColor = fontColor,
        fontFace = fontFace,
        fontSize = fontSize,
        unid = unid,
        room = self
      )
    else:
      msg = Message(
        time = mtime,
        user = User(name),
        body = msg[1:],
        raw = rawmsg[1:],
        ip = ip,
        nameColor = nameColor,
        fontColor = fontColor,
        fontFace = fontFace,
        fontSize = fontSize,
        unid = unid,
        room = self
      )
    self._mqueue[i] = msg
  
  def rcmd_u(self, args):
    temp = Struct(**self._mqueue)
    if hasattr(temp, args[0]):
      msg = getattr(temp, args[0])
      if msg.user != self.user:
        msg.user._fontColor = msg.fontColor
        msg.user._fontFace = msg.fontFace
        msg.user._fontSize = msg.fontSize
        msg.user._nameColor = msg.nameColor
      del self._mqueue[args[0]]
      msg.attach(self, args[1])
      self._addHistory(msg)
      self._callEvent("onMessage", msg.user, msg)
  
  def rcmd_i(self, args):
    mtime = float(args[0])
    puid = args[3]
    ip = args[6]
    if ip == "": ip = None
    name = args[1]
    rawmsg = ":".join(args[8:])
    msg, n, f = clean_message(rawmsg)
    msgid = args[5]
    if name == "":
      nameColor = None
      name = "#" + args[2]
      if name == "#":
        name = "!anon" + getAnonId(n, puid)
    else:
      if n: nameColor = parseNameColor(n)
      else: nameColor = None
    if f: fontColor, fontFace, fontSize = parseFont(f)
    else: fontColor, fontFace, fontSize = None, None, None
    msg = self.createMessage(
      msgid = msgid,
      time = mtime,
      user = User(name),
      body = msg,
      raw = rawmsg,
      ip = args[6],
      unid = args[4],
      nameColor = nameColor,
      fontColor = fontColor,
      fontFace = fontFace,
      fontSize = fontSize,
      room = self
    )
    if msg.user != self.user:
      msg.user._fontColor = msg.fontColor
      msg.user._fontFace = msg.fontFace
      msg.user._fontSize = msg.fontSize
      msg.user._nameColor = msg.nameColor
    self._i_log.append(msg)
  
  def rcmd_g_participants(self, args):
    args = ":".join(args)
    args = args.split(";")
    for data in args:
      data = data.split(":")
      name = data[3].lower()
      if name == "none": continue
      user = User(
        name = name,
        room = self
      )
      user.addSessionId(self, data[0])
      self._userlist.append(user)
  
  def rcmd_participant(self, args):
    if args[0] == "0": #leave
      name = args[3].lower()
      if name == "none": return
      user = User(name)
      user.removeSessionId(self, args[1])
      self._userlist.remove(user)
      if user not in self._userlist or not self.mgr._userlistEventUnique:
        self._callEvent("onLeave", user)
    else: #join
      name = args[3].lower()
      if name == "none": return
      user = User(
        name = name,
        room = self
      )
      user.addSessionId(self, args[1])
      if user not in self._userlist: doEvent = True
      else: doEvent = False
      self._userlist.append(user)
      if doEvent or not self.mgr._userlistEventUnique:
        self._callEvent("onJoin", user)
  
  def rcmd_show_fw(self, args):
    self._callEvent("onFloodWarning")
  
  def rcmd_show_tb(self, args):
    self._callEvent("onFloodBan")
  
  def rcmd_tb(self, args):
    self._callEvent("onFloodBanRepeat")
  
  def rcmd_delete(self, args):
    msg = self.getMessage(args[0])
    if msg:
      if msg in self._history:
        self._history.remove(msg)
        self._callEvent("onMessageDelete", msg.user, msg)
        msg.detach()
  
  def rcmd_deleteall(self, args):
    for msgid in args:
      self.rcmd_delete([msgid])
  
  def rcmd_n(self, args):
    self._userCount = int(args[0], 16)
    self._callEvent("onUserCountChange")
  
  def rcmd_blocklist(self, args):
    self._banlist = list()
    sections = ":".join(args).split(";")
    for section in sections:
      params = section.split(":")
      if len(params) != 5: continue
      if params[2] == "": continue
      self._banlist.append((
        params[0], #unid
        params[1], #ip
        User(params[2]), #target
        float(params[3]), #time
        User(params[4]) #src
      ))
    self._callEvent("onBanlistUpdate")
  
  def rcmd_blocked(self, args):
    if args[2] == "": return
    target = User(args[2])
    user = User(args[3])
    self._banlist.append((args[0], args[1], target, float(args[4]), user))
    self._callEvent("onBan", user, target)
    self.requestBanlist()
  
  def rcmd_unblocked(self, args):
    if args[2] == "": return
    target = User(args[2])
    user = User(args[3])
    self._callEvent("onUnban", user, target)
    self.requestBanlist()
  
  ####
  # Commands
  ####
  def ping(self):
    """Send a ping."""
    self._sendCommand("")
    self._callEvent("onPing")
  
  def rawMessage(self, msg):
    """
    Send a message without n and f tags.
    
    @type msg: str
    @param msg: message
    """
    if not self._silent:
      self._sendCommand("bmsg:tl2r", msg)
  
  def message(self, msg, html = False):
    """
    Send a message.
    
    @type msg: str
    @param msg: message
    """
    if msg==None:
      return
    if not html:
      msg = msg.replace("<", "&lt;").replace(">", "&gt;")
    if len(msg) > self.mgr._maxLength:
      if self.mgr._tooBigMessage == BigMessage_Cut:
        self.message(msg[:self.mgr._maxLength], html = html)
      elif self.mgr._tooBigMessage == BigMessage_Multiple:
        while len(msg) > 0:
          sect = msg[:self.mgr._maxLength]
          msg = msg[self.mgr._maxLength:]
          self.message(sect, html = html)
      return
    msg = "<n" + self.user.nameColor + "/>" + msg
    msg = "<f x%0.2i%s=\"%s\">" %(self.user.fontSize, self.user.fontColor, self.user.fontFace) + msg
    self.rawMessage(msg)
  
  def setBgMode(self, mode):
    self._sendCommand("msgbg", str(mode))
  
  def setRecordingMode(self, mode):
    self._sendCommand("msgmedia", str(mode))

  def addMod(self, user):
    """
    Add a moderator.
    
    @type user: User
    @param user: User to mod.
    """
    if self.getLevel(self.user) == 2:
      self._sendCommand("addmod", user.name)
    
  def removeMod(self, user):
    """
    Remove a moderator.
    
    @type user: User
    @param user: User to demod.
    """
    if self.getLevel(self.user) == 2:
      self._sendCommand("removemod", user.name)
  
  def flag(self, message):
    """
    Flag a message.
    
    @type message: Message
    @param message: message to flag
    """
    self._sendCommand("g_flag", message.msgid)
  
  def flagUser(self, user):
    """
    Flag a user.
    
    @type user: User
    @param user: user to flag
    
    @rtype: bool
    @return: whether a message to flag was found
    """
    msg = self.getLastMessage(user)
    if msg:
      self.flag(msg)
      return True
    return False
  
  def delete(self, message):
    """
    Delete a message. (Moderator only)
    
    @type message: Message
    @param message: message to delete
    """
    if self.getLevel(self.user) > 0:
      self._sendCommand("delmsg", message.msgid)
  
  def rawClearUser(self, unid):
    self._sendCommand("delallmsg", unid)
  
  def clearUser(self, user):
    """
    Clear all of a user's messages. (Moderator only)
    
    @type user: User
    @param user: user to delete messages of
    
    @rtype: bool
    @return: whether a message to delete was found
    """
    if self.getLevel(self.user) > 0:
      msg = self.getLastMessage(user)
      if msg:
        self.rawClearUser(msg.unid)
      return True
    return False
  
  def clearall(self):
    """Clear all messages. (Owner only)"""
    if self.getLevel(self.user) == 2:
      self._sendCommand("clearall")
  
  def rawBan(self, name, ip, unid):
    """
    Execute the block command using specified arguments.
    (For advanced usage)
    
    @type name: str
    @param name: name
    @type ip: str
    @param ip: ip address
    @type unid: str
    @param unid: unid
    """
    self._sendCommand("block", unid, ip, name)
  
  def ban(self, msg):
    """
    Ban a message's sender. (Moderator only)
    
    @type message: Message
    @param message: message to ban sender of
    """
    if self.getLevel(self.user) > 0:
      self.rawBan(msg.user.name, msg.ip, msg.unid)
  
  def banUser(self, user):
    """
    Ban a user. (Moderator only)
    
    @type user: User
    @param user: user to ban
    
    @rtype: bool
    @return: whether a message to ban the user was found
    """
    msg = self.getLastMessage(user)
    if msg:
      self.ban(msg)
      return True
    return False
  
  def requestBanlist(self):
    """Request an updated banlist."""
    self._sendCommand("blocklist", "block", "", "next", "500")
  
  def rawUnban(self, name, ip, unid):
    """
    Execute the unblock command using specified arguments.
    (For advanced usage)
    
    @type name: str
    @param name: name
    @type ip: str
    @param ip: ip address
    @type unid: str
    @param unid: unid
    """
    self._sendCommand("removeblock", unid, ip, name)
  
  def unban(self, user):
    """
    Unban a user. (Moderator only)
    
    @type user: User
    @param user: user to unban
    
    @rtype: bool
    @return: whether it succeeded
    """
    rec = self._getBanRecord(user)
    if rec:
      self.rawUnban(rec[2].name, rec[1], rec[0])
      return True
    else:
      return False
  
  ####
  # Util
  ####
  def _getBanRecord(self, user):
    for record in self._banlist:
      if record[2] == user:
        return record
    return None
  
  def _callEvent(self, evt, *args, **kw):
    getattr(self.mgr, evt)(self, *args, **kw)
    self.mgr.onEventCalled(self, evt, *args, **kw)
  
  def _write(self, data):
    if self._wlock:
      self._wlockbuf += data
    else:
      self.mgr._write(self, data)
  
  def _setWriteLock(self, lock):
    self._wlock = lock
    if self._wlock == False:
      self._write(self._wlockbuf)
      self._wlockbuf = b""
  
  def _sendCommand(self, *args):
    """
    Send a command.
    
    @type args: [str, str, ...]
    @param args: command and list of arguments
    """
    if self._firstCommand:
      terminator = b"\x00"
      self._firstCommand = False
    else:
      terminator = b"\r\n\x00"
    self._write(":".join(args).encode() + terminator)
  
  def getLevel(self, user):
    if user == self._owner: return 2
    if user in self._mods: return 1
    return 0
  
  def getLastMessage(self, user = None):
    if user:
      try:
        i = 1
        while True:
          msg = self._history[-i]
          if msg.user == user:
            return msg
          i += 1
      except IndexError:
        return None
    else:
      try:
        return self._history[-1]
      except IndexError:
        return None
    return None
  
  def findUser(self, name):
    name = name.lower()
    ul = self.getUserlist()
    udi = dict(zip([u.name for u in ul], ul))
    cname = None
    for n in udi.keys():
      if n.find(name) != -1:
        if cname: return None #ambiguous!!
        cname = n
    if cname: return udi[cname]
    else: return None
  
  ####
  # History
  ####
  def _addHistory(self, msg):
    """
    Add a message to history.
    
    @type msg: Message
    @param msg: message
    """
    self._history.append(msg)
    if len(self._history) > self.mgr._maxHistoryLength:
      rest, self._history = self._history[:-self.mgr._maxHistoryLength], self._history[-self.mgr._maxHistoryLength:]
      for msg in rest: msg.detach()

################################################################
# RoomManager class
################################################################
class RoomManager:
  """Class that manages multiple connections."""
  ####
  # Config
  ####
  _Room = Room
  _PM = PM
  _PMHost = "c1.chatango.com"
  _PMPort = 5222
  _TimerResolution = 0.2 #at least x times per second
  _pingDelay = 20
  _userlistMode = Userlist_Recent
  _userlistUnique = True
  _userlistMemory = 50
  _userlistEventUnique = False
  _tooBigMessage = BigMessage_Multiple
  _maxLength = 1800
  _maxHistoryLength = 150
  
  ####
  # Init
  ####
  def __init__(self, name = None, password = None, pm = True):
    self._name = name
    self._password = password
    self._running = False
    self._tasks = set()
    self._rooms = dict()
    if pm:
      self._pm = self._PM(mgr = self)
    else:
      self._pm = None
  
  ####
  # Join/leave
  ####
  def joinRoom(self, room):
    """
    Join a room or return None if already joined.
    
    @type room: str
    @param room: room to join
    
    @rtype: Room or None
    @return: the room or nothing
    """
    room = room.lower()
    if room not in self._rooms:
      con = self._Room(room, mgr = self)
      self._rooms[room] = con
      return con
    else:
      return None
  
  def leaveRoom(self, room):
    """
    Leave a room.
    
    @type room: str
    @param room: room to leave
    """
    room = room.lower()
    if room in self._rooms:
      con = self._rooms[room]
      con.disconnect()
  
  def getRoom(self, room):
    """
    Get room with a name, or None if not connected to this room.
    
    @type room: str
    @param room: room
    
    @rtype: Room
    @return: the room
    """
    room = room.lower()
    if room in self._rooms:
      return self._rooms[room]
    else:
      return None
  
  ####
  # Properties
  ####
  def getUser(self): return User(self._name)
  def getName(self): return self._name
  def getPassword(self): return self._password
  def getRooms(self): return set(self._rooms.values())
  def getRoomNames(self): return set(self._rooms.keys())
  def getPM(self): return self._pm
  
  user = property(getUser)
  name = property(getName)
  password = property(getPassword)
  rooms = property(getRooms)
  roomnames = property(getRoomNames)
  pm = property(getPM)
  
  ####
  # Virtual methods
  ####
  def onInit(self):
    """Called on init."""
    pass
  
  def onConnect(self, room):
    """
    Called when connected to the room.
    
    @type room: Room
    @param room: room where the event occured
    """
    pass
  
  def onReconnect(self, room):
    """
    Called when reconnected to the room.
    
    @type room: Room
    @param room: room where the event occured
    """
    pass
  
  def onConnectFail(self, room):
    """
    Called when the connection failed.
    
    @type room: Room
    @param room: room where the event occured
    """
    pass
  
  def onDisconnect(self, room):
    """
    Called when the client gets disconnected.
    
    @type room: Room
    @param room: room where the event occured
    """
    pass
  
  def onLoginFail(self, room):
    """
    Called on login failure, disconnects after.
    
    @type room: Room
    @param room: room where the event occured
    """
    pass
  
  def onFloodBan(self, room):
    """
    Called when either flood banned or flagged.
    
    @type room: Room
    @param room: room where the event occured
    """
    pass
  
  def onFloodBanRepeat(self, room):
    """
    Called when trying to send something when floodbanned.
    
    @type room: Room
    @param room: room where the event occured
    """
    pass
  
  def onFloodWarning(self, room):
    """
    Called when an overflow warning gets received.
    
    @type room: Room
    @param room: room where the event occured
    """
    pass
  
  def onMessageDelete(self, room, user, message):
    """
    Called when a message gets deleted.
    
    @type room: Room
    @param room: room where the event occured
    @type user: User
    @param user: owner of deleted message
    @type message: Message
    @param message: message that got deleted
    """
    pass
  
  def onModChange(self, room):
    """
    Called when the moderator list changes.
    
    @type room: Room
    @param room: room where the event occured
    """
    pass
  
  def onModAdd(self, room, user):
    """
    Called when a moderator gets added.
    
    @type room: Room
    @param room: room where the event occured
    """
    pass
  
  def onModRemove(self, room, user):
    """
    Called when a moderator gets removed.
    
    @type room: Room
    @param room: room where the event occured
    """
    pass
  
  def onMessage(self, room, user, message):
    """
    Called when a message gets received.
    
    @type room: Room
    @param room: room where the event occured
    @type user: User
    @param user: owner of message
    @type message: Message
    @param message: received message
    """
    pass
  
  def onHistoryMessage(self, room, user, message):
    """
    Called when a message gets received from history.
    
    @type room: Room
    @param room: room where the event occured
    @type user: User
    @param user: owner of message
    @type message: Message
    @param message: the message that got added
    """
    pass
  
  def onJoin(self, room, user):
    """
    Called when a user joins. Anonymous users get ignored here.
    
    @type room: Room
    @param room: room where the event occured
    @type user: User
    @param user: the user that has joined
    """
    pass
  
  def onLeave(self, room, user):
    """
    Called when a user leaves. Anonymous users get ignored here.
    
    @type room: Room
    @param room: room where the event occured
    @type user: User
    @param user: the user that has left
    """
    pass
  
  def onRaw(self, room, raw):
    """
    Called before any command parsing occurs.
    
    @type room: Room
    @param room: room where the event occured
    @type raw: str
    @param raw: raw command data
    """
    pass
  
  def onPing(self, room):
    """
    Called when a ping gets sent.
    
    @type room: Room
    @param room: room where the event occured
    """
    pass
  
  def onUserCountChange(self, room):
    """
    Called when the user count changes.
    
    @type room: Room
    @param room: room where the event occured
    """
    pass
  
  def onBan(self, room, user, target):
    """
    Called when a user gets banned.
    
    @type room: Room
    @param room: room where the event occured
    @type user: User
    @param user: user that banned someone
    @type target: User
    @param target: user that got banned
    """
    pass
  
  def onUnban(self, room, user, target):
    """
    Called when a user gets unbanned.
    
    @type room: Room
    @param room: room where the event occured
    @type user: User
    @param user: user that unbanned someone
    @type target: User
    @param target: user that got unbanned
    """
    pass
  
  def onBanlistUpdate(self, room):
    """
    Called when a banlist gets updated.
    
    @type room: Room
    @param room: room where the event occured
    """
    pass
  
  def onPMConnect(self, pm):
    pass
  
  def onPMDisconnect(self, pm):
    pass
  
  def onPMPing(self, pm):
    pass
  
  def onPMMessage(self, pm, user, body):
    pass
  
  def onPMOfflineMessage(self, pm, user, body):
    pass
  
  def onPMContactlistReceive(self, pm):
    pass
  
  def onPMBlocklistReceive(self, pm):
    pass
  
  def onPMContactAdd(self, pm, user):
    pass
  
  def onPMContactRemove(self, pm, user):
    pass
  
  def onPMBlock(self, pm, user):
    pass
  
  def onPMUnblock(self, pm, user):
    pass
  
  def onPMContactOnline(self, pm, user):
    pass
  
  def onPMContactOffline(self, pm, user):
    pass
  
  def onEventCalled(self, room, evt, *args, **kw):
    """
    Called on every room-based event.
    
    @type room: Room
    @param room: room where the event occured
    @type evt: str
    @param evt: the event
    """
    pass
  
  ####
  # Deferring
  ####
  def deferToThread(self, callback, func, *args, **kw):
    """
    Defer a function to a thread and callback the return value.
    
    @type callback: function
    @param callback: function to call on completion
    @type cbargs: tuple or list
    @param cbargs: arguments to get supplied to the callback
    @type func: function
    @param func: function to call
    """
    def f(func, callback, *args, **kw):
      ret = func(*args, **kw)
      self.setTimeout(0, callback, ret)
    threading._start_new_thread(f, (func, callback) + args, kw)
  
  ####
  # Scheduling
  ####
  class _Task:
    def cancel(self):
      """Sugar for removeTask."""
      self.mgr.removeTask(self)
  
  def _tick(self):
    now = time.time()
    for task in set(self._tasks):
      if task.target <= now:
        task.func(*task.args, **task.kw)
        if task.isInterval:
          task.target = now + task.timeout
        else:
          self._tasks.remove(task)
  
  def setTimeout(self, timeout, func, *args, **kw):
    """
    Call a function after at least timeout seconds with specified arguments.
    
    @type timeout: int
    @param timeout: timeout
    @type func: function
    @param func: function to call
    
    @rtype: _Task
    @return: object representing the task
    """
    task = self._Task()
    task.mgr = self
    task.target = time.time() + timeout
    task.timeout = timeout
    task.func = func
    task.isInterval = False
    task.args = args
    task.kw = kw
    self._tasks.add(task)
    return task
  
  def setInterval(self, timeout, func, *args, **kw):
    """
    Call a function at least every timeout seconds with specified arguments.
    
    @type timeout: int
    @param timeout: timeout
    @type func: function
    @param func: function to call
    
    @rtype: _Task
    @return: object representing the task
    """
    task = self._Task()
    task.mgr = self
    task.target = time.time() + timeout
    task.timeout = timeout
    task.func = func
    task.isInterval = True
    task.args = args
    task.kw = kw
    self._tasks.add(task)
    return task
  
  def removeTask(self, task):
    """
    Cancel a task.
    
    @type task: _Task
    @param task: task to cancel
    """
    self._tasks.remove(task)
  
  ####
  # Util
  ####
  def _write(self, room, data):
    room._wbuf += data
  
  def getConnections(self):
    li = list(self._rooms.values())
    if self._pm:
      li.append(self._pm)
    return [c for c in li if c._sock != None]
  
  ####
  # Main
  ####
  def main(self):
    self.onInit()
    self._running = True
    while self._running:
      conns = self.getConnections()
      socks = [x._sock for x in conns]
      wsocks = [x._sock for x in conns if x._wbuf != b""]
      rd, wr, sp = select.select(socks, wsocks, [], self._TimerResolution)
      for sock in rd:
        con = [c for c in conns if c._sock == sock][0]
        try:
          data = sock.recv(1024)
          if(len(data) > 0):
            con._feed(data)
          else:
            con.disconnect()
        except socket.error:
          pass
      for sock in wr:
        con = [c for c in conns if c._sock == sock][0]
        try:
          size = sock.send(con._wbuf)
          con._wbuf = con._wbuf[size:]
        except socket.error:
          pass
      self._tick()
  
  @classmethod
  def easy_start(cl, rooms = None, name = None, password = None, pm = True):
    """
    Prompts the user for missing info, then starts.
    
    @type rooms: list
    @param room: rooms to join
    @type name: str
    @param name: name to join as ("" = None, None = unspecified)
    @type password: str
    @param password: password to join with ("" = None, None = unspecified)
    """
    if not rooms: rooms = str(input("Room names separated by semicolons: ")).split(";")
    if len(rooms) == 1 and rooms[0] == "": rooms = []
    if not name: name = str(input("User name: "))
    if name == "": name = None
    if not password: password = str(input("User password: "))
    if password == "": password = None
    self = cl(name, password, pm = pm)
    if len(rooms) > 5:
      # slow down connection to stop fail connection
      t = 1
      for room in rooms:
        self.setTimeout(int(t),self.joinRoom,room)
        if len(rooms) > 10:
          t = t + 1
        else:
          t = t + 0.5
    else:
      for room in rooms:
        self.joinRoom(room)
    self.main()
  
  def stop(self):
    for conn in list(self._rooms.values()):
      conn.disconnect()
    self._running = False
  
  ####
  # Commands
  ####
  def enableBg(self):
    """Enable background if available."""
    self.user._mbg = True
    for room in self.rooms:
      room.setBgMode(1)
  
  def disableBg(self):
    """Disable background."""
    self.user._mbg = False
    for room in self.rooms:
      room.setBgMode(0)
  
  def enableRecording(self):
    """Enable recording if available."""
    self.user._mrec = True
    for room in self.rooms:
      room.setRecordingMode(1)
  
  def disableRecording(self):
    """Disable recording."""
    self.user._mrec = False
    for room in self.rooms:
      room.setRecordingMode(0)
  
  def setNameColor(self, color3x):
    """
    Set name color.
    
    @type color3x: str
    @param color3x: a 3-char RGB hex code for the color
    """
    self.user._nameColor = color3x
  
  def setFontColor(self, color3x):
    """
    Set font color.
    
    @type color3x: str
    @param color3x: a 3-char RGB hex code for the color
    """
    self.user._fontColor = color3x
  
  def setFontFace(self, face):
    """
    Set font face/family.
    
    @type face: str
    @param face: the font face
    """
    self.user._fontFace = face
  
  def setFontSize(self, size):
    """
    Set font size.
    
    @type size: int
    @param size: the font size (limited: 9 to 22)
    """
    if size < 9: size = 9
    if size > 22: size = 22
    self.user._fontSize = size

################################################################
# User class (well, yeah, I lied, it's actually _User)
################################################################
_users = dict()
def User(name, *args, **kw):
  if name == None: name = ""
  name = name.lower()
  user = _users.get(name)
  if not user:
    user = _User(name = name, *args, **kw)
    _users[name] = user
  return user

class _User:
  """Class that represents a user."""
  ####
  # Init
  ####
  def __init__(self, name, **kw):
    self._name = name.lower()
    self._sids = dict()
    self._msgs = list()
    self._nameColor = "000"
    self._fontSize = 12
    self._fontFace = "0"
    self._fontColor = "000"
    self._mbg = False
    self._mrec = False
    for attr, val in kw.items():
      if val == None: continue
      setattr(self, "_" + attr, val)
  
  ####
  # Properties
  ####
  def getName(self): return self._name
  def getSessionIds(self, room = None):
    if room:
      return self._sids.get(room, set())
    else:
      return set.union(*self._sids.values())
  def getRooms(self): return self._sids.keys()
  def getRoomNames(self): return [room.name for room in self.getRooms()]
  def getFontColor(self): return self._fontColor
  def getFontFace(self): return self._fontFace
  def getFontSize(self): return self._fontSize
  def getNameColor(self): return self._nameColor
  
  name = property(getName)
  sessionids = property(getSessionIds)
  rooms = property(getRooms)
  roomnames = property(getRoomNames)
  fontColor = property(getFontColor)
  fontFace = property(getFontFace)
  fontSize = property(getFontSize)
  nameColor = property(getNameColor)
  
  ####
  # Util
  ####
  def addSessionId(self, room, sid):
    if room not in self._sids:
      self._sids[room] = set()
    self._sids[room].add(sid)
  
  def removeSessionId(self, room, sid):
    try:
      self._sids[room].remove(sid)
      if len(self._sids[room]) == 0:
        del self._sids[room]
    except KeyError:
      pass
  
  def clearSessionIds(self, room):
    try:
      del self._sids[room]
    except KeyError:
      pass
  
  def hasSessionId(self, room, sid):
    try:
      if sid in self._sids[room]:
        return True
      else:
        return False
    except KeyError:
      return False
  
  ####
  # Repr
  ####
  def __repr__(self):
    return "<User: %s>" %(self.name)

################################################################
# Message class
################################################################
class Message:
  """Class that represents a message."""
  ####
  # Attach/detach
  ####
  def attach(self, room, msgid):
    """
    Attach the Message to a message id.
    
    @type msgid: str
    @param msgid: message id
    """
    if self._msgid == None:
      self._room = room
      self._msgid = msgid
      self._room._msgs[msgid] = self
  
  def detach(self):
    """Detach the Message."""
    if self._msgid != None and self._msgid in self._room._msgs:
      del self._room._msgs[self._msgid]
      self._msgid = None
  
  ####
  # Init
  ####
  def __init__(self, **kw):
    self._msgid = None
    self._time = None
    self._user = None
    self._body = None
    self._room = None
    self._raw = ""
    self._ip = None
    self._unid = ""
    self._nameColor = "000"
    self._fontSize = 12
    self._fontFace = "0"
    self._fontColor = "000"
    for attr, val in kw.items():
      if val == None: continue
      setattr(self, "_" + attr, val)
  
  ####
  # Properties
  ####
  def getId(self): return self._msgid
  def getTime(self): return self._time
  def getUser(self): return self._user
  def getBody(self): return self._body
  def getIP(self): return self._ip
  def getFontColor(self): return self._fontColor
  def getFontFace(self): return self._fontFace
  def getFontSize(self): return self._fontSize
  def getNameColor(self): return self._nameColor
  def getRoom(self): return self._room
  def getRaw(self): return self._raw
  def getUnid(self): return self._unid
  
  msgid = property(getId)
  time = property(getTime)
  user = property(getUser)
  body = property(getBody)
  room = property(getRoom)
  ip = property(getIP)
  fontColor = property(getFontColor)
  fontFace = property(getFontFace)
  fontSize = property(getFontSize)
  raw = property(getRaw)
  nameColor = property(getNameColor)
  unid = property(getUnid)
