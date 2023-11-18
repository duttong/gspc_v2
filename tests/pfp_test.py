#! /usr/bin/env python
""" Simple PFP test program using similar code as gspc pfp.py 
    Geoff 231117 
"""
from time import sleep
import argparse
import typing
import re
import serial
import serial.tools.list_ports


class pfp_test():
    TIMEOUT = 1

    def __init__(self, port: typing.Optional[typing.Union[str, serial.Serial]] = None):
        port = serial.Serial(port=port, baudrate=9600,
                            timeout=self.TIMEOUT, inter_byte_timeout=0, write_timeout=0)
        self._port = port

    @staticmethod
    def _get_unload_prompt(port: serial.Serial) -> bool:
        try:
            port.reset_input_buffer()
            port.write(b'\r')
            resp = port.readlines()
            resp = ''.join(map(str, resp))
            if "UNLOAD>" in resp:
                return True
            for i in range(5):
                if "AS>" in resp:
                    break
                port.reset_input_buffer()
                port.write(b'Q\r')
                resp = port.readlines()
                resp = ''.join(map(str, resp))
            else:
                print(f'Failed to reach UNLOAD prompt, AS> not found.')
                return False
            port.write(b'U\r')
            resp = port.readlines()
            resp = ''.join(map(str, resp))
            if "UNLOAD>" in resp:
                return True
        except (ValueError, serial.SerialException) as e:
            print(f'Exception found. Failed to reach UNLOAD prompt. {e}')

        print(f'Failed to reach UNLOAD prompt.')
        return False

    def _prompt_unload(self):
        if not self._get_unload_prompt(self._port):
            print("Failed to get unload prompt from pfp")

    def read_pressure(self) -> float:
        """Read the current pressure
           updated with readlines method and regex decoding. GSD """

        self._prompt_unload()
        self._port.write(b"P\r")
        response = self._port.readlines()
        response = ''.join([s.decode("utf-8") for s in response])
        m = re.search(r' (\d+.\d+)', response)
        if m is None:
            return -1
        return float(m.group(1))
    
    def open_valve(self, pos: int) -> str:
        """Open a sample valve
           switched to readlines method
           returns valve and status """

        self._prompt_unload()
        self._port.write(b"O\r%d\r" % pos)
        print(f"Attempting to Open PFP valve {pos}")
        sleep(10)
        response = self._port.readlines()
        response = ''.join([s.decode("utf-8") for s in response])
        return response[24:-8].strip()

    def close_valve(self, pos: int) -> str:
        """Close a sample valve"""

        self._prompt_unload()
        self._port.write(b"C\r%d\r" % pos)
        print(f"Attempting to Close PFP valve {pos}")
        sleep(10)
        response = self._port.readlines()
        response = ''.join([s.decode("utf-8") for s in response])
        return response[24:-8].strip()


if __name__ == '__main__':

    opt = argparse.ArgumentParser(
    description='PFP comms test program'
    )
    opt.add_argument('-p', action='store_true', help=f'Read PFP pressure.')
    opt.add_argument('-o', action='store', metavar='VALVE', help='Open a PFP.')
    opt.add_argument('-c', action='store', metavar='VALVE', help='Close a PFP.')

    options = opt.parse_args()

    pfp = pfp_test('COM11')

    if options.p:
        p = pfp.read_pressure()
        print(f'PFP pressure {p:.2f}')
    elif options.o is not None:
        response = pfp.open_valve(int(options.o))
        print(f'Open PFP {options.o}: {response}')
    elif options.c is not None:
        response = pfp.close_valve(int(options.c))
        print(f'Close PFP {options.c}: {response}')
