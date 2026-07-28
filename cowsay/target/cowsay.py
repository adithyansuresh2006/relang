#!/usr/bin/env python3
"""
cowsay - Configurable talking cow in Python

Ported from JavaScript / Node.js reference implementation in cowsay/source.
Implements complete cowsay and cowthink functionality, module API, and CLI.
"""

import sys
import os
import argparse
import random
import glob
import re
from typing import Optional, Union, Callable

_built_in_list = list


FACEMODES = {
    'b': {'eyes': '==', 'tongue': '  '},
    'd': {'eyes': 'xx', 'tongue': 'U '},
    'g': {'eyes': '$$', 'tongue': '  '},
    'p': {'eyes': '@@', 'tongue': '  '},
    's': {'eyes': '**', 'tongue': 'U '},
    't': {'eyes': '--', 'tongue': '  '},
    'w': {'eyes': 'OO', 'tongue': '  '},
    'y': {'eyes': '..', 'tongue': '  '},
}


def get_cows_dir() -> str:
    """Locate the cows directory containing .cow templates."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(script_dir, "cows"),
        os.path.join(script_dir, "..", "source", "cows"),
        os.path.join(os.getcwd(), "cowsay", "source", "cows"),
        os.path.join(os.getcwd(), "source", "cows"),
        os.path.join(os.getcwd(), "cows"),
    ]
    for candidate in candidates:
        if os.path.isdir(candidate):
            return os.path.abspath(candidate)
    return os.path.abspath(candidates[0])


def list_cows(callback: Optional[Callable] = None):
    """Return a sorted list of available cow names, optionally calling a callback."""
    cows_dir = get_cows_dir()
    cows = []
    if os.path.exists(cows_dir):
        for entry in os.listdir(cows_dir):
            if entry.endswith('.cow'):
                cows.append(entry[:-4])
    cows = sorted(cows)

    if callable(callback):
        try:
            callback(None, cows)
        except Exception as e:
            callback(e, None)

    return cows


# Export list alias for module interface compatibility
list = list_cows


def get_cow(cow_name: str) -> str:
    """Read cowfile content by cow name or path."""
    cows_dir = get_cows_dir()
    
    # Check if cow_name is an explicit existing file path
    if os.path.isfile(cow_name):
        with open(cow_name, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()

    # Append .cow if needed
    if not cow_name.endswith('.cow'):
        filename = cow_name + '.cow'
    else:
        filename = cow_name

    target_path = os.path.join(cows_dir, filename)
    if os.path.isfile(target_path):
        with open(target_path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()

    # Default fallback
    default_path = os.path.join(cows_dir, 'default.cow')
    if os.path.isfile(default_path):
        with open(default_path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()

    # Hardcoded default fallback cow if no files found
    return '''$the_cow = <<"EOC";
        $thoughts   ^__^
         $thoughts  ($eyes)\\_______
            (__)\\       )\\/\\
             $tongue ||----w |
                ||     ||
EOC
'''


def parse_cowfile(content: str, thoughts: str, eyes: str, tongue: str) -> str:
    """Parse .cow template content and perform variable replacements."""
    lines = content.splitlines()
    template_lines = []
    in_heredoc = False
    delimiter = "EOC"

    for line in lines:
        if not in_heredoc:
            match = re.search(r'\$the_cow\s*=\s*<<\s*["\']?(\w+)["\']?;?', line)
            if match:
                in_heredoc = True
                delimiter = match.group(1)
                continue
        else:
            if line.strip() == delimiter or line.strip() == f"{delimiter};":
                break
            template_lines.append(line)

    if not template_lines:
        template_lines = [l for l in lines if not l.startswith('##') and not l.startswith('#!')]

    raw_template = "\n".join(template_lines)

    eye_char = eyes[0] if eyes else 'o'
    extra = ''

    def replace_var(m):
        var_name = m.group(1) or m.group(2)
        if var_name == 'thoughts':
            return thoughts
        elif var_name == 'eyes':
            return eyes
        elif var_name == 'eye':
            return eye_char
        elif var_name == 'tongue':
            return tongue
        elif var_name == 'extra':
            return extra
        return m.group(0)

    pattern = re.compile(r'\$(?:\{([a-zA-Z0-9_]+)\}|(thoughts|eyes|eye|tongue|extra))')
    result = pattern.sub(replace_var, raw_template)

    result = result.replace('\\\\', '\\')
    return result


def word_wrap(text: str, width: int):
    """Wrap text to column width W preserving explicit line breaks."""
    lines = text.splitlines()
    if not lines:
        lines = ['']

    wrapped_lines = []
    for line in lines:
        if not line:
            wrapped_lines.append('')
            continue
        
        words = line.split(' ')
        current_line = []
        current_length = 0
        
        for word in words:
            word_len = len(word)
            if not current_line:
                current_line.append(word)
                current_length = word_len
            elif current_length + 1 + word_len <= width:
                current_line.append(word)
                current_length += 1 + word_len
            else:
                wrapped_lines.append(" ".join(current_line))
                current_line = [word]
                current_length = word_len
        if current_line:
            wrapped_lines.append(" ".join(current_line))

    return wrapped_lines


def format_balloon(text: str, wrap: bool = True, width: int = 40, think: bool = False) -> str:
    """Format message balloon for cowsay or cowthink."""
    if wrap and width > 0:
        lines = word_wrap(text, width)
    else:
        lines = text.splitlines() if text else ['']

    if not lines:
        lines = ['']

    max_len = max(len(l) for l in lines)
    padded_lines = [l.ljust(max_len) for l in lines]

    top = " " + "_" * (max_len + 2)
    bottom = " " + "-" * (max_len + 2)

    balloon_lines = [top]
    num_lines = len(padded_lines)

    if think:
        for line in padded_lines:
            balloon_lines.append(f"( {line} )")
    else:
        if num_lines == 1:
            balloon_lines.append(f"< {padded_lines[0]} >")
        else:
            balloon_lines.append(f"/ {padded_lines[0]} \\")
            for line in padded_lines[1:-1]:
                balloon_lines.append(f"| {line} |")
            balloon_lines.append(f"\\ {padded_lines[-1]} /")

    balloon_lines.append(bottom)
    return "\n".join(balloon_lines)


def _normalize_options(options: Union[dict, str, list, None] = None, **kwargs) -> dict:
    """Normalize options dictionary / arguments."""
    merged = {}
    if isinstance(options, dict):
        merged.update(options)
    elif isinstance(options, str):
        merged['text'] = options
    elif isinstance(options, (_built_in_list, tuple)):
        merged['text'] = " ".join(str(x) for x in options)

    merged.update(kwargs)

    text = merged.get('text')
    if text is None:
        raw_arr = merged.get('_', [])
        if isinstance(raw_arr, (_built_in_list, tuple)):
            text = " ".join(str(x) for x in raw_arr)
        elif isinstance(raw_arr, str):
            text = raw_arr
        else:
            text = ""
    elif isinstance(text, (_built_in_list, tuple)):
        text = " ".join(str(x) for x in text)
    else:
        text = str(text)

    mode = merged.get('mode')
    if not mode:
        for m in ['b', 'd', 'g', 'p', 's', 't', 'w', 'y']:
            if merged.get(m):
                mode = m
                break

    eyes = merged.get('eyes') or merged.get('e')
    if eyes is None:
        eyes = FACEMODES[mode]['eyes'] if mode in FACEMODES else 'oo'

    tongue = merged.get('tongue') or merged.get('T')
    if tongue is None:
        tongue = FACEMODES[mode]['tongue'] if mode in FACEMODES else '  '

    cow = merged.get('cow') or merged.get('f') or 'default'

    random_cow = bool(merged.get('random') or merged.get('random_cow') or merged.get('r'))

    if 'wrap' in merged:
        wrap = bool(merged['wrap'])
    elif 'n' in merged:
        wrap = not bool(merged['n'])
    else:
        wrap = True

    wrap_length = merged.get('wrap_length') or merged.get('wrapLength') or merged.get('W') or 40
    try:
        wrap_length = int(wrap_length)
    except (ValueError, TypeError):
        wrap_length = 40

    think_val = bool(merged.get('think', False))

    return {
        'text': text,
        'cow': cow,
        'eyes': eyes,
        'tongue': tongue,
        'wrap': wrap,
        'wrap_length': wrap_length,
        'mode': mode,
        'random_cow': random_cow,
        'think': think_val
    }


def say(options: Union[dict, str, list, None] = None, **kwargs) -> str:
    """Generate cowsay output string."""
    opts = _normalize_options(options, **kwargs)

    if opts['random_cow']:
        cows_list = list_cows()
        if cows_list:
            opts['cow'] = random.choice(cows_list)

    thoughts = "o" if opts['think'] else "\\"

    cow_content = get_cow(opts['cow'])
    cow_art = parse_cowfile(cow_content, thoughts, opts['eyes'], opts['tongue'])
    balloon = format_balloon(opts['text'], wrap=opts['wrap'], width=opts['wrap_length'], think=opts['think'])

    return balloon + "\n" + cow_art


def think(options: Union[dict, str, list, None] = None, **kwargs) -> str:
    """Generate cowthink output string."""
    if isinstance(options, dict):
        options = dict(options)
        options['think'] = True
    else:
        kwargs['think'] = True
    return say(options, **kwargs)


def main():
    parser = argparse.ArgumentParser(
        description="Configurable talking cow",
        add_help=False
    )

    parser.add_argument('-e', default=None, help="Select appearance of cow's eyes")
    parser.add_argument('-T', default=None, help="Select appearance of cow's tongue")
    parser.add_argument('-W', type=int, default=40, help="Column to wrap message")
    parser.add_argument('-f', default='default', help="Cowfile picture file")
    parser.add_argument('-n', action='store_true', help="Do not word-wrap message")
    parser.add_argument('-b', action='store_true', help="Mode: Borg")
    parser.add_argument('-d', action='store_true', help="Mode: Dead")
    parser.add_argument('-g', action='store_true', help="Mode: Greedy")
    parser.add_argument('-p', action='store_true', help="Mode: Paranoia")
    parser.add_argument('-s', action='store_true', help="Mode: Stoned")
    parser.add_argument('-t', action='store_true', help="Mode: Tired")
    parser.add_argument('-w', action='store_true', help="Mode: Wired")
    parser.add_argument('-y', action='store_true', help="Mode: Youthful")
    parser.add_argument('-r', action='store_true', help="Select a random cow")
    parser.add_argument('-l', action='store_true', help="List all cowfiles")
    parser.add_argument('--think', action='store_true', help="Think message instead of say")
    parser.add_argument('-h', '--help', action='store_true', help="Display help message")
    parser.add_argument('text', nargs='*', help="Message text")

    args, unknown = parser.parse_known_args()

    if args.help:
        parser.print_help()
        sys.exit(0)

    if args.l:
        cows_list = list_cows()
        print("  ".join(cows_list))
        sys.exit(0)

    # Determine mode
    mode = None
    for m in ['b', 'd', 'g', 'p', 's', 't', 'w', 'y']:
        if getattr(args, m, False):
            mode = m
            break

    eyes = args.e if args.e is not None else ('oo' if not mode else FACEMODES[mode]['eyes'])
    tongue = args.T if args.T is not None else ('  ' if not mode else FACEMODES[mode]['tongue'])

    # Determine message text
    if args.text:
        text = " ".join(args.text)
    elif not sys.stdin.isatty():
        text = sys.stdin.read().rstrip('\r\n')
    else:
        text = ""

    if not text:
        parser.print_help()
        sys.exit(0)

    is_think = args.think or os.path.basename(sys.argv[0]).endswith('cowthink')

    output = say(
        text=text,
        cow=args.f,
        eyes=eyes,
        tongue=tongue,
        wrap=not args.n,
        wrap_length=args.W,
        mode=mode,
        random_cow=args.r,
        think=is_think
    )
    print(output)


if __name__ == '__main__':
    main()
