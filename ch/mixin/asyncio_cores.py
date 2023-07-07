"Some black magic lies here"

import asyncio
import contextlib
import socket
import time
from typing import Any, Awaitable, Callable

# Importing ch for type hinting
import ch
from ch import RoomManager
from ._base import Base


class Asyncio_Task(ch.Task):
    "class to override ch.Task"
    _asyncio_task: Awaitable[Any] | None = None
    __asyncio_wake = asyncio.Event()

    def __init__(self, mgr: RoomManager, timeout: int, func: Callable[..., None], isInterval: bool, args: ..., kw: ...):
        super().__init__(mgr, timeout, func, isInterval, args, kw)
        Asyncio_Task.__asyncio_wake.set()
        if Asyncio_Task._asyncio_task is None:
            Asyncio_Task._asyncio_task = asyncio.ensure_future(self._Tasks_Worker())

    async def _Tasks_Worker(self):
        while (time_to_next_task := self.tick()) is not None:
            Asyncio_Task.__asyncio_wake.clear()
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(Asyncio_Task.__asyncio_wake.wait(), time_to_next_task)
        Asyncio_Task._asyncio_task = None


print("[WARNING][asyncio_cores] Importing this module modify ch internals!")
ch.Task = Asyncio_Task


class _Asyncio_Core(ch.RoomManager):
    """
    Override method in RoomManager to use asyncio
    """
    def main(self):
        def async_conn_and_task():
            li = [x._rfeed_worker_task for x in self._rooms.values()]
            if self._pm:
                li.append(self._pm._rfeed_worker_task)
            if Asyncio_Task._asyncio_task:
                li.append(Asyncio_Task._asyncio_task)
            return li
        loop = asyncio.get_event_loop()
        self.onInit()
        self._running = True
        while self._running:
            ct = async_conn_and_task()
            if not ct:
                if not self._deferredThreads and self.disconnectOnEmptyConnAndTask:
                    self.stop()
                    break
                time.sleep(self._TimerResolution)

            loop.run_until_complete(asyncio.gather(*ct))

class IOCPConn(Base):
    __wfeed_worker_task: Awaitable[Any] | None = None

    def __init__(self, room: str, uid: str | None, mgr: RoomManager):
        self._async_connected = asyncio.Event()
        self._rfeed_worker_task = asyncio.ensure_future(self.async_rfeed())
        super().__init__(room, uid, mgr)

    async def async_connect(self):
        while True:
            code = self.sock.connect_ex((self._server, self._port))
            if code == 0 or code == 106 or code == 10056:
                # successful connect or connected already
                self._async_connected.set()
                break
            await asyncio.sleep(0)

    def _connect(self):
        super()._connect()
        asyncio.ensure_future(self.async_connect())

    def _disconnect(self):
        self._async_connected.clear()
        return super()._disconnect()

    async def async_rfeed(self):
        await self._async_connected.wait()
        while self.connected:
            try:
                size = await asyncio.get_running_loop().sock_recv_into(self.sock, self._sbuf)
                if size:
                    self._rbuf += self._sbuf[:size]
                    self.feed_tick()
                else:
                    self.disconnect()
            except socket.error as error:
                print("[Room][async rfeed] Socket error", error)

    async def _wfeed_worker(self):
        await self._async_connected.wait()
        while self._wbuf:
            self.wfeed()
            await asyncio.sleep(0)
        self.__wfeed_worker_task = None

    def _write(self, data: bytes):
        super()._write(data)
        if self.__wfeed_worker_task is None:
            self.__wfeed_worker_task = asyncio.ensure_future(self._wfeed_worker())


class Asyncio_IOCPCore(Base):
    """
    Override method in RoomManager to use asyncio
    """
    class _Room(IOCPConn, ch.Room):
        ...

    class _PM(IOCPConn, ch.PM):
        ...

    main = _Asyncio_Core.main


class LWMConn(ch.Room):
    def __init__(self, room: str, uid: str | None, mgr: RoomManager):
        self._rfeed_running = asyncio.Event()
        self._rfeed_worker_task = self._rfeed_running.wait()
        super().__init__(room, uid, mgr)
        asyncio.get_event_loop().add_reader(self.sock, self.rfeed)

    def _connect(self):
        self._rfeed_running.clear()
        super()._connect()

    def _disconnect(self):
        asyncio.get_event_loop().remove_reader(self.sock)
        self._rfeed_running.set()
        asyncio.get_event_loop().remove_writer(self.sock)
        super()._disconnect()

    def _write(self, data: bytes):
        super()._write(data)
        asyncio.get_event_loop().add_writer(self.sock, self.wfeed)

    def wfeed(self):
        super().wfeed()
        if not self._sbuf:
            asyncio.get_event_loop().remove_writer(self.sock)


class Asyncio_LWMCore(Base):
    """
    Override method in RoomManager to use asyncio
    """
    class _Room(LWMConn, ch.Room):
        ...

    class _PM(LWMConn, ch.PM):
        ...

    main = _Asyncio_Core.main
