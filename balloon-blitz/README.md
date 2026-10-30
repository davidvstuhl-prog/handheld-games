# Balloon Blitz 🎈

A balloon-popping tower defense game for the
homemade Raspberry Pi handheld. To play it on a computer, use the
emulator in [`../pc-tester`](../pc-tester).

## Share it with friends (no Python needed)

GitHub builds ready-to-play versions automatically every time the game changes:
**Windows** (`BalloonBlitz.exe`), **Mac** (`BalloonBlitz.app`) and **Linux**.
They're on the [**PC build** release](../../../releases/tag/pc-latest). Download the zip for your
computer, unzip it and double-click **BalloonBlitz**. `PLAYING.txt` inside explains the keys.

- Windows may say "Windows protected your PC": click **More info** then **Run anyway**
  (the game just isn't signed by a company).
- Mac: the first time, right-click the app, choose **Open**, then **Open** again.
- F11 switches fullscreen, and the window can be resized.


- **Continue**: carry on your saved game (shown when you have one)
- **Play**: pick a map (left/right flips through them, with a picture, difficulty badge
  and your best round), pick Easy / Normal / Hard, then **START!**
- **Towers & Heroes**: every tower and hero has its own tab. Flip through them with
  the **L / R** bumpers to see all 9 upgrades (3 paths) and every ability, or a hero's
  stats and abilities as it levels up
- **Settings**: auto-start, sound slider and the button test
- **How to Play** and **Quit**

## Mouse, keyboard or controller

Everything works with any of them:
- **Mouse:** click a tower in the shop, then click the map to build it. Click towers to
  upgrade, sell or retarget them, click the round ability buttons to use abilities, and
  use the top-right buttons for start/pause, speed and the menu. Right-click goes back,
  the wheel scrolls.
- **Keyboard:** arrows, Z = A, X = B, A/S = L/R, Enter = START, Tab = SELECT, D = abilities,
  F11 = fullscreen.
- **Controller / the handheld:** D-pad, A, B, L, R, START, SELECT (L + R together = abilities).

## Putting it on Steam (checklist)

- All tower, upgrade and balloon names are original (no names from other games).
- You need a **Steamworks** account and the **$100 Steam Direct fee** per game. Steamworks
  needs an adult to sign the agreements and handle payments and taxes.
- You'll need a store page: description, screenshots, a trailer and capsule art.
- The Windows build from the **PC build** release is what you upload. Steam achievements
  need the Steamworks SDK; the in-game achievements already work.
- Valve reviews the build and store page before release.

## Modifiers

Pick one on the Play screen under the difficulty for an extra challenge:

| Difficulty | Modifiers |
|---|---|
| Easy | **No Heroes**, **3/4 Cash** |
| Normal | **Few Upgrades** (max 4 per tower), **Tier 3 Max**, **Classic Six** (only Dart, Tack, Bomb, Frost, Marksman Nest, Coin Mine) |
| Hard | **Hardcore** (1 life), **Half Cash**, **Quarter Cash**, **No Cash Gain**, **No Abilities**, **Seven Towers** (max 7 at once), **Fortune Run** (start with $50,000, earn nothing, survive to round 50) |

Cash modifiers change all money you earn (pops, round bonuses, mines, abilities);
selling still gives your money back.

## Achievements

34 achievements, from **First Pop** to **Champion** (beat round 150), popping each
boss blimp, maxing a tower to tier 5, getting a hero to level 20, winning on all 8 maps,
and beating every modifier. A banner pops up when you unlock one, and **Achievements** on
the main menu shows them all. Sandbox games don't count.

## How to play

- Balloons follow the dirt track. Pop them before they reach the end.
  Each balloon that escapes costs lives (big balloons cost more, because
  everything inside them escapes too).
- **L / R** picks a tower or hero to build, **A** builds it at the cursor.
- **A** on a tower opens its menu: upgrades, abilities, targeting, selling.
  Next to the tower's name you'll see its **match stats**: total damage dealt and balloons popped.
- **START** sends the next round (and pauses during a round).
- **SELECT** changes the speed: **1x → 2x → 3x**.
- **L + R together** (or **D** on a keyboard) opens the **ability bar**.
- **B** opens the game menu (auto-start, sound slider, **Tower guide**, restart, quit).
  The Tower guide opens on the tower you're looking at; B takes you back to your paused game.
- Beat **round 30** to win, then keep going: the rounds go all the way to **150**.
  Beat round 150 (with the Overlord) to become **Champion**, then freeplay continues.
- **Easy** starts with $850 (instead of $650), slower balloons and cheaper towers.
- **Sandbox** (pick it as the difficulty) is for testing: endless money and lives, and
  **Sandbox tools** in the B menu let you send any balloon (camo / regrow / fortified, 1-50
  at a time), jump to any round 1-50, pop everything and recharge abilities. Sandbox
  games never overwrite your saved game or best rounds.

### Saving

The game **saves after every round**. Pick **Continue** on the title screen to
carry on where you left off (a game over clears the save).

### Upgrades: 3 paths, 5 tiers

Every tower has **three upgrade paths with 5 tiers each** (that's 15 upgrades per tower):

- **Top (orange)** and **bottom (blue)**: stronger attacks, range, camo and so on.
- **Middle (green)**: **tier 4 unlocks an ability** you fire yourself, and **tier 5
  powers that ability up** (more tacks, longer freezes, bigger paydays...).
- **One path can go all the way to tier 5**, and a second path can go up to tier 2.
- Tiers get expensive fast: each one costs about 2.5-4x the one before. Tier 4 is a
  mid-game goal and tier 5 is a late-game prize. Some examples:

| Tower | Top path tier 4 / 5 | Middle tier 4 (ability) / 5 | Bottom path tier 4 / 5 |
|---|---|---|---|
| Crossbow Post | Iron Boulder $3,200 / Doom Boulder $14,000 | Bolt Storm $2,800 / Eye of the Storm $12,000 | Bolt Gunner $2,600 / Bolt Hurricane $11,000 |
| Arcane Tower | Storm Caller $3,500 / Tempest Sage $14,000 | Meteor $4,000 / Starfall $15,000 | Inferno Wyrm $3,200 / Dragon King $13,000 |
| Reef Shark | Titan Bite $4,500 / Megalodon $16,000 | Feeding Frenzy $3,500 / Apex Predator $13,000 | Whirlpool $3,500 / Maelstrom $13,000 |
| Coin Mine | Mother Lode $4,500 / Dragon's Hoard $18,000 | Payday $4,500 / Jackpot $16,000 | Healing Spring $4,000 / Fountain of Life $15,000 |

See every upgrade in **Towers & Heroes** on the main menu (or **Tower guide** in the game menu).

Before you buy, the menu shows exactly what an upgrade changes, like
`> Pierce 3>5, Speed 1.2/s>1.5/s`.

### Abilities

Abilities unlock at **middle tier 4**. Press **L + R** to open the ability bar, pick one with
left/right, and press **A**. Each one then recharges (shown as a countdown on its button).
At middle **tier 5** every ability gets much stronger.

| Tower | Ability | What it does |
|---|---|---|
| Crossbow Post | Bolt Storm | 4x faster darts for 6s |
| Needle Dome | Needle Nova | 48 tacks in every direction |
| Rang Hut | Rang Barrage | 12 boomerangs at once |
| Mortar | Carpet Bomb | Explosions all along the front of the balloons |
| Goo Tank | Goo Rain | Glues every balloon on screen |
| Frost Spire | Blizzard | Freezes every balloon for 3s |
| Shadow Dojo | Smoke Bomb | Knocks every balloon back and stuns it |
| Marksman Nest | Cash Crate | +$300 |
| Arcane Tower | Meteor | Huge blast on the strongest balloon |
| Spike Press | Spike Carpet | Covers the track in spikes |
| Camp | Rally Cry | All towers 2x faster for 8s |
| Star Core | Overdrive | 3x faster for 8s |
| Coin Mine | Payday | +$600 |
| Galleon | Broadside | 16 cannonballs all around |
| Torpedo Sub | Depth Charge | Explosions along the front of the balloons |
| Reef Shark | Feeding Frenzy | Bites 3x faster for 8s |

### Towers

| Tower | Cost | What it does |
|---|---|---|
| Crossbow Post | $170 | Throws darts; top upgrade rolls a bouncing Spike Ball |
| Needle Dome | $280 | Fires 12 tacks in every direction |
| Rang Hut | $325 | Curved throw that comes back (set Left/Right curve in its menu) |
| Mortar | $500 | Explosions pop groups and iron (not black) |
| Goo Tank | $200 | Fast-firing glue slows balloons; acid glue pops them |
| Frost Spire | $350 | Freezes balloons around it |
| Shadow Dojo | $400 | Fast throwing stars, sees camo |
| Marksman Nest | $350 | Hits anything anywhere on the map |
| Arcane Tower | $320 | Magic; Chain Spark and Fire Wyrm upgrades |
| Spike Press | $650 | Drops spike piles on the track (only during rounds) |
| Camp | $900 | Boosts towers in its circle: range, camo, speed, discounts, money |
| Star Core | $2200 | A storm of darts |
| Coin Mine | $600 | Earns money every round |
| 🏴‍☠️ Galleon | $450 | **Water only.** Fires 2 cannonballs at a time |
| 🚢 Torpedo Sub | $350 | **Water only.** Torpedoes; Sonar sees camo |
| 🦈 Reef Shark | $400 | **Water only.** Bites nearby balloons hard |

All towers got a power boost from playtesting: they attack 15% faster, and darts,
tacks, boomerangs, stars, magic and the Star Core pop one extra balloon per shot.

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

- **Iron** (gray): darts and tacks bounce off. Use bombs, fire, magic, or Steel Core snipers.
- **Black**: ignores explosions. **White**: can't be frozen. **Striped**: both.
- **Violet**: fast, and immune to **magic and fire** (Arcane Tower, Flame Halo, Plasma Heart).
- **Camo** (green spots): only towers with camo vision can target them
  (Shadow Dojo, Hawk Lens, Dark Lens, Radar Reload, True Sight, Snap Frost,
  Night Lens, Sonar, Smell Blood, Lookout Mast, heroes, or a Camp with Lookout Post).
- **Healing** (green **+** badge): grows its layers back every 3 seconds. Finish them fast!
- **Armored** (metal band): armored iron, clay balloons and blimps that take twice the hits.
- **Clay**: takes 10 hits.
- **Blimp** (round 25) and **Titan** (round 30): giant bosses with health bars.
- **Phantom** (from round 45): a fast, dark blimp that is **always camo** and immune to
  darts/tacks **and** explosions. Use magic, fire, normal-damage upgrades or bites.
- **Colossus** (from round 50): a huge armored blimp (2,000 health) that drops 4 Titans.
- **Overlord** (rounds 100, 125 and 150): the final boss, 15,000 health. It **can't be
  frozen, slowed, glued, pushed back or lifted**, and it drops 2 Colossi and 3 Phantoms.
  You'll need a defense full of tier 5 towers to beat round 150.

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
