#!/usr/bin/env python3
"""
Balloon Blitz - a balloon-popping tower defense game for a homemade
Raspberry Pi Zero 2 W handheld (480x640 portrait screen, 10 buttons).

Run on a computer for testing:   python3 balloon_blitz.py
Run on the handheld:             python3 balloon_blitz.py --fullscreen
Find out your button numbers:    python3 balloon_blitz.py --buttons
"""
import argparse
import json
import math
import os
import random
from array import array

import pygame

# =====================================================================
# Settings
# =====================================================================
VERSION = "v4.2 (150 rounds, 16 towers, 5 heroes, 8 maps)"
SCREEN_W, SCREEN_H = 480, 640
HUD_H = 40                      # top bar (lives, money, round)
MAP_Y, MAP_H = HUD_H, 480       # the play field is a 480x480 square
PANEL_Y = MAP_Y + MAP_H         # bottom panel (shop / hints)
PANEL_H = SCREEN_H - PANEL_Y
FPS = 60
WIN_ROUND = 30                  # beat this round to win (then keep going)
FINAL_ROUND = 150               # beat this one to be Champion (then freeplay)
START_MONEY = 650
BALLOON_SPEED = 65.0            # pixels per second for a red balloon
PATH_W = 40                     # width of the balloon track
TOWER_R = 18                    # tower radius (for placement)
CELL = 64                       # size of the collision grid cells
SELL_RATE = 0.7                 # selling gives back 70% of what you spent
AUTO_START_DELAY = 2.0          # seconds between rounds when auto-start is on
SAVE_FILE = os.path.expanduser("~/.balloon_blitz.json")

# Gamepad button numbers. The Raspberry Pi Pico in the handheld shows up as
# a USB gamepad; change these numbers to match yours (use --buttons to see
# which number each button sends). The D-pad also works as a hat or as the
# first two axes, whichever your gamepad uses.
PAD_BUTTONS = {
    "A": 0, "B": 1, "SELECT": 2, "START": 3, "L": 4, "R": 5, "ABILITY": 10,
    "UP": 6, "DOWN": 7, "LEFT": 8, "RIGHT": 9,
}
AXIS_DEADZONE = 0.5

# Keyboard controls for testing on a computer.
KEYMAP = {
    "UP": [pygame.K_UP], "DOWN": [pygame.K_DOWN],
    "LEFT": [pygame.K_LEFT], "RIGHT": [pygame.K_RIGHT],
    "A": [pygame.K_z, pygame.K_SPACE], "B": [pygame.K_x, pygame.K_BACKSPACE],
    "L": [pygame.K_a, pygame.K_q], "R": [pygame.K_s, pygame.K_e],
    "START": [pygame.K_RETURN], "SELECT": [pygame.K_TAB, pygame.K_RSHIFT],
    "ABILITY": [pygame.K_d],
}
REPEAT_DELAY, REPEAT_RATE = 0.35, 0.09   # menu auto-repeat when holding
SHOP_SLOTS = 7                  # towers shown at once in the shop bar

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (150, 150, 150)
DARK = (25, 28, 36)
YELLOW = (255, 220, 60)
GREEN = (90, 220, 90)
RED = (235, 70, 70)
GRASS = (88, 166, 72)
GRASS_DARK = (70, 140, 58)
PATH_COL = (214, 186, 130)
PATH_EDGE = (160, 125, 80)
HUD_BG = (30, 34, 48)
PANEL_BG = (38, 42, 58)
PANEL_HI = (70, 90, 140)

# =====================================================================
# Balloons
# =====================================================================
# speed is relative to a red balloon. children = balloons released when
# this one pops. immune = damage types that can't hurt it:
#   sharp   - darts, tacks, sniper (blocked by lead)
#   explode - bombs (blocked by black and zebra)
#   cold    - freezing (blocked by white and zebra)
#   magic   - wizard magic, fire and plasma (blocked by purple)
#   normal  - pops anything
BALLOON_TYPES = {
    "red":     dict(color=(225, 45, 45),   r=12, speed=1.0, hp=1, children=[]),
    "blue":    dict(color=(45, 125, 235),  r=12, speed=1.4, hp=1, children=["red"]),
    "green":   dict(color=(60, 195, 60),   r=13, speed=1.8, hp=1, children=["blue"]),
    "yellow":  dict(color=(250, 220, 40),  r=13, speed=2.3, hp=1, children=["green"]),
    "pink":    dict(color=(250, 125, 185), r=13, speed=2.6, hp=1, children=["yellow"]),
    "black":   dict(color=(28, 28, 32),    r=10, speed=1.8, hp=1, children=["pink", "pink"],
                    immune={"explode"}),
    "white":   dict(color=(245, 245, 245), r=10, speed=2.0, hp=1, children=["pink", "pink"],
                    immune={"cold"}),
    "purple":  dict(color=(150, 60, 210),  r=13, speed=3.0, hp=1, children=["pink", "pink"],
                    immune={"magic"}),
    "zebra":   dict(color=(245, 245, 245), r=13, speed=1.8, hp=1, children=["black", "white"],
                    immune={"explode", "cold"}),
    "lead":    dict(color=(135, 140, 150), r=13, speed=1.0, hp=1, children=["black", "black"],
                    immune={"sharp"}),
    "rainbow": dict(color=(200, 80, 200),  r=14, speed=1.9, hp=1, children=["zebra", "zebra"]),
    "ceramic": dict(color=(175, 105, 45),  r=15, speed=2.0, hp=10, children=["rainbow", "rainbow"]),
    "blimp":   dict(color=(45, 85, 175),   r=30, w=78, h=40, speed=1.0, hp=200,
                    children=["ceramic"] * 4, blimp=True),
    "titan":   dict(color=(195, 45, 65),   r=40, w=104, h=54, speed=0.6, hp=500,
                    children=["blimp"] * 3, blimp=True),
    # fast, always camo, shrugs off darts/tacks and explosions
    "phantom": dict(color=(60, 62, 72),    r=26, w=76, h=30, speed=2.75, hp=300,
                    children=["ceramic"] * 6, blimp=True, always_camo=True, immune={"sharp", "explode"}),
    # a huge armored blimp
    "colossus": dict(color=(45, 125, 65),  r=52, w=134, h=68, speed=0.45, hp=2000,
                     children=["titan"] * 4, blimp=True),
    # the final boss: can't be frozen, slowed, glued, pushed or lifted
    "overlord": dict(color=(105, 35, 125), r=62, w=164, h=82, speed=0.3, hp=15000,
                     children=["colossus", "colossus", "phantom", "phantom", "phantom"], blimp=True,
                     unstoppable=True),
}
BALLOON_ORDER = list(BALLOON_TYPES)   # used for "Strong" targeting
for _info in BALLOON_TYPES.values():
    _info.setdefault("immune", set())

# Sandbox tools: balloon kinds you can send, and how many at once.
SANDBOX_FLAGS = [("Normal", ""), ("Camo", "c"), ("Regrow", "r"), ("Fortified", "f"),
                 ("Camo + Regrow", "cr"), ("Camo + Fortified", "cf")]
SANDBOX_AMOUNTS = [1, 5, 10, 25, 50]

# Regrow balloons grow back one layer at a time along this chain.
REGROW_UP = {"red": "blue", "blue": "green", "green": "yellow", "yellow": "pink"}
REGROW_TIME = 3.0
FORTIFIABLE = ("lead", "ceramic", "blimp", "titan", "phantom", "colossus", "overlord")   # armored versions take 2x hits

# "Red balloon equivalent": how many lives a balloon costs if it gets
# through, counting everything inside it.
RBE = {}
def _rbe(name):
    if name not in RBE:
        info = BALLOON_TYPES[name]
        RBE[name] = info["hp"] + sum(_rbe(c) for c in info["children"])
    return RBE[name]
for _n in BALLOON_TYPES:
    _rbe(_n)

# =====================================================================
# Towers
# =====================================================================
# Each upgrade is (name, cost, description, effects). Effects change the
# tower's stats: ("+", n) adds, ("*", n) multiplies, ("=", v) sets.
# Upgrade rule: each path goes up to 3, but only ONE path can reach 3.
TOWER_TYPES = [
    dict(key="dart", name="Dart Tower", cost=170,
         desc="Throws darts at one balloon",
         base=dict(range=130, rate=0.8, dmg=1, pierce=2, speed=540,
                   dtype="sharp", count=1, spread=0.0),
         paths=[
             [("Sharp Darts", 120, "Darts pop 1 more balloon", {"pierce": ("+", 1)}),
              ("Triple Shot", 340, "Throws 3 darts at once",
               {"count": ("=", 3), "spread": ("=", 0.22)}),
              ("Spike Ball", 1100, "Rolls a huge spiked ball, bounces once",
               {"spikeball": ("=", True), "count": ("=", 1), "rate": ("*", 1.5)})],
             [("Long Range", 75, "+30 range", {"range": ("+", 30)}),
              ("Eagle Eye", 135, "Can see camo balloons",
               {"camo": ("=", True), "range": ("+", 15)}),
              ("Rapid Fire", 425, "Throws twice as fast", {"rate": ("*", 0.5)})],
         ]),
    dict(key="tack", name="Tack Shooter", cost=280,
         desc="Fires tacks in every direction",
         base=dict(range=95, rate=0.9, dmg=1, pierce=1, speed=380,
                   dtype="sharp", count=12),
         paths=[
             [("Quick Spin", 150, "Shoots 20% faster", {"rate": ("*", 0.8)}),
              ("Faster Spin", 260, "Shoots 25% faster", {"rate": ("*", 0.75)}),
              ("Blade Ring", 750, "8 more blades, each pops 3",
               {"count": ("+", 8), "pierce": ("+", 2)})],
             [("Long Reach", 100, "+15 range", {"range": ("+", 15)}),
              ("More Tacks", 250, "+4 tacks per shot", {"count": ("+", 4)}),
              ("Ring of Fire", 1100, "Fire: 2 damage, pops lead",
               {"dtype": ("=", "magic"), "dmg": ("+", 1)})],
         ]),
    dict(key="boom", name="Boomerang", cost=325,
         desc="Curved throw that comes back",
         base=dict(range=120, rate=1.15, dmg=1, pierce=5, speed=360,
                   dtype="sharp", count=1, knock=0),
         paths=[
             [("Wide Arc", 250, "Boomerangs pop 4 more", {"pierce": ("+", 4)}),
              ("Hot Rang", 450, "Red-hot: pops lead", {"dtype": ("=", "normal")}),
              ("Blade Storm", 1500, "+10 pierce, +2 damage",
               {"pierce": ("+", 10), "dmg": ("+", 2)})],
             [("Quick Throw", 200, "Throws 25% faster", {"rate": ("*", 0.75)}),
              ("Double Throw", 500, "Throws 2 boomerangs", {"count": ("=", 2)}),
              ("Push Back", 1300, "Hits knock balloons back",
               {"knock": ("=", 18), "rate": ("*", 0.8)})],
         ]),
    dict(key="bomb", name="Bomb Tower", cost=500,
         desc="Explodes groups. Pops lead",
         base=dict(range=145, rate=1.35, dmg=1, pierce=18, speed=400,
                   dtype="explode", blast=50, cluster=0, blimp_mult=1),
         paths=[
             [("Bigger Bombs", 250, "Bigger explosions", {"blast": ("+", 20)}),
              ("Heavy Bombs", 450, "+1 damage", {"dmg": ("+", 1)}),
              ("Blimp Buster", 1100, "+2 damage, 3x vs blimps",
               {"dmg": ("+", 2), "blimp_mult": ("=", 3)})],
             [("Long Fuse", 200, "+25 range", {"range": ("+", 25)}),
              ("Radar Reload", 350, "25% faster, sees camo",
               {"rate": ("*", 0.75), "camo": ("=", True)}),
              ("Cluster Bombs", 900, "Blasts throw 6 mini bombs", {"cluster": ("=", 6)})],
         ]),
    dict(key="glue", name="Glue Gunner", cost=200,
         desc="Glue slows balloons down",
         base=dict(range=115, rate=0.7, pierce=1, speed=380, slow=0.5, glue_time=11,
                   acid=0, splash=0, glue_blimp=False, count=1, spread=0.0),
         paths=[
             [("Sticky Glue", 150, "Slows more, lasts longer",
               {"slow": ("=", 0.65), "glue_time": ("+", 4)}),
              ("Acid Glue", 340, "Glue pops a layer every 1.5s", {"acid": ("=", 1.5)}),
              ("Melting Goo", 1650, "Fast acid, works on blimps",
               {"acid": ("=", 0.4), "glue_blimp": ("=", True)})],
             [("Glue Spray", 165, "Glue hits 2 more balloons", {"pierce": ("+", 2)}),
              ("Fast Squirt", 300, "Shoots 40% faster", {"rate": ("*", 0.6)}),
              ("Glue Storm", 1200, "Glue splashes a whole area",
               {"splash": ("=", 60), "glue_blimp": ("=", True)})],
         ]),
    dict(key="frost", name="Frost Tower", cost=350,
         desc="Freezes nearby balloons",
         base=dict(range=80, rate=2.2, dmg=0, freeze=1.2, slow_after=0,
                   freeze_white=False),
         paths=[
             [("Deep Freeze", 150, "Freezes for longer", {"freeze": ("+", 0.6)}),
              ("Shatter", 320, "Freezing also pops 1 layer", {"dmg": ("+", 1)}),
              ("Arctic Wind", 800, "+40 range, freezes longer",
               {"range": ("+", 40), "freeze": ("+", 0.4)})],
             [("Wide Chill", 120, "+20 range", {"range": ("+", 20)}),
              ("Permafrost", 250, "Slows balloons after thaw", {"slow_after": ("=", 3.0)}),
              ("Cold Snap", 500, "Freezes white+zebra, sees camo",
               {"freeze_white": ("=", True), "camo": ("=", True)})],
         ]),
    dict(key="ninja", name="Ninja", cost=400,
         desc="Fast stars. Sees camo",
         base=dict(range=125, rate=0.55, dmg=1, pierce=2, speed=620, dtype="sharp",
                   camo=True, count=1, spread=0.0, homing=False, stun=0),
         paths=[
             [("Keen Stars", 300, "Stars pop 2 more", {"pierce": ("+", 2)}),
              ("Homing Stars", 500, "Stars chase balloons", {"homing": ("=", True)}),
              ("Star Storm", 1800, "Throws 4 stars, faster",
               {"count": ("=", 4), "spread": ("=", 0.18), "rate": ("*", 0.7)})],
             [("Quick Hands", 350, "Throws 25% faster", {"rate": ("*", 0.75)}),
              ("Stun Bomb", 600, "Every 4th throw stuns an area", {"stun": ("=", 1.0)}),
              ("Shadow Master", 2600, "+3 damage, throws faster",
               {"dmg": ("+", 3), "rate": ("*", 0.7)})],
         ]),
    dict(key="sniper", name="Sniper", cost=350,
         desc="Hits anything on the map",
         base=dict(range=9999, rate=1.6, dmg=2, dtype="sharp", blimp_mult=1),
         paths=[
             [("Full Metal", 350, "4 damage, pops lead",
               {"dmg": ("=", 4), "dtype": ("=", "normal")}),
              ("Large Calibre", 1000, "7 damage", {"dmg": ("=", 7)}),
              ("Deadeye", 2500, "18 damage, 4x vs blimps",
               {"dmg": ("=", 18), "blimp_mult": ("=", 4)})],
             [("Night Scope", 300, "Can see camo balloons", {"camo": ("=", True)}),
              ("Fast Bolt", 400, "Shoots 40% faster", {"rate": ("*", 0.6)}),
              ("Semi-Auto", 2800, "Shoots 3x faster", {"rate": ("*", 0.33)})],
         ]),
    dict(key="wizard", name="Wizard", cost=320,
         desc="Magic pops every balloon type",
         base=dict(range=120, rate=1.1, dmg=1, pierce=3, speed=330,
                   dtype="magic", homing=False, chain=0, breath=False),
         paths=[
             [("Arcane Blast", 240, "Magic does 1 more damage", {"dmg": ("+", 1)}),
              ("Arcane Mastery", 560, "Casts faster, pops 2 more",
               {"rate": ("*", 0.6), "pierce": ("+", 2)}),
              ("Lightning Bolt", 1280, "Lightning jumps to 8 balloons", {"chain": ("=", 8)})],
             [("Guided Magic", 200, "Magic bolts chase balloons", {"homing": ("=", True)}),
              ("Wizard Sight", 240, "Sees camo, +20 range",
               {"camo": ("=", True), "range": ("+", 20)}),
              ("Dragon's Breath", 1040, "Adds a flamethrower", {"breath": ("=", True)})],
         ]),
    dict(key="spike", name="Spike Factory", cost=650,
         desc="Drops spikes on the track",
         base=dict(range=95, rate=2.0, dmg=1, pierce=5, dtype="sharp", life=25, mines=False),
         paths=[
             [("Bigger Piles", 300, "Piles pop 4 more", {"pierce": ("+", 4)}),
              ("Hot Spikes", 550, "+1 damage, pops lead",
               {"dmg": ("+", 1), "dtype": ("=", "normal")}),
              ("Spike Mines", 1800, "Used-up piles explode", {"mines": ("=", True)})],
             [("Long-lasting", 250, "Spikes last twice as long", {"life": ("*", 2)}),
              ("Faster Making", 700, "Makes spikes 40% faster", {"rate": ("*", 0.6)}),
              ("Spike Storm", 2500, "Makes spikes 3x faster", {"rate": ("*", 0.35)})],
         ]),
    dict(key="village", name="Village", cost=900,
         desc="Boosts towers in its circle",
         base=dict(range=115, boost=0.1, radar=False, drums=0, rune=False, discount=0, income=0),
         paths=[
             [("Radar Hut", 400, "Towers in circle see camo", {"radar": ("=", True)}),
              ("Drum Circle", 900, "Towers in circle 15% faster", {"drums": ("=", 0.15)}),
              ("Ancient Rune", 2200, "Towers in circle pop lead+black", {"rune": ("=", True)})],
             [("Watchtower", 250, "Bigger circle, +20% range",
               {"range": ("+", 30), "boost": ("=", 0.2)}),
              ("Trade Post", 500, "15% off in the circle", {"discount": ("=", 0.15)}),
              ("Gold Market", 2500, "+$300 every round", {"income": ("=", 300)})],
         ]),
    dict(key="super", name="Super Tower", cost=2200,
         desc="A storm of darts. Pricey!",
         base=dict(range=150, rate=0.08, dmg=1, pierce=1, speed=700, dtype="sharp",
                   count=1, spread=0.0, blimp_mult=1),
         paths=[
             [("Laser Vision", 1500, "+1 pierce, 15% faster",
               {"pierce": ("+", 1), "rate": ("*", 0.85)}),
              ("Plasma Core", 3500, "+1 damage, pops lead",
               {"dmg": ("+", 1), "dtype": ("=", "magic")}),
              ("Solar Flare", 11000, "3 beams, +2 damage, +3 pierce",
               {"count": ("=", 3), "spread": ("=", 0.15), "dmg": ("+", 2), "pierce": ("+", 3)})],
             [("Night Goggles", 600, "Sees camo balloons", {"camo": ("=", True)}),
              ("Twin Blasters", 3000, "Shoots 2 at once",
               {"count": ("=", 2), "spread": ("=", 0.12)}),
              ("Blimp Wrecker", 6000, "4x damage to blimps", {"blimp_mult": ("=", 4)})],
         ]),
    dict(key="mine", name="Coin Mine", cost=600,
         desc="Earns money every round",
         base=dict(range=0, income=60, lives=0, mult=1.0),
         paths=[
             [("More Coins", 300, "+40 money per round", {"income": ("+", 40)}),
              ("Gold Vein", 650, "+80 money per round", {"income": ("+", 80)}),
              ("Treasure Pit", 1600, "+220 money per round", {"income": ("+", 220)})],
             [("First Aid", 400, "+1 life per round", {"lives": ("+", 1)}),
              ("Hospital", 700, "+3 lives per round", {"lives": ("+", 3)}),
              ("Gold Rush", 1500, "This mine pays 50% more", {"mult": ("=", 1.5)})],
         ]),
]
# Water towers: can only be built on water.
TOWER_TYPES += [
    dict(key="pirate", name="Pirate Ship", cost=450, water=True,
         desc="Cannonballs, 2 at a time (water)",
         base=dict(range=125, rate=1.0, dmg=1, pierce=4, speed=420, dtype="sharp",
                   count=2, spread=0.14),
         paths=[
             [("Grapeshot", 220, "Cannonballs pop 2 more", {"pierce": ("+", 2)}),
              ("Double Deck", 450, "4 cannonballs per shot", {"count": ("=", 4), "spread": ("=", 0.12)}),
              ("Iron Balls", 1300, "+2 damage, pops lead", {"dmg": ("+", 2), "dtype": ("=", "normal")})],
             [("Crow's Nest", 200, "+25 range, sees camo", {"range": ("+", 25), "camo": ("=", True)}),
              ("Cargo Hold", 500, "+$60 every round", {"income": ("=", 60)}),
              ("Treasure Fleet", 1500, "+$260 every round", {"income": ("=", 260)})],
         ]),
    dict(key="sub", name="Submarine", cost=350, water=True,
         desc="Fires torpedoes (water)",
         base=dict(range=135, rate=0.9, dmg=1, pierce=2, speed=460, dtype="sharp",
                   count=1, spread=0.0, homing=False),
         paths=[
             [("Heavy Torpedo", 250, "+1 damage, pops lead", {"dmg": ("+", 1), "dtype": ("=", "normal")}),
              ("Homing Torpedo", 450, "Torpedoes chase balloons", {"homing": ("=", True)}),
              ("Torpedo Spread", 1400, "3 torpedoes, +2 pierce",
               {"count": ("=", 3), "spread": ("=", 0.2), "pierce": ("+", 2)})],
             [("Sonar", 250, "Sees camo balloons", {"camo": ("=", True)}),
              ("Periscope", 300, "+30 range", {"range": ("+", 30)}),
              ("Blimp Hunter", 1500, "4x damage to blimps", {"blimp_mult": ("=", 4)})],
         ]),
    dict(key="shark", name="Shark", cost=400, water=True,
         desc="Bites nearby balloons hard (water)",
         base=dict(range=90, rate=0.9, dmg=2, pierce=3, dtype="sharp", camo=False, knock=0),
         paths=[
             [("Sharp Teeth", 250, "+1 damage", {"dmg": ("+", 1)}),
              ("Mega Bite", 500, "Bites 3 more balloons", {"pierce": ("+", 3)}),
              ("Great Bite", 1500, "+3 damage, 3x vs blimps", {"dmg": ("+", 3), "blimp_mult": ("=", 3)})],
             [("Wide Circle", 200, "+20 range", {"range": ("+", 20)}),
              ("Smell Blood", 350, "Sees camo balloons", {"camo": ("=", True)}),
              ("Riptide", 1100, "Bites drag balloons back", {"knock": ("=", 30)})],
         ]),
]
WATER_KEYS = ("pirate", "sub", "shark")

# The middle upgrade path of every tower. Its level 3 unlocks an ability
# you fire yourself (L+R together, D on a keyboard, or the tower's menu).
MIDDLE_PATHS = {
    "dart": [("Quick Draw", 150, "Throws 15% faster", {"rate": ("*", 0.85)}),
             ("Keen Eye", 250, "+20 range, pops 1 more", {"range": ("+", 20), "pierce": ("+", 1)}),
             ("Dart Storm", 900, "Ability: 4x faster for 6s", {"ability": ("=", "dart_storm")})],
    "tack": [("Hot Coils", 180, "Shoots 15% faster", {"rate": ("*", 0.85)}),
             ("Sharper Tacks", 300, "Tacks pop 1 more", {"pierce": ("+", 1)}),
             ("Tack Nova", 1000, "Ability: 48-tack blast", {"ability": ("=", "tack_nova")})],
    "boom": [("Light Rangs", 180, "Throws 15% faster", {"rate": ("*", 0.85)}),
             ("Spin Edge", 350, "Boomerangs pop 3 more", {"pierce": ("+", 3)}),
             ("Rang Barrage", 1100, "Ability: 12 boomerangs", {"ability": ("=", "rang_barrage")})],
    "bomb": [("Short Fuse", 220, "Shoots 15% faster", {"rate": ("*", 0.85)}),
             ("Shrapnel", 380, "Bigger blasts", {"blast": ("+", 15)}),
             ("Carpet Bomb", 1300, "Ability: bomb the front line", {"ability": ("=", "carpet_bomb")})],
    "glue": [("Thick Glue", 150, "Glue lasts longer", {"glue_time": ("+", 4)}),
             ("Wide Nozzle", 280, "+20 range", {"range": ("+", 20)}),
             ("Glue Rain", 900, "Ability: glue everything", {"ability": ("=", "glue_rain")})],
    "frost": [("Cold Core", 160, "Pulses 15% faster", {"rate": ("*", 0.85)}),
              ("Big Chill", 320, "+15 range", {"range": ("+", 15)}),
              ("Blizzard", 1100, "Ability: freeze everything", {"ability": ("=", "blizzard")})],
    "ninja": [("Swift Feet", 250, "Throws 15% faster", {"rate": ("*", 0.85)}),
              ("Sharp Edges", 400, "Stars pop 2 more", {"pierce": ("+", 2)}),
              ("Smoke Bomb", 1200, "Ability: knock all back", {"ability": ("=", "smoke_bomb")})],
    "sniper": [("Steady Aim", 300, "Shoots 15% faster", {"rate": ("*", 0.85)}),
               ("Hollow Point", 450, "+1 damage", {"dmg": ("+", 1)}),
               ("Cash Crate", 1400, "Ability: drops $300", {"ability": ("=", "cash_crate")})],
    "wizard": [("Focus Crystal", 240, "+15 range", {"range": ("+", 15)}),
               ("Mana Surge", 450, "Casts 20% faster", {"rate": ("*", 0.8)}),
               ("Meteor", 1400, "Ability: huge blast", {"ability": ("=", "meteor")})],
    "spike": [("Sturdy Spikes", 250, "Spikes last 50% longer", {"life": ("*", 1.5)}),
              ("Quick Press", 450, "Makes spikes 20% faster", {"rate": ("*", 0.8)}),
              ("Spike Carpet", 1300, "Ability: spike the track", {"ability": ("=", "spike_carpet")})],
    "village": [("Big Square", 300, "Bigger circle", {"range": ("+", 25)}),
                ("Training Yard", 600, "+10% more range boost", {"boost": ("+", 0.1)}),
                ("Rally Cry", 2000, "Ability: all towers 2x speed", {"ability": ("=", "rally_cry")})],
    "super": [("Hyper Core", 1800, "Shoots 15% faster", {"rate": ("*", 0.85)}),
              ("Laser Lens", 3000, "+2 pierce", {"pierce": ("+", 2)}),
              ("Overdrive", 8000, "Ability: 3x speed for 8s", {"ability": ("=", "overdrive")})],
    "pirate": [("Quick Crew", 200, "Fires 15% faster", {"rate": ("*", 0.85)}),
               ("Big Guns", 400, "Faster balls, pop 1 more", {"speed": ("+", 120), "pierce": ("+", 1)}),
               ("Broadside", 1200, "Ability: cannons all around", {"ability": ("=", "broadside")})],
    "sub": [("Quick Tubes", 200, "Fires 15% faster", {"rate": ("*", 0.85)}),
            ("Twin Tubes", 450, "2 torpedoes per shot", {"count": ("=", 2), "spread": ("=", 0.15)}),
            ("Depth Charge", 1300, "Ability: blasts the front", {"ability": ("=", "depth_charge")})],
    "shark": [("Fast Fins", 250, "Bites 15% faster", {"rate": ("*", 0.85)}),
              ("Hungry", 450, "Bites pop lead", {"dtype": ("=", "normal")}),
              ("Feeding Frenzy", 1300, "Ability: 3x bites for 8s", {"ability": ("=", "feeding_frenzy")})],
    "mine": [("Bigger Carts", 350, "+30 money per round", {"income": ("+", 30)}),
             ("Coin Polish", 600, "+60 money per round", {"income": ("+", 60)}),
             ("Payday", 1800, "Ability: instant $600", {"ability": ("=", "payday")})],
}
for _tt in TOWER_TYPES:
    _tt["paths"].insert(1, MIDDLE_PATHS[_tt["key"]])

# ---------------------------------------------------------------------
# Tiers 4 and 5. Each tier costs about 2.5-4x the one before and is a
# big jump in power. Only one path per tower can go past level 2.
# ---------------------------------------------------------------------
# Middle path, tiers 3-5: tier 3 is a stat boost, tier 4 UNLOCKS the
# ability, tier 5 powers the ability up ("ab_power").
MIDDLE_TOP = {
    "dart": [("Piercing Darts", 900, "+2 pierce, 15% faster", {"pierce": ("+", 2), "rate": ("*", 0.85)}),
             ("Dart Storm", 2800, "Ability: 4x faster for 6s", {"ability": ("=", "dart_storm"), "rate": ("*", 0.8)}),
             ("Eye of the Storm", 12000, "Huge Dart Storm, 3 darts",
              {"ab_power": ("+", 1), "dmg": ("+", 2), "count": ("=", 3), "rate": ("*", 0.6)})],
    "tack": [("Tack Overload", 1000, "+4 tacks, 15% faster", {"count": ("+", 4), "rate": ("*", 0.85)}),
             ("Tack Nova", 3000, "Ability: 48-tack blast", {"ability": ("=", "tack_nova"), "pierce": ("+", 2)}),
             ("Supernova", 12000, "Massive Tack Nova, +2 dmg", {"ab_power": ("+", 1), "dmg": ("+", 2), "rate": ("*", 0.6)})],
    "boom": [("Return Spin", 1100, "Pops 4 more, 15% faster", {"pierce": ("+", 4), "rate": ("*", 0.85)}),
             ("Rang Barrage", 3000, "Ability: 12 boomerangs", {"ability": ("=", "rang_barrage"), "rate": ("*", 0.85)}),
             ("Boomerang Storm", 12000, "Huge Rang Barrage",
              {"ab_power": ("+", 1), "rate": ("*", 0.5), "pierce": ("+", 8)})],
    "bomb": [("Heavy Shrapnel", 1300, "Bigger blasts, +1 damage", {"blast": ("+", 15), "dmg": ("+", 1)}),
             ("Carpet Bomb", 3500, "Ability: bomb the front line", {"ability": ("=", "carpet_bomb"), "rate": ("*", 0.85)}),
             ("Firestorm Fleet", 14000, "Huge Carpet Bomb, +3 dmg",
              {"ab_power": ("+", 1), "dmg": ("+", 3), "blast": ("+", 20)})],
    "glue": [("Quick Glue", 900, "Shoots 30% faster", {"rate": ("*", 0.7)}),
             ("Glue Rain", 2800, "Ability: glue everything", {"ability": ("=", "glue_rain")}),
             ("Glue Flood", 10000, "Glue Rain melts balloons",
              {"ab_power": ("+", 1), "acid": ("=", 0.5), "pierce": ("+", 3)})],
    "frost": [("Deep Cold", 1100, "Freezes longer, +15 range", {"freeze": ("+", 0.5), "range": ("+", 15)}),
              ("Blizzard", 3000, "Ability: freeze everything", {"ability": ("=", "blizzard")}),
              ("Ice Age", 11000, "Blizzard freezes and hurts", {"ab_power": ("+", 1), "dmg": ("+", 3), "rate": ("*", 0.7)})],
    "ninja": [("Blade Dance", 1200, "Throws 25% faster", {"rate": ("*", 0.75)}),
              ("Smoke Bomb", 3200, "Ability: knock all back", {"ability": ("=", "smoke_bomb")}),
              ("Phantom Clan", 12000, "Huge Smoke Bomb, 3 stars",
               {"ab_power": ("+", 1), "count": ("=", 3), "dmg": ("+", 2)})],
    "sniper": [("Marksman", 1400, "+2 damage, 15% faster", {"dmg": ("+", 2), "rate": ("*", 0.85)}),
               ("Cash Crate", 3500, "Ability: drops $300", {"ability": ("=", "cash_crate")}),
               ("Gold Convoy", 14000, "Bigger crates, +$400/round", {"ab_power": ("+", 1), "income": ("=", 400)})],
    "wizard": [("Arcane Focus", 1400, "+1 damage, pops 2 more", {"dmg": ("+", 1), "pierce": ("+", 2)}),
               ("Meteor", 4000, "Ability: huge blast", {"ability": ("=", "meteor")}),
               ("Starfall", 15000, "Many huge meteors", {"ab_power": ("+", 1), "pierce": ("+", 5), "rate": ("*", 0.6)})],
    "spike": [("Spiky Steel", 1300, "Piles pop 4 more", {"pierce": ("+", 4)}),
              ("Spike Carpet", 3500, "Ability: spike the track", {"ability": ("=", "spike_carpet")}),
              ("Iron Fortress", 14000, "Huge Spike Carpet, +3 dmg", {"ab_power": ("+", 1), "dmg": ("+", 3)})],
    "village": [("Grand Square", 2000, "+20 range, more boost", {"range": ("+", 20), "boost": ("+", 0.05)}),
                ("Rally Cry", 5000, "Ability: all towers 2x speed", {"ability": ("=", "rally_cry")}),
                ("Legend's Banner", 18000, "Huge Rally Cry", {"ab_power": ("+", 1), "drums": ("+", 0.1)})],
    "super": [("Hyper Lens", 8000, "+1 damage, 15% faster", {"dmg": ("+", 1), "rate": ("*", 0.85)}),
              ("Overdrive", 25000, "Ability: 3x speed for 8s", {"ability": ("=", "overdrive")}),
              ("Infinity Drive", 70000, "Huge Overdrive, +5 damage", {"ab_power": ("+", 1), "dmg": ("+", 5)})],
    "mine": [("Gem Carts", 1800, "+$150 every round", {"income": ("+", 150)}),
             ("Payday", 4500, "Ability: instant $600", {"ability": ("=", "payday"), "income": ("+", 100)}),
             ("Jackpot", 16000, "Payday pays $3000", {"ab_power": ("+", 1), "income": ("+", 300)})],
    "pirate": [("Heavy Guns", 1200, "+1 damage, 15% faster", {"dmg": ("+", 1), "rate": ("*", 0.85)}),
               ("Broadside", 3200, "Ability: cannons all around", {"ability": ("=", "broadside")}),
               ("Admiral's Fury", 12000, "Huge Broadside, +3 damage", {"ab_power": ("+", 1), "dmg": ("+", 3)})],
    "sub": [("Rapid Tubes", 1300, "Fires 25% faster", {"rate": ("*", 0.75)}),
            ("Depth Charge", 3500, "Ability: blasts the front", {"ability": ("=", "depth_charge")}),
            ("Abyss Strike", 13000, "Huge Depth Charge, +3 dmg", {"ab_power": ("+", 1), "dmg": ("+", 3)})],
    "shark": [("Strong Jaw", 1300, "+2 damage", {"dmg": ("+", 2)}),
              ("Feeding Frenzy", 3500, "Ability: 3x bites for 8s", {"ability": ("=", "feeding_frenzy")}),
              ("Apex Predator", 13000, "Huge Frenzy, +4 damage", {"ab_power": ("+", 1), "dmg": ("+", 4)})],
}

# Top and bottom paths, tiers 4 and 5: [top (t4, t5), bottom (t4, t5)]
TIERS_4_5 = {
    "dart": [
        [("Iron Boulder", 3200, "Bigger ball, bounces twice",
          {"ball_pierce": ("=", 90), "ball_dmg": ("=", 4), "ball_bounces": ("=", 2)}),
         ("Doom Boulder", 14000, "Crushes 250, bounces 4 times",
          {"ball_pierce": ("=", 250), "ball_dmg": ("=", 12), "ball_bounces": ("=", 4),
           "blimp_mult": ("=", 3), "rate": ("*", 0.7)})],
        [("Dart Gunner", 2600, "Throws twice as fast", {"rate": ("*", 0.5), "pierce": ("+", 1)}),
         ("Dart Hurricane", 11000, "Blinding speed, +2 damage",
          {"rate": ("*", 0.4), "dmg": ("+", 2), "pierce": ("+", 3), "blimp_mult": ("=", 2)})],
    ],
    "tack": [
        [("Blade Cyclone", 2800, "Spins much faster", {"rate": ("*", 0.6), "pierce": ("+", 3)}),
         ("Razor Tempest", 13000, "16 more blades, +3 damage",
          {"count": ("+", 16), "dmg": ("+", 3), "rate": ("*", 0.6), "dtype": ("=", "normal")})],
        [("Inferno Ring", 3500, "+2 fire damage, faster",
          {"dmg": ("+", 2), "rate": ("*", 0.7), "range": ("+", 15)}),
         ("Sun Ring", 15000, "+5 damage, burns blimps",
          {"dmg": ("+", 5), "rate": ("*", 0.5), "pierce": ("+", 5), "blimp_mult": ("=", 2)})],
    ],
    "boom": [
        [("Steel Crescent", 3500, "2 steel rangs, +2 damage",
          {"pierce": ("+", 15), "dmg": ("+", 2), "count": ("=", 2)}),
         ("Eclipse Blade", 14000, "Pops 40 more, +5 damage",
          {"pierce": ("+", 40), "dmg": ("+", 5), "blimp_mult": ("=", 3)})],
        [("Gale Rangs", 3200, "Push back much further", {"knock": ("+", 20), "rate": ("*", 0.7)}),
         ("Tempest Rangs", 13000, "Huge push, +4 damage",
          {"knock": ("+", 30), "dmg": ("+", 4), "rate": ("*", 0.5), "pierce": ("+", 10)})],
    ],
    "bomb": [
        [("Blimp Breaker", 4000, "+5 dmg, hits 15 more, 5x blimps",
          {"dmg": ("+", 5), "blimp_mult": ("=", 5), "pierce": ("+", 15), "rate": ("*", 0.85)}),
         ("Sky Shatter", 16000, "+15 dmg, hits 40 more, 8x blimps",
          {"dmg": ("+", 15), "blimp_mult": ("=", 8), "blast": ("+", 20), "pierce": ("+", 40), "rate": ("*", 0.7)})],
        [("Mega Clusters", 3000, "12 mini bombs, bigger blasts",
          {"cluster": ("=", 12), "dmg": ("+", 1), "blast": ("+", 10), "pierce": ("+", 10)}),
         ("Bomb Cascade", 13000, "20 mini bombs, much faster",
          {"cluster": ("=", 20), "dmg": ("+", 3), "rate": ("*", 0.6), "pierce": ("+", 25)})],
    ],
    "glue": [
        [("Corrosive Goo", 3200, "Acid 6x faster, slows more", {"acid": ("=", 0.25), "slow": ("=", 0.75)}),
         ("Meltdown", 12000, "Acid melts layers nonstop", {"acid": ("=", 0.1), "pierce": ("+", 4)})],
        [("Glue Typhoon", 3000, "Much bigger splash", {"splash": ("+", 40), "rate": ("*", 0.7)}),
         ("Amber Trap", 11000, "Glue almost stops balloons",
          {"splash": ("+", 60), "slow": ("=", 0.9), "glue_time": ("+", 8)})],
    ],
    "frost": [
        [("Glacier Heart", 2800, "Freezes longer, +2 damage", {"freeze": ("+", 0.8), "dmg": ("+", 2)}),
         ("Polar Core", 11000, "+5 damage, huge range",
          {"freeze": ("+", 1.2), "dmg": ("+", 5), "range": ("+", 40), "rate": ("*", 0.7)})],
        [("Frostbite", 2500, "+2 damage, longer slow", {"dmg": ("+", 2), "slow_after": ("+", 3)}),
         ("Endless Winter", 10000, "+4 damage, freezes longer",
          {"dmg": ("+", 4), "freeze": ("+", 1.0), "rate": ("*", 0.6)})],
    ],
    "ninja": [
        [("Star Tempest", 4500, "6 stars, +1 damage", {"count": ("=", 6), "dmg": ("+", 1), "rate": ("*", 0.75)}),
         ("Thousand Stars", 15000, "10 stars, +3 damage", {"count": ("=", 10), "dmg": ("+", 3), "pierce": ("+", 4)})],
        [("Night Blade", 5000, "+4 damage, 3x vs blimps", {"dmg": ("+", 4), "blimp_mult": ("=", 3)}),
         ("Grand Shadow", 16000, "+8 damage, twice as fast",
          {"dmg": ("+", 8), "rate": ("*", 0.5), "stun": ("+", 0.5), "pierce": ("+", 4)})],
    ],
    "sniper": [
        [("Blimp Piercer", 6000, "40 dmg, 6x blimps, faster",
          {"dmg": ("=", 40), "blimp_mult": ("=", 6), "rate": ("*", 0.7)}),
         ("One Shot", 22000, "120 dmg, 8x blimps, faster",
          {"dmg": ("=", 120), "blimp_mult": ("=", 8), "rate": ("*", 0.5)})],
        [("Full Auto", 6000, "Twice as fast, +2 damage", {"rate": ("*", 0.5), "dmg": ("+", 2)}),
         ("Bullet Storm", 20000, "Even faster, +5 damage", {"rate": ("*", 0.4), "dmg": ("+", 5)})],
    ],
    "wizard": [
        [("Storm Caller", 3500, "Lightning hits 16, +2 dmg", {"chain": ("=", 16), "dmg": ("+", 2)}),
         ("Tempest Archmage", 14000, "Lightning hits 30, +5 dmg",
          {"chain": ("=", 30), "dmg": ("+", 5), "rate": ("*", 0.6)})],
        [("Inferno Wyrm", 3200, "Fire does 3 damage", {"breath_dmg": ("=", 3), "range": ("+", 20)}),
         ("Dragon King", 13000, "Fire does 8 damage",
          {"breath_dmg": ("=", 8), "dmg": ("+", 3), "rate": ("*", 0.6)})],
    ],
    "spike": [
        [("Big Mines", 4000, "Piles pop 10 more, +2 dmg", {"pierce": ("+", 10), "dmg": ("+", 2)}),
         ("Minefield", 15000, "Piles pop 30 more, +5 dmg", {"pierce": ("+", 30), "dmg": ("+", 5), "rate": ("*", 0.6)})],
        [("Spike Rain", 6000, "Makes spikes much faster",
          {"rate": ("*", 0.6), "pierce": ("+", 4), "pile_cap": ("=", 60)}),
         ("Spike Apocalypse", 18000, "Spikes everywhere, +4 dmg",
          {"rate": ("*", 0.5), "dmg": ("+", 4), "pierce": ("+", 10), "pile_cap": ("=", 100)})],
    ],
    "village": [
        [("War Drums", 5000, "Towers in circle 30% faster", {"drums": ("=", 0.3)}),
         ("Great Temple", 20000, "45% faster, +20% range", {"drums": ("=", 0.45), "boost": ("+", 0.2)})],
        [("Trade Harbor", 6000, "+$800/round, 20% off", {"income": ("=", 800), "discount": ("=", 0.2)}),
         ("Golden City", 22000, "+$2500/round, 25% off", {"income": ("=", 2500), "discount": ("=", 0.25)})],
    ],
    "super": [
        [("Star Forge", 30000, "+4 damage, +5 pierce", {"dmg": ("+", 4), "pierce": ("+", 5), "rate": ("*", 0.8)}),
         ("Cosmic Titan", 90000, "+12 damage, 4x vs blimps",
          {"dmg": ("+", 12), "pierce": ("+", 10), "blimp_mult": ("=", 4)})],
        [("Robo Guard", 22000, "3 beams, +2 damage", {"count": ("=", 3), "dmg": ("+", 2)}),
         ("Mecha Sentinel", 65000, "4 beams, 8x vs blimps",
          {"count": ("=", 4), "dmg": ("+", 6), "blimp_mult": ("=", 8)})],
    ],
    "mine": [
        [("Mother Lode", 4500, "+$500 every round", {"income": ("+", 500)}),
         ("Dragon's Hoard", 18000, "+$1800 every round", {"income": ("+", 1800)})],
        [("Healing Spring", 4000, "+8 lives every round", {"lives": ("+", 8)}),
         ("Fountain of Life", 15000, "+25 lives, double money", {"lives": ("+", 25), "mult": ("=", 2.0)})],
    ],
    "pirate": [
        [("Warship", 3800, "6 cannonballs, +2 damage", {"count": ("=", 6), "dmg": ("+", 2)}),
         ("Dread Armada", 15000, "10 cannonballs, +4 damage",
          {"count": ("=", 10), "dmg": ("+", 4), "pierce": ("+", 4), "blimp_mult": ("=", 3)})],
        [("Merchant Empire", 5000, "+$700 every round", {"income": ("=", 700)}),
         ("Golden Armada", 18000, "+$2000/round, faster", {"income": ("=", 2000), "rate": ("*", 0.6)})],
    ],
    "sub": [
        [("Torpedo Storm", 3800, "5 torpedoes, +2 damage", {"count": ("=", 5), "dmg": ("+", 2)}),
         ("Leviathan", 15000, "8 torpedoes, +5 damage", {"count": ("=", 8), "dmg": ("+", 5), "pierce": ("+", 5)})],
        [("Blimp Destroyer", 5000, "8x vs blimps, +2 damage", {"blimp_mult": ("=", 8), "dmg": ("+", 2)}),
         ("Sky Hunter", 18000, "12x vs blimps, faster",
          {"blimp_mult": ("=", 12), "dmg": ("+", 5), "rate": ("*", 0.6)})],
    ],
    "shark": [
        [("Titan Bite", 4500, "+6 damage, 5x vs blimps", {"dmg": ("+", 6), "blimp_mult": ("=", 5)}),
         ("Megalodon", 16000, "+15 damage, bites 6 more",
          {"dmg": ("+", 15), "pierce": ("+", 6), "blimp_mult": ("=", 8)})],
        [("Whirlpool", 3500, "Drags much further back", {"knock": ("+", 30), "pierce": ("+", 4)}),
         ("Maelstrom", 13000, "Huge pull, bites 10 more",
          {"knock": ("+", 50), "pierce": ("+", 10), "range": ("+", 30)})],
    ],
}
for _tt in TOWER_TYPES:
    _k = _tt["key"]
    _tt["paths"][0] = _tt["paths"][0] + TIERS_4_5[_k][0]
    _tt["paths"][1] = _tt["paths"][1][:2] + MIDDLE_TOP[_k]   # ability moves to tier 4
    _tt["paths"][2] = _tt["paths"][2] + TIERS_4_5[_k][1]
MAX_TIER = 5
PATH_COLORS = [(255, 120, 80), (110, 220, 110), (90, 170, 255)]   # pips: top, middle, bottom

# ---------------------------------------------------------------------
# Heroes: one per game, bought from the shop. They level up (1-20) by
# themselves as they pop balloons and as rounds go by.
# ---------------------------------------------------------------------
HERO_TYPES = [
    dict(key="knight", name="Spark Knight", cost=550, desc="Lightning sword hits groups",
         hero=True, paths=[], abilities=[(5, "thunder_strike"), (14, "storm_blade")]),
    dict(key="witch", name="Wind Witch", cost=500, desc="Gusts pop and push back",
         hero=True, paths=[], abilities=[(5, "twister"), (14, "hurricane")]),
    dict(key="gear", name="Gear Gunner", cost=500, desc="Rapid-fire bolt gun",
         hero=True, paths=[], abilities=[(5, "overclock"), (14, "mega_mortar")]),
    dict(key="cipher", name="Cipher", cost=600, desc="Hacker: cash, strips camo",
         hero=True, paths=[], abilities=[(4, "crypto_boost"), (12, "glitch_wave")]),
    dict(key="nova", name="Nova", cost=650, desc="Mind power lifts balloons",
         hero=True, paths=[], abilities=[(5, "mind_blast"), (13, "gravity_well")]),
]
HERO_KEYS = [h["key"] for h in HERO_TYPES]
SHOP = TOWER_TYPES + HERO_TYPES
HERO_MAX_LEVEL = 20
# total XP needed to reach each level (index 0 = level 1)
HERO_XP = [0, 40, 100, 180, 280, 400, 540, 700, 880, 1080,
           1300, 1550, 1830, 2140, 2480, 2850, 3250, 3680, 4140, 4630]


def hero_stats(key, lvl):
    """A hero's stats at a level (1-20)."""
    f = (lvl - 1) / (HERO_MAX_LEVEL - 1)
    if key == "knight":
        return dict(range=85 + 25 * f, rate=0.95 - 0.4 * f, dmg=1 + (lvl >= 6) + (lvl >= 12) + (lvl >= 18),
                    pierce=5 + lvl // 2, dtype="normal" if lvl >= 8 else "sharp", camo=lvl >= 10)
    if key == "witch":
        return dict(range=130 + 30 * f, rate=0.85 - 0.35 * f, dmg=1 + (lvl >= 9) + (lvl >= 17),
                    pierce=6 + lvl // 2, knock=14 + lvl, speed=380, dtype="normal", camo=lvl >= 3,
                    count=1 + (lvl >= 11) + (lvl >= 19), spread=0.2)
    if key == "gear":
        return dict(range=140 + 30 * f, rate=0.36 - 0.18 * f, dmg=1 + (lvl >= 7) + (lvl >= 15),
                    pierce=1 + lvl // 6, speed=640, dtype="normal" if lvl >= 9 else "sharp",
                    camo=lvl >= 4, count=1 + (lvl >= 12), spread=0.12)
    if key == "cipher":
        return dict(range=120 + 20 * f, rate=0.9 - 0.4 * f, dmg=1 + (lvl >= 10), pierce=2 + lvl // 5,
                    speed=500, dtype="normal", camo=lvl >= 2, count=1, spread=0.0,
                    income=40 + 15 * lvl, lives=3 if lvl >= 16 else 0, decamo=lvl >= 7)
    # nova
    return dict(range=120 + 30 * f, rate=1.3 - 0.6 * f, lift_n=min(6, 1 + lvl // 4),
                lift_time=1.5 + 0.1 * lvl, dmg=1 + (lvl >= 10) + (lvl >= 18),
                camo=lvl >= 6, lift_heavy=lvl >= 12)


# name, cooldown (seconds), what it does
ABILITIES = {
    "dart_storm":   ("Dart Storm", 40, "Darts fly 4x faster for 6s"),
    "tack_nova":    ("Tack Nova", 35, "Blasts 48 tacks all around"),
    "rang_barrage": ("Rang Barrage", 40, "Throws 12 boomerangs"),
    "carpet_bomb":  ("Carpet Bomb", 50, "Bombs the front of the line"),
    "glue_rain":    ("Glue Rain", 45, "Glues every balloon"),
    "blizzard":     ("Blizzard", 50, "Freezes every balloon 3s"),
    "smoke_bomb":   ("Smoke Bomb", 45, "Knocks all balloons back"),
    "cash_crate":   ("Cash Crate", 50, "Drops $300"),
    "meteor":       ("Meteor", 45, "Huge blast on the strongest"),
    "spike_carpet": ("Spike Carpet", 40, "Covers the track in spikes"),
    "rally_cry":    ("Rally Cry", 60, "All towers 2x faster for 8s"),
    "overdrive":    ("Overdrive", 50, "3x speed for 8s"),
    "payday":       ("Payday", 60, "Instant $600"),
    "broadside":    ("Broadside", 40, "16 cannonballs all around"),
    "depth_charge": ("Depth Charge", 50, "Blasts the front of the line"),
    "feeding_frenzy": ("Feeding Frenzy", 50, "Bites 3x faster for 8s"),
    # hero abilities
    "thunder_strike": ("Thunder Strike", 40, "Lightning jumps to 15 balloons"),
    "storm_blade":    ("Storm Blade", 60, "Slashes 3x faster for 10s"),
    "twister":        ("Twister", 40, "Blows nearby balloons far back"),
    "hurricane":      ("Hurricane", 60, "Slows everything, 2 damage"),
    "overclock":      ("Overclock", 40, "Fires 3x faster for 8s"),
    "mega_mortar":    ("Mega Mortar", 55, "Giant blast on the strongest"),
    "crypto_boost":   ("Crypto Boost", 50, "Instant cash"),
    "glitch_wave":    ("Glitch Wave", 55, "Strips a layer + camo off all"),
    "mind_blast":     ("Mind Blast", 40, "Shockwave: 3 damage + stun"),
    "gravity_well":   ("Gravity Well", 60, "Lifts 30 balloons into the air"),
}

STAT_LABELS = [("dmg", "Damage"), ("pierce", "Pierce"), ("count", "Shots"), ("rate", "Speed"),
               ("range", "Range"), ("blast", "Blast"), ("freeze", "Freeze"), ("chain", "Zaps"),
               ("knock", "Push"), ("glue_time", "Glue"), ("slow", "Slow"), ("life", "Spikes last"),
               ("income", "Income"), ("lives", "Lives"), ("boost", "Boost"), ("discount", "Discount"),
               ("blimp_mult", "vs blimps"), ("ab_power", "Ability power"), ("ball_dmg", "Ball dmg"),
               ("ball_pierce", "Ball pops"), ("ball_bounces", "Bounces"), ("breath_dmg", "Fire dmg"),
               ("drums", "Speed boost"), ("pile_cap", "Max piles"), ("cluster", "Mini bombs"),
               ("splash", "Splash"), ("acid", "Acid every")]
FLAG_LABELS = {"camo": "sees camo", "homing": "homing", "spikeball": "Spike Ball", "breath": "flamethrower",
               "freeze_white": "freezes white", "radar": "camo radar", "rune": "lead popping",
               "glue_blimp": "glues blimps", "mines": "spike mines", "ability": "new ability", "acid": "acid"}


def fmt_stat(key, v):
    if key == "rate":
        return "%.1f/s" % (1.0 / v)
    if key in ("slow", "boost", "discount", "drums"):
        return "%d%%" % round(v * 100)
    if key in ("glue_time", "freeze", "life", "acid"):
        return "%.1fs" % v
    if key == "income":
        return "$%d" % v
    if key == "blimp_mult":
        return "%gx" % v
    return "%d" % round(v) if isinstance(v, float) else str(v)


def stat_changes(old, new):
    """Short text like 'Pierce 3>5, Speed 1.2/s>1.5/s' for an upgrade preview."""
    out = []
    for key, label in STAT_LABELS:
        if key in new and old.get(key) != new[key] and isinstance(new[key], (int, float)) \
                and not isinstance(new[key], bool) and key in old:
            out.append("%s %s>%s" % (label, fmt_stat(key, old[key]), fmt_stat(key, new[key])))
    for key, label in FLAG_LABELS.items():
        if new.get(key) and not old.get(key):
            out.append("+" + label)
    if new.get("dtype") != old.get("dtype") and new.get("dtype") in ("normal", "magic"):
        out.append("+pops lead")
    return ", ".join(out) or "Small boost"


def stat_summary(s):
    parts = []
    for key, label in (("dmg", "Dmg"), ("pierce", "Pierce"), ("count", "Shots"), ("rate", "Speed"),
                       ("range", "Range"), ("income", "Income")):
        if key in s and not (key == "count" and s[key] <= 1) and not (key == "range" and not 0 < s[key] < 600) \
                and not (key == "dmg" and not s[key]) and not (key == "income" and not s[key]):
            parts.append("%s %s" % (label, fmt_stat(key, s[key])))
    return "  ".join(parts)


TARGET_MODES = ["First", "Last", "Strong", "Close"]
TOWER_SPEED_BOOST = 0.85   # all towers attack 15% faster
EXTRA_PIERCE_TOWERS = ("dart", "tack", "boom", "ninja", "wizard", "super")   # +1 pierce
SOUND_ROW = "<sound slider>"   # menus draw this row as a volume slider
NO_TARGETING = ("mine", "frost", "spike", "village")   # towers that don't aim

# =====================================================================
# Maps (coordinates inside the 480x480 play field)
# =====================================================================
# paths: one or more tracks (balloons take turns between them).
# water / rocks: circles (x, y, radius) where you can't build.
# A track that ends inside the field ends in a hole.
MAPS = [
    dict(name="Meadow", level="Easy", seed=3,
         paths=[[(-30, 60), (400, 60), (400, 180), (80, 180), (80, 300),
                 (400, 300), (400, 420), (240, 420), (240, 520)]]),
    dict(name="Lake Loop", level="Easy", seed=5,
         paths=[[(-30, 420), (420, 420), (420, 60), (60, 60), (60, 330),
                 (330, 330), (330, 520)]],
         water=[(185, 195, 72), (295, 195, 72), (240, 180, 60)]),
    dict(name="Harbor", level="Medium", seed=23,
         paths=[[(-30, 60), (440, 60), (440, 440), (40, 440), (40, 150), (100, 150)]],
         water=[(250, 260, 105), (175, 300, 55), (330, 300, 55),
                (385, 260, 38), (115, 290, 40), (250, 380, 35)]),   # coves that reach the track
    dict(name="Crossroads", level="Medium", seed=7,
         paths=[[(-30, 240), (360, 240), (360, 80), (120, 80), (120, 400),
                 (400, 400), (400, 520)]]),
    dict(name="Spiral", level="Medium", seed=13,
         paths=[[(-30, 40), (440, 40), (440, 440), (40, 440), (40, 140),
                 (340, 140), (340, 340), (140, 340), (140, 240), (245, 240)]]),
    dict(name="Rapids", level="Hard", seed=11,
         paths=[[(240, -30), (240, 160), (420, 160), (420, 330), (60, 330),
                 (60, 520)]]),
    dict(name="Twin Lanes", level="Hard", seed=17, extra_money=300, bonus_mult=1.3,
         paths=[[(60, -30), (60, 200), (180, 200), (180, 380), (240, 380), (240, 450),
                 (420, 450), (420, 520)],
                [(420, -30), (420, 200), (300, 200), (300, 380), (240, 380), (240, 450),
                 (420, 450), (420, 520)]],
         water=[(240, 90, 55)]),
    dict(name="Canyon", level="Hard", seed=19,
         paths=[[(-30, 420), (100, 420), (100, 300), (220, 300), (220, 180),
                 (340, 180), (340, 60), (520, 60)]],
         rocks=[(190, 420, 34), (310, 300, 36), (430, 190, 32), (60, 190, 42),
                (200, 60, 36), (430, 420, 46), (320, 420, 28), (100, 60, 26)]),
]

DIFFICULTIES = [
    dict(name="Easy", lives=200, cost=0.8, speed=0.9, money=850),
    dict(name="Normal", lives=150, cost=1.0, speed=1.0, money=START_MONEY),
    dict(name="Hard", lives=100, cost=1.08, speed=1.1, money=START_MONEY),
    dict(name="Sandbox", lives=999999, cost=1.0, speed=1.0, money=999999, sandbox=True),   # for testing
]

# =====================================================================
# Rounds: (balloon, how many, seconds between, start delay, camo?)
# =====================================================================
ROUNDS = [
    [("red", 20, 0.9, 0)],
    [("red", 30, 0.7, 0)],
    [("red", 15, 0.6, 0), ("blue", 8, 1.0, 4)],
    [("red", 25, 0.5, 0), ("blue", 15, 0.8, 3)],
    [("blue", 25, 0.7, 0), ("red", 10, 0.5, 6)],
    [("blue", 20, 0.6, 0), ("green", 6, 1.2, 5)],
    [("blue", 25, 0.5, 0), ("green", 12, 0.9, 4)],
    [("green", 20, 0.7, 0), ("blue", 20, 0.3, 8)],
    [("green", 30, 0.55, 0)],
    [("blue", 80, 0.22, 0)],
    [("green", 20, 0.5, 0), ("yellow", 10, 1.0, 4)],                       # 11
    [("yellow", 20, 0.7, 0), ("green", 15, 0.4, 5)],
    [("green", 30, 0.35, 0), ("yellow", 15, 0.6, 4), ("pink", 6, 1.0, 10, "r")],
    [("pink", 15, 0.8, 0), ("yellow", 25, 0.4, 3)],
    [("black", 12, 0.8, 0), ("white", 12, 0.8, 5)],
    [("yellow", 20, 0.5, 0), ("pink", 15, 0.6, 4), ("green", 8, 0.8, 8, True)],
    [("lead", 8, 1.5, 0), ("yellow", 25, 0.4, 2)],
    [("pink", 30, 0.4, 0), ("black", 10, 0.7, 6), ("purple", 5, 0.9, 12)],
    [("zebra", 10, 1.0, 0), ("pink", 20, 0.4, 3)],
    [("zebra", 8, 0.8, 0), ("lead", 10, 1.0, 4), ("pink", 8, 0.8, 6, True)],
    [("zebra", 15, 0.7, 0), ("rainbow", 5, 1.5, 6), ("yellow", 12, 0.5, 10, "r")],   # 21
    [("rainbow", 10, 1.0, 0), ("lead", 8, 0.8, 5)],
    [("ceramic", 3, 2.5, 0), ("zebra", 15, 0.5, 3), ("black", 8, 0.6, 8, True), ("purple", 8, 0.6, 12)],
    [("rainbow", 14, 0.8, 0), ("ceramic", 3, 2.0, 6)],
    [("ceramic", 4, 1.5, 0), ("blimp", 1, 1, 10)],
    [("zebra", 12, 0.6, 0, True), ("ceramic", 6, 1.2, 6)],
    [("lead", 12, 0.5, 0), ("lead", 4, 1.0, 7, "f"), ("ceramic", 8, 1.0, 4)],
    [("ceramic", 9, 0.8, 0), ("ceramic", 3, 1.5, 6, "f"), ("blimp", 1, 1, 10)],
    [("ceramic", 6, 0.9, 0, True), ("ceramic", 6, 0.9, 6), ("purple", 12, 0.4, 3), ("blimp", 2, 4, 10)],
    [("blimp", 2, 3, 0), ("titan", 1, 1, 8)],
]


def freeplay_round(n):
    """Rounds 31-150 (and freeplay after that) get steadily harder:
    Phantoms from round 45, Colossi from round 50, the Overlord at 100, 125 and 150."""
    k = n - len(ROUNDS)
    flags = ["", "c", "f", "cf"][n % 4]
    groups = [("ceramic", min(25 + k // 2, 70), max(0.12, 0.45 - 0.003 * k), 0, flags),
              ("blimp", min(1 + k // 6, 20), max(0.6, 2.2 - 0.012 * k), 6, "f" if n >= 60 else "")]
    if n % 3 == 0:
        groups.append(("purple", min(10 + k // 3, 40), 0.3, 2))
    if n % 5 == 0:
        groups.append(("lead", 20, 0.25, 3, "f"))
    if n >= 35:
        groups.append(("titan", min(1 + (n - 35) // 8, 12), max(1.0, 4 - 0.03 * (n - 35)), 12,
                       "f" if n >= 80 else ""))
    if n >= 45:
        groups.append(("phantom", min(1 + (n - 45) // 5, 20), max(0.5, 2.0 - 0.015 * (n - 45)), 8))
    if (n >= 50 and n % 10 == 0) or (n >= 90 and n % 5 == 0):
        groups.append(("colossus", 1 + (n - 50) // 30, 6, 20, "f" if n >= 110 else ""))
    if n in (100, 125, FINAL_ROUND) or (n > FINAL_ROUND and n % 10 == 0):
        groups.append(("overlord", 1 + max(0, n - FINAL_ROUND) // 30, 8, 30))
    return groups


def round_cost(base, mult):
    return int(round(base * mult / 5.0)) * 5


# =====================================================================
# Input: keyboard + gamepad, turned into 10 simple actions
# =====================================================================
ACTIONS = ("UP", "DOWN", "LEFT", "RIGHT", "A", "B", "L", "R", "START", "SELECT", "ABILITY")


class Input:
    def __init__(self):
        self.held = set()       # buttons down right now
        self.pressed = set()    # buttons that went down this frame
        self.repeat = set()     # pressed, or held long enough to auto-repeat
        self.hold_time = {}
        self.joys = {}
        self.virtual = set()    # buttons held by something else (the emulator)

    def add_joystick(self, index):
        j = pygame.joystick.Joystick(index)
        j.init()
        self.joys[j.get_instance_id()] = j

    def remove_joystick(self, instance_id):
        self.joys.pop(instance_id, None)

    def update(self, dt):
        cur = set(self.virtual)
        keys = pygame.key.get_pressed()
        for act, keylist in KEYMAP.items():
            if any(keys[k] for k in keylist):
                cur.add(act)
        for j in self.joys.values():
            nb = j.get_numbuttons()
            for act, idx in PAD_BUTTONS.items():
                if idx < nb and j.get_button(idx):
                    cur.add(act)
            if j.get_numhats() > 0:
                hx, hy = j.get_hat(0)
                if hx < 0: cur.add("LEFT")
                if hx > 0: cur.add("RIGHT")
                if hy > 0: cur.add("UP")
                if hy < 0: cur.add("DOWN")
            if j.get_numaxes() >= 2:
                ax, ay = j.get_axis(0), j.get_axis(1)
                if ax < -AXIS_DEADZONE: cur.add("LEFT")
                if ax > AXIS_DEADZONE: cur.add("RIGHT")
                if ay < -AXIS_DEADZONE: cur.add("UP")
                if ay > AXIS_DEADZONE: cur.add("DOWN")
        self.pressed = cur - self.held
        self.repeat = set()
        for a in cur:
            if a in self.pressed:
                self.hold_time[a] = 0.0
                self.repeat.add(a)
                continue
            prev = self.hold_time.get(a, 0.0)
            now = prev + dt
            self.hold_time[a] = now
            if now >= REPEAT_DELAY:
                n_prev = int((prev - REPEAT_DELAY) / REPEAT_RATE) if prev >= REPEAT_DELAY else -1
                if int((now - REPEAT_DELAY) / REPEAT_RATE) > n_prev:
                    self.repeat.add(a)
        self.held = cur

    def any_held_time(self):
        return max((self.hold_time.get(a, 0) for a in self.held), default=0)


# =====================================================================
# Sound effects (made from math, so there are no sound files to copy)
# =====================================================================
class Sounds:
    def __init__(self):
        self.ok = False
        self.sounds = {}
        self.last_pop = 0
        self.volume = 0.7   # 0.0 (muted) to 1.0
        try:
            init = pygame.mixer.get_init()
            if not init:
                return
            self.rate, _, self.channels = init
            pygame.mixer.set_num_channels(12)
            self.sounds["pop"] = self._make(0.05, lambda t, p: random.uniform(-1, 1) * (1 - p) ** 3, 0.35)
            self.sounds["boom"] = self._make(0.25, lambda t, p: random.uniform(-1, 1) * (1 - p) ** 2
                                             * (0.6 + 0.4 * math.sin(t * 300)), 0.4)
            self.sounds["place"] = self._make(0.12, lambda t, p: math.sin(t * 2 * math.pi * (500 + 600 * p))
                                              * (1 - p), 0.3)
            self.sounds["upgrade"] = self._make(0.2, lambda t, p: math.sin(t * 2 * math.pi * (660 if p < 0.5 else 990))
                                                * (1 - p * 0.7), 0.3)
            self.sounds["leak"] = self._make(0.25, lambda t, p: (1 if math.sin(t * 2 * math.pi * 110) > 0 else -1)
                                             * (1 - p), 0.15)
            self.sounds["error"] = self._make(0.12, lambda t, p: (1 if math.sin(t * 2 * math.pi * 160) > 0 else -1)
                                              * (1 - p), 0.15)
            self.ok = True
        except (pygame.error, ValueError):
            self.ok = False

    def _make(self, secs, wave, vol):
        n = int(self.rate * secs)
        data = array("h")
        for i in range(n):
            v = int(max(-1.0, min(1.0, wave(i / self.rate, i / n))) * 32000 * vol)
            for _ in range(self.channels):
                data.append(v)
        return pygame.mixer.Sound(buffer=data.tobytes())

    def set_volume(self, volume):
        self.volume = max(0.0, min(1.0, volume))
        for snd in self.sounds.values():
            snd.set_volume(self.volume)

    def play(self, name):
        if not self.ok or self.volume <= 0:
            return
        if name == "pop":   # many balloons pop at once; don't play them all
            now = pygame.time.get_ticks()
            if now - self.last_pop < 45:
                return
            self.last_pop = now
        self.sounds[name].play()


# =====================================================================
# Game objects
# =====================================================================
class Path:
    """The track balloons follow, made of straight segments."""

    def __init__(self, pts):
        self.pts = pts
        self.segs = []   # (x0, y0, dir_x, dir_y, length, start_distance)
        d = 0.0
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            length = math.hypot(x1 - x0, y1 - y0)
            self.segs.append((x0, y0, (x1 - x0) / length, (y1 - y0) / length, length, d))
            d += length
        self.total = d

    def pos(self, dist, seg=0):
        segs = self.segs
        last = len(segs) - 1
        seg = min(seg, last)
        while seg < last and dist > segs[seg][5] + segs[seg][4]:
            seg += 1
        while seg > 0 and dist < segs[seg][5]:
            seg -= 1
        x0, y0, ux, uy, _, start = segs[seg]
        t = dist - start
        return x0 + ux * t, y0 + uy * t, seg

    def distance_to(self, px, py):
        best = 1e9
        for x0, y0, ux, uy, length, _ in self.segs:
            t = max(0.0, min(length, (px - x0) * ux + (py - y0) * uy))
            best = min(best, math.hypot(px - (x0 + ux * t), py - (y0 + uy * t)))
        return best


class Balloon:
    __slots__ = ("name", "info", "hp", "dist", "x", "y", "seg", "alive", "camo",
                 "frozen", "slow", "id", "speed_now", "rank", "r", "path",
                 "glue", "glue_slow", "acid", "acid_t", "glue_by", "regrow", "regrow_t", "fort",
                 "lift", "lift_t", "lift_by")

    def __init__(self, name, dist, camo, bid, hp_mult, path, regrow=None, fort=False):
        self.name = name
        self.info = BALLOON_TYPES[name]
        self.hp = self.info["hp"] * (hp_mult if self.info["hp"] > 1 else 1)
        self.dist = dist
        self.x = self.y = -100.0
        self.seg = 0
        self.alive = True
        self.camo = camo
        self.frozen = 0.0
        self.slow = 0.0
        self.id = bid
        self.speed_now = 0.0
        self.rank = BALLOON_ORDER.index(name)
        self.r = self.info["r"]
        self.path = path
        self.glue = 0.0          # seconds of glue left
        self.glue_slow = 0.0
        self.acid = 0.0          # acid glue: pops a layer every this many seconds
        self.acid_t = 0.0
        self.glue_by = None
        self.regrow = regrow     # regrow balloons grow back up to this type
        self.regrow_t = 0.0
        self.lift = 0.0          # Nova: seconds held up in the air (can't move)
        self.lift_t = 0.0
        self.lift_by = None
        self.fort = fort and name in FORTIFIABLE
        if self.fort:            # armored: twice the hits (lead needs 4)
            self.hp = self.hp * 2 if self.hp > 1 else 4

    def set_type(self, name):
        """Change into another balloon type (used when regrowing)."""
        self.name = name
        self.info = BALLOON_TYPES[name]
        self.hp = self.info["hp"]
        self.rank = BALLOON_ORDER.index(name)
        self.r = self.info["r"]


class Tower:
    def __init__(self, ttype, x, y, cost):
        self.t = ttype
        self.key = ttype["key"]
        self.x, self.y = x, y
        self.levels = [] if ttype.get("hero") else [0, 0, 0]   # heroes level up instead
        self.spent = cost
        self.cool = 0.2
        self.angle = -math.pi / 2
        self.target_mode = 2 if self.key == "sniper" else 0
        self.pops = 0
        self.dmg_done = 0         # total damage dealt this match (shown in the tower menu)
        self.flash = 0.0
        self.cool2 = 0.0          # Dragon's Breath flamethrower
        self.curve = 1            # Boomerang: 1 = curves right, -1 = curves left
        self.shots = 0            # Ninja: every 4th throw can be a stun bomb
        self.spots = None         # Spike Factory: places on the track it can reach
        self.frenzy_t = 0.0       # abilities like Dart Storm: attack faster for a while
        self.frenzy_rate = 1.0
        self.frenzy_count = 0
        self.ab_cool = {}         # ability -> seconds until it's ready again
        self.hero = bool(ttype.get("hero"))
        self.xp = 0               # heroes only
        self.hero_level = 1
        self.recalc()

    def recalc(self):
        if self.hero:
            s = hero_stats(self.key, self.hero_level)
            if "rate" in s:
                s["rate"] *= TOWER_SPEED_BOOST
            self.s = s
            return
        s = dict(self.t["base"])
        for p in range(len(self.t["paths"])):
            for i in range(self.levels[p]):
                for k, (op, v) in self.t["paths"][p][i][3].items():
                    if op == "+":
                        s[k] = s.get(k, 1 if k == "ab_power" else 0) + v   # ability power starts at 1
                    elif op == "*":
                        s[k] = s.get(k, 1) * v
                    else:
                        s[k] = v
        # every tower got a power boost after playtesting
        if "rate" in s:
            s["rate"] *= TOWER_SPEED_BOOST
        if self.key in EXTRA_PIERCE_TOWERS and "pierce" in s:
            s["pierce"] += 1
        self.s = s

    def upgrade_state(self, p):
        """Returns 'ok', 'max', 'locked' (another path is at 3) or 'two'
        (two other paths are already upgraded) for upgrade path p."""
        lv = self.levels[p]
        if lv >= MAX_TIER:
            return "max"
        others = [self.levels[i] for i in range(len(self.levels)) if i != p]
        if lv == 0 and sum(1 for o in others if o) >= 2:
            return "two"
        if lv + 1 >= 3 and any(o >= 3 for o in others):
            return "locked"   # only one path can go past level 2
        return "ok"

    def abilities(self):
        """Abilities this tower has unlocked."""
        if self.hero:
            return [aid for lvl, aid in self.t["abilities"] if self.hero_level >= lvl]
        return [self.s["ability"]] if self.s.get("ability") else []

    def xp_level(self):
        lvl = 1
        while lvl < HERO_MAX_LEVEL and self.xp >= HERO_XP[lvl]:
            lvl += 1
        return lvl


class Proj:
    __slots__ = ("kind", "x", "y", "vx", "vy", "life", "dmg", "pierce", "dtype",
                 "r", "hit", "tower", "blast", "cluster", "bm", "dead", "angle", "homing",
                 "turn", "knock", "bounces")

    def __init__(self, kind, x, y, angle, speed, life, dmg, pierce, dtype, r, tower):
        self.kind = kind
        self.x, self.y = x, y
        self.angle = angle
        self.vx, self.vy = math.cos(angle) * speed, math.sin(angle) * speed
        self.life = life
        self.dmg = dmg
        self.pierce = pierce
        self.dtype = dtype
        self.r = r
        self.hit = set()
        self.tower = tower
        self.blast = 0
        self.cluster = 0
        self.bm = 1
        self.dead = False
        self.homing = False
        self.turn = 0.0          # boomerangs curve (radians per second)
        self.knock = 0           # push balloons back this far on hit
        self.bounces = 0         # Spike Ball: walls it can still bounce off


# =====================================================================
# Sprite drawing (done once at start, then just copied each frame)
# =====================================================================
def darker(c, f=0.6):
    return tuple(int(v * f) for v in c[:3])


LIGHT = (-0.45, -0.55, 0.70)   # light comes from the top left


def shade_ball(s, cx, cy, rx, ry, strength=1.0):
    """Make a flat circle/ellipse on sprite s look round: darker away from the
    light, plus a shiny spot. Done once when the sprite is made."""
    w, h = s.get_size()
    for y in range(max(0, int(cy - ry)), min(h, int(cy + ry) + 1)):
        for x in range(max(0, int(cx - rx)), min(w, int(cx + rx) + 1)):
            nx, ny = (x - cx) / rx, (y - cy) / ry
            d = nx * nx + ny * ny
            if d >= 1.0:
                continue
            r, g, b, a = s.get_at((x, y))
            if a == 0:
                continue
            nz = math.sqrt(1.0 - d)
            light = max(0.0, nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2])
            f = 1.0 + strength * (0.6 * light - 0.35)
            shine = strength * 150 * light ** 14
            s.set_at((x, y), (min(255, int(r * f + shine)), min(255, int(g * f + shine)),
                              min(255, int(b * f + shine)), a))


def make_balloon_sprite(name, camo):
    info = BALLOON_TYPES[name]
    r = info["r"]
    size = r * 2 + 8
    s = pygame.Surface((size, size + 6), pygame.SRCALPHA)
    c = size // 2
    col = info["color"]
    dark = darker(col) if name not in ("white", "zebra") else (120, 120, 120)
    if name == "black":
        dark = (90, 90, 100)
    # knot and string
    pygame.draw.line(s, (60, 60, 60), (c, c + r + 2), (c - 2, c + r + 6), 1)
    pygame.draw.polygon(s, dark, [(c - 4, c + r + 3), (c + 4, c + r + 3), (c, c + r - 2)])
    if name == "rainbow":
        cols = [(230, 50, 50), (250, 150, 30), (250, 230, 40), (60, 190, 60), (50, 120, 230), (150, 70, 200)]
        for i, rc in enumerate(cols):
            pygame.draw.circle(s, rc, (c, c), max(2, r - i * r // 6))
    else:
        pygame.draw.circle(s, col, (c, c), r)
    if name == "zebra":
        for dy in (-r // 2, 0, r // 2):
            half = int(math.sqrt(max(0, r * r - dy * dy))) - 1
            pygame.draw.line(s, (20, 20, 20), (c - half, c + dy), (c + half, c + dy), 3)
    if name == "ceramic":
        pygame.draw.circle(s, (215, 150, 80), (c, c), r - 4, 3)
    if name == "lead":
        pygame.draw.circle(s, (85, 90, 100), (c, c), r, 3)
    if camo:
        spots = [(-0.4, 0.1, 0.32), (0.35, -0.3, 0.28), (0.2, 0.45, 0.25), (-0.1, -0.5, 0.2)]
        for i, (sx, sy, sr) in enumerate(spots):
            pygame.draw.circle(s, (70, 100, 40) if i % 2 else (110, 130, 60),
                               (int(c + sx * r), int(c + sy * r)), max(2, int(sr * r)))
    shade_ball(s, c, c, r, r)
    pygame.draw.circle(s, (40, 70, 30) if camo else dark, (c, c), r, 2)
    return s, c, c


def make_blimp_sprites(name):
    info = BALLOON_TYPES[name]
    w, h = info["w"], info["h"]
    col = info["color"]
    dark = darker(col)
    s = pygame.Surface((w + 14, h + 10), pygame.SRCALPHA)
    cy = (h + 10) // 2
    # tail fins (blimp faces right)
    pygame.draw.polygon(s, dark, [(0, 2), (22, cy - 4), (8, cy - 4)])
    pygame.draw.polygon(s, dark, [(0, h + 8), (22, cy + 4), (8, cy + 4)])
    body = pygame.Rect(6, 5, w, h)
    pygame.draw.ellipse(s, col, body)
    if name == "phantom":      # sleek, with camo spots and a red stripe
        for fx, fy, fr in ((0.3, 0.4, 0.14), (0.55, 0.65, 0.12), (0.75, 0.35, 0.1), (0.45, 0.25, 0.09)):
            pygame.draw.circle(s, (70, 100, 60), (6 + int(w * fx), 5 + int(h * fy)), int(h * fr * 1.4))
        pygame.draw.line(s, (220, 50, 50), (6 + int(w * 0.15), cy), (6 + int(w * 0.9), cy), 3)
    elif name == "colossus":   # dark armor plates
        for i in range(4):
            x = 6 + int(w * (0.2 + i * 0.17))
            pygame.draw.rect(s, (25, 70, 35), (x, 8, int(w * 0.1), h - 6), border_radius=4)
        pygame.draw.line(s, (240, 240, 240), (6 + int(w * 0.85), 10), (6 + int(w * 0.85), h), 5)
    elif name == "overlord":   # gold bands and a glowing eye
        for fx in (0.3, 0.5, 0.7):
            pygame.draw.line(s, (235, 190, 60), (6 + int(w * fx), 7), (6 + int(w * fx), h + 3), 6)
        pygame.draw.circle(s, (255, 230, 120), (6 + int(w * 0.86), cy), h // 6)
        pygame.draw.circle(s, (200, 30, 30), (6 + int(w * 0.86), cy), h // 10)
    else:
        pygame.draw.line(s, (240, 240, 240), (6 + int(w * 0.62), 8), (6 + int(w * 0.62), h + 2), 4)
        pygame.draw.rect(s, darker(col, 0.7), (6 + int(w * 0.25), cy + h // 3 - 2, w // 3, 6), border_radius=3)
    shade_ball(s, 6 + w / 2, 5 + h / 2, w / 2, h / 2)
    pygame.draw.ellipse(s, dark, body, 3)
    cx = s.get_width() // 2
    out = {"R": (s, cx, cy), "L": (pygame.transform.flip(s, True, False), cx, cy)}
    down = pygame.transform.rotate(s, -90)
    up = pygame.transform.rotate(s, 90)
    out["D"] = (down, down.get_width() // 2, down.get_height() // 2)
    out["U"] = (up, up.get_width() // 2, up.get_height() // 2)
    return out


def draw_stone_base(s, c, r):
    """A round stone base land towers stand on."""
    pygame.draw.circle(s, (96, 92, 88), (c, c), r + 3)
    pygame.draw.circle(s, (150, 144, 136), (c, c), r + 2)
    for i in range(8):
        a = i * math.pi / 4 + 0.2
        pygame.draw.line(s, (110, 105, 100), (c + (r - 1) * math.cos(a), c + (r - 1) * math.sin(a)),
                         (c + (r + 2) * math.cos(a), c + (r + 2) * math.sin(a)), 1)
    shade_ball(s, c, c, r + 3, r + 3, 0.6)


def lit(size, draw, cx, cy, rx, ry, strength=1.0):
    """Draw one part on its own layer and light it so it looks round/3D."""
    part = pygame.Surface(size, pygame.SRCALPHA)
    draw(part)
    shade_ball(part, cx, cy, rx, ry, strength)
    return part


def body_outline(w, profile, top=2):
    """Points around a long body pointing up: profile = [(y, half width), ...]."""
    c = w / 2
    left = [(c - hw, y) for y, hw in profile]
    right = [(c + hw, y) for y, hw in reversed(profile)]
    return [(c, top)] + left + right


def make_tower_sprite(key, font):
    """Top-down 3D-looking tower art (water towers face up and get rotated in game)."""
    if key in WATER_KEYS:
        return make_water_sprite(key)
    size = (44, 44)
    s = pygame.Surface(size, pygame.SRCALPHA)
    c = 22
    r = TOWER_R
    draw_stone_base(s, c, r)
    if key == "dart":   # wooden platform with a bundle of darts
        s.blit(lit(size, lambda p: pygame.draw.circle(p, (150, 100, 55), (c, c), 14), c, c, 14, 14), (0, 0))
        for x in range(c - 10, c + 11, 5):
            pygame.draw.line(s, (110, 70, 35), (x, c - 12), (x, c + 12), 1)
        pygame.draw.circle(s, (80, 50, 25), (c, c), 14, 2)
        for i, (dx, dy) in enumerate(((-9, 5), (-7, 8), (-11, 8))):
            pygame.draw.line(s, (90, 60, 30), (c + dx, c + dy), (c + dx + 3, c + dy - 7), 2)
            pygame.draw.circle(s, (220, 60, 60), (c + dx, c + dy), 2)
    elif key == "tack":   # spiked steel dome
        for i in range(8):
            a = i * math.pi / 4 + math.pi / 8
            tip = (c + 19 * math.cos(a), c + 19 * math.sin(a))
            l = (c + 12 * math.cos(a - 0.3), c + 12 * math.sin(a - 0.3))
            rr = (c + 12 * math.cos(a + 0.3), c + 12 * math.sin(a + 0.3))
            pygame.draw.polygon(s, (205, 210, 220), [tip, l, rr])
            pygame.draw.polygon(s, (110, 115, 130), [tip, l, rr], 1)
        s.blit(lit(size, lambda p: pygame.draw.circle(p, (165, 170, 185), (c, c), 12), c, c, 12, 12, 1.3), (0, 0))
        pygame.draw.circle(s, (90, 95, 110), (c, c), 12, 1)
        pygame.draw.circle(s, (70, 75, 90), (c, c), 3)
    elif key == "boom":   # wooden platform with two crossed boomerangs
        s.blit(lit(size, lambda p: pygame.draw.circle(p, (185, 130, 70), (c, c), 14), c, c, 14, 14), (0, 0))
        pygame.draw.circle(s, (110, 70, 30), (c, c), 14, 2)
        for flip in (1, -1):
            pts = [(c - 10 * flip, c - 8), (c, c + 2), (c + 10 * flip, c - 8)]
            pygame.draw.lines(s, (120, 60, 20), False, [(x + 1, y + 1) for x, y in pts], 6)
            pygame.draw.lines(s, (245, 155, 55), False, pts, 5)
            pygame.draw.lines(s, (255, 210, 130), False, [(x, y - 1) for x, y in pts], 1)
    elif key == "bomb":   # heavy iron mortar with rivets
        s.blit(lit(size, lambda p: pygame.draw.circle(p, (75, 75, 88), (c, c), 15), c, c, 15, 15, 1.2), (0, 0))
        for i in range(8):
            a = i * math.pi / 4
            pygame.draw.circle(s, (150, 150, 165), (int(c + 12 * math.cos(a)), int(c + 12 * math.sin(a))), 1)
        pygame.draw.circle(s, (25, 25, 30), (c, c), 15, 2)
    elif key == "glue":   # green glue tank with a hazard ring
        s.blit(lit(size, lambda p: pygame.draw.circle(p, (110, 185, 70), (c, c), 14), c, c, 14, 14, 1.2), (0, 0))
        for i in range(12):
            a1, a2 = i * math.pi / 6, i * math.pi / 6 + math.pi / 6
            pygame.draw.arc(s, (240, 210, 40) if i % 2 else (30, 30, 30), (c - 15, c - 15, 30, 30), a1, a2, 3)
        pygame.draw.circle(s, (190, 240, 110), (c - 4, c + 5), 3)
        pygame.draw.circle(s, (190, 240, 110), (c + 5, c + 7), 2)
    elif key == "frost":   # cluster of ice crystals
        for i in range(6):
            a = i * math.pi / 3 + 0.3
            tip = (c + 16 * math.cos(a), c + 16 * math.sin(a))
            l = (c + 6 * math.cos(a - 0.5), c + 6 * math.sin(a - 0.5))
            rr = (c + 6 * math.cos(a + 0.5), c + 6 * math.sin(a + 0.5))
            pygame.draw.polygon(s, (150, 215, 250), [tip, l, (c, c), rr])
            pygame.draw.polygon(s, (230, 250, 255), [tip, l, (c, c)])
            pygame.draw.polygon(s, (70, 140, 200), [tip, l, (c, c), rr], 1)
        s.blit(lit(size, lambda p: pygame.draw.circle(p, (200, 240, 255), (c, c), 6), c, c, 6, 6), (0, 0))
    elif key == "ninja":   # pagoda roof seen from above
        for rad, col in ((16, (150, 30, 30)), (11, (190, 50, 45)), (6, (215, 70, 60))):
            pts = [(c + rad * math.cos(i * math.pi / 4 + math.pi / 8), c + rad * math.sin(i * math.pi / 4 + math.pi / 8))
                   for i in range(8)]
            s.blit(lit(size, lambda p, pts=pts, col=col: pygame.draw.polygon(p, col, pts), c, c, rad, rad, 0.9), (0, 0))
            pygame.draw.polygon(s, (90, 15, 15), pts, 1)
        for i in range(8):
            a = i * math.pi / 4 + math.pi / 8
            pygame.draw.line(s, (110, 20, 20), (c, c), (c + 16 * math.cos(a), c + 16 * math.sin(a)), 1)
        pygame.draw.circle(s, (240, 200, 60), (c, c), 3)
    elif key == "sniper":   # sandbag nest
        pygame.draw.circle(s, (70, 85, 50), (c, c), 13)
        for i in range(8):
            a = i * math.pi / 4
            x, y = c + 13 * math.cos(a), c + 13 * math.sin(a)
            s.blit(lit(size, lambda p, x=x, y=y: pygame.draw.ellipse(p, (200, 180, 130), (x - 6, y - 4, 12, 8)),
                       x, y, 6, 4), (0, 0))
    elif key == "wizard":   # stone tower top with a glowing magic circle
        s.blit(lit(size, lambda p: pygame.draw.circle(p, (125, 115, 150), (c, c), 15), c, c, 15, 15), (0, 0))
        pygame.draw.circle(s, (180, 110, 255), (c, c), 11, 2)
        star = [(c + (10 if i % 2 == 0 else 4) * math.cos(i * math.pi / 5 - math.pi / 2),
                 c + (10 if i % 2 == 0 else 4) * math.sin(i * math.pi / 5 - math.pi / 2)) for i in range(10)]
        pygame.draw.polygon(s, (220, 170, 255), star)
        pygame.draw.circle(s, (255, 240, 255), (c, c), 3)
    elif key == "spike":   # steel spike press
        for i in range(4):
            a = i * math.pi / 2 + math.pi / 4
            for off in (-0.35, 0.35):
                tip = (c + 19 * math.cos(a + off), c + 19 * math.sin(a + off))
                pygame.draw.polygon(s, (200, 200, 215), [tip, (c + 10 * math.cos(a + off - 0.3), c + 10 * math.sin(a + off - 0.3)),
                                                         (c + 10 * math.cos(a + off + 0.3), c + 10 * math.sin(a + off + 0.3))])
        s.blit(lit(size, lambda p: pygame.draw.rect(p, (130, 135, 150), (c - 12, c - 12, 24, 24), border_radius=4),
                   c, c, 15, 15, 0.8), (0, 0))
        pygame.draw.rect(s, (60, 60, 75), (c - 12, c - 12, 24, 24), 2, border_radius=4)
        s.blit(lit(size, lambda p: pygame.draw.circle(p, (235, 165, 60), (c, c), 6), c, c, 6, 6), (0, 0))
    elif key == "village":   # thatched hut roof with a chimney
        s.blit(lit(size, lambda p: pygame.draw.circle(p, (215, 175, 85), (c, c), 16), c, c, 16, 16, 1.2), (0, 0))
        for i in range(16):
            a = i * math.pi / 8
            pygame.draw.line(s, (160, 120, 45), (c + 4 * math.cos(a), c + 4 * math.sin(a)),
                             (c + 15 * math.cos(a), c + 15 * math.sin(a)), 1)
        pygame.draw.circle(s, (120, 85, 30), (c, c), 16, 2)
        pygame.draw.rect(s, (130, 70, 50), (c + 4, c - 9, 5, 5))
        pygame.draw.line(s, (90, 60, 30), (c - 6, c - 4), (c - 6, c - 14), 1)
        pygame.draw.polygon(s, (220, 50, 50), [(c - 6, c - 14), (c + 1, c - 12), (c - 6, c - 10)])
    elif key == "super":   # glowing energy core
        s.blit(lit(size, lambda p: pygame.draw.circle(p, (60, 110, 235), (c, c), 15), c, c, 15, 15, 1.4), (0, 0))
        pygame.draw.circle(s, (255, 205, 60), (c, c), 15, 2)
        star = [(c + (9 if i % 2 == 0 else 4) * math.cos(i * math.pi / 5 - math.pi / 2),
                 c + (9 if i % 2 == 0 else 4) * math.sin(i * math.pi / 5 - math.pi / 2)) for i in range(10)]
        pygame.draw.polygon(s, (255, 230, 90), star)
    elif key == "mine":   # mine shaft with gold and a little cart
        pygame.draw.rect(s, (115, 80, 45), (c - 12, c - 12, 24, 24), border_radius=3)
        pygame.draw.rect(s, (25, 20, 15), (c - 8, c - 8, 16, 16))
        pygame.draw.rect(s, (70, 45, 20), (c - 12, c - 12, 24, 24), 2, border_radius=3)
        for x, y in ((c - 4, c - 3), (c + 3, c + 2), (c - 1, c + 4)):
            s.blit(lit(size, lambda p, x=x, y=y: pygame.draw.circle(p, (245, 200, 50), (x, y), 3), x, y, 3, 3), (0, 0))
        pygame.draw.rect(s, (90, 95, 105), (c + 5, c + 9, 10, 6), border_radius=2)
    return s


def make_water_sprite(key):
    """Water towers seen from above, facing up (rotated toward their target in game)."""
    w = 48
    size = (w, w)
    s = pygame.Surface(size, pygame.SRCALPHA)
    c = w // 2
    for rr, col in ((22, (60, 120, 190, 70)), (17, (90, 150, 210, 60))):   # dark water under it
        pygame.draw.ellipse(s, col, (c - rr // 2 - 2, c - rr, rr + 4, rr * 2))
    if key == "shark":
        prof = [(6, 4), (11, 7), (18, 9), (24, 9), (30, 7), (36, 4), (40, 2)]
        body = body_outline(w, prof, top=3)
        for side in (-1, 1):   # pectoral fins
            pygame.draw.polygon(s, (75, 95, 120), [(c + side * 7, 19), (c + side * 18, 29), (c + side * 6, 26)])
        pygame.draw.polygon(s, (75, 95, 120), [(c, 38), (c - 8, 46), (c, 42), (c + 8, 46)])   # tail
        s.blit(lit(size, lambda p: pygame.draw.polygon(p, (110, 135, 160), body), c, 22, 10, 20, 1.1), (0, 0))
        pygame.draw.polygon(s, (60, 75, 95), body, 1)
        pygame.draw.polygon(s, (65, 80, 100), [(c, 17), (c - 3, 27), (c + 3, 27)])   # dorsal fin
        pygame.draw.line(s, (160, 180, 200), (c, 18), (c - 2, 26), 1)
        for side in (-1, 1):
            pygame.draw.circle(s, (15, 15, 20), (c + side * 4, 9), 2)
            pygame.draw.line(s, (90, 105, 125), (c + side * 6, 14), (c + side * 7, 17), 1)   # gills
    elif key == "pirate":
        hull = [(c, 2), (c + 9, 12), (c + 11, 24), (c + 10, 40), (c + 7, 45), (c - 7, 45), (c - 10, 40), (c - 11, 24), (c - 9, 12)]
        for y in (17, 25, 33):   # cannons poking out the sides
            pygame.draw.rect(s, (25, 25, 30), (c - 14, y, 5, 3))
            pygame.draw.rect(s, (25, 25, 30), (c + 9, y, 5, 3))
        s.blit(lit(size, lambda p: pygame.draw.polygon(p, (130, 82, 40), hull), c, 24, 12, 22, 0.9), (0, 0))
        deck = [(c, 6), (c + 7, 13), (c + 8, 24), (c + 7, 39), (c - 7, 39), (c - 8, 24), (c - 7, 13)]
        pygame.draw.polygon(s, (185, 140, 85), deck)
        for x in range(c - 6, c + 7, 3):
            pygame.draw.line(s, (150, 105, 60), (x, 10), (x, 38), 1)
        pygame.draw.polygon(s, (70, 40, 15), hull, 2)
        for y, half, h in ((9, 8, 5), (21, 15, 8), (31, 12, 6)):   # sails, bulging forward
            s.blit(lit(size, lambda p, y=y, half=half, h=h: pygame.draw.ellipse(p, (245, 240, 225), (c - half, y - h // 2, half * 2, h)),
                       c, y, half, h, 0.7), (0, 0))
            pygame.draw.line(s, (100, 70, 40), (c - half, y + 1), (c + half, y + 1), 1)
            pygame.draw.circle(s, (80, 50, 25), (c, y + 1), 2)
        pygame.draw.rect(s, (25, 25, 25), (c - 3, 41, 6, 5))
        pygame.draw.circle(s, WHITE, (c, 43), 1)
    elif key == "sub":
        s.blit(lit(size, lambda p: pygame.draw.ellipse(p, (230, 190, 55), (c - 8, 3, 16, 40)), c, 23, 8, 20, 1.2), (0, 0))
        pygame.draw.ellipse(s, (130, 100, 20), (c - 8, 3, 16, 40), 1)
        for side in (-1, 1):
            pygame.draw.rect(s, (200, 160, 45), (c + (3 if side > 0 else -11), 35, 8, 3), border_radius=1)
        s.blit(lit(size, lambda p: pygame.draw.rect(p, (205, 165, 45), (c - 4, 14, 8, 13), border_radius=4), c, 20, 5, 7), (0, 0))
        pygame.draw.circle(s, (60, 60, 70), (c, 16), 2)
        for y in (9, 32):
            pygame.draw.circle(s, (140, 210, 245), (c, y), 2)
        pygame.draw.line(s, (110, 110, 120), (c - 4, 45), (c + 4, 45), 2)   # propeller
        pygame.draw.line(s, (110, 110, 120), (c, 43), (c, 47), 2)
    return s


def make_hero_sprite(key):
    """Each hero is its own little character, seen from the front.
    The sprite is 52x62; the hero's feet are near the bottom middle."""
    W, H = 52, 62
    size = (W, H)
    s = pygame.Surface(size, pygame.SRCALPHA)
    cx = W // 2

    def head(skin, y=18, r=7):
        s.blit(lit(size, lambda p: pygame.draw.circle(p, skin, (cx, y), r), cx, y, r, r, 0.8), (0, 0))

    if key == "knight":   # armored knight: cape, shield, glowing sword
        pygame.draw.polygon(s, (40, 70, 160), [(cx - 8, 24), (cx + 8, 24), (cx + 13, 54), (cx - 13, 54)])
        for x in (cx - 6, cx + 1):
            pygame.draw.rect(s, (120, 125, 140), (x, 44, 5, 10))
            pygame.draw.rect(s, (60, 60, 70), (x - 1, 52, 7, 4), border_radius=2)
        s.blit(lit(size, lambda p: pygame.draw.rect(p, (185, 190, 205), (cx - 9, 25, 18, 21), border_radius=6),
                   cx, 34, 11, 12, 1.1), (0, 0))
        pygame.draw.rect(s, (110, 80, 40), (cx - 9, 41, 18, 3))
        pygame.draw.line(s, (255, 240, 150), (cx + 14, 42), (cx + 20, 8), 4)   # sword glow
        pygame.draw.line(s, (200, 240, 255), (cx + 14, 42), (cx + 20, 8), 2)
        pygame.draw.line(s, (120, 90, 40), (cx + 10, 40), (cx + 18, 42), 3)
        shield = [(cx - 19, 28), (cx - 7, 28), (cx - 7, 41), (cx - 13, 47), (cx - 19, 41)]
        s.blit(lit(size, lambda p: pygame.draw.polygon(p, (50, 90, 190), shield), cx - 13, 37, 7, 10), (0, 0))
        pygame.draw.polygon(s, (220, 190, 70), shield, 2)
        pygame.draw.polygon(s, (255, 220, 60), [(cx - 12, 31), (cx - 15, 38), (cx - 12, 38), (cx - 14, 44), (cx - 10, 36), (cx - 13, 36)])
        s.blit(lit(size, lambda p: pygame.draw.circle(p, (190, 195, 210), (cx, 17), 9), cx, 17, 9, 9, 1.1), (0, 0))
        pygame.draw.rect(s, (35, 40, 55), (cx - 6, 16, 12, 3), border_radius=1)
        pygame.draw.line(s, (35, 40, 55), (cx, 16), (cx, 23), 2)
        pygame.draw.polygon(s, (255, 215, 60), [(cx - 1, 2), (cx + 5, 8), (cx + 1, 8), (cx + 3, 12), (cx - 3, 6), (cx + 1, 6)])
    elif key == "witch":   # teal dress, wide pointy hat, wind staff
        pygame.draw.line(s, (110, 70, 35), (cx + 15, 56), (cx + 17, 14), 3)
        for i, col in enumerate(((150, 240, 230), (220, 255, 250), (110, 210, 220))):
            pygame.draw.circle(s, col, (cx + 17 + int(4 * math.cos(i * 2.1)), 11 + int(3 * math.sin(i * 2.1))), 5 - i, 2)
        dress = [(cx - 7, 26), (cx + 7, 26), (cx + 14, 56), (cx - 14, 56)]
        s.blit(lit(size, lambda p: pygame.draw.polygon(p, (50, 160, 150), dress), cx, 41, 14, 16), (0, 0))
        pygame.draw.rect(s, (110, 50, 140), (cx - 8, 31, 16, 3))
        head((235, 195, 165), 20)
        pygame.draw.circle(s, (40, 30, 30), (cx - 3, 20), 1)
        pygame.draw.circle(s, (40, 30, 30), (cx + 3, 20), 1)
        pygame.draw.polygon(s, (70, 30, 90), [(cx - 8, 18), (cx - 10, 28), (cx - 6, 22)])   # hair
        pygame.draw.polygon(s, (70, 30, 90), [(cx + 8, 18), (cx + 10, 28), (cx + 6, 22)])
        s.blit(lit(size, lambda p: pygame.draw.ellipse(p, (30, 75, 85), (cx - 15, 11, 30, 7)), cx, 14, 15, 4), (0, 0))
        s.blit(lit(size, lambda p: pygame.draw.polygon(p, (35, 85, 95), [(cx - 7, 14), (cx + 7, 14), (cx + 6, 0)]),
                   cx, 8, 7, 8), (0, 0))
        pygame.draw.rect(s, (200, 170, 60), (cx - 7, 11, 14, 2))
    elif key == "gear":   # engineer: orange jumpsuit, goggles, bolt gun
        for x in (cx - 6, cx + 1):
            pygame.draw.rect(s, (200, 110, 40), (x, 44, 5, 9))
            pygame.draw.rect(s, (40, 35, 30), (x - 1, 52, 7, 4), border_radius=2)
        s.blit(lit(size, lambda p: pygame.draw.rect(p, (235, 135, 45), (cx - 9, 26, 18, 20), border_radius=5),
                   cx, 35, 11, 12), (0, 0))
        pygame.draw.rect(s, (100, 65, 30), (cx - 9, 40, 18, 4))
        pygame.draw.rect(s, (240, 200, 60), (cx - 2, 40, 4, 4))
        s.blit(lit(size, lambda p: pygame.draw.rect(p, (120, 125, 140), (cx + 4, 31, 20, 7), border_radius=2),
                   cx + 14, 34, 10, 4), (0, 0))
        for x in (cx + 9, cx + 13, cx + 17):
            pygame.draw.line(s, (210, 120, 50), (x, 30), (x, 38), 2)
        pygame.draw.circle(s, (130, 220, 255), (cx + 24, 34), 2)
        head((205, 155, 115))
        pygame.draw.rect(s, (90, 60, 35), (cx - 7, 10, 14, 4), border_radius=2)   # hair
        pygame.draw.line(s, (50, 50, 55), (cx - 8, 17), (cx + 8, 17), 2)
        for gx in (cx - 4, cx + 4):
            pygame.draw.circle(s, (60, 60, 70), (gx, 17), 4)
            pygame.draw.circle(s, (150, 220, 255), (gx, 17), 2)
    elif key == "cipher":   # a friendly robot with a screen face
        for x in (cx - 6, cx + 2):
            pygame.draw.rect(s, (120, 125, 140), (x, 45, 5, 8))
            pygame.draw.ellipse(s, (120, 200, 255), (x - 1, 53, 7, 4))   # hover jets
        for side in (-1, 1):
            pygame.draw.line(s, (130, 135, 150), (cx + side * 11, 29), (cx + side * 15, 40), 3)
            pygame.draw.circle(s, (90, 95, 110), (cx + side * 11, 29), 3)
            pygame.draw.circle(s, (90, 95, 110), (cx + side * 15, 41), 3)
        s.blit(lit(size, lambda p: pygame.draw.rect(p, (115, 135, 175), (cx - 11, 25, 22, 21), border_radius=4),
                   cx, 35, 13, 12, 1.1), (0, 0))
        pygame.draw.rect(s, (40, 45, 60), (cx - 6, 29, 12, 7), border_radius=2)
        for i, col in enumerate(((90, 255, 120), (255, 210, 60), (255, 80, 80))):
            pygame.draw.circle(s, col, (cx - 4 + i * 4, 40), 1)
        pygame.draw.line(s, (90, 95, 110), (cx, 7), (cx, 2), 2)   # antenna
        pygame.draw.circle(s, (255, 70, 70), (cx, 2), 2)
        s.blit(lit(size, lambda p: pygame.draw.rect(p, (150, 160, 190), (cx - 10, 7, 20, 17), border_radius=5),
                   cx, 15, 12, 10, 1.1), (0, 0))
        pygame.draw.rect(s, (20, 30, 40), (cx - 7, 10, 14, 10), border_radius=3)
        pygame.draw.rect(s, (90, 255, 140), (cx - 5, 13, 3, 3))
        pygame.draw.rect(s, (90, 255, 140), (cx + 2, 13, 3, 3))
        pygame.draw.line(s, (90, 255, 140), (cx - 3, 18), (cx + 3, 18), 1)
    elif key == "nova":   # a monk floating cross-legged, holding a glowing orb
        glow = pygame.Surface(size, pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (200, 120, 255, 70), (cx - 18, 50, 36, 10))
        s.blit(glow, (0, 0))
        s.blit(lit(size, lambda p: pygame.draw.ellipse(p, (220, 120, 40), (cx - 16, 38, 32, 13)), cx, 44, 16, 7), (0, 0))
        torso = [(cx - 8, 24), (cx + 8, 24), (cx + 11, 42), (cx - 11, 42)]
        s.blit(lit(size, lambda p: pygame.draw.polygon(p, (230, 130, 45), torso), cx, 33, 11, 10), (0, 0))
        pygame.draw.line(s, (140, 40, 50), (cx - 8, 25), (cx + 9, 41), 4)   # sash
        head((180, 125, 90), 17, 8)
        pygame.draw.arc(s, (60, 40, 30), (cx - 6, 16, 5, 4), math.pi, 2 * math.pi, 1)   # closed eyes
        pygame.draw.arc(s, (60, 40, 30), (cx + 1, 16, 5, 4), math.pi, 2 * math.pi, 1)
        pygame.draw.circle(s, (200, 140, 255), (cx, 12), 1)
        pygame.draw.circle(s, (240, 190, 255), (cx, 36), 5)
        pygame.draw.circle(s, (255, 250, 255), (cx, 36), 3)
        for side in (-1, 1):
            pygame.draw.circle(s, (180, 125, 90), (cx + side * 5, 38), 3)
    return s


def finish_tower_sprite(s):
    """A soft shine on the top-left of the tower body."""
    shine = pygame.Surface(s.get_size(), pygame.SRCALPHA)
    pygame.draw.arc(shine, (255, 255, 255, 120), (6, 6, 32, 32), math.radians(100), math.radians(170), 3)
    s.blit(shine, (0, 0))
    return s


BARRELS = {   # (length, width, color) of the part that points at balloons
    "dart": (22, 5, (70, 45, 25)),
    "bomb": (19, 10, (30, 30, 34)),
    "sniper": (28, 4, (40, 50, 25)),
    "glue": (18, 7, (60, 100, 30)),
    "super": (20, 6, (230, 200, 60)),
}


# =====================================================================
# One game (a map being played)
# =====================================================================
class Game:
    def __init__(self, app, map_idx, diff_idx):
        self.app = app
        self.map_idx, self.diff_idx = map_idx, diff_idx
        self.mp = MAPS[map_idx]
        self.diff = DIFFICULTIES[diff_idx]
        self.paths = [Path([(x, y + MAP_Y) for x, y in pts]) for pts in self.mp["paths"]]
        self.water = [(x, y + MAP_Y, r) for x, y, r in self.mp.get("water", [])]
        self.blocked = self.water + [(x, y + MAP_Y, r) for x, y, r in self.mp.get("rocks", [])]
        self.reset()

    def reset(self):
        self.balloons = []
        self.towers = []
        self.projs = []
        self.spikes = []            # spike piles: [x, y, pierce left, life, tower]
        self.fx = []                # visual effects
        self.money = self.diff["money"] + self.mp.get("extra_money", 0)   # two-lane maps pay more
        self.lives = self.diff["lives"]
        self.round = 0              # the round being played / last played
        self.active = False         # is a round running?
        self.queue = []
        self.qi = 0
        self.rtime = 0.0
        self.speed = 1              # 1x / 2x / 3x
        self.rally_t = 0.0          # Rally Cry: all towers faster
        self.rally_mult = 0.5
        self.sandbox = bool(self.diff.get("sandbox"))
        self.sb = dict(kind=BALLOON_ORDER.index("ceramic"), flags=0, amount=2, round=25)
        self.sb_spawns = []         # sandbox balloons waiting to come out: [seconds, name, flags]
        self.ab_idx = 0             # which ability is picked in the ability bar
        self.auto = bool(self.app.save.get("auto_start"))
        self.auto_wait = 0.0        # countdown before an auto-started round
        self.cx, self.cy = 240.0, MAP_Y + 240.0   # cursor
        self.move_t = 0.0
        self.mode = "normal"        # normal / place / menu
        self.shop = 0
        self.menu = 0
        self.sel = None
        self.toast_text, self.toast_t = "", 0.0
        self.overlay = None         # None / pause / over / win
        self.over_idx = 0
        self.won = False
        self.next_id = 1
        self.spawned = 0            # used to take turns between tracks
        self.hp_mult = 1.0
        self.grid = {}

    # ---------------------------------------------------------- helpers
    def cost(self, base):
        return round_cost(base, self.diff["cost"])

    def discount_at(self, x, y, skip=None):
        """Villages with Trade Post make things cheaper inside their circle."""
        best = 0.0
        for v in self.towers:
            if v.key == "village" and v is not skip and v.s["discount"]:
                if (v.x - x) ** 2 + (v.y - y) ** 2 <= v.s["range"] ** 2:
                    best = max(best, v.s["discount"])
        return best

    def place_cost(self, tt, x, y):
        return self.cost(tt["cost"] * (1 - self.discount_at(x, y)))

    def upgrade_cost(self, t, p):
        return self.cost(t.t["paths"][p][t.levels[p]][1] * (1 - self.discount_at(t.x, t.y, t)))

    def refresh_buffs(self):
        """Recalculate every tower's stats, adding boosts from nearby villages."""
        for t in self.towers:   # villages must be up to date before they boost others
            t.recalc()
        villages = [v for v in self.towers if v.key == "village"]
        for t in self.towers:
            if t.key in ("village", "mine"):
                continue
            boost, radar, drums, rune = 0.0, False, 0.0, False
            for v in villages:
                vs = v.s
                if (v.x - t.x) ** 2 + (v.y - t.y) ** 2 <= vs["range"] ** 2:
                    boost = max(boost, vs["boost"])
                    radar = radar or vs["radar"]
                    drums = max(drums, vs["drums"])
                    rune = rune or vs["rune"]
            ts = t.s
            if boost and 0 < ts.get("range", 0) < 600:
                ts["range"] = ts["range"] * (1 + boost)
            if radar:
                ts["camo"] = True
            if drums and "rate" in ts:
                ts["rate"] *= 1 - drums
            if rune and ts.get("dtype") in ("sharp", "explode"):
                ts["dtype"] = "normal"

    def toast(self, text, secs=1.6):
        self.toast_text, self.toast_t = text, secs

    def tower_at(self, x, y):
        for t in self.towers:
            if (t.x - x) ** 2 + (t.y - y) ** 2 <= (TOWER_R + 4) ** 2:
                return t
        return None

    def on_water(self, x, y):
        return any((wx - x) ** 2 + (wy - y) ** 2 <= (wr - 10) ** 2 for wx, wy, wr in self.water)

    def can_place(self, x, y, water=False):
        """Land towers can't go on water; water towers must go on water."""
        if water:
            if not self.on_water(x, y):
                return False
            for t in self.towers:
                if (t.x - x) ** 2 + (t.y - y) ** 2 < (TOWER_R * 2) ** 2:
                    return False
            return True
        if not (TOWER_R <= x <= SCREEN_W - TOWER_R and MAP_Y + TOWER_R <= y <= MAP_Y + MAP_H - TOWER_R):
            return False
        for path in self.paths:
            if path.distance_to(x, y) < PATH_W / 2 + TOWER_R - 2:
                return False
        for bx, by, br in self.blocked:
            if (bx - x) ** 2 + (by - y) ** 2 < (br + TOWER_R - 6) ** 2:
                return False
        for t in self.towers:
            if (t.x - x) ** 2 + (t.y - y) ** 2 < (TOWER_R * 2) ** 2:
                return False
        return True

    def spawn_balloon(self, name, dist, camo, seg=0, path=None, regrow=None, fort=False):
        if path is None:   # a new balloon: take turns between the tracks
            path = self.paths[self.spawned % len(self.paths)]
            self.spawned += 1
        camo = camo or BALLOON_TYPES[name].get("always_camo", False)
        b = Balloon(name, max(0.0, dist), camo, self.next_id, self.hp_mult, path, regrow, fort)
        self.next_id += 1
        b.x, b.y, b.seg = path.pos(b.dist, seg)
        self.balloons.append(b)
        return b

    def add_fx(self, kind, x, y, dur, data=None):
        if len(self.fx) > 90:
            self.fx.pop(0)
        self.fx.append([kind, x, y, 0.0, dur, data])

    def check_hero_levels(self):
        for t in self.towers:
            if t.hero and t.xp_level() != t.hero_level:
                t.hero_level = t.xp_level()
                self.refresh_buffs()
                self.toast("%s reached level %d!" % (t.t["name"], t.hero_level), 1.8)
                self.add_fx("ring", t.x, t.y, 0.5, (TOWER_R + 14, (255, 215, 80)))
                self.app.sounds.play("upgrade")

    # ---------------------------------------------------------- saving
    def snapshot(self):
        """Everything needed to continue this game later (saved between rounds)."""
        return dict(map=self.map_idx, diff=self.diff_idx, round=self.round, money=self.money,
                    lives=self.lives, won=self.won,
                    towers=[dict(key=t.key, x=t.x, y=t.y, levels=t.levels, target=t.target_mode,
                                 curve=t.curve, spent=t.spent, pops=t.pops, xp=t.xp,
                                 dmg=t.dmg_done) for t in self.towers])

    def restore(self, snap):
        self.round, self.money, self.lives, self.won = snap["round"], snap["money"], snap["lives"], snap["won"]
        types = {tt["key"]: tt for tt in SHOP}
        for d in snap["towers"]:
            if d["key"] not in types:
                continue
            t = Tower(types[d["key"]], d["x"], d["y"], d["spent"])
            t.levels = list(d["levels"])
            t.target_mode, t.curve, t.pops, t.xp = d["target"], d["curve"], d["pops"], d["xp"]
            t.dmg_done = d.get("dmg", 0)
            if t.hero:
                t.hero_level = t.xp_level()
            self.towers.append(t)
        self.refresh_buffs()

    # ---------------------------------------------------------- rounds
    def start_round(self):
        self.round += 1
        groups = ROUNDS[self.round - 1] if self.round <= len(ROUNDS) else freeplay_round(self.round)
        q = []
        for g in groups:
            name, count, spacing, delay = g[:4]
            flags = g[4] if len(g) > 4 else ""   # True = camo, or letters: c=camo r=regrow f=fortified
            camo = flags is True or (isinstance(flags, str) and "c" in flags)
            regrow = name if isinstance(flags, str) and "r" in flags else None
            fort = isinstance(flags, str) and "f" in flags
            for i in range(count):
                q.append((delay + i * spacing, name, (camo, regrow, fort)))
        q.sort(key=lambda e: e[0])
        self.queue, self.qi, self.rtime = q, 0, 0.0
        # big balloons get tougher late: +2% per round after 80, +5% per round after 150
        self.hp_mult = 1.0 + max(0, self.round - 80) * 0.02 + max(0, self.round - FINAL_ROUND) * 0.03
        self.active = True
        self.auto_wait = 0.0

    def end_round(self):
        self.active = False
        bonus = int((120 + 3 * self.round) * self.mp.get("bonus_mult", 1))
        income = 0
        lives = 0
        for t in self.towers:
            if t.s.get("income"):
                pay = int(t.s["income"] * t.s.get("mult", 1))
                income += pay
                lives += t.s.get("lives", 0)
                self.add_fx("text", t.x, t.y - 20, 1.2, "+$%d" % pay)
        self.money += bonus + income
        for t in self.towers:   # heroes learn from every round, too
            if t.hero:
                t.xp += 30 + 3 * self.round
        self.check_hero_levels()
        self.lives += lives
        if not self.sandbox:   # sandbox games don't count or overwrite your saved game
            self.app.record_best(self.map_idx, self.diff_idx, self.round)
            self.app.save_resume(self.snapshot())
        self.toast("Round %d done! +$%d" % (self.round, bonus + income))
        if self.round == WIN_ROUND and not self.won and not self.sandbox:
            self.won = True
            self.overlay, self.over_idx = "win", 0
        elif self.round == FINAL_ROUND and not self.sandbox:
            self.overlay, self.over_idx = "champion", 0
        if self.auto:
            self.auto_wait = AUTO_START_DELAY

    # ---------------------------------------------------------- damage
    def damage(self, b, dmg, dtype, proj=None, tower=None):
        if not b.alive:
            return
        if dtype in b.info["immune"]:
            self.add_fx("clink", b.x, b.y, 0.15)
            return
        if tower:   # count the damage that actually landed (not overkill)
            tower.dmg_done += min(dmg, max(0, b.hp))
        b.hp -= dmg
        if b.hp > 0:
            return
        leftover = -b.hp
        b.alive = False
        self.money += 1
        if tower:
            tower.pops += 1
            if tower.hero:
                tower.xp += 1
        self.add_fx("pop", b.x, b.y, 0.32, (b.info["color"], b.id))
        self.app.sounds.play("pop")
        kids = []
        for i, child in enumerate(b.info["children"]):
            nb = self.spawn_balloon(child, b.dist - i * 9, b.camo, b.seg, b.path, b.regrow)
            kids.append(nb)
            if proj:
                proj.hit.add(nb.id)
        if leftover > 0 and kids:
            self.damage(kids[0], leftover, dtype, proj, tower)

    def rbe_left(self, b):
        return int(math.ceil(b.hp)) + sum(RBE[c] for c in b.info["children"])

    # ---------------------------------------------------------- grid
    def build_grid(self):
        g = {}
        for b in self.balloons:
            if b.alive:
                k = (int(b.x) // CELL, int(b.y) // CELL)
                lst = g.get(k)
                if lst is None:
                    g[k] = [b]
                else:
                    lst.append(b)
        self.grid = g

    def query(self, x, y, r):
        r += 44   # biggest balloon radius
        out = []
        g = self.grid
        for gx in range(int(x - r) // CELL, int(x + r) // CELL + 1):
            for gy in range(int(y - r) // CELL, int(y + r) // CELL + 1):
                lst = g.get((gx, gy))
                if lst:
                    out.extend(lst)
        return out

    # ---------------------------------------------------------- towers
    def find_target(self, t, rng=None):
        s = t.s
        rng = s["range"] if rng is None else rng
        mode = TARGET_MODES[t.target_mode]
        cands = self.balloons if rng > 600 else self.query(t.x, t.y, rng)
        best, bestv = None, None
        camo_ok = s.get("camo", False)
        for b in cands:
            if not b.alive or (b.camo and not camo_ok):
                continue
            if b.y < MAP_Y - 4 or b.x < -4 or b.x > SCREEN_W + 4 or b.y > MAP_Y + MAP_H + 4:
                continue
            dx, dy = b.x - t.x, b.y - t.y
            d2 = dx * dx + dy * dy
            rr = rng + b.r
            if d2 > rr * rr:
                continue
            left = b.path.total - b.dist   # distance still to go
            if mode == "First":
                v = -left
            elif mode == "Last":
                v = left
            elif mode == "Strong":
                v = b.rank * 100000 - left
            else:
                v = -d2
            if t.key == "glue" and (b.glue > 0.5 or (b.info.get("blimp") and not s["glue_blimp"])):
                v -= 1e9   # only if there's nothing better to glue
            if bestv is None or v > bestv:
                best, bestv = b, v
        return best

    def lead(self, t, b, speed):
        """Aim where the balloon will be when the shot arrives."""
        d = math.hypot(b.x - t.x, b.y - t.y)
        future = b.dist + b.speed_now * d / speed
        if future >= b.path.total:
            return b.x, b.y
        x, y, _ = b.path.pos(future, b.seg)
        return x, y

    def frost_pulse(self, t):
        s = t.s
        r = s["range"]
        hits = []
        for b in self.query(t.x, t.y, r):
            if not b.alive or (b.camo and not s.get("camo")):
                continue
            if (b.x - t.x) ** 2 + (b.y - t.y) ** 2 > (r + b.r) ** 2:
                continue
            if "cold" in b.info["immune"] and not s.get("freeze_white"):
                continue
            hits.append(b)
        if not hits:
            return False
        for b in hits:
            b.frozen = max(b.frozen, s["freeze"])
            if s.get("slow_after"):
                b.slow = max(b.slow, s["slow_after"])
            if s.get("dmg"):
                self.damage(b, s["dmg"], "normal", None, t)
        self.add_fx("ring", t.x, t.y, 0.35, (r, (190, 235, 255)))
        return True

    def rate_of(self, t):
        """Seconds between attacks, after ability speed-ups."""
        rate = t.s["rate"]
        if t.frenzy_t > 0:
            rate *= t.frenzy_rate
        if self.rally_t > 0:
            rate *= self.rally_mult
        return rate

    # ---------------------------------------------------------- abilities
    def ability_list(self):
        """Every unlocked ability on the field: [(tower, ability id)]."""
        return [(t, a) for t in self.towers for a in t.abilities()]

    def use_ability(self, t, aid):
        left = t.ab_cool.get(aid, 0)
        if left > 0:
            self.toast("%s ready in %ds" % (ABILITIES[aid][0], math.ceil(left)))
            self.app.sounds.play("error")
            return
        t.ab_cool[aid] = ABILITIES[aid][1]
        self.toast(ABILITIES[aid][0] + "!", 1.2)
        self.app.sounds.play("upgrade")
        s = t.s
        on_screen = [b for b in self.balloons if b.alive and MAP_Y - 10 < b.y < PANEL_Y + 10 and -10 < b.x < SCREEN_W + 10]
        P = s.get("ab_power", 1)   # 1 when unlocked at tier 4, 2 at tier 5
        if aid == "dart_storm":
            t.frenzy_t, t.frenzy_rate, t.frenzy_count = 6.0 + 4 * (P - 1), 0.25 / P, 3 + 2 * (P - 1)
        elif aid in ("overdrive", "feeding_frenzy"):
            t.frenzy_t, t.frenzy_rate, t.frenzy_count = 8.0 + 4 * (P - 1), 1 / (3 + P - 1), 0
        elif aid == "tack_nova":
            n = 48 * P
            for i in range(n):
                a = i * 2 * math.pi / n
                self.projs.append(Proj("tack", t.x, t.y, a, 420, 0.9, max(1, s["dmg"]) * P, 4 * P, s["dtype"], 5, t))
        elif aid == "rang_barrage":
            n = 12 * P
            for i in range(n):
                sign = 1 if i % 2 else -1
                pr = Proj("boom", t.x, t.y, i * 2 * math.pi / n, s["speed"], 2 * math.pi * 70 / s["speed"],
                          s["dmg"] * P, s["pierce"] + 4 * P, s["dtype"], 10, t)
                pr.turn = sign * s["speed"] / 70
                self.projs.append(pr)
        elif aid in ("carpet_bomb", "meteor", "depth_charge"):
            front = sorted(on_screen, key=lambda b: b.dist - b.path.total)
            if aid == "meteor":   # the strongest balloons (more meteors at tier 5)
                front = sorted(on_screen, key=lambda b: (-b.rank, b.dist - b.path.total))
            count, dmg, pierce, blast, dtype = {
                "carpet_bomb": (8, 4, 30, 70, "normal"),
                "meteor": (1, 20, 60, 95, "normal"),
                "depth_charge": (6, 5, 30, 60, "normal")}[aid]
            for b in front[:count * (P * 2 if aid == "meteor" else P)]:
                boom = Proj("bomb", b.x, b.y, 0, 0, 0, dmg * P, pierce * P, dtype, 0, t)
                boom.blast = blast + 15 * (P - 1)
                boom.bm = 3
                self.explode(boom)
        elif aid == "glue_rain":
            rain = dict(s, glue_blimp=True)
            for b in on_screen:
                self.apply_glue(b, rain, t)
                if P >= 2:
                    self.damage(b, 2, "normal", None, t)
        elif aid == "blizzard":
            for b in on_screen:
                b.frozen = max(b.frozen, 3.0 * P)
                if P >= 2:
                    self.damage(b, 3, "normal", None, t)
            self.add_fx("ring", SCREEN_W // 2, MAP_Y + MAP_H // 2, 0.5, (300, (200, 240, 255)))
        elif aid == "smoke_bomb":
            for b in on_screen:
                if not b.info.get("blimp"):
                    b.dist = max(0.0, b.dist - 90 * P)
                b.frozen = max(b.frozen, 1.5 * P)
        elif aid in ("cash_crate", "payday"):
            cash = {"cash_crate": (300, 1200), "payday": (600, 3000)}[aid][min(P, 2) - 1]
            self.money += cash
            self.add_fx("text", t.x, t.y - 20, 1.2, "+$%d" % cash)
        elif aid == "spike_carpet":
            self.make_spikes(t)   # makes sure the reachable spots are known
            for x, y in random.sample(t.spots[1], min(25 * P, len(t.spots[1]))):
                self.spikes.append([x, y, t.s["pierce"] * P, t.s["life"], t])
        elif aid == "rally_cry":
            self.rally_t = 8.0 + 4 * (P - 1)
            self.rally_mult = 0.5 if P == 1 else 0.4
        elif aid == "broadside":
            n = 16 * P
            for i in range(n):
                pr = Proj("cannon", t.x, t.y, i * 2 * math.pi / n, s["speed"], (s["range"] + 60) / s["speed"],
                          s["dmg"] * P, s["pierce"] + 2 * P, s["dtype"], 6, t)
                self.projs.append(pr)
        else:
            self.hero_ability(t, aid, on_screen)

    def hero_ability(self, t, aid, on_screen):
        lvl = t.hero_level
        front = sorted(on_screen, key=lambda b: b.dist - b.path.total)
        if aid == "thunder_strike" and front:
            self.lightning(t, front[0], 15, 3 + lvl // 5, "normal")
        elif aid in ("storm_blade", "overclock"):
            t.frenzy_t, t.frenzy_rate, t.frenzy_count = (10.0, 1 / 3, 0) if aid == "storm_blade" else (8.0, 1 / 3, 2)
        elif aid == "twister":
            for b in on_screen:
                if (b.x - t.x) ** 2 + (b.y - t.y) ** 2 <= 170 ** 2:
                    if not b.info.get("unstoppable"):
                        b.dist = max(0.0, b.dist - (40 if b.info.get("blimp") else 130))
            self.add_fx("ring", t.x, t.y, 0.4, (170, (200, 255, 240)))
        elif aid == "hurricane":
            for b in on_screen:
                b.slow = max(b.slow, 8.0)
                self.damage(b, 2, "normal", None, t)
        elif aid == "mega_mortar" and on_screen:
            target = sorted(on_screen, key=lambda b: (-b.rank, b.dist - b.path.total))[0]
            boom = Proj("bomb", target.x, target.y, 0, 0, 0, 12, 80, "explode", 0, t)
            boom.blast, boom.bm = 110, 3
            self.explode(boom)
        elif aid == "crypto_boost":
            cash = 200 + 30 * lvl
            self.money += cash
            self.add_fx("text", t.x, t.y - 20, 1.2, "+$%d" % cash)
        elif aid == "glitch_wave":
            for b in on_screen:
                b.camo = False
                b.regrow = None
                self.damage(b, 30 if b.info.get("blimp") else 1, "normal", None, t)
        elif aid == "mind_blast":
            for b in on_screen:
                if (b.x - t.x) ** 2 + (b.y - t.y) ** 2 <= 200 ** 2:
                    b.frozen = max(b.frozen, 1.0)
                    self.damage(b, 3, "normal", None, t)
            self.add_fx("ring", t.x, t.y, 0.4, (200, (220, 150, 255)))
        elif aid == "gravity_well":
            for b in front[:30]:
                if b.name not in ("titan", "colossus", "overlord"):
                    b.lift, b.lift_t, b.lift_by = (2.0 if b.info.get("blimp") else 4.0), 0.3, t

    def update_tower(self, t, dt):
        s = t.s
        t.flash = max(0.0, t.flash - dt)
        if t.key == "mine":
            return
        if s.get("breath"):
            t.cool2 -= dt
            if t.cool2 <= 0:
                ft = self.find_target(t, 100)
                t.cool2 = 0.12 if ft else 0.05
                if ft:
                    a = math.atan2(ft.y - t.y, ft.x - t.x) + random.uniform(-0.15, 0.15)
                    self.projs.append(Proj("fire", t.x, t.y, a, 320, 0.36, s.get("breath_dmg", 1), 2, "magic", 8, t))
        t.cool -= dt
        if t.cool > 0:
            return
        if t.key == "frost":
            t.cool = self.rate_of(t) if self.frost_pulse(t) else 0.1
            return
        if t.key == "village":
            return
        if t.key == "spike":
            if self.active:   # spikes are only made during a round
                t.cool = self.rate_of(t)
                self.make_spikes(t)
            else:
                t.cool = 0.0
            return
        tgt = self.find_target(t)
        if tgt is None:
            t.cool = 0.05
            return
        t.cool = self.rate_of(t)
        t.flash = 0.08
        if t.key == "dart" and s.get("spikeball"):
            ax, ay = self.lead(t, tgt, 330)
            t.angle = math.atan2(ay - t.y, ax - t.x)
            ball = Proj("spikeball", t.x + math.cos(t.angle) * 16, t.y + math.sin(t.angle) * 16, t.angle,
                        330, 8.0, s.get("ball_dmg", 2), s.get("ball_pierce", 40), "normal", 12, t)
            ball.bounces = s.get("ball_bounces", 1)
            ball.bm = s.get("blimp_mult", 1)
            self.projs.append(ball)
        elif t.key == "knight":   # sword slash: hits a group around the knight
            self.knight_slash(t, tgt)
        elif t.key == "nova":
            self.nova_lift(t)
        elif t.key == "shark":
            self.knight_slash(t, tgt, "chomp")
        elif t.key in ("dart", "ninja", "super", "glue", "witch", "gear", "cipher", "pirate", "sub"):
            kind = {"dart": "dart", "ninja": "star", "super": "laser", "glue": "glue",
                    "witch": "gust", "gear": "laser", "cipher": "zap", "pirate": "cannon",
                    "sub": "torpedo"}[t.key]
            ax, ay = self.lead(t, tgt, s["speed"])
            t.angle = math.atan2(ay - t.y, ax - t.x)
            n = max(s["count"], t.frenzy_count if t.frenzy_t > 0 else 0)
            for i in range(n):
                a = t.angle + (s["spread"] or 0.15) * (i - (n - 1) / 2)
                pr = Proj(kind, t.x + math.cos(a) * 16, t.y + math.sin(a) * 16, a, s["speed"],
                          (s["range"] + 40) / s["speed"], s.get("dmg", 0), s["pierce"], s.get("dtype"),
                          7 if kind == "glue" else 5, t)
                pr.homing = s.get("homing", False)
                pr.bm = s.get("blimp_mult", 1)
                pr.knock = s.get("knock", 0)
                self.projs.append(pr)
            if s.get("stun"):
                t.shots += 1
                if t.shots % 4 == 0:
                    self.stun_bomb(tgt.x, tgt.y, s["stun"])
        elif t.key == "boom":
            d = min(math.hypot(tgt.x - t.x, tgt.y - t.y), s["range"])
            rc = max(30.0, d / 2 + 6)          # radius of the curved flight
            t.angle = aim = math.atan2(tgt.y - t.y, tgt.x - t.x)
            for k in range(s["count"]):
                sign = t.curve if k == 0 else -t.curve   # 2nd boomerang curves the other way
                pr = Proj("boom", t.x, t.y, aim - sign * math.pi / 2, s["speed"],
                          2 * math.pi * rc / s["speed"], s["dmg"], s["pierce"], s["dtype"], 10, t)
                pr.turn = sign * s["speed"] / rc
                pr.knock = s["knock"]
                self.projs.append(pr)
        elif t.key == "tack":
            n = s["count"]
            for i in range(n):
                a = i * 2 * math.pi / n
                self.projs.append(Proj("tack", t.x, t.y, a, s["speed"], (s["range"] + 10) / s["speed"],
                                       s["dmg"], s["pierce"], s["dtype"], 5, t))
        elif t.key == "bomb":
            ax, ay = self.lead(t, tgt, s["speed"])
            t.angle = math.atan2(ay - t.y, ax - t.x)
            p = Proj("bomb", t.x, t.y, t.angle, s["speed"], (s["range"] + 30) / s["speed"],
                     s["dmg"], s["pierce"], s["dtype"], 8, t)
            p.blast, p.cluster, p.bm = s["blast"], s["cluster"], s["blimp_mult"]
            self.projs.append(p)
        elif t.key == "wizard":
            ax, ay = self.lead(t, tgt, s["speed"])
            a = math.atan2(ay - t.y, ax - t.x)
            p = Proj("bolt", t.x, t.y - 4, a, s["speed"], (s["range"] + 60) / s["speed"],
                     s["dmg"], s["pierce"], s["dtype"], 7, t)
            p.homing = s["homing"]
            self.projs.append(p)
            if s["chain"]:
                self.lightning(t, tgt, s["chain"], s["dmg"])
        elif t.key == "sniper":
            t.angle = math.atan2(tgt.y - t.y, tgt.x - t.x)
            dmg = s["dmg"] * (s["blimp_mult"] if tgt.info.get("blimp") else 1)
            self.add_fx("line", t.x, t.y, 0.08, (tgt.x, tgt.y))
            self.damage(tgt, dmg, s["dtype"], None, t)

    def stun_bomb(self, x, y, secs):
        for b in self.query(x, y, 70):
            if b.alive and (b.x - x) ** 2 + (b.y - y) ** 2 <= (70 + b.r) ** 2:
                b.frozen = max(b.frozen, secs)
        self.add_fx("ring", x, y, 0.3, (70, WHITE))

    def apply_glue(self, b, s, tower):
        if b.info.get("blimp") and not s["glue_blimp"]:
            return
        b.glue = s["glue_time"]
        b.glue_slow = s["slow"] * (0.5 if b.info.get("blimp") else 1)
        b.acid = s["acid"]
        b.acid_t = s["acid"]
        b.glue_by = tower

    def make_spikes(self, t):
        if t.spots is None or t.spots[0] != t.s["range"]:
            spots = []   # every reachable point on every track
            for path in self.paths:
                d = 0.0
                while d < path.total:
                    x, y, _ = path.pos(d)
                    if MAP_Y < y < PANEL_Y and 0 < x < SCREEN_W and \
                            (x - t.x) ** 2 + (y - t.y) ** 2 <= t.s["range"] ** 2:
                        spots.append((x, y))
                    d += 10
            t.spots = (t.s["range"], spots)
        spots = t.spots[1]
        if not spots or sum(1 for sp in self.spikes if sp[4] is t) >= t.s.get("pile_cap", 30):
            return
        x, y = random.choice(spots)
        self.spikes.append([x + random.uniform(-9, 9), y + random.uniform(-9, 9),
                            t.s["pierce"], t.s["life"], t])

    def update_spikes(self, dt):
        for sp in self.spikes:
            x, y, _, _, t = sp
            if self.active:
                sp[3] -= dt
            for b in self.query(x, y, 10):
                if sp[2] <= 0:
                    break
                if b.alive and (b.x - x) ** 2 + (b.y - y) ** 2 <= (b.r + 9) ** 2:
                    self.damage(b, t.s["dmg"], t.s["dtype"], None, t)
                    sp[2] -= 1
            if (sp[2] <= 0 or sp[3] <= 0) and t.s["mines"]:
                boom = Proj("bomb", x, y, 0, 0, 0, 2, 20, "explode", 0, t)
                boom.blast = 50
                self.explode(boom)
        self.spikes = [sp for sp in self.spikes if sp[2] > 0 and sp[3] > 0]

    def knight_slash(self, t, first, fx="slash"):
        """Hit a group around the tower: the Spark Knight's sword, the Shark's bite."""
        s = t.s
        t.angle = math.atan2(first.y - t.y, first.x - t.x)
        near = [b for b in self.query(t.x, t.y, s["range"]) if b.alive and (not b.camo or s["camo"])
                and (b.x - t.x) ** 2 + (b.y - t.y) ** 2 <= (s["range"] + b.r) ** 2]
        near.sort(key=lambda b: b.dist - b.path.total)
        for b in near[:s["pierce"]]:
            if s.get("knock") and not b.info.get("blimp"):
                b.dist = max(0.0, b.dist - s["knock"])
            self.damage(b, s["dmg"] * (s.get("blimp_mult", 1) if b.info.get("blimp") else 1), s["dtype"], None, t)
        if fx == "chomp":
            self.add_fx("chomp", first.x, first.y, 0.2)
        else:
            self.add_fx("slash", t.x, t.y, 0.18, (t.angle, s["range"]))

    def nova_lift(self, t):
        """Lift the front balloons into the air, where they float and take damage."""
        s = t.s
        cands = [b for b in self.query(t.x, t.y, s["range"]) if b.alive and b.lift <= 0
                 and (not b.camo or s["camo"]) and not b.info.get("blimp")
                 and (s["lift_heavy"] or (b.name != "ceramic" and not b.fort))
                 and (b.x - t.x) ** 2 + (b.y - t.y) ** 2 <= (s["range"] + b.r) ** 2]
        cands.sort(key=lambda b: b.dist - b.path.total)
        for b in cands[:s["lift_n"]]:
            b.lift, b.lift_t, b.lift_by = s["lift_time"], 0.3, t
            self.add_fx("line", t.x, t.y, 0.12, (b.x, b.y - 10))
        if not cands:
            t.cool = 0.1

    def lightning(self, t, first, jumps, dmg, dtype="magic"):
        """Lightning hits one balloon, then jumps to the nearest new one."""
        hit = set()
        x0, y0 = t.x, t.y
        b = first
        for _ in range(jumps):
            hit.add(b.id)
            self.add_fx("bolt", x0, y0, 0.12, (b.x, b.y))
            x0, y0 = b.x, b.y
            self.damage(b, dmg, dtype, None, t)
            nxt, best = None, 90 ** 2
            for c in self.query(x0, y0, 90):
                if c.alive and c.id not in hit:
                    d2 = (c.x - x0) ** 2 + (c.y - y0) ** 2
                    if d2 < best:
                        nxt, best = c, d2
            if nxt is None:
                break
            b = nxt

    def explode(self, p):
        hits = []
        for b in self.query(p.x, p.y, p.blast):
            if b.alive and (b.x - p.x) ** 2 + (b.y - p.y) ** 2 <= (p.blast + b.r) ** 2:
                hits.append(b)
        hits.sort(key=lambda b: b.dist - b.path.total)
        for b in hits[:p.pierce]:
            self.damage(b, p.dmg * (p.bm if b.info.get("blimp") else 1), p.dtype, None, p.tower)
        self.add_fx("ring", p.x, p.y, 0.25, (p.blast, (255, 170, 50)))
        self.app.sounds.play("boom")
        for i in range(p.cluster):
            a = i * 2 * math.pi / p.cluster
            m = Proj("mini", p.x, p.y, a, 260, 0.22, p.dmg, 6, p.dtype, 5, p.tower)
            m.blast, m.bm = 28, p.bm
            self.projs.append(m)

    # ---------------------------------------------------------- simulate
    def step(self, dt):
        if self.sandbox:   # endless money and lives
            self.money = max(self.money, 999999)
            self.lives = 999999
            for sp in self.sb_spawns:
                sp[0] -= dt
            for _, name, flags in [sp for sp in self.sb_spawns if sp[0] <= 0]:
                self.spawn_balloon(name, 0.0, "c" in flags, regrow=name if "r" in flags else None, fort="f" in flags)
            self.sb_spawns = [sp for sp in self.sb_spawns if sp[0] > 0]
        if self.active:
            self.rtime += dt
            while self.qi < len(self.queue) and self.queue[self.qi][0] <= self.rtime:
                _, name, (camo, regrow, fort) = self.queue[self.qi]
                self.qi += 1
                self.spawn_balloon(name, 0.0, camo, regrow=regrow, fort=fort)

        base = BALLOON_SPEED * self.diff["speed"]
        acid_hits = []
        lift_hits = []
        for b in self.balloons:
            if not b.alive:
                continue
            sp = base * b.info["speed"]
            if b.info.get("unstoppable"):   # the Overlord shrugs off all of these
                b.frozen = b.slow = b.glue = b.lift = 0.0
            if b.frozen > 0:
                b.frozen -= dt
                sp = sp * 0.5 if b.info.get("blimp") else 0.0
            elif b.slow > 0:
                b.slow -= dt
                sp *= 0.5
            if b.regrow and b.name != b.regrow and b.name in REGROW_UP:
                b.regrow_t += dt
                if b.regrow_t >= REGROW_TIME:   # grow a layer back
                    b.regrow_t = 0.0
                    up = REGROW_UP[b.name]
                    if BALLOON_ORDER.index(up) <= BALLOON_ORDER.index(b.regrow):
                        b.set_type(up)
            if b.glue > 0:
                b.glue -= dt
                sp *= 1 - b.glue_slow
                if b.acid:
                    b.acid_t -= dt
                    if b.acid_t <= 0:
                        b.acid_t = b.acid
                        acid_hits.append(b)
            if b.lift > 0:   # floating helplessly, taking damage
                b.lift -= dt
                sp = 0.0
                b.lift_t -= dt
                if b.lift_t <= 0:
                    b.lift_t = 0.6
                    lift_hits.append(b)
            b.speed_now = sp
            b.dist += sp * dt
            if b.dist >= b.path.total:
                b.alive = False
                self.lives -= self.rbe_left(b)
                self.app.sounds.play("leak")
            else:
                b.x, b.y, b.seg = b.path.pos(b.dist, b.seg)

        for b in acid_hits:
            self.damage(b, 1, "normal", None, b.glue_by)
        for b in lift_hits:
            if b.lift_by:
                self.damage(b, b.lift_by.s.get("dmg", 1), "normal", None, b.lift_by)

        self.build_grid()
        self.rally_t = max(0.0, self.rally_t - dt)
        for t in self.towers:
            t.frenzy_t = max(0.0, t.frenzy_t - dt)
            if self.active:
                for aid in t.ab_cool:
                    t.ab_cool[aid] = max(0.0, t.ab_cool[aid] - dt)
            self.update_tower(t, dt)
        self.update_spikes(dt)

        for p in self.projs:
            if p.dead:
                continue
            if p.homing:
                near, best = None, 110 ** 2
                for b in self.query(p.x, p.y, 110):
                    if b.alive and b.id not in p.hit:
                        d2 = (b.x - p.x) ** 2 + (b.y - p.y) ** 2
                        if d2 < best:
                            near, best = b, d2
                if near:
                    sp = math.hypot(p.vx, p.vy)
                    a = math.atan2(near.y - p.y, near.x - p.x)
                    p.vx, p.vy = math.cos(a) * sp, math.sin(a) * sp
                    p.life = max(p.life, 0.3)
            if p.turn:
                c, sn = math.cos(p.turn * dt), math.sin(p.turn * dt)
                p.vx, p.vy = p.vx * c - p.vy * sn, p.vx * sn + p.vy * c
                p.angle += 12 * dt
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.life -= dt
            if p.kind == "spikeball":
                p.angle += 8 * dt   # rolling
                hit_x = p.x < p.r or p.x > SCREEN_W - p.r
                hit_y = p.y < MAP_Y + p.r or p.y > PANEL_Y - p.r
                if (hit_x or hit_y) and p.bounces > 0:   # after its one bounce it rolls off the field
                    p.bounces -= 1
                    if hit_x:
                        p.vx = -p.vx
                        p.x = max(p.r, min(SCREEN_W - p.r, p.x))
                    if hit_y:
                        p.vy = -p.vy
                        p.y = max(MAP_Y + p.r, min(PANEL_Y - p.r, p.y))
                    p.hit.clear()   # it can hit balloons again on the way back
                    self.add_fx("ring", p.x, p.y, 0.2, (16, (220, 220, 230)))
            if p.life <= 0 or p.x < -20 or p.x > SCREEN_W + 20 or p.y < MAP_Y - 20 or p.y > PANEL_Y + 20:
                p.dead = True
                if p.kind in ("bomb", "mini"):
                    self.explode(p)
                continue
            for b in self.query(p.x, p.y, p.r):
                if not b.alive or b.id in p.hit:
                    continue
                rr = b.r + p.r
                if (b.x - p.x) ** 2 + (b.y - p.y) ** 2 <= rr * rr:
                    if p.kind in ("bomb", "mini"):
                        p.dead = True
                        self.explode(p)
                        break
                    p.hit.add(b.id)
                    if p.kind == "glue":
                        ts = p.tower.s
                        if ts["splash"]:
                            for c in self.query(p.x, p.y, ts["splash"]):
                                if c.alive and (c.x - p.x) ** 2 + (c.y - p.y) ** 2 <= (ts["splash"] + c.r) ** 2:
                                    self.apply_glue(c, ts, p.tower)
                            self.add_fx("ring", p.x, p.y, 0.25, (ts["splash"], (170, 220, 60)))
                            p.dead = True
                            break
                        self.apply_glue(b, ts, p.tower)
                        p.pierce -= 1
                        if p.pierce <= 0:
                            p.dead = True
                            break
                        continue
                    if p.kind == "zap" and p.tower.s.get("decamo"):
                        b.camo = False   # Cipher's zaps strip camo
                    if p.knock and not b.info.get("blimp"):
                        b.dist = max(0.0, b.dist - p.knock)
                    self.damage(b, p.dmg * (p.bm if b.info.get("blimp") else 1), p.dtype, p, p.tower)
                    p.pierce -= 1
                    if p.pierce <= 0:
                        p.dead = True
                        break

        self.check_hero_levels()
        self.balloons = [b for b in self.balloons if b.alive]
        self.projs = [p for p in self.projs if not p.dead]

        if self.lives <= 0:
            self.lives = 0
            self.active = False
            self.overlay, self.over_idx = "over", 0
            self.app.clear_resume()   # nothing to continue after a game over
            return
        if self.active and self.qi >= len(self.queue) and not self.balloons:
            self.end_round()

    # ---------------------------------------------------------- input
    def update(self, dt, inp):
        self.toast_t = max(0.0, self.toast_t - dt)
        for f in self.fx:
            f[3] += dt
        self.fx = [f for f in self.fx if f[3] < f[4]]

        if self.overlay:
            self.update_overlay(inp)
            return

        if "SELECT" in inp.pressed:
            self.speed = self.speed % 3 + 1
            self.toast("Speed: %dx" % self.speed, 1.0)
        if "START" in inp.pressed:
            if self.active:
                self.overlay, self.over_idx = "pause", 0
                return
            self.start_round()
            self.toast("Round %d" % self.round, 1.2)
        if self.mode == "normal" and "B" in inp.pressed:
            self.overlay, self.over_idx = "pause", 0   # menu (auto-start etc.)
            return

        if self.auto_wait > 0 and not self.active:
            self.auto_wait -= dt
            if not self.auto:
                self.auto_wait = 0.0
            elif self.auto_wait <= 0:
                self.start_round()
                self.toast("Round %d" % self.round, 1.2)

        chord = {"L", "R"} <= inp.held and ("L" in inp.pressed or "R" in inp.pressed)
        if chord or "ABILITY" in inp.pressed:
            if self.mode == "abilities":
                self.mode = "normal"
            elif self.ability_list():
                self.mode = "abilities"
                self.ab_idx = min(self.ab_idx, len(self.ability_list()) - 1)
            else:
                self.toast("No abilities yet: get a middle-path level 3")
        elif self.mode == "abilities":
            abil = self.ability_list()
            if not abil or "B" in inp.pressed:
                self.mode = "normal"
            else:
                if "LEFT" in inp.repeat:
                    self.ab_idx = (self.ab_idx - 1) % len(abil)
                if "RIGHT" in inp.repeat:
                    self.ab_idx = (self.ab_idx + 1) % len(abil)
                self.ab_idx %= len(abil)
                if "A" in inp.pressed:
                    self.use_ability(*abil[self.ab_idx])
        elif self.mode == "menu":
            self.update_menu(inp)
        else:
            self.move_cursor(dt, inp)
            if self.mode == "normal":
                self.update_normal(inp)
            else:
                self.update_place(inp)

        # Simulate in small steps so fast shots don't skip past balloons.
        sim = dt * self.speed
        steps = max(1, min(12, int(math.ceil(sim / (1 / 60.0)))))
        for _ in range(steps):
            if self.overlay:
                break
            self.step(sim / steps)

    def move_cursor(self, dt, inp):
        dx = ("RIGHT" in inp.held) - ("LEFT" in inp.held)
        dy = ("DOWN" in inp.held) - ("UP" in inp.held)
        if dx or dy:
            self.move_t += dt
            speed = 170 if self.move_t < 0.4 else 340   # speeds up when held
            if dx and dy:
                speed *= 0.7071
            self.cx = max(4, min(SCREEN_W - 4, self.cx + dx * speed * dt))
            self.cy = max(MAP_Y + 4, min(MAP_Y + MAP_H - 4, self.cy + dy * speed * dt))
        else:
            self.move_t = 0.0

    def update_normal(self, inp):
        if "A" in inp.pressed:
            t = self.tower_at(self.cx, self.cy)
            if t:
                self.open_menu(t)
            else:
                self.mode = "place"
        elif "L" in inp.pressed or "R" in inp.pressed:
            self.mode = "place"

    def update_place(self, inp):
        if "L" in inp.repeat:
            self.shop = (self.shop - 1) % len(SHOP)
        if "R" in inp.repeat:
            self.shop = (self.shop + 1) % len(SHOP)
        if "B" in inp.pressed:
            self.mode = "normal"
        if "A" in inp.pressed:
            tt = SHOP[self.shop]
            cost = self.place_cost(tt, self.cx, self.cy)
            existing = self.tower_at(self.cx, self.cy)
            if existing:
                self.open_menu(existing)
            elif tt.get("hero") and any(t.hero for t in self.towers):
                self.toast("Only one hero at a time")
                self.app.sounds.play("error")
            elif self.money < cost:
                self.toast("Need $%d more" % (cost - self.money))
                self.app.sounds.play("error")
            elif not self.can_place(self.cx, self.cy, tt.get("water", False)):
                self.toast("Must go on water" if tt.get("water") else "Can't build there")
                self.app.sounds.play("error")
            else:
                self.money -= cost
                self.towers.append(Tower(tt, self.cx, self.cy, cost))
                self.refresh_buffs()
                self.app.sounds.play("place")
                self.mode = "normal"

    def open_menu(self, t):
        self.sel = t
        self.mode = "menu"
        self.menu = 0

    def menu_rows(self, t):
        """What's in a tower's menu, top to bottom."""
        rows = ["hero"] if t.hero else []
        rows += ["upgrade%d" % p for p in range(len(t.t["paths"]))]
        rows += ["ability:" + a for a in t.abilities()]
        rows.append("target")
        if t.key == "boom":
            rows.append("curve")
        return rows + ["sell"]

    def update_menu(self, inp):
        t = self.sel
        rows = self.menu_rows(t)
        if "UP" in inp.repeat:
            self.menu = (self.menu - 1) % len(rows)
        if "DOWN" in inp.repeat:
            self.menu = (self.menu + 1) % len(rows)
        if "B" in inp.pressed:
            self.mode = "normal"
            return
        if ("L" in inp.pressed or "R" in inp.pressed) and len(self.towers) > 1:
            i = self.towers.index(t) + (1 if "R" in inp.pressed else -1)
            self.sel = t = self.towers[i % len(self.towers)]
            self.cx, self.cy = t.x, t.y
            rows = self.menu_rows(t)
            self.menu = min(self.menu, len(rows) - 1)
        row = rows[self.menu]
        if row == "curve" and ("LEFT" in inp.pressed or "RIGHT" in inp.pressed or "A" in inp.pressed):
            t.curve = -t.curve
            return
        if row == "target" and t.key not in NO_TARGETING:
            if "LEFT" in inp.repeat:
                t.target_mode = (t.target_mode - 1) % len(TARGET_MODES)
            if "RIGHT" in inp.repeat or "A" in inp.pressed:
                t.target_mode = (t.target_mode + 1) % len(TARGET_MODES)
        if "A" not in inp.pressed:
            return
        if row.startswith("ability:"):
            self.use_ability(t, row[8:])
        elif row.startswith("upgrade"):
            p = int(row[7:])
            state = t.upgrade_state(p)
            if state == "max":
                self.toast("That path is maxed out")
            elif state == "locked":
                self.toast("Only one path can go past level 2")
            elif state == "two":
                self.toast("Only 2 paths per tower")
            else:
                cost = self.upgrade_cost(t, p)
                if self.money < cost:
                    self.toast("Need $%d more" % (cost - self.money))
                    self.app.sounds.play("error")
                else:
                    self.money -= cost
                    t.spent += cost
                    t.levels[p] += 1
                    self.refresh_buffs()
                    self.app.sounds.play("upgrade")
                    self.add_fx("ring", t.x, t.y, 0.3, (TOWER_R + 10, YELLOW))
        elif row == "sell":
            value = int(t.spent * SELL_RATE)
            self.money += value
            self.towers.remove(t)
            self.spikes = [sp for sp in self.spikes if sp[4] is not t]
            self.refresh_buffs()
            self.add_fx("text", t.x, t.y, 1.0, "+$%d" % value)
            self.mode = "normal"

    def overlay_items(self):
        if self.overlay == "pause":
            return ["Resume"] + (["Sandbox tools"] if self.sandbox else []) + [
                "Auto-start: %s" % ("ON" if self.auto else "OFF"), SOUND_ROW,
                "Tower guide", "Restart", "Quit to title"]
        if self.overlay == "sandbox":
            sb = self.sb
            return ["Balloon: < %s >" % BALLOON_ORDER[sb["kind"]].capitalize(),
                    "Type: < %s >" % SANDBOX_FLAGS[sb["flags"]][0],
                    "Amount: < %d >" % SANDBOX_AMOUNTS[sb["amount"]],
                    "Send balloons!",
                    "Jump to round: < %d >" % sb["round"],
                    "Pop everything", "Recharge abilities", "Back"]
        if self.overlay in ("win", "champion"):
            return ["Keep playing", "Quit to title"]
        return ["Try again", "Quit to title"]

    def update_overlay(self, inp):
        items = self.overlay_items()
        if "UP" in inp.repeat:
            self.over_idx = (self.over_idx - 1) % len(items)
        if "DOWN" in inp.repeat:
            self.over_idx = (self.over_idx + 1) % len(items)
        if self.overlay == "pause" and ("B" in inp.pressed or "START" in inp.pressed):
            self.overlay = None
            return
        if self.overlay == "sandbox":
            self.update_sandbox(inp, items[self.over_idx])
            return
        choice = items[self.over_idx]
        if choice == SOUND_ROW:
            step = ("RIGHT" in inp.repeat) - ("LEFT" in inp.repeat)
            if step:
                self.app.change_volume(10 * step)
            elif "A" in inp.pressed:
                self.app.change_volume(-100 if self.app.save.get("volume", 70) else 70)
            return
        if "A" not in inp.pressed:
            return
        if choice in ("Resume", "Keep playing"):
            self.overlay = None
        elif choice.startswith("Auto-start"):
            self.auto = not self.auto
            self.app.set_auto_start(self.auto)
            if self.auto and self.round > 0 and not self.active:
                self.auto_wait = AUTO_START_DELAY
        elif choice == "Sandbox tools":
            self.overlay, self.over_idx = "sandbox", 3   # start on "Send balloons!"
        elif choice == "Tower guide":   # look up upgrades without leaving the game
            key = self.sel.key if self.sel and self.mode == "menu" else SHOP[self.shop]["key"]
            self.app.open_guide(key, back="game")
        elif choice in ("Restart", "Try again"):
            self.reset()
        elif choice == "Quit to title":
            self.app.go_title()

    def update_sandbox(self, inp, choice):
        sb = self.sb
        step = ("RIGHT" in inp.repeat) - ("LEFT" in inp.repeat)
        if "B" in inp.pressed or ("A" in inp.pressed and choice == "Back"):
            self.overlay, self.over_idx = "pause", 1
            return
        if step:
            if choice.startswith("Balloon"):
                sb["kind"] = (sb["kind"] + step) % len(BALLOON_ORDER)
            elif choice.startswith("Type"):
                sb["flags"] = (sb["flags"] + step) % len(SANDBOX_FLAGS)
            elif choice.startswith("Amount"):
                sb["amount"] = (sb["amount"] + step) % len(SANDBOX_AMOUNTS)
            elif choice.startswith("Jump"):
                sb["round"] = max(1, min(FINAL_ROUND, sb["round"] + 5 * step if sb["round"] >= 30 else sb["round"] + step))
        if "A" not in inp.pressed:
            return
        if choice == "Send balloons!":
            name, flags = BALLOON_ORDER[sb["kind"]], SANDBOX_FLAGS[sb["flags"]][1]
            gap = 1.0 if BALLOON_TYPES[name].get("blimp") else 0.25
            for i in range(SANDBOX_AMOUNTS[sb["amount"]]):
                self.sb_spawns.append([i * gap, name, flags])
            self.toast("Sending %d %s" % (SANDBOX_AMOUNTS[sb["amount"]], name), 1.2)
            self.overlay = None
        elif choice.startswith("Jump"):
            self.queue, self.qi = [], 0
            self.round = sb["round"] - 1
            self.start_round()
            self.toast("Round %d" % self.round, 1.2)
            self.overlay = None
        elif choice == "Pop everything":
            for b in self.balloons:
                b.alive = False
                self.add_fx("pop", b.x, b.y, 0.32, (b.info["color"], b.id))
            self.balloons, self.sb_spawns = [], []
            self.queue, self.qi = [], 0
            self.toast("All clear!", 1.0)
        elif choice == "Recharge abilities":
            for t in self.towers:
                t.ab_cool.clear()
            self.toast("Abilities ready!", 1.0)

    # ---------------------------------------------------------- drawing
    def draw(self, surf):
        app = self.app
        surf.blit(app.map_bg(self.map_idx), (0, MAP_Y))

        for x, y, _, _, t in self.spikes:
            col = (255, 150, 60) if t.s["dtype"] == "normal" else (205, 205, 215)
            for dx, dy in ((-5, 2), (4, 3), (0, -4)):
                px, py = int(x + dx), int(y + dy)
                pygame.draw.polygon(surf, col, [(px, py - 5), (px - 4, py + 3), (px + 4, py + 3)])
                pygame.draw.polygon(surf, (70, 70, 80), [(px, py - 5), (px - 4, py + 3), (px + 4, py + 3)], 1)

        for t in self.towers:
            sh = app.shadow(40, 14)
            surf.blit(sh, (t.x - 20, t.y + 10))
        for t in self.towers:
            self.draw_tower(surf, t)

        now = pygame.time.get_ticks() / 1000.0
        for b in self.balloons:   # shadows on the ground first
            w = b.info.get("w", b.r * 2) * 0.8
            sh = app.shadow(int(w), max(5, int(b.r * 0.6)))
            surf.blit(sh, (b.x - w / 2 + 3, b.y + b.r * 0.9 + 4))
        for b in self.balloons:
            if b.info.get("blimp"):
                ux, uy = b.path.segs[b.seg][2:4]
                d = ("R" if ux > 0 else "L") if abs(ux) > abs(uy) else ("D" if uy > 0 else "U")
                spr, ox, oy = app.blimp_sprites[b.name][d]
                surf.blit(spr, (b.x - ox, b.y - oy))
                frac = max(0.0, b.hp / (b.info["hp"] * self.hp_mult))
                w = b.info["w"] * 0.7
                pygame.draw.rect(surf, BLACK, (b.x - w / 2 - 1, b.y - b.r - 12, w + 2, 7))
                pygame.draw.rect(surf, GREEN if frac > 0.5 else YELLOW if frac > 0.25 else RED,
                                 (b.x - w / 2, b.y - b.r - 11, w * frac, 5))
                if b.frozen > 0:
                    pygame.draw.ellipse(surf, (190, 235, 255), (b.x - w / 2, b.y - 10, w, 20), 3)
            else:
                spr, ox, oy = app.balloon_sprites[(b.name, b.camo)]
                bob = 0 if b.frozen > 0 else math.sin(now * 5 + b.id) * 1.5   # gentle float
                if b.lift > 0:   # held up in the air by Nova
                    bob = -12 + math.sin(now * 8 + b.id) * 2
                    pygame.draw.circle(surf, (210, 140, 255), (int(b.x), int(b.y + bob)), b.r + 4, 2)
                surf.blit(spr, (b.x - ox, b.y - oy + bob))
                if b.frozen > 0:
                    surf.blit(app.ice_sprite(b.r), (b.x - b.r - 3, b.y - b.r - 3))
            if b.fort:   # armored band
                if b.info.get("blimp"):
                    w = b.info["w"] * 0.9
                    pygame.draw.ellipse(surf, (170, 175, 185), (b.x - w / 2, b.y - b.r * 0.6, w, b.r * 1.2), 4)
                else:
                    pygame.draw.circle(surf, (170, 175, 185), (int(b.x), int(b.y)), b.r + 1, 3)
                    for a in (0.6, 2.2, 3.8, 5.4):
                        pygame.draw.circle(surf, (90, 95, 105), (int(b.x + math.cos(a) * b.r), int(b.y + math.sin(a) * b.r)), 2)
            if b.regrow:   # little green "grows back" badge
                gx, gy = int(b.x + b.r * 0.75), int(b.y - b.r * 0.75)
                pygame.draw.circle(surf, (40, 120, 50), (gx, gy), 6)
                pygame.draw.circle(surf, (120, 240, 120), (gx, gy), 5)
                pygame.draw.line(surf, WHITE, (gx - 3, gy), (gx + 3, gy), 2)
                pygame.draw.line(surf, WHITE, (gx, gy - 3), (gx, gy + 3), 2)
            if b.glue > 0:
                gx, gy = int(b.x), int(b.y - b.r * 0.4)
                col = (150, 230, 60) if not b.acid else (210, 250, 40)
                pygame.draw.circle(surf, col, (gx, gy), max(5, b.r // 2))
                pygame.draw.circle(surf, col, (gx + 4, gy + b.r // 2 + 2), 3)

        for p in self.projs:
            if p.kind == "dart":
                ex, ey = math.cos(p.angle) * 9, math.sin(p.angle) * 9
                pygame.draw.line(surf, (60, 40, 20), (p.x - ex, p.y - ey), (p.x + ex, p.y + ey), 4)
                pygame.draw.circle(surf, (230, 230, 230), (int(p.x + ex), int(p.y + ey)), 2)
            elif p.kind == "spikeball":
                cx, cy = int(p.x), int(p.y)
                for i in range(8):
                    a = p.angle + i * math.pi / 4
                    tip = (p.x + math.cos(a) * 17, p.y + math.sin(a) * 17)
                    l = (p.x + math.cos(a - 0.35) * 10, p.y + math.sin(a - 0.35) * 10)
                    r = (p.x + math.cos(a + 0.35) * 10, p.y + math.sin(a + 0.35) * 10)
                    pygame.draw.polygon(surf, (200, 200, 210), [tip, l, r])
                pygame.draw.circle(surf, (60, 60, 70), (cx, cy), 11)
                pygame.draw.circle(surf, (110, 110, 125), (cx - 3, cy - 3), 5)
                pygame.draw.circle(surf, (30, 30, 36), (cx, cy), 11, 2)
            elif p.kind == "cannon":
                pygame.draw.circle(surf, (30, 30, 34), (int(p.x), int(p.y)), 6)
                pygame.draw.circle(surf, (110, 110, 120), (int(p.x) - 2, int(p.y) - 2), 2)
            elif p.kind == "torpedo":
                ex, ey = math.cos(p.angle) * 8, math.sin(p.angle) * 8
                pygame.draw.line(surf, (70, 75, 90), (p.x - ex, p.y - ey), (p.x + ex, p.y + ey), 6)
                pygame.draw.circle(surf, (230, 90, 60), (int(p.x + ex), int(p.y + ey)), 3)
                pygame.draw.circle(surf, (220, 240, 255), (int(p.x - ex * 1.6), int(p.y - ey * 1.6)), 2)
            elif p.kind == "gust":
                for k in range(3):
                    off = k * 2.1 + p.life * 14
                    pygame.draw.circle(surf, (210, 245, 240), (int(p.x + math.cos(off) * 5), int(p.y + math.sin(off) * 5)), 4 - k, 2)
            elif p.kind == "zap":
                pygame.draw.rect(surf, (90, 255, 120), (int(p.x) - 3, int(p.y) - 3, 7, 7))
                pygame.draw.rect(surf, (20, 90, 40), (int(p.x) - 3, int(p.y) - 3, 7, 7), 1)
            elif p.kind == "star":
                pts = []
                for i in range(8):
                    rad = 8 if i % 2 == 0 else 3
                    a = p.angle * 3 + i * math.pi / 4 + p.life * 20
                    pts.append((p.x + rad * math.cos(a), p.y + rad * math.sin(a)))
                pygame.draw.polygon(surf, (215, 215, 225), pts)
                pygame.draw.polygon(surf, (60, 60, 70), pts, 1)
            elif p.kind == "laser":
                ex, ey = math.cos(p.angle) * 10, math.sin(p.angle) * 10
                col = (255, 90, 90) if p.dtype in ("normal", "magic") else (120, 210, 255)
                pygame.draw.line(surf, col, (p.x - ex, p.y - ey), (p.x + ex, p.y + ey), 4)
            elif p.kind == "glue":
                pygame.draw.circle(surf, (150, 230, 60), (int(p.x), int(p.y)), 6)
                pygame.draw.circle(surf, (70, 120, 30), (int(p.x), int(p.y)), 6, 1)
            elif p.kind == "boom":
                ex, ey = math.cos(p.angle) * 9, math.sin(p.angle) * 9
                fx, fy = math.cos(p.angle + 1.8) * 9, math.sin(p.angle + 1.8) * 9
                col = (255, 120, 40) if p.dtype == "normal" else (220, 150, 60)
                pygame.draw.lines(surf, col, False, [(p.x + ex, p.y + ey), (p.x, p.y), (p.x + fx, p.y + fy)], 5)
            elif p.kind == "bolt":
                pygame.draw.circle(surf, (190, 120, 255), (int(p.x), int(p.y)), 7)
                pygame.draw.circle(surf, (245, 225, 255), (int(p.x), int(p.y)), 3)
            elif p.kind == "fire":
                pygame.draw.circle(surf, (255, 120, 20), (int(p.x), int(p.y)), 8)
                pygame.draw.circle(surf, (255, 230, 90), (int(p.x), int(p.y)), 4)
            elif p.kind == "tack":
                col = (255, 140, 30) if p.dtype in ("normal", "magic") else (220, 220, 230)
                pygame.draw.circle(surf, col, (int(p.x), int(p.y)), 4)
                pygame.draw.circle(surf, (60, 60, 70), (int(p.x), int(p.y)), 4, 1)
            else:
                pygame.draw.circle(surf, (20, 20, 20), (int(p.x), int(p.y)), p.r)
                pygame.draw.circle(surf, (255, 120, 40), (int(p.x + 2), int(p.y - 3)), 2)

        self.draw_fx(surf)

        # range circle, placement ghost and cursor
        if self.mode == "menu" and self.sel:
            self.draw_range(surf, self.sel.x, self.sel.y, self.sel.s["range"], True)
        elif self.mode == "place":
            tt = SHOP[self.shop]
            ok = self.can_place(self.cx, self.cy, tt.get("water", False)) and \
                self.money >= self.place_cost(tt, self.cx, self.cy)
            rng = hero_stats(tt["key"], 1)["range"] if tt.get("hero") else tt["base"]["range"]
            self.draw_range(surf, self.cx, self.cy, rng, ok)
            surf.blit(app.ghost_sprites[tt["key"]], (self.cx - 22, self.cy - 22))
        else:
            t = self.tower_at(self.cx, self.cy)
            if t:
                self.draw_range(surf, t.x, t.y, t.s["range"], True)
                pygame.draw.circle(surf, WHITE, (int(t.x), int(t.y)), TOWER_R + 4, 2)
        if self.mode != "menu":
            x, y = int(self.cx), int(self.cy)
            for col, w in ((BLACK, 5), (WHITE, 2)):
                pygame.draw.line(surf, col, (x - 12, y), (x - 4, y), w)
                pygame.draw.line(surf, col, (x + 4, y), (x + 12, y), w)
                pygame.draw.line(surf, col, (x, y - 12), (x, y - 4), w)
                pygame.draw.line(surf, col, (x, y + 4), (x, y + 12), w)

        self.draw_hud(surf)
        self.draw_panel(surf)
        self.draw_ability_bar(surf)
        if self.mode == "menu" and self.sel:
            self.draw_menu(surf)
        # messages go at the top of the map, or at the bottom if a tower menu is up there
        menu_at_top = self.mode == "menu" and self.sel and self.sel.y >= MAP_Y + MAP_H / 2
        msg_y = PANEL_Y - 90 if menu_at_top else MAP_Y + 30
        if self.auto_wait > 0 and not self.active:
            t = app.text(app.f_norm, "Next round in %d..." % math.ceil(self.auto_wait), YELLOW)
            r = t.get_rect(center=(SCREEN_W // 2, msg_y + 42))
            pygame.draw.rect(surf, DARK, r.inflate(20, 10), border_radius=8)
            surf.blit(t, r)
        if self.toast_t > 0:
            t = app.text(app.f_norm, self.toast_text, WHITE)
            r = t.get_rect(center=(SCREEN_W // 2, msg_y))
            pygame.draw.rect(surf, DARK, r.inflate(20, 10), border_radius=8)
            surf.blit(t, r)
        if self.overlay:
            self.draw_overlay(surf)

    def draw_range(self, surf, x, y, r, ok):
        if 0 < r < 600:
            spr = self.app.range_sprite(int(r), ok)
            surf.blit(spr, (x - spr.get_width() // 2, y - spr.get_height() // 2))

    def draw_ability_bar(self, surf):
        """Round ability buttons along the bottom of the field."""
        app = self.app
        abil = self.ability_list()[:9]
        if not abil:
            return
        y = PANEL_Y - 28
        x0 = SCREEN_W - 26 - 46 * (len(abil) - 1)
        for i, (t, aid) in enumerate(abil):
            x = x0 + i * 46
            left = t.ab_cool.get(aid, 0)
            pygame.draw.circle(surf, (20, 22, 32), (x, y), 21)
            surf.blit(app.mini_sprite(t.key), (x - 15, y - 15))
            if left > 0:   # dark "clock" sweep while recharging
                frac = left / ABILITIES[aid][1]
                cover = pygame.Surface((42, 42), pygame.SRCALPHA)
                pts = [(21, 21)] + [(21 + 21 * math.sin(a / 20 * frac * 2 * math.pi),
                                     21 - 21 * math.cos(a / 20 * frac * 2 * math.pi)) for a in range(21)]
                pygame.draw.polygon(cover, (0, 0, 0, 150), pts)
                surf.blit(cover, (x - 21, y - 21))
                img = app.text(app.f_small, str(math.ceil(left)), WHITE)
                surf.blit(img, img.get_rect(center=(x, y)))
            ring = YELLOW if left <= 0 else (90, 95, 115)
            pygame.draw.circle(surf, ring, (x, y), 21, 3 if left <= 0 else 2)
            if self.mode == "abilities" and i == self.ab_idx:
                pygame.draw.circle(surf, WHITE, (x, y), 25, 3)
                name = app.text(app.f_small, ABILITIES[aid][0], WHITE)
                r = name.get_rect(midbottom=(min(SCREEN_W - name.get_width() // 2 - 6,
                                                 max(name.get_width() // 2 + 6, x)), y - 28))
                pygame.draw.rect(surf, DARK, r.inflate(12, 6), border_radius=6)
                surf.blit(name, r)

    def draw_tower(self, surf, t):
        app = self.app
        if t.hero:
            now = pygame.time.get_ticks() / 1000.0
            bob = {"nova": -4 + math.sin(now * 2.5) * 3, "witch": math.sin(now * 3) * 1.5}.get(t.key, 0)
            spr = app.hero_sprites[(t.key, math.cos(t.angle) < -0.2)]   # face the way it attacks
            surf.blit(spr, (t.x - spr.get_width() // 2, t.y - 40 + bob))
            if t.key == "nova":   # glowing orbs circling the monk
                for i in range(3):
                    a = now * 2 + i * 2 * math.pi / 3
                    ox, oy = t.x + math.cos(a) * 20, t.y - 12 + bob + math.sin(a) * 7
                    pygame.draw.circle(surf, (200, 130, 255), (int(ox), int(oy)), 4)
                    pygame.draw.circle(surf, (255, 235, 255), (int(ox), int(oy)), 2)
        elif t.key in WATER_KEYS:
            spr = app.rotated(t.key, t.angle)
            surf.blit(spr, spr.get_rect(center=(int(t.x), int(t.y))))
        else:
            surf.blit(app.tower_sprites[t.key], (t.x - 22, t.y - 22))
        if t.hero:   # gold level badge
            bx, by = int(t.x + 16), int(t.y + 12)
            pygame.draw.circle(surf, (120, 80, 10), (bx, by), 10)
            pygame.draw.circle(surf, (255, 205, 60), (bx, by), 9)
            img = self.app.text(self.app.f_tiny, str(t.hero_level), (60, 35, 0))
            surf.blit(img, img.get_rect(center=(bx, by + 1)))
        if t.key in BARRELS:
            length, width, col = BARRELS[t.key]
            if t.flash > 0:
                length -= 4
            ex, ey = t.x + math.cos(t.angle) * length, t.y + math.sin(t.angle) * length
            pygame.draw.line(surf, col, (t.x, t.y), (ex, ey), width)
            pygame.draw.circle(surf, col, (int(t.x), int(t.y)), width // 2 + 3)
            if t.key == "dart":   # a crossbow: bow across the front
                px, py = -math.sin(t.angle) * 8, math.cos(t.angle) * 8
                bx, by = t.x + math.cos(t.angle) * (length - 6), t.y + math.sin(t.angle) * (length - 6)
                pygame.draw.line(surf, (60, 35, 15), (bx - px, by - py), (bx + px, by + py), 3)
        for p in range(len(t.levels)):
            x0 = t.x - 25 + p * 17
            for i in range(MAX_TIER):
                rect = (x0 + i * 3, t.y + TOWER_R + 3, 2, 4)
                pygame.draw.rect(surf, PATH_COLORS[p] if i < t.levels[p] else (40, 40, 40), rect)

    def draw_fx(self, surf):
        app = self.app
        for kind, x, y, t, dur, data in self.fx:
            p = t / dur
            if kind == "pop":
                col, seed = data
                if p < 0.3:   # quick white flash
                    pygame.draw.circle(surf, WHITE, (int(x), int(y)), int(4 + 20 * p), 2)
                for i in range(7):   # confetti flying out, then falling
                    a = i * 0.9 + seed
                    speed = 60 + (seed * 37 + i * 13) % 40
                    px = x + math.cos(a) * speed * t
                    py = y + math.sin(a) * speed * t + 140 * t * t
                    size = 4 if i % 2 else 3
                    pygame.draw.rect(surf, col if i % 3 else WHITE, (int(px), int(py), size, size - 1))
            elif kind == "ring":
                rad, col = data
                pygame.draw.circle(surf, col, (int(x), int(y)), max(3, int(rad * (0.4 + 0.6 * p))), 3)
            elif kind == "line":
                pygame.draw.line(surf, (255, 255, 200), (x, y), data, 2)
            elif kind == "bolt":
                mx = (x + data[0]) / 2 + random.uniform(-8, 8)
                my = (y + data[1]) / 2 + random.uniform(-8, 8)
                pygame.draw.lines(surf, (200, 230, 255), False, [(x, y), (mx, my), data], 3)
            elif kind == "chomp":   # two jaws snapping shut
                gap = int(10 * (1 - p))
                for side in (-1, 1):
                    y0 = y + side * (gap + 4)
                    pygame.draw.arc(surf, WHITE, (x - 12, y0 - 8, 24, 16), 0 if side > 0 else math.pi,
                                    math.pi if side > 0 else 2 * math.pi, 3)
            elif kind == "slash":
                ang, rad = data
                rect = pygame.Rect(x - rad, y - rad, rad * 2, rad * 2)
                sweep = -ang - 1.2 + 2.4 * p
                pygame.draw.arc(surf, (255, 240, 120), rect, sweep - 0.8, sweep + 0.8, 5)
                pygame.draw.arc(surf, (140, 220, 255), rect.inflate(-14, -14), sweep - 0.6, sweep + 0.6, 3)
            elif kind == "clink":
                pygame.draw.circle(surf, (200, 200, 210), (int(x), int(y)), 4 + int(6 * p), 2)
            elif kind == "text":
                img = app.text(app.f_small, data, YELLOW)
                surf.blit(img, img.get_rect(center=(x, y - 25 * p)))

    def draw_hud(self, surf):
        app = self.app
        surf.blit(app.hud_bg, (0, 0))
        for rect in ((4, 5, 86, 30), (114, 5, 112, 30)):   # pills behind lives and money
            pygame.draw.rect(surf, (18, 21, 31), rect, border_radius=15)
            pygame.draw.rect(surf, (70, 78, 105), rect, 1, border_radius=15)
        # heart
        pygame.draw.circle(surf, RED, (14, 17), 7)
        pygame.draw.circle(surf, RED, (26, 17), 7)
        pygame.draw.polygon(surf, RED, [(7, 19), (33, 19), (20, 33)])
        surf.blit(app.text(app.f_norm, "inf" if self.sandbox else str(self.lives), WHITE), (40, 8))
        # coin
        pygame.draw.circle(surf, YELLOW, (130, 20), 11)
        pygame.draw.circle(surf, (180, 140, 30), (130, 20), 11, 2)
        surf.blit(app.text(app.f_norm, "%d" % self.money, WHITE), (147, 8))
        if self.auto:
            img = app.text(app.f_small, "AUTO", DARK)
            r = img.get_rect(midleft=(236, 21))
            pygame.draw.rect(surf, GREEN, r.inflate(10, 6), border_radius=6)
            surf.blit(img, r)
        goal = WIN_ROUND if self.round <= WIN_ROUND else FINAL_ROUND
        rtxt = "Round %d/%d" % (max(1, self.round), goal) if self.round <= FINAL_ROUND \
            else "Round %d" % self.round
        img = app.text(app.f_norm, rtxt, WHITE)
        surf.blit(img, (SCREEN_W - img.get_width() - (16 + 13 * self.speed if self.speed > 1 else 10), 8))
        if self.speed > 1:
            for i in range(self.speed):
                x = SCREEN_W - 10 - 13 * self.speed + i * 13
                pygame.draw.polygon(surf, YELLOW, [(x, 11), (x + 12, 20), (x, 29)])

    def draw_shop_strip(self, surf, highlight):
        app = self.app
        shown = min(SHOP_SLOTS, len(SHOP))
        slot_w = SCREEN_W // shown
        first = max(0, min(self.shop - shown // 2, len(SHOP) - shown))
        for i in range(first, first + shown):
            tt = SHOP[i]
            x = (i - first) * slot_w
            cost = self.cost(tt["cost"])
            if highlight and i == self.shop:
                pygame.draw.rect(surf, PANEL_HI, (x + 2, PANEL_Y + 3, slot_w - 4, 62), border_radius=6)
                pygame.draw.rect(surf, YELLOW, (x + 2, PANEL_Y + 3, slot_w - 4, 62), 2, border_radius=6)
            spr = app.icons[tt["key"]]
            surf.blit(spr, (x + slot_w // 2 - 22, PANEL_Y + 2))
            img = app.text(app.f_small, "$%d" % cost, GREEN if self.money >= cost else (230, 110, 110))
            surf.blit(img, img.get_rect(center=(x + slot_w // 2, PANEL_Y + 54)))
        for side, show in ((-1, first > 0), (1, first + shown < len(SHOP))):
            if show:   # little arrows: more towers this way
                ax = 5 if side < 0 else SCREEN_W - 5
                pygame.draw.polygon(surf, YELLOW, [(ax, PANEL_Y + 28), (ax - side * 7, PANEL_Y + 20),
                                                   (ax - side * 7, PANEL_Y + 36)])

    def draw_panel(self, surf):
        app = self.app
        surf.blit(app.panel_bg, (0, PANEL_Y))
        pygame.draw.line(surf, (80, 85, 105), (0, PANEL_Y), (SCREEN_W, PANEL_Y), 2)
        if self.mode == "place":
            self.draw_shop_strip(surf, True)
            tt = SHOP[self.shop]
            name = tt["name"] + ("  (hero)" if tt.get("hero") else "  (water)" if tt.get("water") else "")
            disc = self.discount_at(self.cx, self.cy)
            if disc:
                name += "  $%d!" % self.place_cost(tt, self.cx, self.cy)
            surf.blit(app.text(app.f_norm, name, YELLOW if disc else WHITE), (10, PANEL_Y + 68))
            hint = app.text(app.f_small, "A: build  B: back", GRAY)
            surf.blit(hint, (SCREEN_W - hint.get_width() - 10, PANEL_Y + 72))
            surf.blit(app.text(app.f_small, tt["desc"], (200, 205, 220)), (10, PANEL_Y + 95))
        else:
            self.draw_shop_strip(surf, False)
            if self.mode == "abilities":
                l1, l2 = "LEFT/RIGHT: pick ability", "A: use it  B: close"
            elif self.mode == "menu":
                l1, l2 = "UP/DOWN: choose  A: OK", "L/R: next tower  B: close"
            elif self.active:
                l1, l2 = "L/R: buy  A: tower  B: menu", "START: pause  SELECT: speed  L+R: powers"
            else:
                l1, l2 = "L/R: buy  A: tower  B: menu", "START: go  SELECT: speed  L+R: powers"
            surf.blit(app.text(app.f_small, l1, (200, 205, 220)), (10, PANEL_Y + 70))
            surf.blit(app.text(app.f_small, l2, (200, 205, 220)), (10, PANEL_Y + 95))

    def draw_menu(self, surf):
        """Upgrade menu for the selected tower, drawn over the map."""
        app = self.app
        t = self.sel
        keys = self.menu_rows(t)
        h = 96 + 34 * len(keys)
        y0 = MAP_Y + MAP_H - h - 4 if t.y < MAP_Y + MAP_H / 2 else MAP_Y + 4
        box = pygame.Rect(6, y0, SCREEN_W - 12, h)
        pygame.draw.rect(surf, (28, 32, 46), box, border_radius=10)
        pygame.draw.rect(surf, (110, 120, 150), box, 2, border_radius=10)
        name = app.text(app.f_norm, t.t["name"], YELLOW)
        surf.blit(name, (18, y0 + 8))
        # match stats right next to the name: damage dealt and layers popped
        x = 18 + name.get_width() + 12
        for label, col, icon in (("%s dmg" % "{:,}".format(int(t.dmg_done)), (230, 110, 60), "sword"),
                                 ("%s pops" % "{:,}".format(t.pops), (70, 140, 220), "balloon")):
            img = app.text(app.f_tiny, label, WHITE)
            pill = pygame.Rect(x, y0 + 9, img.get_width() + 30, 22)
            if pill.right > SCREEN_W - 14:
                break
            pygame.draw.rect(surf, col, pill, border_radius=11)
            pygame.draw.rect(surf, darker(col), pill, 2, border_radius=11)
            ix, iy = pill.x + 11, pill.centery
            if icon == "sword":
                pygame.draw.line(surf, WHITE, (ix - 4, iy + 5), (ix + 4, iy - 5), 2)
                pygame.draw.line(surf, WHITE, (ix - 5, iy + 1), (ix - 1, iy + 5), 2)
            else:
                pygame.draw.circle(surf, WHITE, (ix, iy - 1), 5)
                pygame.draw.line(surf, WHITE, (ix, iy + 4), (ix - 1, iy + 7), 1)
            surf.blit(img, (pill.x + 20, pill.centery - img.get_height() // 2))
            x = pill.right + 6

        rows = []
        stats = stat_summary(t.s)   # line under the description
        if t.hero:
            if t.hero_level >= HERO_MAX_LEVEL:
                xp = "MAX level"
            else:
                xp = "XP %d/%d" % (t.xp, HERO_XP[t.hero_level])
            nxt = [lvl for lvl, _ in t.t["abilities"] if lvl > t.hero_level]
            hint = ("New ability at level %d" % nxt[0]) if nxt else "Levels up by popping balloons"
            rows.append(("Level %d   %s" % (t.hero_level, xp), (255, 215, 80), hint))
        for p in range(len(t.t["paths"])):
            state = t.upgrade_state(p)
            if state == "max":
                rows.append(("Path %s: MAX" % "ABC"[p], GRAY, "Fully upgraded"))
            elif state == "locked":
                rows.append(("Path %s: locked" % "ABC"[p], GRAY, "Another path is past level 2"))
            elif state == "two":
                rows.append(("Path %s: closed" % "ABC"[p], GRAY, "Only 2 paths per tower"))
            else:
                name, _, desc, _ = t.t["paths"][p][t.levels[p]]
                cost = self.upgrade_cost(t, p)
                rows.append(("%s  $%d" % (name, cost), GREEN if self.money >= cost else (230, 110, 110), desc))
                if keys[self.menu] == "upgrade%d" % p:   # show exactly what this upgrade changes
                    before = Tower(t.t, 0, 0, 0)
                    before.levels = list(t.levels)
                    before.recalc()
                    after = Tower(t.t, 0, 0, 0)
                    after.levels = list(t.levels)
                    after.levels[p] += 1
                    after.recalc()
                    stats = "> " + stat_changes(before.s, after.s)
        for aid in t.abilities():
            name, _, desc = ABILITIES[aid]
            left = t.ab_cool.get(aid, 0)
            rows.append(("%s: %s" % (name, "READY (A)" if left <= 0 else "%ds" % math.ceil(left)),
                         YELLOW if left <= 0 else GRAY, "Ability: " + desc))
        if t.key == "spike":
            rows.append(("Piles pop %d each" % t.s["pierce"], WHITE, "Spikes land on the track in range"))
        elif t.key == "village":
            perks = [n for n, on in (("range", True), ("camo", t.s["radar"]), ("speed", t.s["drums"]),
                                     ("lead", t.s["rune"]), ("discount", t.s["discount"])) if on]
            rows.append(("Boosts: " + ", ".join(perks), WHITE, "Helps every tower in its circle"))
        elif t.key == "mine":
            pay = int(t.s["income"] * t.s["mult"])
            extra = " +%d lives" % t.s["lives"] if t.s["lives"] else ""
            rows.append(("Earns $%d/round%s" % (pay, extra), WHITE, "Paid at the end of every round"))
        elif t.key == "frost":
            rows.append(("Freezes %.1fs" % t.s["freeze"], WHITE, "Freezes everything in range"))
        else:
            rows.append(("Target: < %s >" % TARGET_MODES[t.target_mode], WHITE,
                         "Which balloon to shoot first"))
        if t.key == "boom":
            rows.append(("Curve: < %s >" % ("Right" if t.curve > 0 else "Left"), WHITE,
                         "Which way the boomerang flies"))
        value = int(t.spent * SELL_RATE)
        rows.append(("Sell  +$%d" % value, (255, 200, 120), "Remove tower, get money back"))

        surf.blit(app.text(app.f_small, rows[self.menu][2], (190, 195, 210)), (18, y0 + 36))
        stat_col = GREEN if stats.startswith(">") else (150, 200, 255)
        surf.blit(app.text(app.f_small, stats[:46], stat_col), (18, y0 + 60))
        for i, (label, col, _) in enumerate(rows):
            ry = y0 + 90 + i * 34
            if i == self.menu:
                pygame.draw.rect(surf, PANEL_HI, (14, ry - 2, SCREEN_W - 28, 31), border_radius=6)
                pygame.draw.rect(surf, YELLOW, (14, ry - 2, SCREEN_W - 28, 31), 2, border_radius=6)
            surf.blit(app.text(app.f_norm, label, col), (24, ry + 3))
            if i < len(t.t["paths"]):
                for k in range(MAX_TIER):
                    rect = (SCREEN_W - 84 + k * 13, ry + 10, 9, 9)
                    pygame.draw.rect(surf, PATH_COLORS[i], rect, 0 if k < t.levels[i] else 2)

    def draw_overlay(self, surf):
        app = self.app
        surf.blit(app.dim, (0, 0))
        if self.overlay == "pause":
            title, sub = "Paused", "Round %d" % max(1, self.round)
        elif self.overlay == "sandbox":
            title, sub = "Sandbox Tools", "LEFT/RIGHT: change    A: do it"
        elif self.overlay == "over":
            title, sub = "Game Over", "You made it to round %d" % self.round
        elif self.overlay == "champion":
            title, sub = "CHAMPION!", "All %d rounds beaten!" % FINAL_ROUND
        else:
            title, sub = "You Win!", "Round %d beaten! Keep going to %d?" % (WIN_ROUND, FINAL_ROUND)
        items = self.overlay_items()
        top = 190 if len(items) <= 4 else 140 if len(items) <= 6 else 90   # long menus start higher
        img = app.text(app.f_big, title, YELLOW)
        surf.blit(img, img.get_rect(center=(SCREEN_W // 2, top)))
        img = app.text(app.f_norm, sub, WHITE)
        surf.blit(img, img.get_rect(center=(SCREEN_W // 2, top + 55)))
        app.draw_menu_list(surf, items, self.over_idx, top + 110, 52 if len(items) <= 4 else 50 if len(items) <= 6 else 44)


# =====================================================================
# The app: title screen, help, button tester, and the main loop
# =====================================================================
class App:
    def __init__(self, screen, canvas, rotate):
        self.screen = screen
        self.canvas = canvas
        self.rotate = rotate
        self.clock = pygame.time.Clock()
        self.inp = Input()
        self.sounds = Sounds()
        self.f_big = pygame.font.Font(None, 64)
        self.f_med = pygame.font.Font(None, 40)
        self.f_norm = pygame.font.Font(None, 30)
        self.f_small = pygame.font.Font(None, 26)
        self.f_tiny = pygame.font.Font(None, 20)
        self._text_cache = {}
        self._bg_cache = {}
        self._range_cache = {}
        self._ice_cache = {}
        self.balloon_sprites = {(n, c): make_balloon_sprite(n, c)
                                for n, i in BALLOON_TYPES.items() if not i.get("blimp") for c in (False, True)}
        self.blimp_sprites = {n: make_blimp_sprites(n) for n, i in BALLOON_TYPES.items() if i.get("blimp")}
        self.tower_sprites = {}
        for tt in TOWER_TYPES:
            spr = make_tower_sprite(tt["key"], self.f_med)
            self.tower_sprites[tt["key"]] = spr if tt["key"] in WATER_KEYS else finish_tower_sprite(spr)
        self.hero_sprites = {}   # (key, facing left?) -> character picture
        for h in HERO_TYPES:
            spr = make_hero_sprite(h["key"])
            self.hero_sprites[(h["key"], False)] = spr
            self.hero_sprites[(h["key"], True)] = pygame.transform.flip(spr, True, False)
        self.icons = {}          # 44x44 pictures for the shop and ability buttons
        for key, spr in self.tower_sprites.items():
            self.icons[key] = spr if spr.get_width() == 44 else pygame.transform.smoothscale(spr, (44, 44))
        for h in HERO_TYPES:
            spr = self.hero_sprites[(h["key"], False)]
            icon = pygame.Surface((44, 44), pygame.SRCALPHA)
            small = pygame.transform.smoothscale(spr, (int(spr.get_width() * 44 / spr.get_height()), 44))
            icon.blit(small, small.get_rect(center=(22, 22)))
            self.icons[h["key"]] = icon
        self._rot = {}           # rotated water towers
        self.shadows = {}   # soft shadows, by size
        self._mini = {}     # small tower pictures
        self.hud_bg = self.gradient(SCREEN_W, HUD_H, (44, 50, 72), (22, 25, 36))
        self.panel_bg = self.gradient(SCREEN_W, PANEL_H, (46, 51, 70), (26, 29, 41))
        self.ghost_sprites = {}   # see-through copies for the "where will it go" preview
        for key, spr in self.icons.items():
            ghost = spr.copy()
            ghost.set_alpha(170)
            self.ghost_sprites[key] = ghost
        self.dim = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        self.dim.fill((0, 0, 0, 160))
        self.save = self.load_save()
        self.sounds.set_volume(self.save.get("volume", 70) / 100.0)
        self.state = "title"
        self.map_idx = 0
        self.diff_idx = 1
        self.game = None
        self.running = True
        self.title_balloons = [[random.uniform(0, SCREEN_W), random.uniform(0, SCREEN_H),
                                random.choice(["red", "blue", "green", "yellow", "pink"]),
                                random.uniform(25, 60)] for _ in range(14)]
        self.btn_hold = 0.0
        self.title_idx = 0       # main menu: Continue (if saved) or Play
        self.play_idx = 2        # play screen: START
        self.set_idx = 0
        self.tab_idx = 0         # Towers & Heroes screen
        self.guide_back = "title"
        self._previews = {}

    # ---------------------------------------------------------- caches
    def text(self, font, s, color):
        key = (id(font), s, color)
        img = self._text_cache.get(key)
        if img is None:
            if len(self._text_cache) > 400:
                self._text_cache.clear()
            img = font.render(s, True, color)
            self._text_cache[key] = img
        return img

    def map_bg(self, idx):
        if idx not in self._bg_cache:
            self._bg_cache[idx] = self.render_map(MAPS[idx])
        return self._bg_cache[idx]

    def render_map(self, mp):
        surf = pygame.Surface((SCREEN_W, MAP_H)).convert()
        surf.fill(GRASS)
        rnd = random.Random(mp["seed"])
        for i in range(-MAP_H, SCREEN_W, 48):   # mowed-lawn stripes
            pygame.draw.polygon(surf, (95, 175, 79), [(i, 0), (i + 24, 0), (i + 24 + MAP_H, MAP_H), (i + MAP_H, MAP_H)])
        patch = pygame.Surface((80, 80), pygame.SRCALPHA)
        for _ in range(26):   # soft darker patches
            patch.fill((0, 0, 0, 0))
            rr = rnd.randrange(18, 40)
            pygame.draw.circle(patch, GRASS_DARK + (110,), (40, 40), rr)
            surf.blit(patch, (rnd.randrange(SCREEN_W) - 40, rnd.randrange(MAP_H) - 40))
        for _ in range(160):
            x, y = rnd.randrange(SCREEN_W), rnd.randrange(MAP_H)
            pygame.draw.line(surf, (60, 125, 50), (x, y), (x + rnd.choice((-3, 3)), y - 6), 2)
        for _ in range(30):
            x, y = rnd.randrange(SCREEN_W), rnd.randrange(MAP_H)
            pygame.draw.circle(surf, rnd.choice([(250, 250, 250), (250, 220, 80), (240, 140, 180)]), (x, y), 3)
        for x, y, r in mp.get("water", []):
            pygame.draw.circle(surf, (60, 120, 200), (x, y), r + 5)
        for x, y, r in mp.get("water", []):
            pygame.draw.circle(surf, (80, 150, 230), (x, y), r)
        for x, y, r in mp.get("water", []):   # little waves
            for i in range(3):
                wx, wy = x - r // 3 + i * 14 - 10, y - r // 3 + i * 16
                pygame.draw.arc(surf, (170, 210, 250), (wx, wy, 18, 10), 0.3, 2.8, 2)
        for col, half in ((PATH_EDGE, PATH_W // 2 + 4), (PATH_COL, PATH_W // 2)):
            for pts in mp["paths"]:
                for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                    surf.fill(col, pygame.Rect(min(x0, x1) - half, min(y0, y1) - half,
                                               abs(x1 - x0) + 2 * half, abs(y1 - y0) + 2 * half))
        for pts in mp["paths"]:   # wheel ruts down the middle of the track
            for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                horiz = y0 == y1
                for off in (-8, 8):
                    a = (x0, y0 + off) if horiz else (x0 + off, y0)
                    b = (x1, y1 + off) if horiz else (x1 + off, y1)
                    pygame.draw.line(surf, (196, 166, 112), a, b, 3)
        for pts in mp["paths"]:
            for (x0, y0), (x1, y1) in zip(pts, pts[1:]):   # little pebbles on the track
                for _ in range(int(math.hypot(x1 - x0, y1 - y0) / 25)):
                    t = rnd.random()
                    px = x0 + (x1 - x0) * t + rnd.randint(-12, 12)
                    py = y0 + (y1 - y0) * t + rnd.randint(-12, 12)
                    pygame.draw.circle(surf, (190, 160, 110), (int(px), int(py)), 2)
            ex, ey = pts[-1]
            if 0 <= ex <= SCREEN_W and 0 <= ey <= MAP_H:   # track ends in a hole
                pygame.draw.circle(surf, (60, 45, 30), (ex, ey), PATH_W // 2 + 2)
                pygame.draw.circle(surf, (15, 10, 5), (ex, ey), PATH_W // 2 - 4)
        shade = pygame.Surface((SCREEN_W, MAP_H), pygame.SRCALPHA)   # darker edges, for depth
        for i in range(14):
            pygame.draw.rect(shade, (0, 0, 0, 7), (i, i, SCREEN_W - 2 * i, MAP_H - 2 * i), 1)
        for x, y, r in mp.get("rocks", []):
            pygame.draw.circle(surf, (95, 90, 85), (x, y + 3), r)
            pygame.draw.circle(surf, (135, 128, 120), (x, y), r)
            pygame.draw.circle(surf, (165, 158, 150), (x - r // 3, y - r // 3), r // 3)
            pygame.draw.circle(surf, (85, 80, 75), (x, y), r, 2)
        surf.blit(shade, (0, 0))
        return surf

    def gradient(self, w, h, top, bottom):
        g = pygame.Surface((w, h)).convert()
        for y in range(h):
            f = y / max(1, h - 1)
            g.fill(tuple(int(top[i] + (bottom[i] - top[i]) * f) for i in range(3)), (0, y, w, 1))
        return g

    def rotated(self, key, angle):
        """A water tower turned to face angle (sprites face up), in 15-degree steps."""
        step = int(round(((-math.degrees(angle) - 90) % 360) / 15)) % 24
        k = (key, step)
        if k not in self._rot:
            self._rot[k] = pygame.transform.rotate(self.tower_sprites[key], step * 15)
        return self._rot[k]

    def mini_sprite(self, key):
        if key not in self._mini:
            self._mini[key] = pygame.transform.smoothscale(self.icons[key], (30, 30))
        return self._mini[key]

    def shadow(self, w, h):
        key = (w, h)
        if key not in self.shadows:
            sh = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.ellipse(sh, (0, 0, 0, 60), (0, 0, w, h))
            pygame.draw.ellipse(sh, (0, 0, 0, 40), (w // 6, h // 6, w * 2 // 3, h * 2 // 3))
            self.shadows[key] = sh
        return self.shadows[key]

    def range_sprite(self, r, ok):
        key = (r, ok)
        if key not in self._range_cache:
            s = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
            col = (255, 255, 255) if ok else (255, 60, 60)
            pygame.draw.circle(s, col + (45,), (r + 2, r + 2), r)
            pygame.draw.circle(s, col + (160,), (r + 2, r + 2), r, 2)
            self._range_cache[key] = s
        return self._range_cache[key]

    def ice_sprite(self, r):
        if r not in self._ice_cache:
            s = pygame.Surface((r * 2 + 6, r * 2 + 6), pygame.SRCALPHA)
            pygame.draw.circle(s, (190, 235, 255, 140), (r + 3, r + 3), r + 3)
            pygame.draw.circle(s, (230, 250, 255, 220), (r + 3, r + 3), r + 3, 2)
            self._ice_cache[r] = s
        return self._ice_cache[r]

    # ---------------------------------------------------------- saving
    def load_save(self):
        try:
            with open(SAVE_FILE) as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def write_save(self):
        try:
            with open(SAVE_FILE, "w") as f:
                json.dump(self.save, f)
        except OSError:
            pass

    def record_best(self, map_idx, diff_idx, rnd):
        key = "%s|%s" % (MAPS[map_idx]["name"], DIFFICULTIES[diff_idx]["name"])
        if rnd > self.save.get(key, 0):
            self.save[key] = rnd
            self.write_save()

    def save_resume(self, snap):
        self.save["resume"] = snap
        self.write_save()

    def clear_resume(self):
        if self.save.pop("resume", None) is not None:
            self.write_save()

    def continue_game(self):
        snap = self.save["resume"]
        self.map_idx, self.diff_idx = snap["map"], snap["diff"]
        self.game = Game(self, self.map_idx, self.diff_idx)
        self.game.restore(snap)
        self.state = "game"

    def set_auto_start(self, on):
        """Remembered between games (and after turning the handheld off)."""
        self.save["auto_start"] = on
        self.write_save()

    def best(self, map_idx, diff_idx):
        return self.save.get("%s|%s" % (MAPS[map_idx]["name"], DIFFICULTIES[diff_idx]["name"]), 0)

    # ---------------------------------------------------------- screens
    def go_title(self):
        self.state = "title"
        self.game = None
        self.title_idx = 0

    def change_volume(self, step):
        """Move the sound slider by step (in %), save it, and play a test pop."""
        vol = max(0, min(100, self.save.get("volume", 70) + step))
        self.save["volume"] = vol
        self.write_save()
        self.sounds.set_volume(vol / 100.0)
        self.sounds.last_pop = 0
        self.sounds.play("pop")

    def draw_menu_list(self, surf, items, idx, y, gap=52):
        for i, label in enumerate(items):
            col = YELLOW if i == idx else WHITE
            cy = y + i * gap
            if label == SOUND_ROW:   # "Sound" with a slider bar
                vol = self.save.get("volume", 70)
                img = self.text(self.f_med, "Sound", col)
                pct = self.text(self.f_small, "%d%%" % vol if vol else "OFF", col)
                bar_w = 150
                total = img.get_width() + 14 + bar_w + 12 + 46
                x0 = SCREEN_W // 2 - total // 2
                r = pygame.Rect(x0, cy - img.get_height() // 2, total, img.get_height())
                if i == idx:
                    pygame.draw.rect(surf, PANEL_HI, r.inflate(30, 14), border_radius=10)
                    pygame.draw.rect(surf, YELLOW, r.inflate(30, 14), 2, border_radius=10)
                surf.blit(img, (x0, r.y))
                bx = x0 + img.get_width() + 14
                pygame.draw.rect(surf, (20, 22, 32), (bx, cy - 6, bar_w, 12), border_radius=6)
                pygame.draw.rect(surf, col, (bx, cy - 6, int(bar_w * vol / 100), 12), border_radius=6)
                pygame.draw.rect(surf, (120, 130, 160), (bx, cy - 6, bar_w, 12), 1, border_radius=6)
                pygame.draw.circle(surf, WHITE, (bx + int(bar_w * vol / 100), cy), 9)
                pygame.draw.circle(surf, (60, 60, 80), (bx + int(bar_w * vol / 100), cy), 9, 2)
                surf.blit(pct, (bx + bar_w + 14, cy - pct.get_height() // 2))
                continue
            img = self.text(self.f_med, label, col)
            r = img.get_rect(center=(SCREEN_W // 2, cy))
            if i == idx:
                pygame.draw.rect(surf, PANEL_HI, r.inflate(40, 14), border_radius=10)
                pygame.draw.rect(surf, YELLOW, r.inflate(40, 14), 2, border_radius=10)
            surf.blit(img, r)

    # ---------------------------------------------------------- home screens
    # Main menu -> Play (pick map + difficulty) / Settings / How to play
    def title_rows(self):
        rows = ["continue"] if self.save.get("resume") else []
        return rows + ["play", "towers", "settings", "help", "quit"]

    PLAY_ROWS = ["map", "mode", "start", "back"]
    SETTINGS_ROWS = ["auto", "sound", "buttons", "back"]

    def make_title_bg(self):
        """Sky, clouds and rolling hills behind the menus (drawn once)."""
        bg = self.gradient(SCREEN_W, SCREEN_H, (95, 165, 240), (200, 230, 255))
        rnd = random.Random(4)
        cloud = pygame.Surface((160, 70), pygame.SRCALPHA)
        for _ in range(6):
            cloud.fill((0, 0, 0, 0))
            for _ in range(6):
                pygame.draw.ellipse(cloud, (255, 255, 255, 150),
                                    (rnd.randint(0, 80), rnd.randint(10, 30), rnd.randint(50, 80), rnd.randint(28, 40)))
            bg.blit(cloud, (rnd.randint(-40, SCREEN_W - 100), rnd.randint(10, 330)))
        for col, base, amp, ph in (((120, 190, 100), 520, 30, 0.5), ((90, 165, 75), 560, 25, 2.0)):
            pts = [(x, base - amp * math.sin(x / 80 + ph)) for x in range(0, SCREEN_W + 10, 10)]
            pygame.draw.polygon(bg, col, pts + [(SCREEN_W, SCREEN_H), (0, SCREEN_H)])
        pts = [(x, 600 - 18 * math.sin(x / 60)) for x in range(0, SCREEN_W + 10, 10)]   # a dirt track
        pygame.draw.lines(bg, (170, 135, 85), False, pts, 30)
        pygame.draw.lines(bg, (214, 186, 130), False, pts, 24)
        return bg.convert()

    def draw_title_bg(self, surf):
        if not hasattr(self, "_title_bg"):
            self._title_bg = self.make_title_bg()
        surf.blit(self._title_bg, (0, 0))
        for x, y, name, _ in self.title_balloons:
            spr, ox, oy = self.balloon_sprites[(name, False)]
            surf.blit(spr, (x - ox, y - oy))

    def draw_logo(self, surf, y=62):
        for i, (word, col) in enumerate((("BALLOON", (255, 230, 80)), ("BLITZ", (255, 110, 110)))):
            img = self.text(self.f_big, word, col)
            out = self.text(self.f_big, word, (40, 30, 70))
            r = img.get_rect(center=(SCREEN_W // 2, y + i * 54))
            for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3), (4, 5)):   # thick outline + shadow
                surf.blit(out, r.move(dx, dy))
            surf.blit(img, r)

    def draw_button(self, surf, rect, label, selected, color=(70, 90, 150), sub=None):
        rect = pygame.Rect(rect)
        pygame.draw.rect(surf, (20, 25, 45), rect.move(0, 5), border_radius=14)   # shadow
        top = tuple(min(255, c + (40 if selected else 15)) for c in color)
        pygame.draw.rect(surf, top, rect, border_radius=14)
        pygame.draw.rect(surf, color, (rect.x, rect.centery, rect.w, rect.h // 2), border_bottom_left_radius=14,
                         border_bottom_right_radius=14)
        pygame.draw.rect(surf, YELLOW if selected else (25, 30, 50), rect, 3 if selected else 2, border_radius=14)
        img = self.text(self.f_med, label, YELLOW if selected else WHITE)
        cy = rect.centery - (8 if sub else 0)
        surf.blit(img, img.get_rect(center=(rect.centerx, cy)))
        if sub:
            img = self.text(self.f_small, sub, (220, 225, 240))
            surf.blit(img, img.get_rect(center=(rect.centerx, cy + 22)))

    def animate_title(self, dt):
        for b in self.title_balloons:
            b[1] -= b[3] * dt
            if b[1] < -30:
                b[0], b[1] = random.uniform(0, SCREEN_W), SCREEN_H + 30

    def menu_move(self, idx, n):
        if "UP" in self.inp.repeat:
            idx = (idx - 1) % n
        if "DOWN" in self.inp.repeat:
            idx = (idx + 1) % n
        return idx % n

    # ----- main menu
    def update_title(self, dt):
        self.animate_title(dt)
        rows = self.title_rows()
        self.title_idx = self.menu_move(self.title_idx, len(rows))
        if not ("A" in self.inp.pressed or "START" in self.inp.pressed):
            return
        row = rows[self.title_idx]
        if row == "continue":
            self.continue_game()
        elif row == "play":
            self.state, self.play_idx = "play", self.PLAY_ROWS.index("start")
        elif row == "settings":
            self.state, self.set_idx = "settings", 0
        elif row == "towers":
            self.open_guide(back="title")
        elif row == "help":
            self.state = "help"
        elif row == "quit":
            self.running = False

    def draw_title(self, surf):
        self.draw_title_bg(surf)
        self.draw_logo(surf)
        rows = self.title_rows()
        y = 186 if len(rows) > 5 else 205
        for i, row in enumerate(rows):
            sub = None
            if row == "continue":
                snap = self.save["resume"]
                label, color = "Continue", (60, 150, 90)
                sub = "%s  -  round %d" % (MAPS[snap["map"]]["name"], snap["round"] + 1)
            else:
                label = {"play": "Play", "towers": "Towers & Heroes", "settings": "Settings",
                         "help": "How to Play", "quit": "Quit"}[row]
                color = (215, 120, 40) if row == "play" else (120, 80, 160) if row == "towers" else (70, 90, 150)
            h = 60 if sub else 50
            self.draw_button(surf, (90, y, 300, h), label, i == self.title_idx, color, sub)
            y += h + 12
        img = self.text(self.f_small, "D-pad: choose    A: OK", (40, 60, 40))
        surf.blit(img, img.get_rect(center=(SCREEN_W // 2, 628 - 20)))
        img = self.text(self.f_tiny, VERSION, (40, 60, 90))
        surf.blit(img, (SCREEN_W - img.get_width() - 8, 6))

    # ----- play: pick a map and a difficulty
    def map_preview(self, idx, size):
        key = (idx, size)
        if key not in self._previews:
            self._previews[key] = pygame.transform.smoothscale(self.map_bg(idx), (size, size))
        return self._previews[key]

    def update_play(self, dt):
        self.animate_title(dt)
        self.play_idx = self.menu_move(self.play_idx, len(self.PLAY_ROWS))
        row = self.PLAY_ROWS[self.play_idx]
        step = ("RIGHT" in self.inp.repeat) - ("LEFT" in self.inp.repeat)
        if row == "map" and step:
            self.map_idx = (self.map_idx + step) % len(MAPS)
        elif row == "mode" and step:
            self.diff_idx = (self.diff_idx + step) % len(DIFFICULTIES)
        if "B" in self.inp.pressed or ("A" in self.inp.pressed and row == "back"):
            self.state = "title"
        elif ("A" in self.inp.pressed and row != "back") or "START" in self.inp.pressed:
            self.game = Game(self, self.map_idx, self.diff_idx)
            self.state = "game"

    def draw_play(self, surf):
        self.draw_title_bg(surf)
        row = self.PLAY_ROWS[self.play_idx]
        img = self.text(self.f_med, "Choose a Map", WHITE)
        out = self.text(self.f_med, "Choose a Map", (40, 30, 70))
        r = img.get_rect(center=(SCREEN_W // 2, 34))
        surf.blit(out, r.move(2, 3))
        surf.blit(img, r)
        # the map card
        card = pygame.Rect(60, 60, 360, 350)
        pygame.draw.rect(surf, (20, 25, 45), card.move(0, 6), border_radius=16)
        pygame.draw.rect(surf, (40, 48, 75), card, border_radius=16)
        pygame.draw.rect(surf, YELLOW if row == "map" else (90, 100, 140), card, 3, border_radius=16)
        prev = self.map_preview(self.map_idx, 230)
        pr = prev.get_rect(center=(SCREEN_W // 2, 190))
        pygame.draw.rect(surf, WHITE, pr.inflate(8, 8), border_radius=6)
        surf.blit(prev, pr)
        for side in (-1, 1):   # arrows to flip through maps
            ax = SCREEN_W // 2 + side * 152
            col = YELLOW if row == "map" else (150, 160, 190)
            pygame.draw.polygon(surf, col, [(ax + side * 12, 190), (ax - side * 6, 172), (ax - side * 6, 208)])
        mp = MAPS[self.map_idx]
        img = self.text(self.f_med, mp["name"], WHITE)
        surf.blit(img, img.get_rect(center=(SCREEN_W // 2, 334)))
        badge_col = {"Easy": (70, 180, 80), "Medium": (220, 170, 40), "Hard": (210, 70, 60)}[mp["level"]]
        badge = self.text(self.f_small, mp["level"], WHITE)
        best = self.best(self.map_idx, self.diff_idx)
        info = self.text(self.f_small, ("Best: round %d" % best) +
                         ("  - CHAMPION!" if best >= FINAL_ROUND else "  - beaten!" if best >= WIN_ROUND else ""),
                         (255, 220, 120) if best >= WIN_ROUND else (200, 205, 225))
        total = badge.get_width() + 24 + 14 + info.get_width()
        bx = SCREEN_W // 2 - total // 2
        br = pygame.Rect(bx, 360, badge.get_width() + 24, 30)
        pygame.draw.rect(surf, badge_col, br, border_radius=15)
        surf.blit(badge, badge.get_rect(center=br.center))
        surf.blit(info, (br.right + 14, br.centery - info.get_height() // 2))
        # difficulty
        diff = DIFFICULTIES[self.diff_idx]
        self.draw_button(surf, (90, 426, 300, 58), "< %s >" % diff["name"], row == "mode", (70, 90, 150),
                         "Endless money and lives" if diff.get("sandbox") else
                         "%d lives  -  $%d to start" % (diff["lives"], diff["money"] + mp.get("extra_money", 0)))
        self.draw_button(surf, (90, 500, 300, 56), "START!", row == "start", (60, 160, 70))
        self.draw_button(surf, (170, 572, 140, 42), "Back", row == "back", (90, 90, 110))

    # ----- towers & heroes: every upgrade, one tab per tower (L/R to switch)
    def wrap(self, text, font, width):
        words, lines, line = text.split(), [], ""
        for w in words:
            test = (line + " " + w).strip()
            if font.size(test)[0] <= width:
                line = test
            else:
                lines.append(line)
                line = w
        return lines + [line] if line else lines

    def open_guide(self, key=None, back="title"):
        """Open the Towers & Heroes screen (from the main menu or the in-game menu)."""
        if key:
            self.tab_idx = [tt["key"] for tt in SHOP].index(key)
        self.guide_back = back
        self.state = "towers"

    def update_towers(self, dt):
        inp = self.inp
        if "L" in inp.repeat or "LEFT" in inp.repeat or "UP" in inp.repeat:
            self.tab_idx = (self.tab_idx - 1) % len(SHOP)
        if "R" in inp.repeat or "RIGHT" in inp.repeat or "DOWN" in inp.repeat:
            self.tab_idx = (self.tab_idx + 1) % len(SHOP)
        if "B" in inp.pressed or "A" in inp.pressed:
            self.state = self.guide_back   # back to the main menu, or to the paused game

    def draw_towers(self, surf):
        surf.fill((30, 34, 50))
        tt = SHOP[self.tab_idx]
        # tab strip with every tower's icon
        pygame.draw.rect(surf, (22, 25, 38), (0, 0, SCREEN_W, 58))
        shown = 8
        first = max(0, min(self.tab_idx - shown // 2, len(SHOP) - shown))
        for i in range(first, first + shown):
            x = 26 + (i - first) * 54
            sel = i == self.tab_idx
            rect = pygame.Rect(x - 25, 4, 50, 50)
            pygame.draw.rect(surf, (70, 80, 120) if sel else (40, 45, 65), rect, border_radius=10)
            if sel:
                pygame.draw.rect(surf, YELLOW, rect, 3, border_radius=10)
            surf.blit(pygame.transform.smoothscale(self.icons[SHOP[i]["key"]], (40, 40)), (x - 20, 9))
        for side, show in ((-1, first > 0), (1, first + shown < len(SHOP))):
            if show:
                ax = 3 if side < 0 else SCREEN_W - 3
                pygame.draw.polygon(surf, YELLOW, [(ax, 29), (ax - side * 7, 21), (ax - side * 7, 37)])
        # the tower itself
        if tt.get("hero"):
            big = pygame.transform.smoothscale(self.hero_sprites[(tt["key"], False)], (78, 93))
        else:
            big = pygame.transform.smoothscale(self.icons[tt["key"]], (88, 88))
        surf.blit(big, big.get_rect(center=(62, 120)))
        surf.blit(self.text(self.f_med, tt["name"], YELLOW), (116, 70))
        kind = "Hero" if tt.get("hero") else "Water tower" if tt.get("water") else "Tower"
        surf.blit(self.text(self.f_small, "%s  -  $%d" % (kind, tt["cost"]), (160, 210, 255)), (116, 104))
        for j, line in enumerate(self.wrap(tt["desc"], self.f_small, 350)[:2]):
            surf.blit(self.text(self.f_small, line, WHITE), (116, 128 + j * 22))
        y = 180
        if tt.get("hero"):
            surf.blit(self.text(self.f_norm, "Levels up by itself: 1 to 20", (255, 215, 80)), (16, y))
            y += 36
            for lvl in (1, 10, 20):
                txt = "Level %2d:  %s" % (lvl, stat_summary(hero_stats(tt["key"], lvl)))
                surf.blit(self.text(self.f_small, txt[:44], (200, 210, 230)), (24, y))
                y += 28
            y += 12
            surf.blit(self.text(self.f_norm, "Abilities", (255, 215, 80)), (16, y))
            y += 34
            for lvl, aid in tt["abilities"]:
                name, cd, desc = ABILITIES[aid]
                card = pygame.Rect(16, y, SCREEN_W - 32, 64)
                pygame.draw.rect(surf, (45, 52, 80), card, border_radius=10)
                pygame.draw.rect(surf, (110, 220, 110), card, 2, border_radius=10)
                surf.blit(self.text(self.f_norm, "%s  (level %d)" % (name, lvl), WHITE), (28, y + 8))
                surf.blit(self.text(self.f_small, "%s  -  recharges in %ds" % (desc, cd), (190, 200, 220)), (28, y + 36))
                y += 76
        else:
            names = ("Top path", "Middle path (ability at level 4)", "Bottom path")
            for p, path in enumerate(tt["paths"]):
                surf.blit(self.text(self.f_small, names[p], PATH_COLORS[p]), (12, y))
                y += 22
                for k, (name, cost, desc, fx) in enumerate(path):
                    card = pygame.Rect(4 + k * 95, y, 91, 98)
                    pygame.draw.rect(surf, (55, 62, 95) if k >= 3 else (45, 52, 80), card, border_radius=8)
                    pygame.draw.rect(surf, PATH_COLORS[p], card, 3 if k >= 3 else 2, border_radius=8)
                    surf.blit(self.text(self.f_tiny, "LV%d" % (k + 1), PATH_COLORS[p]), (card.x + 5, card.y + 4))
                    cost_img = self.text(self.f_tiny, "$%d" % cost, GREEN)
                    surf.blit(cost_img, (card.right - cost_img.get_width() - 5, card.y + 4))
                    ab = "ability" in fx or "ab_power" in fx
                    title = ("* " if ab else "") + name
                    for j, line in enumerate(self.wrap(title, self.f_tiny, 83)[:2]):
                        surf.blit(self.text(self.f_tiny, line, YELLOW if ab else WHITE), (card.x + 5, card.y + 20 + j * 14))
                    for j, line in enumerate(self.wrap(desc, self.f_tiny, 83)[:3]):
                        surf.blit(self.text(self.f_tiny, line, (180, 190, 215)), (card.x + 5, card.y + 52 + j * 14))
                y += 106
            surf.blit(self.text(self.f_tiny, "* = ability (L + R).  One path can reach 5, another up to 2.",
                                (160, 170, 200)), (12, y))
        pygame.draw.rect(surf, (22, 25, 38), (0, SCREEN_H - 30, SCREEN_W, 30))
        img = self.text(self.f_small, "L / R: switch tab     B: back to " + ("game" if self.guide_back == "game" else "menu"),
                        (200, 205, 225))
        surf.blit(img, img.get_rect(center=(SCREEN_W // 2, SCREEN_H - 15)))

    # ----- settings
    def update_settings(self, dt):
        self.animate_title(dt)
        self.set_idx = self.menu_move(self.set_idx, len(self.SETTINGS_ROWS))
        row = self.SETTINGS_ROWS[self.set_idx]
        step = ("RIGHT" in self.inp.repeat) - ("LEFT" in self.inp.repeat)
        if "B" in self.inp.pressed or ("A" in self.inp.pressed and row == "back"):
            self.state = "title"
        elif row == "auto" and (step or "A" in self.inp.pressed):
            self.set_auto_start(not self.save.get("auto_start"))
        elif row == "sound":
            if step:
                self.change_volume(10 * step)
            elif "A" in self.inp.pressed:   # A on the slider: mute / unmute
                self.change_volume(-100 if self.save.get("volume", 70) else 70)
        elif row == "buttons" and "A" in self.inp.pressed:
            self.state = "buttons"
            self.btn_hold = 0.0

    def draw_settings(self, surf):
        self.draw_title_bg(surf)
        img = self.text(self.f_big, "Settings", WHITE)
        out = self.text(self.f_big, "Settings", (40, 30, 70))
        r = img.get_rect(center=(SCREEN_W // 2, 70))
        surf.blit(out, r.move(3, 4))
        surf.blit(img, r)
        panel = pygame.Rect(40, 130, 400, 360)
        pygame.draw.rect(surf, (20, 25, 45), panel.move(0, 6), border_radius=18)
        pygame.draw.rect(surf, (40, 48, 75), panel, border_radius=18)
        items = ["Auto-start: < %s >" % ("ON" if self.save.get("auto_start") else "OFF"),
                 SOUND_ROW, "Button test", "Back"]
        self.draw_menu_list(surf, items, self.set_idx, 190, 78)
        tips = {"auto": "Start the next round by itself",
                "sound": "LEFT/RIGHT: volume   A: mute",
                "buttons": "Check your handheld's buttons",
                "back": "Back to the main menu"}
        img = self.text(self.f_small, tips[self.SETTINGS_ROWS[self.set_idx]], (40, 60, 40))
        surf.blit(img, img.get_rect(center=(SCREEN_W // 2, 540)))

    HELP = [
        ("GOAL", YELLOW),
        ("Pop balloons before they reach the end.", WHITE),
        ("", WHITE),
        ("CONTROLS", YELLOW),
        ("D-pad: move cursor", WHITE),
        ("L / R: pick a tower or hero to build", WHITE),
        ("A: build, or open a tower's menu", WHITE),
        ("B: cancel / close / game menu", WHITE),
        ("START: next round / pause", WHITE),
        ("SELECT: speed 1x / 2x / 3x", WHITE),
        ("L + R together: use abilities", WHITE),
        ("", WHITE),
        ("TIPS", YELLOW),
        ("Middle path level 4 = an ability.", WHITE),
        ("One path can reach 5, another up to 2.", WHITE),
        ("One hero per game; it levels up to 20.", WHITE),
        ("Ships, subs and sharks go on water.", WHITE),
        ("Lead: bombs, fire or magic. Purple: no magic.", WHITE),
        ("Regrow balloons grow back: finish them!", WHITE),
        ("Beat round 150 to be Champion! (autosaves)", WHITE),
    ]

    def draw_help(self, surf):
        surf.fill(DARK)
        for i, (line, col) in enumerate(self.HELP):
            surf.blit(self.text(self.f_small, line, col), (20, 14 + i * 28))
        img = self.text(self.f_small, "Press A or B to go back", GRAY)
        surf.blit(img, img.get_rect(center=(SCREEN_W // 2, SCREEN_H - 20)))

    def update_buttons(self, dt):
        # Leave with Esc, or by holding any button for 3 seconds (so it
        # works even when the button numbers are set up wrong).
        if self.inp.held or self.any_raw_button():
            self.btn_hold += dt
        else:
            self.btn_hold = 0.0
        if self.btn_hold > 3.0:
            self.state = "title"

    def any_raw_button(self):
        for j in self.inp.joys.values():
            if any(j.get_button(i) for i in range(j.get_numbuttons())):
                return True
        return False

    def draw_buttons(self, surf):
        surf.fill(DARK)
        y = 16
        surf.blit(self.text(self.f_med, "Button test", YELLOW), (20, y))
        y += 50
        if not self.inp.joys:
            surf.blit(self.text(self.f_small, "No gamepad found. Keyboard only.", WHITE), (20, y))
            y += 34
        for j in self.inp.joys.values():
            surf.blit(self.text(self.f_small, j.get_name()[:32], GREEN), (20, y))
            y += 30
            down = [str(i) for i in range(j.get_numbuttons()) if j.get_button(i)]
            surf.blit(self.text(self.f_small, "Buttons down: " + (", ".join(down) or "-"), WHITE), (20, y))
            y += 30
            for h in range(j.get_numhats()):
                surf.blit(self.text(self.f_small, "Hat %d: %s" % (h, j.get_hat(h)), WHITE), (20, y))
                y += 30
            for a in range(min(4, j.get_numaxes())):
                surf.blit(self.text(self.f_small, "Axis %d: %+.2f" % (a, j.get_axis(a)), WHITE), (20, y))
                y += 30
            y += 10
        y += 10
        surf.blit(self.text(self.f_small, "Game sees: " + (" ".join(sorted(self.inp.held)) or "-"), YELLOW),
                  (20, y))
        y += 40
        for line in ("Press each button and write down", "its number. Then edit PAD_BUTTONS",
                     "at the top of balloon_blitz.py.", "", "Hold any button 3 sec to go back."):
            surf.blit(self.text(self.f_small, line, GRAY), (20, y))
            y += 30

    # ---------------------------------------------------------- main loop
    def run(self):
        for i in range(pygame.joystick.get_count()):
            self.inp.add_joystick(i)
        while self.running:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.1)
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.running = False
                elif e.type == pygame.JOYDEVICEADDED:
                    self.inp.add_joystick(e.device_index)
                elif e.type == pygame.JOYDEVICEREMOVED:
                    self.inp.remove_joystick(e.instance_id)
                elif self.on_event(e):
                    pass
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    if self.state == "game" and self.game and not self.game.overlay:
                        self.game.overlay, self.game.over_idx = "pause", 0
                    elif self.state == "title":
                        self.running = False
                    elif self.state != "game":
                        self.state = "title"
            self.inp.update(dt)

            if self.state == "title":
                self.update_title(dt)
                self.draw_title(self.canvas)
            elif self.state == "play":
                self.update_play(dt)
                if self.state == "play":
                    self.draw_play(self.canvas)
            elif self.state == "settings":
                self.update_settings(dt)
                if self.state == "settings":
                    self.draw_settings(self.canvas)
            elif self.state == "towers":
                self.update_towers(dt)
                if self.state == "towers":
                    self.draw_towers(self.canvas)
            elif self.state == "help":
                if "A" in self.inp.pressed or "B" in self.inp.pressed:
                    self.state = "title"
                self.draw_help(self.canvas)
            elif self.state == "buttons":
                self.update_buttons(dt)
                self.draw_buttons(self.canvas)
            elif self.state == "game":
                self.game.update(dt, self.inp)
                if self.game:   # may have quit to the title
                    self.game.draw(self.canvas)
            self.present()
            pygame.display.flip()

    def on_event(self, e):
        """Lets a subclass (the emulator) handle extra events. True = handled."""
        return False

    def present(self):
        if self.rotate:
            self.screen.blit(pygame.transform.rotate(self.canvas, self.rotate), (0, 0))


def main():
    global FPS
    ap = argparse.ArgumentParser(description="Balloon Blitz tower defense")
    ap.add_argument("--fullscreen", action="store_true", help="fill the whole screen (use on the handheld)")
    ap.add_argument("--rotate", type=int, choices=[0, 90, 180, 270], default=0,
                    help="turn the picture if your screen is mounted sideways")
    ap.add_argument("--buttons", action="store_true", help="start on the button test screen")
    ap.add_argument("--fps", type=int, default=FPS, help="frames per second (30 saves battery)")
    ap.add_argument("--mute", action="store_true", help="no sound")
    args = ap.parse_args()
    FPS = args.fps

    if not args.mute:
        pygame.mixer.pre_init(22050, -16, 1, 512)
    pygame.init()
    if args.mute:
        pygame.mixer.quit()
    pygame.display.set_caption("Balloon Blitz")
    flags = pygame.SCALED | (pygame.FULLSCREEN if args.fullscreen else 0)
    sideways = args.rotate in (90, 270)
    size = (SCREEN_H, SCREEN_W) if sideways else (SCREEN_W, SCREEN_H)
    screen = pygame.display.set_mode(size, flags)
    if args.fullscreen:
        pygame.mouse.set_visible(False)
    canvas = pygame.Surface((SCREEN_W, SCREEN_H)).convert() if args.rotate else screen
    app = App(screen, canvas, args.rotate)
    if args.buttons:
        app.state = "buttons"
    app.run()
    pygame.quit()


if __name__ == "__main__":
    main()
