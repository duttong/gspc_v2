#! /usr/bin/env python

import pandas as pd
from time import sleep, time
import argparse

from labjack import ljm


class t7_labjack():

    def __init__(self):
        self.handle = self.connect_labjack()
        self.df = None

    def connect_labjack(self):
        # Open first found LabJack
        handle = ljm.open(ljm.constants.dtANY, ljm.constants.ctANY, "ANY")
        info = ljm.getHandleInfo(handle)
        print(f"Opened a LabJack with Device type: {info[0]}, \
            Connection type: {info[1]}, Serial number: {info[2]}")
        return handle
    
        

    def analog(self, address):
        """ Returns a value from one analog channel """
        
        
        cmd = f'AIN{address}'
        return ljm.eReadName(self.handle, cmd)
    

    def analogs(self, addresses):
        """ Returns values from an integer list of analog channels """
        cmds = [f'AIN{add}' for add in addresses]
        return ljm.eReadNames(self.handle, len(cmds), cmds)
        """ Returns a value from one digital channel """
        cmd = f'FIO{address}'
        return ljm.eReadName(self.handle, cmd)

    def dio_multi_read(self, addresses):
        """ Returns a value from a list of digital channels """
        cmds = [f'FIO{add}' for add in addresses]
        return ljm.eReadNames(self.handle, len(cmds), cmds)

    def dio_write(self, address, state):
        """ Sets a digital state (0 or 1) for one digital channel """
        cmd = f'FIO{address}'
        ljm.eWriteName(self.handle, cmd, state)

    def disconnect(self):
        ljm.close(self.handle)


if __name__ == '__main__':

    opt = argparse.ArgumentParser(
        description='Basic control of a T7 LabJack'
    )
    opt.add_argument('--high', action='store', metavar='ADD',
        dest='high', help='Set digital address to high (1)')
    opt.add_argument('--low', action='store', metavar='ADD',
        dest='low', help='Set digital address to low (0)')
    opt.add_argument('--tog', action='store', metavar='ADD',
        dest='tog', help='Toggle digital address from low to high to low for one second')

    options = opt.parse_args()

    t7 = t7_labjack()

    if options.high:
        t7.dio_write(options.high, 1)

    if options.low:
        t7.dio_write(options.low, 0)

    if options.tog:
        t7.dio_write(options.tog, 0)
        sleep(0.05)
        t7.dio_write(options.tog, 1)
        sleep(1)
        t7.dio_write(options.tog, 0)
