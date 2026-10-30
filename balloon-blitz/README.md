# Balloon Blitz 🎈

A balloon-popping tower defense game (inspired by Bloons TD 6) for the
homemade Raspberry Pi handheld. To play it on a computer, use the
emulator in [`../pc-tester`](../pc-tester).

## Home screen

- **Continue**: carry on your saved game (shown when you have one)
- **Play**: pick a map (left/right flips through them, with a picture, difficulty badge
  and your best round), pick Easy / Normal / Hard, then **START!**
- **Towers & Heroes**: every tower and hero has its own tab. Flip through them with
  the **L / R** bumpers to see all 9 upgrades (3 paths) and every ability, or a hero's
  stats and abilities as it levels up
- **Settings**: auto-start, sound slider and the button test
- **How to Play** and **Quit**

## How to play

- Balloons follow the dirt track. Pop them before they reach the end.
  Each balloon that escapes costs lives (big balloons cost more, because
  everything inside them escapes too).
- **L / R** picks a tower or hero to build, **A** builds it at the cursor.
- **A** on a tower opens its menu: upgrades, abilities, targeting, selling.
- **START** sends the next round (and pauses during a round).
- **SELECT** changes the speed: **1x → 2x → 3x**.
- **L + R together** (or **D** on a keyboard) opens the **ability bar**.
- **B** opens the game menu (auto-start, sound slider, restart, quit).
- Beat **round 30** to win, then keep going in freeplay.
- **Easy** starts with $850 (instead of $650), slower balloons and cheaper towers.

### Saving

The game **saves after every round**. Pick **Continue** on the title screen to
carry on where you left off (a game over clears the save).

### Upgrades: 3 paths

Every tower has **three upgrade paths with 3 levels each**:

- **Top (orange)** and **bottom (blue)**: stronger attacks, range, camo and so on.
- **Middle (green)**: its **level 3 unlocks an ability** you fire yourself.
- Only **2 paths per tower** can be upgraded, and only **one** of them can reach level 3.

Before you buy, the menu shows exactly what an upgrade changes, like
`> Pierce 3>5, Speed 1.2/s>1.5/s`.

### Abilities

Press **L + R** to open the ability bar, pick one with left/right, and press **A**.
Each one then recharges (shown as a countdown on its button).

| Tower | Ability | What it does |
|---|---|---|
| Dart Tower | Dart Storm | 4x faster darts for 6s |
| Tack Shooter | Tack Nova | 48 tacks in every direction |
| Boomerang | Rang Barrage | 12 boomerangs at once |
| Bomb Tower | Carpet Bomb | Explosions all along the front of the balloons |
| Glue Gunner | Glue Rain | Glues every balloon on screen |
| Frost Tower | Blizzard | Freezes every balloon for 3s |
| Ninja | Smoke Bomb | Knocks every balloon back and stuns it |
| Sniper | Cash Crate | +$300 |
| Wizard | Meteor | Huge blast on the strongest balloon |
| Spike Factory | Spike Carpet | Covers the track in spikes |
| Village | Rally Cry | All towers 2x faster for 8s |
| Super Tower | Overdrive | 3x faster for 8s |
| Coin Mine | Payday | +$600 |
| Pirate Ship | Broadside | 16 cannonballs all around |
| Submarine | Depth Charge | Explosions along the front of the balloons |
| Shark | Feeding Frenzy | Bites 3x faster for 8s |

### Towers

| Tower | Cost | What it does |
|---|---|---|
| Dart Tower | $170 | Throws darts; top upgrade rolls a bouncing Spike Ball |
| Tack Shooter | $280 | Fires 12 tacks in every direction |
| Boomerang | $325 | Curved throw that comes back (set Left/Right curve in its menu) |
| Bomb Tower | $500 | Explosions pop groups and lead (not black) |
| Glue Gunner | $200 | Fast-firing glue slows balloons; acid glue pops them |
| Frost Tower | $350 | Freezes balloons around it |
| Ninja | $400 | Fast throwing stars, sees camo |
| Sniper | $350 | Hits anything anywhere on the map |
| Wizard | $320 | Magic; Lightning Bolt and Dragon's Breath upgrades |
| Spike Factory | $650 | Drops spike piles on the track (only during rounds) |
| Village | $900 | Boosts towers in its circle: range, camo, speed, discounts, money |
| Super Tower | $2200 | A storm of darts |
| Coin Mine | $600 | Earns money every round |
| 🏴‍☠️ Pirate Ship | $450 | **Water only.** Fires 2 cannonballs at a time |
| 🚢 Submarine | $350 | **Water only.** Torpedoes; Sonar sees camo |
| 🦈 Shark | $400 | **Water only.** Bites nearby balloons hard |

All towers got a power boost from playtesting: they attack 15% faster, and darts,
tacks, boomerangs, stars, magic and the Super Tower pop one extra balloon per shot.

### Heroes

Each hero is its own character standing on the map (not a tower): an armored
**knight**, a **witch** with a wind staff, an **engineer** with a coil gun, **Cipher the
robot**, and **Nova the monk** who floats with glowing orbs around them.

Buy **one hero per game** from the end of the shop. Heroes have no upgrade
paths: they **level up by themselves, from 1 to 20**, by popping balloons and
as rounds go by. They unlock two abilities as they level up.

| Hero | Cost | Style | Abilities |
|---|---|---|---|
| ⚔️ Spark Knight | $550 | Lightning sword slashes a whole group | Thunder Strike (lv 5), Storm Blade (lv 14) |
| 🌪️ Wind Witch | $500 | Gusts pop balloons and push them back | Twister (lv 5), Hurricane (lv 14) |
| ⚙️ Gear Gunner | $500 | Rapid-fire bolt gun | Overclock (lv 5), Mega Mortar (lv 14) |
| 💻 Cipher | $600 | Hacker: earns cash every round, zaps strip camo | Crypto Boost (lv 4), Glitch Wave (lv 12) |
| 🔮 Nova | $650 | Mind power lifts balloons into the air, where they can't move and take damage | Mind Blast (lv 5), Gravity Well (lv 13) |

### Maps

| Map | Difficulty | What's special |
|---|---|---|
| Meadow | Easy | Long winding track |
| Lake Loop | Easy | A lake in the middle (for water towers) |
| Harbor | Medium | A big bay with coves near the track (great for water towers) |
| Crossroads | Medium | The track crosses itself |
| Spiral | Medium | Spirals into a hole in the middle |
| Rapids | Hard | Short track |
| Twin Lanes | Hard | Two tracks, balloons take turns (+$300 to start, 30% bigger round bonus) |
| Canyon | Hard | Staircase track, rocks block good spots |

### Balloons to watch out for

- **Lead** (gray): darts and tacks bounce off. Use bombs, fire, magic, or Full Metal snipers.
- **Black**: ignores explosions. **White**: can't be frozen. **Zebra**: both.
- **Purple**: fast, and immune to **magic and fire** (Wizard, Ring of Fire, Plasma).
- **Camo** (green spots): only towers with camo vision can target them
  (Ninja, Eagle Eye, Night Scope, Radar Reload, Wizard Sight, Cold Snap,
  Night Goggles, Sonar, Smell Blood, Crow's Nest, heroes, or a Village with Radar Hut).
- **Regrow** (green **+** badge): grows its layers back every 3 seconds. Finish them fast!
- **Fortified** (metal band): armored lead, ceramics and blimps that take twice the hits.
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
    "A": 0, "B": 1, "SELECT": 2, "START": 3, "L": 4, "R": 5, "ABILITY": 10,
    "UP": 6, "DOWN": 7, "LEFT": 8, "RIGHT": 9,
}
```

(The handheld has no separate ability button, so just press L and R together.
If your D-pad shows up as a "hat" or as axes, it already works without
changing anything.) To leave the button test, hold any button for 3 seconds.

Best rounds, settings and your saved game live in `~/.balloon_blitz.json`.
