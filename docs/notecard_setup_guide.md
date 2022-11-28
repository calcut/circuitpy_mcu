
Download a suitable release
https://github.com/calcut/circuitpy_mcu/releases/

rename the folder so it appears as
CIRCUITPY/circuitpy_mcu

IN CIRCUITPY, create/update the following files
secrets.py
code.py
boot.py (if using github OTA method)

Examples are provided in the circuitpy_mcu/templates folder
Be sure to update wifi credentials (if using) and the Notehub productUID

Download zip from here (use the main branch, not a release)
https://github.com/blues/note-python

Place the "notecard" folder in the CIRCUITPY/lib folder

Make sure the notecard is powered via the notecarrier board (e.g. microUSB).
This is particularly important for cellular notecards, which will typically draw too much for a PC USB port.
