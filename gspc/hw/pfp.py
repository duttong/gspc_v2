import asyncio
import logging
import typing
import re
import serial
import serial.tools.list_ports
from threading import Thread
from . import claimed_serial_ports

_LOGGER = logging.getLogger(__name__)


class PFP:
    TIMEOUT = 2

    def __init__(self, port: typing.Optional[typing.Union[str, serial.Serial]] = None):
        if not isinstance(port, serial.Serial):
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

    @classmethod
    def detect_optional(cls, com: str) -> typing.Optional["PFP"]:
        try:
            port = serial.Serial(port=com, baudrate=9600, timeout=1.0, inter_byte_timeout=0, write_timeout=0)
        except (ValueError, serial.SerialException, IOError):
            return None
        try:
            if not PFP._get_unload_prompt(port):
                port.close()
                return None
        except IOError:
            try:
                port.close()
            except:
                pass
            return None
        port.timeout = cls.TIMEOUT
        print(f'found pfp on {com}')
        return cls(port)

    def _run(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    @staticmethod
    def _get_unload_prompt(port: serial.Serial) -> bool:
        try:
            port.reset_input_buffer()
            port.write(b' \r')
            resp = port.readlines()
            resp = ''.join(map(str, resp))
            if "UNLOAD>" in resp:
                return True
            for i in range(5):
                if "AS>" in resp:
                    break
                port.write(b'Q\r')
                port.reset_input_buffer()
                port.write(b' \r')
                resp = port.readlines()
                resp = ''.join(map(str, resp))
            else:
                # AS> prompt not reached
                return False
            port.write(b'U\r')
            resp = port.readlines()
            resp = ''.join(map(str, resp))
            if "UNLOAD>" in resp:
                return True
        except (ValueError, serial.SerialException):
            pass
        return False

    def _prompt_unload(self):
        if not self._get_unload_prompt(self._port):
            _LOGGER.warning("Failed to get unload prompt from pfp")
            #raise RuntimeError("Failed to get unload prompt")

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
        """Read the current pressure
           updated with readlines method and regex decoding. GSD """

        async def execute_read() -> float:
            return 0.999
            """
            self._prompt_unload()
            self._port.write(b"P\r")
            response = self._port.readlines()
            response = ''.join([s.decode("utf-8") for s in response])
            m = re.search(r' (\d+.\d+)', response)
            if m is None:
                return -1
            return float(m.group(1))
            """

        return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(execute_read(), self._loop))

    async def open_valve(self, pos: int) -> str:
        """Open a sample valve
           switched to readlines method
           returns valve and status """

        async def execute_write() -> str:
            self._prompt_unload()
            self._port.write(b"O\r%d\r" % pos)
            await asyncio.sleep(3)
            _LOGGER.info(f"Attempting to Open PFP valve {pos}")
            response = self._port.readlines()
            response = ''.join([s.decode("utf-8") for s in response])
            return response[24:-8].strip()

        return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(execute_write(), self._loop))

    async def close_valve(self, pos: int) -> str:
        """Close a sample valve"""

        async def execute_write() -> str:
            self._prompt_unload()
            self._port.write(b"C\r%d\r" % pos)
            await asyncio.sleep(3)
            _LOGGER.info(f"Attempting to Close PFP valve {pos}")
            response = self._port.readlines()
            response = ''.join([s.decode("utf-8") for s in response])
            return response[24:-8].strip()

        return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(execute_write(), self._loop))
