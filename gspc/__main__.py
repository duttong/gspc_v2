import sys
import asyncio
import logging
from gspc.util import initialize_ui_thread, background_task
from gspc.output import install_output_log_handler
from threading import Thread, Event
from PyQt5 import QtWidgets
from gspc.control import Window


def event_thread():
    loop = asyncio.new_event_loop()

    def _run():
        asyncio.set_event_loop(loop)
        loop.run_forever()

    Thread(name="EventProcessing", target=_run, daemon=True).start()
    return loop


def main():
    loop = event_thread()
    app = QtWidgets.QApplication(sys.argv)

    root_logger = logging.getLogger()
    if "--debug" in app.arguments():
        root_logger.setLevel(logging.DEBUG)
        console = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s %(name)s: %(message)s')
        console.setFormatter(formatter)
        console.setLevel(logging.DEBUG)
        root_logger.addHandler(console)
    else:
        root_logger.setLevel(logging.INFO)

    initialize_ui_thread()

    enable_pfp: bool = True
    if "--simulate" in app.arguments():
        from gspc.ui.simulator import Display
        from gspc.control import Simulator
        simulator = Display()
        simulator.show()
        interface = Simulator(loop, simulator)
    else:
        from gspc.hw.instrument import Instrument
        interface = Instrument(loop)
        enable_pfp = interface.has_pfp
        loop.call_soon_threadsafe(lambda: background_task(interface.initialization()))

    window = Window(loop, interface, enable_pfp=enable_pfp)
    window.show()

    install_output_log_handler()

    rc = app.exec_()
    shutdown_complete = Event()

    async def safe_shutdown():
        await interface.shutdown()
        shutdown_complete.set()

    loop.call_soon_threadsafe(lambda: background_task(safe_shutdown()))
    shutdown_complete.wait(30)
    sys.exit(rc)


if __name__ == "__main__":
    sys.exit(main())
