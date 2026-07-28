"""
Pure Python SL Engine - Steam Locomotive animation
Ported from C (sl.c / sl.h) to Python
"""

import random

# D51 Locomotive Constants & Strings
D51HEIGHT = 10
D51FUNNEL = 7
D51LENGTH = 83
D51PATTERNS = 6

D51STR = [
    "      ====        ________                ___________ ",
    "  _D _|  |_______/        \\__I_I_____===__|_________| ",
    "   |(_)---  |   H\\________/ |   |        =|___ ___|   ",
    "   /     |  |   H  |  |     |   |         ||_| |_||   ",
    "  |      |  |   H  |__--------------------| [___] |   ",
    "  | ________|___H__/__|_____/[][]~\\_______|       |   ",
    "  |/ |   |-----------I_____I [][] []  D   |=======|__ "
]

D51WHL = [
    [
        "__/ =| o |=-~~\\  /~~\\  /~~\\  /~~\\ ____Y___________|__ ",
        " |/-=|___|=    ||    ||    ||    |_____/~\\___/        ",
        "  \\_/      \\O=====O=====O=====O_/      \\_/            "
    ],
    [
        "__/ =| o |=-~~\\  /~~\\  /~~\\  /~~\\ ____Y___________|__ ",
        " |/-=|___|=O=====O=====O=====O   |_____/~\\___/        ",
        "  \\_/      \\__/  \\__/  \\__/  \\__/      \\_/            "
    ],
    [
        "__/ =| o |=-O=====O=====O=====O \\ ____Y___________|__ ",
        " |/-=|___|=    ||    ||    ||    |_____/~\\___/        ",
        "  \\_/      \\__/  \\__/  \\__/  \\__/      \\_/            "
    ],
    [
        "__/ =| o |=-~O=====O=====O=====O\\ ____Y___________|__ ",
        " |/-=|___|=    ||    ||    ||    |_____/~\\___/        ",
        "  \\_/      \\__/  \\__/  \\__/  \\__/      \\_/            "
    ],
    [
        "__/ =| o |=-~~\\  /~~\\  /~~\\  /~~\\ ____Y___________|__ ",
        " |/-=|___|=   O=====O=====O=====O|_____/~\\___/        ",
        "  \\_/      \\__/  \\__/  \\__/  \\__/      \\_/            "
    ],
    [
        "__/ =| o |=-~~\\  /~~\\  /~~\\  /~~\\ ____Y___________|__ ",
        " |/-=|___|=    ||    ||    ||    |_____/~\\___/        ",
        "  \\_/      \\_O=====O=====O=====O/      \\_/            "
    ]
]

D51DEL = "                                                      "

COAL = [
    "                              ",
    "                              ",
    "    _________________         ",
    "   _|                \\_____A  ",
    " =|                        |  ",
    " -|                        |  ",
    "__|________________________|_ ",
    "|__________________________|_ ",
    "   |_D__D__D_|  |_D__D__D_|   ",
    "    \\_/   \\_/    \\_/   \\_/    ",
    "                              "
]

# LOGO Train Constants & Strings
LOGOPATTERNS = 6
LOGOHEIGHT = 6
LOGOFUNNEL = 4
LOGOLENGTH = 84

LOGO_STR = [
    "     ++      +------ ",
    "     ||      |+-+ |  ",
    "   /---------|| | |  ",
    "  + ========  +-+ |  "
]

LWHL = [
    [" _|--O========O~\\-+  ", "//// \\_/      \\_/    "],
    [" _|--/O========O\\-+  ", "//// \\_/      \\_/    "],
    [" _|--/~O========O-+  ", "//// \\_/      \\_/    "],
    [" _|--/~\\------/~\\-+  ", "//// \\_O========O    "],
    [" _|--/~\\------/~\\-+  ", "//// \\O========O/    "],
    [" _|--/~\\------/~\\-+  ", "//// O========O_/    "]
]

LCOAL = [
    "____                 ",
    "|   \\@@@@@@@@@@@     ",
    "|    \\@@@@@@@@@@@@@_ ",
    "|                  | ",
    "|__________________| ",
    "   (O)       (O)     ",
    "                     "
]

LCAR = [
    "____________________ ",
    "|  ___ ___ ___ ___ | ",
    "|  |_| |_| |_| |_| | ",
    "|__________________| ",
    "|__________________| ",
    "   (O)        (O)    ",
    "                     "
]

DELLN = "                     "

# C51 Locomotive Constants & Strings
C51HEIGHT = 11
C51FUNNEL = 7
C51LENGTH = 87
C51PATTERNS = 6
C51DEL = "                                                       "

C51STR = [
    "        ___                                            ",
    "       _|_|_  _     __       __             ___________",
    "    D__/   \\_(_)___|  |__H__|  |_____I_Ii_()|_________|",
    "     | `---'   |:: `--'  H  `--'         |  |___ ___|  ",
    "    +|~~~~~~~~++::~~~~~~~H~~+=====+~~~~~~|~~||_| |_||  ",
    "    ||        | ::       H  +=====+      |  |::  ...|  ",
    "|    | _______|_::-----------------[][]-----|       |  "
]

C51WH = [
    [
        "| /~~ ||   |-----/~~~~\\  /[I_____I][][] --|||_______|__",
        "------'|oOo|=[]=-      ||      ||      |  ||=======_|__",
        "/~\\____|___|/~\\_|  O=======O=======O   |__|+-/~\\_|     ",
        "\\_/         \\_/  \\____/  \\____/  \\____/      \\_/       "
    ],
    [
        "| /~~ ||   |-----/~~~~\\  /[I_____I][][] --|||_______|__",
        "------'|oOo|=[]=- O=======O=======O    |  ||=======_|__",
        "/~\\____|___|/~\\_|      ||      ||      |__|+-/~\\_|     ",
        "\\_/         \\_/  \\____/  \\____/  \\____/      \\_/       "
    ],
    [
        "| /~~ ||   |-----/~~~~\\  /[I_____I][][] --|||_______|__",
        "------'|oOo|==[]=- O=======O=======O   |  ||=======_|__",
        "/~\\____|___|/~\\_|      ||      ||      |__|+-/~\\_|     ",
        "\\_/         \\_/  \\____/  \\____/  \\____/      \\_/       "
    ],
    [
        "| /~~ ||   |-----/~~~~\\  /[I_____I][][] --|||_______|__",
        "------'|oOo|===[]=- O=======O=======O  |  ||=======_|__",
        "/~\\____|___|/~\\_|      ||      ||      |__|+-/~\\_|     ",
        "\\_/         \\_/  \\____/  \\____/  \\____/      \\_/       "
    ],
    [
        "| /~~ ||   |-----/~~~~\\  /[I_____I][][] --|||_______|__",
        "------'|oOo|===[]=-    ||      ||      |  ||=======_|__",
        "/~\\____|___|/~\\_|    O=======O=======O |__|+-/~\\_|     ",
        "\\_/         \\_/  \\____/  \\____/  \\____/      \\_/       "
    ],
    [
        "| /~~ ||   |-----/~~~~\\  /[I_____I][][] --|||_______|__",
        "------'|oOo|==[]=-     ||      ||      |  ||=======_|__",
        "/~\\____|___|/~\\_|   O=======O=======O  |__|+-/~\\_|     ",
        "\\_/         \\_/  \\____/  \\____/  \\____/      \\_/       "
    ]
]

SMOKEPTNS = 16
Smoke = [
    ["(   )", "(    )", "(    )", "(   )", "(  )", "(  )", "( )", "( )", "()", "()", "O", "O", "O", "O", "O", " "],
    ["(@@@)", "(@@@@)", "(@@@@)", "(@@@)", "(@@)", "(@@)", "(@)", "(@)", "@@", "@@", "@", "@", "@", "@", "@", " "]
]
Eraser = ["     ", "      ", "      ", "     ", "    ", "    ", "   ", "   ", "  ", "  ", " ", " ", " ", " ", " ", " "]
dy_smoke = [2, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
dx_smoke = [-2, -1, 0, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 3, 3, 3]

man = [["", "(O)"], ["Help!", "\\O/"]]
fdancer = [["\\\\0", "/\\", "|\\"], ["0//", "/\\", "/|"]]
Efdancer = [["   ", "  ", "  "], ["   ", "  ", "  "]]
mdancer = [["_O_", " #", "/\\"], ["(0)", " #", "/\\"], ["(O_", " #", "/\\"]]
Emdancer = [["   ", "  ", "  "], ["   ", "  ", "  "], ["   ", "  ", "  "]]


class SLEngine:
    def __init__(self, cols, lines, arg=""):
        self.cols = cols
        self.lines = lines
        self.accident = 0
        self.logo = 0
        self.fly = 0
        self.c51 = 0
        self.dance = 0
        self.rand = 0

        self.parse_arg(arg)
        if self.rand:
            self.accident |= random.randint(0, 1)
            self.logo |= random.randint(0, 1)
            self.fly |= random.randint(0, 1)
            self.c51 |= random.randint(0, 1)
            self.dance |= random.randint(0, 1)

        self.smokes = []
        self.smoke_sum = 0

        min_val = 0
        offset = 21
        if self.logo >= 1:
            min_val = -LOGOLENGTH - 1 - offset * (self.logo - 1)
        elif self.c51 == 1:
            min_val = -C51LENGTH - 1
        else:
            min_val = -D51LENGTH - 1

        self.total_steps = -min_val + self.cols - 1
        self.current_step = 0

    def parse_arg(self, arg):
        if not arg:
            return
        idx = 0
        while idx < len(arg):
            if arg[idx] == '-':
                idx += 1
                while idx < len(arg) and arg[idx] != '-':
                    ch = arg[idx]
                    if ch == 'l': self.logo += 1
                    elif ch == 'a': self.accident = 1
                    elif ch == 'F': self.fly = 1
                    elif ch == 'c': self.c51 = 1
                    elif ch == 'd': self.dance = 1
                    elif ch == 'r': self.rand = 1
                    idx += 1
            else:
                idx += 1

    def step(self):
        if self.current_step >= self.total_steps:
            return None

        grid = [[' '] * self.cols for _ in range(self.lines)]

        def addch(y, x, c):
            if 0 <= y < self.lines and 0 <= x < self.cols:
                grid[y][x] = c

        def mvaddstr(y, x, s):
            for i, ch in enumerate(s):
                addch(y, x + i, ch)

        def add_man(y, x):
            idx = ((LOGOLENGTH + x) // 12) % 2
            for i in range(2):
                mvaddstr(y + i, x, man[idx][i])

        def add_fdancer(y, x):
            idx = ((LOGOLENGTH + x) // 12) % 2
            for i in range(3):
                mvaddstr(y + i, x + 1, Efdancer[idx][i])
                mvaddstr(y + i, x, fdancer[idx][i])

        def add_mdancer(y, x):
            idx = ((LOGOLENGTH + x) // 12) % 3
            for i in range(3):
                mvaddstr(y + i, x + 1, Emdancer[idx][i])
                mvaddstr(y + i, x, mdancer[idx][i])

        def add_smoke(y, x):
            if x % 4 == 0:
                for s in self.smokes:
                    mvaddstr(s['y'], s['x'], Eraser[s['ptrn']])
                    s['y'] -= dy_smoke[s['ptrn']]
                    s['x'] += dx_smoke[s['ptrn']]
                    if s['ptrn'] < SMOKEPTNS - 1:
                        s['ptrn'] += 1
                    mvaddstr(s['y'], s['x'], Smoke[s['kind']][s['ptrn']])

                mvaddstr(y, x, Smoke[self.smoke_sum % 2][0])
                self.smokes.append({
                    'y': y,
                    'x': x,
                    'ptrn': 0,
                    'kind': self.smoke_sum % 2
                })
                self.smoke_sum += 1

        mod = self.current_step
        x = -mod + self.cols - 1

        if self.logo >= 1:
            y = self.lines // 2 - 3
            py1 = py2 = py3 = 0
            offset = 21
            if self.fly == 1:
                y = (x // 6) + self.lines - (self.cols // 6) - LOGOHEIGHT
                py1 = 2; py2 = 4; py3 = 6

            sl_pat_idx = ((LOGOLENGTH + offset * (self.logo - 1) + x) // 3) % LOGOPATTERNS
            sl_lines = LOGO_STR + LWHL[sl_pat_idx] + [DELLN]
            coal_lines = LCOAL
            car_lines = LCAR

            for i in range(LOGOHEIGHT + 1):
                mvaddstr(y + i, x, sl_lines[i])
                mvaddstr(y + i + py1, x + 21, coal_lines[i])
                for j in range(self.logo + 1):
                    yoffset = 2 * j * self.fly
                    mvaddstr(y + i + py3 + yoffset, x + 42 + offset * j, car_lines[i])

            if self.accident == 1:
                add_man(y + 1, x + 14)
                for j in range(self.logo + 1):
                    yoffset = self.fly * (2 + 2 * j)
                    add_man(y + 1 + py2 + yoffset, x + 45 + offset * j)
                    add_man(y + 1 + py2 + yoffset, x + 53 + offset * j)

            if self.dance == 1 and self.accident == 0 and self.fly == 0:
                add_mdancer(y - 2, x + 21)
                for j in range(self.logo + 1):
                    add_mdancer(y + py2 - 2, x + 45 + offset * j)
                    add_mdancer(y + py2 - 2, x + 50 + offset * j)
                    add_mdancer(y + py2 - 2, x + 55 + offset * j)

            add_smoke(y - 1, x + LOGOFUNNEL)

        elif self.c51 == 1:
            y = self.lines // 2 - 5
            dy = 0
            if self.fly == 1:
                y = (x // 7) + self.lines - (self.cols // 7) - C51HEIGHT
                dy = 1

            pat_idx = (C51LENGTH + x) % C51PATTERNS
            c51_lines = C51STR + C51WH[pat_idx] + [C51DEL]

            for i in range(C51HEIGHT + 1):
                mvaddstr(y + i, x, c51_lines[i])
                mvaddstr(y + i + dy, x + 55, COAL[i])

            if self.accident == 1:
                add_man(y + 3, x + 45)
                add_man(y + 3, x + 49)

            if self.dance == 1 and self.accident == 0 and self.fly == 0:
                add_mdancer(y - 1, x + 45)
                add_fdancer(y - 1, x + 50)

            add_smoke(y - 1, x + C51FUNNEL)

        else:
            y = self.lines // 2 - 5
            dy = 0
            if self.fly == 1:
                y = (x // 7) + self.lines - (self.cols // 7) - D51HEIGHT
                dy = 1

            pat_idx = (D51LENGTH + x) % D51PATTERNS
            d51_lines = D51STR + D51WHL[pat_idx] + [D51DEL]

            for i in range(D51HEIGHT + 1):
                mvaddstr(y + i, x, d51_lines[i])
                mvaddstr(y + i + dy, x + 53, COAL[i])

            if self.accident == 1:
                add_man(y + 2, x + 43)
                add_man(y + 2, x + 47)

            if self.dance == 1 and self.accident == 0 and self.fly == 0:
                add_mdancer(y - 2, x + 43)
                add_fdancer(y - 2, x + 48)

            add_smoke(y - 1, x + D51FUNNEL)

        self.current_step += 1
        return "\n".join("".join(row) for row in grid)
