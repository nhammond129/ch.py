################################################################
# File: ch.py
# Title: Chatango Library
# Original Author: Lumirayz/Lumz <lumirayz@gmail.com>
# Current Maintainers and Contributors:
#  Nullspeaker <import codecs;codecs.encode('aunzzbaq129@tznvy.pbz','rot_13')>
#  asl97 <asl97@outlook.com>
#  pystub
#  dani87
#  domzy
#  kamijoutouma
#  piks
# Version: 1.3.8
# Description:
#  An event-based library for connecting to one or multiple Chatango rooms, has
#  support for several things including: messaging, message font,
#  name color, deleting, banning, recent history, 2 userlist modes,
#  flagging, avoiding flood bans, detecting flags.
# Contact Info:
#  Any question, comment, or suggestion should be directed to the current
#  maintainers and contributors, located at:
#   https://github.com/Nullspeaker/ch.py
#  Where a more satisfactory response to all bug reports (which can be made on the
#  issues page) and other statements can be garnered. For things not specific or
#  in direct reference to this library, 'ch.py', a direct response can be filed
#  to the individual persons listed above as 'Current Maintainers and Contributors.'
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
# Debug stuff
################################################################
debug = False

################################################################
# Python 2 compatibility
################################################################
if sys.version_info[0] < 3:
  class urllib:
    parse = __import__("urllib")
    request = __import__("urllib2")
  input = raw_input
  import codecs
  import Queue as queue
else:
  import queue
  import urllib.request
  import urllib.parse

################################################################
# Constants
################################################################
Userlist_Recent = 0
Userlist_All = 1

BigMessage_Multiple = 0
BigMessage_Cut = 1

# minimum of 1 thread needed
Number_of_Threads = 1
################################################################
# Struct class
################################################################
class Struct:
  def __init__(self, **entries):
    self.__dict__.update(entries)

################################################################
# Tagserver stuff
################################################################
specials = {'mitvcanal': 56, 'animeultimacom': 34, 'cricket365live': 21, 'pokemonepisodeorg': 22, 'animelinkz': 20, 'sport24lt': 56, 'narutowire': 10, 'watchanimeonn': 22, 'cricvid-hitcric-': 51, 'narutochatt': 70, 'leeplarp': 27, 'stream2watch3': 56, 'ttvsports': 56, 'ver-anime': 8, 'vipstand': 21, 'eafangames': 56, 'soccerjumbo': 21, 'myfoxdfw': 67, 'kiiiikiii': 21, 'de-livechat': 5, 'rgsmotrisport': 51, 'dbzepisodeorg': 10, 'watch-dragonball': 8, 'peliculas-flv': 69, 'tvanimefreak': 54, 'tvtvanimefreak': 54}
tsweights = [['5', 75], ['6', 75], ['7', 75], ['8', 75], ['16', 75], ['17', 75], ['18', 75], ['9', 95], ['11', 95], ['12', 95], ['13', 95], ['14', 95], ['15', 95], ['19', 110], ['23', 110], ['24', 110], ['25', 110], ['26', 110], ['28', 104], ['29', 104], ['30', 104], ['31', 104], ['32', 104], ['33', 104], ['35', 101], ['36', 101], ['37', 101], ['38', 101], ['39', 101], ['40', 101], ['41', 101], ['42', 101], ['43', 101], ['44', 101], ['45', 101], ['46', 101], ['47', 101], ['48', 101], ['49', 101], ['50', 101], ['52', 110], ['53', 110], ['55', 110], ['57', 110], ['58', 110], ['59', 110], ['60', 110], ['61', 110], ['62', 110], ['63', 110], ['64', 110], ['65', 110], ['66', 110], ['68', 95], ['71', 116], ['72', 116], ['73', 116], ['74', 116], ['75', 116], ['76', 116], ['77', 116], ['78', 116], ['79', 116], ['80', 116], ['81', 116], ['82', 116], ['83', 116], ['84', 116]]

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
def _genUid():
  """
  generate a uid
  """
  return str(random.randrange(10 ** 15, 10 ** 16))

################################################################
# Message stuff
################################################################
def _clean_message(msg):
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
  msg = _strip_html(msg)
  msg = msg.replace("&lt;", "<")
  msg = msg.replace("&gt;", ">")
  msg = msg.replace("&quot;", "\"")
  msg = msg.replace("&apos;", "'")
  msg = msg.replace("&amp;", "&")
  return msg, n, f

def _strip_html(msg):
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

def _parseNameColor(n):
  """This just returns its argument, should return the name color."""
  #probably is already the name
  return n

def _parseFont(f):
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
def _getAnonId(n, ssid):
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
# ANON PM class
################################################################

class _ANON_PM_OBJECT:
  """Manages connection with Chatango anon PM."""
  def __init__(self, mgr, name):
    self._connected = False
    self._mgr = mgr
    self._wlock = False
    self._firstCommand = True
    self._wbuf = b""
    self._wlockbuf = b""
    self._rbuf = b""
    self._pingTask = None
    self._name = name

  def _auth(self):
    self._sendCommand("mhs","mini","unknown","%s" % (self._name))
    self._setWriteLock(True)
    return True

  def disconnect(self):
    """Disconnect the bot from PM"""
    self._disconnect()
    self._callEvent("onAnonPMDisconnect", User(self._name))

  def _disconnect(self):
    self._connected = False
    self._sock.close()
    self._sock = None

  def ping(self):
    """send a ping"""
    self._sendCommand("")
    self._callEvent("onPMPing")

  def message(self, user, msg):
    """send a pm to a user"""
    if msg!=None:
      self._sendCommand("msg", user.name, msg)

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
        self._process(food.decode(errors="replace").rstrip("\r\n"))
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
    func = "_rcmd_" + cmd
    if hasattr(self, func):
      getattr(self, func)(args)
    else:
      if debug:
        print("unknown data: "+str(data))

  def _getManager(self): return self._mgr

  mgr = property(_getManager)

  ####
  # Received Commands
  ####

  def _rcmd_mhs(self, args):
    """
    note to future maintainers
    
    args[1] is ether "online" or "offline"
    """
    self._connected = True
    self._setWriteLock(False)

  def _rcmd_msg(self, args):
    user = User(args[0])
    body = _strip_html(":".join(args[5:]))
    self._callEvent("onPMMessage", user, body)

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

class ANON_PM:
  """Comparable wrapper for anon Chatango PM"""
  ####
  # Init
  ####
  def __init__(self, mgr):
    self._mgr = mgr
    self._wlock = False
    self._firstCommand = True
    self._persons = dict()
    self._wlockbuf = b""
    self._pingTask = None

  ####
  # Connections
  ####
  def _connect(self,name):
    self._persons[name] = _ANON_PM_OBJECT(self._mgr,name)
    sock = socket.socket()
    sock.connect((self._mgr._anonPMHost, self._mgr._PMPort))
    sock.setblocking(False)
    self._persons[name]._sock = sock
    if not self._persons[name]._auth(): return
    self._persons[name]._pingTask = self._mgr.setInterval(self._mgr._pingDelay, self._persons[name].ping)
    self._persons[name]._connected = True

  def message(self, user, msg):
    """send a pm to a user"""
    if not user.name in self._persons:
      self._connect(user.name)
    self._persons[user.name].message(user,msg)

  def getConnections(self):
    return list(self._persons.values())

################################################################
# PM class
################################################################
class PM:
  """Manages a connection with Chatango PM."""
  ####
  # Init
  ####
  def __init__(self, mgr):
    self._auth_re = re.compile(r"auth\.chatango\.com ?= ?([^;]*)", re.IGNORECASE)
    self._connected = False
    self._mgr = mgr
    self._auid = None
    self._blocklist = set()
    self._contacts = set()
    self._status = dict()
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


  def _getAuth(self, name, password):
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
        m = self._auth_re.search(value)
        if m:
          auth = m.group(1)
          if auth == "":
            return None
          return auth
    return None

  def _auth(self):
    self._auid = self._getAuth(self._mgr.name, self._mgr.password)
    if self._auid == None:
      self._sock.close()
      self._callEvent("onLoginFail")
      self._sock = None
      return False
    self._sendCommand("tlogin", self._auid, "2")
    self._setWriteLock(True)
    return True

  def disconnect(self):
    """Disconnect the bot from PM"""
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
        self._process(food.decode(errors="replace").rstrip("\r\n"))
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
    func = "_rcmd_" + cmd
    if hasattr(self, func):
      getattr(self, func)(args)
    else:
      if debug:
        print("unknown data: "+str(data))

  ####
  # Properties
  ####
  def _getManager(self): return self._mgr
  def _getContacts(self): return self._contacts
  def _getBlocklist(self): return self._blocklist

  mgr = property(_getManager)
  contacts = property(_getContacts)
  blocklist = property(_getBlocklist)

  ####
  # Received Commands
  ####
  def _rcmd_OK(self, args):
    self._setWriteLock(False)
    self._sendCommand("wl")
    self._sendCommand("getblock")
    self._callEvent("onPMConnect")

  def _rcmd_wl(self, args):
    self._contacts = set()
    for i in range(len(args) // 4):
      name, last_on, is_on, idle = args[i * 4: i * 4 + 4]
      user = User(name)
      if last_on=="None":pass#in case chatango gives a "None" as data argument
      elif not is_on == "on": self._status[user] = [int(last_on), False, 0]
      elif idle == '0': self._status[user] = [int(last_on), True, 0]
      else: self._status[user] = [int(last_on), True, time.time() - int(idle) * 60]
      self._contacts.add(user)
    self._callEvent("onPMContactlistReceive")

  def _rcmd_block_list(self, args):
    self._blocklist = set()
    for name in args:
      if name == "": continue
      self._blocklist.add(User(name))

  def _rcmd_idleupdate(self, args):
    user = User(args[0])
    last_on, is_on, idle = self._status[user]
    if args[1] == '1':
      self._status[user] = [last_on, is_on, 0]
    else:
      self._status[user] = [last_on, is_on, time.time()]

  def _rcmd_track(self, args):
    user = User(args[0])
    if user in self._status:
      last_on = self._status[user][0]
    else:
      last_on = 0
    if args[1] == '0':
      idle = 0
    else:
      idle = time.time() - int(args[1]) * 60
    if args[2] == "online":
      is_on = True
    else:
      is_on = False
    self._status[user] = [last_on, is_on, idle]

  def _rcmd_DENIED(self, args):
    self._disconnect()
    self._callEvent("onLoginFail")

  def _rcmd_msg(self, args):
    user = User(args[0])
    body = _strip_html(":".join(args[5:]))
    self._callEvent("onPMMessage", user, body)

  def _rcmd_msgoff(self, args):
    user = User(args[0])
    body = _strip_html(":".join(args[5:]))
    self._callEvent("onPMOfflineMessage", user, body)

  def _rcmd_wlonline(self, args):
    user = User(args[0])
    last_on = float(args[1])
    self._status[user] = [last_on,True,last_on]
    self._callEvent("onPMContactOnline", user)

  def _rcmd_wloffline(self, args):
    user = User(args[0])
    last_on = float(args[1])
    self._status[user] = [last_on,False,0]
    self._callEvent("onPMContactOffline", user)

  def _rcmd_kickingoff(self, args):
    self.disconnect()

  def _rcmd_toofast(self, args):
    self.disconnect()

  def _rcmd_unblocked(self, user):
    """call when successfully unblocked"""
    if user in self._blocklist:
      self._blocklist.remove(user)
      self._callEvent("onPMUnblock", user)


  ####
  # Commands
  ####
  def ping(self):
    """send a ping"""
    self._sendCommand("")
    self._callEvent("onPMPing")

  def message(self, user, msg):
    """send a pm to a user"""
    if msg!=None:
      self._sendCommand("msg", user.name, msg)

  def addContact(self, user):
    """add contact"""
    if user not in self._contacts:
      self._sendCommand("wladd", user.name)
      self._contacts.add(user)
      self._callEvent("onPMContactAdd", user)

  def removeContact(self, user):
    """remove contact"""
    if user in self._contacts:
      self._sendCommand("wldelete", user.name)
      self._contacts.remove(user)
      self._callEvent("onPMContactRemove", user)

  def block(self, user):
    """block a person"""
    if user not in self._blocklist:
      self._sendCommand("block", user.name, user.name, "S")
      self._blocklist.add(user)
      self._callEvent("onPMBlock", user)

  def unblock(self, user):
    """unblock a person"""
    if user in self._blocklist:
      self._sendCommand("unblock", user.name)

  def track(self, user):
    """get and store status of person for future use"""
    self._sendCommand("track", user.name)

  def checkOnline(self, user):
    """return True if online, False if offline, None if unknown"""
    if user in self._status:
      return self._status[user][1]
    else:
      return None

  def getIdle(self, user):
    """return last active time, time.time() if isn't idle, 0 if offline, None if unknown"""
    if not user in self._status: return None
    if not self._status[user][1]: return 0
    if not self._status[user][2]: return time.time()
    else: return self._status[user][2]

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

  def getConnections(self):
    return [self]

################################################################
# Room class
################################################################
class Room:
  """Manages a connection with a Chatango room."""
  ####
  # Init
  ####
  def __init__(self, room, uid = None, server = None, port = None, mgr = None):
    """init, don't overwrite"""
    # Basic stuff
    self._name = room
    self._server = server or getServer(room)
    self._port = port or 443
    self._mgr = mgr

    # Under the hood
    self._connected = False
    self._reconnecting = False
    self._uid = uid or _genUid()
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
    self._botname = None
    self._currentname = None
    self._users = dict()
    self._msgs = dict()
    self._wlock = False
    self._silent = False
    self._banlist = dict()
    self._unbanlist = dict()

    # Inited vars
    if self._mgr: self._connect()

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
    self._uid = _genUid()
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
      self._currentname = self.mgr.name
    # login as anon
    else:
      self._sendCommand("bauth", self.name)

    self._setWriteLock(True)

  ####
  # Properties
  ####
  def _getName(self): return self._name
  def _getBotName(self):
    if self.mgr.name and self.mgr.password:
      return self.mgr.name
    elif self.mgr.name and self.mgr.password == None:
      return "#" + self.mgr.name
    elif self.mgr.name == None:
      return self._botname
  def _getCurrentname(self): return self._currentname
  def _getManager(self): return self._mgr
  def _getUserlist(self, mode = None, unique = None, memory = None):
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
  def _getUserNames(self):
    ul = self.userlist
    return list(map(lambda x: x.name, ul))
  def _getUser(self): return self.mgr.user
  def _getOwner(self): return self._owner
  def _getOwnerName(self): return self._owner.name
  def _getMods(self):
    newset = set()
    for mod in self._mods:
      newset.add(mod)
    return newset
  def _getModNames(self):
    mods = self._getMods()
    return [x.name for x in mods]
  def _getUserCount(self): return self._userCount
  def _getSilent(self): return self._silent
  def _setSilent(self, val): self._silent = val
  def _getBanlist(self): return list(self._banlist.keys())
  def _getUnBanlist(self): return [[record["target"], record["src"]] for record in self._unbanlist.values()]

  name = property(_getName)
  botname = property(_getBotName)
  currentname = property(_getCurrentname)
  mgr = property(_getManager)
  userlist = property(_getUserlist)
  usernames = property(_getUserNames)
  user = property(_getUser)
  owner = property(_getOwner)
  ownername = property(_getOwnerName)
  mods = property(_getMods)
  modnames = property(_getModNames)
  usercount = property(_getUserCount)
  silent = property(_getSilent, _setSilent)
  banlist = property(_getBanlist)
  unbanlist = property(_getUnBanlist)

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
        self._process(food.decode(errors="replace").rstrip("\r\n"))
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
    func = "_rcmd_" + cmd
    if hasattr(self, func):
      getattr(self, func)(args)
    else:
      if debug:
        print("unknown data: "+str(data))

  ####
  # Received Commands
  ####
  def _rcmd_ok(self, args):
    # if no name, join room as anon and no password
    if args[2] == "N" and self.mgr.password == None and self.mgr.name == None:
      n = args[4].rsplit('.', 1)[0]
      n = n[-4:]
      aid = args[1][0:8]
      pid = "!anon" + _getAnonId(n, aid)
      self._botname = pid
      self._currentname = pid
      self.user._nameColor = n
    # if got name, join room as name and no password
    elif args[2] == "N" and self.mgr.password == None:
      self._sendCommand("blogin", self.mgr.name)
      self._currentname = self.mgr.name
    # if got password but fail to login
    elif args[2] != "M": #unsuccesful login
      self._callEvent("onLoginFail")
      self.disconnect()
    self._owner = User(args[0])
    self._uid = args[1]
    self._aid = args[1][4:8]
    self._mods = set(map(lambda x: User(x.split(",")[0]), args[6].split(";")))
    self._i_log = list()

  def _rcmd_denied(self, args):
    self._disconnect()
    self._callEvent("onConnectFail")

  def _rcmd_inited(self, args):
    self._sendCommand("g_participants", "start")
    self._sendCommand("getpremium", "1")
    self.requestBanlist()
    self.requestUnBanlist()
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

  def _rcmd_premium(self, args):
    if float(args[1]) > time.time():
      self._premium = True
      if self.user._mbg: self.setBgMode(1)
      if self.user._mrec: self.setRecordingMode(1)
    else:
      self._premium = False

  def _rcmd_mods(self, args):
    modnames = args
    mods = set(map(lambda x: User(x.split(",")[0]), modnames))
    premods = self._mods
    for user in mods - premods: #modded
      self._mods.add(user)
      self._callEvent("onModAdd", user)
    for user in premods - mods: #demodded
      self._mods.remove(user)
      self._callEvent("onModRemove", user)
    self._callEvent("onModChange")

  def _rcmd_b(self, args):
    mtime = float(args[0])
    puid = args[3]
    ip = args[6]
    name = args[1]
    rawmsg = ":".join(args[9:])
    msg, n, f = _clean_message(rawmsg)
    if name == "":
      nameColor = None
      name = "#" + args[2]
      if name == "#":
        name = "!anon" + _getAnonId(n, puid)
    else:
      if n: nameColor = _parseNameColor(n)
      else: nameColor = None
    i = args[5]
    unid = args[4]
    user = User(name)
    #Create an anonymous message and queue it because msgid is unknown.
    if f: fontColor, fontFace, fontSize = _parseFont(f)
    else: fontColor, fontFace, fontSize = None, None, None
    msg = Message(
      time = mtime,
      user = user,
      body = msg,
      raw = rawmsg,
      ip = ip,
      nameColor = nameColor,
      fontColor = fontColor,
      fontFace = fontFace,
      fontSize = fontSize,
      unid = unid,
      puid = puid,
      room = self
    )
    self._mqueue[i] = msg

  def _rcmd_u(self, args):
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

  def _rcmd_i(self, args):
    mtime = float(args[0])
    puid = args[3]
    ip = args[6]
    name = args[1]
    rawmsg = ":".join(args[9:])
    msg, n, f = _clean_message(rawmsg)
    if name == "":
      nameColor = None
      name = "#" + args[2]
      if name == "#":
        name = "!anon" + _getAnonId(n, puid)
    else:
      if n: nameColor = _parseNameColor(n)
      else: nameColor = None
    i = args[5]
    unid = args[4]
    user = User(name)
    #Create an anonymous message and queue it because msgid is unknown.
    if f: fontColor, fontFace, fontSize = _parseFont(f)
    else: fontColor, fontFace, fontSize = None, None, None
    msg = Message(
      time = mtime,
      user = user,
      body = msg,
      raw = rawmsg,
      ip = ip,
      nameColor = nameColor,
      fontColor = fontColor,
      fontFace = fontFace,
      fontSize = fontSize,
      unid = unid,
      puid = puid,
      room = self
    )
    self._i_log.append(msg)

  def _rcmd_g_participants(self, args):
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

  def _rcmd_participant(self, args):
    name = args[3].lower()
    if name == "none": return
    user = User(name)
    puid = args[2]

    if args[0] == "0": #leave
      user.removeSessionId(self, args[1])
      self._userlist.remove(user)
      if user not in self._userlist or not self.mgr._userlistEventUnique:
        self._callEvent("onLeave", user, puid)
    else: #join
      user.addSessionId(self, args[1])
      if user not in self._userlist: doEvent = True
      else: doEvent = False
      self._userlist.append(user)
      if doEvent or not self.mgr._userlistEventUnique:
        self._callEvent("onJoin", user, puid)

  def _rcmd_show_fw(self, args):
    self._callEvent("onFloodWarning")

  def _rcmd_show_tb(self, args):
    self._callEvent("onFloodBan")

  def _rcmd_tb(self, args):
    self._callEvent("onFloodBanRepeat")

  def _rcmd_delete(self, args):
    msg = self._msgs.get(args[0])
    if msg:
      if msg in self._history:
        self._history.remove(msg)
        self._callEvent("onMessageDelete", msg.user, msg)
        msg.detach()

  def _rcmd_deleteall(self, args):
    for msgid in args:
      self._rcmd_delete([msgid])

  def _rcmd_n(self, args):
    self._userCount = int(args[0], 16)
    self._callEvent("onUserCountChange")

  def _rcmd_blocklist(self, args):
    self._banlist = dict()
    sections = ":".join(args).split(";")
    for section in sections:
      params = section.split(":")
      if len(params) != 5: continue
      if params[2] == "": continue
      user = User(params[2])
      self._banlist[user] = {
        "unid":params[0],
        "ip":params[1],
        "target":user,
        "time":float(params[3]),
        "src":User(params[4])
      }
    self._callEvent("onBanlistUpdate")

  def _rcmd_unblocklist(self, args):
    self._unbanlist = dict()
    sections = ":".join(args).split(";")
    for section in sections:
      params = section.split(":")
      if len(params) != 5: continue
      if params[2] == "": continue
      user = User(params[2])
      self._unbanlist[user] = {
        "unid":params[0],
        "ip":params[1],
        "target":user,
        "time":float(params[3]),
        "src":User(params[4])
      }
    self._callEvent("onUnBanlistUpdate")

  def _rcmd_blocked(self, args):
    if args[2] == "": return
    target = User(args[2])
    user = User(args[3])
    self._banlist[target] = {"unid":args[0], "ip":args[1], "target":target, "time":float(args[4]), "src":user}
    self._callEvent("onBan", user, target)

  def _rcmd_unblocked(self, args):
    if args[2] == "": return
    target = User(args[2])
    user=User(args[3])
    del self._banlist[target]
    self._unbanlist[user] = {"unid":args[0], "ip":args[1], "target":target, "time":float(args[4]), "src":user}
    self._callEvent("onUnban", user, target)

  ####
  # Commands
  ####
  def login(self, NAME, PASS = None):
    """login as a user or set a name in room"""
    if PASS:
      self._sendCommand("blogin", NAME, PASS)
    else:
      self._sendCommand("blogin", NAME)
    self._currentname = NAME

  def logout(self):
    """logout of user in a room"""
    self._sendCommand("blogout")
    self._currentname = self._botname

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
    Send a message. (Use "\n" for new line)

    @type msg: str
    @param msg: message
    """
    if msg==None:
      return
    msg = msg.rstrip()
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
    if self._currentname != None and not self._currentname.startswith("!anon"):
      font_properties = "<f x%0.2i%s=\"%s\">" %(self.user.fontSize, self.user.fontColor, self.user.fontFace)
      if "\n" in msg:
        msg.replace("\n", "</f></p><p>%s" %(font_properties))
      msg = font_properties + msg
    msg.replace("~","&#126;")
    self.rawMessage(msg)

  def setBgMode(self, mode):
    """turn on/off bg"""
    self._sendCommand("msgbg", str(mode))

  def setRecordingMode(self, mode):
    """turn on/off rcecording"""
    self._sendCommand("msgmedia", str(mode))

  def addMod(self, user):
    """
    Add a moderator.

    @type user: User
    @param user: User to mod.
    """
    if self.getLevel(User(self.currentname)) == 2:
      self._sendCommand("addmod", user.name)

  def removeMod(self, user):
    """
    Remove a moderator.

    @type user: User
    @param user: User to demod.
    """
    if self.getLevel(User(self.currentname)) == 2:
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

  def deleteMessage(self, message):
    """
    Delete a message. (Moderator only)

    @type message: Message
    @param message: message to delete
    """
    if self.getLevel(self.user) > 0:
      self._sendCommand("delmsg", message.msgid)

  def deleteUser(self, user):
    """
    Delete a message. (Moderator only)

    @type message: User
    @param message: delete user's last message
    """
    if self.getLevel(self.user) > 0:
      msg = self.getLastMessage(user)
      if msg:
        self._sendCommand("delmsg", msg.msgid)
      return True
    return False

  def delete(self, message):
    """
    compatibility wrapper for deleteMessage
    """
    print("[obsolete] the delete function is obsolete, please use deleteMessage")
    return self.deleteMessage(message)

  def rawClearUser(self, unid, ip, user):
    self._sendCommand("delallmsg", unid, ip, user)
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
        if msg.user.name[0] in ["!","#"]:self.rawClearUser(msg.unid, msg.ip,"")
        else:self.rawClearUser(msg.unid,msg.ip,msg.user.name)
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

  def requestUnBanlist(self):
    """Request an updated banlist."""
    self._sendCommand("blocklist", "unblock", "", "next", "500")

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
      self.rawUnban(rec["target"].name, rec["ip"], rec["unid"])
      return True
    else:
      return False

  ####
  # Util
  ####
  def _getBanRecord(self, user):
    if user in self._banlist:
      return self._banlist[user]
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
    """get the level of user in a room"""
    if user == self._owner: return 2
    if user.name in self.modnames: return 1
    return 0

  def getLastMessage(self, user = None):
    """get last message said by user in a room"""
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
    """check if user is in the room
    
    return User(name) if name in room else None"""
    name = name.lower()
    ul = self._getUserlist()
    udi = dict(zip([u.name for u in ul], ul))
    cname = None
    for n in udi.keys():
      if name in n:
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
  _ANON_PM = ANON_PM
  _anonPMHost = "b1.chatango.com"
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
    self._rooms_queue = queue.Queue()
    self._rooms_lock = threading.Lock()
    if pm:
      if self._password:
        self._pm = self._PM(mgr = self)
      else:
        self._pm = self._ANON_PM(mgr = self)
    else:
      self._pm = None

  def _joinThread(self):
    while True:
      room = self._rooms_queue.get()
      with self._rooms_lock:
        con = self._Room(room, mgr = self)
        self._rooms[room] = con

  ####
  # Join/leave
  ####
  def joinRoom(self, room):
    """
    Join a room or return None if already joined.

    @type room: str
    @param room: room to join

    @rtype: Room or None
    @return: True or nothing
    """
    room = room.lower()
    if room not in self._rooms:
      self._rooms_queue.put(room)
      return True
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
      with self._rooms_lock:
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
  def _getUser(self): return User(self._name)
  def _getName(self): return self._name
  def _getPassword(self): return self._password
  def _getRooms(self): return set(self._rooms.values())
  def _getRoomNames(self): return set(self._rooms.keys())
  def _getPM(self): return self._pm

  user = property(_getUser)
  name = property(_getName)
  password = property(_getPassword)
  rooms = property(_getRooms)
  roomnames = property(_getRoomNames)
  pm = property(_getPM)

  ####
  # Virtual methods
  ####
  def onInit(self):
    """Called on init."""
    pass

  def safePrint(self, text):
    """Use this to safely print text with unicode"""
    while True:
      try:
        print(text)
        break
      except UnicodeEncodeError as ex:
        text = (text[0:ex.start]+'(unicode)'+text[ex.end:])

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

  def onJoin(self, room, user, puid):
    """
    Called when a user joins. Anonymous users get ignored here.

    @type room: Room
    @param room: room where the event occured
    @type user: User
    @param user: the user that has joined
    @type puid: str
    @param puid: the personal unique id for the user
    """
    pass

  def onLeave(self, room, user, puid):
    """
    Called when a user leaves. Anonymous users get ignored here.

    @type room: Room
    @param room: room where the event occured
    @type user: User
    @param user: the user that has left
    @type puid: str
    @param puid: the personal unique id for the user
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

  def onUnBanlistUpdate(self, room):
    """
    Called when a unbanlist gets updated.

    @type room: Room
    @param room: room where the event occured
    """
    pass

  def onPMConnect(self, pm):
    """
    Called when connected to the pm
    
    @type pm: PM
    @param pm: the pm
    """
    pass

  def onAnonPMDisconnect(self, pm, user):
    """
    Called when disconnected from the pm
    
    @type pm: PM
    @param pm: the pm
    """
    pass

  def onPMDisconnect(self, pm):
    """
    Called when disconnected from the pm
    
    @type pm: PM
    @param pm: the pm
    """
    pass

  def onPMPing(self, pm):
    """
    Called when sending a ping to the pm
    
    @type pm: PM
    @param pm: the pm
    """
    pass

  def onPMMessage(self, pm, user, body):
    """
    Called when a message is received
    
    @type pm: PM
    @param pm: the pm
    @type user: User
    @param user: owner of message
    @type message: Message
    @param message: received message
    """
    pass

  def onPMOfflineMessage(self, pm, user, body):
    """
    Called when connected if a message is received while offline
    
    @type pm: PM
    @param pm: the pm
    @type user: User
    @param user: owner of message
    @type message: Message
    @param message: received message
    """
    pass

  def onPMContactlistReceive(self, pm):
    """
    Called when the contact list is received
    
    @type pm: PM
    @param pm: the pm
    """
    pass

  def onPMBlocklistReceive(self, pm):
    """
    Called when the block list is received
    
    @type pm: PM
    @param pm: the pm
    """
    pass

  def onPMContactAdd(self, pm, user):
    """
    Called when the contact added message is received
    
    @type pm: PM
    @param pm: the pm
    @type user: User
    @param user: the user that gotten added
    """
    pass

  def onPMContactRemove(self, pm, user):
    """
    Called when the contact remove message is received
    
    @type pm: PM
    @param pm: the pm
    @type user: User
    @param user: the user that gotten remove
    """
    pass

  def onPMBlock(self, pm, user):
    """
    Called when successfully block a user
    
    @type pm: PM
    @param pm: the pm
    @type user: User
    @param user: the user that gotten block
    """
    pass

  def onPMUnblock(self, pm, user):
    """
    Called when successfully unblock a user
    
    @type pm: PM
    @param pm: the pm
    @type user: User
    @param user: the user that gotten unblock
    """
    pass

  def onPMContactOnline(self, pm, user):
    """
    Called when a user from the contact come online
    
    @type pm: PM
    @param pm: the pm
    @type user: User
    @param user: the user that came online
    """
    pass

  def onPMContactOffline(self, pm, user):
    """
    Called when a user from the contact go offline
    
    @type pm: PM
    @param pm: the pm
    @type user: User
    @param user: the user that went offline
    """
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
      li.extend(self._pm.getConnections())
    return [c for c in li if c._sock != None]

  ####
  # Main
  ####
  def main(self):
    self.onInit()
    self._running = True
    for l in range(0,Number_of_Threads):
      t = threading.Thread(target=self._joinThread)
      t.daemon = True
      t.start()
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
  def _getName(self): return self._name
  def _getSessionIds(self, room = None):
    if room:
      return self._sids.get(room, set())
    else:
      return set.union(*self._sids.values())
  def _getRooms(self): return self._sids.keys()
  def _getRoomNames(self): return [room.name for room in self._getRooms()]
  def _getFontColor(self): return self._fontColor
  def _getFontFace(self): return self._fontFace
  def _getFontSize(self): return self._fontSize
  def _getNameColor(self): return self._nameColor

  name = property(_getName)
  sessionids = property(_getSessionIds)
  rooms = property(_getRooms)
  roomnames = property(_getRoomNames)
  fontColor = property(_getFontColor)
  fontFace = property(_getFontFace)
  fontSize = property(_getFontSize)
  nameColor = property(_getNameColor)

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

  def delete(self):
    self._room.deleteMessage(self)

  ####
  # Init
  ####
  def __init__(self, **kw):
    """init, don't overwrite"""
    self._msgid = None
    self._time = None
    self._user = None
    self._body = None
    self._room = None
    self._raw = ""
    self._ip = None
    self._unid = ""
    self._puid = ""
    self._uid = ""
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
  def _getId(self): return self._msgid
  def _getTime(self): return self._time
  def _getUser(self): return self._user
  def _getBody(self): return self._body
  def _getIP(self): return self._ip
  def _getFontColor(self): return self._fontColor
  def _getFontFace(self): return self._fontFace
  def _getFontSize(self): return self._fontSize
  def _getNameColor(self): return self._nameColor
  def _getRoom(self): return self._room
  def _getRaw(self): return self._raw
  def _getUnid(self): return self._unid
  def _getPuid(self): return self._puid

  msgid = property(_getId)
  time = property(_getTime)
  user = property(_getUser)
  body = property(_getBody)
  room = property(_getRoom)
  ip = property(_getIP)
  fontColor = property(_getFontColor)
  fontFace = property(_getFontFace)
  fontSize = property(_getFontSize)
  raw = property(_getRaw)
  nameColor = property(_getNameColor)
  unid = property(_getUnid)
  puid = property(_getPuid)
  uid = property(_getPuid) # other library use uid so we create an alias
