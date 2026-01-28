#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
WOW Sound Show (single file, no pip)
------------------------------------
Un "effet waouw" en console sans dessin : mini show sonore (mélodie + effets).
- Windows : son propre via winsound (fréquences + durées)
- macOS/Linux : fallback beep terminal (si le terminal/OS l'autorise)

Touches:
  Espace : rejouer le show
  q      : quitter
"""

import os
import sys
import time
import math
import random
import signal

IS_WINDOWS = (os.name == "nt")

# ----------- Non-blocking input -----------

class KeyReader:
    def __init__(self):
        self.is_windows = IS_WINDOWS
        self._old = None

        if not self.is_windows:
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
        if self.is_windows:
            import msvcrt
            if msvcrt.kbhit():
                return msvcrt.getwch()
            return None
        else:
            import select
            r, _, _ = select.select([sys.stdin], [], [], 0)
            if r:
                return sys.stdin.read(1)
            return None

# ----------- Sound backends -----------

def beep(f_hz: int, ms: int):
    """Play one beep. Windows: winsound.Beep. Else: terminal bell."""
    f_hz = int(max(37, min(32767, f_hz)))
    ms = int(max(10, ms))

    if IS_WINDOWS:
        import winsound
        winsound.Beep(f_hz, ms)
    else:
        # terminal bell (may be disabled depending on settings)
        sys.stdout.write("\a")
        sys.stdout.flush()
        time.sleep(ms / 1000.0)

def note_freq(note: str) -> int:
    """
    Convert note name to frequency in Hz.
    note examples: "C4", "D#5", "A3"
    """
    note = note.strip().upper()
    if note == "R":  # rest
        return 0

    names = {"C":0, "C#":1, "DB":1, "D":2, "D#":3, "EB":3, "E":4,
             "F":5, "F#":6, "GB":6, "G":7, "G#":8, "AB":8, "A":9,
             "A#":10, "BB":10, "B":11}

    # parse
    if len(note) < 2:
        raise ValueError(f"Bad note: {note}")

    if note[1] in ("#", "B"):
        key = note[:2]
        octave = int(note[2:])
    else:
        key = note[:1]
        octave = int(note[1:])

    n = names[key]
    # MIDI note number: C4=60, A4=69
    midi = (octave + 1) * 12 + n
    a4 = 69
    freq = 440.0 * (2 ** ((midi - a4) / 12))
    return int(round(freq))

def play_tone(freq: int, ms: int):
    if freq <= 0:
        time.sleep(ms / 1000.0)
    else:
        beep(freq, ms)

# ----------- Show content -----------

def laser_sweep():
    # effet "laser": fréquence qui monte vite, puis retombe
    for i in range(18):
        f = 600 + i * 140
        play_tone(f, 18)
    for i in range(12):
        f = 3200 - i * 170
        play_tone(f, 16)

def explosion():
    # pseudo explosion: bruit "granuleux" par beeps aléatoires
    for i in range(28):
        f = random.randint(80, 800) + int((28 - i) * 25)
        play_tone(f, 12)

def arpeggio():
    # petit arpège "cinématique"
    seq = [
        ("E4", 110), ("G4", 110), ("B4", 110), ("E5", 180),
        ("D5", 90), ("B4", 90), ("G4", 120), ("B4", 140),
        ("C5", 160), ("G4", 90), ("E4", 180),
    ]
    for n, d in seq:
        play_tone(note_freq(n), d)

def fanfare():
    # fanfare courte + effet waouw final
    seq = [
        ("C4", 120), ("E4", 120), ("G4", 120), ("C5", 220),
        ("R", 70),
        ("A4", 120), ("B4", 120), ("C5", 220),
        ("R", 70),
        ("G4", 120), ("E4", 120), ("C4", 260),
    ]
    for n, d in seq:
        play_tone(note_freq(n) if n != "R" else 0, d)

def wow_finale():
    # montée progressive + petit "sparkle"
    for i in range(22):
        f = 240 + int(i * 95 + 40 * math.sin(i * 0.9))
        play_tone(f, 22)
    for _ in range(14):
        play_tone(random.randint(1200, 3200), 18)

def show():
    # ordre du show
    laser_sweep()
    arpeggio()
    explosion()
    fanfare()
    wow_finale()

# ----------- UI (no drawing, no scrolling dependency) -----------

def print_header():
    sys.stdout.write("\n")
    sys.stdout.write("🎆  WOW SONORE (sans pip, sans dessin)\n")
    sys.stdout.write("    Espace : rejouer | q : quitter\n")
    sys.stdout.write("    (Sur Windows le rendu est bien meilleur)\n\n")
    sys.stdout.flush()

def main():
    def cleanup(*_):
        sys.stdout.write("\nBye 👋\n")
        sys.stdout.flush()
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, cleanup)

    print_header()

    reader = KeyReader()
    try:
        # lance une première fois
        show()

        while True:
            k = reader.get_key()
            if k:
                if k.lower() == "q":
                    break
                if k == " ":
                    sys.stdout.write("▶️  Showtime !\n")
                    sys.stdout.flush()
                    show()
                    sys.stdout.write("✅  (Espace pour rejouer)\n")
                    sys.stdout.flush()
            time.sleep(0.02)
    finally:
        reader.close()

if __name__ == "__main__":
    main()
