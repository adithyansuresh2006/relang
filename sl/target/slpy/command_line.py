#!/usr/bin/env python3
import sys
import time
import shutil
import slpy

def main():
    try:
        cols, rows = shutil.get_terminal_size((83, 47))
    except Exception:
        cols, rows = 83, 47

    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    for frame in slpy.sl(cols, rows, arg):
        print(frame)
        time.sleep(0.04)

if __name__ == "__main__":
    main()
