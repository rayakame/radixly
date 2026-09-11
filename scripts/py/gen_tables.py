# Copyright (c) 2026-present rayakame
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""Generate the committed lookup-table headers for the C codecs."""

from __future__ import annotations

import itertools
import pathlib
import typing

CURRENT_PATH: typing.Final[pathlib.Path] = pathlib.Path(__file__).resolve()
REPO_ROOT: typing.Final[pathlib.Path] = CURRENT_PATH.parent.parent.parent
CURRENT_RELATIVE_PATH: typing.Final[pathlib.Path] = CURRENT_PATH.relative_to(REPO_ROOT)
PACKAGE_ROOT: typing.Final[pathlib.Path] = REPO_ROOT / "src" / "radixly"
BITS_PER_BYTE: typing.Final = 8

BASE_32768_PATH: typing.Final[pathlib.Path] = PACKAGE_ROOT / "base32768" / "_tables.h"
BASE_32768_BITS_PER_CHAR: typing.Final = 15
BASE_2048_PATH: typing.Final[pathlib.Path] = PACKAGE_ROOT / "base2048" / "_tables.h"
BASE_2048_BITS_PER_CHAR: typing.Final = 11
BASE_65536_PATH: typing.Final[pathlib.Path] = PACKAGE_ROOT / "base65536" / "_tables.h"
BASE_65536_BLOCK_SIZE: typing.Final = 256

# The same MIT block every source file carries, so regeneration keeps it.
_LICENSE_HEADER: typing.Final[tuple[str, ...]] = (
    "/*",
    " * Copyright (c) 2026-present rayakame",
    " *",
    " * Permission is hereby granted, free of charge, to any person obtaining a copy",
    ' * of this software and associated documentation files (the "Software"), to deal',
    " * in the Software without restriction, including without limitation the rights",
    " * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell",
    " * copies of the Software, and to permit persons to whom the Software is",
    " * furnished to do so, subject to the following conditions:",
    " *",
    " * The above copyright notice and this permission notice shall be included in all",
    " * copies or substantial portions of the Software.",
    " *",
    ' * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR',
    " * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,",
    " * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE",
    " * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER",
    " * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,",
    " * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE",
    " * SOFTWARE.",
    " */",
)
# Alphabet data from qntm's base32768 (github.com/qntm/base32768), MIT, copyright qntm.
BASE_32768_PAIR_STRINGS: typing.Final[tuple[str, ...]] = (
    "ҠҿԀԟڀڿݠޟ߀ߟကဟႠႿᄀᅟᆀᆟᇠሿበቿዠዿጠጿᎠᏟᐠᙟᚠᛟកសᠠᡟᣀᣟᦀᦟ᧠᧿ᨠᨿᯀᯟᰀᰟᴀᴟ⇠⇿⋀⋟⍀⏟␀␟─❟➀➿⠀⥿⦠⦿⨠⩟⪀⪿⫠⭟ⰀⰟⲀⳟⴀⴟⵀⵟ⺠⻟㇀㇟㐀䶟䷀龿ꀀꑿ꒠꒿ꔀꗿꙀꙟꚠꛟ꜀ꝟꞀꞟꡀꡟ",
    "ƀƟɀʟ",
)
# Alphabet data from qntm's base2048 (github.com/qntm/base2048), MIT, copyright qntm.
BASE_2048_PAIR_STRINGS: typing.Final[tuple[str, ...]] = (
    "89AZazÆÆÐÐØØÞßææððøøþþĐđĦħııĸĸŁłŊŋŒœŦŧƀƟƢƮƱǃǝǝǤǥǶǷȜȝȠȥȴʯͰͳͶͷͻͽͿͿΑΡΣΩαωϏϏϗϯϳϳϷϸϺϿЂЂЄІЈЋЏИКикяђђєіјћџѵѸҁҊӀӃӏӔӕӘәӠӡӨөӶӷӺԯԱՖաֆאתװײؠءاؿفي٠٩ٮٯٱٴٹڿہہۃےەەۮۼۿۿܐܐܒܯݍޥޱޱ߀ߪࠀࠕࡀࡘࡠࡪࢠࢴࢶࢽऄनपरलळवहऽऽॐॐॠॡ०९ॲঀঅঌএঐওনপরললশহঽঽৎৎৠৡ০ৱ৴৹ৼৼਅਊਏਐਓਨਪਰਲਲਵਵਸਹੜੜ੦੯ੲੴઅઍએઑઓનપરલળવહઽઽૐૐૠૡ૦૯ૹૹଅଌଏଐଓନପରଲଳଵହଽଽୟୡ୦୯ୱ୷ஃஃஅஊஎஐஒஓககஙசஜஜஞடணதநபமஹௐௐ௦௲అఌఎఐఒనపహఽఽౘౚౠౡ౦౯౸౾ಀಀಅಌಎಐಒನಪಳವಹಽಽೞೞೠೡ೦೯ೱೲഅഌഎഐഒഺഽഽൎൎൔൖ൘ൡ൦൸ൺൿඅඖකනඳරලලවෆ෦෯กะาาเๅ๐๙ກຂຄຄງຈຊຊຍຍດທນຟມຣລລວວສຫອະາາຽຽເໄ໐໙ໞໟༀༀ༠༳ཀགངཇཉཌཎདནབམཛཝཨཪཬྈྌကဥဧဪဿ၉ၐၕ",  # ruff: ignore[ambiguous-unicode-character-string]
    "07",
)
# Block data from qntm's base65536 (github.com/qntm/base65536), MIT, copyright qntm.
BASE_65536_PAIR_STRINGS: typing.Final[tuple[str, ...]] = (
    "㐀䳿一黿ꄀꏿꔀꗿ𐘀𐛿𒀀𒋿𓀀𓏿𔐀𔗿𖠀𖧿𠀀𨗿",
    "ᔀᗿ",
)


class IndentWriter:
    """Indent writer used for dynamically generate files."""

    def __init__(self, file_path: pathlib.Path, *, indent_char: str = " ", indent_amount: int = 4) -> None:
        """Construct a new indent writer object."""
        self.file_path: pathlib.Path = file_path
        self.lines: list[tuple[str, int]] = []
        self.indent_char: str = indent_char
        self.indent_amount: int = indent_amount

    def write_line(self, text: str, indent_depth: int = 0) -> None:
        """Write a line with a new line character at the end to the buffer."""
        self.lines.append((text + "\n", indent_depth))

    def write_blank(self) -> None:
        """Write a blank empty line to the buffer."""
        self.lines.append(("\n", 0))

    def write_file(self) -> None:
        """Write content to file."""
        with self.file_path.open("w", encoding="utf-8", newline="\n") as file:
            for line in self.lines:
                indent: str = (self.indent_char * self.indent_amount) * line[1]
                file.write(indent + line[0])


def _expand(pair_string: str) -> tuple[int, ...]:
    """Flatten inclusive code point ranges, two characters per range."""
    repertoire: list[int] = []
    for i in range(0, len(pair_string), 2):
        first, last = ord(pair_string[i]), ord(pair_string[i + 1])
        repertoire.extend(range(first, last + 1))
    return tuple(repertoire)


def _build_bit_tables(pair_strings: tuple[str, ...], bits_per_char: int) -> dict[int, tuple[int, ...]]:
    """Repertoires keyed by width: the full width, then one byte narrower per extra pair string."""
    return {bits_per_char - BITS_PER_BYTE * r: _expand(pair_string) for r, pair_string in enumerate(pair_strings)}


def _verify_bit_tables(lookup_e: dict[int, tuple[int, ...]], *, min_char: int, max_char: int) -> None:
    """Every width holds exactly 2**width distinct code points, disjoint across widths and inside the C bounds."""
    seen: set[int] = set()
    for width, repertoire in lookup_e.items():
        assert len(repertoire) == 1 << width, (
            f"{width}-bit repertoire has {len(repertoire)} code points, expected {1 << width}"
        )
        assert len(set(repertoire)) == len(repertoire), f"{width}-bit repertoire contains duplicate code points"
        overlap = seen & set(repertoire)
        assert not overlap, f"repertoires overlap: {sorted(hex(cp) for cp in overlap)}"
        seen.update(repertoire)
        for cp in repertoire:
            assert min_char <= cp <= max_char, f"code point U+{cp:04X} outside [U+{min_char:04X}, U+{max_char:04X}]"


def _build_base65536_tables() -> tuple[tuple[int, ...], int]:
    """Block starts of the 16-bit repertoire, in order, and the start of the 8-bit tail block."""
    full, tail = (_expand(pair_string) for pair_string in BASE_65536_PAIR_STRINGS)
    assert len(full) == 1 << 16, f"16-bit repertoire has {len(full)} code points, expected 65536"
    assert len(tail) == 1 << BITS_PER_BYTE, f"8-bit repertoire has {len(tail)} code points, expected 256"
    starts = full[::BASE_65536_BLOCK_SIZE]
    for k, start in enumerate(starts):
        assert start % BASE_65536_BLOCK_SIZE == 0, f"block {k} starts at U+{start:05X}, not 256-aligned"
        block = full[k * BASE_65536_BLOCK_SIZE : (k + 1) * BASE_65536_BLOCK_SIZE]
        assert block == tuple(range(start, start + BASE_65536_BLOCK_SIZE)), f"block {k} is not contiguous"
    assert starts == tuple(sorted(starts)), "blocks must ascend so the first astral index splits the table"
    assert tail[0] % BASE_65536_BLOCK_SIZE == 0, f"tail block starts at U+{tail[0]:04X}, not 256-aligned"
    assert tail == tuple(range(tail[0], tail[0] + BASE_65536_BLOCK_SIZE)), "tail block is not contiguous"
    assert not set(full) & set(tail), "tail block overlaps the 16-bit repertoire"
    for cp in (*full, *tail):
        assert cp <= 0x10FFFF, f"code point U+{cp:06X} beyond Unicode"
        assert not 0xD800 <= cp <= 0xDFFF, f"surrogate U+{cp:04X} in the repertoire"
    return starts, tail[0]


def _write_header(writer: IndentWriter, guard: str, source: str) -> None:
    for line in _LICENSE_HEADER:
        writer.write_line(line)
    writer.write_line("//")
    writer.write_line(f"// Auto generated by {CURRENT_RELATIVE_PATH}")
    writer.write_line(f"// {source}")
    writer.write_line("//")
    writer.write_line(f"#ifndef {guard}")
    writer.write_line(f"#define {guard}")
    writer.write_line("#include <stdint.h>")
    writer.write_blank()


def _write_array(writer: IndentWriter, ctype: str, name: str, values: tuple[int, ...], *, digits: int = 4) -> None:
    writer.write_line(f"static const {ctype} {name}[{len(values)}] = {{")
    for chunk in itertools.batched(values, 14):
        writer.write_line(", ".join(f"0x{cp:0{digits}X}" for cp in chunk) + ",", indent_depth=1)
    writer.write_line("};")
    writer.write_blank()


def write_base_32768_table() -> None:
    """Generate src/radixly/base32768/_tables.h from qntm's repertoire."""
    lookup_e = _build_bit_tables(BASE_32768_PAIR_STRINGS, BASE_32768_BITS_PER_CHAR)
    _verify_bit_tables(lookup_e, min_char=0x100, max_char=0xFFFF)

    writer = IndentWriter(BASE_32768_PATH)
    _write_header(
        writer,
        "RADIXLY_BASE32768_TABLES_H",
        "Alphabet data copied from qntm's base32768 (github.com/qntm/base32768), MIT licensed, copyright qntm.",
    )
    _write_array(writer, "uint16_t", "RADIXLY_B32768_FWD15", lookup_e[BASE_32768_BITS_PER_CHAR])
    _write_array(writer, "uint16_t", "RADIXLY_B32768_FWD7", lookup_e[BASE_32768_BITS_PER_CHAR - BITS_PER_BYTE])
    writer.write_line("#endif")
    writer.write_file()


def write_base_2048_table() -> None:
    """Generate src/radixly/base2048/_tables.h from qntm's repertoire."""
    lookup_e = _build_bit_tables(BASE_2048_PAIR_STRINGS, BASE_2048_BITS_PER_CHAR)
    # The repertoire dips into ASCII, so the C cannot assume a 2-byte string; it stays under U+1100.
    _verify_bit_tables(lookup_e, min_char=0x20, max_char=0x10FF)

    writer = IndentWriter(BASE_2048_PATH)
    _write_header(
        writer,
        "RADIXLY_BASE2048_TABLES_H",
        "Alphabet data copied from qntm's base2048 (github.com/qntm/base2048), MIT licensed, copyright qntm.",
    )
    _write_array(writer, "uint16_t", "RADIXLY_B2048_FWD11", lookup_e[BASE_2048_BITS_PER_CHAR])
    _write_array(writer, "uint16_t", "RADIXLY_B2048_FWD3", lookup_e[BASE_2048_BITS_PER_CHAR - BITS_PER_BYTE])
    writer.write_line("#endif")
    writer.write_file()


def write_base_65536_table() -> None:
    """Generate src/radixly/base65536/_tables.h from qntm's block layout."""
    starts, pad_start = _build_base65536_tables()
    first_astral = next(k for k, start in enumerate(starts) if start > 0xFFFF)

    writer = IndentWriter(BASE_65536_PATH)
    _write_header(
        writer,
        "RADIXLY_BASE65536_TABLES_H",
        "Block data copied from qntm's base65536 (github.com/qntm/base65536), MIT licensed, copyright qntm.",
    )
    writer.write_line("enum {")
    writer.write_line(f"RADIXLY_B65536_PAD_START = 0x{pad_start:04X},", indent_depth=1)
    writer.write_line(f"RADIXLY_B65536_FIRST_ASTRAL_BLOCK = {first_astral},", indent_depth=1)
    writer.write_line("};")
    writer.write_blank()
    _write_array(writer, "uint32_t", "RADIXLY_B65536_BLOCK_START", starts, digits=5)
    writer.write_line("#endif")
    writer.write_file()


if __name__ == "__main__":
    write_base_32768_table()
    write_base_2048_table()
    write_base_65536_table()
