import sys
import asyncio
import logging
from threading import Thread, Event

from gspc.util import initialize_ui_thread, background_task
from gspc.output import install_output_log_handler
from gspc.schedule import Task, Execute
from gspc.hw.instrument import Instrument
from gspc.tasks.flow import FeedbackFlow


def event_thread():
    loop = asyncio.new_event_loop()

    def _run():
        asyncio.set_event_loop(loop)
        loop.run_forever()

    Thread(name="EventProcessing", target=_run, daemon=True).start()
    return loop


class TestTask(Task):
    def schedule(self, context):
        return [ FeedbackFlow(context, context.origin, 5) ]


loop = event_thread()

interface = Instrument(loop)
enable_pfp = interface.has_pfp
loop.call_soon_threadsafe(lambda: background_task(interface.initialization()))


exe = Execute([TestTask()])
exe.execute(interface)
#loop.run_until_complete(exe.execute(interface))