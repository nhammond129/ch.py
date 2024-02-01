r"""
################################################################
# File: ch.py
# Title: Chatango Library
# Original Author: Lumirayz/Lumz <lumirayz@gmail.com>
# Current Maintainers and Contributors:
#   asl97 <asl97@outlook.com>
# Past Maintainers and Contributors:
#   Nullspeaker <import codecs;codecs.encode('aunzzbaq129@tznvy.pbz','rot_13')>
#   pystub
#   dani87
#   domzy
#   kamijoutouma
#   piks
# Version: pre-1.4.0
# Changelog:
#   pre-1.4.0:
#       * Generalize handling of Room and PM into Conn like object - asl97
#           - for easier to support other platform other than chatango - asl97
#       * Improve buffer performance by using bytearrays in place of bytes in places - asl97
#           - Update the buffer in-place whenever possible
#       * General assumed performance improvement of miscellaneous functions  - asl97
#       * Close the bot when not connected to anything with no pending task or running thread via deferToThread
#           - New task/room/output usually only get added due to input via select.select, existing tasks or deferToThread, they don't magically appear except when people mess with threading
#           \
#           Use the newly added flag as shown in example.py
#           `disconnectOnEmptyConnAndTask = False`
#           \
#           for old behavior of pointlessly checking every 0.2 seconds by default \- asl97
#       * Use deterministic waiting for tasks in main loop - asl97
#       * No more joinThread nonsense, Fixes joinRoom to returns Room Object again
#       - Seem to work fine when testing connecting to 15 rooms at once \- asl97
#       * Mostly cleaning up my mess and modernizing the code base - asl97
#       * Python 2 is no longer supported for good, it's EoL since 2020 - asl97
# Description:
#   A mostly abandoned event-based library for connecting
#   to one or multiple Chatango rooms, has support for several things
#   including: messaging, message font, name color, deleting, banning,
#   recent history, 2 userlist modes, flagging, avoiding flood bans,
#   detecting flags.
# Contact Info:
#   Any question, comment, or suggestion should be directed to the current
#   maintainers and contributors, located at:
#   https://github.com/Nullspeaker/ch.py
################################################################
""" # noqa

################################################################
# License
################################################################
# Copyright 2011 Lumirayz
# This program is distributed under the terms of the GNU GPL.

################################################################
# Imports
################################################################
from __future__ import annotations
from typing import Any, Generator, Protocol, Self, Callable, Optional
import typing
import enum

import socket
import threading
import time
import random
import re
import select
import urllib.request
import urllib.parse
import urllib.error
import bisect
import heapq
import html as _html

from .ch_weights import specials, tsweights  # pylint: disable=E0401


################################################################
# Debug stuff
################################################################
debug = False


################################################################
# Constants
################################################################
class Userlist_Mode(enum.Enum):
    Recent = 1
    All = 2


class BigMessage_Mode(enum.Enum):
    Multiple = 1
    Cut = 2


class BanRecord(typing.NamedTuple):
    unid: str
    ip: str
    target: User
    time: float
    src: User


################################################################
# Tag server stuff
################################################################
# generate a more efficient data structure from tsweights,
# improve `_getServer` performance by 10x
ts_sum = sum(x[1] for x in tsweights)
ts_server: list[str] = []
ts_freq: list[float] = []
freq = 0.0
for server, weight in tsweights:
    ts_server.append(server)
    freq += weight/ts_sum
    ts_freq.append(freq)
del freq


def _getServer(group: str):
    group = group.replace("_", "q")
    group = group.replace("-", "q")
    fnv = int(group[0:5], 36)
    lnv = max(int(group[6:9], 36), 1000) if len(group) > 6 else 1000
    num = (fnv / lnv) % 1

    return ts_server[bisect.bisect_left(ts_freq, num)]


def getServer(group: str) -> str:
    """
    Get the server host for a certain room.

    @param group: room name

    @return: the server's hostname
    """
    return "s" + str(specials.get(group, _getServer(group))) + ".chatango.com"


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
def _clean_message(msg: str) -> tuple[str, str, str]:
    """
    Clean a message and return the message, n tag and f tag.

    @param msg: the message

    @returns: cleaned message, n tag contents, f tag contents
    """
    n = (r := re.search("<n(.*?)/>", msg)) and r.group(1) or ""
    f = (r := re.search("<f(.*?)>", msg)) and r.group(1) or ""
    msg = _strip_html(msg)
    msg = _html.unescape(msg)
    msg = msg.strip()
    return msg, n, f


def _strip_html(msg: str):
    """Strip HTML."""
    return re.sub("<.*?>", "", msg)


def _parseNameColor(n: str):
    """This just returns its argument, should return the name color."""
    # probably is already the name
    return n


font_re = re.compile(r'x(\d{2})s?(.{0,6})="(.*?)"')


def _parseFont(f: str):
    """Parses the contents of a f tag and returns color, face and size."""
    # 'xSZCOL="FONT"'
    if (r := font_re.search(f)):
        return r.groups()
    else:
        return "", "", ""


################################################################
# Anon id
################################################################
def _getAnonId(n: str, ssid: str) -> str:
    """
    Gets the anon's id.

    # Sum each digit together, get first digit of each sum
    n        = 1297
    ssid[4:] = 4368
    anonid   = 5555

    1: 1+4=5
    2: 2+3=5
    3: 9+6=15, '15'[-1] = '5'
    4: 7+8=15, '15'[-1] = '5'

    @param n: server given id
    @param ssid: session id

    @return: the anon number
    """
    try:
        # if n is None, default to "5504", from original code
        return "".join(str(int(a) + int(b))[-1] for a, b in zip(n or "5504", ssid[4:]))
    except ValueError:
        return "NNNN"


################################################################
# User class
################################################################
class User:
    """Class that represents a user."""

    _users: dict[str, Self] = dict()

    def __new__(cls, name: str, **_kw: ...) -> Self:
        """Return existing User Object for given user name"""
        lname = name.lower()
        if lname not in cls._users:
            cls._users[lname] = super().__new__(cls)
        return cls._users[lname]

    ####
    # Init
    ####
    def __init__(self, name: str, **kw: ...):
        self.name = name.lower()
        self.sids: dict[Room, set[str]] = dict()
        self.msgs: list[Message] = list()
        self.nameColor = "000"
        self.fontSize = "12"
        self.fontFace = "0"
        self.fontColor = "000"
        self.mbg = False
        self.mrec = False
        for attr, val in kw.items():
            # Avoid overriding existing val with None
            if val is not None:
                setattr(self, attr, val)

    ####
    # Properties
    ####
    def getSessionIds(self, room: Optional[Room] = None) -> set[str]:
        if room:
            return self.sids.get(room, set())
        elif (sids := self.sids.values()):
            # check that we actually have some data.
            # set.union will crash without args

            # type checking doesn't like that the set.union return unknown
            # explicitly create a set with the expected typing
            output: set[str] = set()
            return output.union(*sids)
        else:
            return set()

    @property
    def rooms(self): return list(self.sids.keys())

    @property
    def roomnames(self): return [room.name for room in self.rooms]

    sessionids = property(getSessionIds)

    ####
    # Util
    ####
    def addSessionId(self, room: Room, sid: str):
        if room not in self.sids:
            self.sids[room] = set()
        self.sids[room].add(sid)

    def removeSessionId(self, room: Room, sid: str):
        try:
            self.sids[room].remove(sid)
            if len(self.sids[room]) == 0:
                del self.sids[room]
        except KeyError:
            pass

    def clearSessionIds(self, room: Room):
        try:
            del self.sids[room]
        except KeyError:
            pass

    def hasSessionId(self, room: Room | None, sid: str):
        return sid in self.getSessionIds(room)

    def addMessage(self, msg: Message):
        self.msgs.append(msg)

    def clearMessages(self):
        self.msgs.clear()

    ####
    # Repr
    ####
    def __repr__(self):
        return f"<User: {self.name}>"


################################################################
# Message class
################################################################
class Message:
    """Class that represents a message."""
    ####
    # Attach/detach
    ####
    def attach(self, room: Room, msgid: str):
        """
        Attach the Message to a message id.

        @param room: the room that the message originated from
        @param msgid: message id
        """
        if self.msgid is None:
            self.room = room
            self.msgid = msgid
            self.room.msgs[msgid] = self

    def detach(self):
        """Detach the Message."""
        if self.msgid is not None and self.msgid in self.room.msgs:
            del self.room.msgs[self.msgid]
            self.msgid = None

    def delete(self):
        self.room.deleteMessage(self)

    ####
    # Init
    ####
    def __init__(self, /, timestamp: float, user: User, body: str, raw: str, ip: str,
                 nameColor: str | None, fontColor: str | None, fontFace: str | None,
                 fontSize: str | None, unid: str, puid: str, room: Room | PM, **kw: ...):
        """init, don't overwrite"""
        self.msgid: Optional[str] = None
        self.time = timestamp
        self.user = user
        self.body = body
        self.raw = raw
        self.ip = ip
        self.nameColor = nameColor or "000"
        self.fontColor = fontColor or "000"
        self.fontFace = fontFace or "0"
        self.fontSize = fontSize or "11"
        self.unid = unid
        self.puid = puid
        self.room = room
        for attr, val in kw.items():
            # Avoid overriding existing val with None
            if val is not None:
                setattr(self, attr, val)

    ####
    # Properties
    ####
    @property
    def uid(self): return self.puid  # other library use uid so we create an alias


class Task:
    """
    Better Deterministic Task Manager using Heapq
    """
    _tasks_queue:  list[tuple[float, int, Task]] = []
    _tasks_once: set[Task] = set()
    _tasks: set[Task] = set()
    # Task counter/id to serve as tie breaker
    # if there are multiple conflicting time target
    _counter: int = 0

    # for getting size of task queue by keeping track of count of canceled task
    _removed: int = 0

    running_task: None | Task = None

    def __init__(self, mgr: RoomManager, timeout: int, func: Callable[..., None],
                 isInterval: bool, args: ..., kw: ...):
        Task._counter += 1

        self.mgr = mgr
        self.target = time.time() + timeout
        self.counter = Task._counter
        self.timeout = timeout
        self.func = func
        self.isInterval = isInterval
        self.args = args
        self.kw = kw
        self.cancelled = False

        if timeout < 0:
            self.queued = True
            if isInterval:
                Task._tasks.add(self)
            else:
                Task._tasks_once.add(self)
        else:
            self.queued = False
            self.queue()

    def cancel(self):
        """
        Mark task as canceled without removing from the list

        Because removing from the list would require reheapifying the list
        """
        Task._removed += 1
        self.cancelled = True

    def queue(self):
        """
        A helper function for queuing the task into the task queue
        """
        if not self.queued:
            self.queued = True
            heapq.heappush(Task._tasks_queue, (self.target, self.counter, self))

    def size(self):
        """Return the number of task queued, excluding cancelled task"""
        return len(Task._tasks_queue) + len(Task._tasks) + len(Task._tasks_once) - Task._removed  # noqa: E501

    # TODO: figure out if there a naming convention for iter/yield function name
    # like there is for length, queue.qsize
    @staticmethod
    def _yield_tasks(now: float) -> Generator[Task, None, None]:
        """Yield the overdue tasks"""
        while Task._tasks_queue and (Task._tasks_queue[0][0] <= now or
                                     Task._tasks_queue[0][2].cancelled):
            _target, _counter, task = heapq.heappop(Task._tasks_queue)
            task.queued = False
            yield task

        # We don't set the queued to False for `run on next tick` tasks
        # so it doesn't get added to the regular queue
        yield from Task._tasks

        yield from Task._tasks_once
        Task._tasks_once.clear()

    @staticmethod
    def get_next_tick_target() -> float | None:
        while Task._tasks_queue:
            target, _tid, task = Task._tasks_queue[0]
            if task.cancelled:
                heapq.heappop(Task._tasks_queue)
                continue
            return target

    @staticmethod
    def tick() -> float | None:
        """
        Process the tasks

        @return: time in seconds to the next task or None if no task
        """
        # TODO: Add performance related data gathering and warning if a task took too long
        now = time.time()
        tasks: list[Task] = []

        for task in Task._yield_tasks(now):
            if task.cancelled:
                Task._removed -= 1
            else:
                tasks.append(task)

        for task in tasks:
            Task.running_task = task
            task.func(*task.args, **task.kw)
            if task.isInterval:
                task.target = now + task.timeout
                task.queue()

        Task.running_task = None

        if target := Task.get_next_tick_target():
            return target - now


class Conn(Protocol):
    """
    A Class that describes the required members and functions required
    of a Conn object like Room and PM
    """
    sock: socket.socket

    @property
    def pendingWrite(self) -> bool:
        ...

    def rfeed(self):
        ...

    def wfeed(self):
        ...

    def disconnect(self):
        ...


################################################################
# PM class
################################################################
class PM:
    """Manages a connection with Chatango PM."""
    ####
    # Init
    ####
    PMHost = "c1.chatango.com"
    PMPort = 5222

    def __init__(self, mgr: RoomManager):
        self.connected = False
        self.blocklist: set[User] = set()
        self.contacts: set[User] = set()
        self.status: dict[User, tuple[int, bool]] = dict()
        """Dict containing {User: (last_active_timestamp, is_online)}

        last_active_timestamp = logout_time | enter_idle_time | 0
        when is_online is False, last_active_timestamp is logout_time
        when is_online is True, and
         1. last_active_timestamp is -1, User status is unknown
         2. last_active_timestamp is 0, User is active online
         3. last_active_timestamp is enter_idle_time*

         *rounded to the minute, chatango limitation
        """

        self.msgs: dict[str, "Message"] = dict()
        """Dict containing {str(timestamp): Message}"""

        self._auth_re = re.compile(r"auth\.chatango\.com ?= ?([^;]*)", re.IGNORECASE)
        self._mgr = mgr
        self._wlock = False
        self._firstCommand = True
        self._wbuf = bytearray()
        self._wlockbuf = bytearray()
        self._rbuf = bytearray()
        self._sbuf = bytearray(2**14)
        self._pingTask = None
        self._connect()

    ####
    # Connections
    ####
    def _connect(self):
        self._wbuf.clear()
        self._firstCommand = True
        if self._auth():
            self.sock = socket.socket()
            self.sock.setblocking(False)
            self.sock.connect_ex((self.PMHost, self.PMPort))

            self._pingTask = self._mgr.setInterval(self._mgr.pingDelay, self.ping)
            self.connected = True

    def _getAuth(self, name: str, password: str) -> str | None:
        """
        Request an auid using name and password.

        @param name: name
        @param password: password

        @return: auid
        """
        data = urllib.parse.urlencode({
            "user_id": name,
            "password": password,
            "storecookie": "on",
            "checkerrors": "yes"
        }).encode()

        try:
            headers = urllib.request.urlopen("http://chatango.com/login", data).headers
        except urllib.error.HTTPError as error:
            print("[PM][Auth]", error)
            return None

        for header, value in headers.items():
            if header.lower() == "set-cookie":
                if (m := self._auth_re.search(value)):
                    return m.group(1) or None

    def _auth(self):
        auid = self._getAuth(self._mgr.name, self._mgr.password)
        if auid is None:
            self._mgr._callEvent(self, "onLoginFail")
            return False
        self._sendCommand("tlogin", auid, "2")
        self._setWriteLock(True)
        return True

    def disconnect(self):
        """Disconnect the bot from PM"""
        self._disconnect()
        self._mgr._callEvent(self, "onPMDisconnect")

    def _disconnect(self):
        self.connected = False
        self.sock.close()
        self._mgr.removePMConnection()

    def _updateStatus(self, user: User, status: str, timestamp: int, idle_duration: str = "0"):
        if status == "off" or status == "offline":
            self.status[user] = (timestamp, False)
        elif status == "on" or status == "app" or status == "online":
            if idle_duration == '0':
                self.status[user] = (0, True)
            else:
                self.status[user] = (int(time.time()) - int(float(idle_duration)) * 60, True)
        else:
            # unknown status, `online` is not off | on | app
            return False

        return True

    ####
    # Feed
    ####
    @property
    def pendingWrite(self) -> bool:
        return bool(self._wbuf)

    def feed_tick(self):
        # wait till entire message is received, message is delimited by 0
        if self._rbuf[-1] == 0:
            del self._rbuf[-1]

            lines = self._rbuf.decode().split("\x00")
            for line in lines:
                self._process(line.rstrip("\r\n"))
            self._rbuf.clear()

    def rfeed(self):
        try:
            size = self.sock.recv_into(self._sbuf)
            if size > 0:
                self._rbuf += self._sbuf[:size]
                self.feed_tick()
            else:
                self.disconnect()
        except socket.error as error:
            print("[PM][rfeed] Socket error", error)

    def wfeed(self):
        try:
            size = self.sock.send(self._wbuf)
            del self._wbuf[:size]
        except socket.error as error:
            print("[PM][wfeed] Socket error", error)

    def _process(self, data: str):
        """
        Process a command string.

        @param data: the command string
        """
        # Assume we intended to disconnect for some reason
        # We shouldn't continue to process the rest of the data still in the pipe
        # as it might error due to us already clearing the room state when disconnecting
        if not self.connected:
            return

        self._mgr._callEvent(self, "onRaw", data)
        cmd, *args = data.split(":")
        func = "_rcmd_" + cmd
        try:
            getattr(self, func)(args)
        except AttributeError:
            if debug:
                print("unknown data: "+str(data))

    ####
    # Received Commands
    ####
    def _rcmd_OK(self, _args: list[str]):
        self._setWriteLock(False)
        self._sendCommand("wl")
        self._sendCommand("getblock")
        self._mgr._callEvent(self, "onPMConnect")

    def _rcmd_wl(self, args: list[str]):
        self.contacts = set()
        # would have liked to just use `zip(*[iter(args)]*4)` but type hint hates it
        iargs = iter(args)
        for name, last_on, is_on, idle in zip(iargs, iargs, iargs, iargs):
            user = User(name)
            # in case chatango gives a "None" as data argument
            if last_on != "None":
                if not self._updateStatus(user, is_on, int(last_on), idle):
                    print("[PM][wl] Unsupported format: ", name, last_on, is_on, idle)
            else:
                print("[PM][wl] Received None for timestamp, consider submitting an issue:")
                print(" -> ", name, last_on, is_on, idle)
                continue
            self.contacts.add(user)
        self._mgr._callEvent(self, "onPMContactlistReceive")

    def _rcmd_block_list(self, args: list[str]):
        new_blocklist = {User(name) for name in args if name != ""}
        if self.blocklist:
            for user in new_blocklist-self.blocklist:
                self.blocklist.add(user)
                self._mgr._callEvent(self, "onPMBlock", user)
        self.blocklist = new_blocklist

    def _rcmd_idleupdate(self, args: list[str]):
        user = User(args[0])
        if args[1] == '1':
            self.status[user] = (0, True)
        else:
            self.status[user] = (int(time.time()), True)

    def _rcmd_track(self, args: list[str]):
        user = User(args[0])
        if not self._updateStatus(user, args[2], int(args[1]), args[1]):
            print("[PM][track] Unsupported format: ", *args)

    def _rcmd_status(self, args: list[str]):
        user = User(args[0])
        if not self._updateStatus(user, args[2], int(float(args[1])), args[1]):
            print("[PM][status] Unsupported format: ", *args)

    def _rcmd_DENIED(self, _args: list[str]):
        self._disconnect()
        self._mgr._callEvent(self, "onLoginFail")

    def _rcmd_msg(self, args: list[str]):
        user = User(args[0])
        msgtime = args[3]
        rawmsg = ":".join(args[5:])
        body, n, f = _clean_message(rawmsg)

        nameColor = _parseNameColor(n)
        fontColor, fontFace, fontSize = _parseFont(f)

        msg = Message(
            timestamp=float(msgtime),
            user=user,
            body=body,
            raw=rawmsg,
            ip="",
            nameColor=nameColor,
            fontColor=fontColor,
            fontFace=fontFace,
            fontSize=fontSize,
            unid="",
            puid="",
            room=self
        )

        self.msgs[msgtime] = msg
        self._mgr._callEvent(self, "onPMMessage", user, msg)

    def _rcmd_msgoff(self, args: list[str]):
        user = User(args[0])
        body = _strip_html(":".join(args[5:]))
        self._mgr._callEvent(self, "onPMOfflineMessage", user, body)

    def _rcmd_wladd(self, args: list[str]):
        user = User(args[0])
        self._updateStatus(user, args[1], int(args[2]), args[2])
        self.contacts.add(user)
        self._mgr._callEvent(self, "onPMContactAdd", user)

    def _rcmd_wldelete(self, args: list[str]):
        user = User(args[0])
        del self.status[user]
        self.contacts.remove(user)
        self._mgr._callEvent(self, "onPMContactRemove", user)

    def _rcmd_wlapp(self, args: list[str]):
        user = User(args[0])
        self.status[user] = (0, True)
        self._mgr._callEvent(self, "onPMContactOnline", user)

    def _rcmd_wlonline(self, args: list[str]):
        user = User(args[0])
        self.status[user] = (0, True)
        self._mgr._callEvent(self, "onPMContactOnline", user)

    def _rcmd_wloffline(self, args: list[str]):
        user = User(args[0])
        last_on = int(float(args[1]))
        self.status[user] = (last_on, False)
        self._mgr._callEvent(self, "onPMContactOffline", user)

    def _rcmd_kickingoff(self, _args: list[str]):
        self.disconnect()

    def _rcmd_toofast(self, _args: list[str]):
        self.disconnect()

    def _rcmd_unblocked(self, args: list[str]):
        """call when successfully unblocked"""
        user = User(args[0])
        if user in self.blocklist:
            self.blocklist.remove(user)
            self._mgr._callEvent(self, "onPMUnblock", user)

    ####
    # Commands
    ####
    def ping(self):
        """send a ping"""
        self._sendCommand("")
        self._mgr._callEvent(self, "onPMPing")

    def message(self, user: User, msg: str):
        """send a pm to a user"""
        if msg != "":
            msg = msg.replace('\n', '\r')
            self._sendCommand("msg", user.name, msg)

    def addContact(self, user: User):
        """add contact"""
        if user not in self.contacts:
            self._sendCommand("wladd", user.name)

    def removeContact(self, user: User):
        """remove contact"""
        if user in self.contacts:
            self._sendCommand("wldelete", user.name)

    def deleteMessage(self, msg: Message):
        """chatango PM doesn't support deletion

        method added for unified interface compatibility"""

    def block(self, user: User):
        """block a person"""
        if user not in self.blocklist:
            self._sendCommand("block", user.name, user.name, "S")

    def unblock(self, user: User):
        """unblock a person"""
        if user in self.blocklist:
            self._sendCommand("unblock", user.name)

    def track(self, user: User):
        """get and store status of person for future use"""
        self._sendCommand("track", user.name)

    def checkOnline(self, user: User):
        """return True if online, False if offline, None if unknown"""
        if user in self.status:
            return self.status[user][1]
        else:
            return None

    def getIdle(self, user: User):
        """return last active time, time.time() if isn't idle, 0 if offline, None if unknown"""
        if user not in self.status:
            return None
        if not self.status[user][1]:
            return 0
        if self.status[user][0] == 0:
            return time.time()
        else:
            return self.status[user][0]

    ####
    # Util
    ####
    def _write(self, data: bytes):
        if self._wlock:
            self._wlockbuf += data
        else:
            self._wbuf += data

    def _setWriteLock(self, lock: bool):
        self._wlock = lock
        if self._wlock is False:
            self._write(self._wlockbuf)
            self._wlockbuf.clear()

    def _sendCommand(self, *args: str):
        """
        Send a command.

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
    def __init__(self, room: str, uid: str | None, mgr: RoomManager):
        """init, don't overwrite"""
        # Basic stuff
        self.name = room
        self._server = getServer(room)
        self._port = 443
        self._mgr = mgr

        # Under the hood
        self.connected = False
        self._reconnecting = False
        self._provided_uid = uid
        self.uid: str = self._provided_uid or _genUid()

        self._sbuf = bytearray(2**14)
        self._rbuf = bytearray()
        self._wbuf = bytearray()
        self._wlockbuf = bytearray()

        self.owner: User
        self._mods: set[User] = set()
        self._mqueue: dict[str, Message] = dict()
        # NOTE: Is userlist with recent mode commonly used?
        # if not, we should optimize for better onMessage Performance

        # Look into better option for history,
        # assuming we want to keep recent mode performance
        # deque is not suitable due to the lack of slicing
        # Set lack order,  possible to use dict[msg, None] but no slicing
        self.history: list[Message] = list()
        self._i_log: list[Message] = list()
        self._ihistoryIndex: int | None = 0
        self._gettingmorehistory: bool = False
        self._userlist: list[User] = list()
        self._firstCommand = True
        self._connectAmount = 0
        self.premium = False
        self.usercount = 0
        self.pingTask: Task
        self._bot_name: str = ""
        self._login_name = ""
        self._anon_name = ""
        self._anon_n = ""
        self.users: dict[str, User] = dict()
        self.msgs: dict[str, "Message"] = dict()
        self._wlock = False
        self.silent = False
        self._banlist: dict[User, BanRecord] = dict()
        self._unbanlist: dict[User, BanRecord] = dict()

        # Inited vars
        if self._mgr:
            self._connect()

    ####
    # Connect/disconnect
    ####
    def _connect(self):
        """Connect to the server."""
        self.sock = socket.socket()
        self.sock.setblocking(False)
        self.sock.connect_ex((self._server, self._port))
        self._mgr.addConnection(self)
        self._firstCommand = True
        self._wbuf.clear()
        self._auth()
        self.pingTask: Task = self._mgr.setInterval(self._mgr.pingDelay, self.ping)
        self.connected = True

    def reconnect(self):
        """Reconnect."""
        self._reconnecting = True
        if self.connected:
            self._disconnect()
        self.uid = self._provided_uid or _genUid()
        self._connect()
        self._reconnecting = False

    def disconnect(self):
        """Disconnect."""
        self._disconnect()
        self._mgr._callEvent(self, "onDisconnect")

    def _disconnect(self):
        """Disconnect from the server."""
        self.connected = False
        for user in self._userlist:
            user.clearSessionIds(self)
        self._userlist = list()
        self.pingTask.cancel()
        self.sock.close()
        self._mgr.removeConnection(self)

    def _auth(self):
        """Authenticate."""
        # login as name with password
        if self._mgr.name and self._mgr.password:
            self._sendCommand("bauth", self.name, self.uid, self._mgr.name, self._mgr.password)
        # login as anon
        else:
            self._sendCommand("bauth", self.name, "", "", "")

        self._setWriteLock(True)

    ####
    # Properties
    ####
    @property
    def botname(self) -> str:
        return self._bot_name

    @property
    def pendingWrite(self) -> bool:
        return bool(self._wbuf)

    def getUserlist(self, mode: Optional[Userlist_Mode] = None,
                    unique: Optional[bool] = None, memory: Optional[int] = None):
        ul = []
        mode = mode or self._mgr.userlistMode
        unique = unique or self._mgr.userlistUnique
        memory = memory or self._mgr.userlistMemory
        if mode is Userlist_Mode.Recent:
            ul = [x.user for x in self.history[-memory:]]
        elif mode is Userlist_Mode.All:
            ul = self._userlist
        if unique:
            return list(set(ul))
        else:
            return ul

    userlist = property(getUserlist)

    @property
    def usernames(self):
        return [x.name for x in self._userlist]

    @property
    def user(self): return self._mgr.user

    @property
    def ownername(self): return self.owner.name

    @property
    def mods(self):
        return set(self._mods)

    @property
    def modnames(self):
        return [x.name for x in self.mods]

    @property
    def banlist(self): return list(self._banlist.keys())

    @property
    def unbanlist(self): return [[r.target, r.src] for r in self._unbanlist.values()]

    ####
    # Feed/process
    ####
    def feed_tick(self):
        # wait till entire message is received, message is delimited by 0
        if self._rbuf[-1] == 0:
            del self._rbuf[-1]
            lines = self._rbuf.decode(errors='ignore').split("\x00")
            for line in lines:
                self._process(line.rstrip("\r\n"))
            self._rbuf.clear()

    def rfeed(self):
        try:
            size = self.sock.recv_into(self._sbuf)
            if size > 0:
                self._rbuf += self._sbuf[:size]
                self.feed_tick()
            else:
                self.disconnect()
        except socket.error as error:
            print("[Room][rfeed] Socket error", error)

    def wfeed(self):
        try:
            size = self.sock.send(self._wbuf)
            del self._wbuf[:size]
        except socket.error as error:
            print("[Room][wfeed] Socket error", error)

    def _process(self, line: str):
        """
        Process a command string.

        @param data: the command string
        """
        # Assume we intended to disconnect for some reason
        # We shouldn't continue to process the rest of the data still in the pipe
        # as it might error due to us already clearing the room state when disconnecting
        if not self.connected:
            return

        self._mgr._callEvent(self, "onRaw", line)
        cmd, *args = line.split(":")
        func = "_rcmd_" + cmd
        if hasattr(self, func):
            getattr(self, func)(args)
        else:
            if debug:
                print("unknown data: "+str(line))

    ####
    # Received Commands
    ####
    def _rcmd_ok(self, args: list[str]):
        # Figure out self anon id in the current room and store it
        n = args[4].rsplit('.', 1)[0]
        n = n[-4:]
        aid = args[1][0:8]
        pid = "!anon" + _getAnonId(n, aid)
        self._anon_name = pid
        self._bot_name = pid
        self._anon_n = n

        # if no name and no password is provided, join room as anon
        if args[2] == "N" and self._mgr.password is None and self._mgr.name is None:
            # Nothing need to be done for anon login
            pass
        # if name is provided but no password, attempt to change name to temp name
        elif args[2] == "N" and self._mgr.password is None:
            self._sendCommand("blogin", self._mgr.name)
        # if name and password is provided but fail to login
        elif args[2] != "M":  # unsuccessful login
            self._mgr._callEvent(self, "onLoginFail")
            self.disconnect()
        # Successful login
        elif args[2] == "M":
            self._bot_name: str = self._mgr.name
        self.owner = User(args[0])
        self.uid = args[1]
        self._mods = set(map(lambda x: User(x.split(",")[0]), args[6].split(";")))

    def _rcmd_aliasok(self, _args: list[str]):
        # Successful Setting Temp Name
        self._bot_name = "#"+self._login_name

    def _rcmd_pwdok(self, _args: list[str]):
        # Successful login from anon/temp mode
        self._bot_name = self._login_name

    def _rcmd_denied(self, _args: list[str]):
        self._disconnect()
        self._mgr._callEvent(self, "onConnectFail")

    def _rcmd_inited(self, _args: list[str]):
        self._sendCommand("g_participants", "start")
        self._sendCommand("getpremium", "1")
        self.requestBanlist()
        self.requestUnBanlist()
        if self._connectAmount == 0:
            self._mgr._callEvent(self, "onConnect")
            for msg in reversed(self._i_log):
                user = msg.user
                self._mgr._callEvent(self, "onHistoryMessage", user, msg)
                self._addHistory(msg)
            self._i_log.clear()
            self._mgr._callEvent(self, "onHistoryMessageUpdate")
        else:
            self._mgr._callEvent(self, "onReconnect")
            # we do not repeat onHistoryMessage calls but we still need to clear the log
            # in case the users uses getMoreHistory
            self._i_log.clear()
        self._connectAmount += 1
        self._setWriteLock(False)

    def _rcmd_premium(self, args: list[str]):
        if float(args[1]) > time.time():
            self.premium = True
            if self.user.mbg:
                self.setBgMode(1)
            if self.user.mrec:
                self.setRecordingMode(1)
        else:
            self.premium = False

    def _rcmd_mods(self, args: list[str]):
        modnames = args
        mods = set(map(lambda x: User(x.split(",")[0]), modnames))
        premods = self._mods
        for user in mods - premods:  # modded
            self._mods.add(user)
            self._mgr._callEvent(self, "onModAdd", user)
        for user in premods - mods:  # demodded
            self._mods.remove(user)
            self._mgr._callEvent(self, "onModRemove", user)
        self._mgr._callEvent(self, "onModChange")

    def _rcmd_b(self, args: list[str]):
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
            if n:
                nameColor = _parseNameColor(n)
            else:
                nameColor = None
        i = args[5]
        unid = args[4]
        # Replace message.user with our unique user object
        # if name matches the current bot name in room
        # to simplify telling apart the bot (self) for the user
        user = User(name) if name != self._bot_name else self.user
        # Create an anonymous message and queue it because msgid is unknown.
        if f:
            fontColor, fontFace, fontSize = _parseFont(f)
        else:
            fontColor, fontFace, fontSize = None, None, None
        msg = Message(
            timestamp=mtime,
            user=user,
            body=msg,
            raw=rawmsg,
            ip=ip,
            nameColor=nameColor,
            fontColor=fontColor,
            fontFace=fontFace,
            fontSize=fontSize,
            unid=unid,
            puid=puid,
            room=self
        )
        self._mqueue[i] = msg

    def _rcmd_u(self, args: list[str]):
        if msg := self._mqueue.pop(args[0], None):
            msg.attach(self, args[1])
            self._addHistory(msg)
            self._mgr._callEvent(self, "onMessage", msg.user, msg)

    def _rcmd_i(self, args: list[str]):
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
            if n:
                nameColor = _parseNameColor(n)
            else:
                nameColor = None
        # i = args[5]
        unid = args[4]
        # Replace message.user with our unique user object
        # if name matches the current bot name in room
        # to simplify telling apart the bot (self) for the user
        user = User(name) if name != self._bot_name else self.user
        # Create an anonymous message and queue it because msgid is unknown.
        if f:
            fontColor, fontFace, fontSize = _parseFont(f)
        else:
            fontColor, fontFace, fontSize = None, None, None
        msg = Message(
            timestamp=mtime,
            user=user,
            body=msg,
            raw=rawmsg,
            ip=ip,
            nameColor=nameColor,
            fontColor=fontColor,
            fontFace=fontFace,
            fontSize=fontSize,
            unid=unid,
            puid=puid,
            room=self
        )
        self._i_log.append(msg)

    def _rcmd_gotmore(self, _args: list[str]):
        self._gettingmorehistory = False
        for msg in reversed(self._i_log):
            user = msg.user
            self._mgr._callEvent(self, "onHistoryMessage", user, msg)
            self._addHistory(msg)
        self._i_log.clear()
        self._mgr._callEvent(self, "onHistoryMessageUpdate")

    def _rcmd_nomore(self, _args: list[str]):
        self._ihistoryIndex = None

    def getMoreHistory(self):
        """
        Request for more room message

        Note: getMoreHistory not meant to be called more than once
              per onHistoryMessageUpdate

        @return: If there is more history message
        """
        # We shouldn't send out more than one request batch at a time
        if self._ihistoryIndex is not None and not self._gettingmorehistory:
            self._gettingmorehistory = True
            self._sendCommand('get_more', '20', str(self._ihistoryIndex))
            self._ihistoryIndex += 1
        return bool(self._ihistoryIndex)

    def _rcmd_g_participants(self, args: list[str]):
        args = ":".join(args).split(";")
        for data in args:
            data = data.split(":")
            name = data[3].lower()
            if name == "none":
                continue
            user = User(
                name=name,
                room=self
            )
            user.addSessionId(self, data[0])
            self._userlist.append(user)

    def _rcmd_participant(self, args: list[str]):
        name = args[3].lower()
        if name == "none":
            return
        user = User(name)
        puid = args[2]

        if args[0] == "0":  # leave
            user.removeSessionId(self, args[1])
            self._userlist.remove(user)
            if user not in self._userlist or not self._mgr.userlistEventUnique:
                self._mgr._callEvent(self, "onLeave", user, puid)
        else:  # join
            user.addSessionId(self, args[1])
            if user not in self._userlist:
                doEvent = True
            else:
                doEvent = False
            self._userlist.append(user)
            if doEvent or not self._mgr.userlistEventUnique:
                self._mgr._callEvent(self, "onJoin", user, puid)

    def _rcmd_show_fw(self, _args: list[str]):
        self._mgr._callEvent(self, "onFloodWarning")

    def _rcmd_show_tb(self, _args: list[str]):
        self._mgr._callEvent(self, "onFloodBan")

    def _rcmd_tb(self, _args: list[str]):
        self._mgr._callEvent(self, "onFloodBanRepeat")

    def _rcmd_delete(self, args: list[str]):
        msg = self.msgs.get(args[0])
        if msg:
            if msg in self.history:
                self.history.remove(msg)
                self._mgr._callEvent(self, "onMessageDelete", msg.user, msg)
                msg.detach()

    def _rcmd_deleteall(self, args: list[str]):
        for msgid in args:
            self._rcmd_delete([msgid])

    def _rcmd_n(self, args: list[str]):
        self.usercount = int(args[0], 16)
        self._mgr._callEvent(self, "onUserCountChange")

    def _rcmd_blocklist(self, args: list[str]):
        self._banlist = dict()
        sections = ":".join(args).split(";")
        for section in sections:
            p = section.split(":")
            if len(p) != 5:
                continue
            if p[2] == "":
                continue
            user = User(p[2])
            self._banlist[user] = BanRecord(p[0], p[1], user, float(p[3]), User(p[4]))
        self._mgr._callEvent(self, "onBanlistUpdate")

    def _rcmd_unblocklist(self, args: list[str]):
        self._unbanlist = dict()
        sections = ":".join(args).split(";")
        for section in sections:
            p = section.split(":")
            if len(p) != 5:
                continue
            if p[2] == "":
                continue
            user = User(p[2])
            self._unbanlist[user] = BanRecord(p[0], p[1], user, float(p[3]), User(p[4]))
        self._mgr._callEvent(self, "onUnBanlistUpdate")

    def _rcmd_blocked(self, args: list[str]):
        if args[2] == "":
            return
        target = User(args[2])
        user = User(args[3])
        self._banlist[target] = BanRecord(args[0], args[1], target, float(args[4]), user)

        self._mgr._callEvent(self, "onBan", user, target)

    def _rcmd_unblocked(self, args: list[str]):
        if args[2] == "":
            return
        target = User(args[2])
        user = User(args[3])
        del self._banlist[target]
        self._unbanlist[user] = BanRecord(args[0], args[1], target, float(args[4]), user)
        self._mgr._callEvent(self, "onUnban", user, target)

    ####
    # Commands
    ####
    def login(self, NAME: str, PASS: Optional[str] = None):
        """login as a user or set a name in room"""
        if PASS:
            self._sendCommand("blogin", NAME, PASS)
        else:
            self._sendCommand("blogin", NAME)
        self._login_name = NAME

    def logout(self):
        """logout of user in a room"""
        self._sendCommand("blogout")
        self._bot_name = self._anon_name

    def ping(self):
        """Send a ping."""
        self._sendCommand("")
        self._mgr._callEvent(self, "onPing")

    def rawMessage(self, msg: str):
        """
        Send a message without n and f tags.

        @param msg: message
        """
        if not self.silent:
            self._sendCommand("bmsg:tl2r", msg)

    def message(self, msg: str, html: bool = False):
        """
        Send a message. (Use "\n" for new line)

        @param msg: message
        """
        msg = msg.rstrip()
        if not html:
            msg = msg.replace("<", "&lt;").replace(">", "&gt;")

        if len(msg) > self._mgr.maxLength:
            if self._mgr.tooBigMessage == BigMessage_Mode.Cut:
                self.message(msg[:self._mgr.maxLength], html=html)
            elif self._mgr.tooBigMessage == BigMessage_Mode.Multiple:
                for index in range(0, len(msg), self._mgr.maxLength):
                    self.message(msg[index:index+self._mgr.maxLength], html=html)
            return

        if self._bot_name.startswith("!anon"):
            # if the bot is current login as anon
            # use the anon n that was provided by the server
            msg = "<n" + self._anon_n + "/>" + msg
        else:
            msg = "<n" + self.user.nameColor + "/>" + msg

        if not self._bot_name.startswith("!anon"):
            font_properties = "<f x%s%s=\"%s\">" % (self.user.fontSize.zfill(2),
                                                    self.user.fontColor,
                                                    self.user.fontFace)
            msg = font_properties + msg

        if "\n" in msg:
            msg = msg.replace("\n", "\r")

        msg.replace("~", "&#126;")
        self.rawMessage(msg)

    def setBgMode(self, mode: int):
        """turn on/off bg"""
        self._sendCommand("msgbg", str(mode))

    def setRecordingMode(self, mode: int):
        """turn on/off recording"""
        self._sendCommand("msgmedia", str(mode))

    def addMod(self, user: User):
        """
        Add a moderator.

        @param user: User to mod.
        """
        if self.getLevel(User(self.botname)) == 2:
            self._sendCommand("addmod", user.name)

    def removeMod(self, user: User):
        """
        Remove a moderator.

        @param user: User to demod.
        """
        if self.getLevel(User(self.botname)) == 2:
            self._sendCommand("removemod", user.name)

    def flag(self, message: Message):
        """
        Flag a message.

        @param message: message to flag
        """
        if message.msgid:
            self._sendCommand("g_flag", message.msgid)

    def flagUser(self, user: User) -> bool:
        """
        Flag a user.

        @param user: user to flag

        @return: whether a message to flag was found
        """
        msg = self.getLastMessage(user)
        if msg:
            self.flag(msg)
            return True
        return False

    def deleteMessage(self, message: Message):
        """
        Delete a message. (Moderator only)

        @param message: message to delete
        """
        if message.msgid and self.getLevel(self.user) > 0:
            self._sendCommand("delmsg", message.msgid)

    def deleteUser(self, user: User):
        """
        Delete a message. (Moderator only)

        @param message: delete user's last message
        """
        if self.getLevel(self.user) > 0:
            msg = self.getLastMessage(user)
            if msg and msg.msgid:
                self._sendCommand("delmsg", msg.msgid)
            return True
        return False

    def delete(self, message: Message):
        """
        compatibility wrapper for deleteMessage
        """
        print("[obsolete] the delete function is obsolete, please use deleteMessage")
        return self.deleteMessage(message)

    def rawClearUser(self, unid: str, ip: str, user: str):
        self._sendCommand("delallmsg", unid, ip, user)

    def clearUser(self, user: User) -> bool:
        """
        Clear all of a user's messages. (Moderator only)

        @param user: user to delete messages of

        @return: whether a message to delete was found
        """
        if self.getLevel(self.user) > 0:
            msg = self.getLastMessage(user)
            if msg:
                if msg.user.name[0] in ["!", "#"]:
                    self.rawClearUser(msg.unid, msg.ip, "")
                else:
                    self.rawClearUser(msg.unid, msg.ip, msg.user.name)
                return True
        return False

    def clearall(self):
        """Clear all messages. (Owner only)"""
        if self.getLevel(self.user) == 2:
            self._sendCommand("clearall")

    def rawBan(self, name: str, ip: str, unid: str):
        """
        Execute the block command using specified arguments.
        (For advanced usage)

        @param name: name
        @param ip: ip address
        @param unid: unid
        """
        self._sendCommand("block", unid, ip, name)

    def ban(self, msg: Message):
        """
        Ban a message's sender. (Moderator only)

        @param message: message to ban sender of
        """
        if self.getLevel(self.user) > 0:
            self.rawBan(msg.user.name, msg.ip, msg.unid)

    def banUser(self, user: User) -> bool:
        """
        Ban a user. (Moderator only)

        @param user: user to ban

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

    def rawUnban(self, name: str, ip: str, unid: str):
        """
        Execute the unblock command using specified arguments.
        (For advanced usage)

        @param name: name
        @param ip: ip address
        @param unid: unid
        """
        self._sendCommand("removeblock", unid, ip, name)

    def unban(self, user: User) -> bool:
        """
        Unban a user. (Moderator only)

        @param user: user to unban

        @return: whether it succeeded
        """
        rec = self._getBanRecord(user)
        if rec:
            self.rawUnban(rec.target.name, rec.ip, rec.unid)
            return True
        else:
            return False

    ####
    # Util
    ####
    def _getBanRecord(self, user: User):
        if user in self._banlist:
            return self._banlist[user]
        return None

    def _write(self, data: bytes):
        if self._wlock:
            self._wlockbuf += data
        else:
            self._wbuf += data

    def _setWriteLock(self, lock: bool):
        self._wlock = lock
        if self._wlock is False:
            self._write(self._wlockbuf)
            self._wlockbuf.clear()

    def _sendCommand(self, *args: str):
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

    def getLevel(self, user: User):
        """get the level of user in a room"""
        if user == self.owner:
            return 2
        if user.name in self.modnames:
            return 1
        return 0

    def getLastMessage(self, user: Optional[User] = None):
        """get last message said by user in a room"""
        if user:
            try:
                i = 1
                while True:
                    msg = self.history[-i]
                    if msg.user == user:
                        return msg
                    i += 1
            except IndexError:
                return None
        else:
            try:
                return self.history[-1]
            except IndexError:
                return None
        return None

    def findUser(self, name: str):
        """check if user is in the room

        return User(name) if name in room else None"""
        name = name.lower()

        # To avoid a false ambiguous result,
        # We need to check through the whole userlist

        # Since we are looping though the whole userlist
        # let's make it into a dict and limit it to users that contain the provided name
        users = {user.name: user for user in self.getUserlist() if name in user.name}

        if len(users) == 1:
            name, user = users.popitem()
            return user
        else:
            # Multiple user with the same name or no user with the name

            # Dict.get will return User if there is an exact match
            # Otherwise it will return None
            return users.get(name)

    ####
    # History
    ####
    def _addHistory(self, msg: Message):
        """
        Add a message to history.

        @param msg: message
        """
        self.history.append(msg)
        if len(self.history) > self._mgr.maxHistoryLength:
            rest, self.history = self.history[:-self._mgr.maxHistoryLength], \
                                 self.history[-self._mgr.maxHistoryLength:]
            for msg in rest:
                msg.detach()


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
    # socket select wait/sleep time in seconds before next task tick
    _TimerResolution = 0.2
    _deferredThreads: set[threading.Thread] = set()
    disconnectOnEmptyConnAndTask = True
    pingDelay = 90
    userlistMode = Userlist_Mode.Recent
    userlistUnique = True
    userlistMemory = 50
    userlistEventUnique = False
    tooBigMessage = BigMessage_Mode.Multiple
    maxLength = 1800
    maxHistoryLength = 150

    ####
    # Init
    ####
    def __init__(self, name: Optional[str] = None, password: Optional[str] = None,
                 pm: bool = True):
        self._name = name
        self._password = password
        self._running = False
        self._rooms: dict[str, Room] = dict()
        if self._password and pm:
            self._pm = self._PM(mgr=self)
        else:
            self._pm = None

    ####
    # Join/leave
    ####
    def joinRoom(self, room: str, uid: Optional[str] = None) -> Room:
        """
        Join a room or return None if already joined.

        @param room: room to join
        """
        room = room.lower()
        if (con := self._rooms.get(room)) is None:
            con = self._Room(room, uid, mgr=self)
        return con

    def leaveRoom(self, room: str):
        """
        Leave a room.

        @param room: room to leave
        """
        room = room.lower()
        if con := self._rooms.get(room):
            con.disconnect()

    def getRoom(self, room: str) -> Room | None:
        """
        Get room with a name, or None if not connected to this room.

        @param room: room

        @return: Room or None
        """
        return self._rooms.get(room.lower())

    ####
    # Properties
    ####
    def _getUser(self): return User("@self") if self._name is None else User(self._name)
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

    def safePrint(self, text: str):
        """Use this to safely print text with unicode"""
        while True:
            try:
                print(text)
                break
            except UnicodeEncodeError as ex:
                text = (text[0:ex.start]+'(unicode)'+text[ex.end:])

    def _callEvent(self, conn: Conn, evt: str, *args: ..., **kw: ...):
        getattr(self, evt)(conn, *args, **kw)
        self.onEventCalled(conn, evt, *args, **kw)

    def onConnect(self, room: Room):
        """
        Called when connected to the room.

        @param room: room where the event occurred
        """

    def onReconnect(self, room: Room):
        """
        Called when reconnected to the room.
        @param room: room where the event occurred
        """

    def onConnectFail(self, room: Room):
        """
        Called when the connection failed.

        @param room: room where the event occurred
        """

    def onDisconnect(self, room: Room):
        """
        Called when the client gets disconnected.

        @param room: room where the event occurred
        """

    def onLoginFail(self, room: Room):
        """
        Called on login failure, disconnects after.

        @param room: room where the event occurred
        """

    def onFloodBan(self, room: Room):
        """
        Called when either flood banned or flagged.

        @param room: room where the event occurred
        """

    def onFloodBanRepeat(self, room: Room):
        """
        Called when trying to send something when floodbanned.

        @param room: room where the event occurred
        """

    def onFloodWarning(self, room: Room):
        """
        Called when an overflow warning gets received.

        @param room: room where the event occurred
        """

    def onMessageDelete(self, room: Room, user: User, message: Message):
        """
        Called when a message gets deleted.

        @param room: room where the event occurred
        @param user: owner of deleted message
        @param message: message that got deleted
        """

    def onModChange(self, room: Room):
        """
        Called when the moderator list changes.

        @param room: room where the event occurred
        """

    def onModAdd(self, room: Room, user: User):
        """
        Called when a moderator gets added.

        @param room: room where the event occurred
        """

    def onModRemove(self, room: Room, user: User):
        """
        Called when a moderator gets removed.

        @param room: room where the event occurred
        """

    def onMessage(self, room: Room, user: User, message: Message):
        """
        Called when a message gets received.

        @param room: room where the event occurred
        @param user: owner of message
        @param message: received message
        """

    def onHistoryMessage(self, room: Room, user: User, message: Message):
        """
        Called when a message gets received from history.

        @param room: room where the event occurred
        @param user: owner of message
        @param message: the message that got added
        """

    def onHistoryMessageUpdate(self, room: Room):
        """
        Called when a set of history has been received.

        @param room: room where the event occurred
        """

    def onJoin(self, room: Room, user: User, puid: str):
        """
        Called when a user joins. Anonymous users get ignored here.

        @param room: room where the event occurred
        @param user: the user that has joined
        @param puid: the personal unique id for the user
        """

    def onLeave(self, room: Room, user: User, puid: str):
        """
        Called when a user leaves. Anonymous users get ignored here.

        @param room: room where the event occurred
        @param user: the user that has left
        @param puid: the personal unique id for the user
        """

    def onRaw(self, room: Room, raw: str):
        """
        Called before any command parsing occurs.

        @param room: room where the event occurred
        @param raw: raw command data
        """

    def onPing(self, room: Room):
        """
        Called when a ping gets sent.

        @param room: room where the event occurred
        """

    def onUserCountChange(self, room: Room):
        """
        Called when the user count changes.

        @param room: room where the event occurred
        """

    def onBan(self, room: Room, user: User, target: User):
        """
        Called when a user gets banned.

        @param room: room where the event occurred
        @param user: user that banned someone
        @param target: user that got banned
        """

    def onUnban(self, room: Room, user: User, target: User):
        """
        Called when a user gets unbanned.

        @param room: room where the event occurred
        @param user: user that unbanned someone
        @param target: user that got unbanned
        """

    def onBanlistUpdate(self, room: Room):
        """
        Called when a banlist gets updated.

        @param room: room where the event occurred
        """

    def onUnBanlistUpdate(self, room: Room):
        """
        Called when a unbanlist gets updated.

        @param room: room where the event occurred
        """

    def onPMConnect(self, pm: PM):
        """
        Called when connected to the pm

        @param pm: the pm
        """

    def onPMDisconnect(self, pm: PM):
        """
        Called when disconnected from the pm

        @param pm: the pm
        """

    def onPMPing(self, pm: PM):
        """
        Called when sending a ping to the pm

        @param pm: the pm
        """

    def onPMMessage(self, pm: PM, user: User, message: Message):
        """
        Called when a message is received

        @param pm: the pm
        @param user: owner of message
        @param message: received message
        """

    def onPMOfflineMessage(self, pm: PM, user: User, body: str):
        """
        Called when connected if a message is received while offline

        @param pm: the pm
        @param user: owner of message
        @param message: received message
        """

    def onPMContactlistReceive(self, pm: PM):
        """
        Called when the contact list is received

        @param pm: the pm
        """

    def onPMBlocklistReceive(self, pm: PM):
        """
        Called when the block list is received

        @param pm: the pm
        """

    def onPMContactAdd(self, pm: PM, user: User):
        """
        Called when the contact added message is received

        @param pm: the pm
        @param user: the user that gotten added
        """

    def onPMContactRemove(self, pm: PM, user: User):
        """
        Called when the contact remove message is received

        @param pm: the pm
        @param user: the user that gotten remove
        """

    def onPMBlock(self, pm: PM, user: User):
        """
        Called when successfully block a user

        @param pm: the pm
        @param user: the user that gotten block
        """

    def onPMUnblock(self, pm: PM, user: User):
        """
        Called when successfully unblock a user

        @param pm: the pm
        @param user: the user that gotten unblock
        """

    def onPMContactOnline(self, pm: PM, user: User):
        """
        Called when a user from the contact come online

        @param pm: the pm
        @param user: the user that came online
        """

    def onPMContactOffline(self, pm: PM, user: User):
        """
        Called when a user from the contact go offline

        @param pm: the pm
        @param user: the user that went offline
        """

    def onEventCalled(self, room: Conn, evt: str, *args: ..., **kw: ...):
        """
        Called on every room-based event.

        @param room: room where the event occurred
        @param evt: the event
        """

    ####
    # Deferring
    ####
    def deferToThread(self, cb: Callable[..., None], func: Callable[..., None],
                      *args: ..., **kw: ...):
        """
        Defer a function to a thread and callback the return value.

        @param callback: function to call on completion
        @param cbargs: arguments to get supplied to the callback
        @param func: function to call
        """
        def f(func: Callable[..., None], cb: Callable[..., None], *args: ..., **kw: ...):
            ret = func(*args, **kw)
            self.setTimeout(0, cb, ret)
            self._deferredThreads.remove(threading.current_thread())

        t = threading.Thread(target=f, args=(func, cb, *args), kwargs=kw)
        self._deferredThreads.add(t)
        t.start()

    ####
    # Scheduling
    ####

    def setTimeout(self, timeout: int, func: Callable[..., None],
                   *args: ..., **kw: ...) -> Task:
        """
        Call a function after at least timeout seconds with specified arguments.

        @param timeout: timeout
        @param func: function to call

        @return: object representing the task
        """
        # TODO: is there an valid use case of timeout 0?
        # I guess it could be use to setup an equivalent of setimmediate which runs
        # after cleanly exiting bot related code and running all preexisiting pending tasks

        # This will only be printed with an error raised when the user does a dumb thing
        # like a function calling setTimeout on itself with timeout 0 instead of using
        # setInterval

        # def dumbfunc(self):
        #    self.setTimeout(0, self.dumbfunc)

        if timeout == 0 and Task.running_task is not None and Task.running_task.func == func:
            print('[task][warning] `timeout == 0` will result in high cpu usage with '
                  '"interval usage", use -1 timeout if intended to run once per tick, '
                  'or a reasonable amount of timeout like 0.2 (5 times per second)')
            print('[task][note] An error will be raised to avoid this message being printed '
                  'multiple times, consider using setInterval instead of a setTimeout within '
                  'a setTimeout if timeout 0 is required, and canceling it via '
                  'ch.Task.running_task.cancel() from within the task itself')
            raise RuntimeError('Preemptively exiting to prevent possible log flood causing '
                               'disk space exhaustion')

        task = Task(
            mgr=self,
            timeout=timeout,
            func=func,
            isInterval=False,
            args=args,
            kw=kw
        )
        return task

    def setInterval(self, timeout: int, func: Callable[..., None],
                    *args: Any, **kw: Any) -> Task:
        """
        Call a function at least every timeout seconds with specified arguments.

        @param timeout: timeout
        @param func: function to call

        @return: object representing the task
        """

        if timeout == 0:
            print('[RoomManager][setInterval] `timeout == 0` will result in high cpu usage '
                  'with "interval usage", use -1 timeout if intended to run once per tick, '
                  'or a reasonable amount of timeout like 0.2 (5 times per second)')

        task = Task(
            mgr=self,
            timeout=timeout,
            func=func,
            isInterval=True,
            args=args,
            kw=kw
        )
        return task

    def removeTask(self, task: Task):
        """
        Sugar for task.cancel for backward compatibility

        @param task: task to cancel
        """
        task.cancel()

    ####
    # Util
    ####
    def addConnection(self, room: Room):
        self._rooms[room.name] = room

    def removeConnection(self, room: Room):
        del self._rooms[room.name]

    def addPMConnection(self, pm: PM):
        self._pm = pm

    def removePMConnection(self):
        self._pm = None

    def getConnections(self):
        li: dict[socket.socket, Conn] = dict((x.sock, x) for x in self._rooms.values())
        if self._pm:
            li[self.pm.sock] = self._pm
        return li

    ####
    # Main
    ####
    def main(self):
        self.onInit()
        self._running = True
        while self._running:
            time_to_next_task = Task.tick()

            conns = self.getConnections()
            wsocks = [sock for sock, x in conns.items() if x.pendingWrite]

            if not conns:
                if time_to_next_task is None:
                    # Backward compatibilty in case of deferToThread joinRoom
                    # or user managed threading

                    # NOTE: Check for threading.active_count() instead?
                    if not self._deferredThreads and self.disconnectOnEmptyConnAndTask:
                        self.stop()
                        break

                    time.sleep(self._TimerResolution)
                else:
                    time.sleep(time_to_next_task)

                continue

            rd, wr, _ = select.select(conns, wsocks, [], time_to_next_task)
            for sock in rd:
                con = conns[sock]
                con.rfeed()
            for sock in wr:
                con = conns[sock]
                con.wfeed()

    @classmethod
    def easy_start(cls, rooms: Optional[list[str]] = None,
                   name: Optional[str] = None, password: Optional[str] = None,
                   pm: bool = True):
        """
        Prompts the user for missing info, then starts.

        @param room: rooms to join
        @param name: name to join as ("" = None, None = unspecified)
        @param password: password to join with ("" = None, None = unspecified)
        """
        if rooms is None:
            rooms = str(input("Room names separated by semicolons: ")).split(";")
        if len(rooms) == 1 and rooms[0] == "":
            rooms = []

        if name is None:
            name = str(input("User name: "))
        if name == "":
            name = None

        if password is None:
            password = str(input("User password: "))
        if password == "":
            password = None

        self = cls(name, password, pm=pm)
        if rooms:
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
        self.user.mbg = True
        for room in self.rooms:
            room.setBgMode(1)

    def disableBg(self):
        """Disable background."""
        self.user.mbg = False
        for room in self.rooms:
            room.setBgMode(0)

    def enableRecording(self):
        """Enable recording if available."""
        self.user.mrec = True
        for room in self.rooms:
            room.setRecordingMode(1)

    def disableRecording(self):
        """Disable recording."""
        self.user.mrec = False
        for room in self.rooms:
            room.setRecordingMode(0)

    def setNameColor(self, color3x: str):
        """
        Set name color.

        @param color3x: a 3-char RGB hex code for the color
        """
        self.user.nameColor = color3x

    def setFontColor(self, color3x: str):
        """
        Set font color.

        @param color3x: a 3-char RGB hex code for the color
        """
        self.user.fontColor = color3x

    def setFontFace(self, face: str):
        """
        Set font face/family.

        @param face: the font face
        """
        self.user.fontFace = face

    def setFontSize(self, size: int):
        """
        Set font size.

        @param size: the font size (limited: 9 to 22)
        """
        if size < 9:
            size = 9
        if size > 22:
            size = 22
        self.user.fontSize = str(size)
