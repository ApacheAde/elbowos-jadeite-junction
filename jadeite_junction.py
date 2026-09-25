#!/usr/bin/env python3
"""Jadeite Junction — neon pipe-dream arcade for ElbowOS."""
from __future__ import annotations

import math
import os
import random
import subprocess
import sys

import pygame

W, H = 1080, 1920
FPS = 30
TITLE = "JADEITE JUNCTION"
HANDLE = "x.com/ElbowOS"

VOID = (4, 18, 14)
INK = (8, 36, 28)
JADE = (48, 220, 140)
MINT = (160, 255, 210)
COPP = (232, 132, 48)
GOLD = (255, 214, 72)
TEAL = (20, 160, 150)
CREAM = (240, 255, 236)
ROSE = (255, 90, 120)
NAVY = (10, 48, 40)

# N E S W bitmasks
N, E, S, Wd = 1, 2, 4, 8
SHAPES = {
    "I": (N | S, E | Wd),
    "L": (N | E, E | S, S | Wd, Wd | N),
    "T": (E | S | Wd, S | Wd | N, Wd | N | E, N | E | S),
    "X": (N | E | S | Wd,),
}
KINDS = ("I", "I", "L", "L", "L", "T", "X")
COLS, ROWS = 6, 8
CELL = 132
OX, OY = 144, 280


def rot_mask(m: int, k: int) -> int:
    for _ in range(k % 4):
        m = ((m << 1) & 15) | (1 if m & 8 else 0)
    return m


class Spark:
    __slots__ = ("x", "y", "vx", "vy", "life", "col", "r")

    def __init__(self, x, y, vx, vy, life, col, r=4):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.life, self.col, self.r = life, col, r


class Game:
    def __init__(self, record: bool):
        self.record = record
        self.surf = pygame.Surface((W, H))
        self.clock = pygame.time.Clock()
        self.font_lg = pygame.font.Font(None, 56)
        self.font_md = pygame.font.Font(None, 42)
        self.font_sm = pygame.font.Font(None, 30)
        self.screen = None
        if not record:
            self.screen = pygame.display.set_mode((W, H))
            pygame.display.set_caption(TITLE)
        self.reset()

    def reset(self) -> None:
        self.t = 0.0
        self.score = 0
        self.circuits = 0
        self.sparks: list[Spark] = []
        self.pops: list[tuple] = []
        self.flow = 0.0
        self.hot: set[tuple[int, int]] = set()
        self.flash = 0.0
        self._last_twist = -1.0
        self.stars = [(random.randint(0, W), random.randint(0, H), random.random()) for _ in range(70)]
        self.running = True
        self._new_board()

    def _new_board(self) -> None:
        self.grid = []
        for r in range(ROWS):
            row = []
            for c in range(COLS):
                kind = random.choice(KINDS)
                rot = random.randint(0, 3)
                row.append([kind, rot])
            self.grid.append(row)
        self.grid[ROWS // 2][0] = ["I", 1]
        self.grid[ROWS // 2][COLS - 1] = ["I", 1]
        self.hot.clear()
        self.flow = 0.0
        self._recompute()

    def mask_at(self, c, r) -> int:
        kind, rot = self.grid[r][c]
        return rot_mask(SHAPES[kind][0] if kind != "I" else SHAPES[kind][rot % 2], 0 if kind == "I" else rot)

    def center(self, c, r) -> tuple[int, int]:
        return OX + c * CELL + CELL // 2, OY + r * CELL + CELL // 2

    def burst(self, x, y, col, n=14) -> None:
        for _ in range(n):
            a = random.uniform(0, math.tau)
            sp = random.uniform(60, 420)
            self.sparks.append(Spark(x, y, math.cos(a) * sp, math.sin(a) * sp,
                                     random.uniform(0.18, 0.5), col, random.randint(3, 7)))

    def _recompute(self) -> None:
        sr = ROWS // 2
        start = (0, sr)
        seen = set()
        q = [start]
        opp = {N: S, S: N, E: Wd, Wd: E}
        step = {N: (0, -1), E: (1, 0), S: (0, 1), Wd: (-1, 0)}
        while q:
            c, r = q.pop()
            if (c, r) in seen:
                continue
            seen.add((c, r))
            m = self.mask_at(c, r)
            for bit, (dc, dr) in step.items():
                if not (m & bit):
                    continue
                nc, nr = c + dc, r + dr
                if not (0 <= nc < COLS and 0 <= nr < ROWS):
                    continue
                if self.mask_at(nc, nr) & opp[bit]:
                    q.append((nc, nr))
        self.hot = seen
        linked = (COLS - 1, sr) in seen and (self.mask_at(COLS - 1, sr) & E)
        if linked and self.flow < 0.2:
            self.flow = 1.0
            self.circuits += 1
            self.score += 50 + 8 * len(seen)
            self.flash = 0.28
            x, y = self.center(COLS - 1, sr)
            self.burst(x, y, GOLD, 28)
            self.pops.append(("CIRCUIT +", x - 40, y - 40, 0.9, GOLD))

    def twist(self, c, r) -> None:
        kind, rot = self.grid[r][c]
        self.grid[r][c][1] = (rot + 1) % 4
        x, y = self.center(c, r)
        self.burst(x, y, JADE, 8)
        self._recompute()

    def update(self, dt: float) -> None:
        self.t += dt
        self.flash = max(0.0, self.flash - dt)
        if self.record:
            self.autoplay(dt)
        if self.flow > 0:
            self.flow -= dt * 0.55
            if self.flow <= 0:
                self._new_board()
        sparks = []
        for sp in self.sparks:
            sp.x += sp.vx * dt
            sp.y += sp.vy * dt
            sp.life -= dt
            if sp.life > 0:
                sparks.append(sp)
        self.sparks = sparks[-220:]
        self.pops = [(a, x, y - 50 * dt, life - dt, c) for a, x, y, life, c in self.pops if life - dt > 0]

    def autoplay(self, dt: float) -> None:
        if self.flow > 0.18:
            return
        if self.t - self._last_twist < 0.26:
            return
        self._last_twist = self.t
        sr = ROWS // 2
        for c in range(COLS):
            m = self.mask_at(c, sr)
            if not (m & E and m & Wd):
                kind = self.grid[sr][c][0]
                if kind == "L":
                    self.grid[sr][c] = ["I", 1]
                    self._recompute()
                else:
                    self.twist(c, sr)
                return
        r = max(0, min(ROWS - 1, sr + random.choice((-2, -1, 1, 2))))
        self.twist(random.randrange(COLS), r)

    def draw_pipe(self, s, c, r) -> None:
        x, y = self.center(c, r)
        m = self.mask_at(c, r)
        lit = (c, r) in self.hot
        body = JADE if lit else TEAL
        glow = MINT if lit else (30, 70, 60)
        pygame.draw.rect(s, INK, (x - 58, y - 58, 116, 116), border_radius=16)
        pygame.draw.rect(s, glow, (x - 58, y - 58, 116, 116), 2, border_radius=16)
        pygame.draw.circle(s, body, (x, y), 16)
        w = 18
        if m & N:
            pygame.draw.rect(s, body, (x - w // 2, y - 58, w, 58))
        if m & S:
            pygame.draw.rect(s, body, (x - w // 2, y, w, 58))
        if m & E:
            pygame.draw.rect(s, body, (x, y - w // 2, 58, w))
        if m & Wd:
            pygame.draw.rect(s, body, (x - 58, y - w // 2, 58, w))
        if lit:
            pulse = 0.5 + 0.5 * math.sin(self.t * 8 + c + r)
            pygame.draw.circle(s, CREAM, (x - 4, y - 5), 4)
            pygame.draw.circle(s, GOLD, (x, y), int(8 + 4 * pulse))

    def draw(self, s: pygame.Surface) -> None:
        s.fill(VOID)
        for sx, sy, tw in self.stars:
            yy = int((sy + self.t * (6 + tw * 18)) % H)
            g = 40 + int(tw * 80)
            pygame.draw.circle(s, (g // 5, g // 2, g // 3), (sx, yy), 1 + int(tw * 2))
        pygame.draw.rect(s, INK, pygame.Rect(48, 150, W - 96, H - 280), border_radius=28)
        pygame.draw.rect(s, NAVY, pygame.Rect(48, 150, W - 96, H - 280), 3, border_radius=28)
        sr = ROWS // 2
        sx, sy = self.center(0, sr)
        dx, dy = self.center(COLS - 1, sr)
        pygame.draw.circle(s, COPP, (sx - 86, sy), 34)
        pygame.draw.circle(s, GOLD, (sx - 86, sy), 18)
        pygame.draw.circle(s, ROSE, (dx + 86, dy), 34)
        pygame.draw.circle(s, CREAM, (dx + 86, dy), 16)
        for r in range(ROWS):
            for c in range(COLS):
                self.draw_pipe(s, c, r)
        if self.flow > 0:
            veil = pygame.Surface((W, H), pygame.SRCALPHA)
            veil.fill((80, 255, 160, int(40 * self.flow)))
            s.blit(veil, (0, 0))
        for sp in self.sparks:
            pygame.draw.circle(s, sp.col, (int(sp.x), int(sp.y)), max(1, int(sp.r * sp.life / 0.4)))
        if self.flash > 0:
            veil = pygame.Surface((W, H), pygame.SRCALPHA)
            veil.fill((255, 230, 120, int(70 * self.flash / 0.28)))
            s.blit(veil, (0, 0))
        title = self.font_lg.render(TITLE, True, GOLD)
        s.blit(title, title.get_rect(center=(W // 2, 52)))
        handle = self.font_sm.render(HANDLE, True, MINT)
        s.blit(handle, handle.get_rect(center=(W // 2, 102)))
        s.blit(self.font_md.render(f"FLOW  {self.score}", True, JADE), (64, 1788))
        s.blit(self.font_md.render(f"NET  {self.circuits}", True, COPP), (W - 280, 1788))
        hint = self.font_sm.render("twist pipes  copper source -> rose drain", True, CREAM)
        s.blit(hint, hint.get_rect(center=(W // 2, 1844)))
        for tag, x, y, life, col in self.pops:
            img = self.font_md.render(tag, True, col)
            s.blit(img, img.get_rect(center=(int(x), int(y))))
        foot = self.font_sm.render("click tile to rotate   R reset   ESC quit", True, (160, 210, 180))
        s.blit(foot, foot.get_rect(center=(W // 2, H - 24)))

    def handle(self, ev) -> None:
        if ev.type == pygame.QUIT:
            self.running = False
        elif ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                self.running = False
            elif ev.key == pygame.K_r:
                self.reset()
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            mx, my = ev.pos
            c = (mx - OX) // CELL
            r = (my - OY) // CELL
            if 0 <= c < COLS and 0 <= r < ROWS:
                self.twist(c, r)

    def play(self) -> None:
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            for ev in pygame.event.get():
                self.handle(ev)
            self.update(dt)
            self.draw(self.surf)
            self.screen.blit(self.surf, (0, 0))
            pygame.display.flip()

    def record_mp4(self, path: str) -> None:
        cmd = [
            "ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
            "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-crf", "20", "-preset", "fast", "-movflags", "+faststart", path,
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        frames = FPS * 15
        for i in range(frames):
            self.update(1.0 / FPS)
            self.draw(self.surf)
            proc.stdin.write(pygame.image.tostring(self.surf, "RGB"))
            if i % 30 == 0:
                print(f"frame {i}/{frames}", flush=True)
        proc.stdin.close()
        rc = proc.wait()
        if rc != 0:
            raise SystemExit(f"ffmpeg failed: {rc}")
        print("wrote", path)


def main() -> None:
    record = "--record" in sys.argv or os.environ.get("ELBOWOS_RECORD") == "1"
    play = "--play" in sys.argv
    if record or not play:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    pygame.init()
    pygame.font.init()
    g = Game(record or not play)
    if record or not play:
        out = os.environ.get("ELBOWOS_MP4", "/home/workdir/artifacts/JADEITE_JUNCTION_ElbowOS.mp4")
        g.record_mp4(out)
    else:
        g.play()
    pygame.quit()


if __name__ == "__main__":
    main()
