"Some black magic lies here"

# pylint fail to properly detect member, false positive so disabled
# pylint: disable=no-member
import select
import socket
import time

# Importing ch for type hinting
import ch
from ._base import Base


class _WindowsMainLoopFix(ch.RoomManager):
    """
    Override method in RoomManager to make keyboard interrupt works better on windows

    asl97: Can't think of a better way to fix the warnings other than to inherit from
    RoomManager and then just extract the method we are replacing
    """

    def main(self):
        self.onInit()
        self._running = True
        while self._running:
            time_to_next_task = ch.Task.tick()

            conns = self.getConnections()
            socks = [x.sock for x in conns]
            wsocks = [x.sock for x in conns if x.wbuf != b""]

            if not socks:
                if time_to_next_task is None:
                    # Backward compatibility in case of deferToThread joinRoom
                    # or user managed threading

                    # NOTE: Check for threading.active_count() instead?
                    if not self._deferredThreads and self.disconnectOnEmptyConnAndTask:
                        self.stop()
                        break

                    time.sleep(self._TimerResolution)
                else:
                    time.sleep(time_to_next_task)

                continue

            if time_to_next_task is None:
                time_to_next_task = self._TimerResolution

            for _ in range(int((time_to_next_task/0.2)+0.5)):
                rd, wr, _ = select.select(socks, wsocks, [], 0.2)
                if rd or wr:
                    for sock in rd:
                        con = [c for c in conns if c.sock == sock][0]
                        try:
                            data = sock.recv(1024)
                            if len(data) > 0:
                                con.feed(data)
                            else:
                                con.disconnect()
                        except socket.error as error:
                            print("[RoomManager][Main Loop] Socket error", error)
                    for sock in wr:
                        con = [c for c in conns if c.sock == sock][0]
                        try:
                            size = sock.send(con.wbuf)
                            con.wbuf = con.wbuf[size:]
                        except socket.error as error:
                            print("[RoomManager][Main Loop] Socket error", error)
                    break


class WindowsMainLoopFix(Base):
    """
    Override method in RoomManager to make keyboard interrupt works better on windows

    asl97: Can't think of a better way to fix the warnings other than to inherit from
    RoomManager and then just extract the method we are replacing
    """
    main = _WindowsMainLoopFix.main
