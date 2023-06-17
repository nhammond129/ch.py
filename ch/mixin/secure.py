"Some black magic lies here"

# pylint fail to properly detect member, false positive so disabled
# pylint: disable=no-member
from typing import Optional

# Importing ch for type hinting
import ch
from ._base import Base


class Secure(Base):
    """
    Override method in RoomManager to not store the password with self

    and instead make uses of local closure scoping to prevent access from

    within an instance.

    [WARNING] not audited by third party but I believe the password shouldn't
    be accessible within a bot instance
    """
    @classmethod
    def easy_start(cls: type[ch.RoomManager], rooms: Optional[list[str]] = None, # type: ignore
                          name: Optional[str] = None, password: Optional[str] = None,
                          pm: bool = True):
        """
        Prompts the user for missing info, then starts,
        while avoiding storing the password within self

        [WARNING] not audited by third party but I believe the password
                  shouldn't be accessible within a bot instance

        @param room: rooms to join
        @param name: name to join as ("" = None, None = unspecified)
        @param password: password to join with ("" = None, None = unspecified)
        """
        print("Starting ch.RoomManager with secure_easy_start")
        print("[WARNING] not audited by third party but I believe the password"
              " shouldn't be accessible within bot instance")
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

        class _RoomSecure(Base):
            def _auth(self):
                """Authenticate."""
                # login as name with password
                if name and password:
                    self._sendCommand("bauth", self.name, self.uid, name, password)
                # login as anon
                else:
                    self._sendCommand("bauth", self.name, "", "", "")

                self._setWriteLock(True)

            def _rcmd_ok(self, args: list[str]):
                # Figure out self anon id in the current room and store it
                n = args[4].rsplit('.', 1)[0]
                n = n[-4:]
                aid = args[1][0:8]
                pid = "!anon" + ch._getAnonId(n, aid)
                self._anon_name = pid
                self._bot_name = pid
                self._anon_n = n

                # if no name and no password is provided, join room as anon
                if args[2] == "N" and password is None and self._mgr.name is None:
                    # Nothing need to be done for anon login
                    pass
                # if name is provided but no password, attempt to change name to temp name
                elif args[2] == "N" and password is None:
                    self._sendCommand("blogin", self._mgr.name)
                # if name and password is provided but fail to login
                elif args[2] != "M":  # unsuccessful login
                    self._callEvent("onLoginFail")
                    self.disconnect()
                # Successful login
                elif args[2] == "M":
                    self._bot_name: str = self._mgr.name
                self.owner = ch.User(args[0])
                self.uid = args[1]
                self._mods = set(map(lambda x: ch.User(x.split(",")[0]), args[6].split(";")))
                self._i_log.clear()

        class RoomSecure(_RoomSecure, cls._Room):
            ...

        class _PMSecure(Base):
            def _auth(self):
                auid = self._getAuth(name, password)  # type: ignore
                if auid is None:
                    self._callEvent("onLoginFail")
                    return False
                self._sendCommand("tlogin", auid, "2")
                self._setWriteLock(True)
                return True

        class PMSecure(_PMSecure, cls._PM):
            ...

        class RoomManagerSecure(cls):
            _Room = RoomSecure
            _PM = PMSecure

            def __init__(self, pm: bool = True):  # pylint: disable=super-init-not-called
                self._name = name
                self._password = "" # blank dummy so stuff doesn't break
                self._running = False
                self._rooms = dict()
                if password and pm:
                    self._pm = self._PM(mgr=self)
                else:
                    self._pm = None

        self = RoomManagerSecure(pm=pm)
        if rooms:
            for room in rooms:
                self.joinRoom(room)

        self.main()
