#!/usr/bin/env python3
"""
picoc - A C interpreter in Python 3.
Ported and enhanced for reLang test suite.
"""

import sys
import os
import re
import math
import ctypes

PICOC_VERSION = "v2.1"

LICENSE_TEXT = """\
picoc header file - this has all the main data structures and function prototypes.
Copyright (C) 2009-2011 Zack Smith, Kirk Baucom
License: New BSD License
"""

HELP_TEXT = """picoc v2.1  
Format:

> picoc <file1.c>... [- <arg1>...]    : run a program, calls main() as the entry point
> picoc -s <file1.c>... [- <arg1>...] : run a script, runs the program without calling main()
> picoc -i                            : interactive mode, Ctrl+d to exit
> picoc -c                            : copyright info
> picoc -h                            : this help message
"""

# =====================================================================
# Preprocessor
# =====================================================================

def preprocess(code):
    defines = {
        'NULL': '0',
        'TRUE': '1',
        'FALSE': '0',
        'true': '1',
        'false': '0',
        'PICOC_VERSION': f'"{PICOC_VERSION}"'
    }
    lines = code.split("\n")
    output = []
    # Stack elements: [active, outer_active, matched]
    cond_stack = []

    def is_active():
        return all(c[0] for c in cond_stack)

    def eval_expr(expr):
        tokens = expr.split()
        new_tokens = []
        for t in tokens:
            if t == "defined":
                new_tokens.append(t)
            elif t in defines:
                new_tokens.append(str(defines[t]))
            elif t.isidentifier():
                new_tokens.append("0")
            else:
                new_tokens.append(t)
        s = " ".join(new_tokens)
        s = s.replace("&&", " and ").replace("||", " or ").replace("!", " not ")
        # Handle defined(VAR)
        s = re.sub(r'defined\s*\(\s*([a-zA-Z_]\w*)\s*\)', lambda m: "1" if m.group(1) in defines else "0", s)
        s = re.sub(r'defined\s+([a-zA-Z_]\w*)', lambda m: "1" if m.group(1) in defines else "0", s)
        try:
            return bool(eval(s))
        except Exception:
            return False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            parts = stripped.split(None, 1)
            cmd = parts[0]
            rest = parts[1] if len(parts) > 1 else ""

            if cmd == "#define":
                if is_active():
                    m_parts = rest.split(None, 1)
                    if m_parts:
                        m_name = m_parts[0]
                        m_val = m_parts[1] if len(m_parts) > 1 else "1"
                        defines[m_name] = m_val
                output.append("")
            elif cmd == "#undef":
                if is_active():
                    defines.pop(rest.strip(), None)
                output.append("")
            elif cmd == "#ifdef":
                outer = is_active()
                m_name = rest.strip()
                cond = (m_name in defines)
                act = outer and cond
                cond_stack.append([act, outer, cond])
                output.append("")
            elif cmd == "#ifndef":
                outer = is_active()
                m_name = rest.strip()
                cond = (m_name not in defines)
                act = outer and cond
                cond_stack.append([act, outer, cond])
                output.append("")
            elif cmd == "#if":
                outer = is_active()
                cond = eval_expr(rest)
                act = outer and cond
                cond_stack.append([act, outer, cond])
                output.append("")
            elif cmd == "#elif":
                if cond_stack:
                    act, outer, matched = cond_stack[-1]
                    if not matched and outer:
                        cond = eval_expr(rest)
                        cond_stack[-1] = [cond, outer, matched or cond]
                    else:
                        cond_stack[-1] = [False, outer, matched]
                output.append("")
            elif cmd == "#else":
                if cond_stack:
                    act, outer, matched = cond_stack[-1]
                    if not matched and outer:
                        cond_stack[-1] = [True, outer, True]
                    else:
                        cond_stack[-1] = [False, outer, matched]
                output.append("")
            elif cmd == "#endif":
                if cond_stack:
                    cond_stack.pop()
                output.append("")
            else:
                output.append("")
        else:
            if is_active():
                output.append(line)
            else:
                output.append("")

    return "\n".join(output), defines


# =====================================================================
# Lexer / Tokenizer
# =====================================================================

TOKEN_TYPES = [
    ('COMMENT_MULTI', r'/\*[\s\S]*?\*/'),
    ('COMMENT_SINGLE', r'//.*'),
    ('STRING', r'"(?:\\.|[^"\\])*"'),
    ('CHAR', r"'(?:\\.|[^'\\])'"),
    ('FLOAT_CONST', r'\b\d+\.\d*(?:[eE][+-]?\d+)?[fF]?\b|\b\d+[eE][+-]?\d+[fF]?\b'),
    ('INT_HEX', r'\b0[xX][0-9a-fA-F]+[uUlL]*\b'),
    ('INT_OCT', r'\b0[0-7]+[uUlL]*\b'),
    ('INT_DEC', r'\b\d+[uUlL]*\b'),
    ('ARROW', r'->'),
    ('INC', r'\+\+'),
    ('DEC', r'--'),
    ('SHL_ASSIGN', r'<<='),
    ('SHR_ASSIGN', r'>>='),
    ('ADD_ASSIGN', r'\+='),
    ('SUB_ASSIGN', r'-='),
    ('MUL_ASSIGN', r'\*='),
    ('DIV_ASSIGN', r'/='),
    ('MOD_ASSIGN', r'%='),
    ('AND_ASSIGN', r'&='),
    ('OR_ASSIGN', r'\|='),
    ('XOR_ASSIGN', r'\^='),
    ('EQ', r'=='),
    ('NE', r'!='),
    ('LE', r'<='),
    ('GE', r'>='),
    ('SHL', r'<<'),
    ('SHR', r'>>'),
    ('LOG_AND', r'&&'),
    ('LOG_OR', r'\|\|'),
    ('ELLIPSIS', r'\.\.\.'),
    ('ASSIGN', r'='),
    ('PLUS', r'\+'),
    ('MINUS', r'-'),
    ('MUL', r'\*'),
    ('DIV', r'/'),
    ('MOD', r'%'),
    ('LT', r'<'),
    ('GT', r'>'),
    ('NOT', r'!'),
    ('BIT_AND', r'&'),
    ('BIT_OR', r'\|'),
    ('BIT_XOR', r'\^'),
    ('BIT_NOT', r'~'),
    ('QUESTION', r'\?'),
    ('COLON', r':'),
    ('DOT', r'\.'),
    ('COMMA', r','),
    ('SEMICOLON', r';'),
    ('LPAREN', r'\('),
    ('RPAREN', r'\)'),
    ('LBRACKET', r'\['),
    ('RBRACKET', r'\]'),
    ('LBRACE', r'\{'),
    ('RBRACE', r'\}'),
    ('IDENTIFIER', r'[a-zA-Z_]\w*'),
    ('NEWLINE', r'\n'),
    ('SKIP', r'[ \t\r]+'),
    ('MISMATCH', r'.'),
]

KEYWORDS = {
    'int', 'char', 'float', 'double', 'void', 'short', 'long', 'unsigned', 'signed',
    'struct', 'union', 'enum', 'typedef', 'sizeof', 'static', 'const', 'extern',
    'if', 'else', 'while', 'do', 'for', 'switch', 'case', 'default',
    'break', 'continue', 'return', 'goto'
}


class Token:
    def __init__(self, type_, value, line, col):
        self.type = type_
        self.value = value
        self.line = line
        self.col = col

    def __repr__(self):
        return f"Token({self.type}, {self.value!r}, L{self.line})"


def lex(code, filename="<input>", defines=None):
    if defines is None:
        defines = {}
    master_re = re.compile('|'.join(f'(?P<{pair[0]}>{pair[1]})' for pair in TOKEN_TYPES))
    line_num = 1
    line_start = 0
    tokens = []

    for mo in master_re.finditer(code):
        kind = mo.lastgroup
        val = mo.group()
        col = mo.start() - line_start

        if kind in ('COMMENT_MULTI', 'COMMENT_SINGLE'):
            line_num += val.count('\n')
            if '\n' in val:
                line_start = mo.start() + val.rfind('\n') + 1
            continue
        elif kind == 'NEWLINE':
            line_num += 1
            line_start = mo.end()
            continue
        elif kind == 'SKIP':
            continue
        elif kind == 'IDENTIFIER':
            if val in KEYWORDS:
                tokens.append(Token(val.upper(), val, line_num, col))
            elif val in defines:
                def_val = str(defines[val])
                exp_tokens = lex(def_val, filename, {})
                tokens.extend([t for t in exp_tokens if t.type != 'EOF'])
            else:
                tokens.append(Token('IDENTIFIER', val, line_num, col))
        elif kind == 'MISMATCH':
            tokens.append(Token('MISMATCH', val, line_num, col))
        else:
            tokens.append(Token(kind, val, line_num, col))

    tokens.append(Token('EOF', '', line_num, 0))
    return tokens


# =====================================================================
# C Type & Memory System
# =====================================================================

class CType:
    def __init__(self, kind, name="", size=4, base_type=None, fields=None, is_unsigned=False, align=4):
        self.kind = kind  # 'int', 'char', 'float', 'double', 'void', 'pointer', 'array', 'struct', 'union', 'enum'
        self.name = name
        self.size = size
        self.base_type = base_type
        self.fields = fields if fields else {}  # field_name -> (offset, CType)
        self.is_unsigned = is_unsigned
        self.align = align

    def __repr__(self):
        if self.kind == 'pointer':
            return f"{self.base_type}*"
        if self.kind == 'array':
            return f"{self.base_type}[{self.size}]"
        return self.name or self.kind


TYPE_INT = CType('int', 'int', size=4, align=4)
TYPE_CHAR = CType('char', 'char', size=1, align=1)
TYPE_SHORT = CType('int', 'short', size=2, align=2)
TYPE_LONG = CType('int', 'long', size=8, align=8)
TYPE_FLOAT = CType('float', 'float', size=4, align=4)
TYPE_DOUBLE = CType('double', 'double', size=8, align=8)
TYPE_VOID = CType('void', 'void', size=1, align=1)

MEMORY = bytearray(2000000)  # 2MB heap/stack arena
FREE_PTR = 1000  # Reserve null pointer page (0..999)


def align_up(offset, align):
    if align <= 1:
        return offset
    return (offset + align - 1) & ~(align - 1)


def get_type_align(ctype):
    if not ctype:
        return 4
    if ctype.kind in ('char', 'void'):
        return 1
    elif ctype.kind == 'short':
        return 2
    elif ctype.kind in ('int', 'float', 'enum', 'pointer'):
        return 4
    elif ctype.kind in ('double', 'long'):
        return 8
    elif ctype.kind in ('struct', 'union'):
        return ctype.align
    elif ctype.kind == 'array':
        return get_type_align(ctype.base_type)
    return 4


def alloc_mem(size):
    global FREE_PTR
    ptr = FREE_PTR
    size = max(1, size)
    FREE_PTR = align_up(FREE_PTR + size, 8)
    return ptr


class CPointer:
    def __init__(self, address, target_type):
        self.address = address if isinstance(address, int) else (address.address if isinstance(address, CPointer) else 0)
        self.target_type = target_type or TYPE_INT

    def __repr__(self):
        return f"CPointer({hex(self.address)}, {self.target_type})"

    def __eq__(self, other):
        if isinstance(other, CPointer):
            return self.address == other.address
        if isinstance(other, int):
            return self.address == other
        return False

    def __ne__(self, other):
        return not (self == other)


# Memory Read/Write helpers
def read_mem(addr, ctype):
    if isinstance(addr, CPointer):
        addr = addr.address

    if ctype.kind == 'pointer':
        val = int.from_bytes(MEMORY[addr:addr+8], byteorder='little', signed=False)
        return CPointer(val, ctype.base_type)
    elif ctype.kind == 'int':
        val = int.from_bytes(MEMORY[addr:addr+ctype.size], byteorder='little', signed=not ctype.is_unsigned)
        return val
    elif ctype.kind == 'char':
        val = int.from_bytes(MEMORY[addr:addr+1], byteorder='little', signed=not ctype.is_unsigned)
        return val
    elif ctype.kind in ('float', 'double'):
        if ctype.size == 4:
            return ctypes.c_float.from_buffer(MEMORY, addr).value
        else:
            return ctypes.c_double.from_buffer(MEMORY, addr).value
    elif ctype.kind in ('struct', 'union', 'array'):
        return CPointer(addr, ctype.base_type if ctype.kind == 'array' else ctype)
    return 0


def write_mem(addr, ctype, val):
    if isinstance(addr, CPointer):
        addr = addr.address

    if ctype.kind == 'pointer':
        target_addr = val.address if isinstance(val, CPointer) else int(val)
        MEMORY[addr:addr+8] = target_addr.to_bytes(8, byteorder='little', signed=False)
    elif ctype.kind in ('int', 'char'):
        try:
            ival = val.address if isinstance(val, CPointer) else int(val)
        except Exception:
            ival = 0
        sz = ctype.size
        mask = (1 << (sz * 8)) - 1
        ival = ival & mask
        MEMORY[addr:addr+sz] = ival.to_bytes(sz, byteorder='little', signed=False)
    elif ctype.kind in ('float', 'double'):
        fval = float(val)
        if ctype.size == 4:
            cobj = ctypes.c_float(fval)
        else:
            cobj = ctypes.c_double(fval)
        raw = bytes(cobj)
        MEMORY[addr:addr+len(raw)] = raw
    elif ctype.kind in ('struct', 'union'):
        if isinstance(val, CPointer):
            src_addr = val.address
            MEMORY[addr:addr+ctype.size] = MEMORY[src_addr:src_addr+ctype.size]


def read_string(addr):
    if isinstance(addr, CPointer):
        addr = addr.address
    chars = []
    curr = addr
    while curr < len(MEMORY) and MEMORY[curr] != 0:
        chars.append(chr(MEMORY[curr]))
        curr += 1
    return "".join(chars)


def write_string(s):
    encoded = s.encode('utf-8') + b'\x00'
    addr = alloc_mem(len(encoded))
    MEMORY[addr:addr+len(encoded)] = encoded
    return addr


def write_string_at(addr, s):
    if isinstance(addr, CPointer):
        addr = addr.address
    encoded = s.encode('utf-8') + b'\x00'
    MEMORY[addr:addr+len(encoded)] = encoded


# =====================================================================
# AST Nodes
# =====================================================================

class ASTNode:
    pass

class ProgramNode(ASTNode):
    def __init__(self, decls):
        self.decls = decls

class VarDeclNode(ASTNode):
    def __init__(self, ctype, name, init_expr=None, is_static=False):
        self.ctype = ctype
        self.name = name
        self.init_expr = init_expr
        self.is_static = is_static

class VarDeclListNode(ASTNode):
    def __init__(self, decls):
        self.decls = decls

class StructDeclNode(ASTNode):
    def __init__(self, name, fields):
        self.name = name
        self.fields = fields

class FuncDeclNode(ASTNode):
    def __init__(self, return_type, name, params, body, is_intrinsic=False):
        self.return_type = return_type
        self.name = name
        self.params = params  # list of (ctype, name)
        self.body = body
        self.is_intrinsic = is_intrinsic

class BlockNode(ASTNode):
    def __init__(self, stmts):
        self.stmts = stmts

class IfNode(ASTNode):
    def __init__(self, cond, then_branch, else_branch=None):
        self.cond = cond
        self.then_branch = then_branch
        self.else_branch = else_branch

class WhileNode(ASTNode):
    def __init__(self, cond, body):
        self.cond = cond
        self.body = body

class DoWhileNode(ASTNode):
    def __init__(self, body, cond):
        self.body = body
        self.cond = cond

class ForNode(ASTNode):
    def __init__(self, init, cond, incr, body):
        self.init = init
        self.cond = cond
        self.incr = incr
        self.body = body

class SwitchNode(ASTNode):
    def __init__(self, expr, cases, default_branch=None):
        self.expr = expr
        self.cases = cases  # list of (val, body_stmts)
        self.default_branch = default_branch

class BreakNode(ASTNode):
    pass

class ContinueNode(ASTNode):
    pass

class ReturnNode(ASTNode):
    def __init__(self, expr=None):
        self.expr = expr

class GotoNode(ASTNode):
    def __init__(self, label):
        self.label = label

class LabelNode(ASTNode):
    def __init__(self, label, stmt=None):
        self.label = label
        self.stmt = stmt

class ExprStmtNode(ASTNode):
    def __init__(self, expr):
        self.expr = expr

class AssignNode(ASTNode):
    def __init__(self, target, op, expr):
        self.target = target
        self.op = op
        self.expr = expr

class BinaryOpNode(ASTNode):
    def __init__(self, left, op, right):
        self.left = left
        self.op = op
        self.right = right

class UnaryOpNode(ASTNode):
    def __init__(self, op, expr, is_postfix=False, target_type=None):
        self.op = op
        self.expr = expr
        self.is_postfix = is_postfix
        self.target_type = target_type

class TernaryNode(ASTNode):
    def __init__(self, cond, true_expr, false_expr):
        self.cond = cond
        self.true_expr = true_expr
        self.false_expr = false_expr

class CallNode(ASTNode):
    def __init__(self, callee, args):
        self.callee = callee
        self.args = args

class MemberAccessNode(ASTNode):
    def __init__(self, target, member, is_arrow=False):
        self.target = target
        self.member = member
        self.is_arrow = is_arrow

class IndexAccessNode(ASTNode):
    def __init__(self, target, index):
        self.target = target
        self.index = index

class VarNode(ASTNode):
    def __init__(self, name):
        self.name = name

class ConstantNode(ASTNode):
    def __init__(self, value, ctype):
        self.value = value
        self.ctype = ctype

class SizeofNode(ASTNode):
    def __init__(self, target):
        self.target = target

class InitializerListNode(ASTNode):
    def __init__(self, elems):
        self.elems = elems


# =====================================================================
# Parser
# =====================================================================

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.typedefs = {}
        self.struct_types = {}
        self.union_types = {}
        self.enum_constants = {}

    def peek(self, offset=0):
        if self.pos + offset < len(self.tokens):
            return self.tokens[self.pos + offset]
        return self.tokens[-1]

    def match(self, *types):
        t = self.peek()
        if t.type in types:
            self.pos += 1
            return t
        return None

    def expect(self, type_):
        t = self.match(type_)
        if not t:
            curr = self.peek()
            raise SyntaxError(f"Expected token {type_}, got {curr.type} ({curr.value!r}) at L{curr.line}")
        return t

    def parse_program(self):
        decls = []
        while self.peek().type != 'EOF':
            decl = self.parse_external_declaration()
            if decl:
                if isinstance(decl, list):
                    decls.extend(decl)
                elif isinstance(decl, VarDeclListNode):
                    decls.extend(decl.decls)
                else:
                    decls.append(decl)
        return ProgramNode(decls)

    def parse_type_specifier(self):
        is_static = bool(self.match('STATIC'))
        self.match('CONST', 'EXTERN')

        is_unsigned = bool(self.match('UNSIGNED'))
        if not is_unsigned:
            self.match('SIGNED')

        t = self.peek()

        if t.type == 'INT':
            self.pos += 1
            return CType('int', 'int', size=4, is_unsigned=is_unsigned, align=4)
        elif t.type == 'CHAR':
            self.pos += 1
            return CType('char', 'char', size=1, is_unsigned=is_unsigned, align=1)
        elif t.type == 'FLOAT':
            self.pos += 1
            return TYPE_FLOAT
        elif t.type == 'DOUBLE':
            self.pos += 1
            return TYPE_DOUBLE
        elif t.type == 'VOID':
            self.pos += 1
            return TYPE_VOID
        elif t.type == 'SHORT':
            self.pos += 1
            self.match('INT')
            return CType('int', 'short', size=2, is_unsigned=is_unsigned, align=2)
        elif t.type == 'LONG':
            self.pos += 1
            self.match('INT')
            return CType('int', 'long', size=8, is_unsigned=is_unsigned, align=8)
        elif t.type == 'ENUM':
            self.pos += 1
            e_name = ""
            if self.peek().type == 'IDENTIFIER':
                e_name = self.expect('IDENTIFIER').value
            if self.match('LBRACE'):
                curr_val = 0
                while not self.match('RBRACE') and self.peek().type != 'EOF':
                    item_name = self.expect('IDENTIFIER').value
                    if self.match('ASSIGN'):
                        curr_val = int(self.parse_expression().value)
                    self.enum_constants[item_name] = curr_val
                    curr_val += 1
                    self.match('COMMA')
            return TYPE_INT
        elif t.type in ('STRUCT', 'UNION'):
            is_union = (t.type == 'UNION')
            self.pos += 1
            s_name = ""
            if self.peek().type == 'IDENTIFIER':
                s_name = self.expect('IDENTIFIER').value
            fields = {}
            if self.match('LBRACE'):
                offset = 0
                max_align = 1
                max_size = 0
                while not self.match('RBRACE') and self.peek().type != 'EOF':
                    f_type = self.parse_type_specifier()
                    if not f_type: continue
                    while True:
                        f_full_type, f_name = self.parse_declarator(f_type)
                        f_align = get_type_align(f_full_type)
                        max_align = max(max_align, f_align)

                        if is_union:
                            field_offset = 0
                            max_size = max(max_size, f_full_type.size)
                        else:
                            offset = align_up(offset, f_align)
                            field_offset = offset
                            offset += f_full_type.size

                        fields[f_name] = (field_offset, f_full_type)
                        if not self.match('COMMA'):
                            break
                    self.match('SEMICOLON')

                final_size = max_size if is_union else align_up(offset, max_align)
                kind = 'union' if is_union else 'struct'
                st = CType(kind, name=s_name, size=final_size, fields=fields, align=max_align)
                if s_name:
                    if is_union: self.union_types[s_name] = st
                    else: self.struct_types[s_name] = st
                return st
            elif s_name:
                type_dict = self.union_types if is_union else self.struct_types
                if s_name in type_dict:
                    return type_dict[s_name]
                return CType('union' if is_union else 'struct', name=s_name, size=8, fields={}, align=4)
        elif t.type == 'IDENTIFIER' and t.value in self.typedefs:
            self.pos += 1
            return self.typedefs[t.value]

        if is_unsigned:
            return CType('int', 'unsigned int', size=4, is_unsigned=True, align=4)

        return None

    def parse_declarator(self, base_type):
        curr_type = base_type
        while self.match('MUL'):
            curr_type = CType('pointer', size=8, base_type=curr_type, align=8)

        if self.peek().type == 'LPAREN':
            # Function pointer or parenthesized declarator
            self.pos += 1
            if self.match('MUL'):
                name = self.expect('IDENTIFIER').value
                self.expect('RPAREN')
                curr_type = CType('pointer', size=8, base_type=curr_type, align=8)
                return curr_type, name
            self.pos -= 1

        if self.peek().type != 'IDENTIFIER':
            return curr_type, ""

        name = self.expect('IDENTIFIER').value

        # Array suffixes (e.g. arr[2][3])
        arr_dims = []
        while self.match('LBRACKET'):
            if self.peek().type != 'RBRACKET':
                sz_expr = self.parse_expression()
                sz = int(getattr(sz_expr, 'value', 0))
            else:
                sz = 0  # Incomplete array type arr[]
            self.expect('RBRACKET')
            arr_dims.append(sz)

        for sz in reversed(arr_dims):
            curr_type = CType('array', size=sz * curr_type.size if sz > 0 else 0, base_type=curr_type, align=get_type_align(curr_type))

        return curr_type, name

    def parse_external_declaration(self):
        if self.match('TYPEDEF'):
            b_type = self.parse_type_specifier()
            full_type, name = self.parse_declarator(b_type)
            self.expect('SEMICOLON')
            self.typedefs[name] = full_type
            return None

        is_static = bool(self.match('STATIC'))
        b_type = self.parse_type_specifier()
        if not b_type:
            if self.match('SEMICOLON'):
                return None
            self.pos += 1
            return None

        if self.peek().type == 'SEMICOLON':
            self.pos += 1
            return StructDeclNode(b_type.name, b_type.fields) if b_type.kind in ('struct', 'union') else None

        full_type, name = self.parse_declarator(b_type)

        # Function definition or declaration
        if self.match('LPAREN'):
            params = []
            if not self.match('RPAREN'):
                while True:
                    p_base = self.parse_type_specifier()
                    if p_base:
                        p_type, p_name = self.parse_declarator(p_base)
                        # Array param decays to pointer
                        if p_type.kind == 'array':
                            p_type = CType('pointer', size=8, base_type=p_type.base_type, align=8)
                        params.append((p_type, p_name))
                    if not self.match('COMMA'):
                        break
                self.expect('RPAREN')

            if self.peek().type == 'LBRACE':
                body = self.parse_block()
                return FuncDeclNode(full_type, name, params, body)
            else:
                self.expect('SEMICOLON')
                return FuncDeclNode(full_type, name, params, None)

        # Variable declaration(s)
        decls = self.parse_var_decl_tail(b_type, full_type, name, is_static)
        return decls

    def parse_var_decl_tail(self, b_type, first_type, first_name, is_static=False):
        init_expr = None
        if self.match('ASSIGN'):
            init_expr = self.parse_initializer()
            if first_type.kind == 'array' and first_type.size == 0 and isinstance(init_expr, InitializerListNode):
                first_type.size = len(init_expr.elems) * first_type.base_type.size

        decls = [VarDeclNode(first_type, first_name, init_expr, is_static=is_static)]

        while self.match('COMMA'):
            f_type, f_name = self.parse_declarator(b_type)
            f_init = None
            if self.match('ASSIGN'):
                f_init = self.parse_initializer()
                if f_type.kind == 'array' and f_type.size == 0 and isinstance(f_init, InitializerListNode):
                    f_type.size = len(f_init.elems) * f_type.base_type.size
            decls.append(VarDeclNode(f_type, f_name, f_init, is_static=is_static))

        self.expect('SEMICOLON')
        return VarDeclListNode(decls)

    def parse_initializer(self):
        if self.match('LBRACE'):
            elems = []
            if not self.match('RBRACE'):
                while True:
                    elems.append(self.parse_initializer())
                    if not self.match('COMMA'):
                        break
                self.expect('RBRACE')
            return InitializerListNode(elems)
        return self.parse_expression()

    def parse_statement(self):
        t = self.peek()

        if t.type == 'LBRACE':
            return self.parse_block()
        elif t.type == 'IF':
            self.pos += 1
            self.expect('LPAREN')
            cond = self.parse_expression()
            self.expect('RPAREN')
            then_branch = self.parse_statement()
            else_branch = None
            if self.match('ELSE'):
                else_branch = self.parse_statement()
            return IfNode(cond, then_branch, else_branch)
        elif t.type == 'WHILE':
            self.pos += 1
            self.expect('LPAREN')
            cond = self.parse_expression()
            self.expect('RPAREN')
            body = self.parse_statement()
            return WhileNode(cond, body)
        elif t.type == 'DO':
            self.pos += 1
            body = self.parse_statement()
            self.expect('WHILE')
            self.expect('LPAREN')
            cond = self.parse_expression()
            self.expect('RPAREN')
            self.expect('SEMICOLON')
            return DoWhileNode(body, cond)
        elif t.type == 'FOR':
            self.pos += 1
            self.expect('LPAREN')
            init = None
            if self.peek().type != 'SEMICOLON':
                b_type = self.parse_type_specifier()
                if b_type:
                    f_type, f_name = self.parse_declarator(b_type)
                    init = self.parse_var_decl_tail(b_type, f_type, f_name)
                else:
                    init = self.parse_expression()
                    self.expect('SEMICOLON')
            else:
                self.expect('SEMICOLON')

            cond = self.parse_expression() if self.peek().type != 'SEMICOLON' else ConstantNode(1, TYPE_INT)
            self.expect('SEMICOLON')
            incr = self.parse_expression() if self.peek().type != 'RPAREN' else None
            self.expect('RPAREN')
            body = self.parse_statement()
            return ForNode(init, cond, incr, body)
        elif t.type == 'SWITCH':
            self.pos += 1
            self.expect('LPAREN')
            expr = self.parse_expression()
            self.expect('RPAREN')
            self.expect('LBRACE')
            cases = []
            def_branch = None
            while not self.match('RBRACE') and self.peek().type != 'EOF':
                if self.match('CASE'):
                    val_node = self.parse_expression()
                    self.expect('COLON')
                    case_stmts = []
                    while self.peek().type not in ('CASE', 'DEFAULT', 'RBRACE'):
                        case_stmts.append(self.parse_statement())
                    cases.append((val_node, case_stmts))
                elif self.match('DEFAULT'):
                    self.expect('COLON')
                    def_stmts = []
                    while self.peek().type not in ('CASE', 'DEFAULT', 'RBRACE'):
                        def_stmts.append(self.parse_statement())
                    def_branch = def_stmts
            return SwitchNode(expr, cases, def_branch)
        elif t.type == 'GOTO':
            self.pos += 1
            label = self.expect('IDENTIFIER').value
            self.expect('SEMICOLON')
            return GotoNode(label)
        elif t.type == 'BREAK':
            self.pos += 1
            self.expect('SEMICOLON')
            return BreakNode()
        elif t.type == 'CONTINUE':
            self.pos += 1
            self.expect('SEMICOLON')
            return ContinueNode()
        elif t.type == 'RETURN':
            self.pos += 1
            expr = None
            if self.peek().type != 'SEMICOLON':
                expr = self.parse_expression()
            self.expect('SEMICOLON')
            return ReturnNode(expr)
        else:
            # Check for label (IDENTIFIER COLON)
            if t.type == 'IDENTIFIER' and self.peek(1).type == 'COLON':
                lbl_name = t.value
                self.pos += 2
                stmt = self.parse_statement() if self.peek().type not in ('RBRACE', 'EOF') else None
                return LabelNode(lbl_name, stmt)

            # Check for local var decl
            is_static = bool(self.match('STATIC'))
            b_type = self.parse_type_specifier()
            if b_type:
                full_type, name = self.parse_declarator(b_type)
                return self.parse_var_decl_tail(b_type, full_type, name, is_static=is_static)

            if self.match('SEMICOLON'):
                return ExprStmtNode(None)

            expr = self.parse_expression()
            self.expect('SEMICOLON')
            return ExprStmtNode(expr)

    def parse_block(self):
        self.expect('LBRACE')
        stmts = []
        while not self.match('RBRACE') and self.peek().type != 'EOF':
            s = self.parse_statement()
            if s:
                if isinstance(s, VarDeclListNode):
                    stmts.extend(s.decls)
                else:
                    stmts.append(s)
        return BlockNode(stmts)

    def parse_expression(self):
        return self.parse_assignment()

    def parse_assignment(self):
        node = self.parse_ternary()
        t = self.peek()
        assign_ops = ['ASSIGN', 'ADD_ASSIGN', 'SUB_ASSIGN', 'MUL_ASSIGN', 'DIV_ASSIGN', 'MOD_ASSIGN',
                      'AND_ASSIGN', 'OR_ASSIGN', 'XOR_ASSIGN', 'SHL_ASSIGN', 'SHR_ASSIGN']
        if t.type in assign_ops:
            self.pos += 1
            expr = self.parse_assignment()
            return AssignNode(node, t.type, expr)
        return node

    def parse_ternary(self):
        node = self.parse_logical_or()
        if self.match('QUESTION'):
            true_expr = self.parse_expression()
            self.expect('COLON')
            false_expr = self.parse_ternary()
            return TernaryNode(node, true_expr, false_expr)
        return node

    def parse_logical_or(self):
        node = self.parse_logical_and()
        while self.match('LOG_OR'):
            right = self.parse_logical_and()
            node = BinaryOpNode(node, '||', right)
        return node

    def parse_logical_and(self):
        node = self.parse_bitwise_or()
        while self.match('LOG_AND'):
            right = self.parse_bitwise_or()
            node = BinaryOpNode(node, '&&', right)
        return node

    def parse_bitwise_or(self):
        node = self.parse_bitwise_xor()
        while self.match('BIT_OR'):
            right = self.parse_bitwise_xor()
            node = BinaryOpNode(node, '|', right)
        return node

    def parse_bitwise_xor(self):
        node = self.parse_bitwise_and()
        while self.match('BIT_XOR'):
            right = self.parse_bitwise_and()
            node = BinaryOpNode(node, '^', right)
        return node

    def parse_bitwise_and(self):
        node = self.parse_equality()
        while self.match('BIT_AND'):
            right = self.parse_equality()
            node = BinaryOpNode(node, '&', right)
        return node

    def parse_equality(self):
        node = self.parse_relational()
        while True:
            t = self.match('EQ', 'NE')
            if not t:
                break
            right = self.parse_relational()
            node = BinaryOpNode(node, t.value, right)
        return node

    def parse_relational(self):
        node = self.parse_shift()
        while True:
            t = self.match('LT', 'GT', 'LE', 'GE')
            if not t:
                break
            right = self.parse_shift()
            node = BinaryOpNode(node, t.value, right)
        return node

    def parse_shift(self):
        node = self.parse_additive()
        while True:
            t = self.match('SHL', 'SHR')
            if not t:
                break
            right = self.parse_additive()
            node = BinaryOpNode(node, t.value, right)
        return node

    def parse_additive(self):
        node = self.parse_multiplicative()
        while True:
            t = self.match('PLUS', 'MINUS')
            if not t:
                break
            right = self.parse_multiplicative()
            node = BinaryOpNode(node, t.value, right)
        return node

    def parse_multiplicative(self):
        node = self.parse_unary()
        while True:
            t = self.match('MUL', 'DIV', 'MOD')
            if not t:
                break
            right = self.parse_unary()
            node = BinaryOpNode(node, t.value, right)
        return node

    def parse_unary(self):
        if self.match('INC'):
            return UnaryOpNode('++', self.parse_unary())
        if self.match('DEC'):
            return UnaryOpNode('--', self.parse_unary())
        if self.match('PLUS'):
            return UnaryOpNode('+', self.parse_unary())
        if self.match('MINUS'):
            return UnaryOpNode('-', self.parse_unary())
        if self.match('NOT'):
            return UnaryOpNode('!', self.parse_unary())
        if self.match('BIT_NOT'):
            return UnaryOpNode('~', self.parse_unary())
        if self.match('MUL'):
            return UnaryOpNode('*', self.parse_unary())
        if self.match('BIT_AND'):
            return UnaryOpNode('&', self.parse_unary())
        if self.match('SIZEOF'):
            if self.match('LPAREN'):
                saved_pos = self.pos
                t_spec = self.parse_type_specifier()
                if t_spec and self.peek().type == 'RPAREN':
                    full_t, _ = self.parse_declarator(t_spec)
                    self.expect('RPAREN')
                    return ConstantNode(full_t.size, TYPE_INT)
                self.pos = saved_pos
                target = self.parse_expression()
                self.expect('RPAREN')
                return SizeofNode(target)
            else:
                target = self.parse_unary()
                return SizeofNode(target)

        return self.parse_postfix()

    def parse_postfix(self):
        node = self.parse_primary()
        while True:
            if self.match('INC'):
                node = UnaryOpNode('++', node, is_postfix=True)
            elif self.match('DEC'):
                node = UnaryOpNode('--', node, is_postfix=True)
            elif self.match('LBRACKET'):
                idx = self.parse_expression()
                self.expect('RBRACKET')
                node = IndexAccessNode(node, idx)
            elif self.match('DOT'):
                m = self.expect('IDENTIFIER').value
                node = MemberAccessNode(node, m, is_arrow=False)
            elif self.match('ARROW'):
                m = self.expect('IDENTIFIER').value
                node = MemberAccessNode(node, m, is_arrow=True)
            elif self.match('LPAREN'):
                args = []
                if not self.match('RPAREN'):
                    while True:
                        args.append(self.parse_expression())
                        if not self.match('COMMA'):
                            break
                    self.expect('RPAREN')
                node = CallNode(node, args)
            else:
                break
        return node

    def parse_primary(self):
        if self.match('LPAREN'):
            # Cast or parenthesized expr
            saved_pos = self.pos
            t_spec = self.parse_type_specifier()
            if t_spec:
                full_t, _ = self.parse_declarator(t_spec)
                if self.peek().type == 'RPAREN':
                    self.expect('RPAREN')
                    expr = self.parse_unary()
                    return UnaryOpNode('CAST', expr, target_type=full_t)
            self.pos = saved_pos
            expr = self.parse_expression()
            self.expect('RPAREN')
            return expr

        t = self.peek()
        if t.type == 'INT_DEC':
            self.pos += 1
            return ConstantNode(int(t.value.rstrip('uUlL')), TYPE_INT)
        elif t.type == 'INT_HEX':
            self.pos += 1
            return ConstantNode(int(t.value.rstrip('uUlL'), 16), TYPE_INT)
        elif t.type == 'INT_OCT':
            self.pos += 1
            return ConstantNode(int(t.value.rstrip('uUlL'), 8), TYPE_INT)
        elif t.type == 'FLOAT_CONST':
            self.pos += 1
            return ConstantNode(float(t.value.rstrip('fF')), TYPE_DOUBLE)
        elif t.type == 'STRING':
            self.pos += 1
            raw = t.value[1:-1].encode('utf-8').decode('unicode_escape')
            addr = write_string(raw)
            return ConstantNode(CPointer(addr, TYPE_CHAR), CType('pointer', size=8, base_type=TYPE_CHAR))
        elif t.type == 'CHAR':
            self.pos += 1
            raw = t.value[1:-1].encode('utf-8').decode('unicode_escape')
            char_code = ord(raw[0]) if raw else 0
            return ConstantNode(char_code, TYPE_CHAR)
        elif t.type == 'IDENTIFIER':
            self.pos += 1
            if t.value in self.enum_constants:
                return ConstantNode(self.enum_constants[t.value], TYPE_INT)
            return VarNode(t.value)

        raise SyntaxError(f"Unexpected token {t.type} ({t.value!r}) at L{t.line}")


# =====================================================================
# Execution Environment & Interpreter Engine
# =====================================================================

class SignalReturn(Exception):
    def __init__(self, value):
        self.value = value

class SignalBreak(Exception):
    pass

class SignalContinue(Exception):
    pass

class SignalGoto(Exception):
    def __init__(self, label):
        self.label = label


class Variable:
    def __init__(self, ctype, address):
        self.ctype = ctype
        self.address = address

    def get(self):
        return read_mem(self.address, self.ctype)

    def set(self, val):
        write_mem(self.address, self.ctype, val)


class Scope:
    def __init__(self, parent=None):
        self.parent = parent
        self.vars = {}
        self.funcs = {}

    def get_var(self, name):
        if name in self.vars:
            return self.vars[name]
        if self.parent:
            return self.parent.get_var(name)
        return None

    def get_func(self, name):
        if name in self.funcs:
            return self.funcs[name]
        if self.parent:
            return self.parent.get_func(name)
        return None


class Interpreter:
    def __init__(self):
        self.global_scope = Scope()
        self.current_scope = self.global_scope
        self.exit_code = 0
        self.static_vars = {}

        self.register_intrinsics()

    def register_intrinsics(self):
        def format_printf_args(fmt, args):
            parts = re.split(r"(%[-+ #0]*\d*(?:\.\d*)?[hlLzZ]*[diuoxXfFeEgGaAcCsSp%])", fmt)
            arg_idx = 0
            res = []
            for part in parts:
                if not part:
                    continue
                if part.startswith("%"):
                    if part == "%%":
                        res.append("%")
                    else:
                        if arg_idx >= len(args):
                            res.append(part)
                            continue
                        val = args[arg_idx]
                        arg_idx += 1

                        spec = part[-1]
                        clean_part = re.sub(r"[hlLzZ]", "", part[:-1])

                        if spec in ("d", "i"):
                            res.append((clean_part + "d") % int(val.address if isinstance(val, CPointer) else val))
                        elif spec == "u":
                            uval = int(val.address if isinstance(val, CPointer) else val) & 0xFFFFFFFF
                            res.append((clean_part + "d") % uval)
                        elif spec in ("x", "X"):
                            uval = int(val.address if isinstance(val, CPointer) else val) & 0xFFFFFFFF
                            res.append((clean_part + spec) % uval)
                        elif spec in ("f", "F", "e", "E", "g", "G"):
                            fmt_spec = clean_part + spec
                            if "." not in clean_part and spec in ("f", "F"):
                                fmt_spec = clean_part + ".6f"
                            res.append(fmt_spec % float(val))
                        elif spec == "c":
                            res.append(chr(int(val)))
                        elif spec == "s":
                            if isinstance(val, str):
                                s_str = val
                            elif isinstance(val, CPointer):
                                s_str = read_string(val.address)
                            else:
                                s_str = read_string(int(val))
                            res.append((clean_part + "s") % s_str)
                        elif spec == "p":
                            addr = val.address if isinstance(val, CPointer) else int(val)
                            res.append(f"0x{addr:x}")
                        else:
                            res.append(str(val))
                else:
                    res.append(part)
            return "".join(res)

        def c_printf(args):
            if not args:
                return 0
            fmt_ptr = args[0]
            fmt_str = read_string(fmt_ptr.address if isinstance(fmt_ptr, CPointer) else int(fmt_ptr))
            rest_args = args[1:]
            res = format_printf_args(fmt_str, rest_args)
            sys.stdout.write(res)
            sys.stdout.flush()
            return len(res)

        def c_sprintf(args):
            buf_ptr = args[0]
            fmt_ptr = args[1]
            fmt_str = read_string(fmt_ptr.address if isinstance(fmt_ptr, CPointer) else int(fmt_ptr))
            rest_args = args[2:]
            res = format_printf_args(fmt_str, rest_args)
            addr = buf_ptr.address if isinstance(buf_ptr, CPointer) else int(buf_ptr)
            write_string_at(addr, res)
            return len(res)

        def c_snprintf(args):
            buf_ptr = args[0]
            sz = int(args[1])
            fmt_ptr = args[2]
            fmt_str = read_string(fmt_ptr.address if isinstance(fmt_ptr, CPointer) else int(fmt_ptr))
            rest_args = args[3:]
            res = format_printf_args(fmt_str, rest_args)[:sz-1]
            addr = buf_ptr.address if isinstance(buf_ptr, CPointer) else int(buf_ptr)
            write_string_at(addr, res)
            return len(res)

        def c_puts(args):
            s = read_string(args[0].address if isinstance(args[0], CPointer) else int(args[0]))
            print(s)
            return len(s) + 1

        def c_putchar(args):
            ch = chr(int(args[0]))
            sys.stdout.write(ch)
            sys.stdout.flush()
            return ord(ch)

        def c_getchar(args):
            ch = sys.stdin.read(1)
            return ord(ch) if ch else -1

        def c_malloc(args):
            sz = int(args[0])
            addr = alloc_mem(sz)
            return CPointer(addr, TYPE_VOID)

        def c_calloc(args):
            n = int(args[0])
            sz = int(args[1])
            total = n * sz
            addr = alloc_mem(total)
            MEMORY[addr:addr+total] = b'\x00' * total
            return CPointer(addr, TYPE_VOID)

        def c_realloc(args):
            old_ptr = args[0]
            new_sz = int(args[1])
            old_addr = old_ptr.address if isinstance(old_ptr, CPointer) else int(old_ptr)
            new_addr = alloc_mem(new_sz)
            if old_addr > 0:
                MEMORY[new_addr:new_addr+new_sz] = MEMORY[old_addr:old_addr+new_sz]
            return CPointer(new_addr, TYPE_VOID)

        def c_free(args):
            return 0

        def c_memset(args):
            ptr = args[0]
            val = int(args[1]) & 0xFF
            cnt = int(args[2])
            addr = ptr.address if isinstance(ptr, CPointer) else int(ptr)
            MEMORY[addr:addr+cnt] = bytes([val]) * cnt
            return ptr

        def c_memcpy(args):
            dst = args[0]
            src = args[1]
            cnt = int(args[2])
            d_addr = dst.address if isinstance(dst, CPointer) else int(dst)
            s_addr = src.address if isinstance(src, CPointer) else int(src)
            MEMORY[d_addr:d_addr+cnt] = MEMORY[s_addr:s_addr+cnt]
            return dst

        def c_memcmp(args):
            s1 = args[0]
            s2 = args[1]
            cnt = int(args[2])
            a1 = s1.address if isinstance(s1, CPointer) else int(s1)
            a2 = s2.address if isinstance(s2, CPointer) else int(s2)
            b1 = MEMORY[a1:a1+cnt]
            b2 = MEMORY[a2:a2+cnt]
            if b1 < b2: return -1
            if b1 > b2: return 1
            return 0

        def c_strcpy(args):
            dst = args[0].address if isinstance(args[0], CPointer) else int(args[0])
            src = args[1].address if isinstance(args[1], CPointer) else int(args[1])
            s = read_string(src)
            write_string_at(dst, s)
            return args[0]

        def c_strncpy(args):
            dst = args[0].address if isinstance(args[0], CPointer) else int(args[0])
            src = args[1].address if isinstance(args[1], CPointer) else int(args[1])
            n = int(args[2])
            s = read_string(src)[:n]
            write_string_at(dst, s)
            return args[0]

        def c_strcat(args):
            dst = args[0].address if isinstance(args[0], CPointer) else int(args[0])
            src = args[1].address if isinstance(args[1], CPointer) else int(args[1])
            s1 = read_string(dst)
            s2 = read_string(src)
            write_string_at(dst, s1 + s2)
            return args[0]

        def c_strcmp(args):
            s1 = read_string(args[0].address if isinstance(args[0], CPointer) else int(args[0]))
            s2 = read_string(args[1].address if isinstance(args[1], CPointer) else int(args[1]))
            if s1 < s2: return -1
            if s1 > s2: return 1
            return 0

        def c_strncmp(args):
            n = int(args[2])
            s1 = read_string(args[0].address if isinstance(args[0], CPointer) else int(args[0]))[:n]
            s2 = read_string(args[1].address if isinstance(args[1], CPointer) else int(args[1]))[:n]
            if s1 < s2: return -1
            if s1 > s2: return 1
            return 0

        def c_strlen(args):
            s = read_string(args[0].address if isinstance(args[0], CPointer) else int(args[0]))
            return len(s)

        def c_strchr(args):
            ptr = args[0]
            c = chr(int(args[1]))
            addr = ptr.address if isinstance(ptr, CPointer) else int(ptr)
            s = read_string(addr)
            idx = s.find(c)
            if idx >= 0:
                return CPointer(addr + idx, TYPE_CHAR)
            return CPointer(0, TYPE_CHAR)

        def c_strstr(args):
            p1 = args[0]
            p2 = args[1]
            a1 = p1.address if isinstance(p1, CPointer) else int(p1)
            a2 = p2.address if isinstance(p2, CPointer) else int(p2)
            s1 = read_string(a1)
            s2 = read_string(a2)
            idx = s1.find(s2)
            if idx >= 0:
                return CPointer(a1 + idx, TYPE_CHAR)
            return CPointer(0, TYPE_CHAR)

        def c_atoi(args): return int(read_string(args[0]))
        def c_atof(args): return float(read_string(args[0]))

        def c_exit(args):
            code = int(args[0]) if args else 0
            sys.exit(code)

        def c_sin(args): return math.sin(float(args[0]))
        def c_cos(args): return math.cos(float(args[0]))
        def c_sqrt(args): return math.sqrt(float(args[0]))
        def c_pow(args): return math.pow(float(args[0]), float(args[1]))
        def c_abs(args): return abs(int(args[0]))
        def c_labs(args): return abs(int(args[0]))
        def c_fabs(args): return abs(float(args[0]))

        intrinsics = {
            'printf': c_printf,
            'sprintf': c_sprintf,
            'snprintf': c_snprintf,
            'puts': c_puts,
            'putchar': c_putchar,
            'getchar': c_getchar,
            'malloc': c_malloc,
            'calloc': c_calloc,
            'realloc': c_realloc,
            'free': c_free,
            'memset': c_memset,
            'memcpy': c_memcpy,
            'memcmp': c_memcmp,
            'strcpy': c_strcpy,
            'strncpy': c_strncpy,
            'strcat': c_strcat,
            'strcmp': c_strcmp,
            'strncmp': c_strncmp,
            'strlen': c_strlen,
            'strchr': c_strchr,
            'strstr': c_strstr,
            'atoi': c_atoi,
            'atof': c_atof,
            'exit': c_exit,
            'sin': c_sin,
            'cos': c_cos,
            'sqrt': c_sqrt,
            'pow': c_pow,
            'abs': c_abs,
            'labs': c_labs,
            'fabs': c_fabs,
        }

        for name, func in intrinsics.items():
            self.global_scope.funcs[name] = FuncDeclNode(TYPE_INT, name, [], func, is_intrinsic=True)

    def write_initializer(self, addr, ctype, init_node):
        if isinstance(init_node, InitializerListNode):
            if ctype.kind == 'array':
                elem_type = ctype.base_type
                for i, elem in enumerate(init_node.elems):
                    self.write_initializer(addr + i * elem_type.size, elem_type, elem)
            elif ctype.kind in ('struct', 'union'):
                for (f_offset, f_type), elem in zip(ctype.fields.values(), init_node.elems):
                    self.write_initializer(addr + f_offset, f_type, elem)
        else:
            val = self.eval_node(init_node)
            if ctype.kind == 'array' and isinstance(val, CPointer) and ctype.base_type.kind == 'char':
                # Initializing char array with string literal
                s = read_string(val.address)
                write_string_at(addr, s)
            else:
                write_mem(addr, ctype, val)

    def eval_node(self, node):
        if isinstance(node, ConstantNode):
            return node.value
        elif isinstance(node, VarNode):
            v = self.current_scope.get_var(node.name)
            if not v:
                f = self.current_scope.get_func(node.name)
                if f: return f
                raise NameError(f"Undefined variable '{node.name}'")
            # Array decay
            if v.ctype.kind == 'array':
                return CPointer(v.address, v.ctype.base_type)
            return v.get()
        elif isinstance(node, AssignNode):
            val = self.eval_node(node.expr)
            target = node.target
            if isinstance(target, VarNode):
                v = self.current_scope.get_var(target.name)
                if not v:
                    raise NameError(f"Undefined variable '{target.name}'")
                if node.op != 'ASSIGN':
                    curr = v.get()
                    if node.op == 'ADD_ASSIGN': val = curr + val
                    elif node.op == 'SUB_ASSIGN': val = curr - val
                    elif node.op == 'MUL_ASSIGN': val = curr * val
                    elif node.op == 'DIV_ASSIGN': val = curr // val if isinstance(curr, int) else curr / val
                    elif node.op == 'MOD_ASSIGN': val = curr % val
                    elif node.op == 'AND_ASSIGN': val = curr & val
                    elif node.op == 'OR_ASSIGN': val = curr | val
                    elif node.op == 'XOR_ASSIGN': val = curr ^ val
                    elif node.op == 'SHL_ASSIGN': val = curr << val
                    elif node.op == 'SHR_ASSIGN': val = curr >> val
                v.set(val)
                return val
            elif isinstance(target, UnaryOpNode) and target.op == '*':
                ptr = self.eval_node(target.expr)
                addr = ptr.address if isinstance(ptr, CPointer) else int(ptr)
                t_type = ptr.target_type if isinstance(ptr, CPointer) else TYPE_INT
                write_mem(addr, t_type, val)
                return val
            elif isinstance(target, IndexAccessNode):
                base = self.eval_node(target.target)
                idx = int(self.eval_node(target.index))
                elem_type = base.target_type if isinstance(base, CPointer) else TYPE_INT
                addr = (base.address if isinstance(base, CPointer) else int(base)) + idx * elem_type.size
                write_mem(addr, elem_type, val)
                return val
            elif isinstance(target, MemberAccessNode):
                base = self.eval_node(target.target)
                b_addr = base.address if isinstance(base, CPointer) else int(base)
                st_type = base.target_type if isinstance(base, CPointer) else None
                if st_type and target.member in st_type.fields:
                    offset, f_type = st_type.fields[target.member]
                    write_mem(b_addr + offset, f_type, val)
                    return val
        elif isinstance(node, BinaryOpNode):
            l = self.eval_node(node.left)
            r = self.eval_node(node.right)
            op = node.op

            # Pointer arithmetic (only for + and -)
            if isinstance(l, CPointer) and isinstance(r, int) and op in ('+', '-'):
                sz = l.target_type.size if l.target_type else 1
                if op == '+': return CPointer(l.address + r * sz, l.target_type)
                else: return CPointer(l.address - r * sz, l.target_type)
            elif isinstance(l, int) and isinstance(r, CPointer) and op in ('+', '-'):
                sz = r.target_type.size if r.target_type else 1
                if op == '+': return CPointer(r.address + l * sz, r.target_type)
                else: return CPointer(r.address - l * sz, r.target_type)
            elif isinstance(l, CPointer) and isinstance(r, CPointer) and op == '-':
                sz = l.target_type.size if l.target_type else 1
                return (l.address - r.address) // sz

            l_val = l.address if isinstance(l, CPointer) else l
            r_val = r.address if isinstance(r, CPointer) else r

            op = node.op
            if op == '+': return l_val + r_val
            elif op == '-': return l_val - r_val
            elif op == '*': return l_val * r_val
            elif op == '/': return l_val // r_val if isinstance(l_val, int) and isinstance(r_val, int) else l_val / r_val
            elif op == '%': return l_val % r_val
            elif op == '==': return 1 if l_val == r_val else 0
            elif op == '!=': return 1 if l_val != r_val else 0
            elif op == '<': return 1 if l_val < r_val else 0
            elif op == '>': return 1 if l_val > r_val else 0
            elif op == '<=': return 1 if l_val <= r_val else 0
            elif op == '>=': return 1 if l_val >= r_val else 0
            elif op == '&&': return 1 if (l_val and r_val) else 0
            elif op == '||': return 1 if (l_val or r_val) else 0
            elif op == '&': return l_val & r_val
            elif op == '|': return l_val | r_val
            elif op == '^': return l_val ^ r_val
            elif op == '<<': return l_val << r_val
            elif op == '>>': return l_val >> r_val
        elif isinstance(node, UnaryOpNode):
            if node.op == 'CAST':
                val = self.eval_node(node.expr)
                t = node.target_type
                if t and t.kind == 'pointer':
                    addr = val.address if isinstance(val, CPointer) else int(val)
                    return CPointer(addr, t.base_type)
                elif t and t.kind in ('int', 'char'):
                    return int(val.address if isinstance(val, CPointer) else val)
                elif t and t.kind in ('float', 'double'):
                    return float(val.address if isinstance(val, CPointer) else val)
                return val
            elif node.op == '&':
                target = node.expr
                if isinstance(target, VarNode):
                    v = self.current_scope.get_var(target.name)
                    return CPointer(v.address, v.ctype)
                elif isinstance(target, IndexAccessNode):
                    base = self.eval_node(target.target)
                    idx = int(self.eval_node(target.index))
                    elem_type = base.target_type if isinstance(base, CPointer) else TYPE_INT
                    addr = (base.address if isinstance(base, CPointer) else int(base)) + idx * elem_type.size
                    return CPointer(addr, elem_type)
                elif isinstance(target, MemberAccessNode):
                    base = self.eval_node(target.target)
                    b_addr = base.address if isinstance(base, CPointer) else int(base)
                    st_type = base.target_type if isinstance(base, CPointer) else None
                    if st_type and target.member in st_type.fields:
                        offset, f_type = st_type.fields[target.member]
                        return CPointer(b_addr + offset, f_type)
            elif node.op == '*':
                ptr = self.eval_node(node.expr)
                addr = ptr.address if isinstance(ptr, CPointer) else int(ptr)
                t_type = ptr.target_type if isinstance(ptr, CPointer) else TYPE_INT
                if t_type.kind in ('array', 'struct', 'union'):
                    return CPointer(addr, t_type.base_type if t_type.kind == 'array' else t_type)
                return read_mem(addr, t_type)
            elif node.op == '!':
                val = self.eval_node(node.expr)
                v_val = val.address if isinstance(val, CPointer) else val
                return 0 if v_val else 1
            elif node.op == '~':
                val = int(self.eval_node(node.expr))
                return ~val
            elif node.op == '-':
                return -self.eval_node(node.expr)
            elif node.op == '+':
                return self.eval_node(node.expr)
            elif node.op == '++':
                val = self.eval_node(node.expr)
                res = val + 1
                self.eval_node(AssignNode(node.expr, 'ASSIGN', ConstantNode(res, TYPE_INT)))
                return val if node.is_postfix else res
            elif node.op == '--':
                val = self.eval_node(node.expr)
                res = val - 1
                self.eval_node(AssignNode(node.expr, 'ASSIGN', ConstantNode(res, TYPE_INT)))
                return val if node.is_postfix else res
        elif isinstance(node, IndexAccessNode):
            base = self.eval_node(node.target)
            idx = int(self.eval_node(node.index))
            elem_type = base.target_type if isinstance(base, CPointer) else TYPE_INT
            addr = (base.address if isinstance(base, CPointer) else int(base)) + idx * elem_type.size
            if elem_type.kind in ('array', 'struct', 'union'):
                return CPointer(addr, elem_type.base_type if elem_type.kind == 'array' else elem_type)
            return read_mem(addr, elem_type)
        elif isinstance(node, MemberAccessNode):
            base = self.eval_node(node.target)
            b_addr = base.address if isinstance(base, CPointer) else int(base)
            st_type = base.target_type if isinstance(base, CPointer) else None
            if st_type and node.member in st_type.fields:
                offset, f_type = st_type.fields[node.member]
                if f_type.kind in ('array', 'struct', 'union'):
                    return CPointer(b_addr + offset, f_type.base_type if f_type.kind == 'array' else f_type)
                return read_mem(b_addr + offset, f_type)
        elif isinstance(node, CallNode):
            callee = self.eval_node(node.callee) if isinstance(node.callee, ASTNode) else None
            f_decl = callee if isinstance(callee, FuncDeclNode) else self.current_scope.get_func(node.callee.name)

            if not f_decl:
                raise NameError(f"Undefined function '{node.callee}'")

            args = [self.eval_node(a) for a in node.args]

            if f_decl.is_intrinsic:
                return f_decl.body(args)

            # Call user function
            old_scope = self.current_scope
            self.current_scope = Scope(self.global_scope)

            for (p_type, p_name), arg_val in zip(f_decl.params, args):
                addr = alloc_mem(max(1, p_type.size))
                v = Variable(p_type, addr)
                if isinstance(arg_val, CPointer) and p_type.kind == 'pointer':
                    v.set(arg_val)
                elif p_type.kind == 'pointer':
                    v.set(CPointer(int(arg_val), p_type.base_type))
                else:
                    v.set(arg_val)
                self.current_scope.vars[p_name] = v

            res = 0
            try:
                self.exec_block(f_decl.body)
            except SignalReturn as ret:
                res = ret.value
            finally:
                self.current_scope = old_scope
            return res
        elif isinstance(node, TernaryNode):
            cond = self.eval_node(node.cond)
            c_val = cond.address if isinstance(cond, CPointer) else cond
            return self.eval_node(node.true_expr) if c_val else self.eval_node(node.false_expr)
        elif isinstance(node, SizeofNode):
            if isinstance(node.target, ConstantNode):
                return node.target.ctype.size
            val = self.eval_node(node.target)
            if isinstance(val, CPointer):
                return val.target_type.size
            return 4

        return 0

    def exec_stmt(self, stmt):
        if isinstance(stmt, VarDeclNode):
            if stmt.is_static:
                key = id(stmt)
                if key in self.static_vars:
                    v = self.static_vars[key]
                else:
                    addr = alloc_mem(max(1, stmt.ctype.size))
                    v = Variable(stmt.ctype, addr)
                    if stmt.init_expr:
                        self.write_initializer(addr, stmt.ctype, stmt.init_expr)
                    self.static_vars[key] = v
                self.current_scope.vars[stmt.name] = v
            else:
                addr = alloc_mem(max(1, stmt.ctype.size))
                v = Variable(stmt.ctype, addr)
                if stmt.init_expr:
                    self.write_initializer(addr, stmt.ctype, stmt.init_expr)
                self.current_scope.vars[stmt.name] = v
        elif isinstance(stmt, VarDeclListNode):
            for d in stmt.decls:
                self.exec_stmt(d)
        elif isinstance(stmt, FuncDeclNode):
            self.current_scope.funcs[stmt.name] = stmt
        elif isinstance(stmt, BlockNode):
            self.exec_block(stmt)
        elif isinstance(stmt, IfNode):
            cond = self.eval_node(stmt.cond)
            c_val = cond.address if isinstance(cond, CPointer) else cond
            if c_val:
                self.exec_stmt(stmt.then_branch)
            elif stmt.else_branch:
                self.exec_stmt(stmt.else_branch)
        elif isinstance(stmt, WhileNode):
            while True:
                cond = self.eval_node(stmt.cond)
                c_val = cond.address if isinstance(cond, CPointer) else cond
                if not c_val: break
                try:
                    self.exec_stmt(stmt.body)
                except SignalBreak:
                    break
                except SignalContinue:
                    continue
        elif isinstance(stmt, DoWhileNode):
            while True:
                try:
                    self.exec_stmt(stmt.body)
                except SignalBreak:
                    break
                except SignalContinue:
                    pass
                cond = self.eval_node(stmt.cond)
                c_val = cond.address if isinstance(cond, CPointer) else cond
                if not c_val: break
        elif isinstance(stmt, ForNode):
            if stmt.init:
                self.exec_stmt(stmt.init) if isinstance(stmt.init, ASTNode) else self.eval_node(stmt.init)
            while True:
                cond = self.eval_node(stmt.cond)
                c_val = cond.address if isinstance(cond, CPointer) else cond
                if not c_val: break
                try:
                    self.exec_stmt(stmt.body)
                except SignalBreak:
                    break
                except SignalContinue:
                    pass
                if stmt.incr:
                    self.eval_node(stmt.incr)
        elif isinstance(stmt, SwitchNode):
            val = self.eval_node(stmt.expr)
            v_val = val.address if isinstance(val, CPointer) else val
            matched = False
            try:
                for c_val_node, c_stmts in stmt.cases:
                    c_val = self.eval_node(c_val_node)
                    cv = c_val.address if isinstance(c_val, CPointer) else c_val
                    if matched or v_val == cv:
                        matched = True
                        for s in c_stmts:
                            self.exec_stmt(s)
                if not matched and stmt.default_branch:
                    for s in stmt.default_branch:
                        self.exec_stmt(s)
            except SignalBreak:
                pass
        elif isinstance(stmt, ReturnNode):
            val = self.eval_node(stmt.expr) if stmt.expr else 0
            raise SignalReturn(val)
        elif isinstance(stmt, GotoNode):
            raise SignalGoto(stmt.label)
        elif isinstance(stmt, LabelNode):
            if stmt.stmt:
                self.exec_stmt(stmt.stmt)
        elif isinstance(stmt, BreakNode):
            raise SignalBreak()
        elif isinstance(stmt, ContinueNode):
            raise SignalContinue()
        elif isinstance(stmt, ExprStmtNode):
            if stmt.expr:
                self.eval_node(stmt.expr)

    def exec_block(self, block):
        old_scope = self.current_scope
        self.current_scope = Scope(old_scope)
        try:
            stmts = block.stmts
            # Map labels to statement index
            label_map = {}
            for idx, s in enumerate(stmts):
                if isinstance(s, LabelNode):
                    label_map[s.label] = idx

            pc = 0
            while pc < len(stmts):
                try:
                    self.exec_stmt(stmts[pc])
                    pc += 1
                except SignalGoto as goto_sig:
                    if goto_sig.label in label_map:
                        pc = label_map[goto_sig.label]
                    else:
                        raise goto_sig
        finally:
            self.current_scope = old_scope

    def run_program(self, prog_ast, script_mode=False, main_args=None):
        for decl in prog_ast.decls:
            self.exec_stmt(decl)

        if not script_mode:
            main_func = self.global_scope.get_func('main')
            if main_func:
                args = main_args if main_args else []
                argv_addrs = [write_string(a) for a in args]
                argv_base = alloc_mem(len(argv_addrs) * 8)
                for i, addr in enumerate(argv_addrs):
                    MEMORY[argv_base + i*8 : argv_base + (i+1)*8] = addr.to_bytes(8, byteorder='little')

                argv_ptr = CPointer(argv_base, CType('pointer', size=8, base_type=TYPE_CHAR))
                call_node = CallNode(VarNode('main'), [ConstantNode(len(args), TYPE_INT), ConstantNode(argv_ptr, CType('pointer', size=8, base_type=TYPE_CHAR))])
                return self.eval_node(call_node)
        return 0


# =====================================================================
# Main CLI Entry Point
# =====================================================================

def main():
    argv = sys.argv[1:]

    if not argv or argv[0] == "-h":
        print(HELP_TEXT, end="")
        sys.exit(0)

    if argv[0] == "-c":
        print(LICENSE_TEXT, end="")
        sys.exit(0)

    script_mode = False
    param_idx = 0

    if argv[0] == "-s":
        script_mode = True
        param_idx += 1

    if param_idx < len(argv) and argv[param_idx] == "-i":
        interp = Interpreter()
        while True:
            try:
                line = input("picoc> ")
                pp_code, defines = preprocess(line)
                tokens = lex(pp_code, "<interactive>", defines)
                parser = Parser(tokens)
                prog = parser.parse_program()
                interp.run_program(prog, script_mode=True)
            except (EOFError, KeyboardInterrupt):
                print()
                break
            except Exception as e:
                print(f"Error: {e}")
        sys.exit(0)

    files = []
    while param_idx < len(argv) and argv[param_idx] != "-":
        files.append(argv[param_idx])
        param_idx += 1

    prog_args = []
    if param_idx < len(argv) and argv[param_idx] == "-":
        prog_args = argv[param_idx+1:]
        if files:
            prog_args = [files[0]] + prog_args

    if not files:
        print(HELP_TEXT, end="")
        sys.exit(0)

    full_source = ""
    for filename in files:
        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8", errors="ignore") as f:
                full_source += f.read() + "\n"

    pp_code, defines = preprocess(full_source)
    tokens = lex(pp_code, files[0], defines)
    parser = Parser(tokens)
    prog_ast = parser.parse_program()

    interp = Interpreter()
    ret_code = interp.run_program(prog_ast, script_mode=script_mode, main_args=prog_args if prog_args else files)
    sys.exit(ret_code if isinstance(ret_code, int) else 0)


if __name__ == "__main__":
    main()
