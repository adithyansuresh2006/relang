#!/usr/bin/env python3
"""
tclock - Terminal Clock in Python

Ported from Go reference implementation in tclock/source.
Supports digital 7-segment bignum clock, analog clock, countdown mode,
date/time targets (-until), word tailing, bouncing, breathing effects, and ANSI styling.
"""

import sys
import os
import time
import datetime
import argparse
import math
import select
import re
import signal
from typing import List, Tuple, Optional, Dict

# ANSI Escape Sequences
CLEAR_SCREEN = "\033[2J\033[H"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"
RESET_STYLE = "\033[0m"
INVERSE_STYLE = "\033[7m"

# Named Colors (ANSI 16 / Truecolor RGB mapping)
COLOR_MAP = {
    "black": "\033[30m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "orange": "\033[38;2;255;165;0m",
    "blue": "\033[34m",
    "purple": "\033[35m",
    "cyan": "\033[36m",
    "gray": "\033[90m",
    "darkgray": "\033[90m",
    "brightred": "\033[91m",
    "brightgreen": "\033[92m",
    "brightyellow": "\033[93m",
    "brightblue": "\033[94m",
    "brightpurple": "\033[95m",
    "brightcyan": "\033[96m",
    "white": "\033[97m",
    "none": "",
}

RGB_COLOR_MAP = {
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "yellow": (255, 255, 0),
    "orange": (255, 165, 0),
    "blue": (0, 0, 255),
    "purple": (128, 0, 128),
    "cyan": (0, 255, 255),
    "white": (255, 255, 255),
    "gray": (128, 128, 128),
    "black": (0, 0, 0),
}

# -----------------------------------------------------------------------------
# 7-Segment Bignum Character Definition
# -----------------------------------------------------------------------------

NUMBERS_TEMPLATE = """
 ━━ 
┃  ┃

┃  ┃
 ━━ 

    
   ┃

   ┃


 ━━ 
   ┃
 ━━ 
┃   
 ━━ 

 ━━ 
   ┃
 ━━ 
   ┃
 ━━ 

    
┃  ┃
 ━━ 
   ┃


 ━━ 
┃   
 ━━ 
   ┃
 ━━ 

 ━━ 
┃   
 ━━ 
┃  ┃
 ━━ 

 ━━ 
   ┃

   ┃


 ━━ 
┃  ┃
 ━━ 
┃  ┃
 ━━ 

 ━━ 
┃  ┃
 ━━ 
   ┃
 ━━ 

    

 :: 

    

    

 .. 

    
"""

BIGNUM_HEIGHT = 5
BIGNUM_WIDTH = 4

def _init_bignum_lines() -> List[str]:
    raw_lines = NUMBERS_TEMPLATE.split("\n")[1:]
    lines = []
    for i, line in enumerate(raw_lines):
        if i >= len(raw_lines) - 1:
            break
        extra = 1 if i < 10 * (BIGNUM_HEIGHT + 1) else -1
        target_len = BIGNUM_WIDTH + extra
        # Pad line to target length
        pad_len = target_len - len(line)
        if pad_len > 0:
            line += " " * pad_len
        lines.append(line)
    return lines

NUMBER_LINES = _init_bignum_lines()

def time_string(num_str: str, blink: bool = False) -> str:
    """Format string of digits/colons into 5-line 7-segment bignum representation."""
    display_lines = [""] * BIGNUM_HEIGHT
    for c in num_str:
        if '0' <= c <= '9':
            digit = ord(c) - ord('0')
        else:
            digit = 11 if blink else 10
        start = digit * (BIGNUM_HEIGHT + 1)
        for i in range(BIGNUM_HEIGHT):
            if start + i < len(NUMBER_LINES):
                display_lines[i] += NUMBER_LINES[start + i]
    return "\n".join(display_lines)

# -----------------------------------------------------------------------------
# Duration & Date Parsing
# -----------------------------------------------------------------------------

def parse_duration(s: str) -> float:
    """Parse duration string like 5m, 30s, 2h, 3w2d10h into total seconds."""
    pattern = re.compile(r'(\d+)\s*([a-zA-Z]+)')
    matches = pattern.findall(s)
    if not matches:
        raise ValueError(f"Invalid duration format: {s}")
    total_seconds = 0.0
    unit_map = {
        's': 1, 'sec': 1, 'second': 1, 'seconds': 1,
        'm': 60, 'min': 60, 'minute': 60, 'minutes': 60,
        'h': 3600, 'hr': 3600, 'hour': 3600, 'hours': 3600,
        'd': 86400, 'day': 86400, 'days': 86400,
        'w': 604800, 'week': 604800, 'weeks': 604800,
    }
    for val_str, unit in matches:
        val = int(val_str)
        u_lower = unit.lower()
        if u_lower not in unit_map:
            raise ValueError(f"Unknown duration unit: {unit}")
        total_seconds += val * unit_map[u_lower]
    return total_seconds

def parse_date_time(now: datetime.datetime, s: str) -> datetime.datetime:
    """Parse -until date/time string."""
    s = s.strip()
    # Try YYYY-MM-DD HH:MM:SS
    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"]:
        try:
            dt = datetime.datetime.strptime(s, fmt)
            if fmt == "%Y-%m-%d":
                dt = dt.replace(hour=0, minute=0, second=0)
            return dt
        except ValueError:
            pass

    # Try 12-hour kitchen style (e.g. 3:05 pm, 3:05pm, 11:30 am)
    for fmt in ["%I:%M:%S %p", "%I:%M %p", "%I:%M%p", "%I:%M:%S%p"]:
        try:
            t = datetime.datetime.strptime(s, fmt).time()
            target = datetime.datetime.combine(now.date(), t)
            if target <= now:
                target += datetime.timedelta(days=1)
            return target
        except ValueError:
            pass

    # Try 24h time (e.g. 15:05:00, 15:05)
    for fmt in ["%H:%M:%S", "%H:%M"]:
        try:
            t = datetime.datetime.strptime(s, fmt).time()
            target = datetime.datetime.combine(now.date(), t)
            if target <= now:
                target += datetime.timedelta(days=1)
            return target
        except ValueError:
            pass

    raise ValueError(f"Could not parse target date/time: '{s}'")

def format_duration(seconds: float, show_seconds: bool = True) -> str:
    """Format remaining seconds as DD:HH:MM:SS or HH:MM:SS or MM:SS."""
    sec = max(0, int(round(seconds)))
    mins = sec // 60
    secs = sec % 60
    hrs = mins // 60
    mins = mins % 60
    days = hrs // 24
    hrs = hrs % 24

    parts = []
    if days > 0:
        parts.append(f"{days:02d}")
        parts.append(f"{hrs:02d}")
        parts.append(f"{mins:02d}")
    elif hrs > 0:
        parts.append(f"{hrs:02d}")
        parts.append(f"{mins:02d}")
    else:
        parts.append(f"{mins:02d}")

    res = ":".join(parts)
    if show_seconds:
        res += f":{secs:02d}"
    return res

# -----------------------------------------------------------------------------
# Color & ANSI Utilities
# -----------------------------------------------------------------------------

def parse_color_ansi(c_str: str) -> str:
    """Convert color string/name/hex to ANSI foreground escape code."""
    if not c_str or c_str == "none":
        return ""
    c_str = c_str.lower()
    if c_str in COLOR_MAP:
        return COLOR_MAP[c_str]
    if c_str.startswith("#"):
        c_str = c_str[1:]
    if len(c_str) == 6:
        try:
            r = int(c_str[0:2], 16)
            g = int(c_str[2:4], 16)
            b = int(c_str[4:6], 16)
            return f"\033[38;2;{r};{g};{b}m"
        except ValueError:
            pass
    return "\033[31m"  # Default red

def parse_rgb(c_str: str) -> Tuple[int, int, int]:
    """Parse color string into RGB tuple."""
    if not c_str:
        return (224, 192, 32)
    c_str = c_str.lower()
    if c_str in RGB_COLOR_MAP:
        return RGB_COLOR_MAP[c_str]
    if c_str.startswith("#"):
        c_str = c_str[1:]
    if len(c_str) == 6:
        try:
            r = int(c_str[0:2], 16)
            g = int(c_str[2:4], 16)
            b = int(c_str[4:6], 16)
            return (r, g, b)
        except ValueError:
            pass
    return (255, 0, 0)

def move_cursor(x: int, y: int) -> str:
    """ANSI sequence to move cursor to (x, y) 1-indexed."""
    return f"\033[{y};{x}H"

# -----------------------------------------------------------------------------
# Terminal Size Helper
# -----------------------------------------------------------------------------

def get_terminal_size() -> Tuple[int, int]:
    """Return (width, height) of current terminal."""
    try:
        size = os.get_terminal_size()
        return size.columns, size.lines
    except OSError:
        return 80, 24

# -----------------------------------------------------------------------------
# Analog Clock Renderer
# -----------------------------------------------------------------------------

def render_analog_clock(width: int, height: int, now: datetime.datetime, seconds: bool, continuous: bool) -> List[str]:
    """Render ASCII analog clock face with hour, minute, second hands."""
    lines = [[" "] * width for _ in range(height)]
    cx = width // 2
    cy = height // 2
    radius = min(width // 2, height) - 2
    if radius < 3:
        radius = 3

    # Draw clock numbers 1..12 or dots
    for n in range(1, 61):
        angle = 2.0 * math.pi * (60 - n) / 60.0
        rx = -math.sin(angle) * (radius * 1.8)
        ry = -math.cos(angle) * radius
        px = int(round(cx + rx / 2))
        py = int(round(cy + ry / 2))
        if 0 <= py < height and 0 <= px < width:
            if n % 5 == 0:
                num = str(n // 5)
                for idx, ch in enumerate(num):
                    if 0 <= px + idx < width:
                        lines[py][px + idx] = ch
            elif seconds:
                lines[py][px] = "•"

    sec = now.second + (now.microsecond / 1e6 if continuous else 0)
    minute = now.minute + sec / 60.0
    hour = (now.hour % 12) + minute / 60.0

    # Hand lengths
    s_len = radius * 0.9
    m_len = radius * 0.8
    h_len = radius * 0.5

    def draw_line_coords(angle: float, length: float, char: str):
        steps = int(length * 2)
        for i in range(1, steps + 1):
            t = (i / steps) * length
            rx = -math.sin(angle) * (t * 1.8)
            ry = -math.cos(angle) * t
            px = int(round(cx + rx / 2))
            py = int(round(cy + ry / 2))
            if 0 <= py < height and 0 <= px < width:
                lines[py][px] = char

    # Hour hand
    h_angle = 2.0 * math.pi * (12.0 - hour) / 12.0
    draw_line_coords(h_angle, h_len, "H")

    # Minute hand
    m_angle = 2.0 * math.pi * (60.0 - minute) / 60.0
    draw_line_coords(m_angle, m_len, "M")

    # Second hand
    if seconds:
        s_angle = 2.0 * math.pi * (60.0 - sec) / 60.0
        draw_line_coords(s_angle, s_len, "s")

    return ["".join(row) for row in lines]

# -----------------------------------------------------------------------------
# Main Clock Logic
# -----------------------------------------------------------------------------

def run_tclock(args):
    """Main terminal loop for tclock."""
    # Check one-off digit display mode: e.g. `tclock 12345`
    if len(args.digits) == 1:
        num_str = args.digits[0]
        if num_str != "-":
            if num_str.isdigit() or ":" in num_str:
                print(time_string(num_str, False))
                return 0

    # Parse countdown / until settings
    countdown_mode = False
    end_time = None
    if args.countdown:
        try:
            dur_sec = parse_duration(args.countdown)
            end_time = datetime.datetime.now() + datetime.timedelta(seconds=dur_sec)
            countdown_mode = True
        except ValueError as e:
            print(f"Error parsing countdown: {e}", file=sys.stderr)
            return 1
    elif args.until:
        try:
            now = datetime.datetime.now()
            end_time = parse_date_time(now, args.until)
            countdown_mode = True
        except ValueError as e:
            print(f"Error parsing until: {e}", file=sys.stderr)
            return 1

    color_ansi = parse_color_ansi(args.color)
    box_color_ansi = parse_color_ansi(args.color_box) if args.color_box else color_ansi

    # Setup terminal for raw mode / non-blocking key reads
    try:
        sys.stdout.write(HIDE_CURSOR + CLEAR_SCREEN)
        sys.stdout.flush()
    except Exception:
        pass

    bounce_speed = args.bounce
    bounce_counter = 0
    analog_mode = args.analog or args.aa
    continuous = args.c

    last_blink_sec = -1
    blink_state = False

    try:
        import tty, termios
        fd = sys.stdin.fileno()
        is_tty = os.isatty(fd)
        if is_tty:
            old_settings = termios.tcgetattr(fd)
            tty.setcbreak(fd)
    except Exception:
        is_tty = False
        old_settings = None

    try:
        while True:
            # Check non-blocking keyboard input
            if is_tty:
                rlist, _, _ = select.select([sys.stdin], [], [], 0.05)
                if rlist:
                    ch = sys.stdin.read(1)
                    if ch in ['q', 'Q', '\x03']:
                        if countdown_mode:
                            now_str = datetime.datetime.now().strftime("%H:%M:%S")
                            sys.stdout.write(f"\r\nCountdown aborted at {now_str}\r\n")
                            sys.stdout.flush()
                            return 1
                        break
                    elif ch in ['a', 'A']:
                        analog_mode = not analog_mode
                    elif ch in ['c', 'C']:
                        continuous = not continuous
            else:
                time.sleep(0.05)

            term_w, term_h = get_terminal_size()
            now = datetime.datetime.now()

            # Determine string to display
            if countdown_mode:
                rem_sec = (end_time - now).total_seconds()
                if rem_sec <= 0:
                    now_str = now.strftime("%H:%M:%S")
                    sys.stdout.write(f"\r\n\aTime's up reached at {now_str}\r\n")
                    sys.stdout.flush()
                    return 0
                num_str = format_duration(rem_sec, not args.no_seconds)
            else:
                time_fmt = "%H:%M" if args.f24 else "%I:%M"
                if not args.no_seconds:
                    time_fmt += ":%S"
                num_str = now.strftime(time_fmt).lstrip("0") if not args.f24 else now.strftime(time_fmt)

            # Blink colon state
            if not args.no_blink:
                if now.second != last_blink_sec:
                    last_blink_sec = now.second
                    blink_state = not blink_state
            else:
                blink_state = False

            sys.stdout.write(CLEAR_SCREEN)

            if analog_mode:
                analog_lines = render_analog_clock(term_w, term_h, now, not args.no_seconds, continuous)
                for y, row in enumerate(analog_lines):
                    sys.stdout.write(move_cursor(1, y + 1) + color_ansi + row + RESET_STYLE)
            else:
                # Render 7-segment digital clock
                bignum_str = time_string(num_str, blink_state)
                lines = bignum_str.split("\n")
                clock_w = max(len(l) for l in lines)
                clock_h = len(lines)

                box_pad = 2 if args.box or args.color_box else 0
                total_w = clock_w + box_pad
                total_h = clock_h + box_pad

                # Calculate position (center or bounce)
                if bounce_speed > 0:
                    bounce_counter += 1
                    max_x = max(1, term_w - total_w)
                    max_y = max(1, term_h - total_h)
                    b_step = bounce_counter // bounce_speed
                    start_x = 1 + (b_step % max_x)
                    start_y = 1 + (b_step % max_y)
                else:
                    start_x = max(1, (term_w - total_w) // 2 + 1)
                    start_y = max(1, (term_h - total_h) // 2 + 1)

                # Draw outer box outline if requested
                if args.box or args.color_box:
                    box_top = "╭" + "─" * (clock_w) + "╮"
                    box_bot = "╰" + "─" * (clock_w) + "╯"
                    sys.stdout.write(move_cursor(start_x, start_y) + box_color_ansi + box_top + RESET_STYLE)
                    for i in range(clock_h):
                        sys.stdout.write(move_cursor(start_x, start_y + 1 + i) + box_color_ansi + "│" + RESET_STYLE)
                        sys.stdout.write(move_cursor(start_x + clock_w + 1, start_y + 1 + i) + box_color_ansi + "│" + RESET_STYLE)
                    sys.stdout.write(move_cursor(start_x, start_y + clock_h + 1) + box_color_ansi + box_bot + RESET_STYLE)
                    digit_start_x = start_x + 1
                    digit_start_y = start_y + 1
                else:
                    digit_start_x = start_x
                    digit_start_y = start_y

                # Draw bignum lines
                style_prefix = color_ansi
                if args.inverse:
                    style_prefix += INVERSE_STYLE
                for i, line in enumerate(lines):
                    sys.stdout.write(move_cursor(digit_start_x, digit_start_y + i) + style_prefix + line + RESET_STYLE)

                # Draw extra text below clock if specified
                if args.text and args.text != "none":
                    text_x = max(1, (term_w - len(args.text)) // 2 + 1)
                    text_y = min(term_h, digit_start_y + clock_h + 1)
                    sys.stdout.write(move_cursor(text_x, text_y) + args.text + RESET_STYLE)

            sys.stdout.flush()
            time.sleep(0.05 if continuous else 0.2)

    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write(SHOW_CURSOR + RESET_STYLE + "\n")
        sys.stdout.flush()
        if is_tty and old_settings:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            except Exception:
                pass
    return 0

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

    parser = argparse.ArgumentParser(description="Terminal clock using bignum digits / analog mode")
    parser.add_argument('-24', action='store_true', dest='f24', help="Use 24-hour time format")
    parser.add_argument('-analog', action='store_true', help="Analog clock with hours, minutes and seconds hands")
    parser.add_argument('-aa', action='store_true', help="Use antialiased image based analog clock")
    parser.add_argument('-c', action='store_true', help="Analog clock updates continuously instead of seconds ticks")
    parser.add_argument('-no-seconds', action='store_true', help="Don't show seconds")
    parser.add_argument('-no-blink', action='store_true', help="Don't blink the colon")
    parser.add_argument('-box', action='store_true', help="Draw a simple rounded corner outline around the time")
    parser.add_argument('-color', default="red", help="Color to use")
    parser.add_argument('-color-disc', default="", help="Color disc around time")
    parser.add_argument('-color-box', default="", help="Color box around time")
    parser.add_argument('-breath', action='store_true', help="Pulse the color")
    parser.add_argument('-bounce', type=int, default=0, help="Bounce speed")
    parser.add_argument('-inverse', action='store_true', help="Inverse foreground and background")
    parser.add_argument('-countdown', help="Countdown duration (e.g. 5m, 3w2d10h)")
    parser.add_argument('-until', help="Countdown until date/time")
    parser.add_argument('-text', default="", help="Text to display below clock")
    parser.add_argument('-tail', help="Tail given file while showing clock")
    parser.add_argument('digits', nargs='*', help="One-off digits to display")

    args = parser.parse_args()
    sys.exit(run_tclock(args))

if __name__ == '__main__':
    main()
