import typing
import logging
import asyncio
import threading
from PyQt5 import QtCore


class _CallEvent(QtCore.QEvent):
    def __init__(self, f: typing.Callable[[], None]):
        QtCore.QEvent.__init__(self, QtCore.QEvent.User)
        self.f = f


class _Receiver(QtCore.QObject):
    def customEvent(self, event):
        event.f()


_receiver_object = None


def initialize_ui_thread() -> None:
    """Initialize the thread used to receive calls for the UI"""
    global _receiver_object
    _receiver_object = _Receiver()


def call_on_ui(f: typing.Callable[[], None]) -> None:
    """Call a function on the UI thread"""
    QtCore.QCoreApplication.postEvent(_receiver_object, _CallEvent(f))


_background_tasks = threading.local()


def background_task(coro: typing.Awaitable) -> asyncio.Task:
    """Put a task into the background, keeping a reference, so it does not get GCed"""
    r = asyncio.get_event_loop().create_task(coro)
    task_storage = getattr(_background_tasks, 'task_storage', None)
    if task_storage is None:
        task_storage = set()
        _background_tasks.task_storage = task_storage
    task_storage.add(r)
    r.add_done_callback(lambda task: task_storage.discard(r))
    return r


class LogHandler(logging.Handler):
    """A logging handler that synchronizes to the Qt thread it was created from"""

    class _LogSignal(QtCore.QObject):
        log_record = QtCore.pyqtSignal(str, logging.LogRecord)

    def __init__(self, slotfunc: typing.Callable[[str, logging.LogRecord], None], *args, **kwargs):
        logging.Handler.__init__(self, *args, **kwargs)
        self.log_signal = self._LogSignal()
        self.log_signal.log_record.connect(slotfunc, type=QtCore.Qt.QueuedConnection)

    def emit(self, record: logging.LogRecord) -> None:
        s = self.format(record)
        self.log_signal.log_record.emit(s, record)
