import asyncio
import logging
import re
import typing
import serial
import serial.tools.list_ports
from threading import Thread
from . import claimed_serial_ports

_LOGGER = logging.getLogger(__name__)


class SSV:
    TIMEOUT = 2

    def __init__(self, port: typing.Optional[str] = None):
        if port is None:
            port = self._autodetect()
        else:
            port = serial.Serial(port=port, baudrate=9600,
                                 timeout=self.TIMEOUT, inter_byte_timeout=0, write_timeout=0)
        claimed_serial_ports.add(port.port)
        self._port = port

        self._loop = asyncio.new_event_loop()
        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _is_on_port(self, port: serial.Serial) -> bool:
        try:
            port.write(b'CP\r')
            v = int(port.readline())
            if v >= 1 and v <= 16:
                return True
        except (ValueError, serial.SerialException):
            pass
        return False

    def _autodetect(self) -> serial.Serial:
        for port_info in serial.tools.list_ports.comports():
            if port_info.name in claimed_serial_ports:
                continue
            port = serial.Serial(port=port_info.name, baudrate=9600,
                                 timeout=self.TIMEOUT, inter_byte_timeout=0, write_timeout=0)
            if not self._is_on_port(port):
                continue
            return port
        raise RuntimeError("SSV not found")

    def _parse_cp(self, valcostr: str) -> int:
        """ parse the string returned from a Valco SSV valve """
        m = re.search(r'= (\d+)', valcostr)
        if m is None:
            return -1
        return int(m.group(1))

    async def read(self) -> int:
        """Read the current position"""

        async def execute_read() -> int:
            self._port.write(b"CP\r")
            v = self._port.readline()
            v = self._parse_cp(v.decode())
            # handle port 16 differently. If 16 return 0
            # v = 0 if v == 16 else v
            # changed this behavior 231113
            return int(v)

        return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(execute_read(), self._loop))

    async def set(self, pos: int) -> None:
        """Set the current position. When pos is 0 send SSV to position 16 """

        async def execute_write() -> None:
            nonlocal pos
            pos = 16 if pos == 0 else pos
            self._port.write(b"GO%d\r" % pos)
            self._port.flushOutput()
            await asyncio.sleep(0.1)
            self._port.flushInput()

        return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(execute_write(), self._loop))
