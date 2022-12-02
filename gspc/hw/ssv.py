import asyncio
import logging
import typing
import serial
import serial.tools.list_ports
from threading import Thread
from . import claimed_serial_ports


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

    async def read(self) -> int:
        """Read the current position"""

        async def execute_read() -> int:
            self._port.write(b"CP\r")
            v = self._port.readline()
            v = int(v) - 1
            return v

        return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(execute_read(), self._loop))

    async def set(self, pos: int) -> None:
        """Set the current position"""

        async def execute_write() -> None:
            self._port.write(b"GO%d\r" % (pos + 1))
            self._port.flushOutput()
            await asyncio.sleep(0.1)
            self._port.flushInput()

        return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(execute_write(), self._loop))
