# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

GSPC (Gas Sampler Process Controller) is a PyQt5 desktop control program for a custom gas sampling instrument. It conditions gas samples and triggers an external gas chromatograph (GC) by relay, then records run conditions and per-cycle results to disk. Production runs typically execute on a Windows machine attached to the physical hardware; development on macOS/Linux uses simulation mode.

## Common commands

```shell
# Editable install (Python >=3.7)
pip install -e .

# Run with simulated hardware (no physical instrument required)
gspc --simulate

# Verbose console logging
gspc --simulate --debug

# Run all tests
pytest tests/

# Run a single test
pytest tests/test_schedule.py::test_schedule_basic
```

There is no separate lint/format step configured in this repo. `tests/pfp_test.py` is not part of the pytest suite — it is a standalone serial-port utility for poking at PFP hardware directly.

## Architecture

### Two-thread split: Qt UI + asyncio loop

`gspc/__main__.py` starts a daemon thread that runs an asyncio event loop (`event_thread()`), then runs the Qt application on the main thread. **All hardware I/O lives on the asyncio loop; all UI updates must run on the Qt thread.** The bridge is in [gspc/util.py](gspc/util.py):

- `call_on_ui(callable)` posts work to the Qt thread via a `QCoreApplication.postEvent` / custom `QEvent` round-trip. Use this from inside coroutines whenever you touch widgets.
- `background_task(coro)` schedules a coroutine on the asyncio loop and keeps a strong reference so it isn't GC'd. Code on the Qt side calls into the loop via `loop.call_soon_threadsafe(lambda: background_task(...))`.
- `LogHandler` is a `logging.Handler` whose `emit` marshals records onto the Qt thread via a queued signal — used to feed the on-screen log panel.

Getting this wrong (touching Qt from the asyncio thread, or blocking the asyncio loop with sync I/O) is the most common class of bug.

### Hardware abstraction

[gspc/hw/interface.py](gspc/hw/interface.py) defines an `Interface` ABC covering every operation (read pressure/temperature/flow, set valves, sample/inject control, SSV/PFP positioning, etc.). Two concrete implementations exist:

- [gspc/hw/instrument.py](gspc/hw/instrument.py) — real hardware. Talks to a LabJack DAQ ([gspc/hw/lj.py](gspc/hw/lj.py)) via `labjack-ljm`, a stream selector valve ([gspc/hw/ssv.py](gspc/hw/ssv.py)) via `pyserial`, the PFP flask manifold ([gspc/hw/pfp.py](gspc/hw/pfp.py)), and pressure/Omega flow sensors. Digital and analog channel assignments are constants on `Instrument`.
- `Simulator` in [gspc/control.py](gspc/control.py) — drives the simulator UI in [gspc/ui/simulator.py](gspc/ui/simulator.py); selected by `--simulate`.

When adding a new hardware operation, add the abstract method to `Interface` and implement on both sides.

### Schedule engine — Runnables, Tasks, Gates

[gspc/schedule.py](gspc/schedule.py) is the heart of the program.

- A **`Runnable`** is one atomic step. It has an `origin` (target time, in seconds from schedule start) plus optional `set_events` / `clear_events` strings. It exposes `execute()` (background coroutine, doesn't delay the schedule) and `delay()` (runs in the foreground; if it returns `True` the time it consumed is absorbed and the schedule's zero point shifts). Most concrete runnables override one or the other.
- **`Gate`** is a `Runnable` that blocks `delay()` until N futures resolve — used to synchronize on conditions like "oven cooled" or "pressure stable".
- **`AbortPoint`** is a `Runnable` that aborts the schedule when its `delay()` runs *if* something previously called `.abort(msg)` on it. Used to defer aborts until a safe boundary.
- A **`Task`** has a `schedule(context)` method that returns a list of `Runnable`s with computed origin times, plus an `origin_advance` (how far this task moves the cycle origin forward). Tasks compose runnables; runnables don't know about tasks.
- **`Execute`** drives a sequence of tasks: at each step it picks the next runnable by origin time, kicks off its `execute()` in the background, awaits its `delay()`, then folds events and reaps completed background work. It also supports mid-run rescheduling and abort propagation.

### Tasks and how they're loaded

Concrete tasks live in [gspc/tasks/](gspc/tasks/) (`Flask`, `Tank`, `PFPFlask`, `Zero`, `Sample`, etc.). [gspc/tasks/__init__.py](gspc/tasks/__init__.py) imports them and calls `register_task(name, instance)` to populate the global `known_tasks` registry. The UI loads task files (CSV-style: one task name per line, optional comma-separated data) and matches names against this registry. To add a runnable task, register it there.

The cardinal task is `Sample` in [gspc/tasks/sample.py](gspc/tasks/sample.py). It schedules an entire ~22-minute sampling cycle: cryogen prep, vacuum sequence, sample valve open/close, GC injection trigger, pressure measurements before/after, and recording the result row. `Flask`/`Tank`/`PFPFlask`/`Zero` are thin wrappers that configure SSV / PFP positions then delegate to `Sample.schedule(...)`.

`CYCLE_SECONDS`, `SAMPLE_OPEN_AT`, `SAMPLE_SECONDS` in [gspc/const.py](gspc/const.py) define the cycle timing budget.

### Output and the Windows file-lock case

[gspc/output.py](gspc/output.py) owns two output files: `<name>.txt` (human log) and `<name>.xl` (tab-separated data, one row per cycle). All writes go through a single `threading.Lock` — these can be called from either thread.

Excel on Windows opens files with exclusive write access, so an operator viewing `<name>.xl` mid-run will cause `open(..., "a+")` to raise `PermissionError`. The module handles this transparently:

- `CycleData.write` / `CycleData.header` buffer pending lines in `_pending_data` / `_pending_header` on `PermissionError` and flush on the next successful open.
- A one-shot UI alert is fired through `set_lock_alert_handler(...)` (registered by `Window` in [gspc/control.py](gspc/control.py)) — popup shown once per lock event, with a recovery popup when the file becomes writable again.
- If the buffer exceeds `_PENDING_FLUSH_THRESHOLD` (~500 cycles) or the process exits with the file still locked, the buffer dumps to `<name>.xl.recovery` so nothing is lost.
- `log_message` silently drops lines when the log file is locked (it would recurse into the logging system otherwise).

If you change anything in `output.py`, keep both the buffered path and the alert state-machine working: every successful write must clear the active lock alert, and every flush must respect the "header only when file is empty" invariant.
