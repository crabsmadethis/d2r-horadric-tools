"""Huffman encoding/decoding tables for D2R item type codes.

Sources:
- Encode table (HUFFMAN): from d07RiV's published D2R format notes
- Decode tree (HUFFMAN_TREE): nested list, 0=left 1=right, leaf=char
- Rune names: rXX codes to human-readable names
"""

# Huffman encode table: char -> (code_value, bit_length)
HUFFMAN = {
    ' ':(1,2), '0':(223,8), '1':(31,7), '2':(12,6), '3':(91,7), '4':(95,8),
    '5':(104,8), '6':(123,7), '7':(30,5), '8':(8,6), '9':(14,5), 'a':(15,5),
    'b':(10,4), 'c':(2,5), 'd':(35,6), 'e':(3,6), 'f':(50,6), 'g':(11,5),
    'h':(24,5), 'i':(63,7), 'j':(232,9), 'k':(18,6), 'l':(23,5), 'm':(22,5),
    'n':(44,6), 'o':(127,7), 'p':(19,5), 'q':(155,8), 'r':(7,5), 's':(4,4),
    't':(6,5), 'u':(16,5), 'v':(59,7), 'w':(0,5), 'x':(28,5), 'y':(40,7),
    'z':(27,8)
}

# Huffman decode tree: [left, right] or leaf char. 0-bit=left, 1-bit=right.
HUFFMAN_TREE = [
    [
        [
            [
                ["w", "u"],
                [["8", ["y", ["5", ["j", []]]]], "h"]
            ],
            ["s", [["2", "n"], "x"]]
        ],
        [
            [["c", ["k", "f"]], "b"],
            [["t", "m"], ["9", "7"]]
        ]
    ],
    [
        " ",
        [
            [
                [["e", "d"], "p"],
                ["g", [[["z", "q"], "3"], ["v", "6"]]]
            ],
            [
                ["r", "l"],
                ["a", [["1", ["4", "0"]], ["i", "o"]]]
            ]
        ]
    ]
]

# Rune code -> human name
RUNE_NAMES = {
    'r01':'El',  'r02':'Eld', 'r03':'Tir',  'r04':'Nef', 'r05':'Eth',
    'r06':'Ith', 'r07':'Tal', 'r08':'Ral',  'r09':'Ort', 'r10':'Thul',
    'r11':'Amn', 'r12':'Sol', 'r13':'Shael','r14':'Dol', 'r15':'Hel',
    'r16':'Io',  'r17':'Lum', 'r18':'Ko',   'r19':'Fal', 'r20':'Lem',
    'r21':'Pul', 'r22':'Um',  'r23':'Mal',  'r24':'Ist', 'r25':'Gul',
    'r26':'Vex', 'r27':'Ohm', 'r28':'Lo',   'r29':'Sur', 'r30':'Ber',
    'r31':'Jah', 'r32':'Cham','r33':'Zod',
}
