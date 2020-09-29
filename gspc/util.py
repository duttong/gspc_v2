import typing
import logging
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
    """Call a function on the the UI thread"""
    QtCore.QCoreApplication.postEvent(_receiver_object, _CallEvent(f))


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
