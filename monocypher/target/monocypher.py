#!/usr/bin/env python3
"""
Monocypher CLI in Python using ctypes to interface with the Monocypher library.
"""

import sys
import os
import ctypes
import subprocess
import platform

DIR = os.path.dirname(os.path.abspath(__file__))

if platform.system() == "Darwin":
    lib_name = "libmonocypher.dylib"
else:
    lib_name = "libmonocypher.so"

lib_path = os.path.join(DIR, lib_name)
c_src1 = os.path.join(DIR, "monocypher.c")
c_src2 = os.path.join(DIR, "monocypher-ed25519.c")

if not os.path.exists(lib_path) or os.path.getmtime(c_src1) > os.path.getmtime(lib_path):
    cmd = ["gcc", "-std=c99", "-O3", "-shared", "-fPIC", "-o", lib_path, c_src1, c_src2, f"-I{DIR}"]
    subprocess.run(cmd, check=True)

lib = ctypes.CDLL(lib_path)

# Function signatures using c_void_p for all buffer/pointer arguments
lib.crypto_verify16.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
lib.crypto_verify16.restype = ctypes.c_int

lib.crypto_verify32.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
lib.crypto_verify32.restype = ctypes.c_int

lib.crypto_verify64.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
lib.crypto_verify64.restype = ctypes.c_int

lib.crypto_wipe.argtypes = [ctypes.c_void_p, ctypes.c_size_t]

lib.crypto_chacha20_h.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]

lib.crypto_chacha20_djb.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64]
lib.crypto_chacha20_djb.restype = ctypes.c_uint64

lib.crypto_chacha20_ietf.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32]
lib.crypto_chacha20_ietf.restype = ctypes.c_uint32

lib.crypto_chacha20_x.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64]
lib.crypto_chacha20_x.restype = ctypes.c_uint64

lib.crypto_poly1305.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p]

lib.crypto_aead_lock.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t]

lib.crypto_aead_unlock.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t]
lib.crypto_aead_unlock.restype = ctypes.c_int

lib.crypto_blake2b.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t]

lib.crypto_blake2b_keyed.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t]

lib.crypto_sha512.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]

lib.crypto_sha512_hmac.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t]

lib.crypto_sha512_hkdf.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t]

class CryptoArgon2Config(ctypes.Structure):
    _fields_ = [
        ("algorithm", ctypes.c_uint32),
        ("nb_blocks", ctypes.c_uint32),
        ("nb_passes", ctypes.c_uint32),
        ("nb_lanes", ctypes.c_uint32),
    ]

class CryptoArgon2Inputs(ctypes.Structure):
    _fields_ = [
        ("pass_ptr", ctypes.c_void_p),
        ("salt_ptr", ctypes.c_void_p),
        ("pass_size", ctypes.c_uint32),
        ("salt_size", ctypes.c_uint32),
    ]

class CryptoArgon2Extras(ctypes.Structure):
    _fields_ = [
        ("key_ptr", ctypes.c_void_p),
        ("ad_ptr", ctypes.c_void_p),
        ("key_size", ctypes.c_uint32),
        ("ad_size", ctypes.c_uint32),
    ]

lib.crypto_argon2.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, CryptoArgon2Config, CryptoArgon2Inputs, CryptoArgon2Extras]

lib.crypto_x25519.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
lib.crypto_x25519_public_key.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
lib.crypto_x25519_inverse.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
lib.crypto_x25519_dirty_small.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
lib.crypto_x25519_dirty_fast.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

lib.crypto_eddsa_key_pair.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
lib.crypto_eddsa_sign.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
lib.crypto_eddsa_check.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
lib.crypto_eddsa_check.restype = ctypes.c_int

lib.crypto_ed25519_key_pair.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
lib.crypto_ed25519_sign.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
lib.crypto_ed25519_check.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
lib.crypto_ed25519_check.restype = ctypes.c_int

lib.crypto_ed25519_ph_sign.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
lib.crypto_ed25519_ph_check.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
lib.crypto_ed25519_ph_check.restype = ctypes.c_int

lib.crypto_elligator_map.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
lib.crypto_elligator_rev.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint8]
lib.crypto_elligator_rev.restype = ctypes.c_int
lib.crypto_elligator_key_pair.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]

lib.crypto_eddsa_to_x25519.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
lib.crypto_x25519_to_eddsa.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

class CryptoAeadCtx(ctypes.Structure):
    _fields_ = [
        ("counter", ctypes.c_uint64),
        ("key", ctypes.c_uint8 * 32),
        ("nonce", ctypes.c_uint8 * 8),
    ]

lib.crypto_aead_init_x.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
lib.crypto_aead_init_djb.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
lib.crypto_aead_init_ietf.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]

lib.crypto_aead_write.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t]

lib.crypto_eddsa_trim_scalar.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
lib.crypto_eddsa_reduce.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
lib.crypto_eddsa_mul_add.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
lib.crypto_eddsa_scalarbase.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
lib.crypto_eddsa_check_equation.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
lib.crypto_eddsa_check_equation.restype = ctypes.c_int


# Protocol I/O helpers
def read_line():
    line = sys.stdin.readline()
    if not line:
        return None
    return line.rstrip('\r\n: ')

def read_hex_param():
    line = read_line()
    if line is None:
        sys.exit(1)
    return bytes.fromhex(line) if line else b""

def print_hex(b):
    sys.stdout.write(b.hex() + ":\n")
    sys.stdout.flush()

def print_u64_le(v):
    sys.stdout.write(v.to_bytes(8, 'little').hex() + ":\n")
    sys.stdout.flush()

def load64_le(b):
    return int.from_bytes(b, 'little')

def load32_le(b):
    return int.from_bytes(b, 'little')


def main():
    func_name = read_line()
    if not func_name:
        sys.exit(1)

    if func_name == "crypto_verify16":
        a = read_hex_param()
        b = read_hex_param()
        r = lib.crypto_verify16(a, b)
        sys.stdout.write(f"{(r & 0xffffffff):02x}:\n")
    elif func_name == "crypto_verify32":
        a = read_hex_param()
        b = read_hex_param()
        r = lib.crypto_verify32(a, b)
        sys.stdout.write(f"{(r & 0xffffffff):02x}:\n")
    elif func_name == "crypto_verify64":
        a = read_hex_param()
        b = read_hex_param()
        r = lib.crypto_verify64(a, b)
        sys.stdout.write(f"{(r & 0xffffffff):02x}:\n")
    elif func_name == "crypto_wipe":
        data = bytearray(read_hex_param())
        buf = (ctypes.c_uint8 * len(data)).from_buffer(data)
        lib.crypto_wipe(buf, len(data))
        print_hex(bytes(data))
    elif func_name == "crypto_chacha20_h":
        key = read_hex_param()
        inp = read_hex_param()
        out = (ctypes.c_uint8 * 32)()
        lib.crypto_chacha20_h(out, key, inp)
        print_hex(bytes(out))
    elif func_name == "crypto_chacha20_djb":
        key = read_hex_param()
        nonce = read_hex_param()
        plain = read_hex_param()
        ctr_buf = read_hex_param()
        psize = len(plain)
        cipher = (ctypes.c_uint8 * max(1, psize))()
        new_ctr = lib.crypto_chacha20_djb(cipher, plain, psize, key, nonce, load64_le(ctr_buf))
        print_hex(bytes(cipher)[:psize])
        print_u64_le(new_ctr)
    elif func_name == "crypto_chacha20_ietf":
        key = read_hex_param()
        nonce = read_hex_param()
        plain = read_hex_param()
        ctr_buf = read_hex_param()
        psize = len(plain)
        cipher = (ctypes.c_uint8 * max(1, psize))()
        new_ctr = lib.crypto_chacha20_ietf(cipher, plain, psize, key, nonce, load32_le(ctr_buf))
        print_hex(bytes(cipher)[:psize])
        print_hex(new_ctr.to_bytes(4, 'little'))
    elif func_name == "crypto_chacha20_x":
        key = read_hex_param()
        nonce = read_hex_param()
        plain = read_hex_param()
        ctr_buf = read_hex_param()
        psize = len(plain)
        cipher = (ctypes.c_uint8 * max(1, psize))()
        new_ctr = lib.crypto_chacha20_x(cipher, plain, psize, key, nonce, load64_le(ctr_buf))
        print_hex(bytes(cipher)[:psize])
        print_u64_le(new_ctr)
    elif func_name == "crypto_poly1305":
        key = read_hex_param()
        msg = read_hex_param()
        mac = (ctypes.c_uint8 * 16)()
        lib.crypto_poly1305(mac, msg, len(msg), key)
        print_hex(bytes(mac))
    elif func_name == "crypto_aead_lock":
        key = read_hex_param()
        nonce = read_hex_param()
        ad = read_hex_param()
        pt = read_hex_param()
        pt_size = len(pt)
        ct = (ctypes.c_uint8 * max(1, pt_size))()
        mac = (ctypes.c_uint8 * 16)()
        lib.crypto_aead_lock(ct, mac, key, nonce, ad, len(ad), pt, pt_size)
        print_hex(bytes(ct)[:pt_size])
        print_hex(bytes(mac))
    elif func_name == "crypto_aead_unlock":
        key = read_hex_param()
        nonce = read_hex_param()
        ad = read_hex_param()
        ct = read_hex_param()
        mac = read_hex_param()
        ct_size = len(ct)
        pt = (ctypes.c_uint8 * max(1, ct_size))()
        r = lib.crypto_aead_unlock(pt, mac, key, nonce, ad, len(ad), ct, ct_size)
        if r == 0:
            print_hex(bytes(pt)[:ct_size])
        sys.stdout.write(f"{(r & 0xff):02x}:\n")
    elif func_name == "crypto_blake2b":
        msg = read_hex_param()
        h = (ctypes.c_uint8 * 64)()
        lib.crypto_blake2b(h, 64, msg, len(msg))
        print_hex(bytes(h))
    elif func_name == "crypto_blake2b_keyed":
        msg = read_hex_param()
        key = read_hex_param()
        ksize = min(len(key), 64)
        h = (ctypes.c_uint8 * 64)()
        lib.crypto_blake2b_keyed(h, 64, key, ksize, msg, len(msg))
        print_hex(bytes(h))
    elif func_name == "crypto_sha512":
        msg = read_hex_param()
        h = (ctypes.c_uint8 * 64)()
        lib.crypto_sha512(h, msg, len(msg))
        print_hex(bytes(h))
    elif func_name == "crypto_sha512_hmac":
        key = read_hex_param()
        msg = read_hex_param()
        hmac = (ctypes.c_uint8 * 64)()
        lib.crypto_sha512_hmac(hmac, key, len(key), msg, len(msg))
        print_hex(bytes(hmac))
    elif func_name == "crypto_sha512_hkdf":
        ikm = read_hex_param()
        salt = read_hex_param()
        info = read_hex_param()
        line = read_line()
        okm_size = len(line) // 2
        okm = (ctypes.c_uint8 * max(1, okm_size))()
        lib.crypto_sha512_hkdf(okm, okm_size, ikm, len(ikm), salt, len(salt), info, len(info))
        print_hex(bytes(okm)[:okm_size])
    elif func_name == "crypto_argon2":
        algo_b = read_hex_param()
        blocks_b = read_hex_param()
        passes_b = read_hex_param()
        lanes_b = read_hex_param()
        pass_b = read_hex_param()
        salt_b = read_hex_param()
        key_b = read_hex_param()
        ad_b = read_hex_param()
        line = read_line()
        hash_size = len(line) // 2

        config = CryptoArgon2Config(load32_le(algo_b), load32_le(blocks_b), load32_le(passes_b), load32_le(lanes_b))
        inputs = CryptoArgon2Inputs(
            ctypes.cast(pass_b, ctypes.c_void_p) if pass_b else None,
            ctypes.cast(salt_b, ctypes.c_void_p) if salt_b else None,
            len(pass_b),
            len(salt_b)
        )
        extras = CryptoArgon2Extras(
            ctypes.cast(key_b, ctypes.c_void_p) if key_b else None,
            ctypes.cast(ad_b, ctypes.c_void_p) if ad_b else None,
            len(key_b),
            len(ad_b)
        )

        nb_blocks = load32_le(blocks_b)
        work_area = (ctypes.c_uint8 * (nb_blocks * 1024))()
        h = (ctypes.c_uint8 * max(1, hash_size))()
        lib.crypto_argon2(h, hash_size, work_area, config, inputs, extras)
        print_hex(bytes(h)[:hash_size])
    elif func_name == "crypto_x25519":
        sk = read_hex_param()
        pk = read_hex_param()
        shared = (ctypes.c_uint8 * 32)()
        lib.crypto_x25519(shared, sk, pk)
        print_hex(bytes(shared))
    elif func_name == "crypto_x25519_public_key":
        sk = read_hex_param()
        pk = (ctypes.c_uint8 * 32)()
        lib.crypto_x25519_public_key(pk, sk)
        print_hex(bytes(pk))
    elif func_name == "crypto_x25519_inverse":
        sk = read_hex_param()
        pt = read_hex_param()
        blind = (ctypes.c_uint8 * 32)()
        lib.crypto_x25519_inverse(blind, sk, pt)
        print_hex(bytes(blind))
    elif func_name == "crypto_x25519_dirty_small":
        sk = read_hex_param()
        pk = (ctypes.c_uint8 * 32)()
        lib.crypto_x25519_dirty_small(pk, sk)
        print_hex(bytes(pk))
    elif func_name == "crypto_x25519_dirty_fast":
        sk = read_hex_param()
        pk = (ctypes.c_uint8 * 32)()
        lib.crypto_x25519_dirty_fast(pk, sk)
        print_hex(bytes(pk))
    elif func_name == "crypto_eddsa_key_pair":
        seed = read_hex_param()
        sk = (ctypes.c_uint8 * 64)()
        pk = (ctypes.c_uint8 * 32)()
        lib.crypto_eddsa_key_pair(sk, pk, seed)
        print_hex(bytes(sk))
        print_hex(bytes(pk))
    elif func_name == "crypto_eddsa_sign":
        sk = read_hex_param()
        pk = read_hex_param()
        msg = read_hex_param()
        fat_sk = sk[:32] + pk[:32]
        sig = (ctypes.c_uint8 * 64)()
        lib.crypto_eddsa_sign(sig, fat_sk, msg, len(msg))
        print_hex(bytes(sig))
    elif func_name == "crypto_eddsa_check":
        sig = read_hex_param()
        pk = read_hex_param()
        msg = read_hex_param()
        r = lib.crypto_eddsa_check(sig, pk, msg, len(msg))
        sys.stdout.write(f"{(r & 0xff):02x}:\n")
    elif func_name == "crypto_ed25519_key_pair":
        seed = read_hex_param()
        sk = (ctypes.c_uint8 * 64)()
        pk = (ctypes.c_uint8 * 32)()
        lib.crypto_ed25519_key_pair(sk, pk, seed)
        print_hex(bytes(sk))
        print_hex(bytes(pk))
    elif func_name == "crypto_ed25519_sign":
        sk = read_hex_param()
        pk = read_hex_param()
        msg = read_hex_param()
        fat_sk = sk[:32] + pk[:32]
        sig = (ctypes.c_uint8 * 64)()
        lib.crypto_ed25519_sign(sig, fat_sk, msg, len(msg))
        print_hex(bytes(sig))
    elif func_name == "crypto_ed25519_check":
        sig = read_hex_param()
        pk = read_hex_param()
        msg = read_hex_param()
        r = lib.crypto_ed25519_check(sig, pk, msg, len(msg))
        sys.stdout.write(f"{(r & 0xff):02x}:\n")
    elif func_name == "crypto_ed25519_ph_sign":
        sk = read_hex_param()
        pk = read_hex_param()
        h = read_hex_param()
        fat_sk = sk[:32] + pk[:32]
        sig = (ctypes.c_uint8 * 64)()
        lib.crypto_ed25519_ph_sign(sig, fat_sk, h)
        print_hex(bytes(sig))
    elif func_name == "crypto_ed25519_ph_check":
        sig = read_hex_param()
        pk = read_hex_param()
        h = read_hex_param()
        r = lib.crypto_ed25519_ph_check(sig, pk, h)
        sys.stdout.write(f"{(r & 0xff):02x}:\n")
    elif func_name == "crypto_elligator_map":
        hidden = read_hex_param()
        curve = (ctypes.c_uint8 * 32)()
        lib.crypto_elligator_map(curve, hidden)
        print_hex(bytes(curve))
    elif func_name == "crypto_elligator_rev":
        point = read_hex_param()
        line = read_line()
        tweak = int(line, 16) & 0xff if line else 0
        hidden = (ctypes.c_uint8 * 32)()
        r = lib.crypto_elligator_rev(hidden, point, tweak)
        if r == 0:
            print_hex(bytes(hidden))
        sys.stdout.write(f"{(r & 0xff):02x}:\n")
    elif func_name == "crypto_elligator_key_pair":
        seed = read_hex_param()
        r_buf = (ctypes.c_uint8 * 32)()
        sk = (ctypes.c_uint8 * 32)()
        lib.crypto_elligator_key_pair(r_buf, sk, seed)
        print_hex(bytes(r_buf))
        print_hex(bytes(sk))
    elif func_name == "crypto_eddsa_to_x25519":
        eddsa = read_hex_param()
        x25519 = (ctypes.c_uint8 * 32)()
        lib.crypto_eddsa_to_x25519(x25519, eddsa)
        print_hex(bytes(x25519))
    elif func_name == "crypto_x25519_to_eddsa":
        x = read_hex_param()
        ed = (ctypes.c_uint8 * 32)()
        lib.crypto_x25519_to_eddsa(ed, x)
        print_hex(bytes(ed))
    elif func_name == "crypto_aead_init_x":
        key = read_hex_param()
        nonce = read_hex_param()
        ctx = CryptoAeadCtx()
        lib.crypto_aead_init_x(ctypes.byref(ctx), key, nonce)
        print_hex(bytes(ctx))
    elif func_name == "crypto_aead_init_djb":
        key = read_hex_param()
        nonce = read_hex_param()
        ctx = CryptoAeadCtx()
        lib.crypto_aead_init_djb(ctypes.byref(ctx), key, nonce)
        print_hex(bytes(ctx))
    elif func_name == "crypto_aead_init_ietf":
        key = read_hex_param()
        nonce = read_hex_param()
        ctx = CryptoAeadCtx()
        lib.crypto_aead_init_ietf(ctypes.byref(ctx), key, nonce)
        print_hex(bytes(ctx))
    elif func_name == "crypto_aead_write":
        key = read_hex_param()
        nonce = read_hex_param()
        ad = read_hex_param()
        pt = read_hex_param()
        pt_size = len(pt)
        ctx = CryptoAeadCtx()
        lib.crypto_aead_init_ietf(ctypes.byref(ctx), key, nonce)
        ct = (ctypes.c_uint8 * max(1, pt_size))()
        mac = (ctypes.c_uint8 * 16)()
        lib.crypto_aead_write(ctypes.byref(ctx), ct, mac, ad, len(ad), pt, pt_size)
        print_hex(bytes(ct)[:pt_size])
        print_hex(bytes(mac))
    elif func_name == "crypto_eddsa_trim_scalar":
        inp = read_hex_param()
        out = (ctypes.c_uint8 * 32)()
        lib.crypto_eddsa_trim_scalar(out, inp)
        print_hex(bytes(out))
    elif func_name == "crypto_eddsa_reduce":
        exp = read_hex_param()
        red = (ctypes.c_uint8 * 32)()
        lib.crypto_eddsa_reduce(red, exp)
        print_hex(bytes(red))
    elif func_name == "crypto_eddsa_mul_add":
        a = read_hex_param()
        b = read_hex_param()
        c = read_hex_param()
        r = (ctypes.c_uint8 * 32)()
        lib.crypto_eddsa_mul_add(r, a, b, c)
        print_hex(bytes(r))
    elif func_name == "crypto_eddsa_scalarbase":
        scalar = read_hex_param()
        point = (ctypes.c_uint8 * 32)()
        lib.crypto_eddsa_scalarbase(point, scalar)
        print_hex(bytes(point))
    elif func_name == "crypto_eddsa_check_equation":
        sig = read_hex_param()
        pk = read_hex_param()
        hram = read_hex_param()
        r = lib.crypto_eddsa_check_equation(sig, pk, hram)
        sys.stdout.write(f"{(r & 0xff):02x}:\n")
    else:
        sys.stderr.write(f"unknown function: {func_name}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
