# Gas Sampler Process Controller

This is a control program for a custom gas sampling instrument.  It is designed to control the selection and conditioning of as samples or references into a stand along gas chromatograph.  In general this process involves conditioning the gas to be sampled then triggering the gas chromatograph with a relay signal.  General results about the conditions and sample time are written to a results log file.

The control process operates by performing a series "runnable items" that compose a "task".  The runnable items include direct control manipulation (e.x. changing the valves) as well as gating mechanisms (e.x. waiting for cooling).  The tasks are higher level scheduling mechanisms (e.x. "Sample Flask 1").  Tasks themselves may also alter their run sequence depending on the time in the task sequence they are scheduled (e.x. to cooling down things ahead of time while the previous task is still completing other runnable items). 

The scheduling is controlled by tasks files.  These are simple comma separate files that consist of a task ID name followed by optional task data.  Additionally, there are a number of default basic sampling tasks available.

## Example Task File

Below is an extremely basic task file.

```
Zero
Tank 0
Flask 1
Flask 3
Zero
```

## Getting Started

For local development or testing, running the system in a Python virtual environment is the simplest approach.  To get this ready, the following sequence of commands can be used:

```shell
git clone https://gitlab.com/derek.hageman/gspc.git gspc
cd gspc
python3 -m venv venv
. venv/bin/activate
pip3 install -e .
```

You can then run the program in simulation mode.  In simulation mode, an additional window is created showing the inputs and outputs  to the control process.  This can be used without physical hardware to see how the program would manipulate things.

```shell
gspc --simulate
```
