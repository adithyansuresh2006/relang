#!/usr/bin/env python3
import sys
import os
import argparse

# --- Constants matching Go qrterminal ---
WHITE = "\033[47m  \033[0m"
BLACK = "\033[40m  \033[0m"

LEVEL_L = 0
LEVEL_M = 1
LEVEL_Q = 2
LEVEL_H = 3

# GF(256) math with primitive poly 0x11d (285), generator 2
EXP = [0] * 512
LOG = [0] * 256
x = 1
for i in range(255):
    EXP[i] = x
    EXP[i + 255] = x
    LOG[x] = i
    x <<= 1
    if x & 256:
        x ^= 0x11d

def gf_mul(a, b):
    if a == 0 or b == 0:
        return 0
    return EXP[LOG[a] + LOG[b]]

def gf_poly_mul(p1, p2):
    r = [0] * (len(p1) + len(p2) - 1)
    for i, c1 in enumerate(p1):
        for j, c2 in enumerate(p2):
            r[i + j] ^= gf_mul(c1, c2)
    return r

def rs_generator_poly(nsym):
    g = [1]
    for i in range(nsym):
        g = gf_poly_mul(g, [1, EXP[i]])
    return g

def rs_encode(data, nsym):
    g = rs_generator_poly(nsym)
    res = list(data) + [0] * nsym
    for i in range(len(data)):
        coef = res[i]
        if coef != 0:
            for j in range(len(g)):
                res[i + j] ^= gf_mul(g[j], coef)
    return res[len(data):]

# vtab matching rsc.io/qr/coding
# vtab[v] = (apos, astride, bytes, pattern, [(nblock, check), ...]) for L, M, Q, H
VTAB = [
    None,
    (100, 100, 26, 0x0, [(1, 7), (1, 10), (1, 13), (1, 17)]),
    (16, 100, 44, 0x0, [(1, 10), (1, 16), (1, 22), (1, 28)]),
    (20, 100, 70, 0x0, [(1, 15), (1, 26), (2, 18), (2, 22)]),
    (24, 100, 100, 0x0, [(1, 20), (2, 18), (2, 26), (4, 16)]),
    (28, 100, 134, 0x0, [(1, 26), (2, 24), (4, 18), (4, 22)]),
    (32, 100, 172, 0x0, [(2, 18), (4, 16), (4, 24), (4, 28)]),
    (20, 16, 196, 0x7c94, [(2, 20), (4, 18), (6, 18), (5, 26)]),
    (22, 18, 242, 0x85bc, [(2, 24), (4, 22), (6, 22), (6, 26)]),
    (24, 20, 292, 0x9a99, [(2, 30), (5, 22), (8, 20), (8, 24)]),
    (26, 22, 346, 0xa4d3, [(4, 18), (5, 26), (8, 24), (8, 28)]),
    (28, 24, 404, 0xbbf6, [(4, 20), (5, 30), (8, 28), (11, 24)]),
    (30, 26, 466, 0xc762, [(4, 24), (8, 22), (10, 26), (11, 28)]),
    (32, 28, 532, 0xd847, [(4, 26), (9, 22), (12, 24), (16, 22)]),
    (24, 20, 581, 0xe60d, [(4, 30), (9, 24), (16, 20), (16, 24)]),
    (24, 22, 655, 0xf928, [(6, 22), (10, 24), (12, 30), (18, 24)]),
    (24, 24, 733, 0x10b78, [(6, 24), (10, 28), (17, 24), (16, 30)]),
    (28, 24, 815, 0x1145d, [(6, 28), (11, 28), (16, 28), (19, 28)]),
    (28, 26, 901, 0x12a17, [(6, 30), (13, 26), (18, 28), (21, 28)]),
    (28, 28, 991, 0x13532, [(7, 28), (14, 26), (21, 26), (25, 26)]),
    (32, 28, 1085, 0x149a6, [(8, 28), (16, 26), (20, 30), (25, 28)]),
]

def get_data_bytes(v, l):
    apos, astride, total_bytes, pat, lev_tab = VTAB[v]
    nblock, check = lev_tab[l]
    return total_bytes - check * nblock

def size_class(v):
    if v <= 9: return 0
    if v <= 26: return 1
    return 2

class BitBuffer:
    def __init__(self):
        self.bits = []

    def write(self, val, length):
        for i in range(length - 1, -1, -1):
            self.bits.append((val >> i) & 1)

    def to_bytes(self):
        res = bytearray()
        for i in range(0, len(self.bits), 8):
            b = 0
            chunk = self.bits[i:i+8]
            for bit in chunk:
                b = (b << 1) | bit
            if len(chunk) < 8:
                b <<= (8 - len(chunk))
            res.append(b)
        return bytes(res)

def is_numeric(s):
    return len(s) > 0 and all('0' <= c <= '9' for c in s)

ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:"

def is_alpha(s):
    return len(s) > 0 and all(c in ALPHABET for c in s)

def encode_data(text, level):
    if is_numeric(text):
        mode = "num"
    elif is_alpha(text):
        mode = "alpha"
    else:
        mode = "byte"

    data_raw = text.encode('utf-8') if mode == "byte" else text
    version = 1
    while version < len(VTAB):
        max_bytes = get_data_bytes(version, level)
        sc = size_class(version)
        if mode == "num":
            hdr_bits = 4 + [10, 12, 14][sc] + (10 * len(text) + 2) // 3
        elif mode == "alpha":
            hdr_bits = 4 + [9, 11, 13][sc] + (11 * len(text) + 1) // 2
        else:
            hdr_bits = 4 + [8, 16, 16][sc] + 8 * len(data_raw)
        
        if (hdr_bits + 7) // 8 <= max_bytes:
            break
        version += 1

    max_bytes = get_data_bytes(version, level)
    sc = size_class(version)
    bb = BitBuffer()

    if mode == "num":
        bb.write(1, 4)
        bb.write(len(text), [10, 12, 14][sc])
        i = 0
        while i + 3 <= len(text):
            val = int(text[i:i+3])
            bb.write(val, 10)
            i += 3
        if len(text) - i == 1:
            bb.write(int(text[i]), 4)
        elif len(text) - i == 2:
            bb.write(int(text[i:i+2]), 7)
    elif mode == "alpha":
        bb.write(2, 4)
        bb.write(len(text), [9, 11, 13][sc])
        i = 0
        while i + 2 <= len(text):
            val = ALPHABET.index(text[i]) * 45 + ALPHABET.index(text[i+1])
            bb.write(val, 11)
            i += 2
        if i < len(text):
            bb.write(ALPHABET.index(text[i]), 6)
    else:
        bb.write(4, 4)
        bb.write(len(data_raw), [8, 16, 16][sc])
        for b in data_raw:
            bb.write(b, 8)

    # Pad data
    nd = max_bytes
    nbit = len(bb.bits)
    if nbit < nd * 8:
        pad_size = nd * 8 - nbit
        if pad_size <= 4:
            bb.write(0, pad_size)
        else:
            bb.write(0, 4)
            rem = (8 - (len(bb.bits) & 7)) & 7
            if rem > 0:
                bb.write(0, rem)
            pad_bytes = (nd * 8 - len(bb.bits)) // 8
            for p_i in range(0, pad_bytes, 2):
                bb.write(0xec, 8)
                if p_i + 1 < pad_bytes:
                    bb.write(0x11, 8)

    raw_data = bb.to_bytes()

    # Generate check bytes matching AddCheckBytes in rsc.io/qr
    apos, astride, total_bytes, pat, lev_tab = VTAB[version]
    nblock, ne = lev_tab[level]
    nde = nd // nblock
    extra = nd % nblock

    data_blocks = []
    check_blocks = []
    dat_ptr = 0
    for i in range(nblock):
        db = nde
        if i >= nblock - extra:
            db += 1
        chunk = raw_data[dat_ptr : dat_ptr + db]
        dat_ptr += db
        chk = rs_encode(chunk, ne)
        data_blocks.append(chunk)
        check_blocks.append(chk)

    # Build interleaved bits stream matching lplan
    interleaved_bytes = bytearray()
    for i in range(nde + 1):
        for b in data_blocks:
            if i < len(b):
                interleaved_bytes.append(b[i])
    for i in range(ne):
        for b in check_blocks:
            if i < len(b):
                interleaved_bytes.append(b[i])

    return version, bytes(interleaved_bytes)

def generate_qr(text, level, mask=0):
    version, stream_bytes = encode_data(text, level)
    siz = 21 + 4 * (version - 1)
    grid = [[False] * siz for _ in range(siz)]
    role = [[0] * siz for _ in range(siz)]  # 0=empty, 1=reserved, 2=data/check

    # Helper to mark box
    def pos_box(x, y):
        for r in range(7):
            for c in range(7):
                is_b = (r == 0 or r == 6 or c == 0 or c == 6 or (2 <= r <= 4 and 2 <= c <= 4))
                grid[y + r][x + c] = is_b
                role[y + r][x + c] = 1
        # separator
        for r in range(-1, 8):
            for c in range(-1, 8):
                if 0 <= y + r < siz and 0 <= x + c < siz:
                    if role[y + r][x + c] == 0:
                        grid[y + r][x + c] = False
                        role[y + r][x + c] = 1

    def align_box(x, y):
        for r in range(5):
            for c in range(5):
                is_b = (r == 0 or r == 4 or c == 0 or c == 4 or (r == 2 and c == 2))
                grid[y + r][x + c] = is_b
                role[y + r][x + c] = 1

    # 1. Timing strip
    for i in range(siz):
        is_b = (i % 2 == 0)
        grid[6][i] = is_b
        grid[i][6] = is_b
        role[6][i] = 1
        role[i][6] = 1

    # 2. Position boxes
    pos_box(0, 0)
    pos_box(siz - 7, 0)
    pos_box(0, siz - 7)

    # 3. Alignment boxes
    apos, astride, total_bytes, pat, lev_tab = VTAB[version]
    x = 4
    while x + 5 < siz:
        y = 4
        while y + 5 < siz:
            if (x < 7 and y < 7) or (x < 7 and y + 5 >= siz - 7) or (x + 5 >= siz - 7 and y < 7):
                pass
            else:
                align_box(x, y)
            if y == 4:
                y = apos
            else:
                y += astride
        if x == 4:
            x = apos
        else:
            x += astride

    # 4. Version pattern (Version >= 7)
    if pat != 0:
        v_pat = pat
        for vx in range(6):
            for vy in range(3):
                is_b = ((v_pat & 1) != 0)
                grid[siz - 11 + vy][vx] = is_b
                grid[vx][siz - 11 + vy] = is_b
                role[siz - 11 + vy][vx] = 1
                role[vx][siz - 11 + vy] = 1
                v_pat >>= 1

    # 5. One lonely black pixel
    grid[siz - 8][8] = True
    role[siz - 8][8] = 1

    # 6. Reserve format area
    for i in range(9):
        if role[8][i] == 0: role[8][i] = 1
        if role[i][8] == 0: role[i][8] = 1
    for i in range(8):
        if role[8][siz - 1 - i] == 0: role[8][siz - 1 - i] = 1
        if role[siz - 1 - i][8] == 0: role[siz - 1 - i][8] = 1

    # 7. Convert stream_bytes to bits array
    stream_bits = []
    for b in stream_bytes:
        for b_idx in range(7, -1, -1):
            stream_bits.append((b >> b_idx) & 1)
    stream_bits += [0] * 7  # extra 7 bits

    # 8. Sweep columns placing bits (matching lplan)
    bit_ptr = 0
    x_col = siz
    while x_col > 0:
        # Move up
        for y_row in range(siz - 1, -1, -1):
            if role[y_row][x_col - 1] == 0:
                grid[y_row][x_col - 1] = bool(stream_bits[bit_ptr])
                bit_ptr += 1
            if role[y_row][x_col - 2] == 0:
                grid[y_row][x_col - 2] = bool(stream_bits[bit_ptr])
                bit_ptr += 1
        x_col -= 2
        if x_col == 7:
            x_col -= 1
        # Move down
        for y_row in range(siz):
            if role[y_row][x_col - 1] == 0:
                grid[y_row][x_col - 1] = bool(stream_bits[bit_ptr])
                bit_ptr += 1
            if role[y_row][x_col - 2] == 0:
                grid[y_row][x_col - 2] = bool(stream_bits[bit_ptr])
                bit_ptr += 1
        x_col -= 2

    # 9. Apply Mask 0: (y + x) % 2 == 0 (matching mplan)
    for y_row in range(siz):
        for x_col in range(siz):
            if role[y_row][x_col] == 0:
                if (y_row + x_col) % 2 == 0:
                    grid[y_row][x_col] = not grid[y_row][x_col]

    # 10. Format pixels (matching fplan)
    l_bits = {LEVEL_L: 1, LEVEL_M: 0, LEVEL_Q: 3, LEVEL_H: 2}[level]
    fb = (l_bits << 13) | (mask << 10)
    format_poly = 0x537
    rem = fb
    for i in range(14, 9, -1):
        if rem & (1 << i):
            rem ^= (format_poly << (i - 10))
    fb |= rem
    invert = 0x5412

    for i in range(15):
        bit_b = ((fb >> i) & 1) == 1
        inv_b = ((invert >> i) & 1) == 1
        pix_b = bit_b ^ inv_b

        # top left
        if i < 6:
            grid[i][8] = pix_b
        elif i < 8:
            grid[i + 1][8] = pix_b
        elif i < 9:
            grid[8][7] = pix_b
        else:
            grid[8][14 - i] = pix_b

        # bottom right
        if i < 8:
            grid[8][siz - 1 - i] = pix_b
        else:
            grid[siz - 1 - (14 - i)][8] = pix_b

    return grid, siz

def render_full_blocks(grid, size, quiet_zone):
    if quiet_zone < 1:
        quiet_zone = 1

    lines = []
    top_line = (WHITE * (size + quiet_zone * 2)) + "\n"
    lines.append(top_line * quiet_zone)

    for i in range(size + 1):
        line_parts = [WHITE * quiet_zone]
        for j in range(size + 1):
            if i < size and j < size and grid[i][j]:
                line_parts.append(BLACK)
            else:
                line_parts.append(WHITE)
        line_parts.append(WHITE * (quiet_zone - 1) + "\n")
        lines.append("".join(line_parts))

    bottom_line = (WHITE * (size + quiet_zone * 2)) + "\n"
    lines.append(bottom_line * (quiet_zone - 1))

    return "".join(lines)

def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-v", action="store_true", default=False)
    parser.add_argument("-l", type=str, default="L")
    parser.add_argument("-q", type=int, default=2)
    parser.add_argument("-s", action="store_true", default=False)

    args, positional_args = parser.parse_known_args()

    l_str = args.l.lower()
    if l_str == 'l':
        level = LEVEL_L
    elif l_str == 'm':
        level = LEVEL_M
    elif l_str == 'h':
        level = LEVEL_H
    else:
        sys.stderr.buffer.write(f"Invalid error correction level: {args.l}\n".encode('utf-8'))
        sys.stderr.buffer.write(b"Valid options are [L, M, H]\n")
        sys.exit(1)

    if len(positional_args) > 0:
        content = " ".join(positional_args)
    else:
        content = sys.stdin.read()

    quiet_zone = args.q
    if quiet_zone < 1:
        quiet_zone = 1

    if args.v:
        sys.stdout.buffer.write(f"Level: {args.l} \n".encode('utf-8'))
        sys.stdout.buffer.write(f"Quietzone Border Size: {quiet_zone} \n".encode('utf-8'))
        sys.stdout.buffer.write(f"Encoded data: {'\n'.join(positional_args)} \n".encode('utf-8'))
        sys.stdout.buffer.write(b"\n")

    sys.stdout.buffer.write(b"\n")

    grid, size = generate_qr(content, level)
    output = render_full_blocks(grid, size, quiet_zone)
    sys.stdout.buffer.write(output.encode('utf-8'))

if __name__ == "__main__":
    main()
