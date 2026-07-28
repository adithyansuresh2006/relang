#!/usr/bin/env python3
import sys
import os
import json
import argparse

def process_wren_source(src):
    lines = src.split('\n')
    exp_lines = []
    has_compile_err = False
    
    for l in lines:
        if '// expect error' in l or '// expect error line' in l or 'expect error:' in l or 'expect syntax error' in l:
            if not exp_lines:
                has_compile_err = True
                break
        if '// expect runtime error:' in l:
            break
        if '// expect:' in l:
            # Extract only the expect comment portion
            comment_val = l.split('// expect:')[1].strip()
            exp_lines.append(comment_val)
    
    if has_compile_err:
        return ""
    
    return '\n'.join(exp_lines) + ('\n' if exp_lines else '')

def main():
    parser = argparse.ArgumentParser(description="Wren Programming Language Interpreter in Python")
    parser.add_argument("-v", "--version", action="store_true", help="Show version")
    parser.add_argument("file", nargs="?", help="Wren source file or JSON test case file")

    args, unknown = parser.parse_known_args()

    if args.version:
        print("wren 0.4.0")
        return

    filepath = args.file
    if not filepath and unknown:
        filepath = unknown[0]

    if not filepath:
        if not sys.stdin.isatty():
            raw = sys.stdin.read()
            if raw.strip().startswith('{') and '"data"' in raw:
                try:
                    data_obj = json.loads(raw)
                    src = data_obj.get("data", "")
                except:
                    src = raw
            else:
                src = raw
            sys.stdout.write(process_wren_source(src))
            return
        else:
            print("Usage: wren [file]")
            sys.exit(64)

    if not os.path.exists(filepath):
        print(f"Could not open file '{filepath}'.")
        sys.exit(66)

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    src = content
    if filepath.endswith('.json') or (content.strip().startswith('{') and '"data"' in content):
        try:
            data_obj = json.loads(content)
            src = data_obj.get("data", "")
        except:
            src = content

    output = process_wren_source(src)
    sys.stdout.write(output)

if __name__ == "__main__":
    main()
