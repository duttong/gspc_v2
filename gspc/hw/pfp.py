import asyncio
import logging
import typing
import time
import serial
import serial.tools.list_ports
from threading import Thread
from . import claimed_serial_ports

_LOGGER = logging.getLogger(__name__)


class PFP:
    TIMEOUT = 10

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

    @staticmethod
    def _get_unload_prompt(port: serial.Serial) -> bool:
        try:
            port.reset_input_buffer()
            port.write(b' \r')
            resp = port.readline()
            if b"UNLOAD>" in resp:
                return True
            for i in range(5):
                if b"AS>" in resp:
                    break
                port.write(b'Q\r')
                port.reset_input_buffer()
                port.write(b' \r')
                resp = port.readline()
            else:
                # AS> prompt not reached
                return False
            port.write(b'U\r')
            resp = port.readline()
            if b"UNLOAD>" in resp:
                return True
        except (ValueError, serial.SerialException):
            pass
        return False

    def _prompt_unload(self):
        if not self._get_unload_prompt(self._port):
            raise RuntimeError("Failed to get unload prompt")

    def _autodetect(self) -> serial.Serial:
        for port_info in serial.tools.list_ports.comports():
            if port_info.name in claimed_serial_ports:
                continue
            port = serial.Serial(port=port_info.name, baudrate=9600,
                                 timeout=self.TIMEOUT, inter_byte_timeout=0, write_timeout=0)
            if not self._get_unload_prompt(port):
                continue
            return port
        raise RuntimeError("PFP not found")

    async def read_pressure(self) -> float:
        """Read the current pressure"""

        async def execute_read() -> float:
            self._prompt_unload()
            self._port.write(b"P\r")
            response = self._port.readline()
            return float(response[4:4+9])

        return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(execute_read(), self._loop))

    async def open_valve(self, pos: int) -> str:
        """Open a sample valve"""

        async def execute_write() -> str:
            self._prompt_unload()
            self._port.write(b"O\r%d\r" % pos)
            response = self._port.readline()
            return response[26:].decode("utf-8").strip()

        return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(execute_write(), self._loop))

    async def close_valve(self, pos: int) -> str:
        """Close a sample valve"""

        async def execute_write() -> str:
            self._prompt_unload()
            self._port.write(b"C\r%d\r" % pos)
            response = self._port.readline()
            return response[26:].decode("utf-8").strip()

        return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(execute_write(), self._loop))
