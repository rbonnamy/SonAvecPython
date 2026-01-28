#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WOW Terminal Show (single-file, no dependencies)
------------------------------------------------
Un petit "effet waouw" en plein terminal : starfield + particules + fireworks + texte qui apparaît.
- Lance : python wow_show.py
- Quitter : q
- Déclencher un feu d’artifice : espace

Fonctionne sur Windows / macOS / Linux (ANSI). Sur Windows, le script active l'ANSI si besoin.
"""

import os
import sys
import math
import time
import random
import shutil
import signal

# ------------------------ ANSI helpers ------------------------

ESC = "\x1b"

def enable_ansi_on_windows():
    """Active les séquences ANSI sur Windows (Windows 10+)."""
    if os.name != "nt":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        h = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE = -11
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(h, ctypes.byref(mode)) == 0:
            return
        # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        kernel32.SetConsoleMode(h, mode.value | 0x0004)
    except Exception:
        pass

def hide_cursor():
    sys.stdout.write(f"{ESC}[?25l")

def show_cursor():
    sys.stdout.write(f"{ESC}[?25h")

def clear_screen():
    sys.stdout.write(f"{ESC}[2J{ESC}[H")

def move_home():
    sys.stdout.write(f"{ESC}[H")

def set_rgb(r, g, b, bg=False):
    return f"{ESC}[{'48' if bg else '38'};2;{r};{g};{b}m"

def reset_style():
    return f"{ESC}[0m"

def clamp(x, a, b):
    return a if x < a else b if x > b else x

# ------------------------ Non-blocking input ------------------------

class KeyReader:
    def __init__(self):
        self.is_windows = (os.name == "nt")
        self._old = None

        if not self.is_windows:
            # Unix: put terminal in cbreak mode
            import termios, tty
            self.termios = termios
            self.tty = tty
            self.fd = sys.stdin.fileno()
            self._old = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)

    def close(self):
        if not self.is_windows and self._old is not None:
            self.termios.tcsetattr(self.fd, self.termios.TCSADRAIN, self._old)

    def get_key(self):
        """Return a single character if available, else None."""
        if self.is_windows:
            import msvcrt
            if msvcrt.kbhit():
                ch = msvcrt.getwch()
                return ch
            return None
        else:
            import select
            r, _, _ = select.select([sys.stdin], [], [], 0)
            if r:
                ch = sys.stdin.read(1)
                return ch
            return None

# ------------------------ Visual objects ------------------------

class Star:
    __slots__ = ("x", "y", "z", "vx", "vy")
    def __init__(self, w, h):
        self.reset(w, h)

    def reset(self, w, h):
        # 3D-ish starfield: x/y around center, z depth
        self.x = random.uniform(-w, w)
        self.y = random.uniform(-h, h)
        self.z = random.uniform(0.2, 1.0)
        # tiny drift for parallax feel
        self.vx = random.uniform(-0.05, 0.05)
        self.vy = random.uniform(-0.03, 0.03)

    def step(self, speed, w, h):
        # Move "towards viewer": z decreases
        self.z -= speed
        self.x += self.vx
        self.y += self.vy
        if self.z <= 0.02:
            self.reset(w, h)

    def project(self, cx, cy):
        # perspective projection
        px = int(cx + (self.x / self.z) * 0.10)
        py = int(cy + (self.y / self.z) * 0.06)
        return px, py

class Particle:
    __slots__ = ("x","y","vx","vy","life","maxlife","r","g","b","char","gravity","drag")
    def __init__(self, x, y, vx, vy, life, color, char="•", gravity=0.12, drag=0.992):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.life = life
        self.maxlife = life
        self.r, self.g, self.b = color
        self.char = char
        self.gravity = gravity
        self.drag = drag

    def alive(self):
        return self.life > 0

    def step(self):
        self.life -= 1
        self.vx *= self.drag
        self.vy = self.vy * self.drag + self.gravity
        self.x += self.vx
        self.y += self.vy

    def fade_color(self):
        # smooth fade to darker as life decreases
        t = self.life / self.maxlife if self.maxlife else 0
        t = clamp(t, 0.0, 1.0)
        # slightly non-linear for nicer decay
        t2 = t * t
        return (int(self.r * t2), int(self.g * t2), int(self.b * t2))

# ------------------------ Rendering buffer ------------------------

class Buffer:
    def __init__(self, w, h):
        self.resize(w, h)

    def resize(self, w, h):
        self.w = max(20, w)
        self.h = max(10, h)
        self.ch = [[" "]*self.w for _ in range(self.h)]
        self.fg = [[None]*self.w for _ in range(self.h)]

    def clear(self):
        for y in range(self.h):
            row = self.ch[y]
            col = self.fg[y]
            for x in range(self.w):
                row[x] = " "
                col[x] = None

    def put(self, x, y, c, color=None):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.ch[y][x] = c
            self.fg[y][x] = color

    def draw_text_center(self, y, text, color):
        x0 = (self.w - len(text)) // 2
        for i, ch in enumerate(text):
            self.put(x0 + i, y, ch, color)

    def render(self):
        # Render with minimal ANSI color changes
        out_lines = []
        last = None
        for y in range(self.h):
            line_parts = []
            for x in range(self.w):
                col = self.fg[y][x]
                if col != last:
                    if col is None:
                        line_parts.append(reset_style())
                    else:
                        r, g, b = col
                        line_parts.append(set_rgb(r, g, b))
                    last = col
                line_parts.append(self.ch[y][x])
            line_parts.append(reset_style())
            out_lines.append("".join(line_parts))
            last = None
        return "\n".join(out_lines)

# ------------------------ Fireworks logic ------------------------

def random_vibrant_color():
    # pick bright colors that "pop"
    base = random.choice([
        (255, 80, 80),
        (255, 180, 60),
        (255, 255, 120),
        (120, 255, 160),
        (80, 200, 255),
        (200, 120, 255),
        (255, 120, 220),
    ])
    # small jitter
    r = clamp(base[0] + random.randint(-25, 25), 0, 255)
    g = clamp(base[1] + random.randint(-25, 25), 0, 255)
    b = clamp(base[2] + random.randint(-25, 25), 0, 255)
    return (r, g, b)

def spawn_firework(particles, w, h):
    # rocket start bottom-ish, go up
    x = random.uniform(w*0.2, w*0.8)
    y = random.uniform(h*0.65, h*0.90)
    vx = random.uniform(-0.25, 0.25)
    vy = random.uniform(-2.6, -2.0)
    color = (220, 220, 220)
    # rocket particle itself
    particles.append(Particle(x, y, vx, vy, life=random.randint(18, 28), color=color, char="|", gravity=0.09, drag=0.995))
    return

def explode(particles, x, y, w, h):
    color = random_vibrant_color()
    # burst: radial particles
    n = random.randint(70, 130)
    for _ in range(n):
        ang = random.uniform(0, math.tau)
        spd = random.uniform(0.4, 2.6)
        vx = math.cos(ang) * spd
        vy = math.sin(ang) * spd
        life = random.randint(18, 40)
        char = random.choice(["•", "·", "*", "✦", "✧"])
        particles.append(Particle(x, y, vx, vy, life=life, color=color, char=char, gravity=0.10, drag=0.990))

    # glitter / sparkles (slower, longer)
    for _ in range(random.randint(40, 70)):
        ang = random.uniform(0, math.tau)
        spd = random.uniform(0.15, 1.2)
        vx = math.cos(ang) * spd
        vy = math.sin(ang) * spd
        life = random.randint(35, 65)
        pastel = (int((color[0] + 255) / 2), int((color[1] + 255) / 2), int((color[2] + 255) / 2))
        particles.append(Particle(x, y, vx, vy, life=life, color=pastel, char="·", gravity=0.06, drag=0.993))

def draw_gradient_bg(buf, t):
    # subtle moving "aurora" near top
    h = buf.h
    w = buf.w
    top = max(1, h // 4)
    for y in range(top):
        for x in range(w):
            # wavy bands
            a = math.sin((x * 0.06) + (t * 1.3) + (y * 0.15))
            b = math.cos((x * 0.04) - (t * 1.0) + (y * 0.22))
            v = (a + b) * 0.5
            # dark background with slight tint
            r = int(8 + (v + 1) * 6)
            g = int(10 + (v + 1) * 10)
            bb = int(14 + (v + 1) * 14)
            # use spaces tinted (still looks like a "mist")
            # We'll set fg color; space itself gives subtle effect due to many terminals not coloring spaces strongly.
            # So we add faint dots sometimes.
            if random.random() < 0.005:
                buf.put(x, y, "·", (r, g, bb))
            else:
                # keep empty, but we can tint very lightly by putting a thin char
                # To avoid too much noise, do nothing.
                pass

def fancy_title_frame(buf, frame, total_frames):
    # reveal "WAOUW !" / "WOW !" with shimmering
    msg = "EFFET WAOUW !"
    sub = "Appuie sur ESPACE pour un feu d’artifice — q pour quitter"
    # animation: shimmer along letters
    base_y = max(2, buf.h // 6)
    y1 = base_y
    y2 = base_y + 2

    # shimmer position
    p = (frame % 120) / 120.0
    shimmer_x = int(p * (len(msg) + 12)) - 6

    for i, ch in enumerate(msg):
        # shimmer highlight
        dist = abs(i - shimmer_x)
        if dist <= 1:
            col = (255, 255, 255)
        elif dist <= 2:
            col = (220, 240, 255)
        else:
            col = (170, 210, 255)
        buf.put((buf.w - len(msg)) // 2 + i, y1, ch, col)

    # sub text
    sx = (buf.w - len(sub)) // 2
    for i, ch in enumerate(sub):
        col = (140, 180, 210)
        buf.put(sx + i, y2, ch, col)

    # tiny "pulse" underline
    underline_len = len(msg)
    ul_y = y1 + 1
    for i in range(underline_len):
        wave = math.sin((i * 0.5) + (frame * 0.18))
        if wave > 0.4:
            buf.put((buf.w - underline_len) // 2 + i, ul_y, "─", (120, 170, 255))
        else:
            buf.put((buf.w - underline_len) // 2 + i, ul_y, "─", (70, 90, 120))

# ------------------------ Main loop ------------------------

def main():
    enable_ansi_on_windows()

    # restore cursor on exit no matter what
    def cleanup(*_):
        try:
            show_cursor()
            sys.stdout.write(reset_style())
            sys.stdout.flush()
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, cleanup)

    # sizing
    w, h = shutil.get_terminal_size(fallback=(100, 30))
    buf = Buffer(w, h)

    # starfield
    stars = []
    # number of stars depends on size
    star_count = max(80, (w * h) // 35)
    cx, cy = w // 2, h // 2
    for _ in range(star_count):
        stars.append(Star(w, h))

    particles = []

    reader = KeyReader()
    hide_cursor()
    clear_screen()
    sys.stdout.flush()

    t0 = time.perf_counter()
    last = t0
    frame = 0

    # schedule periodic fireworks
    next_auto = 0.0

    try:
        while True:
            now = time.perf_counter()
            dt = now - last
            last = now
            t = now - t0
            frame += 1

            # resize handling
            nw, nh = shutil.get_terminal_size(fallback=(w, h))
            if nw != w or nh != h:
                w, h = nw, nh
                buf.resize(w, h)
                cx, cy = w // 2, h // 2
                # re-seed some stars for new size
                stars = [Star(w, h) for _ in range(max(80, (w * h) // 35))]

            # input
            key = reader.get_key()
            if key:
                if key.lower() == "q":
                    break
                if key == " ":
                    # manual firework
                    spawn_firework(particles, w, h)

            # auto fireworks rhythm
            if t >= next_auto:
                if random.random() < 0.55:
                    spawn_firework(particles, w, h)
                next_auto = t + random.uniform(0.6, 1.6)

            # clear buffer
            buf.clear()

            # subtle background
            draw_gradient_bg(buf, t)

            # update + draw stars
            speed = 0.012 + 0.010 * (0.5 + 0.5 * math.sin(t * 0.8))
            for s in stars:
                s.step(speed, w, h)
                px, py = s.project(cx, cy)
                if 0 <= px < w and 0 <= py < h:
                    # brightness depends on z
                    b = int(60 + (1.0 - s.z) * 195)
                    b = clamp(b, 60, 255)
                    # star character depends on brightness
                    ch = "·"
                    if b > 210:
                        ch = "✦"
                    elif b > 170:
                        ch = "*"
                    elif b > 120:
                        ch = "•"
                    buf.put(px, py, ch, (b, b, b))

            # update particles; rockets explode at end
            new_particles = []
            for p in particles:
                # if it's a rocket (char "|") and nearly done, explode
                if p.char == "|" and p.life == 1:
                    explode(new_particles, p.x, p.y, w, h)

                p.step()
                if p.alive():
                    new_particles.append(p)

                    x = int(p.x)
                    y = int(p.y)
                    col = p.fade_color()

                    # draw with a small trail effect
                    buf.put(x, y, p.char, col)
                    if random.random() < 0.25:
                        buf.put(x - 1, y, "·", (max(0, col[0] // 2), max(0, col[1] // 2), max(0, col[2] // 2)))
                    if random.random() < 0.25:
                        buf.put(x + 1, y, "·", (max(0, col[0] // 2), max(0, col[1] // 2), max(0, col[2] // 2)))

            particles = new_particles

            # title overlay
            fancy_title_frame(buf, frame, 10**9)

            # footer tiny status
            footer = f"FPS ~ {int(1/max(dt, 1e-6))}   Particules: {len(particles)}"
            for i, ch in enumerate(footer[:w-1]):
                buf.put(1 + i, h - 1, ch, (90, 110, 130))

            # render
            move_home()
            sys.stdout.write(buf.render())
            sys.stdout.flush()

            # frame cap
            # ~60 fps max, but adapt gracefully
            target = 1.0 / 60.0
            if dt < target:
                time.sleep(target - dt)

    finally:
        reader.close()
        show_cursor()
        sys.stdout.write(reset_style())
        sys.stdout.write("\n")
        sys.stdout.flush()

if __name__ == "__main__":
    main()
