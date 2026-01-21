import asyncio
import logging
import typing
from threading import Thread
from labjack import ljm

_LOGGER = logging.getLogger(__name__)


class LabJack:
    """A simple interface to a LabJack device that wraps the vendor library in an asyncio friendly interface."""

    def __init__(self):
        self._loop = asyncio.new_event_loop()
        self._handle = None
        # Use a dedicated thread, since we have no idea how the vendor library handles concurrency
        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        self._handle = ljm.open(ljm.constants.dtANY, ljm.constants.ctANY, "ANY")
        info = ljm.getHandleInfo(self._handle)
        _LOGGER.debug(
            f'Opened a LabJack with Device type: {info[0]}, Connection type: {info[1]}, Serial number: {info[2]}')

        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    async def read_analog(self, *addresses: int) -> float:
        """Read one or more analog values from the specified addresses."""

        async def execute_read() -> typing.Tuple[float, ...]:
            if len(addresses) > 1:
                names = []
                for add in addresses:
                    names.append(f'AIN{add}')
                result = ljm.eReadNames(self._handle, len(names), names)
                _LOGGER.debug(f'Read LabJack analog channels {addresses}: {result}')
                return tuple(result)
            else:
                cmd = f'AIN{addresses[0]}'
                result = ljm.eReadName(self._handle, cmd)
                _LOGGER.debug(f'Read LabJack analog channel {addresses[0]}: {result}')
                return result

        return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(execute_read(), self._loop))

    async def read_therm(self, address: int, *, ef_read: str = "A") -> float:
        """Read a thermistor/thermocouple value via AIN EF (e.g., AIN#_EF_READ_A)."""
        ef_read = ef_read.upper()
        if ef_read not in {"A", "B"}:
            raise ValueError("ef_read must be 'A' or 'B'")

        async def execute_read() -> float:
            cmd = f'AIN{address}_EF_READ_{ef_read}'
            result = ljm.eReadName(self._handle, cmd)
            _LOGGER.debug(f'Read LabJack therm value {cmd}: {result}')
            return result

        return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(execute_read(), self._loop))

    async def configure_ain_ef(
        self,
        address: int,
        ef_index: int,
        *,
        config: typing.Optional[typing.Dict[str, float]] = None,
    ) -> None:
        """Configure AIN EF for a channel using EF index and optional config A-F values."""
        config = config or {}
        names = [f'AIN{address}_EF_INDEX']
        values = [ef_index]
        for key, value in sorted(config.items()):
            key = key.upper()
            if key not in {"A", "B", "C", "D", "E", "F"}:
                raise ValueError("EF config keys must be A-F")
            names.append(f'AIN{address}_EF_CONFIG_{key}')
            values.append(value)

        async def execute_write() -> None:
            ljm.eWriteNames(self._handle, len(names), names, values)
            _LOGGER.debug(
                f'Configured LabJack AIN{address} EF index {ef_index} with {config}')

        return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(execute_write(), self._loop))

    async def configure_thermocouple_type_e(
        self,
        address: int,
        *,
        ef_index: int = 22,
        cjc_source: typing.Optional[int] = None,
        cjc_address: typing.Optional[int] = None,
        units: typing.Optional[int] = None,
    ) -> None:
        """Configure AIN EF for a Type E thermocouple (defaults match T-series)."""
        config = {"A": ljm.constants.ttE}
        if cjc_source is not None:
            config["B"] = cjc_source
        if cjc_address is not None:
            config["C"] = cjc_address
        if units is None:
            units = getattr(ljm.constants, "tempC", 1)
        if units is not None:
            config["D"] = units
        await self.configure_ain_ef(address, ef_index, config=config)

    async def write_analog(self, address: int, value: float) -> None:
        """Set a single analog channel."""

        async def execute_write() -> None:
            cmd = f'DAC{address}'
            ljm.eWriteName(self._handle, cmd, value)
            _LOGGER.debug(f'Write LabJack analog channel {address}: {value:.2f}')

        return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(execute_write(), self._loop))

    async def read_digital(self, address: str) -> bool:
        """Read a single digital channel."""

        async def execute_read() -> bool:
            cmd = f'{address}'
            result = ljm.eReadName(self._handle, cmd)
            if result:
                result = True
                _LOGGER.debug(f'Read LabJack digital channel {address}: HIGH')
            else:
                result = False
                _LOGGER.debug(f'Read LabJack digital channel {address}: LOW')
            return result

        return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(execute_read(), self._loop))

    async def write_digital(self, address: str, state: bool) -> None:
        """Set a single digital channel."""
        if state:
            state = 0
        else:
            state = 1

        async def execute_write() -> None:
            cmd = f'{address}'
            ljm.eWriteName(self._handle, cmd, state)
            if state != 0:
                _LOGGER.debug(f'Write LabJack digital channel {address}: HIGH')
            else:
                _LOGGER.debug(f'Write LabJack digital channel {address}: LOW')

        return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(execute_write(), self._loop))

    async def disconnect(self) -> None:
        """Disconnect from the LabJack, no further communication is possible"""

        async def execute_action():
            ljm.close(self._handle)
            _LOGGER.debug(f'LabJack disconnected')
            self._handle = None

        return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(execute_action(), self._loop))


if __name__ == '__main__':
    import argparse

    opt = argparse.ArgumentParser(
        description='Basic control of a T7 LabJack'
    )
    opt.add_argument('--high', action='store', metavar='CHANNEL',
                     dest='high', help='Set digital address to high (1)')
    opt.add_argument('--low', action='store', metavar='CHANNEL',
                     dest='low', help='Set digital address to low (0)')
    opt.add_argument('--tog', action='store', metavar='CHANNEL',
                     dest='tog', help='Toggle digital address from low to high to low for one second')
    opt.add_argument('--therm', action='store', metavar='AIN',
                     dest='therm', help='Read thermocouple temperature from AIN for 10 seconds')

    options = opt.parse_args()

    t7 = LabJack()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)


    async def dout():
        if options.high:
            await t7.write_digital(options.high, True)

        if options.low:
            await t7.write_digital(options.low, False)

        if options.tog:
            await t7.write_digital(options.tog, False)
            await asyncio.sleep(0.05)
            await t7.write_digital(options.tog, True)
            await asyncio.sleep(1)
            await t7.write_digital(options.tog, False)


    async def ain():
        while True:
            ain = await t7.read_analog(0)
            print(f'Read value: {ain}')
            await asyncio.sleep(1)

    async def therm():
        for _ in range(10):
            temp = await t7.read_therm(int(options.therm))
            print(f'Thermocouple AIN{options.therm}: {temp:.2f} °C')
            await asyncio.sleep(1)
        await t7.disconnect()
        loop.stop()

    t1 = loop.create_task(dout())
    if options.therm is not None:
        t2 = loop.create_task(therm())
    else:
        t2 = loop.create_task(ain())
    loop.run_forever()
