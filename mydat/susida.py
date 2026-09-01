#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
寿司打風 タイピングゲーム (curses非依存 / 標準ライブラリのみ)

「寿司打」にインスパイアされた、時間制限内にどれだけ日本語をローマ字入力
できるかを競うタイピングゲームです。お題(寿司ネタなど)の読みをローマ字で
入力していくと"稼いだ金額"が加算され、制限時間終了時にコース料金との
損益が表示されます。

ローマ字入力について:
    各モーラ(かな1文字、拗音は2文字)を、そのかなに対応するローマ字に
    置き換えていくだけのシンプルなルールです。「し」は shi/si、「つ」は
    tsu/tu、「ん」は n/nn など、よくある表記ゆれはなるべく受け付けます。
    促音(っ)は、xtu/ltu(またはxtsu/ltsu)を単独のモーラとして入力する
    方法と、次の子音を重ねて入力する従来方法(例: がっこう→gakkou)の
    どちらも受け付けます。長音(ー)は半角ハイフン「-」で入力します。

操作方法:
    メニュー画面 : 1 / 2 / 3  コース選択、  q  終了
    プレイ中     : a-z        ローマ字入力
                   Backspace  1文字取り消し
                   Esc        一時停止/再開
                   q          終了
    結果画面     : Enter      メニューに戻る、  q  終了

単語データ:
    sushi_words.txt (このスクリプトと同じディレクトリ) から読み込みます。
    フォーマットは「表示文字列<TAB>読み」を1行ずつ。読みはひらがな/
    カタカナどちらでも構いません。

対応環境:
    ANSIエスケープシーケンス + UTF-8表示に対応したターミナル。
    Windowsでは Windows Terminal の利用を推奨します
    (レガシーな cmd.exe の場合は事前に `chcp 65001` を実行してください)。
"""

import itertools
import os
import random
import sys
import time
import unicodedata

# ============================================================
# かな -> ローマ字 変換エンジン
# ============================================================

# 各モーラに対する有効なローマ字表記(先頭が標準的な表記)
KANA_TABLE = {
    "あ": ["a"], "い": ["i"], "う": ["u"], "え": ["e"], "お": ["o"],
    "か": ["ka"], "き": ["ki"], "く": ["ku"], "け": ["ke"], "こ": ["ko"],
    "さ": ["sa"], "し": ["shi", "si"], "す": ["su"], "せ": ["se"], "そ": ["so"],
    "た": ["ta"], "ち": ["chi", "ti"], "つ": ["tsu", "tu"], "て": ["te"], "と": ["to"],
    "な": ["na"], "に": ["ni"], "ぬ": ["nu"], "ね": ["ne"], "の": ["no"],
    "は": ["ha"], "ひ": ["hi"], "ふ": ["fu", "hu"], "へ": ["he"], "ほ": ["ho"],
    "ま": ["ma"], "み": ["mi"], "む": ["mu"], "め": ["me"], "も": ["mo"],
    "や": ["ya"], "ゆ": ["yu"], "よ": ["yo"],
    "ら": ["ra"], "り": ["ri"], "る": ["ru"], "れ": ["re"], "ろ": ["ro"],
    "わ": ["wa"], "を": ["wo"],
    "が": ["ga"], "ぎ": ["gi"], "ぐ": ["gu"], "げ": ["ge"], "ご": ["go"],
    "ざ": ["za"], "じ": ["ji", "zi"], "ず": ["zu"], "ぜ": ["ze"], "ぞ": ["zo"],
    "だ": ["da"], "ぢ": ["ji", "di"], "づ": ["zu", "du"], "で": ["de"], "ど": ["do"],
    "ば": ["ba"], "び": ["bi"], "ぶ": ["bu"], "べ": ["be"], "ぼ": ["bo"],
    "ぱ": ["pa"], "ぴ": ["pi"], "ぷ": ["pu"], "ぺ": ["pe"], "ぽ": ["po"],
    # 拗音
    "きゃ": ["kya"], "きゅ": ["kyu"], "きょ": ["kyo"],
    "しゃ": ["sha", "sya"], "しゅ": ["shu", "syu"], "しょ": ["sho", "syo"],
    "ちゃ": ["cha", "tya"], "ちゅ": ["chu", "tyu"], "ちょ": ["cho", "tyo"],
    "にゃ": ["nya"], "にゅ": ["nyu"], "にょ": ["nyo"],
    "ひゃ": ["hya"], "ひゅ": ["hyu"], "ひょ": ["hyo"],
    "みゃ": ["mya"], "みゅ": ["myu"], "みょ": ["myo"],
    "りゃ": ["rya"], "りゅ": ["ryu"], "りょ": ["ryo"],
    "ぎゃ": ["gya"], "ぎゅ": ["gyu"], "ぎょ": ["gyo"],
    "じゃ": ["ja", "zya"], "じゅ": ["ju", "zyu"], "じょ": ["jo", "zyo"],
    "びゃ": ["bya"], "びゅ": ["byu"], "びょ": ["byo"],
    "ぴゃ": ["pya"], "ぴゅ": ["pyu"], "ぴょ": ["pyo"],
    # 単独小文字(まれな外来語用)
    "ぁ": ["xa", "la", "a"], "ぃ": ["xi", "li", "i"], "ぅ": ["xu", "lu", "u"],
    "ぇ": ["xe", "le", "e"], "ぉ": ["xo", "lo", "o"],
    # 撥音・促音・長音 (それぞれ独立したモーラとして、前後の文脈に関係なく
    # 固定のローマ字を割り当てる。前の音を重ねたり伸ばしたりする特殊処理は
    # あえて行わない、単純な「1モーラ=決まったローマ字」ルール)
    "ん": ["n", "nn"],
    "っ": ["xtu", "ltu", "xtsu", "ltsu"],
    "ー": ["-"],
}

HIRAGANA_START, HIRAGANA_END = 0x3041, 0x3096
KATAKANA_START, KATAKANA_END = 0x30A1, 0x30F6
KATA_HIRA_OFFSET = 0x60


def kata_to_hira(ch):
    """カタカナ1文字をひらがなに変換する(範囲外はそのまま返す)"""
    code = ord(ch)
    if KATAKANA_START <= code <= KATAKANA_END:
        return chr(code - KATA_HIRA_OFFSET)
    return ch


def normalize_reading(s):
    """読み文字列内のカタカナをすべてひらがなに正規化する"""
    return "".join(kata_to_hira(c) for c in s)


def tokenize_mora(s):
    """ひらがな文字列をモーラ単位のトークン列に分割する。
    拗音(きゃ等)は2文字1トークンとしてまとめる。それ以外(ん・っ・ー含む)は
    すべて1文字1トークンとして扱い、KANA_TABLEを引くだけのシンプルな規則。
    """
    tokens = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if i + 1 < n and s[i + 1] in ("ゃ", "ゅ", "ょ") and (c + s[i + 1]) in KANA_TABLE:
            tokens.append(c + s[i + 1])
            i += 2
            continue
        tokens.append(c)
        i += 1
    return tokens


def reading_to_chunks(reading):
    """正規化済みひらがな文字列 -> [ [alt1, alt2, ...], ... ] のチャンク列に変換。

    基本は各モーラを独立にKANA_TABLEで引くだけのシンプルな規則。
    ただし促音(っ)だけは例外的に、次のモーラと合わせて1チャンクとして
    まとめ、次の2通りの入力方法を両方受け付ける:
      1) 独立したモーラとして xtu/ltu/xtsu/ltsu を打つ方法
      2) 次の子音を重ねて打つ従来方法 (例: がっこう -> gakkou)
    """
    tokens = tokenize_mora(reading)
    chunks = []
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]

        if tok == "っ" and i + 1 < n:
            next_tok = tokens[i + 1]
            next_alts = KANA_TABLE.get(next_tok, [next_tok])

            combined = []
            seen = set()

            def add(s):
                if s not in seen:
                    seen.add(s)
                    combined.append(s)

            # 1) 独立したモーラとして入力する方法 (xtu/ltu/xtsu/ltsu + 次のモーラ)
            for a in KANA_TABLE["っ"]:
                for b in next_alts:
                    add(a + b)
            # 2) 次の子音を重ねて入力する従来方法 (例: k + ko -> kko)
            for b in next_alts:
                if b and b[0] not in "aiueo":
                    add(b[0] + b)

            chunks.append(combined)
            i += 2
            continue

        alts = KANA_TABLE.get(tok)
        if alts is None:
            # テーブルにない文字はそのまま1文字ローマ字として扱う(フォールバック)
            alts = [tok]
        chunks.append(alts)
        i += 1

    return chunks


def compute_completions(chunks, limit=128):
    """チャンク列から、有効な全ローマ字表記の集合を計算する"""
    if not chunks:
        return {""}
    combos = itertools.islice(itertools.product(*chunks), limit)
    return {"".join(parts) for parts in combos}


def compute_canonical(chunks):
    """標準的な(先頭表記の)ローマ字文字列を組み立てる"""
    return "".join(alts[0] for alts in chunks if alts)


# ============================================================
# 単語データ
# ============================================================

class WordEntry:
    __slots__ = ("display", "reading", "canonical", "completions")

    def __init__(self, display, reading):
        self.display = display
        self.reading = reading
        norm = normalize_reading(reading)
        chunks = reading_to_chunks(norm)
        self.canonical = compute_canonical(chunks)
        self.completions = compute_completions(chunks)


DEFAULT_WORDS = [
    ("すし", "すし"), ("まぐろ", "まぐろ"), ("たまご", "たまご"),
    ("おいしい", "おいしい"), ("ありがとう", "ありがとう"),
    ("がっこう", "がっこう"), ("こんにちは", "こんにちは"),
]

WORDS_FILENAME = "sushi_words.txt"


def load_word_entries(path):
    entries = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n").strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) < 2:
                    parts = line.split()
                if len(parts) < 2:
                    continue
                display, reading = parts[0], parts[1]
                entries.append(WordEntry(display, reading))
    except OSError:
        return None
    return entries if entries else None


def _load_default_entries():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(script_dir, WORDS_FILENAME)
    entries = load_word_entries(path)
    if entries is None:
        print(
            f"[警告] {path} が見つからないため、内蔵の簡易単語リストで起動します。",
            file=sys.stderr,
        )
        entries = [WordEntry(d, r) for d, r in DEFAULT_WORDS]
    return entries


WORD_ENTRIES = _load_default_entries()

# ============================================================
# ゲームロジック
# ============================================================

YEN_PER_CHAR = 3
WORD_BONUS = 5

COURSES = [
    (60, 3000, "お手軽3000円コース"),
    (90, 5000, "しっかり5000円コース"),
    (150, 10000, "遊び放題10000円コース"),
]


class Game:
    def __init__(self, words):
        self.words = words
        self.bag = []
        self._last_word = None
        self._refill_bag()

        self.total_time = 0
        self.cost = 0
        self.course_name = ""
        self.start_time = 0.0
        self.score = 0
        self.completed = 0
        self.mistakes = 0
        self.keystrokes = 0
        self.total_chars_typed = 0
        self.typed_buffer = ""
        self.current = None
        self.finished = False
        self.paused = False
        self._pause_started = 0.0

    def _refill_bag(self):
        self.bag = list(self.words)
        random.shuffle(self.bag)
        if self._last_word is not None and self.bag and self.bag[0] is self._last_word:
            if len(self.bag) > 1:
                self.bag[0], self.bag[1] = self.bag[1], self.bag[0]

    def _pop_word(self):
        if not self.bag:
            self._refill_bag()
        w = self.bag.pop()
        self._last_word = w
        return w

    def start(self, total_time, cost, course_name=""):
        self.total_time = total_time
        self.cost = cost
        self.course_name = course_name
        self.start_time = time.time()
        self.score = 0
        self.completed = 0
        self.mistakes = 0
        self.keystrokes = 0
        self.total_chars_typed = 0
        self.typed_buffer = ""
        self.current = self._pop_word()
        self.finished = False
        self.paused = False

    def toggle_pause(self):
        if self.finished:
            return
        if self.paused:
            self.start_time += time.time() - self._pause_started
            self.paused = False
        else:
            self._pause_started = time.time()
            self.paused = True

    def time_left(self):
        if self.paused:
            elapsed = self._pause_started - self.start_time
        else:
            elapsed = time.time() - self.start_time
        return max(0.0, self.total_time - elapsed)

    def update(self):
        if not self.finished and not self.paused and self.time_left() <= 0:
            self.finished = True

    def handle_char(self, ch):
        if self.finished or self.paused or self.current is None:
            return
        ch = ch.lower()
        if len(ch) != 1 or not (ch.isalpha() or ch == "-"):
            return
        self.keystrokes += 1
        candidate = self.typed_buffer + ch
        if not any(c.startswith(candidate) for c in self.current.completions):
            self.mistakes += 1
            return
        self.typed_buffer = candidate
        self.total_chars_typed += 1
        if candidate in self.current.completions:
            self._complete_word()

    def handle_backspace(self):
        if self.finished or self.paused:
            return
        if self.typed_buffer:
            self.typed_buffer = self.typed_buffer[:-1]

    def _complete_word(self):
        earned = len(self.typed_buffer) * YEN_PER_CHAR + WORD_BONUS
        self.score += earned
        self.completed += 1
        self.typed_buffer = ""
        self.current = self._pop_word()

    def accuracy(self):
        if self.keystrokes == 0:
            return 100.0
        correct = self.keystrokes - self.mistakes
        return 100.0 * correct / self.keystrokes

    def chars_per_sec(self):
        elapsed = self.total_time - self.time_left()
        if elapsed <= 0:
            return 0.0
        return self.total_chars_typed / elapsed

    def profit(self):
        return self.score - self.cost


# ============================================================
# 表示幅計算(全角文字を考慮)
# ============================================================

def display_width(s):
    width = 0
    for c in s:
        w = unicodedata.east_asian_width(c)
        width += 2 if w in ("W", "F") else 1
    return width


def pad_to(s, width):
    w = display_width(s)
    if w >= width:
        return s
    return s + " " * (width - w)


# ============================================================
# ANSI描画ヘルパー
# ============================================================

RESET = "\x1b[0m"
HIDE_CURSOR = "\x1b[?25l"
SHOW_CURSOR = "\x1b[?25h"
CLEAR_SCREEN = "\x1b[2J"
HOME = "\x1b[H"

BOX_WIDTH = 56


def move_to(row, col):
    return f"\x1b[{row};{col}H"


def c_bold(s):
    return f"\x1b[1m{s}{RESET}"


def c_green(s):
    return f"\x1b[1;32m{s}{RESET}"


def c_yellow(s):
    return f"\x1b[33m{s}{RESET}"


def c_gray(s):
    return f"\x1b[90m{s}{RESET}"


def c_cyan(s):
    return f"\x1b[36m{s}{RESET}"


def c_red(s):
    return f"\x1b[1;31m{s}{RESET}"


def c_reverse(s):
    return f"\x1b[7m{s}{RESET}"


def box_line(text_line=""):
    return "| " + pad_to(text_line, BOX_WIDTH) + " |"


def box_border(ch="-"):
    return "+" + ch * (BOX_WIDTH + 2) + "+"


# ============================================================
# 入力(クロスプラットフォーム、標準ライブラリのみ)
# ============================================================

IS_WINDOWS = os.name == "nt"

if IS_WINDOWS:
    import msvcrt
else:
    import select
    import termios
    import tty


class Terminal:
    """rawモード切替・ANSI/UTF-8有効化・非ブロッキングキー入力をまとめる"""

    def __enter__(self):
        if IS_WINDOWS:
            self._enable_windows_ansi()
        else:
            self._fd = sys.stdin.fileno()
            self._old_settings = termios.tcgetattr(self._fd)
            tty.setcbreak(self._fd)
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
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
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)

    def get_key(self):
        """非ブロッキングでキーを読む。戻り値は以下のいずれか:
        'ENTER' / 'BACKSPACE' / 'ESC' / 1文字の小文字英数字 / None
        (矢印キー等の未使用エスケープシーケンスは読み捨てて無視する)
        """
        return self._get_key_windows() if IS_WINDOWS else self._get_key_unix()

    @staticmethod
    def _get_key_windows():
        if not msvcrt.kbhit():
            return None
        ch = msvcrt.getch()
        if ch in (b"\x00", b"\xe0"):
            msvcrt.getch()  # ファンクション/矢印キーの2バイト目を読み捨て
            return None
        if ch == b"\r":
            return "ENTER"
        if ch == b"\x08":
            return "BACKSPACE"
        if ch == b"\x1b":
            return "ESC"
        if ch == b"\x03":
            raise KeyboardInterrupt
        try:
            c = ch.decode("utf-8", errors="ignore")
        except UnicodeDecodeError:
            return None
        if c and (c.isalnum() or c == "-"):
            return c.lower()
        return None

    @staticmethod
    def _get_key_unix():
        if not select.select([sys.stdin], [], [], 0)[0]:
            return None
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            if select.select([sys.stdin], [], [], 0)[0]:
                ch2 = sys.stdin.read(1)
                if ch2 == "[":
                    if select.select([sys.stdin], [], [], 0)[0]:
                        sys.stdin.read(1)  # 矢印キーコードを読み捨て
                    return None
                return "ESC"
            return "ESC"
        if ch in ("\r", "\n"):
            return "ENTER"
        if ch in ("\x7f", "\x08"):
            return "BACKSPACE"
        if ch == "\x03":
            raise KeyboardInterrupt
        if ch.isalnum() or ch == "-":
            return ch.lower()
        return None


# ============================================================
# 描画
# ============================================================

def render_menu():
    out = [HOME]
    out.append(move_to(1, 1) + c_bold("=== 寿司打風 タイピングゲーム ==="))
    out.append(move_to(3, 1) + box_border())
    row = 4
    out.append(move_to(row, 1) + box_line("制限時間内にローマ字入力でお題を打ち切ろう!"))
    row += 1
    out.append(move_to(row, 1) + box_line())
    row += 1
    for i, (seconds, cost, name) in enumerate(COURSES, start=1):
        line = f"[{i}] {name}  (制限時間 約{seconds}秒)"
        out.append(move_to(row, 1) + box_line(line))
        row += 1
    out.append(move_to(row, 1) + box_line())
    row += 1
    out.append(move_to(row, 1) + box_line("数字キーでコースを選択 / q で終了"))
    row += 1
    out.append(move_to(row, 1) + box_border())
    sys.stdout.write("".join(out))
    sys.stdout.flush()


def render_playing(game):
    out = [HOME]
    out.append(move_to(1, 1) + c_bold("=== 寿司打風 タイピングゲーム ===") + "   " + c_gray(game.course_name))
    out.append(move_to(3, 1) + box_border())

    row = 4
    word = game.current
    out.append(move_to(row, 1) + box_line("おだい:"))
    row += 1
    out.append(move_to(row, 1) + box_line("  " + word.display))
    row += 1
    out.append(move_to(row, 1) + box_line())
    row += 1

    typed = game.typed_buffer
    rest = word.canonical[len(typed):] if word.canonical.startswith(typed) else word.canonical
    typed_disp = c_green(typed)
    rest_disp = c_yellow(rest)
    out.append(move_to(row, 1) + box_line("  よみ:"))
    row += 1
    # ANSIコード込みだと表示幅計算がずれるため、box_lineは使わずシンプルに出力
    plain_line = "  " + typed + rest
    colored_line = "  " + typed_disp + rest_disp
    pad = max(0, BOX_WIDTH - display_width(plain_line))
    out.append(move_to(row, 1) + "| " + colored_line + (" " * pad) + " |")
    row += 1
    out.append(move_to(row, 1) + box_line())
    row += 1

    if game.paused:
        out.append(move_to(row, 1) + box_line(c_reverse(" -- PAUSED (Esc で再開) -- ")))
    else:
        out.append(move_to(row, 1) + box_line())
    row += 1
    out.append(move_to(row, 1) + box_border())
    row += 2

    out.append(move_to(row, 1) + c_cyan(f"残り時間: {game.time_left():5.1f}秒"))
    row += 1
    out.append(move_to(row, 1) + f"金額    : ¥{game.score}")
    row += 1
    out.append(move_to(row, 1) + f"完了    : {game.completed} 問   ミス: {game.mistakes}")
    row += 1
    out.append(move_to(row, 1) + f"正解率  : {game.accuracy():.0f}%   速度: {game.chars_per_sec():.1f} 文字/秒")
    row += 1
    out.append(move_to(row, 1) + c_gray("a-z:入力  Backspace:1文字戻す  Esc:一時停止  q:終了"))

    sys.stdout.write("".join(out))
    sys.stdout.flush()


def render_result(game):
    out = [HOME]
    out.append(move_to(1, 1) + c_bold("=== 結果発表 ==="))
    out.append(move_to(3, 1) + box_border())

    row = 4
    out.append(move_to(row, 1) + box_line(f"コース    : {game.course_name}"))
    row += 1
    out.append(move_to(row, 1) + box_line(f"稼いだ金額: ¥{game.score}"))
    row += 1
    out.append(move_to(row, 1) + box_line(f"コース料金: ¥{game.cost}"))
    row += 1

    profit = game.profit()
    if profit >= 0:
        result_line = f"損益      : 得! (+¥{profit})"
    else:
        result_line = f"損益      : 損...(-¥{-profit})"
    out.append(move_to(row, 1) + box_line(result_line))
    row += 1
    out.append(move_to(row, 1) + box_line())
    row += 1
    out.append(move_to(row, 1) + box_line(f"完了問題数: {game.completed} 問"))
    row += 1
    out.append(move_to(row, 1) + box_line(f"総打鍵数  : {game.keystrokes} 打  (ミス: {game.mistakes})"))
    row += 1
    out.append(move_to(row, 1) + box_line(f"正解率    : {game.accuracy():.1f} %"))
    row += 1
    out.append(move_to(row, 1) + box_line(f"平均速度  : {game.chars_per_sec():.2f} 文字/秒"))
    row += 1
    out.append(move_to(row, 1) + box_line())
    row += 1
    out.append(move_to(row, 1) + box_line("Enter でメニューに戻る / q で終了"))
    row += 1
    out.append(move_to(row, 1) + box_border())

    sys.stdout.write("".join(out))
    sys.stdout.flush()


# ============================================================
# メインループ
# ============================================================

def main():
    with Terminal() as term:
        state = "menu"
        game = Game(WORD_ENTRIES)

        while True:
            if state == "menu":
                render_menu()
            elif state == "playing":
                game.update()
                render_playing(game)
                if game.finished:
                    state = "result"
                    continue
            elif state == "result":
                render_result(game)

            key = term.get_key()
            if key is None:
                time.sleep(0.02)
                continue

            if key == "q":
                return

            if state == "menu":
                if key in ("1", "2", "3"):
                    idx = int(key) - 1
                    seconds, cost, name = COURSES[idx]
                    game = Game(WORD_ENTRIES)
                    game.start(seconds, cost, name)
                    state = "playing"

            elif state == "playing":
                if key == "ESC":
                    game.toggle_pause()
                elif key == "BACKSPACE":
                    game.handle_backspace()
                elif len(key) == 1 and (key.isalpha() or key == "-"):
                    game.handle_char(key)

            elif state == "result":
                if key == "ENTER":
                    state = "menu"


def run():
    try:
        main()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
