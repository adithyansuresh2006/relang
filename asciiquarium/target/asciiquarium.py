#!/usr/bin/env python3
"""
Asciiquarium - An aquarium animation in ASCII art.
Ported from Perl reference implementation to Python 3.
"""

import sys
import os
import time
import random
import argparse
import curses

# --- Depth Constants ---
DEPTH = {
    'shark': 2,
    'fish_start': 3,
    'fish_end': 20,
    'seaweed': 21,
    'castle': 22,
    'water_line': 2,
    'water_gap': 5,
}

# --- ASCII Art & Color Masks ---

CASTLE_IMAGE = r"""
               T~~
               |
              /^\
             /   \
 _   _   _  /     \  _   _   _
[ ]_[ ]_[ ]/ _   _ \[ ]_[ ]_[ ]
|_=__-_ =_|_[ ]_[ ]_|_=-___-__|
 | _- =  | =_ = _    |= _=   |
 |= -[]  |- = _ =    |_-=_[] |
 | =_    |= - ___    | =_ =  |
 |=  []- |-  /| |\   |=_ =[] |
 |- =_   | =| | | |  |- = -  |
 |_______|__|_|_|_|__|_______|
"""

CASTLE_MASK = r"""
                RR

              yyy
             y   y
            y     y
           y       y



              yyy
             yy yy
            y y y y
            yyyyyyy
"""

WATER_LINE_SEGMENTS = [
    r"~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
    r"^^^^ ^^^  ^^^   ^^^    ^^^^      ",
    r"^^^^      ^^^^     ^^^    ^^     ",
    r"^^      ^^^^      ^^^    ^^^^^^  "
]

NEW_FISH_DATA = [
    # Fish 1 (Right)
    (r"""
   \
  / \
>=_('>
  \_/
   /
""", r"""
   1
  1 1
663745
  111
   3
"""),
    # Fish 1 (Left)
    (r"""
  /
 / \
<')_=<
 \_/
  \
""", r"""
  2
 111
547366
 111
  3
"""),
    # Fish 2 (Right)
    (r"""
     ,
     }\
\  .'  `\
}}<   ( 6>
/  `,  .'
     }/
     '
""", r"""
     2
     22
6  11  11
661   7 45
6  11  11
     33
     3
"""),
    # Fish 2 (Left)
    (r"""
    ,
   /{
 /'  `.  /
<6 )   >{{
 `.  ,'  \
   \{
    `
""", r"""
    2
   22
 11  11  6
54 7   166
 11  11  6
   33
    3
"""),
    # Fish 3 (Right)
    (r"""
            \'`.
             )  \
(`.      _.-`' ' '`-.
 \ `.  .`        (o) \_
  >  ><     (((       (
 / .`  `._      /_|  /'
(.`       `-. _  _.-`
            /__/'
""", r"""
            1111
             1  1
111      11111 1 1111
 1 11  11        141 11
  1  11     777       5
 1 11  111      333  11
111       111 1  1111
            11111
"""),
    # Fish 3 (Left)
    (r"""
       .'`/
      /  (
  .-'` ` `'-._      .')
_/ (o)        '.  .' /
)       )))     ><  <
`\  |_\      _.'  '. \
  '-._  _ .-'       .)
      `\__\
""", r"""
       1111
      1  1
  1111 1 11111      111
11 141        11  11 1
5       777     11  1
11  333      111  11 1
  1111  1 111       111
      11111
"""),
    # Fish 4 (Right)
    (r"""
       ,--,_
__    _\.---'-.
\ '.-"     // o\
/_.'-._    \\  /
       `"--(/"`
""", r"""
       22222
66    121111211
6 6111     77 41
6661111    77  1
       11113311
"""),
    # Fish 4 (Left)
    (r"""
    _,--,
 .-'---./_    __
/o \\     "-.' /
\  //    _.-'._\
 `" Cot"--"`
""".replace(' Cot', ')'), r"""
    22222
 112111121    66
14 77     1116 6
1  77    1111666
 11331111
""")
]

OLD_FISH_DATA = [
    # Fish 1 (Right)
    (r"""
       \
     ...\..,
\  /'       \
 >=     (  ' >
/  \      / /
    `"'"'/''
""", r"""
       2
     1112111
6  11       1
 66     7  4 5
6  1      3 1
    11111311
"""),
    # Fish 1 (Left)
    (r"""
      /
  ,../...
 /       '\  /
< '  )     =<
 \ \      /  \
  `'\'"'"'
""", r"""
      2
  1112111
 1       11  6
5 4  7     66
 1 3      1  6
  11311111
"""),
    # Fish 2 (Right)
    (r"""
    \
\ /--\
>=  (o>
/ \__/
    /
""", r"""
    2
6 1111
66  745
6 1111
    3
"""),
    # Fish 2 (Left)
    (r"""
  /
 /--\ /
<o)  =<
 \__/ \
  \
""", r"""
  2
 1111 6
547  66
 1111 6
  3
"""),
    # Fish 3 (Right)
    (r"""
       \:.
\;,   ,;\\\\\,,
  \\\\\;;:::::::o
  ///;;::::::::<
 /;` ``/////``
""", r"""
       222
666   1122211
  6661111111114
  66611111111115
 666 113333311
"""),
    # Fish 3 (Left)
    (r"""
      .:/
   ,,///;,   ,;/
 o:::::::;;///
>::::::::;;\\\\\
  ''\\\\\\\\\'' ';\
""", r"""
      222
   1122211   666
 4111111111666
51111111111666
  113333311 666
"""),
    # Fish 4 (Right)
    (r"""
  __
><_'>
   '
""", r"""
  11
61145
   3
"""),
    # Fish 4 (Left)
    (r"""
 __
<'_><
 `
""", r"""
 11
54116
 3
"""),
    # Fish 5 (Right)
    (r"""
   ..\,
>='   ('>
  '''/''
""", r"""
   1121
661   745
  111311
"""),
    # Fish 5 (Left)
    (r"""
  ,/..
<')   `=<
 ``\```
""", r"""
  1211
547   166
 113111
"""),
    # Fish 6 (Right)
    (r"""
   \
  / \
>=_('>
  \_/
   /
""", r"""
   2
  1 1
661745
  111
   3
"""),
    # Fish 6 (Left)
    (r"""
  /
 / \
<')_=<
 \_/
  \
""", r"""
  2
 1 1
547166
 111
  3
"""),
    # Fish 7 (Right)
    (r"""
  ,\
>=('>
  '/
""", r"""
  12
66745
  13
"""),
    # Fish 7 (Left)
    (r"""
 /,
<')=<
 \`
""", r"""
 21
54766
 31
"""),
    # Fish 8 (Right)
    (r"""
  __
\/ o\
/\__/
""", r"""
  11
61 41
61111
"""),
    # Fish 8 (Left)
    (r"""
 __
/o \/
\__/\
""", r"""
 11
14 16
11116
""")
]

SHARK_IMAGE = [
    # Right
    r"""
                              __
                             ( `\
  ,                          )   `\
;' `.                        (     `\__
 ;   `.             __..---''          `~~~~-._
  `.   `.____...--''                       (b  `--._
    >                     _.-'      .((      ._     )
  .`.-`--...__         .-'     -.___.....-(|/|/|/|/'
 ;.'         `. ...----`.___.',,,_______......---'
 '           '-'
""",
    # Left
    r"""
                     __
                    /' )
                  /'   (                          ,
              __/'     )                        .' `;
      _.-~~~~'          ``---..__             .'   ;
 _.--'  b)                       ``--...____.'   .'
(     _.      )).      `-._                     <
 `\|\|\|\|)-.....___.-     `-.         __...--'-.'.
   `---......_______,,,`.___.'----... .'         `.;
                                     `-`           `
"""
]

SHARK_MASK = [
    r"""




                                           cR

                                          cWWWWWWWW
""",
    r"""




        Rc

  WWWWWWWWc
"""
]

SPLAT_FRAMES = [
    r"""

   .
  ***
   '

""",
    r"""

 ",*;`
 "*,**
 *"'~'

""",
    r"""

  , ,
 " ","'
 *" *'"
  " ; .

""",
    r"""
* ' , ' `
' ` * . '
 ' `' ",'
* ' " * .
" * ', '
"""
]

SHIP_IMAGE = [
    # Right
    r"""
     |    |    |
    )_)  )_)  )_)
   )___))___))___)\
  )____)____)_____)\\\
_____|____|____|____\\\\\__
\                   /
""",
    # Left
    r"""
         |    |    |
        (_(  (_(  (_(
      /(___((___((___(
    //(_____(____(____(
__///____|____|____|_____
    \                   /
"""
]

SHIP_MASK = [
    r"""
     y    y    y

                  w
                   ww
yyyyyyyyyyyyyyyyyyyywwwyy
y                   y
""",
    r"""
         y    y    y

      w
    ww
yywwwyyyyyyyyyyyyyyyyyyyy
    y                   y
"""
]

WHALE_IMAGE = [
    # Right
    r"""
        .-----:
      .'       `.
,    /       (o) \
\`._/          ,__)
""",
    # Left
    r"""
    :-----.
  .'       `.
 / (o)       \    ,
(__,          \_.'/
"""
]

WHALE_MASK = [
    r"""
             C C
           CCCCCCC
           C  C  C
        BBBBBBB
      BB       BB
B    B       BWB B
BBBBB          BBBB
""",
    r"""
   C C
 CCCCCCC
 C  C  C
    BBBBBBB
  BB       BB
 B BWB       B    B
BBBB          BBBBB
"""
]

WATER_SPOUT_FRAMES = [
    "\n\n   :",
    "\n   :\n   :",
    "  . .\n  -:-\n   :",
    "  . .\n .-:-\n   :",
    "  . .\n'.-:-.`\n'  :  '",
    "\n .- -.\n;  :  ;",
    "\n\n;     ;"
]

NEW_MONSTER_IMAGE = [
    # Right
    [
        r"""
         _   _                     _   _       _a_a
       _{.`=`.}_      _   _      _{.`=`.}_    {/ ''\_
 _    {.'  _  '.}    {.`'`.}    {.'  _  '.}  {|  ._oo)
{ \  {/  .' '.  \}  {/ .-. \}  {/  .' '.  \} {/  |
""",
        r"""
                      _   _                    _a_a
  _      _   _      _{.`=`.}_      _   _      {/ ''\_
 { \    {.`'`.}    {.'  _  '.}    {.`'`.}    {|  ._oo)
  \ \  {/ .-. \}  {/  .' '.  \}  {/ .-. \}   {/  |
"""
    ],
    # Left
    [
        r"""
   a_a_       _   _                     _   _
 _/'' \}    _{.`=`.}_      _   _      _{.`=`.}_
(oo_.  |}  {.'  _  '.}    {.`'`.}    {.'  _  '.}    _
    |  \} {/  .' '.  \}  {/ .-. \}  {/  .' '.  \}  / }
""",
        r"""
   a_a_                    _   _
 _/'' \}      _   _      _{.`=`.}_      _   _      _
(oo_.  |}    {.`'`.}    {.'  _  '.}    {.`'`.}    / }
    |  \}   {/ .-. \}  {/  .' '.  \}  {/ .-. \}  / /
"""
    ]
]

NEW_MONSTER_MASK = [
    r"""                                                W W



""",
    r"""   W W



"""
]

OLD_MONSTER_IMAGE = [
    # Right
    [
        r"""
                                                          ____
            __                                           /   o  \
          /    \        _                     _         /     ____ >
  _      |  __  |     /   \        _        /   \      |     |
 | \     |  ||  |    |     |     /   \     |     |     |     |
""",
        r"""
                                                          ____
                                             __          /   o  \
             _                     _        /    \      /     ____ >
   _       /   \        _        /   \     |  __  |    |     |
  | \     |     |     /   \     |     |    |  ||  |    |     |
""",
        r"""
                                                          ____
                                  __                     /   o  \
 _                      _        /    \        _        /     ____ >
| \          _        /   \     |  __  |     /   \     |     |
 \ \       /   \     |     |    |  ||  |    |     |    |     |
""",
        r"""
                                                          ____
                       __                               /   o  \
  _          _        /    \        _                  /     ____ >
 | \       /   \     |  __  |     /   \        _      |     |
  \ \     |     |    |  ||  |    |     |     /   \    |     |
"""
    ],
    # Left
    [
        r"""
    ____
  /  o   \                                                  __
< ____     \       _                     _                /    \
      |     |    /   \        _        /   \     |  __  |      _
      |     |   |     |     /   \     |     |    |  ||  |     / |
""",
        r"""
    ____
  /  o   \         __
< ____     \     /    \       _                     _
      |     |   |  __  |    /   \        _        /   \       _
      |     |   |  ||  |   |     |     /   \     |     |     / |
""",
        r"""
    ____
  /  o   \                    __
< ____     \       _        /    \       _                      _
      |     |    /   \     |  __  |    /   \        _          / |
      |     |   |     |    |  ||  |   |     |     /   \       / /
""",
        r"""
    ____
  /  o   \                               __
< ____     \                  _        /    \       _          _
      |     |      _        /   \     |  __  |    /   \       / |
      |     |    /   \     |     |    |  ||  |   |     |     / /
"""
    ]
]

OLD_MONSTER_MASK = [
    r"""


                                                            W



""",
    r"""


     W



"""
]

BIG_FISH_1_IMAGE = [
    # Right
    r"""
 ______
`""-.  `````-----.....__
     `.  .      .       `-.
       :     .     .       `.
 ,     :   .    .          _ :
: `.   :                  (@) `._
 `. `..'     .     =`-.       .__)
   ;     .        =  ~  :     .-"
 .' .'`.   .    .  =.-'  `._ .'
: .'   :               .   .'
 '   .'  .    .     .   .-'
   .'____....----''.'=.'
   ""             .'.'
               ''"'`
""",
    # Left
    r"""
                           ______
          __.....-----'''''  .-""'
       .-'       .      .  .'
     .'       .     .     :
    : _          .    .   :     ,
 _.' (@)                  :   .' :
(__.       .-'=     .     `..' .'
 "-.     :  ~  =        .     ;
   `. _.'  `-.=  .    .   .'`. `.
     `.   .               :   `. :
       `-.   .     .    .  `.   `
          `.=`.``----....____`.
            `.`.             ""
              '`"``
"""
]

BIG_FISH_1_MASK = [
    r"""
 111111
11111  11111111111111111
     11  2      2       111
       1     2     2       11
 1     1   2    2          1 1
1 11   1                  1W1 111
 11 1111     2     1111       1111
   1     2        1  1  1     111
 11 1111   2    2  1111  111 11
1 11   1               2   11
 1   11  2    2     2   111
   111111111111111111111
   11             1111
               11111
""",
    r"""
                           111111
          11111111111111111  11111
       111       2      2  11
     11       2     2     1
    1 1          2    2   1     1
 111 1W1                  1   11 1
1111       1111     2     1111 11
 111     1  1  1        2     1
   11 111  1111  2    2   1111 11
     11   2               1   11 1
       111   2     2    2  11   1
          111111111111111111111
            1111             11
              11111
"""
]

BIG_FISH_2_IMAGE = [
    # Right
    r"""
                _ _ _
             .='\\ \\ \\`"=,
           .'\\ \\ \\ \\ \\ \\ \\
\'=._     / \\ \\ \\_\\_\\_\\_\\_\\
\'=._'.  /\\ \\,-"`- _ - _ - '-.
  \`=._\|'.\/- _ - _ - _ - _- \
  ;"= ._\=./_ -_ -_ {`"=_    @ \
   ;="_-_=- _ -  _ - {"=_"-     \
   ;_=_--_.,          {_.='   .-/
  ;.="` / ';\        _.     _.-`
  /_.='/ \/ /;._ _ _{.-;`/"`
/._=_.'   '/ / / / /{.= /
/.='      `'./_/_.=`{_/
""",
    # Left
    r"""
            _ _ _
        ,="`/ / /'=.
       / / / / / / /'.
      /_/_/_/_/_/ / / \     _.='/
   .-' - _ - _ -`"-,/ /\  .'_.='/
  / -_ - _ - _ - _ -\/.'|/_.=`/
 / @    _="\} _- _- _\.=/_. =";
/     -"_="\} - _  - _ -=_-_"=;
\-.   '=._\}          ,._--_=_;
 `-._     ._        /;' \ `"=.;
     `"\`;-.\}_ _ _.;\ \/ \'=._\
        \ =.\}\ \ \ \ \'   '._=_.\
         \_\}`=._\_\.'`       '=.\
"""
]

BIG_FISH_2_MASK = [
    r"""
                1 1 1
             1111 1 11111
           111 1 1 1 1 1 1
11111     1 1 1 11111111111
1111111  11 111112 2 2 2 2 111
  111111111112 2 2 2 2 2 2 22 1
  111 1111 12 22 22 11111    W 1
   11111112 2 2  2 2 111111     1
   111111111          11111   111
  11111 11111        11     1111
  111111 11 1111 1 111111111
1111111   11 1 1 1 1111 1
1111       1111111111111
""",
    r"""
            1 1 1
        11111 1 1111
       1 1 1 1 1 1 111
      11111111111 1 1 1     11111
   111 2 2 2 2 211111 11  1111111
  1 22 2 2 2 2 2 2 211111111111
 1 W    11111 22 22 2111111 111
1     111111 2 2  2 2 21111111
111   11111          111111111
 1111     11        111 1 11111
     111111111 1 1111 11 111111
        1 1111 1 1 1 11   1111111
         1111111111111       1111
"""
]

# Color Character Map
COLOR_MAP = {
    'c': 1, 'C': 1,
    'r': 2, 'R': 2,
    'y': 3, 'Y': 3,
    'b': 4, 'B': 4,
    'g': 5, 'G': 5,
    'm': 6, 'M': 6,
    'w': 7, 'W': 7,
    'k': 8, 'K': 8
}

COLOR_CHOICES = ['c', 'C', 'r', 'R', 'y', 'Y', 'b', 'B', 'g', 'G', 'm', 'M']

def map_random_colors(mask_str):
    mapping = {}
    for d in "123456789":
        mapping[d] = random.choice(COLOR_CHOICES)
    mapping['4'] = 'W'
    res = []
    for char in mask_str:
        if char in mapping:
            res.append(mapping[char])
        else:
            res.append(char)
    return "".join(res)


class Entity:
    def __init__(self, name="", etype="", shapes=None, colors=None, pos=None,
                 dx=0.0, dy=0.0, z=10, default_color=7, anim_speed=0.25,
                 die_offscreen=True, die_time=None, death_cb=None, die_frame=None):
        self.name = name
        self.etype = etype
        self.shapes = shapes if shapes else [""]
        if isinstance(self.shapes, str):
            self.shapes = [self.shapes]
        self.colors = colors if colors else [""]
        if isinstance(self.colors, str):
            self.colors = [self.colors]

        self.x = pos[0] if pos else 0.0
        self.y = pos[1] if pos else 0.0
        self.z = pos[2] if pos and len(pos) > 2 else z

        self.dx = dx
        self.dy = dy
        self.default_color = default_color
        self.anim_speed = anim_speed
        self.frame_idx = 0
        self.last_anim = time.time()
        self.die_offscreen = die_offscreen
        self.die_time = die_time
        self.death_cb = death_cb
        self.die_frame = die_frame
        self.alive = True
        self.frame_count = 0

    @property
    def current_shape(self):
        return self.shapes[self.frame_idx % len(self.shapes)]

    @property
    def current_color(self):
        if not self.colors or not self.colors[0]:
            return None
        return self.colors[self.frame_idx % len(self.colors)]

    @property
    def width(self):
        lines = self.current_shape.strip('\n').split('\n')
        return max(len(l) for l in lines) if lines else 0

    @property
    def height(self):
        lines = self.current_shape.strip('\n').split('\n')
        return len(lines)

    def update(self, aquarium):
        now = time.time()
        if now - self.last_anim >= self.anim_speed:
            self.frame_idx = (self.frame_idx + 1)
            self.frame_count += 1
            self.last_anim = now
            if self.die_frame is not None and self.frame_count >= self.die_frame:
                self.kill(aquarium)
                return

        self.x += self.dx
        self.y += self.dy

        if self.die_time and now >= self.die_time:
            self.kill(aquarium)
            return

        if self.die_offscreen:
            w = aquarium.width
            h = aquarium.height
            if self.dx > 0 and self.x > w + 2:
                self.kill(aquarium)
            elif self.dx < 0 and self.x < -self.width - 2:
                self.kill(aquarium)
            elif self.dy < 0 and self.y < -self.height:
                self.kill(aquarium)
            elif self.dy > 0 and self.y > h + 2:
                self.kill(aquarium)

    def kill(self, aquarium):
        if not self.alive:
            return
        self.alive = False
        if self.death_cb:
            self.death_cb(self, aquarium)


class Aquarium:
    def __init__(self, stdscr, classic_mode=False):
        self.stdscr = stdscr
        self.classic_mode = classic_mode
        self.entities = []
        self.paused = False
        self.running = True

        curses.curs_set(0)
        self.stdscr.nodelay(True)

        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            # Pairs: 1: Cyan, 2: Red, 3: Yellow, 4: Blue, 5: Green, 6: Magenta, 7: White, 8: Black
            curses.init_pair(1, curses.COLOR_CYAN, -1)
            curses.init_pair(2, curses.COLOR_RED, -1)
            curses.init_pair(3, curses.COLOR_YELLOW, -1)
            curses.init_pair(4, curses.COLOR_BLUE, -1)
            curses.init_pair(5, curses.COLOR_GREEN, -1)
            curses.init_pair(6, curses.COLOR_MAGENTA, -1)
            curses.init_pair(7, curses.COLOR_WHITE, -1)
            curses.init_pair(8, curses.COLOR_BLACK, -1)

        self.height, self.width = self.stdscr.getmaxyx()
        self.init_world()

    def init_world(self):
        self.entities = []
        self.add_environment()
        self.add_castle()
        self.add_seaweed_all()
        self.add_fish_all()
        self.spawn_random_object()

    def add_environment(self):
        # Tiled waterlines across screen width
        seg_len = len(WATER_LINE_SEGMENTS[0])
        repeats = (self.width // seg_len) + 2
        for i, seg in enumerate(WATER_LINE_SEGMENTS):
            tiled = seg * repeats
            e = Entity(
                name=f"water_{i}",
                etype="waterline",
                shapes=tiled,
                pos=[0, i + 5, DEPTH['water_line'] + i],
                default_color=1,
                die_offscreen=False
            )
            self.entities.append(e)

    def add_castle(self):
        c_x = max(0, self.width - 32)
        c_y = max(0, self.height - 13)
        e = Entity(
            name="castle",
            etype="castle",
            shapes=CASTLE_IMAGE.strip('\n'),
            colors=CASTLE_MASK.strip('\n'),
            pos=[c_x, c_y, DEPTH['castle']],
            default_color=8,
            die_offscreen=False
        )
        self.entities.append(e)

    def add_seaweed_all(self):
        count = max(2, self.width // 15)
        for _ in range(count):
            self.add_seaweed()

    def add_seaweed(self, dead_obj=None, aq=None):
        h = random.randint(3, 6)
        s1, s2 = "", ""
        for i in range(1, h + 1):
            if i % 2 == 1:
                s1 += "(\n"
                s2 += " )\n"
            else:
                s1 += " )\n"
                s2 += "(\n"

        x = random.randint(1, max(2, self.width - 3))
        y = max(0, self.height - h)
        speed = random.uniform(0.2, 0.4)
        life = time.time() + random.randint(480, 720)

        e = Entity(
            name=f"seaweed_{random.random()}",
            etype="seaweed",
            shapes=[s1, s2],
            pos=[x, y, DEPTH['seaweed']],
            default_color=5,
            anim_speed=speed,
            die_offscreen=False,
            die_time=life,
            death_cb=self.add_seaweed
        )
        self.entities.append(e)

    def add_fish_all(self):
        screen_size = max(1, (self.height - 9) * self.width)
        fish_count = max(2, screen_size // 350)
        for _ in range(fish_count):
            self.add_fish()

    def add_fish(self, dead_obj=None, aq=None):
        data_pool = OLD_FISH_DATA
        if not self.classic_mode and random.randint(1, 12) > 8:
            data_pool = NEW_FISH_DATA

        idx = random.randint(0, (len(data_pool) // 2) - 1) * 2
        # idx is right-facing, idx+1 is left-facing
        dir_right = (idx % 4 == 0)
        shape_str, mask_str = data_pool[idx] if dir_right else data_pool[idx + 1]

        color_mask = map_random_colors(mask_str.strip('\n'))

        speed = random.uniform(0.3, 1.2)
        if not dir_right:
            speed = -speed

        depth = random.randint(DEPTH['fish_start'], DEPTH['fish_end'])
        h_lines = shape_str.strip('\n').split('\n')
        f_h = len(h_lines)
        f_w = max(len(l) for l in h_lines)

        min_y = 9
        max_y = max(min_y + 1, self.height - f_h)
        y = random.randint(min_y, max_y)

        x = 1 - f_w if dir_right else self.width - 2

        e = Entity(
            name=f"fish_{random.random()}",
            etype="fish",
            shapes=shape_str.strip('\n'),
            colors=color_mask,
            pos=[x, y, depth],
            dx=speed,
            dy=0,
            default_color=7,
            die_offscreen=True,
            death_cb=self.add_fish
        )
        self.entities.append(e)

    def add_bubble(self, fish):
        bx = fish.x + (fish.width if fish.dx > 0 else 0)
        by = fish.y + (fish.height // 2)
        bz = fish.z - 1

        b_shapes = ['.', 'o', 'O', 'O', 'O']
        e = Entity(
            name="bubble",
            etype="bubble",
            shapes=b_shapes,
            pos=[bx, by, bz],
            dx=0,
            dy=-0.2,
            default_color=1,
            anim_speed=0.3,
            die_offscreen=True
        )
        self.entities.append(e)

    def add_splat(self, x, y, z):
        e = Entity(
            name="splat",
            etype="splat",
            shapes=[s.strip('\n') for s in SPLAT_FRAMES],
            pos=[x - 4, y - 2, z - 2],
            default_color=2,
            anim_speed=0.15,
            die_offscreen=False,
            die_frame=15
        )
        self.entities.append(e)

    def spawn_random_object(self, dead_obj=None, aq=None):
        options = [self.add_shark, self.add_ship, self.add_whale, self.add_monster, self.add_big_fish]
        spawner = random.choice(options)
        spawner()

    def add_shark(self):
        dir_idx = random.randint(0, 1)
        dir_right = (dir_idx == 0)
        speed = 1.5 if dir_right else -1.5

        x = -53 if dir_right else self.width - 2
        min_y = 9
        max_y = max(min_y + 1, self.height - 15)
        y = random.randint(min_y, max_y)

        shark_shape = SHARK_IMAGE[dir_idx].strip('\n')
        shark_mask = SHARK_MASK[dir_idx].strip('\n')

        e_shark = Entity(
            name="shark",
            etype="shark",
            shapes=shark_shape,
            colors=shark_mask,
            pos=[x, y, DEPTH['shark']],
            dx=speed,
            default_color=1,
            die_offscreen=True,
            death_cb=self.spawn_random_object
        )

        teeth_x = x + (44 if dir_right else 9)
        e_teeth = Entity(
            name="teeth",
            etype="teeth",
            shapes="*",
            pos=[teeth_x, y + 7, DEPTH['shark'] + 1],
            dx=speed,
            default_color=2,
            die_offscreen=True
        )

        self.entities.extend([e_shark, e_teeth])

    def add_ship(self):
        dir_idx = random.randint(0, 1)
        dir_right = (dir_idx == 0)
        speed = 0.8 if dir_right else -0.8
        x = -24 if dir_right else self.width - 2

        e = Entity(
            name="ship",
            etype="ship",
            shapes=SHIP_IMAGE[dir_idx].strip('\n'),
            colors=SHIP_MASK[dir_idx].strip('\n'),
            pos=[x, 0, DEPTH['water_line']],
            dx=speed,
            default_color=7,
            die_offscreen=True,
            death_cb=self.spawn_random_object
        )
        self.entities.append(e)

    def add_whale(self):
        dir_idx = random.randint(0, 1)
        dir_right = (dir_idx == 0)
        speed = 0.8 if dir_right else -0.8
        x = -18 if dir_right else self.width - 2

        spout_align = 11 if not dir_right else 1
        base_whale = WHALE_IMAGE[dir_idx].strip('\n')
        base_mask = WHALE_MASK[dir_idx].strip('\n')

        anim_frames = ["\n\n\n" + base_whale] * 4
        anim_masks = [base_mask] * 4

        for spout in WATER_SPOUT_FRAMES:
            aligned_spout = "\n".join((' ' * spout_align) + line for line in spout.split('\n'))
            anim_frames.append(aligned_spout + "\n" + base_whale)
            anim_masks.append(base_mask)

        e = Entity(
            name="whale",
            etype="whale",
            shapes=anim_frames,
            colors=anim_masks,
            pos=[x, 0, DEPTH['water_line']],
            dx=speed,
            default_color=7,
            anim_speed=0.2,
            die_offscreen=True,
            death_cb=self.spawn_random_object
        )
        self.entities.append(e)

    def add_monster(self):
        is_new = not self.classic_mode
        images = NEW_MONSTER_IMAGE if is_new else OLD_MONSTER_IMAGE
        masks = NEW_MONSTER_MASK if is_new else OLD_MONSTER_MASK

        dir_idx = random.randint(0, 1)
        dir_right = (dir_idx == 0)
        speed = 1.2 if dir_right else -1.2
        x = -54 if dir_right else self.width - 2

        frames = [f.strip('\n') for f in images[dir_idx]]
        mask_frames = [masks[dir_idx].strip('\n')] * len(frames)

        e = Entity(
            name="monster",
            etype="monster",
            shapes=frames,
            colors=mask_frames,
            pos=[x, 2, DEPTH['water_line']],
            dx=speed,
            default_color=5,
            anim_speed=0.25,
            die_offscreen=True,
            death_cb=self.spawn_random_object
        )
        self.entities.append(e)

    def add_big_fish(self):
        use_type_2 = not self.classic_mode and random.choice([True, False])
        images = BIG_FISH_2_IMAGE if use_type_2 else BIG_FISH_1_IMAGE
        masks = BIG_FISH_2_MASK if use_type_2 else BIG_FISH_1_MASK

        dir_idx = random.randint(0, 1)
        dir_right = (dir_idx == 0)
        speed = 1.5 if dir_right else -1.5
        x = -34 if dir_right else self.width - 2

        y = random.randint(9, max(10, self.height - 15))
        c_mask = map_random_colors(masks[dir_idx].strip('\n'))

        e = Entity(
            name="big_fish",
            etype="big_fish",
            shapes=images[dir_idx].strip('\n'),
            colors=c_mask,
            pos=[x, y, DEPTH['shark']],
            dx=speed,
            default_color=3,
            die_offscreen=True,
            death_cb=self.spawn_random_object
        )
        self.entities.append(e)

    def check_collisions(self):
        teeth = [e for e in self.entities if e.etype == "teeth" and e.alive]
        fish_list = [e for e in self.entities if e.etype == "fish" and e.alive]
        bubbles = [e for e in self.entities if e.etype == "bubble" and e.alive]

        # Shark teeth vs Fish collision
        for t in teeth:
            for f in fish_list:
                if f.height <= 5:
                    if abs(f.x - t.x) < 3 and abs(f.y - t.y) < 3:
                        self.add_splat(f.x, f.y, f.z)
                        f.kill(self)

        # Bubble vs Waterline collision
        for b in bubbles:
            if b.y <= 6:
                b.kill(self)

    def handle_input(self):
        try:
            ch = self.stdscr.getch()
            if ch == -1:
                return
            key = chr(ch).lower() if 0 <= ch < 256 else ''
            if key == 'q':
                self.running = False
            elif key == 'p':
                self.paused = not self.paused
            elif key == 'r':
                self.init_world()
        except Exception:
            pass

    def run(self):
        last_tick = time.time()
        while self.running:
            now = time.time()
            dt = now - last_tick
            if dt >= 0.05:
                last_tick = now
                self.handle_input()
                if not self.paused:
                    # Update entities
                    for e in list(self.entities):
                        if e.alive:
                            e.update(self)
                            # Fish bubble chance
                            if e.etype == "fish" and random.random() < 0.02:
                                self.add_bubble(e)

                    self.check_collisions()
                    # Remove dead entities
                    self.entities = [e for e in self.entities if e.alive]

                self.render()

            time.sleep(0.01)

    def render(self):
        self.height, self.width = self.stdscr.getmaxyx()
        self.stdscr.erase()

        # Sort entities by Z-depth (highest z drawn first -> lower z drawn on top)
        sorted_entities = sorted(self.entities, key=lambda e: e.z, reverse=True)

        for e in sorted_entities:
            shape = e.current_shape.strip('\n')
            color_mask = e.current_color.strip('\n') if e.current_color else None

            shape_lines = shape.split('\n')
            mask_lines = color_mask.split('\n') if color_mask else []

            for r, line in enumerate(shape_lines):
                draw_y = int(e.y) + r
                if draw_y < 0 or draw_y >= self.height - 1:
                    continue

                mask_line = mask_lines[r] if r < len(mask_lines) else ""

                for c, char in enumerate(line):
                    if char == ' ':
                        continue
                    draw_x = int(e.x) + c
                    if draw_x < 0 or draw_x >= self.width - 1:
                        continue

                    color_code = e.default_color
                    if c < len(mask_line):
                        m_char = mask_line[c]
                        if m_char in COLOR_MAP:
                            color_code = COLOR_MAP[m_char]

                    try:
                        attr = curses.color_pair(color_code)
                        self.stdscr.addch(draw_y, draw_x, char, attr)
                    except curses.error:
                        pass

        self.stdscr.refresh()


def main():
    parser = argparse.ArgumentParser(description="Asciiquarium in Python 3")
    parser.add_argument('-c', '--classic', action='store_true', help='Classic mode (Asciiquarium 1.0 species only)')
    args = parser.parse_args()

    def run_app(stdscr):
        app = Aquarium(stdscr, classic_mode=args.classic)
        app.run()

    try:
        curses.wrapper(run_app)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
