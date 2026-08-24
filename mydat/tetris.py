#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
コマンドライン・テトリス (curses使用)

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
"""

import curses
import random
import time

BOARD_W = 10
BOARD_H = 20

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

# 各ミノに割り当てる背景色 (curses標準色)
COLOR_MAP = {
    'I': curses.COLOR_CYAN,
    'O': curses.COLOR_YELLOW,
    'T': curses.COLOR_MAGENTA,
    'S': curses.COLOR_GREEN,
    'Z': curses.COLOR_RED,
    'J': curses.COLOR_BLUE,
    'L': curses.COLOR_WHITE,
}

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


def init_colors():
    curses.start_color()
    try:
        curses.use_default_colors()
        bg_default = -1
    except curses.error:
        bg_default = curses.COLOR_BLACK

    pairs = {}
    pair_id = 1
    for kind, color in COLOR_MAP.items():
        curses.init_pair(pair_id, curses.COLOR_BLACK, color)
        pairs[kind] = curses.color_pair(pair_id)
        pair_id += 1

    curses.init_pair(pair_id, curses.COLOR_WHITE, bg_default)
    pairs['border'] = curses.color_pair(pair_id) | curses.A_BOLD
    pair_id += 1

    curses.init_pair(pair_id, curses.COLOR_WHITE, bg_default)
    pairs['text'] = curses.color_pair(pair_id)
    pair_id += 1

    curses.init_pair(pair_id, curses.COLOR_WHITE, bg_default)
    pairs['ghost'] = curses.color_pair(pair_id) | curses.A_DIM
    return pairs


def safe_addstr(stdscr, y, x, text, attr=0):
    max_y, max_x = stdscr.getmaxyx()
    if y < 0 or y >= max_y or x >= max_x:
        return
    if x < 0:
        text = text[-x:]
        x = 0
    if x + len(text) > max_x:
        text = text[: max_x - x]
    if text:
        try:
            stdscr.addstr(y, x, text, attr)
        except curses.error:
            pass


def draw_cell(stdscr, y, x, pair):
    safe_addstr(stdscr, y, x, "  ", pair)


def draw_board_frame(stdscr, top, left, pairs):
    width = BOARD_W * 2
    safe_addstr(stdscr, top, left, "+" + "-" * width + "+", pairs['border'])
    for row in range(BOARD_H):
        safe_addstr(stdscr, top + 1 + row, left, "|", pairs['border'])
        safe_addstr(stdscr, top + 1 + row, left + width + 1, "|", pairs['border'])
    safe_addstr(stdscr, top + BOARD_H + 1, left, "+" + "-" * width + "+", pairs['border'])


def draw_game(stdscr, game, pairs, top, left):
    draw_board_frame(stdscr, top, left, pairs)

    board_top = top + 1
    board_left = left + 1

    # 固定済みブロック
    for y in range(BOARD_H):
        for x in range(BOARD_W):
            kind = game.board[y][x]
            if kind is not None:
                draw_cell(stdscr, board_top + y, board_left + x * 2, pairs[kind])

    if not game.game_over:
        # ゴースト(落下予測位置)
        gy = game.ghost_y()
        for x, y in game.current.cells(y=gy):
            if 0 <= y < BOARD_H and 0 <= x < BOARD_W:
                safe_addstr(stdscr, board_top + y, board_left + x * 2, "::", pairs['ghost'])

        # 現在落下中のブロック
        for x, y in game.current.cells():
            if 0 <= y < BOARD_H and 0 <= x < BOARD_W:
                draw_cell(stdscr, board_top + y, board_left + x * 2, pairs[game.current.kind])

    # サイドパネル
    panel_left = left + BOARD_W * 2 + 4
    safe_addstr(stdscr, top, panel_left, "NEXT", pairs['text'] | curses.A_BOLD)
    for py in range(4):
        safe_addstr(stdscr, top + 1 + py, panel_left, " " * 10, pairs['text'])
    for x, y in SHAPES[game.next_kind][0]:
        draw_cell(stdscr, top + 1 + y, panel_left + x * 2, pairs[game.next_kind])

    info_top = top + 6
    safe_addstr(stdscr, info_top, panel_left, f"SCORE: {game.score}", pairs['text'])
    safe_addstr(stdscr, info_top + 1, panel_left, f"LEVEL: {game.level}", pairs['text'])
    safe_addstr(stdscr, info_top + 2, panel_left, f"LINES: {game.lines}", pairs['text'])

    controls_top = info_top + 4
    controls = [
        "[<-][->] move",
        "[UP]     rotate",
        "[DOWN]   soft drop",
        "[SPACE]  hard drop",
        "[p]      pause",
        "[q]      quit",
    ]
    for i, line in enumerate(controls):
        safe_addstr(stdscr, controls_top + i, panel_left, line, pairs['text'])

    if game.game_over:
        msg = " GAME OVER - Enter:restart / q:quit "
        my = board_top + BOARD_H // 2
        mx = board_left + max(0, (BOARD_W * 2 - len(msg)) // 2)
        safe_addstr(stdscr, my, mx, msg, pairs['text'] | curses.A_REVERSE | curses.A_BOLD)


def main(stdscr):
    curses.curs_set(0)
    stdscr.keypad(True)
    stdscr.nodelay(True)
    stdscr.timeout(30)

    pairs = init_colors()

    game = Game()
    last_drop = time.time()
    paused = False

    top, left = 1, 1

    while True:
        stdscr.erase()

        now = time.time()
        if not game.game_over and not paused:
            if now - last_drop >= game.drop_interval():
                game.soft_drop()
                last_drop = now

        status = ""
        if paused:
            status = " -- PAUSED -- "
        safe_addstr(stdscr, 0, left, "TETRIS " + status, pairs['text'] | curses.A_BOLD)

        draw_game(stdscr, game, pairs, top, left)
        stdscr.refresh()

        try:
            key = stdscr.getch()
        except curses.error:
            key = -1

        if key == -1:
            continue

        if key in (ord('q'), ord('Q')):
            break

        if game.game_over:
            if key in (curses.KEY_ENTER, 10, 13):
                game = Game()
                last_drop = time.time()
                paused = False
            continue

        if key in (ord('p'), ord('P')):
            paused = not paused
            continue

        if paused:
            continue

        if key == curses.KEY_LEFT:
            game.try_move(-1, 0)
        elif key == curses.KEY_RIGHT:
            game.try_move(1, 0)
        elif key == curses.KEY_DOWN:
            game.soft_drop()
            last_drop = time.time()
        elif key == curses.KEY_UP:
            game.rotate()
        elif key == ord(' '):
            game.hard_drop()
            last_drop = time.time()


def run():
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
