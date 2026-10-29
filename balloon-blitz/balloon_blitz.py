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
SCREEN_W, SCREEN_H = 480, 640
HUD_H = 40                      # top bar (lives, money, round)
MAP_Y, MAP_H = HUD_H, 480       # the play field is a 480x480 square
PANEL_Y = MAP_Y + MAP_H         # bottom panel (shop / hints)
PANEL_H = SCREEN_H - PANEL_Y
FPS = 60
WIN_ROUND = 30                  # beat this round to win (then freeplay)
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
    "A": 0, "B": 1, "SELECT": 2, "START": 3, "L": 4, "R": 5,
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
}
REPEAT_DELAY, REPEAT_RATE = 0.35, 0.09   # menu auto-repeat when holding

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
}
BALLOON_ORDER = list(BALLOON_TYPES)   # used for "Strong" targeting
for _info in BALLOON_TYPES.values():
    _info.setdefault("immune", set())

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
    dict(key="dart", name="Dart Tower", cost=200,
         desc="Throws darts at one balloon",
         base=dict(range=130, rate=0.8, dmg=1, pierce=2, speed=540,
                   dtype="sharp", count=1, spread=0.0),
         paths=[
             [("Sharp Darts", 140, "Darts pop 1 more balloon", {"pierce": ("+", 1)}),
              ("Razor Darts", 220, "Darts pop 2 more balloons", {"pierce": ("+", 2)}),
              ("Triple Shot", 400, "Throws 3 darts at once",
               {"count": ("=", 3), "spread": ("=", 0.22)})],
             [("Long Range", 90, "+30 range", {"range": ("+", 30)}),
              ("Eagle Eye", 160, "Can see camo balloons",
               {"camo": ("=", True), "range": ("+", 15)}),
              ("Rapid Fire", 500, "Throws twice as fast", {"rate": ("*", 0.5)})],
         ]),
    dict(key="tack", name="Tack Shooter", cost=280,
         desc="Fires tacks in every direction",
         base=dict(range=95, rate=1.05, dmg=1, pierce=1, speed=380,
                   dtype="sharp", count=8),
         paths=[
             [("Quick Spin", 150, "Shoots 20% faster", {"rate": ("*", 0.8)}),
              ("Faster Spin", 260, "Shoots 25% faster", {"rate": ("*", 0.75)}),
              ("Blade Ring", 750, "8 more blades, each pops 3",
               {"count": ("+", 8), "pierce": ("+", 2)})],
             [("Long Reach", 100, "+15 range", {"range": ("+", 15)}),
              ("More Tacks", 250, "+4 tacks per shot", {"count": ("+", 4)}),
              ("Ring of Fire", 1100, "Fire: 2 damage, pops lead",
               {"dtype": ("=", "normal"), "dmg": ("+", 1)})],
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
    dict(key="wizard", name="Wizard", cost=400,
         desc="Magic pops every balloon type",
         base=dict(range=120, rate=1.1, dmg=1, pierce=3, speed=330,
                   dtype="normal", homing=False, chain=0, breath=False),
         paths=[
             [("Arcane Blast", 300, "Magic does 1 more damage", {"dmg": ("+", 1)}),
              ("Arcane Mastery", 700, "Casts faster, pops 2 more",
               {"rate": ("*", 0.6), "pierce": ("+", 2)}),
              ("Lightning Bolt", 1600, "Lightning jumps to 8 balloons", {"chain": ("=", 8)})],
             [("Guided Magic", 250, "Magic bolts chase balloons", {"homing": ("=", True)}),
              ("Wizard Sight", 300, "Sees camo, +20 range",
               {"camo": ("=", True), "range": ("+", 20)}),
              ("Dragon's Breath", 1300, "Adds a flamethrower", {"breath": ("=", True)})],
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
TARGET_MODES = ["First", "Last", "Strong", "Close"]

# =====================================================================
# Maps (coordinates inside the 480x480 play field)
# =====================================================================
MAPS = [
    dict(name="Meadow", level="Easy", seed=3,
         path=[(-30, 60), (400, 60), (400, 180), (80, 180), (80, 300),
               (400, 300), (400, 420), (240, 420), (240, 520)]),
    dict(name="Crossroads", level="Medium", seed=7,
         path=[(-30, 240), (360, 240), (360, 80), (120, 80), (120, 400),
               (400, 400), (400, 520)]),
    dict(name="Rapids", level="Hard", seed=11,
         path=[(240, -30), (240, 160), (420, 160), (420, 330), (60, 330),
               (60, 520)]),
]

DIFFICULTIES = [
    dict(name="Easy", lives=200, cost=0.8, speed=0.95),
    dict(name="Normal", lives=150, cost=1.0, speed=1.0),
    dict(name="Hard", lives=100, cost=1.08, speed=1.1),
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
    [("green", 30, 0.35, 0), ("yellow", 15, 0.6, 4), ("pink", 6, 1.0, 10)],
    [("pink", 15, 0.8, 0), ("yellow", 25, 0.4, 3)],
    [("black", 12, 0.8, 0), ("white", 12, 0.8, 5)],
    [("yellow", 20, 0.5, 0), ("pink", 15, 0.6, 4), ("green", 8, 0.8, 8, True)],
    [("lead", 8, 1.5, 0), ("yellow", 25, 0.4, 2)],
    [("pink", 30, 0.4, 0), ("black", 10, 0.7, 6)],
    [("zebra", 10, 1.0, 0), ("pink", 20, 0.4, 3)],
    [("zebra", 8, 0.8, 0), ("lead", 10, 1.0, 4), ("pink", 8, 0.8, 6, True)],
    [("zebra", 15, 0.7, 0), ("rainbow", 5, 1.5, 6)],                       # 21
    [("rainbow", 10, 1.0, 0), ("lead", 8, 0.8, 5)],
    [("ceramic", 3, 2.5, 0), ("zebra", 15, 0.5, 3), ("black", 8, 0.6, 8, True)],
    [("rainbow", 14, 0.8, 0), ("ceramic", 3, 2.0, 6)],
    [("ceramic", 4, 1.5, 0), ("blimp", 1, 1, 10)],
    [("zebra", 12, 0.6, 0, True), ("ceramic", 6, 1.2, 6)],
    [("lead", 15, 0.5, 0), ("ceramic", 8, 1.0, 4)],
    [("ceramic", 12, 0.8, 0), ("blimp", 1, 1, 10)],
    [("ceramic", 6, 0.9, 0, True), ("ceramic", 6, 0.9, 6), ("blimp", 2, 4, 10)],
    [("blimp", 2, 3, 0), ("titan", 1, 1, 8)],
]


def freeplay_round(n):
    """Rounds after the last designed one keep getting harder."""
    k = n - len(ROUNDS)
    groups = [("ceramic", 20 + 3 * k, max(0.15, 0.5 - 0.01 * k), 0, k % 2 == 0),
              ("blimp", 2 + k // 2, max(0.8, 2.5 - 0.08 * k), 6)]
    if k >= 3:
        groups.append(("titan", k // 3, 6, 15))
    return groups


def round_cost(base, mult):
    return int(round(base * mult / 5.0)) * 5


# =====================================================================
# Input: keyboard + gamepad, turned into 10 simple actions
# =====================================================================
ACTIONS = ("UP", "DOWN", "LEFT", "RIGHT", "A", "B", "L", "R", "START", "SELECT")


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

    def play(self, name):
        if not self.ok:
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
                 "frozen", "slow", "id", "speed_now", "rank", "r")

    def __init__(self, name, dist, camo, bid, hp_mult):
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


class Tower:
    def __init__(self, ttype, x, y, cost):
        self.t = ttype
        self.key = ttype["key"]
        self.x, self.y = x, y
        self.levels = [0, 0]
        self.spent = cost
        self.cool = 0.2
        self.angle = -math.pi / 2
        self.target_mode = 2 if self.key == "sniper" else 0
        self.pops = 0
        self.flash = 0.0
        self.cool2 = 0.0          # Dragon's Breath flamethrower
        self.recalc()

    def recalc(self):
        s = dict(self.t["base"])
        for p in (0, 1):
            for i in range(self.levels[p]):
                for k, (op, v) in self.t["paths"][p][i][3].items():
                    if op == "+":
                        s[k] = s.get(k, 0) + v
                    elif op == "*":
                        s[k] = s.get(k, 1) * v
                    else:
                        s[k] = v
        self.s = s

    def upgrade_state(self, p):
        """Returns 'ok', 'max' or 'locked' for upgrade path p."""
        lv = self.levels[p]
        if lv >= 3:
            return "max"
        if lv + 1 == 3 and self.levels[1 - p] == 3:
            return "locked"
        return "ok"


class Proj:
    __slots__ = ("kind", "x", "y", "vx", "vy", "life", "dmg", "pierce", "dtype",
                 "r", "hit", "tower", "blast", "cluster", "bm", "dead", "angle", "homing")

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


# =====================================================================
# Sprite drawing (done once at start, then just copied each frame)
# =====================================================================
def darker(c, f=0.6):
    return tuple(int(v * f) for v in c[:3])


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
    pygame.draw.circle(s, dark, (c, c), r, 2)
    pygame.draw.circle(s, (255, 255, 255, 180), (c - r // 3, c - r // 3), max(2, r // 4))
    if camo:
        spots = [(-0.4, 0.1, 0.32), (0.35, -0.3, 0.28), (0.2, 0.45, 0.25), (-0.1, -0.5, 0.2)]
        for i, (sx, sy, sr) in enumerate(spots):
            pygame.draw.circle(s, (70, 100, 40) if i % 2 else (110, 130, 60),
                               (int(c + sx * r), int(c + sy * r)), max(2, int(sr * r)))
        pygame.draw.circle(s, (40, 70, 30), (c, c), r, 2)
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
    pygame.draw.ellipse(s, darker(col, 0.8), body.inflate(-w // 3, -h // 2))
    pygame.draw.line(s, (240, 240, 240), (6 + int(w * 0.62), 8), (6 + int(w * 0.62), h + 2), 4)
    pygame.draw.ellipse(s, dark, body, 3)
    pygame.draw.ellipse(s, (255, 255, 255, 140), (6 + w // 2, 9, w // 4, h // 5))
    cx = s.get_width() // 2
    out = {"R": (s, cx, cy), "L": (pygame.transform.flip(s, True, False), cx, cy)}
    down = pygame.transform.rotate(s, -90)
    up = pygame.transform.rotate(s, 90)
    out["D"] = (down, down.get_width() // 2, down.get_height() // 2)
    out["U"] = (up, up.get_width() // 2, up.get_height() // 2)
    return out


def make_tower_sprite(key, font):
    s = pygame.Surface((44, 44), pygame.SRCALPHA)
    c = 22
    r = TOWER_R
    if key == "dart":
        pygame.draw.circle(s, (125, 82, 45), (c, c), r)
        pygame.draw.circle(s, (195, 150, 100), (c, c), r - 7)
        pygame.draw.circle(s, (60, 40, 20), (c, c), r, 2)
    elif key == "tack":
        pts = [(c + r * math.cos(i * math.pi / 4 + math.pi / 8), c + r * math.sin(i * math.pi / 4 + math.pi / 8))
               for i in range(8)]
        pygame.draw.polygon(s, (155, 155, 168), pts)
        pygame.draw.polygon(s, (70, 70, 80), pts, 2)
        pygame.draw.circle(s, (80, 80, 92), (c, c), 7)
        for i in range(8):
            a = i * math.pi / 4
            pygame.draw.circle(s, (230, 230, 240), (int(c + (r - 4) * math.cos(a)), int(c + (r - 4) * math.sin(a))), 2)
    elif key == "bomb":
        pygame.draw.circle(s, (62, 62, 70), (c, c), r)
        pygame.draw.circle(s, (105, 105, 118), (c, c), r - 7)
        pygame.draw.circle(s, (20, 20, 24), (c, c), r, 2)
    elif key == "frost":
        pygame.draw.circle(s, (150, 210, 245), (c, c), r)
        pygame.draw.circle(s, (70, 140, 200), (c, c), r, 2)
        for i in range(3):
            a = i * math.pi / 3
            dx, dy = math.cos(a) * (r - 4), math.sin(a) * (r - 4)
            pygame.draw.line(s, WHITE, (c - dx, c - dy), (c + dx, c + dy), 3)
    elif key == "sniper":
        pygame.draw.circle(s, (92, 112, 60), (c, c), r)
        pygame.draw.circle(s, (135, 155, 85), (c, c), r - 8)
        pygame.draw.circle(s, (40, 55, 25), (c, c), r, 2)
    elif key == "wizard":
        pygame.draw.circle(s, (110, 60, 170), (c, c), r)
        pygame.draw.circle(s, (55, 25, 95), (c, c), r, 2)
        pygame.draw.polygon(s, (70, 40, 140), [(c - 11, c + 6), (c + 11, c + 6), (c + 2, c - 15)])
        pygame.draw.polygon(s, (40, 20, 80), [(c - 11, c + 6), (c + 11, c + 6), (c + 2, c - 15)], 2)
        pygame.draw.circle(s, (255, 225, 80), (c + 1, c - 2), 3)
    elif key == "mine":
        rect = pygame.Rect(c - r + 1, c - r + 1, 2 * r - 2, 2 * r - 2)
        pygame.draw.rect(s, (205, 165, 45), rect, border_radius=6)
        pygame.draw.rect(s, (110, 75, 20), rect, 3, border_radius=6)
        t = font.render("$", True, (110, 75, 20))
        s.blit(t, t.get_rect(center=(c, c + 1)))
    return s


BARRELS = {   # (length, width, color) of the part that points at balloons
    "dart": (22, 5, (70, 45, 25)),
    "bomb": (19, 10, (30, 30, 34)),
    "sniper": (28, 4, (40, 50, 25)),
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
        self.path = Path([(x, y + MAP_Y) for x, y in self.mp["path"]])
        self.reset()

    def reset(self):
        self.balloons = []
        self.towers = []
        self.projs = []
        self.fx = []                # visual effects
        self.money = START_MONEY
        self.lives = self.diff["lives"]
        self.round = 0              # the round being played / last played
        self.active = False         # is a round running?
        self.queue = []
        self.qi = 0
        self.rtime = 0.0
        self.fast = False
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
        self.hp_mult = 1.0
        self.grid = {}

    # ---------------------------------------------------------- helpers
    def cost(self, base):
        return round_cost(base, self.diff["cost"])

    def toast(self, text, secs=1.6):
        self.toast_text, self.toast_t = text, secs

    def tower_at(self, x, y):
        for t in self.towers:
            if (t.x - x) ** 2 + (t.y - y) ** 2 <= (TOWER_R + 4) ** 2:
                return t
        return None

    def can_place(self, x, y):
        if not (TOWER_R <= x <= SCREEN_W - TOWER_R and MAP_Y + TOWER_R <= y <= MAP_Y + MAP_H - TOWER_R):
            return False
        if self.path.distance_to(x, y) < PATH_W / 2 + TOWER_R - 2:
            return False
        for t in self.towers:
            if (t.x - x) ** 2 + (t.y - y) ** 2 < (TOWER_R * 2) ** 2:
                return False
        return True

    def spawn_balloon(self, name, dist, camo, seg=0):
        b = Balloon(name, max(0.0, dist), camo, self.next_id, self.hp_mult)
        self.next_id += 1
        b.x, b.y, b.seg = self.path.pos(b.dist, seg)
        self.balloons.append(b)
        return b

    def add_fx(self, kind, x, y, dur, data=None):
        if len(self.fx) > 90:
            self.fx.pop(0)
        self.fx.append([kind, x, y, 0.0, dur, data])

    # ---------------------------------------------------------- rounds
    def start_round(self):
        self.round += 1
        groups = ROUNDS[self.round - 1] if self.round <= len(ROUNDS) else freeplay_round(self.round)
        q = []
        for g in groups:
            name, count, spacing, delay = g[:4]
            camo = g[4] if len(g) > 4 else False
            for i in range(count):
                q.append((delay + i * spacing, name, camo))
        q.sort(key=lambda e: e[0])
        self.queue, self.qi, self.rtime = q, 0, 0.0
        self.hp_mult = 1.0 + max(0, self.round - len(ROUNDS)) * 0.06
        self.active = True
        self.auto_wait = 0.0

    def end_round(self):
        self.active = False
        bonus = 120 + 3 * self.round
        income = 0
        lives = 0
        for t in self.towers:
            if t.key == "mine":
                pay = int(t.s["income"] * t.s["mult"])
                income += pay
                lives += t.s["lives"]
                self.add_fx("text", t.x, t.y - 20, 1.2, "+$%d" % pay)
        self.money += bonus + income
        self.lives += lives
        self.app.record_best(self.map_idx, self.diff_idx, self.round)
        self.toast("Round %d done! +$%d" % (self.round, bonus + income))
        if self.round == WIN_ROUND and not self.won:
            self.won = True
            self.overlay, self.over_idx = "win", 0
        if self.auto:
            self.auto_wait = AUTO_START_DELAY

    # ---------------------------------------------------------- damage
    def damage(self, b, dmg, dtype, proj=None, tower=None):
        if not b.alive:
            return
        if dtype in b.info["immune"]:
            self.add_fx("clink", b.x, b.y, 0.15)
            return
        b.hp -= dmg
        if b.hp > 0:
            return
        leftover = -b.hp
        b.alive = False
        self.money += 1
        if tower:
            tower.pops += 1
        self.add_fx("pop", b.x, b.y, 0.18, b.info["color"])
        self.app.sounds.play("pop")
        kids = []
        for i, child in enumerate(b.info["children"]):
            nb = self.spawn_balloon(child, b.dist - i * 9, b.camo, b.seg)
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
            if mode == "First":
                v = b.dist
            elif mode == "Last":
                v = -b.dist
            elif mode == "Strong":
                v = b.rank * 100000 + b.dist
            else:
                v = -d2
            if bestv is None or v > bestv:
                best, bestv = b, v
        return best

    def lead(self, t, b, speed):
        """Aim where the balloon will be when the shot arrives."""
        d = math.hypot(b.x - t.x, b.y - t.y)
        future = b.dist + b.speed_now * d / speed
        if future >= self.path.total:
            return b.x, b.y
        x, y, _ = self.path.pos(future, b.seg)
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
                    self.projs.append(Proj("fire", t.x, t.y, a, 320, 0.36, 1, 2, "normal", 8, t))
        t.cool -= dt
        if t.cool > 0:
            return
        if t.key == "frost":
            t.cool = s["rate"] if self.frost_pulse(t) else 0.1
            return
        tgt = self.find_target(t)
        if tgt is None:
            t.cool = 0.05
            return
        t.cool = s["rate"]
        t.flash = 0.08
        if t.key == "dart":
            ax, ay = self.lead(t, tgt, s["speed"])
            t.angle = math.atan2(ay - t.y, ax - t.x)
            n = s["count"]
            for i in range(n):
                a = t.angle + s["spread"] * (i - (n - 1) / 2)
                self.projs.append(Proj("dart", t.x + math.cos(a) * 16, t.y + math.sin(a) * 16, a, s["speed"],
                                       (s["range"] + 40) / s["speed"], s["dmg"], s["pierce"], s["dtype"], 5, t))
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

    def lightning(self, t, first, jumps, dmg):
        """Lightning hits one balloon, then jumps to the nearest new one."""
        hit = set()
        x0, y0 = t.x, t.y
        b = first
        for _ in range(jumps):
            hit.add(b.id)
            self.add_fx("bolt", x0, y0, 0.12, (b.x, b.y))
            x0, y0 = b.x, b.y
            self.damage(b, dmg, "normal", None, t)
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
        hits.sort(key=lambda b: -b.dist)
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
        if self.active:
            self.rtime += dt
            while self.qi < len(self.queue) and self.queue[self.qi][0] <= self.rtime:
                _, name, camo = self.queue[self.qi]
                self.qi += 1
                self.spawn_balloon(name, 0.0, camo)

        base = BALLOON_SPEED * self.diff["speed"]
        total = self.path.total
        for b in self.balloons:
            if not b.alive:
                continue
            sp = base * b.info["speed"]
            if b.frozen > 0:
                b.frozen -= dt
                sp = sp * 0.5 if b.info.get("blimp") else 0.0
            elif b.slow > 0:
                b.slow -= dt
                sp *= 0.5
            b.speed_now = sp
            b.dist += sp * dt
            if b.dist >= total:
                b.alive = False
                self.lives -= self.rbe_left(b)
                self.app.sounds.play("leak")
            else:
                b.x, b.y, b.seg = self.path.pos(b.dist, b.seg)

        self.build_grid()
        for t in self.towers:
            self.update_tower(t, dt)

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
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.life -= dt
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
                    self.damage(b, p.dmg * (p.bm if b.info.get("blimp") else 1), p.dtype, p, p.tower)
                    p.pierce -= 1
                    if p.pierce <= 0:
                        p.dead = True
                        break

        self.balloons = [b for b in self.balloons if b.alive]
        self.projs = [p for p in self.projs if not p.dead]

        if self.lives <= 0:
            self.lives = 0
            self.active = False
            self.overlay, self.over_idx = "over", 0
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
            self.fast = not self.fast
            self.toast("Speed: %s" % ("FAST >>" if self.fast else "Normal"), 1.0)
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

        if self.mode == "menu":
            self.update_menu(inp)
        else:
            self.move_cursor(dt, inp)
            if self.mode == "normal":
                self.update_normal(inp)
            else:
                self.update_place(inp)

        # Simulate in small steps so fast shots don't skip past balloons.
        sim = dt * (2 if self.fast else 1)
        steps = max(1, min(8, int(math.ceil(sim / (1 / 60.0)))))
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
            self.shop = (self.shop - 1) % len(TOWER_TYPES)
        if "R" in inp.repeat:
            self.shop = (self.shop + 1) % len(TOWER_TYPES)
        if "B" in inp.pressed:
            self.mode = "normal"
        if "A" in inp.pressed:
            tt = TOWER_TYPES[self.shop]
            cost = self.cost(tt["cost"])
            existing = self.tower_at(self.cx, self.cy)
            if existing:
                self.open_menu(existing)
            elif self.money < cost:
                self.toast("Need $%d more" % (cost - self.money))
                self.app.sounds.play("error")
            elif not self.can_place(self.cx, self.cy):
                self.toast("Can't build there")
                self.app.sounds.play("error")
            else:
                self.money -= cost
                self.towers.append(Tower(tt, self.cx, self.cy, cost))
                self.app.sounds.play("place")
                self.mode = "normal"

    def open_menu(self, t):
        self.sel = t
        self.mode = "menu"
        self.menu = 0

    def update_menu(self, inp):
        t = self.sel
        if "UP" in inp.repeat:
            self.menu = (self.menu - 1) % 4
        if "DOWN" in inp.repeat:
            self.menu = (self.menu + 1) % 4
        if "B" in inp.pressed:
            self.mode = "normal"
            return
        if ("L" in inp.pressed or "R" in inp.pressed) and len(self.towers) > 1:
            i = self.towers.index(t) + (1 if "R" in inp.pressed else -1)
            self.sel = t = self.towers[i % len(self.towers)]
            self.cx, self.cy = t.x, t.y
        if self.menu == 2 and t.key not in ("mine", "frost"):
            if "LEFT" in inp.repeat:
                t.target_mode = (t.target_mode - 1) % len(TARGET_MODES)
            if "RIGHT" in inp.repeat or "A" in inp.pressed:
                t.target_mode = (t.target_mode + 1) % len(TARGET_MODES)
        if "A" not in inp.pressed:
            return
        if self.menu in (0, 1):
            p = self.menu
            state = t.upgrade_state(p)
            if state == "max":
                self.toast("That path is maxed out")
            elif state == "locked":
                self.toast("Only one path can reach level 3")
            else:
                cost = self.cost(t.t["paths"][p][t.levels[p]][1])
                if self.money < cost:
                    self.toast("Need $%d more" % (cost - self.money))
                    self.app.sounds.play("error")
                else:
                    self.money -= cost
                    t.spent += cost
                    t.levels[p] += 1
                    t.recalc()
                    self.app.sounds.play("upgrade")
                    self.add_fx("ring", t.x, t.y, 0.3, (TOWER_R + 10, YELLOW))
        elif self.menu == 3:
            value = int(t.spent * SELL_RATE)
            self.money += value
            self.towers.remove(t)
            self.add_fx("text", t.x, t.y, 1.0, "+$%d" % value)
            self.mode = "normal"

    def overlay_items(self):
        if self.overlay == "pause":
            return ["Resume", "Auto-start: %s" % ("ON" if self.auto else "OFF"), "Restart", "Quit to title"]
        if self.overlay == "win":
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
        if "A" not in inp.pressed:
            return
        choice = items[self.over_idx]
        if choice in ("Resume", "Keep playing"):
            self.overlay = None
        elif choice.startswith("Auto-start"):
            self.auto = not self.auto
            self.app.set_auto_start(self.auto)
            if self.auto and self.round > 0 and not self.active:
                self.auto_wait = AUTO_START_DELAY
        elif choice in ("Restart", "Try again"):
            self.reset()
        elif choice == "Quit to title":
            self.app.go_title()

    # ---------------------------------------------------------- drawing
    def draw(self, surf):
        app = self.app
        surf.blit(app.map_bg(self.map_idx), (0, MAP_Y))

        for t in self.towers:
            self.draw_tower(surf, t)

        for b in self.balloons:
            if b.info.get("blimp"):
                ux, uy = self.path.segs[b.seg][2:4]
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
                surf.blit(spr, (b.x - ox, b.y - oy))
                if b.frozen > 0:
                    surf.blit(app.ice_sprite(b.r), (b.x - b.r - 3, b.y - b.r - 3))

        for p in self.projs:
            if p.kind == "dart":
                ex, ey = math.cos(p.angle) * 9, math.sin(p.angle) * 9
                pygame.draw.line(surf, (60, 40, 20), (p.x - ex, p.y - ey), (p.x + ex, p.y + ey), 4)
                pygame.draw.circle(surf, (230, 230, 230), (int(p.x + ex), int(p.y + ey)), 2)
            elif p.kind == "bolt":
                pygame.draw.circle(surf, (190, 120, 255), (int(p.x), int(p.y)), 7)
                pygame.draw.circle(surf, (245, 225, 255), (int(p.x), int(p.y)), 3)
            elif p.kind == "fire":
                pygame.draw.circle(surf, (255, 120, 20), (int(p.x), int(p.y)), 8)
                pygame.draw.circle(surf, (255, 230, 90), (int(p.x), int(p.y)), 4)
            elif p.kind == "tack":
                col = (255, 140, 30) if p.dtype == "normal" else (220, 220, 230)
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
            tt = TOWER_TYPES[self.shop]
            ok = self.can_place(self.cx, self.cy) and self.money >= self.cost(tt["cost"])
            self.draw_range(surf, self.cx, self.cy, tt["base"]["range"], ok)
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
        if self.mode == "menu" and self.sel:
            self.draw_menu(surf)
        if self.auto_wait > 0 and not self.active:
            t = app.text(app.f_norm, "Next round in %d..." % math.ceil(self.auto_wait), YELLOW)
            r = t.get_rect(center=(SCREEN_W // 2, MAP_Y + 72))
            pygame.draw.rect(surf, DARK, r.inflate(20, 10), border_radius=8)
            surf.blit(t, r)
        if self.toast_t > 0:
            t = app.text(app.f_norm, self.toast_text, WHITE)
            r = t.get_rect(center=(SCREEN_W // 2, MAP_Y + 30))
            pygame.draw.rect(surf, DARK, r.inflate(20, 10), border_radius=8)
            surf.blit(t, r)
        if self.overlay:
            self.draw_overlay(surf)

    def draw_range(self, surf, x, y, r, ok):
        if 0 < r < 600:
            spr = self.app.range_sprite(int(r), ok)
            surf.blit(spr, (x - spr.get_width() // 2, y - spr.get_height() // 2))

    def draw_tower(self, surf, t):
        surf.blit(self.app.tower_sprites[t.key], (t.x - 22, t.y - 22))
        if t.key in BARRELS:
            length, width, col = BARRELS[t.key]
            if t.flash > 0:
                length -= 4
            ex, ey = t.x + math.cos(t.angle) * length, t.y + math.sin(t.angle) * length
            pygame.draw.line(surf, col, (t.x, t.y), (ex, ey), width)
            pygame.draw.circle(surf, col, (int(t.x), int(t.y)), width // 2 + 3)
        for p, col, x0 in ((0, (255, 120, 80), t.x - 17), (1, (90, 170, 255), t.x + 3)):
            for i in range(3):
                rect = (x0 + i * 5, t.y + TOWER_R + 2, 4, 4)
                pygame.draw.rect(surf, col if i < t.levels[p] else (40, 40, 40), rect)

    def draw_fx(self, surf):
        app = self.app
        for kind, x, y, t, dur, data in self.fx:
            p = t / dur
            if kind == "pop":
                r = 6 + 14 * p
                for i in range(6):
                    a = i * math.pi / 3 + 0.4
                    pygame.draw.line(surf, data, (x + math.cos(a) * r * 0.5, y + math.sin(a) * r * 0.5),
                                     (x + math.cos(a) * r, y + math.sin(a) * r), 3)
            elif kind == "ring":
                rad, col = data
                pygame.draw.circle(surf, col, (int(x), int(y)), max(3, int(rad * (0.4 + 0.6 * p))), 3)
            elif kind == "line":
                pygame.draw.line(surf, (255, 255, 200), (x, y), data, 2)
            elif kind == "bolt":
                mx = (x + data[0]) / 2 + random.uniform(-8, 8)
                my = (y + data[1]) / 2 + random.uniform(-8, 8)
                pygame.draw.lines(surf, (200, 230, 255), False, [(x, y), (mx, my), data], 3)
            elif kind == "clink":
                pygame.draw.circle(surf, (200, 200, 210), (int(x), int(y)), 4 + int(6 * p), 2)
            elif kind == "text":
                img = app.text(app.f_small, data, YELLOW)
                surf.blit(img, img.get_rect(center=(x, y - 25 * p)))

    def draw_hud(self, surf):
        app = self.app
        pygame.draw.rect(surf, HUD_BG, (0, 0, SCREEN_W, HUD_H))
        # heart
        pygame.draw.circle(surf, RED, (14, 17), 7)
        pygame.draw.circle(surf, RED, (26, 17), 7)
        pygame.draw.polygon(surf, RED, [(7, 19), (33, 19), (20, 33)])
        surf.blit(app.text(app.f_norm, str(self.lives), WHITE), (40, 8))
        # coin
        pygame.draw.circle(surf, YELLOW, (130, 20), 11)
        pygame.draw.circle(surf, (180, 140, 30), (130, 20), 11, 2)
        surf.blit(app.text(app.f_norm, "%d" % self.money, WHITE), (147, 8))
        if self.auto:
            img = app.text(app.f_small, "AUTO", DARK)
            r = img.get_rect(midleft=(236, 21))
            pygame.draw.rect(surf, GREEN, r.inflate(10, 6), border_radius=6)
            surf.blit(img, r)
        rtxt = "Round %d/%d" % (max(1, self.round), WIN_ROUND) if self.round <= WIN_ROUND \
            else "Round %d" % self.round
        img = app.text(app.f_norm, rtxt, WHITE)
        surf.blit(img, (SCREEN_W - img.get_width() - (44 if self.fast else 10), 8))
        if self.fast:
            for i in range(2):
                x = SCREEN_W - 36 + i * 13
                pygame.draw.polygon(surf, YELLOW, [(x, 11), (x + 12, 20), (x, 29)])

    def draw_shop_strip(self, surf, highlight):
        app = self.app
        slot_w = SCREEN_W // len(TOWER_TYPES)
        for i, tt in enumerate(TOWER_TYPES):
            x = i * slot_w
            cost = self.cost(tt["cost"])
            if highlight and i == self.shop:
                pygame.draw.rect(surf, PANEL_HI, (x + 2, PANEL_Y + 3, slot_w - 4, 62), border_radius=6)
                pygame.draw.rect(surf, YELLOW, (x + 2, PANEL_Y + 3, slot_w - 4, 62), 2, border_radius=6)
            spr = app.tower_sprites[tt["key"]]
            surf.blit(spr, (x + slot_w // 2 - 22, PANEL_Y + 2))
            img = app.text(app.f_small, "$%d" % cost, GREEN if self.money >= cost else (230, 110, 110))
            surf.blit(img, img.get_rect(center=(x + slot_w // 2, PANEL_Y + 54)))

    def draw_panel(self, surf):
        app = self.app
        pygame.draw.rect(surf, PANEL_BG, (0, PANEL_Y, SCREEN_W, PANEL_H))
        pygame.draw.line(surf, (80, 85, 105), (0, PANEL_Y), (SCREEN_W, PANEL_Y), 2)
        if self.mode == "place":
            self.draw_shop_strip(surf, True)
            tt = TOWER_TYPES[self.shop]
            surf.blit(app.text(app.f_norm, tt["name"], WHITE), (10, PANEL_Y + 68))
            hint = app.text(app.f_small, "A: build  B: back", GRAY)
            surf.blit(hint, (SCREEN_W - hint.get_width() - 10, PANEL_Y + 72))
            surf.blit(app.text(app.f_small, tt["desc"], (200, 205, 220)), (10, PANEL_Y + 95))
        else:
            self.draw_shop_strip(surf, False)
            if self.mode == "menu":
                l1, l2 = "UP/DOWN: choose  A: OK", "L/R: next tower  B: close"
            elif self.active:
                l1, l2 = "L/R: buy  A: tower  B: menu", "START: pause  SELECT: speed"
            else:
                l1, l2 = "L/R: buy  A: tower  B: menu", "START: next round  SELECT: speed"
            surf.blit(app.text(app.f_small, l1, (200, 205, 220)), (10, PANEL_Y + 70))
            surf.blit(app.text(app.f_small, l2, (200, 205, 220)), (10, PANEL_Y + 95))

    def draw_menu(self, surf):
        """Upgrade menu for the selected tower, drawn over the map."""
        app = self.app
        t = self.sel
        h = 214
        y0 = MAP_Y + MAP_H - h - 4 if t.y < MAP_Y + MAP_H / 2 else MAP_Y + 4
        box = pygame.Rect(6, y0, SCREEN_W - 12, h)
        pygame.draw.rect(surf, (28, 32, 46), box, border_radius=10)
        pygame.draw.rect(surf, (110, 120, 150), box, 2, border_radius=10)
        title = "%s  (popped %d)" % (t.t["name"], t.pops)
        surf.blit(app.text(app.f_norm, title, YELLOW), (18, y0 + 8))

        rows = []
        for p in (0, 1):
            state = t.upgrade_state(p)
            if state == "max":
                rows.append(("Path %s: MAX" % "AB"[p], GRAY, "Fully upgraded"))
            elif state == "locked":
                rows.append(("Path %s: locked" % "AB"[p], GRAY, "Only one path can reach level 3"))
            else:
                name, cost, desc, _ = t.t["paths"][p][t.levels[p]]
                cost = self.cost(cost)
                rows.append(("%s  $%d" % (name, cost), GREEN if self.money >= cost else (230, 110, 110), desc))
        if t.key == "mine":
            pay = int(t.s["income"] * t.s["mult"])
            extra = " +%d lives" % t.s["lives"] if t.s["lives"] else ""
            rows.append(("Earns $%d/round%s" % (pay, extra), WHITE, "Paid at the end of every round"))
        elif t.key == "frost":
            rows.append(("Freezes %.1fs" % t.s["freeze"], WHITE, "Freezes everything in range"))
        else:
            rows.append(("Target: < %s >" % TARGET_MODES[t.target_mode], WHITE,
                         "Which balloon to shoot first"))
        value = int(t.spent * SELL_RATE)
        rows.append(("Sell  +$%d" % value, (255, 200, 120), "Remove tower, get money back"))

        surf.blit(app.text(app.f_small, rows[self.menu][2], (190, 195, 210)), (18, y0 + 38))
        for i, (label, col, _) in enumerate(rows):
            ry = y0 + 66 + i * 36
            if i == self.menu:
                pygame.draw.rect(surf, PANEL_HI, (14, ry - 2, SCREEN_W - 28, 32), border_radius=6)
                pygame.draw.rect(surf, YELLOW, (14, ry - 2, SCREEN_W - 28, 32), 2, border_radius=6)
            surf.blit(app.text(app.f_norm, label, col), (24, ry + 3))
            if i < 2:
                for k in range(3):
                    rect = (SCREEN_W - 70 + k * 14, ry + 9, 10, 10)
                    pygame.draw.rect(surf, (255, 120, 80) if i == 0 else (90, 170, 255), rect,
                                     0 if k < t.levels[i] else 2)

    def draw_overlay(self, surf):
        app = self.app
        surf.blit(app.dim, (0, 0))
        if self.overlay == "pause":
            title, sub = "Paused", "Round %d" % self.round
        elif self.overlay == "over":
            title, sub = "Game Over", "You made it to round %d" % self.round
        else:
            title, sub = "You Win!", "All %d rounds beaten!" % WIN_ROUND
        img = app.text(app.f_big, title, YELLOW)
        surf.blit(img, img.get_rect(center=(SCREEN_W // 2, 190)))
        img = app.text(app.f_norm, sub, WHITE)
        surf.blit(img, img.get_rect(center=(SCREEN_W // 2, 245)))
        app.draw_menu_list(surf, self.overlay_items(), self.over_idx, 300)


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
        self._text_cache = {}
        self._bg_cache = {}
        self._range_cache = {}
        self._ice_cache = {}
        self.balloon_sprites = {(n, c): make_balloon_sprite(n, c)
                                for n, i in BALLOON_TYPES.items() if not i.get("blimp") for c in (False, True)}
        self.blimp_sprites = {n: make_blimp_sprites(n) for n, i in BALLOON_TYPES.items() if i.get("blimp")}
        self.tower_sprites = {tt["key"]: make_tower_sprite(tt["key"], self.f_med) for tt in TOWER_TYPES}
        self.ghost_sprites = {}   # see-through copies for the "where will it go" preview
        for key, spr in self.tower_sprites.items():
            ghost = spr.copy()
            ghost.set_alpha(170)
            self.ghost_sprites[key] = ghost
        self.dim = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        self.dim.fill((0, 0, 0, 160))
        self.save = self.load_save()
        self.state = "title"
        self.title_idx = 3   # "Start game"
        self.map_idx = 0
        self.diff_idx = 1
        self.game = None
        self.running = True
        self.title_balloons = [[random.uniform(0, SCREEN_W), random.uniform(0, SCREEN_H),
                                random.choice(["red", "blue", "green", "yellow", "pink"]),
                                random.uniform(25, 60)] for _ in range(14)]
        self.btn_hold = 0.0

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
        for _ in range(26):
            pygame.draw.circle(surf, GRASS_DARK, (rnd.randrange(SCREEN_W), rnd.randrange(MAP_H)),
                               rnd.randrange(18, 40))
        for _ in range(160):
            x, y = rnd.randrange(SCREEN_W), rnd.randrange(MAP_H)
            pygame.draw.line(surf, (60, 125, 50), (x, y), (x + rnd.choice((-3, 3)), y - 6), 2)
        for _ in range(30):
            x, y = rnd.randrange(SCREEN_W), rnd.randrange(MAP_H)
            pygame.draw.circle(surf, rnd.choice([(250, 250, 250), (250, 220, 80), (240, 140, 180)]), (x, y), 3)
        pts = mp["path"]
        for col, half in ((PATH_EDGE, PATH_W // 2 + 4), (PATH_COL, PATH_W // 2)):
            for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                surf.fill(col, pygame.Rect(min(x0, x1) - half, min(y0, y1) - half,
                                           abs(x1 - x0) + 2 * half, abs(y1 - y0) + 2 * half))
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):   # little pebbles on the track
            for _ in range(int(math.hypot(x1 - x0, y1 - y0) / 25)):
                t = rnd.random()
                px = x0 + (x1 - x0) * t + rnd.randint(-12, 12)
                py = y0 + (y1 - y0) * t + rnd.randint(-12, 12)
                pygame.draw.circle(surf, (190, 160, 110), (int(px), int(py)), 2)
        return surf

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

    def draw_menu_list(self, surf, items, idx, y, gap=52):
        for i, label in enumerate(items):
            img = self.text(self.f_med, label, YELLOW if i == idx else WHITE)
            r = img.get_rect(center=(SCREEN_W // 2, y + i * gap))
            if i == idx:
                pygame.draw.rect(surf, PANEL_HI, r.inflate(40, 14), border_radius=10)
                pygame.draw.rect(surf, YELLOW, r.inflate(40, 14), 2, border_radius=10)
            surf.blit(img, r)

    def title_items(self):
        return ["Map: < %s >" % MAPS[self.map_idx]["name"],
                "Mode: < %s >" % DIFFICULTIES[self.diff_idx]["name"],
                "Auto-start: < %s >" % ("ON" if self.save.get("auto_start") else "OFF"),
                "Start game", "How to play", "Button test", "Quit"]

    def update_title(self, dt):
        inp = self.inp
        n = len(self.title_items())
        if "UP" in inp.repeat:
            self.title_idx = (self.title_idx - 1) % n
        if "DOWN" in inp.repeat:
            self.title_idx = (self.title_idx + 1) % n
        step = ("RIGHT" in inp.repeat) - ("LEFT" in inp.repeat)
        if self.title_idx == 0 and step:
            self.map_idx = (self.map_idx + step) % len(MAPS)
        if self.title_idx == 1 and step:
            self.diff_idx = (self.diff_idx + step) % len(DIFFICULTIES)
        if self.title_idx == 2 and (step or "A" in inp.pressed):
            self.set_auto_start(not self.save.get("auto_start"))
        elif "A" in inp.pressed or "START" in inp.pressed:
            if self.title_idx in (0, 1, 2, 3):
                self.game = Game(self, self.map_idx, self.diff_idx)
                self.state = "game"
            elif self.title_idx == 4:
                self.state = "help"
            elif self.title_idx == 5:
                self.state = "buttons"
                self.btn_hold = 0.0
            elif self.title_idx == 6:
                self.running = False
        for b in self.title_balloons:
            b[1] -= b[3] * dt
            if b[1] < -30:
                b[0], b[1] = random.uniform(0, SCREEN_W), SCREEN_H + 30

    def draw_title(self, surf):
        surf.fill((70, 140, 220))
        for x, y, name, _ in self.title_balloons:
            spr, ox, oy = self.balloon_sprites[(name, False)]
            surf.blit(spr, (x - ox, y - oy))
        for i, (word, col) in enumerate((("BALLOON", (255, 230, 80)), ("BLITZ", (255, 110, 110)))):
            img = self.text(self.f_big, word, col)
            sh = self.text(self.f_big, word, (30, 30, 60))
            r = img.get_rect(center=(SCREEN_W // 2, 50 + i * 52))
            surf.blit(sh, r.move(3, 3))
            surf.blit(img, r)
        # map preview
        thumb = pygame.transform.smoothscale(self.map_bg(self.map_idx), (140, 140))
        tr = thumb.get_rect(center=(SCREEN_W // 2, 210))
        pygame.draw.rect(surf, WHITE, tr.inflate(6, 6), border_radius=4)
        surf.blit(thumb, tr)
        mp = MAPS[self.map_idx]
        info = "%s map  -  Best: round %d" % (mp["level"], self.best(self.map_idx, self.diff_idx))
        img = self.text(self.f_small, info, WHITE)
        surf.blit(img, img.get_rect(center=(SCREEN_W // 2, 300)))
        self.draw_menu_list(surf, self.title_items(), self.title_idx, 338, 46)

    HELP = [
        ("GOAL", YELLOW),
        ("Pop balloons before they reach the end.", WHITE),
        ("Each balloon that escapes costs lives.", WHITE),
        ("", WHITE),
        ("CONTROLS", YELLOW),
        ("D-pad: move cursor", WHITE),
        ("L / R: pick a tower to build", WHITE),
        ("A: build, or open a tower's menu", WHITE),
        ("B: cancel / close", WHITE),
        ("START: next round / pause", WHITE),
        ("SELECT: fast forward", WHITE),
        ("", WHITE),
        ("TIPS", YELLOW),
        ("Lead balloons need bombs, fire or magic.", WHITE),
        ("Black ones ignore bombs.", WHITE),
        ("Camo balloons need Eagle Eye,", WHITE),
        ("Night Scope, Radar or Cold Snap.", WHITE),
        ("Only one upgrade path can reach 3.", WHITE),
    ]

    def draw_help(self, surf):
        surf.fill(DARK)
        for i, (line, col) in enumerate(self.HELP):
            surf.blit(self.text(self.f_small, line, col), (24, 18 + i * 31))
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
