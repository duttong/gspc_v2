import logging
import typing
import threading


_lock = threading.Lock()
_log_file: typing.Optional[str] = None
_data_file: typing.Optional[str] = None


def log_message(line: str):
    with _lock:
        if _log_file is None:
            return
        with open(_log_file, "at+") as f:
            f.write(line)
            f.write("\n")


def install_output_log_handler():
    class _Handler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            log_message(self.format(record))
    log_format = logging.Formatter('%(asctime)s: %(message)s')
    log_handler = _Handler()
    log_handler.setFormatter(log_format)
    log_handler.setLevel(logging.INFO)
    root_logger = logging.getLogger()
    root_logger.addHandler(log_handler)


class CycleData:
    def __init__(self):
        self.data: typing.Dict[str, str] = dict()

    @staticmethod
    def write(line: str):
        with _lock:
            if _data_file is None:
                return
            with open(_data_file, "a+") as f:
                f.write(line)
                f.write("\n")

    @staticmethod
    def header(line: str):
        with _lock:
            if _data_file is None:
                return
            with open(_data_file, "a+") as f:
                if f.tell() != 0:
                    return
                f.write(line)
                f.write("\n")

    @staticmethod
    def current_file_name() -> typing.Optional[str]:
        with _lock:
            return _data_file

    def finish(self):
        pass

    def abort(self, message: typing.Optional[str] = None):
        pass


_active_cycle: typing.Optional[CycleData] = None


def begin_cycle(data: CycleData):
    global _active_cycle
    with _lock:
        _active_cycle = data


def complete_cycle():
    global _active_cycle
    with _lock:
        data: typing.Optional[CycleData] = _active_cycle
        _active_cycle = None
    if data is None:
        return
    data.finish()


def abort_cycle(message: typing.Optional[str]):
    global _active_cycle
    with _lock:
        data: typing.Optional[CycleData] = _active_cycle
        _active_cycle = None
    if data is None:
        return
    data.abort(message)


def set_output_name(name: str):
    global _log_file
    global _data_file
    with _lock:
        if len(name) < 1:
            _log_file = None
            _data_file = None
            return
        _log_file = name + ".txt"
        _data_file = name + ".xl"

