#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
コマンドライン・テトリス (curses非依存版 / 標準ライブラリのみ)

ゲームロジック(Piece/Gameクラス)はcurses版と完全に同一です。
画面描画と入力受付だけをANSIエスケープシーケンス + 標準モジュール
(Unix: termios/tty/select, Windows: msvcrt/ctypes)で実装しています。

操作方法:
    ← / →   : 左右移動
    ↓       : ソフトドロップ(1マス落下)
    ↑       : 回転
    Space   : ハードドロップ(一気に落下)
    p       : 一時停止
    q       : 終了
    Enter   : ゲームオーバー後にリスタート

1ブロック = 半角スペース2つ分の幅で、色付きの背景として描画します。
何もないマスは何も描画しません(スペースのみ)。

対応環境:
    ANSIエスケープシーケンスに対応したターミナル
    (Windows 10以降のターミナル/cmd.exe/PowerShell、macOS、Linuxの各種端末)
"""

import os
import random
import sys
import time

BOARD_W = 10
BOARD_H = 20

# ============================================================
# ゲームロジック (curses版と完全に同一)
# ============================================================

# 各テトリミノの回転パターン (4状態分、(x, y)オフセットのリスト)
SHAPES = {
    'I': [
        [(0, 1), (1, 1), (2, 1), (3, 1)],
        [(2, 0), (2, 1), (2, 2), (2, 3)],
        [(0, 2), (1, 2), (2, 2), (3, 2)],
        [(1, 0), (1, 1), (1, 2), (1, 3)],
    ],
    'O': [
        [(1, 0), (2, 0), (1, 1), (2, 1)],
    ] * 4,
    'T': [
        [(1, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (1, 1), (2, 1), (1, 2)],
        [(0, 1), (1, 1), (2, 1), (1, 2)],
        [(1, 0), (0, 1), (1, 1), (1, 2)],
    ],
    'S': [
        [(1, 0), (2, 0), (0, 1), (1, 1)],
        [(1, 0), (1, 1), (2, 1), (2, 2)],
        [(1, 1), (2, 1), (0, 2), (1, 2)],
        [(0, 0), (0, 1), (1, 1), (1, 2)],
    ],
    'Z': [
        [(0, 0), (1, 0), (1, 1), (2, 1)],
        [(2, 0), (1, 1), (2, 1), (1, 2)],
        [(0, 1), (1, 1), (1, 2), (2, 2)],
        [(1, 0), (0, 1), (1, 1), (0, 2)],
    ],
    'J': [
        [(0, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (2, 0), (1, 1), (1, 2)],
        [(0, 1), (1, 1), (2, 1), (2, 2)],
        [(1, 0), (1, 1), (0, 2), (1, 2)],
    ],
    'L': [
        [(2, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (1, 1), (1, 2), (2, 2)],
        [(0, 1), (1, 1), (2, 1), (0, 2)],
        [(0, 0), (1, 0), (1, 1), (1, 2)],
    ],
}

KINDS = list(SHAPES.keys())

SCORE_TABLE = {0: 0, 1: 100, 2: 300, 3: 500, 4: 800}


class Piece:
    def __init__(self, kind):
        self.kind = kind
        self.rot = 0
        self.x = 3
        self.y = 0

    def cells(self, rot=None, x=None, y=None):
        r = self.rot if rot is None else rot
        px = self.x if x is None else x
        py = self.y if y is None else y
        return [(px + dx, py + dy) for dx, dy in SHAPES[self.kind][r % 4]]


def new_bag():
    bag = list(KINDS)
    random.shuffle(bag)
    return bag


class Game:
    def __init__(self):
        self.board = [[None] * BOARD_W for _ in range(BOARD_H)]
        self.bag = new_bag()
        self.next_kind = self.bag.pop()
        self.score = 0
        self.lines = 0
        self.level = 1
        self.game_over = False
        self.current = None
        self.spawn()

    def spawn(self):
        if not self.bag:
            self.bag = new_bag()
        kind = self.next_kind
        self.next_kind = self.bag.pop()
        self.current = Piece(kind)
        if self.collide(self.current.cells()):
            self.game_over = True

    def collide(self, cells):
        for x, y in cells:
            if x < 0 or x >= BOARD_W or y >= BOARD_H:
                return True
            if y >= 0 and self.board[y][x] is not None:
                return True
        return False

    def lock(self):
        for x, y in self.current.cells():
            if 0 <= y < BOARD_H and 0 <= x < BOARD_W:
                self.board[y][x] = self.current.kind
        self.clear_lines()
        if not self.game_over:
            self.spawn()

    def clear_lines(self):
        remaining = [row for row in self.board if any(c is None for c in row)]
        cleared = BOARD_H - len(remaining)
        for _ in range(cleared):
            remaining.insert(0, [None] * BOARD_W)
        self.board = remaining
        if cleared:
            self.lines += cleared
            self.score += SCORE_TABLE[cleared] * self.level
            self.level = 1 + self.lines // 10

    def try_move(self, dx, dy):
        cells = self.current.cells(x=self.current.x + dx, y=self.current.y + dy)
        if not self.collide(cells):
            self.current.x += dx
            self.current.y += dy
            return True
        return False

    def rotate(self):
        new_rot = (self.current.rot + 1) % 4
        for kick in (0, -1, 1, -2, 2):
            cells = self.current.cells(rot=new_rot, x=self.current.x + kick)
            if not self.collide(cells):
                self.current.rot = new_rot
                self.current.x += kick
                return True
        return False

    def hard_drop(self):
        while self.try_move(0, 1):
            self.score += 2
        self.lock()

    def soft_drop(self):
        if self.try_move(0, 1):
            self.score += 1
        else:
            self.lock()

    def ghost_y(self):
        gy = self.current.y
        while not self.collide(self.current.cells(y=gy + 1)):
            gy += 1
        return gy

    def drop_interval(self):
        return max(0.08, 0.6 - (self.level - 1) * 0.05)


# ============================================================
# ここから下は curses非依存の 描画 / 入力 レイヤー
# (ANSIエスケープシーケンス + 標準ライブラリのみ)
# ============================================================

# 各ミノに割り当てる背景色 (ANSI標準16色の背景色コード)
ANSI_BG = {
    'I': 46,  # cyan
    'O': 43,  # yellow
    'T': 45,  # magenta
    'S': 42,  # green
    'Z': 41,  # red
    'J': 44,  # blue
    'L': 47,  # white
}

RESET = "\x1b[0m"
HIDE_CURSOR = "\x1b[?25l"
SHOW_CURSOR = "\x1b[?25h"
CLEAR_SCREEN = "\x1b[2J"
HOME = "\x1b[H"


def move_to(row, col):
    """1始まりの行・列にカーソル移動するエスケープシーケンス"""
    return f"\x1b[{row};{col}H"


def block(kind):
    """色付きブロック(半角スペース2つ分)"""
    return f"\x1b[30;{ANSI_BG[kind]}m  {RESET}"


def ghost_block():
    return f"\x1b[2m::{RESET}"


def text(s, bold=False):
    return f"\x1b[{'1;' if bold else ''}37m{s}{RESET}"


# ---------------- 入力(クロスプラットフォーム) ----------------

IS_WINDOWS = os.name == "nt"

if IS_WINDOWS:
    import msvcrt
else:
    import select
    import termios
    import tty


class Terminal:
    """rawモード切替・ANSI有効化・非ブロッキングキー入力をまとめたラッパー"""

    def __enter__(self):
        if IS_WINDOWS:
            self._enable_windows_ansi()
        else:
            self._fd = sys.stdin.fileno()
            self._old_settings = termios.tcgetattr(self._fd)
            tty.setcbreak(self._fd)
        sys.stdout.write(HIDE_CURSOR + CLEAR_SCREEN + HOME)
        sys.stdout.flush()
        return self

    def __exit__(self, exc_type, exc, tb):
        if not IS_WINDOWS:
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old_settings)
        sys.stdout.write(RESET + SHOW_CURSOR + CLEAR_SCREEN + HOME)
        sys.stdout.flush()

    @staticmethod
    def _enable_windows_ansi():
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)  # VT PROCESSING

    def get_key(self):
        """非ブロッキングでキーを読み取る。無ければNone。"""
        if IS_WINDOWS:
            return self._get_key_windows()
        return self._get_key_unix()

    @staticmethod
    def _get_key_windows():
        if not msvcrt.kbhit():
            return None
        ch = msvcrt.getch()
        if ch in (b"\x00", b"\xe0"):
            ch2 = msvcrt.getch()
            return {
                b"H": "UP", b"P": "DOWN", b"K": "LEFT", b"M": "RIGHT",
            }.get(ch2)
        if ch == b" ":
            return "SPACE"
        if ch in (b"\r", b"\n"):
            return "ENTER"
        if ch in (b"\x03",):  # Ctrl+C
            raise KeyboardInterrupt
        try:
            c = ch.decode("utf-8", errors="ignore")
        except UnicodeDecodeError:
            return None
        if c in ("p", "P"):
            return "p"
        if c in ("q", "Q"):
            return "q"
        return None

    @staticmethod
    def _get_key_unix():
        if not select.select([sys.stdin], [], [], 0)[0]:
            return None
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            # カーソルキーなどのエスケープシーケンス (ESC [ A/B/C/D)
            if select.select([sys.stdin], [], [], 0)[0]:
                ch2 = sys.stdin.read(1)
                if ch2 == "[" and select.select([sys.stdin], [], [], 0)[0]:
                    ch3 = sys.stdin.read(1)
                    return {
                        "A": "UP", "B": "DOWN", "C": "RIGHT", "D": "LEFT",
                    }.get(ch3)
            return None
        if ch == " ":
            return "SPACE"
        if ch in ("\r", "\n"):
            return "ENTER"
        if ch == "\x03":  # Ctrl+C
            raise KeyboardInterrupt
        if ch in ("p", "P"):
            return "p"
        if ch in ("q", "Q"):
            return "q"
        return None


# ---------------- 描画 ----------------

def render(game, top=1, left=1):
    out = []
    width = BOARD_W * 2

    out.append(move_to(top, left) + text("TETRIS", bold=True))

    # 枠
    out.append(move_to(top + 1, left) + text("+" + "-" * width + "+"))
    for row in range(BOARD_H):
        out.append(move_to(top + 2 + row, left) + text("|"))
        out.append(move_to(top + 2 + row, left + width + 1) + text("|"))
    out.append(move_to(top + 2 + BOARD_H, left) + text("+" + "-" * width + "+"))

    board_top = top + 2
    board_left = left + 1

    # 盤面(固定済みブロック。無ければ半角スペースで上書きしてクリア)
    for y in range(BOARD_H):
        row_chunks = []
        for x in range(BOARD_W):
            kind = game.board[y][x]
            row_chunks.append(block(kind) if kind else "  ")
        out.append(move_to(board_top + y, board_left) + "".join(row_chunks))

    if not game.game_over:
        # 現在のミノの位置に、盤面の内容を一旦復元してから重ね書きする
        # (前フレームの残像を消すため、行単位で毎回全再描画している)
        gy = game.ghost_y()
        ghost_cells = set(game.current.cells(y=gy))
        cur_cells = set(game.current.cells())
        for x, y in ghost_cells - cur_cells:
            if 0 <= y < BOARD_H and 0 <= x < BOARD_W and game.board[y][x] is None:
                out.append(move_to(board_top + y, board_left + x * 2) + ghost_block())
        for x, y in cur_cells:
            if 0 <= y < BOARD_H and 0 <= x < BOARD_W:
                out.append(
                    move_to(board_top + y, board_left + x * 2) + block(game.current.kind)
                )

    # サイドパネル
    panel_left = left + width + 4
    out.append(move_to(top + 1, panel_left) + text("NEXT", bold=True))
    for py in range(4):
        out.append(move_to(top + 2 + py, panel_left) + "          ")
    for x, y in SHAPES[game.next_kind][0]:
        out.append(move_to(top + 2 + y, panel_left + x * 2) + block(game.next_kind))

    info_top = top + 7
    out.append(move_to(info_top, panel_left) + text(f"SCORE: {game.score}   "))
    out.append(move_to(info_top + 1, panel_left) + text(f"LEVEL: {game.level}   "))
    out.append(move_to(info_top + 2, panel_left) + text(f"LINES: {game.lines}   "))

    controls_top = info_top + 4
    controls = [
        "<- ->  move",
        "UP     rotate",
        "DOWN   soft drop",
        "SPACE  hard drop",
        "p      pause",
        "q      quit",
    ]
    for i, line in enumerate(controls):
        out.append(move_to(controls_top + i, panel_left) + text(line))

    if game.game_over:
        msg = " GAME OVER - Enter:restart / q:quit "
        my = board_top + BOARD_H // 2
        mx = board_left + max(0, (width - len(msg)) // 2)
        out.append(move_to(my, mx) + f"\x1b[7m{msg}{RESET}")

    sys.stdout.write("".join(out))
    sys.stdout.flush()


# ---------------- メインループ ----------------

def main():
    with Terminal() as term:
        game = Game()
        last_drop = time.time()
        paused = False

        while True:
            now = time.time()
            if not game.game_over and not paused:
                if now - last_drop >= game.drop_interval():
                    game.soft_drop()
                    last_drop = now

            status = " -- PAUSED -- " if paused else ""
            render(game)
            if status:
                sys.stdout.write(move_to(1, 8) + text(status, bold=True))
                sys.stdout.flush()

            key = term.get_key()
            if key is None:
                time.sleep(0.02)
                continue

            if key == "q":
                break

            if game.game_over:
                if key == "ENTER":
                    game = Game()
                    last_drop = time.time()
                    paused = False
                continue

            if key == "p":
                paused = not paused
                continue

            if paused:
                continue

            if key == "LEFT":
                game.try_move(-1, 0)
            elif key == "RIGHT":
                game.try_move(1, 0)
            elif key == "DOWN":
                game.soft_drop()
                last_drop = time.time()
            elif key == "UP":
                game.rotate()
            elif key == "SPACE":
                game.hard_drop()
                last_drop = time.time()


def run():
    try:
        main()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
