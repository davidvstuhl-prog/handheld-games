# PC Tester (handheld emulator)

Play the handheld games on a normal computer, inside a pretend handheld with
clickable buttons. Use it to test before the real hardware is built.

## Setup

1. Install **Python 3** from <https://www.python.org/downloads/>.
   On Windows, tick **"Add Python to PATH"** during install.
2. Install pygame:
   ```
   pip install pygame
   ```
3. From this folder, run:
   ```
   python handheld_emulator.py
   ```

The emulator loads the game from the `balloon-blitz` folder next to this one,
so keep both folders together.

## Controls

Click the on-screen buttons with the mouse (they light up while held), or use the keyboard:

| Handheld button | Keyboard |
|---|---|
| D-pad | Arrow keys |
| A | Z (or Space) |
| B | X (or Backspace) |
| L / R | A / S |
| START | Enter |
| SELECT | Tab |
| Pause / quit | Esc |

The window can be resized or maximized.
