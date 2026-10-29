#!/usr/bin/env python3
"""
Handheld emulator for Balloon Blitz.

Shows the game on a pretend handheld so you can test it on a computer
before the real parts arrive. Click the buttons with the mouse, or use
the keyboard:

    Arrow keys = D-pad     Z = A     X = B     A = L     S = R
    Enter = START          Tab = SELECT

Run it with:   python3 handheld_emulator.py

It loads the game from the balloon-blitz folder next to this one.
"""
import os
import sys

import pygame

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)   # a copy of balloon_blitz.py in here works too...
sys.path.insert(0, os.path.join(HERE, "..", "balloon-blitz"))   # ...but the real one wins
import balloon_blitz as bb  # noqa: E402

WIN_W, WIN_H = 1000, 750
SCREEN_X, SCREEN_Y = (WIN_W - bb.SCREEN_W) // 2, 40
BODY = (48, 54, 78)
BODY_EDGE = (28, 32, 48)
BTN = (70, 76, 100)
BTN_DOWN = (255, 210, 70)
LABEL = (200, 205, 220)

# Where each on-screen button is: action -> (shape, rect or circle, label, key hint)
LEFT_X = SCREEN_X // 2
RIGHT_X = SCREEN_X + bb.SCREEN_W + (WIN_W - SCREEN_X - bb.SCREEN_W) // 2
BUTTONS = {
    "UP":     ("rect", pygame.Rect(LEFT_X - 28, 270, 56, 64), "", ""),
    "DOWN":   ("rect", pygame.Rect(LEFT_X - 28, 390, 56, 64), "", ""),
    "LEFT":   ("rect", pygame.Rect(LEFT_X - 92, 334, 64, 56), "", ""),
    "RIGHT":  ("rect", pygame.Rect(LEFT_X + 28, 334, 64, 56), "", ""),
    "A":      ("circle", (RIGHT_X + 45, 330, 38), "A", "Z"),
    "B":      ("circle", (RIGHT_X - 45, 400, 38), "B", "X"),
    "L":      ("rect", pygame.Rect(30, 40, 180, 50), "L", "A key"),
    "R":      ("rect", pygame.Rect(WIN_W - 210, 40, 180, 50), "R", "S key"),
    "SELECT": ("rect", pygame.Rect(RIGHT_X - 95, 560, 90, 34), "SELECT", "Tab"),
    "START":  ("rect", pygame.Rect(RIGHT_X + 5, 560, 90, 34), "START", "Enter"),
}


def hit(shape, geom, pos):
    if shape == "rect":
        return geom.collidepoint(pos)
    x, y, r = geom
    return (pos[0] - x) ** 2 + (pos[1] - y) ** 2 <= r * r


class EmulatorApp(bb.App):
    def __init__(self, screen, canvas):
        super().__init__(screen, canvas, 0)
        self.f_btn = pygame.font.Font(None, 34)
        self.f_hint = pygame.font.Font(None, 22)
        self.mouse_btn = None

    def on_event(self, e):
        # Holding the mouse on a button = holding that button down.
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for act, (shape, geom, _, _) in BUTTONS.items():
                if hit(shape, geom, e.pos):
                    self.mouse_btn = act
                    self.inp.virtual = {act}
            return True
        if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            self.mouse_btn = None
            self.inp.virtual = set()
            return True
        return False

    def present(self):
        s = self.screen
        s.fill((20, 22, 30))
        body = pygame.Rect(10, 20, WIN_W - 20, WIN_H - 40)
        pygame.draw.rect(s, BODY, body, border_radius=40)
        pygame.draw.rect(s, BODY_EDGE, body, 4, border_radius=40)
        # screen with a bezel
        bezel = pygame.Rect(SCREEN_X - 14, SCREEN_Y - 14, bb.SCREEN_W + 28, bb.SCREEN_H + 28)
        pygame.draw.rect(s, (12, 12, 16), bezel, border_radius=12)
        s.blit(self.canvas, (SCREEN_X, SCREEN_Y))

        held = self.inp.held
        # D-pad: draw the cross, then light up pressed arms
        pygame.draw.rect(s, BTN, BUTTONS["UP"][1].union(BUTTONS["DOWN"][1]), border_radius=8)
        pygame.draw.rect(s, BTN, BUTTONS["LEFT"][1].union(BUTTONS["RIGHT"][1]), border_radius=8)
        for act, arrow in (("UP", (0, -1)), ("DOWN", (0, 1)), ("LEFT", (-1, 0)), ("RIGHT", (1, 0))):
            r = BUTTONS[act][1]
            if act in held:
                pygame.draw.rect(s, BTN_DOWN, r, border_radius=8)
            cx, cy = r.center
            dx, dy = arrow
            tip = (cx + dx * 14, cy + dy * 14)
            side1 = (cx - dy * 10 - dx * 4, cy - dx * 10 - dy * 4)
            side2 = (cx + dy * 10 - dx * 4, cy + dx * 10 - dy * 4)
            pygame.draw.polygon(s, BODY_EDGE, [tip, side1, side2])
        hint = self.f_hint.render("Arrow keys", True, LABEL)
        s.blit(hint, hint.get_rect(center=(LEFT_X, 480)))

        for act in ("A", "B", "L", "R", "SELECT", "START"):
            shape, geom, label, key = BUTTONS[act]
            col = BTN_DOWN if act in held else BTN
            if shape == "circle":
                x, y, r = geom
                pygame.draw.circle(s, col, (x, y), r)
                pygame.draw.circle(s, BODY_EDGE, (x, y), r, 3)
                center, below = (x, y), (x, y + r + 16)
            else:
                pygame.draw.rect(s, col, geom, border_radius=16)
                pygame.draw.rect(s, BODY_EDGE, geom, 3, border_radius=16)
                center, below = geom.center, (geom.centerx, geom.bottom + 14)
            img = (self.f_btn if len(label) == 1 else self.f_hint).render(label, True, BODY_EDGE if act in held
                                                                           else (235, 238, 245))
            s.blit(img, img.get_rect(center=center))
            img = self.f_hint.render(key, True, LABEL)
            s.blit(img, img.get_rect(center=below))

        title = self.f_hint.render("BALLOON BLITZ  -  handheld emulator", True, LABEL)
        s.blit(title, title.get_rect(center=(WIN_W // 2, WIN_H - 38)))


def main():
    bb.pygame.mixer.pre_init(22050, -16, 1, 512)
    pygame.init()
    pygame.display.set_caption("Balloon Blitz - Handheld Emulator")
    # SCALED lets you resize/maximize the window and keeps it sharp.
    screen = pygame.display.set_mode((WIN_W, WIN_H), pygame.SCALED | pygame.RESIZABLE)
    canvas = pygame.Surface((bb.SCREEN_W, bb.SCREEN_H)).convert()
    print("Loaded Balloon Blitz %s from %s" % (getattr(bb, "VERSION", "(old version)"), bb.__file__))
    EmulatorApp(screen, canvas).run()
    pygame.quit()


if __name__ == "__main__":
    main()
