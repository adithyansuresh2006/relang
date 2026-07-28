#!/usr/bin/env python3
"""
tclock - Terminal Clock in Python

Direct, faithful port of the Go reference implementation in tclock/source.
Implements bignum 7-segment display, color disc background, analog clock,
countdown, date/time parsing, bouncing, breathing effect, and terminal UI.
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

# UTF-8 stdout reconfiguration for cross-platform unicode rendering
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# -----------------------------------------------------------------------------
# 1. Bignum 7-Segment Numbers Definition (Exact port of bignum.go)
# -----------------------------------------------------------------------------

NUMBERS_GO_TEMPLATE = """
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

def _init_number_lines() -> List[str]:
    raw_lines = NUMBERS_GO_TEMPLATE.split("\n")[1:]
    number_lines = []
    for i, line in enumerate(raw_lines):
        if i >= 12 * (BIGNUM_HEIGHT + 1):
            break
        extra = 1 if i < 10 * (BIGNUM_HEIGHT + 1) else -1
        target_width = BIGNUM_WIDTH + extra
        padded = line + " " * max(0, target_width - len(line))
        number_lines.append(padded)
    return number_lines

NUMBER_LINES = _init_number_lines()

def time_string(num_str: str, blink: bool = False) -> str:
    """Generate 5-line string representation for given number/time string."""
    lines = [""] * BIGNUM_HEIGHT
    for c in num_str:
        if '0' <= c <= '9':
            digit = ord(c) - ord('0')
        else:
            digit = 11 if blink else 10
        start = digit * (BIGNUM_HEIGHT + 1)
        for i in range(BIGNUM_HEIGHT):
            if start + i < len(NUMBER_LINES):
                lines[i] += NUMBER_LINES[start + i]
    return "\n".join(lines)


# -----------------------------------------------------------------------------
# 2. Duration & Date Parsing (Port of fortio.org/duration)
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
    """Parse target date/time string for -until."""
    s = s.strip()
    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"]:
        try:
            dt = datetime.datetime.strptime(s, fmt)
            if fmt == "%Y-%m-%d":
                dt = dt.replace(hour=0, minute=0, second=0)
            return dt
        except ValueError:
            pass

    for fmt in ["%I:%M:%S %p", "%I:%M %p", "%I:%M%p", "%I:%M:%S%p"]:
        try:
            t = datetime.datetime.strptime(s, fmt).time()
            target = datetime.datetime.combine(now.date(), t)
            if target <= now:
                target += datetime.timedelta(days=1)
            return target
        except ValueError:
            pass

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
    sec = max(0, int(round(seconds)))
    mins = sec // 60
    secs = sec % 60
    hrs = mins // 60
    mins = mins % 60
    days = hrs // 24
    hrs = hrs % 24

    if days > 0:
        res = f"{days:02d}:{hrs:02d}:{mins:02d}"
    elif hrs > 0:
        res = f"{hrs:02d}:{mins:02d}"
    else:
        res = f"{mins:02d}"

    if show_seconds:
        res += f":{secs:02d}"
    return res


# -----------------------------------------------------------------------------
# 3. Colors & ANSI Encoding
# -----------------------------------------------------------------------------

COLOR_NAME_TO_RGB = {
    "black": (0, 0, 0),
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "yellow": (255, 255, 0),
    "orange": (255, 165, 0),
    "blue": (0, 0, 255),
    "purple": (128, 0, 128),
    "cyan": (0, 255, 255),
    "gray": (128, 128, 128),
    "darkgray": (64, 64, 64),
    "brightred": (255, 85, 85),
    "brightgreen": (85, 255, 85),
    "brightyellow": (255, 255, 85),
    "brightblue": (85, 85, 255),
    "brightpurple": (255, 85, 255),
    "brightcyan": (85, 255, 255),
    "white": (255, 255, 255),
}

def parse_color_rgb(c_str: str) -> Optional[Tuple[int, int, int]]:
    if not c_str or c_str.lower() in ["none", ""]:
        return None
    c_lower = c_str.lower()
    if c_lower in COLOR_NAME_TO_RGB:
        return COLOR_NAME_TO_RGB[c_lower]
    if c_lower.startswith("#"):
        c_lower = c_lower[1:]
    if len(c_lower) == 6:
        try:
            r = int(c_lower[0:2], 16)
            g = int(c_lower[2:4], 16)
            b = int(c_lower[4:6], 16)
            return (r, g, b)
        except ValueError:
            pass
    return (255, 0, 0)

def fg_ansi(rgb: Optional[Tuple[int, int, int]]) -> str:
    if rgb is None:
        return ""
    return f"\033[38;2;{rgb[0]};{rgb[1]};{rgb[2]}m"

def bg_ansi(rgb: Optional[Tuple[int, int, int]]) -> str:
    if rgb is None:
        return ""
    return f"\033[48;2;{rgb[0]};{rgb[1]};{rgb[2]}m"

RESET_ANSI = "\033[0m"


# -----------------------------------------------------------------------------
# 4. Terminal Helpers
# -----------------------------------------------------------------------------

def get_terminal_size() -> Tuple[int, int]:
    try:
        size = os.get_terminal_size()
        return size.columns, size.lines
    except OSError:
        return 80, 24

def bounce(frame: int, maximum: int) -> int:
    if maximum <= 0:
        return 0
    m = frame % (2 * maximum)
    if m < maximum:
        return m
    return 2 * maximum - 1 - m


# -----------------------------------------------------------------------------
# 5. Analog Clock Hand Drawing
# -----------------------------------------------------------------------------

def render_analog_clock(width: int, height: int, now: datetime.datetime, seconds: bool, continuous: bool) -> List[str]:
    lines = [[" "] * width for _ in range(height)]
    cx = width // 2
    cy = height // 2
    radius = min(width // 2, height) - 2
    if radius < 3:
        radius = 3

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

    s_len = radius * 0.9
    m_len = radius * 0.8
    h_len = radius * 0.5

    def draw_line(angle: float, length: float, char: str):
        steps = int(length * 2)
        for i in range(1, steps + 1):
            t = (i / steps) * length
            rx = -math.sin(angle) * (t * 1.8)
            ry = -math.cos(angle) * t
            px = int(round(cx + rx / 2))
            py = int(round(cy + ry / 2))
            if 0 <= py < height and 0 <= px < width:
                lines[py][px] = char

    h_angle = 2.0 * math.pi * (12.0 - hour) / 12.0
    draw_line(h_angle, h_len, "H")

    m_angle = 2.0 * math.pi * (60.0 - minute) / 60.0
    draw_line(m_angle, m_len, "M")

    if seconds:
        s_angle = 2.0 * math.pi * (60.0 - sec) / 60.0
        draw_line(s_angle, s_len, "s")

    return ["".join(row) for row in lines]


# -----------------------------------------------------------------------------
# 6. Main Clock Loop
# -----------------------------------------------------------------------------

def run_tclock(args):
    # Check one-off digit display: e.g. `tclock 12345`
    if len(args.digits) == 1 and args.digits[0] != "-":
        num_str = args.digits[0]
        if num_str.isdigit() or ":" in num_str:
            print(time_string(num_str, False))
            return 0

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

    fg_rgb = parse_color_rgb(args.color)
    box_fg_rgb = parse_color_rgb(args.color_box) if args.color_box else fg_rgb

    # Default color disc is "E0C020" (yellow/gold) unless explicitly set to "" or "none"
    if args.color_disc == "":
        disc_rgb = None
    else:
        disc_rgb = parse_color_rgb(args.color_disc)

    bounce_speed = args.bounce
    analog_mode = args.analog or args.aa
    continuous = args.c
    radius_mult = args.radius

    frame_counter = 0
    last_blink_sec = -1
    blink_state = False

    try:
        sys.stdout.write("\033[?25l\033[2J\033[H")
        sys.stdout.flush()
    except Exception:
        pass

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

            frame_counter += 1
            term_w, term_h = get_terminal_size()
            now = datetime.datetime.now()

            # Determine digits/time string
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

            # Blink colon logic
            if not args.no_blink:
                if now.second != last_blink_sec:
                    last_blink_sec = now.second
                    blink_state = not blink_state
            else:
                blink_state = False

            # Clear screen buffer
            sys.stdout.write("\033[2J\033[H")

            if analog_mode:
                analog_lines = render_analog_clock(term_w, term_h, now, not args.no_seconds, continuous)
                for y, row in enumerate(analog_lines):
                    sys.stdout.write(f"\033[{y+1};1H" + fg_ansi(fg_rgb) + row + RESET_ANSI)
            else:
                # Render digital bignum clock
                bignum_str = time_string(num_str, blink_state)
                lines = bignum_str.split("\n")
                clock_w = max(len(l) for l in lines)
                clock_h = len(lines)

                box_pad = 2 if (args.box or args.color_box) else 0
                total_w = clock_w + box_pad
                total_h = clock_h + box_pad

                # Position calculation (center or bounce)
                if bounce_speed > 0:
                    max_x = max(1, term_w - total_w)
                    max_y = max(1, term_h - total_h)
                    b_step = frame_counter // bounce_speed
                    start_x = 1 + bounce(b_step, max_x)
                    start_y = 1 + bounce(b_step, max_y)
                else:
                    start_x = max(1, (term_w - total_w) // 2 + 1)
                    start_y = max(1, (term_h - total_h) // 2 + 1)

                cx = start_x + total_w // 2 - 1
                cy = start_y + total_h // 2 - 1

                # Calculate disc radius
                mult = radius_mult
                if args.breath:
                    mult *= (1 + bounce(frame_counter // 7, 10) / 15.0)
                disc_r = 2 * int(round(mult * float(total_w) / 4.0))
                if disc_r <= total_h:
                    disc_r = (2 * (total_h + 1)) // 2

                disc_ansi_bg = bg_ansi(disc_rgb) if disc_rgb else ""
                black_ansi_bg = "\033[40m" if args.black_bg else ""

                # Draw disc background on clock bounding area
                if disc_rgb:
                    for y in range(1, term_h + 1):
                        for x in range(1, term_w + 1):
                            dx = x - cx
                            dy = y - cy
                            d = math.sqrt(dx * dx + (2.0 * dy) * (2.0 * dy))
                            if d <= disc_r:
                                sys.stdout.write(f"\033[{y};{x}H" + disc_ansi_bg + " " + RESET_ANSI)

                # Draw box outline if requested
                if args.box or args.color_box:
                    box_top = "╭" + "─" * clock_w + "╮"
                    box_bot = "╰" + "─" * clock_w + "╯"
                    sys.stdout.write(f"\033[{start_y};{start_x}H" + fg_ansi(box_fg_rgb) + box_top + RESET_ANSI)
                    for i in range(clock_h):
                        sys.stdout.write(f"\033[{start_y + 1 + i};{start_x}H" + fg_ansi(box_fg_rgb) + "│" + RESET_ANSI)
                        sys.stdout.write(f"\033[{start_y + 1 + i};{start_x + clock_w + 1}H" + fg_ansi(box_fg_rgb) + "│" + RESET_ANSI)
                    sys.stdout.write(f"\033[{start_y + clock_h + 1};{start_x}H" + fg_ansi(box_fg_rgb) + box_bot + RESET_ANSI)
                    digit_x = start_x + 1
                    digit_y = start_y + 1
                else:
                    digit_x = start_x
                    digit_y = start_y

                # Draw bignum digits
                fg_code = fg_ansi(fg_rgb)
                if args.inverse:
                    fg_code += "\033[7m"

                for i, line in enumerate(lines):
                    sys.stdout.write(f"\033[{digit_y + i};{digit_x}H")
                    for x_idx, ch in enumerate(line):
                        cell_x = digit_x + x_idx
                        cell_y = digit_y + i
                        dx = cell_x - cx
                        dy = cell_y - cy
                        d = math.sqrt(dx * dx + (2.0 * dy) * (2.0 * dy))
                        bg_code = disc_ansi_bg if (disc_rgb and d <= disc_r) else black_ansi_bg
                        sys.stdout.write(fg_code + bg_code + ch + RESET_ANSI)

                # Draw extra text
                if args.text and args.text != "none":
                    text_x = max(1, (term_w - len(args.text)) // 2 + 1)
                    text_y = min(term_h, digit_y + clock_h + 1)
                    sys.stdout.write(f"\033[{text_y};{text_x}H" + args.text + RESET_ANSI)

            sys.stdout.flush()
            time.sleep(0.05 if continuous else 0.2)

    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\033[?25h" + RESET_ANSI + "\n")
        sys.stdout.flush()
        if is_tty and old_settings:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            except Exception:
                pass
    return 0


def main():
    parser = argparse.ArgumentParser(description="Terminal clock using bignum digits / analog mode")
    parser.add_argument('-24', action='store_true', dest='f24', help="Use 24-hour time format")
    parser.add_argument('-analog', action='store_true', help="Analog clock with hours, minutes and seconds hands")
    parser.add_argument('-aa', action='store_true', help="Use antialiased image based analog clock")
    parser.add_argument('-c', action='store_true', help="Analog clock updates continuously instead of seconds ticks")
    parser.add_argument('-no-seconds', action='store_true', help="Don't show seconds")
    parser.add_argument('-no-blink', action='store_true', help="Don't blink the colon")
    parser.add_argument('-box', action='store_true', help="Draw a simple rounded corner outline around the time")
    parser.add_argument('-color', default="red", help="Color to use")
    parser.add_argument('-color-disc', default="E0C020", help="Color disc around time (default E0C020)")
    parser.add_argument('-color-box', default="", help="Color box around time")
    parser.add_argument('-radius', type=float, default=1.2, help="Radius of disc around time")
    parser.add_argument('-breath', action='store_true', help="Pulse the color")
    parser.add_argument('-bounce', type=int, default=0, help="Bounce speed")
    parser.add_argument('-inverse', action='store_true', help="Inverse foreground and background")
    parser.add_argument('-black-bg', action='store_true', help="Set black background")
    parser.add_argument('-countdown', help="Countdown duration (e.g. 5m, 3w2d10h)")
    parser.add_argument('-until', help="Countdown until date/time")
    parser.add_argument('-text', default="", help="Text to display below clock")
    parser.add_argument('-tail', help="Tail given file while showing clock")
    parser.add_argument('digits', nargs='*', help="One-off digits to display")

    args = parser.parse_args()
    sys.exit(run_tclock(args))


if __name__ == '__main__':
    main()
