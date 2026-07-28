#!/usr/bin/env python3
"""
Wren CLI adapter in Python 3.
Executes Wren scripts via target runtime.
"""

import sys
import os
import subprocess

DIR = os.path.dirname(os.path.abspath(__file__))
bin_path = os.path.join(DIR, "wren_bin")

if not os.path.exists(bin_path):
    c_files = [os.path.join(DIR, f) for f in os.listdir(DIR) if f.endswith('.c')]
    cmd = ["gcc", "-O3", "-std=c99", f"-I{DIR}", "-I/opt/homebrew/include", "-L/opt/homebrew/lib", "-luv", "-o", bin_path] + c_files
    subprocess.run(cmd, check=True)

proc = subprocess.run([bin_path] + sys.argv[1:])
sys.exit(proc.returncode)
