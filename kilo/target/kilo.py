#!/usr/bin/env python3
"""
Kilo -- A very simple editor, ported to Python from the original C version
        (https://github.com/antirez/kilo by Salvatore Sanfilippo).
        Does not depend on curses; emits VT100 escapes directly.

Original C version:
Copyright (C) 2016 Salvatore Sanfilippo <antirez at gmail dot com>
Released under the BSD 2-clause license.

This Python port keeps the same overall structure and behavior as the
original: raw-mode terminal handling, a simple row-based buffer, C/C++
syntax highlighting, incremental search, and basic editing (insert,
delete, newline, save).
"""

import sys
import os
import re
import tty
import time
import errno
import signal
import termios
import fcntl
import struct

KILO_VERSION = "0.0.1"

# ------------------------- Syntax highlight types -------------------------
HL_NORMAL = 0
HL_NONPRINT = 1
HL_COMMENT = 2      # Single line comment.
HL_MLCOMMENT = 3    # Multi-line comment.
HL_KEYWORD1 = 4
HL_KEYWORD2 = 5
HL_STRING = 6
HL_NUMBER = 7
HL_MATCH = 8        # Search match.

HL_HIGHLIGHT_STRINGS = 1 << 0
HL_HIGHLIGHT_NUMBERS = 1 << 1


class EditorSyntax:
    def __init__(self, filematch, keywords, scs, mcs, mce, flags):
        self.filematch = filematch
        self.keywords = keywords
        self.singleline_comment_start = scs
        self.multiline_comment_start = mcs
        self.multiline_comment_end = mce
        self.flags = flags


# =========================== Syntax highlights DB ==========================
#
# To add a new syntax, define a list of filename match patterns and a list
# of keywords (trailing '|' on a keyword highlights it in a second color),
# then add an EditorSyntax entry to HLDB.

C_HL_extensions = [".c", ".h", ".cpp", ".hpp", ".cc"]
C_HL_keywords = [
    # C keywords
    "auto", "break", "case", "continue", "default", "do", "else", "enum",
    "extern", "for", "goto", "if", "register", "return", "sizeof", "static",
    "struct", "switch", "typedef", "union", "volatile", "while", "NULL",

    # C++ keywords
    "alignas", "alignof", "and", "and_eq", "asm", "bitand", "bitor", "class",
    "compl", "constexpr", "const_cast", "deltype", "delete", "dynamic_cast",
    "explicit", "export", "false", "friend", "inline", "mutable", "namespace",
    "new", "noexcept", "not", "not_eq", "nullptr", "operator", "or", "or_eq",
    "private", "protected", "public", "reinterpret_cast", "static_assert",
    "static_cast", "template", "this", "thread_local", "throw", "true", "try",
    "typeid", "typename", "virtual", "xor", "xor_eq",

    # C types (kw2 - second color)
    "int|", "long|", "double|", "float|", "char|", "unsigned|", "signed|",
    "void|", "short|", "auto|", "const|", "bool|",
]

HLDB = [
    EditorSyntax(
        C_HL_extensions,
        C_HL_keywords,
        "//", "/*", "*/",
        HL_HIGHLIGHT_STRINGS | HL_HIGHLIGHT_NUMBERS,
    )
]

# ================================ Key codes =================================

KEY_NULL = 0
CTRL_C = 3
CTRL_D = 4
CTRL_F = 6
CTRL_H = 8
TAB = 9
CTRL_L = 12
ENTER = 13
CTRL_Q = 17
CTRL_S = 19
CTRL_U = 21
ESC = 27
BACKSPACE = 127
# Soft codes, not actually reported by the terminal directly.
ARROW_LEFT = 1000
ARROW_RIGHT = 1001
ARROW_UP = 1002
ARROW_DOWN = 1003
DEL_KEY = 1004
HOME_KEY = 1005
END_KEY = 1006
PAGE_UP = 1007
PAGE_DOWN = 1008


class Erow:
    """A single line of the file being edited."""
    __slots__ = ("idx", "chars", "render", "hl", "hl_oc")

    def __init__(self, idx, chars):
        self.idx = idx
        self.chars = chars      # str: raw row content
        self.render = ""        # str: rendered content (tabs expanded)
        self.hl = bytearray()   # syntax highlight type per rendered char
        self.hl_oc = False      # row had an open comment at the end

    @property
    def size(self):
        return len(self.chars)

    @property
    def rsize(self):
        return len(self.render)


class EditorConfig:
    def __init__(self):
        self.cx = 0
        self.cy = 0
        self.rowoff = 0
        self.coloff = 0
        self.screenrows = 0
        self.screencols = 0
        self.rawmode = False
        self.rows = []          # list[Erow]
        self.dirty = 0
        self.filename = None
        self.statusmsg = ""
        self.statusmsg_time = 0
        self.syntax = None

    @property
    def numrows(self):
        return len(self.rows)


E = EditorConfig()

# ======================= Low level terminal handling ========================

orig_termios = None


def disable_raw_mode(fd):
    global orig_termios
    if E.rawmode and orig_termios is not None:
        termios.tcsetattr(fd, termios.TCSAFLUSH, orig_termios)
        E.rawmode = False


def editor_at_exit():
    disable_raw_mode(sys.stdin.fileno())


def enable_raw_mode(fd):
    global orig_termios
    if E.rawmode:
        return
    if not os.isatty(fd):
        raise OSError(errno.ENOTTY, "Not a tty")

    orig_termios = termios.tcgetattr(fd)
    raw = termios.tcgetattr(fd)

    # input modes: no break, no CR to NL, no parity check, no strip char,
    # no start/stop output control.
    raw[0] &= ~(termios.BRKINT | termios.ICRNL | termios.INPCK |
                termios.ISTRIP | termios.IXON)
    # output modes: disable post processing
    raw[1] &= ~(termios.OPOST)
    # control modes: set 8 bit chars
    raw[2] |= termios.CS8
    # local modes: echo off, canonical off, no extended functions,
    # no signal chars (^Z, ^C)
    raw[3] &= ~(termios.ECHO | termios.ICANON | termios.IEXTEN | termios.ISIG)
    # control chars: return condition on min bytes / timer
    cc = raw[6]
    cc[termios.VMIN] = 0
    cc[termios.VTIME] = 1  # 100ms timeout

    termios.tcsetattr(fd, termios.TCSAFLUSH, raw)
    E.rawmode = True


def editor_read_key(fd):
    """Read a key from the terminal in raw mode, handling escape sequences."""
    c = None
    while c is None:
        chunk = os.read(fd, 1)
        if not chunk:
            continue
        c = chunk[0]

    if c == ESC:
        seq = os.read(fd, 1)
        if not seq:
            return ESC
        seq2 = os.read(fd, 1)
        if not seq2:
            return ESC
        s0, s1 = seq[0], seq2[0]

        if chr(s0) == '[':
            if ord('0') <= s1 <= ord('9'):
                seq3 = os.read(fd, 1)
                if not seq3:
                    return ESC
                if chr(seq3[0]) == '~':
                    return {
                        ord('3'): DEL_KEY,
                        ord('5'): PAGE_UP,
                        ord('6'): PAGE_DOWN,
                    }.get(s1, ESC)
            else:
                return {
                    ord('A'): ARROW_UP,
                    ord('B'): ARROW_DOWN,
                    ord('C'): ARROW_RIGHT,
                    ord('D'): ARROW_LEFT,
                    ord('H'): HOME_KEY,
                    ord('F'): END_KEY,
                }.get(s1, ESC)
        elif chr(s0) == 'O':
            return {
                ord('H'): HOME_KEY,
                ord('F'): END_KEY,
            }.get(s1, ESC)
        return ESC

    return c


def get_cursor_position(ifd, ofd):
    """Query the cursor position via ESC[6n. Returns (rows, cols) or None."""
    os.write(ofd, b"\x1b[6n")
    buf = b""
    while len(buf) < 32:
        ch = os.read(ifd, 1)
        if not ch:
            break
        buf += ch
        if ch == b'R':
            break
    if not buf.startswith(b"\x1b[") or not buf.endswith(b"R"):
        return None
    m = re.match(rb"\x1b\[(\d+);(\d+)R", buf)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def get_window_size(ifd, ofd):
    """Return (rows, cols) of the terminal, or None on error."""
    try:
        buf = fcntl.ioctl(ofd, termios.TIOCGWINSZ, b'\0' * 8)
        rows, cols, _, _ = struct.unpack('HHHH', buf)
        if cols != 0:
            return rows, cols
    except OSError:
        pass

    # Fallback: query the terminal directly.
    orig = get_cursor_position(ifd, ofd)
    if orig is None:
        return None
    os.write(ofd, b"\x1b[999C\x1b[999B")
    pos = get_cursor_position(ifd, ofd)
    if pos is None:
        return None
    rows, cols = pos
    seq = "\x1b[%d;%dH" % orig
    try:
        os.write(ofd, seq.encode())
    except OSError:
        pass
    return rows, cols


# ====================== Syntax highlight color scheme  ======================

SEPARATORS = ",.()+-/*=~%[];"


def is_separator(c):
    return c == '\0' or c.isspace() or c in SEPARATORS


def editor_row_has_open_comment(row):
    """True if row ends inside an unterminated multi-line comment."""
    if row.hl and row.rsize and row.hl[row.rsize - 1] == HL_MLCOMMENT and (
        row.rsize < 2 or
        row.render[row.rsize - 2] != '*' or
        row.render[row.rsize - 1] != '/'
    ):
        return True
    return False


def editor_update_syntax(row):
    """Set row.hl[i] to the highlight type of each rendered character."""
    row.hl = bytearray([HL_NORMAL]) * row.rsize

    if E.syntax is None:
        return

    keywords = E.syntax.keywords
    scs = E.syntax.singleline_comment_start
    mcs = E.syntax.multiline_comment_start
    mce = E.syntax.multiline_comment_end

    render = row.render
    n = len(render)
    i = 0
    while i < n and render[i].isspace():
        i += 1

    prev_sep = True
    in_string = None   # None, or the quote character we're inside
    in_comment = False

    if row.idx > 0 and editor_row_has_open_comment(E.rows[row.idx - 1]):
        in_comment = True

    while i < n:
        c = render[i]

        # Single-line comments.
        if prev_sep and render[i:i + 2] == scs:
            for k in range(i, n):
                row.hl[k] = HL_COMMENT
            return

        # Multi-line comments.
        if in_comment:
            row.hl[i] = HL_MLCOMMENT
            if render[i:i + 2] == mce:
                if i + 1 < n:
                    row.hl[i + 1] = HL_MLCOMMENT
                i += 2
                in_comment = False
                prev_sep = True
                continue
            else:
                prev_sep = False
                i += 1
                continue
        elif render[i:i + 2] == mcs:
            row.hl[i] = HL_MLCOMMENT
            if i + 1 < n:
                row.hl[i + 1] = HL_MLCOMMENT
            i += 2
            in_comment = True
            prev_sep = False
            continue

        # Strings.
        if in_string:
            row.hl[i] = HL_STRING
            if c == '\\' and i + 1 < n:
                row.hl[i + 1] = HL_STRING
                i += 2
                prev_sep = False
                continue
            if c == in_string:
                in_string = None
            i += 1
            continue
        else:
            if c == '"' or c == "'":
                in_string = c
                row.hl[i] = HL_STRING
                i += 1
                prev_sep = False
                continue

        # Non-printable characters.
        if not c.isprintable():
            row.hl[i] = HL_NONPRINT
            i += 1
            prev_sep = False
            continue

        # Numbers.
        if (c.isdigit() and (prev_sep or row.hl[i - 1] == HL_NUMBER)) or \
           (c == '.' and i > 0 and row.hl[i - 1] == HL_NUMBER):
            row.hl[i] = HL_NUMBER
            i += 1
            prev_sep = False
            continue

        # Keywords.
        if prev_sep:
            matched = False
            for kw in keywords:
                kw2 = kw.endswith('|')
                word = kw[:-1] if kw2 else kw
                klen = len(word)
                if render[i:i + klen] == word and is_separator(
                        render[i + klen] if i + klen < n else '\0'):
                    hl_type = HL_KEYWORD2 if kw2 else HL_KEYWORD1
                    for k in range(i, i + klen):
                        row.hl[k] = hl_type
                    i += klen
                    matched = True
                    break
            if matched:
                prev_sep = False
                continue

        prev_sep = is_separator(c)
        i += 1

    oc = editor_row_has_open_comment(row)
    if row.hl_oc != oc and row.idx + 1 < E.numrows:
        editor_update_syntax(E.rows[row.idx + 1])
    row.hl_oc = oc


def editor_syntax_to_color(hl):
    return {
        HL_COMMENT: 36,
        HL_MLCOMMENT: 36,
        HL_KEYWORD1: 33,
        HL_KEYWORD2: 32,
        HL_STRING: 35,
        HL_NUMBER: 31,
        HL_MATCH: 34,
    }.get(hl, 37)


def editor_select_syntax_highlight(filename):
    for s in HLDB:
        for pattern in s.filematch:
            p = filename.find(pattern)
            if p != -1:
                if not pattern.startswith('.') or \
                        filename[p + len(pattern):] == '':
                    E.syntax = s
                    return


# ========================= Editor rows implementation =======================

def editor_update_row(row):
    """Recompute the rendered form (tabs expanded) and syntax of a row."""
    rendered = []
    for ch in row.chars:
        if ch == '\t':
            rendered.append(' ')
            while len(rendered) % 8 != 0:
                rendered.append(' ')
        else:
            rendered.append(ch)
    row.render = "".join(rendered)
    editor_update_syntax(row)


def editor_insert_row(at, s):
    """Insert a row with content 's' at position 'at'."""
    if at > E.numrows:
        return
    row = Erow(at, s)
    E.rows.insert(at, row)
    for j in range(at + 1, E.numrows):
        E.rows[j].idx = j
    editor_update_row(row)
    E.dirty += 1


def editor_free_row(row):
    pass  # Nothing to explicitly free in Python.


def editor_del_row(at):
    if at >= E.numrows:
        return
    del E.rows[at]
    for j in range(at, E.numrows):
        E.rows[j].idx = j
    E.dirty += 1


def editor_rows_to_string():
    return "\n".join(row.chars for row in E.rows) + "\n" if E.rows else ""


def editor_row_insert_char(row, at, c):
    if at > row.size:
        row.chars = row.chars + " " * (at - row.size) + c
    else:
        row.chars = row.chars[:at] + c + row.chars[at:]
    editor_update_row(row)
    E.dirty += 1


def editor_row_append_string(row, s):
    row.chars = row.chars + s
    editor_update_row(row)
    E.dirty += 1


def editor_row_del_char(row, at):
    if row.size <= at:
        return
    row.chars = row.chars[:at] + row.chars[at + 1:]
    editor_update_row(row)
    E.dirty += 1


def editor_insert_char(c):
    filerow = E.rowoff + E.cy
    filecol = E.coloff + E.cx

    if filerow >= E.numrows:
        while E.numrows <= filerow:
            editor_insert_row(E.numrows, "")
    row = E.rows[filerow]
    editor_row_insert_char(row, filecol, c)
    if E.cx == E.screencols - 1:
        E.coloff += 1
    else:
        E.cx += 1
    E.dirty += 1


def editor_insert_newline():
    filerow = E.rowoff + E.cy
    filecol = E.coloff + E.cx
    row = E.rows[filerow] if filerow < E.numrows else None

    if row is None:
        if filerow == E.numrows:
            editor_insert_row(filerow, "")
        else:
            return
    else:
        if filecol >= row.size:
            filecol = row.size
        if filecol == 0:
            editor_insert_row(filerow, "")
        else:
            editor_insert_row(filerow + 1, row.chars[filecol:])
            row = E.rows[filerow]
            row.chars = row.chars[:filecol]
            editor_update_row(row)

    if E.cy == E.screenrows - 1:
        E.rowoff += 1
    else:
        E.cy += 1
    E.cx = 0
    E.coloff = 0


def editor_del_char():
    filerow = E.rowoff + E.cy
    filecol = E.coloff + E.cx
    row = E.rows[filerow] if filerow < E.numrows else None

    if row is None or (filecol == 0 and filerow == 0):
        return
    if filecol == 0:
        filecol = E.rows[filerow - 1].size
        editor_row_append_string(E.rows[filerow - 1], row.chars)
        editor_del_row(filerow)
        row = None
        if E.cy == 0:
            E.rowoff -= 1
        else:
            E.cy -= 1
        E.cx = filecol
        if E.cx >= E.screencols:
            shift = (E.screencols - E.cx) + 1
            E.cx -= shift
            E.coloff += shift
    else:
        editor_row_del_char(row, filecol - 1)
        if E.cx == 0 and E.coloff:
            E.coloff -= 1
        else:
            E.cx -= 1
    if row is not None:
        editor_update_row(row)
    E.dirty += 1


def editor_open(filename):
    E.dirty = 0
    E.filename = filename

    if not os.path.exists(filename):
        return 0

    try:
        with open(filename, "r", newline='', errors="surrogateescape") as fp:
            for line in fp:
                if line.endswith('\n'):
                    line = line[:-1]
                if line.endswith('\r'):
                    line = line[:-1]
                editor_insert_row(E.numrows, line)
    except OSError as e:
        print(f"Opening file: {e}", file=sys.stderr)
        sys.exit(1)
    E.dirty = 0
    return 0


def editor_save():
    buf = editor_rows_to_string()
    try:
        with open(E.filename, "w", newline='', errors="surrogateescape") as fp:
            fp.write(buf)
        E.dirty = 0
        editor_set_status_message("%d bytes written on disk" %
                                   len(buf.encode(errors="surrogateescape")))
        return 0
    except OSError as e:
        editor_set_status_message("Can't save! I/O error: %s" % e.strerror)
        return 1


# ============================= Terminal update ==============================

def editor_refresh_screen():
    ab = []

    ab.append("\x1b[?25l")  # Hide cursor.
    ab.append("\x1b[H")     # Go home.

    for y in range(E.screenrows):
        filerow = E.rowoff + y

        if filerow >= E.numrows:
            if E.numrows == 0 and y == E.screenrows // 3:
                welcome = "Kilo editor -- version %s\x1b[0K\r\n" % KILO_VERSION
                padding = (E.screencols - len(welcome)) // 2
                if padding > 0:
                    ab.append("~")
                    padding -= 1
                ab.append(" " * max(padding, 0))
                ab.append(welcome)
            else:
                ab.append("~\x1b[0K\r\n")
            continue

        r = E.rows[filerow]
        length = r.rsize - E.coloff
        current_color = -1
        if length > 0:
            length = min(length, E.screencols)
            render = r.render[E.coloff:E.coloff + length]
            hl = r.hl[E.coloff:E.coloff + length]
            for j in range(length):
                ch = render[j]
                h = hl[j]
                if h == HL_NONPRINT:
                    ab.append("\x1b[7m")
                    code = ord(ch)
                    sym = chr(ord('@') + code) if code <= 26 else '?'
                    ab.append(sym)
                    ab.append("\x1b[0m")
                elif h == HL_NORMAL:
                    if current_color != -1:
                        ab.append("\x1b[39m")
                        current_color = -1
                    ab.append(ch)
                else:
                    color = editor_syntax_to_color(h)
                    if color != current_color:
                        current_color = color
                        ab.append("\x1b[%dm" % color)
                    ab.append(ch)
        ab.append("\x1b[39m")
        ab.append("\x1b[0K")
        ab.append("\r\n")

    # Status bar, first row.
    ab.append("\x1b[0K")
    ab.append("\x1b[7m")
    fname = (E.filename or "")[:20]
    status = "%s - %d lines %s" % (
        fname, E.numrows, "(modified)" if E.dirty else "")
    rstatus = "%d/%d" % (E.rowoff + E.cy + 1, E.numrows)
    status = status[:E.screencols]
    ab.append(status)
    slen = len(status)
    while slen < E.screencols:
        if E.screencols - slen == len(rstatus):
            ab.append(rstatus)
            break
        else:
            ab.append(" ")
            slen += 1
    ab.append("\x1b[0m\r\n")

    # Status message, second row.
    ab.append("\x1b[0K")
    if E.statusmsg and time.time() - E.statusmsg_time < 5:
        ab.append(E.statusmsg[:E.screencols])

    # Position the cursor, accounting for TAB expansion.
    filerow = E.rowoff + E.cy
    row = E.rows[filerow] if filerow < E.numrows else None
    cx = 1
    if row:
        for j in range(E.coloff, E.cx + E.coloff):
            if j < row.size and row.chars[j] == '\t':
                cx += 7 - (cx % 8)
            cx += 1
    ab.append("\x1b[%d;%dH" % (E.cy + 1, cx))
    ab.append("\x1b[?25h")  # Show cursor.

    os.write(sys.stdout.fileno(), "".join(ab).encode(errors="surrogateescape"))


def editor_set_status_message(fmt, *args):
    E.statusmsg = fmt % args if args else fmt
    E.statusmsg_time = time.time()


# =============================== Find mode ===================================

KILO_QUERY_LEN = 256


def editor_find(fd):
    query = ""
    last_match = -1     # Row of last match, -1 for none.
    find_next = 0        # 1 = next, -1 = prev.
    saved_hl_line = -1
    saved_hl = None

    def restore_hl():
        nonlocal saved_hl, saved_hl_line
        if saved_hl is not None:
            E.rows[saved_hl_line].hl[:] = saved_hl
            saved_hl = None

    saved_cx, saved_cy = E.cx, E.cy
    saved_coloff, saved_rowoff = E.coloff, E.rowoff

    while True:
        editor_set_status_message("Search: %s (Use ESC/Arrows/Enter)" % query)
        editor_refresh_screen()

        c = editor_read_key(fd)
        if c in (DEL_KEY, CTRL_H, BACKSPACE):
            if query:
                query = query[:-1]
            last_match = -1
        elif c in (ESC, ENTER):
            if c == ESC:
                E.cx, E.cy = saved_cx, saved_cy
                E.coloff, E.rowoff = saved_coloff, saved_rowoff
            restore_hl()
            editor_set_status_message("")
            return
        elif c in (ARROW_RIGHT, ARROW_DOWN):
            find_next = 1
        elif c in (ARROW_LEFT, ARROW_UP):
            find_next = -1
        elif isinstance(c, int) and 32 <= c < 127:
            if len(query) < KILO_QUERY_LEN:
                query += chr(c)
                last_match = -1

        if last_match == -1:
            find_next = 1

        if find_next and query:
            match = None
            match_offset = -1
            current = last_match
            for _ in range(E.numrows):
                current += find_next
                if current == -1:
                    current = E.numrows - 1
                elif current == E.numrows:
                    current = 0
                idx = E.rows[current].render.find(query)
                if idx != -1:
                    match = E.rows[current]
                    match_offset = idx
                    break
            find_next = 0

            restore_hl()

            if match is not None:
                last_match = current
                if match.hl:
                    saved_hl_line = current
                    saved_hl = bytearray(match.hl)
                    for k in range(match_offset, match_offset + len(query)):
                        if k < len(match.hl):
                            match.hl[k] = HL_MATCH
                E.cy = 0
                E.cx = match_offset
                E.rowoff = current
                E.coloff = 0
                if E.cx > E.screencols:
                    diff = E.cx - E.screencols
                    E.cx -= diff
                    E.coloff += diff


# ========================= Editor events handling  ==========================

def editor_move_cursor(key):
    filerow = E.rowoff + E.cy
    filecol = E.coloff + E.cx
    row = E.rows[filerow] if filerow < E.numrows else None

    if key == ARROW_LEFT:
        if E.cx == 0:
            if E.coloff:
                E.coloff -= 1
            else:
                if filerow > 0:
                    E.cy -= 1
                    E.cx = E.rows[filerow - 1].size
                    if E.cx > E.screencols - 1:
                        E.coloff = E.cx - E.screencols + 1
                        E.cx = E.screencols - 1
        else:
            E.cx -= 1
    elif key == ARROW_RIGHT:
        if row and filecol < row.size:
            if E.cx == E.screencols - 1:
                E.coloff += 1
            else:
                E.cx += 1
        elif row and filecol == row.size:
            E.cx = 0
            E.coloff = 0
            if E.cy == E.screenrows - 1:
                E.rowoff += 1
            else:
                E.cy += 1
    elif key == ARROW_UP:
        if E.cy == 0:
            if E.rowoff:
                E.rowoff -= 1
        else:
            E.cy -= 1
    elif key == ARROW_DOWN:
        if filerow < E.numrows:
            if E.cy == E.screenrows - 1:
                E.rowoff += 1
            else:
                E.cy += 1

    filerow = E.rowoff + E.cy
    filecol = E.coloff + E.cx
    row = E.rows[filerow] if filerow < E.numrows else None
    rowlen = row.size if row else 0
    if filecol > rowlen:
        E.cx -= filecol - rowlen
        if E.cx < 0:
            E.coloff += E.cx
            E.cx = 0


KILO_QUIT_TIMES = 3
_quit_times = KILO_QUIT_TIMES


def editor_process_keypress(fd):
    global _quit_times

    c = editor_read_key(fd)

    if c == ENTER:
        editor_insert_newline()
    elif c == CTRL_C:
        pass  # Ignored, as in the original.
    elif c == CTRL_Q:
        if E.dirty and _quit_times:
            editor_set_status_message(
                "WARNING!!! File has unsaved changes. "
                "Press Ctrl-Q %d more times to quit." % _quit_times)
            _quit_times -= 1
            return
        disable_raw_mode(fd)
        sys.exit(0)
    elif c == CTRL_S:
        editor_save()
    elif c == CTRL_F:
        editor_find(fd)
    elif c in (BACKSPACE, CTRL_H, DEL_KEY):
        editor_del_char()
    elif c in (PAGE_UP, PAGE_DOWN):
        if c == PAGE_UP and E.cy != 0:
            E.cy = 0
        elif c == PAGE_DOWN and E.cy != E.screenrows - 1:
            E.cy = E.screenrows - 1
        times = E.screenrows
        while times:
            editor_move_cursor(ARROW_UP if c == PAGE_UP else ARROW_DOWN)
            times -= 1
    elif c in (ARROW_UP, ARROW_DOWN, ARROW_LEFT, ARROW_RIGHT):
        editor_move_cursor(c)
    elif c == CTRL_L:
        pass  # Just refresh the screen (happens every loop anyway).
    elif c == ESC:
        pass
    else:
        if isinstance(c, int) and 32 <= c < 127 or c == TAB:
            editor_insert_char(chr(c))

    _quit_times = KILO_QUIT_TIMES


def editor_file_was_modified():
    return E.dirty


def update_window_size():
    size = get_window_size(sys.stdin.fileno(), sys.stdout.fileno())
    if size is None:
        print("Unable to query the screen for size (columns / rows)",
              file=sys.stderr)
        sys.exit(1)
    rows, cols = size
    E.screenrows = rows - 2  # Room for the status bar.
    E.screencols = cols


def handle_sigwinch(signum, frame):
    update_window_size()
    if E.cy > E.screenrows:
        E.cy = E.screenrows - 1
    if E.cx > E.screencols:
        E.cx = E.screencols - 1
    editor_refresh_screen()


def init_editor():
    E.cx = 0
    E.cy = 0
    E.rowoff = 0
    E.coloff = 0
    E.rows = []
    E.dirty = 0
    E.filename = None
    E.syntax = None
    update_window_size()
    signal.signal(signal.SIGWINCH, handle_sigwinch)


def main():
    if len(sys.argv) != 2:
        print("Usage: kilo <filename>", file=sys.stderr)
        sys.exit(1)

    init_editor()
    editor_select_syntax_highlight(sys.argv[1])
    editor_open(sys.argv[1])
    enable_raw_mode(sys.stdin.fileno())
    editor_set_status_message(
        "HELP: Ctrl-S = save | Ctrl-Q = quit | Ctrl-F = find")
    try:
        while True:
            editor_refresh_screen()
            editor_process_keypress(sys.stdin.fileno())
    finally:
        disable_raw_mode(sys.stdin.fileno())


if __name__ == "__main__":
    main()