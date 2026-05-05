import logging
import typing
import threading
import atexit


_lock = threading.Lock()
_log_file: typing.Optional[str] = None
_data_file: typing.Optional[str] = None

# Buffered cycle data while the data file is locked by another program (the
# typical Windows case is the operator viewing the .xl file in Excel, which
# blocks the program from opening it for write). Flushed on the next
# successful open, or to a sidecar recovery file at shutdown / threshold.
_pending_header: typing.Optional[str] = None
_pending_data: typing.List[str] = []
_PENDING_FLUSH_THRESHOLD = 500

_data_locked_alert_active = False
_lock_alert_handler: typing.Optional[typing.Callable[[str, bool], None]] = None


def set_lock_alert_handler(handler: typing.Optional[typing.Callable[[str, bool], None]]) -> None:
    """Register a non-blocking callback invoked when the data file becomes
    locked by another program or recovers. Called with (message, recovered)."""
    global _lock_alert_handler
    _lock_alert_handler = handler


def _fire_alert(message: str, recovered: bool) -> None:
    handler = _lock_alert_handler
    if handler is None:
        return
    try:
        handler(message, recovered)
    except Exception:
        pass


def _on_locked() -> None:
    global _data_locked_alert_active
    if _data_locked_alert_active:
        return
    _data_locked_alert_active = True
    _fire_alert(
        "Cycle data could not be written because the output file is open in "
        f"another program:\n\n{_data_file}\n\n"
        "Please close the file. Sample data will be buffered in memory until then.",
        False,
    )


def _on_recovered() -> None:
    global _data_locked_alert_active
    if not _data_locked_alert_active:
        return
    _data_locked_alert_active = False
    _fire_alert("Output data file is writable again. Buffered data has been written.", True)


def _flush_pending_to_open_file(f) -> None:
    global _pending_header, _pending_data
    if _pending_header is not None and f.tell() == 0:
        f.write(_pending_header)
        f.write("\n")
    _pending_header = None
    if _pending_data:
        for buffered in _pending_data:
            f.write(buffered)
            f.write("\n")
        _pending_data = []


def _flush_pending_to_recovery() -> None:
    global _pending_header, _pending_data
    if _data_file is None:
        _pending_header = None
        _pending_data = []
        return
    sidecar = _data_file + ".recovery"
    try:
        with open(sidecar, "a+") as f:
            _flush_pending_to_open_file(f)
    except OSError:
        _pending_header = None
        _pending_data = []


def log_message(line: str):
    with _lock:
        if _log_file is None:
            return
        try:
            with open(_log_file, "at+") as f:
                f.write(line)
                f.write("\n")
        except PermissionError:
            # Log file is locked by another program; drop this line.
            # Do not call into logging from here — log_message is itself a
            # logging sink and would recurse.
            pass


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
        global _pending_data
        with _lock:
            if _data_file is None:
                return
            try:
                with open(_data_file, "a+") as f:
                    _flush_pending_to_open_file(f)
                    f.write(line)
                    f.write("\n")
            except PermissionError:
                _pending_data.append(line)
                _on_locked()
                if len(_pending_data) >= _PENDING_FLUSH_THRESHOLD:
                    _flush_pending_to_recovery()
                return
            _on_recovered()

    @staticmethod
    def header(line: str):
        global _pending_header
        with _lock:
            if _data_file is None:
                return
            try:
                with open(_data_file, "a+") as f:
                    if f.tell() == 0:
                        f.write(line)
                        f.write("\n")
                        _pending_header = None
                    _flush_pending_to_open_file(f)
            except PermissionError:
                if _pending_header is None:
                    _pending_header = line
                _on_locked()
                return
            _on_recovered()

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
    global _pending_header, _pending_data, _data_locked_alert_active
    with _lock:
        # Flush any buffered data to the previous file (or its recovery sidecar)
        # before switching, so a rename mid-run doesn't lose buffered samples.
        if (_pending_header is not None or _pending_data) and _data_file is not None:
            try:
                with open(_data_file, "a+") as f:
                    _flush_pending_to_open_file(f)
            except OSError:
                _flush_pending_to_recovery()
        _pending_header = None
        _pending_data = []
        _data_locked_alert_active = False
        if len(name) < 1:
            _log_file = None
            _data_file = None
            return
        _log_file = name + ".txt"
        _data_file = name + ".xl"


def _flush_pending_at_exit() -> None:
    """Final attempt to flush buffered cycle data when the program exits.
    Falls back to a sidecar recovery file if the primary is still locked."""
    with _lock:
        if _pending_header is None and not _pending_data:
            return
        if _data_file is not None:
            try:
                with open(_data_file, "a+") as f:
                    _flush_pending_to_open_file(f)
                return
            except OSError:
                pass
        _flush_pending_to_recovery()


atexit.register(_flush_pending_at_exit)
