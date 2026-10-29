# Balloon Blitz CE 🎈 (TI-84 Plus CE)

A smaller version of [Balloon Blitz](../balloon-blitz) for the **TI-84 Plus CE**
graphing calculator, written in C.

- 8 towers: Dart Tower, Tack Shooter, Bomb Tower, Frost Tower, Sniper, Ninja,
  Glue Gunner, Wizard (each with 2 upgrade paths, 2 levels each)
- 4 maps (Meadow, Lake Loop, Crossroads, Rapids) and 3 difficulties
- 30 rounds plus freeplay, camo balloons, lead, ceramics and the Blimp boss
- Auto-start, fast forward, and your best round on each map is saved

## Controls

| Key | What it does |
|---|---|
| Arrows | Move the cursor (tile by tile) |
| `[2nd]` | Build a tower, or open a tower's upgrade menu / choose |
| `[alpha]` | Back / close |
| `[y=]` / `[window]` | Pick which tower to build |
| `[enter]` | Send the next round |
| `[graph]` | Fast forward on/off |
| `[mode]` or `[clear]` | Pause menu (resume, auto-start, restart, quit) |

In a tower's menu: choose an upgrade with the arrows and press `[2nd]` to buy it.
On the *Target* row, left/right changes which balloon it shoots first.

## 1. Build it (make the `.8xp` file)

You need the free **CE C Toolchain**:
<https://github.com/CE-Programming/toolchain/releases>

**Windows**
1. Download `CEdev-Windows.zip` and unzip it somewhere simple, like `C:\CEdev`.
2. Double-click `cedev.bat` in that folder. A command window opens.
3. In that window, go to this folder and build:
   ```
   cd path\to\handheld-games\ti84-ce
   make
   ```
4. The game is now at `bin\BBLITZ.8xp`.

(On Mac/Linux it's the same: download `CEdev-macOS`/`CEdev-Linux`, add its
`bin` folder to your PATH, then run `make` here.)

## 2. Put it on the calculator

1. Install **TI Connect CE** (free from TI) and plug in the calculator.
2. Send **the CE C libraries** first. Download `clibs.8xg` from
   <https://github.com/CE-Programming/libraries/releases> and send it. The game
   needs these (they include graphx, keypadc and fileioc). You only do this once.
3. Send `bin\BBLITZ.8xp`.
4. On the calculator: press `[prgm]`, choose `BBLITZ`, press `[enter]`
   (it pastes `Asm(prgmBBLITZ)` or `prgmBBLITZ`), then `[enter]` again.

### "My calculator won't run it" (OS 5.5 and newer)

TI's newer operating systems (5.5 and up) block C/assembly programs. Check
yours with `[2nd]` `[+]` → **About**. If it's 5.5 or newer, the Cemetech
community's free **arTIfiCE** tool lets you run them again. Search for
"arTIfiCE" on <https://www.cemetech.net>, check which OS versions it supports,
and follow its steps carefully.

## About the code

Everything is in `src/main.c`. The game runs at about 30 frames per second
and is grid based (towers sit on 20×20 tiles of a 16×10 map). Balloon
pictures are drawn once at the start and then copied each frame, which is much
faster on the calculator than drawing circles every time.
