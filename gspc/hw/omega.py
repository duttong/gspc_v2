#!/usr/bin/python3

import serial
import serial.tools.list_ports
import time
import typing
import logging
import asyncio
from threading import Thread
from . import claimed_serial_ports

_LOGGER = logging.getLogger(__name__)


class _Controller:
    OMEGA_WAIT = 0.35  # time to wait after a write and before a read.
    TERMINATOR = '\r'  # Omega terminator string is usually \r

    def __init__(self):
        self._loop = asyncio.new_event_loop()
        self._port = None
        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _omega_command(self, cmd: str, noread: bool = False) -> typing.Optional[float]:
        self._port.flushInput()
        self._port.write(cmd.encode())

        time.sleep(self.OMEGA_WAIT)

        if noread is True:
            return None

        sp = self._port.read(1024)
        """ The returned data has an unknown byte at the beginning. This
            byte cannot be decoded using .decode('utf-8'). Currently stripping
            the first byte before decoding byte string.
            .decode('charmap') shows the first byte.
        """
        try:
            sp = sp[1:].decode('utf-8')
            sp.replace(self.TERMINATOR, '')
        except UnicodeDecodeError:
            logging.warning('UnicodeDecodeError on omega_command')
            sp = ''
        return sp

    async def get_temperature(self, address: int) -> typing.Optional[float]:
        """ Returns temperature reading from an Omega with address: add
            Typical command *01X01\r
        """
        cmd = f'*{address:02d}X01{self.TERMINATOR}'
        rt = self._omega_command(cmd)
        try:
            return float(rt)
        except ValueError:
            return None

    def _decode_value(self, hexstring: str) -> typing.Optional[float]:
        """ Function will decode a string returned by the
            return setpoint commands (R01 or R02).
            The value returned is a floating point number.
        """
        if len(hexstring) == 0:
            return None
        hexstring = hexstring.replace(self.TERMINATOR, '')
        try:
            binary = f'{int(hexstring, 16):0>24b}'  # 24 bit number
        except ValueError:
            return None
        sign = 1 if binary[0] == '0' else -1
        div_key = {'001': 0, '010': 10, '011': 100, '101': 1000}
        try:
            div = div_key[binary[1:4]]
        except KeyError:
            return None
        value = int(binary[5:], 2) / div * sign
        return value

    @staticmethod
    def _encode_value(value: float, dec: int = 1) -> str:
        """ Encodes a setpoint value into a hexidecimal representation for
            an Omega temperature controller.
            dec is for number of characters after the decimal point. Usually 1.
        """
        dec_key = {0: '001', 1: '010', 2: '011', 3: '101'}  # decimal place encoding
        if value > 360:
            print('Omega setpoint is too large > 360 C. Setting to 25 C')
            value = 25
        sign_bit = '0'
        # handle negative setpoint
        if value < 0:
            sign_bit = '1'
            value *= -1
        valueint = int(value * 10 ** dec)
        valuestr = f'{valueint:04d}'  # zero padded 4 chars.
        binary = f'{int(valuestr):0>20b}'  # binary representation
        full = sign_bit + dec_key[dec] + binary  # 24 bit number
        hex_sp = f'{int(full, 2):x}'  # convert binary string to hex
        return hex_sp.upper()

    async def get_sp1(self, address: int = 1) -> typing.Optional[float]:
        """ Returns setpoint1 from an Omega with address: add
            Typical command *01R01\r
        """

        async def execute_read() -> typing.Optional[float]:
            cmd = f'*{address:02d}R01{self.TERMINATOR}'
            rt = self._omega_command(cmd)
            return self._decode_value(rt)

        return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(execute_read(), self._loop))

    async def set_sp1(self, value: float, address: int = 1) -> None:
        """ Sets setpoint1 to value on an Omega with address: add """

        address = int(address)
        value = float(value)

        async def execute_write() -> None:
            hex_sp = self._encode_value(value)
            cmd = f'*{address:02d}W01{hex_sp}{self.TERMINATOR}'
            self._omega_command(cmd, noread=True)

        return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(execute_write(), self._loop))


class Flow(_Controller):
    DELAY = 0.05

    def __init__(self, port=None):
        _Controller.__init__(self)
        if port is None:
            self._port = self._autodetect()
        else:
            self._port = serial.Serial(port=port, baudrate=19200, timeout=self.DELAY)
        claimed_serial_ports.insert(self._port.name)
        _LOGGER.debug(f'Opened an Omega flow controller on port {self._port.name}')

    def _is_on_port(self, port: serial.Serial) -> bool:
        port.write('\rA\r'.encode())
        time.sleep(self.DELAY)
        d = port.read(1000)
        return d is not None and len(d) > 0

    def _autodetect(self) -> serial.Serial:
        for port_info in serial.tools.list_ports.comports():
            if port_info.name in claimed_serial_ports:
                continue
            port = serial.Serial(port=port_info.name, baudrate=19200, timeout=self.DELAY)
            if not self._is_on_port(port):
                continue
            return port
        raise RuntimeError("Omega flow controller not found")


class Temperature(_Controller):
    DELAY = 0.3

    def __init__(self, port=None):
        _Controller.__init__(self)
        if port is None:
            self._port = self._autodetect()
        else:
            self._port = serial.Serial(port=port, baudrate=9600, timeout=self.DELAY)
        claimed_serial_ports.insert(self._port.name)
        _LOGGER.debug(f'Opened an Omega temperature controller on port {self._port.name}')

    def _is_on_port(self, port: serial.Serial) -> bool:
        port.write('*01R01\r'.encode())
        time.sleep(self.DELAY)
        d = port.read(1000)
        try:
            v = d[1:].decode()
            return v is not None and len(v) > 0
        except UnicodeDecodeError:
            return False

    def _autodetect(self) -> serial.Serial:
        for port_info in serial.tools.list_ports.comports():
            if port_info.name in claimed_serial_ports:
                continue
            port = serial.Serial(port=port_info.name, baudrate=9600, timeout=self.DELAY)
            if not self._is_on_port(port):
                continue
            return port
        raise RuntimeError("Omega flow controller not found")
