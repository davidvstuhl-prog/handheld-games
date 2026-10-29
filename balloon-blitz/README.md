# Balloon Blitz 🎈

A balloon-popping tower defense game (inspired by Bloons TD 6) for the
homemade Raspberry Pi handheld. To play it on a computer, use the
emulator in [`../pc-tester`](../pc-tester).

## How to play

- Balloons follow the dirt track. Pop them before they reach the end.
  Each balloon that escapes costs lives (big balloons cost more, because
  everything inside them escapes too).
- **L / R** picks a tower to build, **A** builds it at the cursor.
- **A** on a tower opens its menu: buy upgrades, change targeting, or sell it.
- **START** sends the next round (and pauses during a round).
- **SELECT** toggles fast-forward.
- **B** opens the menu (auto-start, sound, restart, quit).
- **Sound slider:** on the title screen and in the B menu. Left/right changes the
  volume in 10% steps; A mutes and unmutes. Your setting is remembered.
- Beat **round 30** to win, then keep going in freeplay.
- **Easy** starts with $850 (instead of $650), slower balloons and cheaper towers.

### Auto-start

With **Auto-start ON**, each new round starts by itself 2 seconds after the
last one ends (press START to skip the wait). An **AUTO** badge shows in the
top bar while it's on. Turn it on or off from the title screen or from the
**B** menu during a game; the game remembers your choice. You always start
round 1 yourself, so you have time to build.

### Towers

| Tower | Cost | What it does |
|---|---|---|
| Dart Tower | $170 | Throws darts at one balloon; top upgrade rolls a bouncing Spike Ball |
| Tack Shooter | $280 | Fires 12 tacks in every direction |
| Boomerang | $325 | Curved throw that comes back, pops a lot (set Left/Right curve in its menu) |
| Bomb Tower | $500 | Explosions pop groups and lead (not black) |
| Glue Gunner | $200 | Fast-firing glue slows balloons; acid glue pops them |
| Frost Tower | $350 | Freezes balloons around it |
| Ninja | $400 | Fast throwing stars, sees camo |
| Sniper | $350 | Hits anything anywhere on the map |
| Wizard | $320 | Magic pops every balloon type; Lightning Bolt and Dragon's Breath upgrades |
| Spike Factory | $650 | Drops spike piles on the track (only during rounds) |
| Village | $900 | Boosts towers in its circle: range, camo, speed, discounts, money |
| Super Tower | $2200 | A storm of darts |
| Coin Mine | $600 | Earns money every round |

The shop bar shows 7 towers at a time; press L / R to scroll through all 13.
All towers attack a bit faster than their upgrade descriptions suggest (a 15% power boost),
and darts, tacks, boomerangs, stars, magic and the Super Tower pop one extra balloon per shot.

Every tower has **two upgrade paths with 3 levels each**. Only one path can
reach level 3 (like in BTD6).

### Maps

| Map | Difficulty | What's special |
|---|---|---|
| Meadow | Easy | Long winding track |
| Lake Loop | Easy | A lake in the middle you can't build on |
| Crossroads | Medium | The track crosses itself |
| Spiral | Medium | Spirals into a hole in the middle |
| Rapids | Hard | Short track |
| Twin Lanes | Hard | Two tracks, balloons take turns (+$300 to start, 30% bigger round bonus) |
| Canyon | Hard | Staircase track, rocks block good spots |

### Balloons to watch out for

- **Lead** (gray): darts and tacks bounce off. Use bombs, fire, magic, or Full Metal snipers.
- **Black**: ignores explosions.
- **White**: can't be frozen.
- **Zebra**: ignores both explosions and freezing.
- **Camo** (green spots): only towers with camo vision can target them
  (Ninja, Eagle Eye, Night Scope, Radar Reload, Wizard Sight, Cold Snap,
  Night Goggles, or any tower inside a Village with Radar Hut).
- **Ceramic**: takes 10 hits.
- **Blimp** (round 25) and **Titan** (round 30): giant bosses with health bars.

## Run it on the handheld

On the Raspberry Pi (Raspberry Pi OS):

```
sudo apt install python3-pygame
python3 balloon_blitz.py --fullscreen
```

| Option | What it does |
|---|---|
| `--fullscreen` | Fill the whole screen |
| `--buttons` | Start on the button test screen |
| `--rotate 90` | Turn the picture if your screen shows sideways |
| `--fps 30` | Lower frame rate to save battery |
| `--mute` | No sound |

### Setting up your buttons

The Pico board sends your buttons to the Pi as a USB gamepad. Run the game
with `--buttons`, press each button, and write down the number it shows.
Then change the numbers in `PAD_BUTTONS` near the top of `balloon_blitz.py`:

```python
PAD_BUTTONS = {
    "A": 0, "B": 1, "SELECT": 2, "START": 3, "L": 4, "R": 5,
    "UP": 6, "DOWN": 7, "LEFT": 8, "RIGHT": 9,
}
```

(If your D-pad shows up as a "hat" or as axes, it already works without
changing anything.) To leave the button test, hold any button for 3 seconds.

Best rounds and settings are saved in `~/.balloon_blitz.json`.
