"""SPC700 sound driver for Meadow Friends.

A tiny assembler (only the opcodes the driver uses), the driver itself, the
instrument table, a note pitch table and BRR-encoded single-cycle waveforms.

Protocol with the 65816 (after the IPL upload jumps to $0200):
  driver writes $F5 = $5A once it is ready.
  CPU writes port1 = instrument, port2 = note (0 = C2), port3 = voice (0-7),
  then port0 = sequence number (changes every command).
  driver plays the sound and echoes the sequence number on port0.
"""
import math

ORG = 0x0200


class Asm:
    def __init__(self, org):
        self.org = org
        self.code = bytearray()
        self.labels = {}
        self.fix = []

    def pc(self):
        return self.org + len(self.code)

    def L(self, name):
        assert name not in self.labels, name
        self.labels[name] = self.pc()

    def b(self, *bs):
        for v in bs:
            self.code.append(v & 0xFF)

    def _abs(self, name):
        self.fix.append(("abs", len(self.code), name))
        self.code += b"\0\0"

    def _rel(self, name):
        self.fix.append(("rel", len(self.code), name))
        self.code += b"\0"

    def resolve(self):
        for kind, off, name in self.fix:
            if isinstance(name, tuple):
                target = self.labels[name[0]] + name[1]
            else:
                target = self.labels[name]
            if kind == "abs":
                self.code[off] = target & 0xFF
                self.code[off + 1] = target >> 8
            else:
                d = target - (self.org + off + 1)
                assert -128 <= d <= 127, (name, d)
                self.code[off] = d & 0xFF
        return bytes(self.code)

    # --- moves
    def mov_a_imm(self, v): self.b(0xE8, v)
    def mov_x_imm(self, v): self.b(0xCD, v)
    def mov_y_imm(self, v): self.b(0x8D, v)
    def mov_a_dp(self, d): self.b(0xE4, d)
    def mov_dp_a(self, d): self.b(0xC4, d)
    def mov_x_dp(self, d): self.b(0xF8, d)
    def mov_y_dp(self, d): self.b(0xEB, d)
    def mov_dp_imm(self, d, v): self.b(0x8F, v, d)
    def mov_a_dpx(self, d): self.b(0xF4, d)
    def mov_dpx_a(self, d): self.b(0xD4, d)
    def mov_a_absx(self, lbl): self.b(0xF5); self._abs(lbl)
    def mov_a_absy(self, lbl): self.b(0xF6); self._abs(lbl)
    def mov_a_x(self): self.b(0x7D)
    def mov_x_a(self): self.b(0x5D)
    def mov_y_a(self): self.b(0xFD)
    def mov_sp_x(self): self.b(0xBD)
    def mov_xinc_a(self): self.b(0xAF)
    # --- alu
    def cmp_a_imm(self, v): self.b(0x68, v)
    def cmp_a_dp(self, d): self.b(0x64, d)
    def cmp_x_imm(self, v): self.b(0xC8, v)
    def and_a_imm(self, v): self.b(0x28, v)
    def and_a_dp(self, d): self.b(0x24, d)
    def or_a_imm(self, v): self.b(0x08, v)
    def or_a_dp(self, d): self.b(0x04, d)
    def eor_a_imm(self, v): self.b(0x48, v)
    def adc_a_imm(self, v): self.b(0x88, v)
    def adc_a_dpx(self, d): self.b(0x94, d)
    def asl_a(self): self.b(0x1C)
    def dec_a(self): self.b(0x9C)
    def inc_x(self): self.b(0x3D)
    def clrc(self): self.b(0x60)
    # --- flow
    def bra(self, l): self.b(0x2F); self._rel(l)
    def beq(self, l): self.b(0xF0); self._rel(l)
    def bne(self, l): self.b(0xD0); self._rel(l)
    def bmi(self, l): self.b(0x30); self._rel(l)
    def dbnz_y(self, l): self.b(0xFE); self._rel(l)
    def call(self, l): self.b(0x3F); self._abs(l)
    def ret(self): self.b(0x6F)


# Direct-page variables
LAST, NON, INST, NOTE, VOICE, VB, SX = range(7)
SLIDES = 0x10  # 8 voices x 8 bytes: pitch lo, pitch hi, delta lo, delta hi, ticks


def dsp_write_a_to(a, reg_from_vb_or):
    """mov a,VB ; or a,#n ; mov $f2,a  (selects voice register n)."""
    a.mov_a_dp(VB)
    if reg_from_vb_or:
        a.or_a_imm(reg_from_vb_or)
    a.mov_dp_a(0xF2)


def build_driver(dir_page):
    a = Asm(ORG)
    a.L("start")
    a.mov_x_imm(0xCF)
    a.mov_sp_x()
    a.mov_x_imm(0)
    a.L("init")
    a.mov_a_absx("dsp_init")
    a.bmi("init_done")
    a.mov_dp_a(0xF2)
    a.inc_x()
    a.mov_a_absx("dsp_init")
    a.mov_dp_a(0xF3)
    a.inc_x()
    a.bra("init")
    a.L("init_done")
    a.mov_a_imm(0)
    a.mov_x_imm(0)
    a.L("clr")
    a.mov_xinc_a()
    a.cmp_x_imm(0x50)
    a.bne("clr")
    a.mov_dp_imm(0xFA, 64)      # timer 0: 8 kHz / 64 = 125 Hz slide ticks
    a.mov_dp_imm(0xF1, 0x31)    # start timer 0, clear input ports
    a.mov_dp_imm(0xF4, 0)
    a.mov_dp_imm(0xF5, 0x5A)    # ready signature

    a.L("main")
    a.mov_a_dp(0xFD)
    a.beq("chk")
    a.call("slides")
    a.L("chk")
    a.mov_a_dp(0xF4)
    a.cmp_a_dp(0xF4)            # read twice: ignore a value mid-write
    a.bne("main")
    a.cmp_a_dp(LAST)
    a.beq("main")
    a.mov_dp_a(LAST)
    a.mov_a_dp(0xF5)
    a.asl_a(); a.asl_a(); a.asl_a()
    a.mov_dp_a(INST)
    a.mov_a_dp(0xF6)
    a.mov_dp_a(NOTE)
    a.mov_a_dp(0xF7)
    a.and_a_imm(7)
    a.mov_dp_a(VOICE)
    a.call("play")
    a.mov_a_dp(LAST)
    a.mov_dp_a(0xF4)
    a.bra("main")

    # play: INST = instrument*8, NOTE, VOICE
    a.L("play")
    a.mov_a_dp(VOICE)
    a.asl_a(); a.asl_a(); a.asl_a()
    a.mov_dp_a(SX)
    a.asl_a()
    a.mov_dp_a(VB)
    a.mov_y_dp(INST)
    for reg, field in ((4, 0), (5, 1), (6, 2), (0, 3), (1, 3)):
        dsp_write_a_to(a, reg)
        a.mov_a_absy(("inst", field))
        a.mov_dp_a(0xF3)
    a.mov_a_absy(("inst", 4))
    a.beq("tonal")
    a.or_a_imm(0x20)            # FLG: keep echo writes disabled, set noise clock
    a.mov_dp_imm(0xF2, 0x6C)
    a.mov_dp_a(0xF3)
    a.mov_x_dp(VOICE)
    a.mov_a_absx("bits")
    a.or_a_dp(NON)
    a.bra("setnon")
    a.L("tonal")
    a.mov_x_dp(VOICE)
    a.mov_a_absx("bits")
    a.eor_a_imm(0xFF)
    a.and_a_dp(NON)
    a.L("setnon")
    a.mov_dp_a(NON)
    a.mov_dp_imm(0xF2, 0x3D)
    a.mov_dp_a(0xF3)
    a.mov_x_dp(SX)
    for field, off in ((5, 2), (6, 3), (7, 4)):
        a.mov_a_absy(("inst", field))
        a.mov_dpx_a(SLIDES + off)
    a.mov_a_dp(NOTE)
    a.asl_a()
    a.mov_y_a()
    a.mov_a_absy("notes")
    a.mov_dpx_a(SLIDES + 0)
    dsp_write_a_to(a, 2)
    a.mov_a_dpx(SLIDES + 0)
    a.mov_dp_a(0xF3)
    a.mov_a_absy(("notes", 1))
    a.mov_dpx_a(SLIDES + 1)
    dsp_write_a_to(a, 3)
    a.mov_a_dpx(SLIDES + 1)
    a.mov_dp_a(0xF3)
    a.mov_x_dp(VOICE)
    a.mov_a_absx("bits")
    a.mov_dp_imm(0xF2, 0x4C)    # KON
    a.mov_dp_a(0xF3)
    a.mov_y_imm(48)             # let the DSP latch KON before the next write
    a.L("dly")
    a.dbnz_y("dly")
    a.ret()

    # slides: once per timer tick, move each sliding voice's pitch
    a.L("slides")
    a.mov_x_imm(0)
    a.L("sl")
    a.mov_a_dpx(SLIDES + 4)
    a.beq("sn")
    a.dec_a()
    a.mov_dpx_a(SLIDES + 4)
    a.clrc()
    a.mov_a_dpx(SLIDES + 0)
    a.adc_a_dpx(SLIDES + 2)
    a.mov_dpx_a(SLIDES + 0)
    a.mov_a_dpx(SLIDES + 1)
    a.adc_a_dpx(SLIDES + 3)
    a.and_a_imm(0x3F)
    a.mov_dpx_a(SLIDES + 1)
    a.mov_a_x(); a.asl_a(); a.or_a_imm(2); a.mov_dp_a(0xF2)
    a.mov_a_dpx(SLIDES + 0); a.mov_dp_a(0xF3)
    a.mov_a_x(); a.asl_a(); a.or_a_imm(3); a.mov_dp_a(0xF2)
    a.mov_a_dpx(SLIDES + 1); a.mov_dp_a(0xF3)
    a.L("sn")
    a.mov_a_x()
    a.clrc()
    a.adc_a_imm(8)
    a.mov_x_a()
    a.cmp_x_imm(0x40)
    a.bne("sl")
    a.ret()

    # --- data
    a.L("bits")
    a.b(1, 2, 4, 8, 16, 32, 64, 128)
    a.L("dsp_init")
    init = [(0x6C, 0xE0), (0x0C, 0x58), (0x1C, 0x58), (0x2C, 0), (0x3C, 0),
            (0x4C, 0), (0x5C, 0xFF), (0x2D, 0), (0x3D, 0), (0x4D, 0),
            (0x5D, dir_page), (0x6D, 0xFE), (0x7D, 0), (0x0D, 0)]
    init += [((i << 4) | 0x0F, 0) for i in range(8)]
    init += [((v << 4) | r, 0) for v in range(8) for r in (0, 1)]
    init += [(0x5C, 0), (0x6C, 0x20)]
    for r, v in init:
        a.b(r, v)
    a.b(0xFF)
    a.L("inst")
    for row in INSTRUMENTS:
        a.b(*row)
    a.L("notes")
    for n in range(72):
        f = 65.406 * 2 ** (n / 12)
        p = min(0x3FFF, round(f * 4096 * CYCLE / 32000))
        a.b(p & 0xFF, p >> 8)
    return a


CYCLE = 32  # samples per waveform cycle

# instrument rows: srcn, adsr1, adsr2, volume, noise clock (0 = tonal),
#                  slide delta lo, slide delta hi, slide ticks (125 Hz)
def _slide(d):
    d &= 0xFFFF
    return d & 0xFF, d >> 8


INSTRUMENTS = [
    (0, 0x8F, 0xF3, 0x48, 0, 0, 0, 0),              # 0 chime: sine, ~0.8 s ring
    (1, 0x8F, 0xF8, 0x34, 0, *_slide(36), 14),      # 1 boop: soft square, rising
    (0, 0x8F, 0xFB, 0x58, 0x1C, 0, 0, 0),           # 2 pop: noise burst
    (1, 0x8F, 0xF6, 0x34, 0, *_slide(-22), 18),     # 3 boing: falling square
    (0, 0x8F, 0xF4, 0x2C, 0, *_slide(16), 30),      # 4 whoo: balloon arriving
    (3, 0x8F, 0xF4, 0x3C, 0, 0, 0, 0),              # 5 note: organ, jingle melody
    (2, 0x8F, 0xF2, 0x50, 0, 0, 0, 0),              # 6 bass: triangle
    (0, 0x8F, 0xF6, 0x34, 0, *_slide(28), 10),      # 7 spark: bright rising sine
]


def waveforms():
    out = []
    n = CYCLE
    sine = [math.sin(2 * math.pi * i / n) for i in range(n)]
    out.append(sine)
    sq = []
    for i in range(n):
        s = math.sin(2 * math.pi * i / n)
        sq.append(max(-1, min(1, s * 2.2)) * 0.85)
    out.append(sq)
    tri = [(1 - 4 * abs(((i + n / 4) % n) / n - 0.5)) for i in range(n)]
    out.append(tri)
    organ = [0.7 * math.sin(2 * math.pi * i / n) + 0.3 * math.sin(4 * math.pi * i / n) for i in range(n)]
    out.append(organ)
    return out


def brr_encode_loop(samples):
    """Filter-0 BRR at range 12: nibble n decodes to n*2048. Exact, so loops are clean."""
    assert len(samples) % 16 == 0
    blocks = []
    nblocks = len(samples) // 16
    for bi in range(nblocks):
        hdr = (12 << 4) | 0x02 | (1 if bi == nblocks - 1 else 0)
        nib = []
        for s in samples[bi * 16:(bi + 1) * 16]:
            v = max(-7, min(7, round(s * 7)))
            nib.append(v & 0xF)
        data = bytes((nib[i] << 4) | nib[i + 1] for i in range(0, 16, 2))
        blocks.append(bytes([hdr]) + data)
    return b"".join(blocks)


def build():
    # first pass to learn the code size, then place the sample directory after it
    probe = build_driver(0).resolve()
    end = ORG + len(probe)
    dir_page = (end + 0xFF) >> 8
    a = build_driver(dir_page)
    code = a.resolve()
    dir_addr = dir_page << 8
    waves = [brr_encode_loop(w) for w in waveforms()]
    sample_base = dir_addr + 4 * len(waves)
    directory = bytearray()
    blob = bytearray()
    for w in waves:
        addr = sample_base + len(blob)
        directory += bytes([addr & 0xFF, addr >> 8, addr & 0xFF, addr >> 8])
        blob += w
    image = bytearray(code)
    image += b"\0" * (dir_addr - (ORG + len(image)))
    image += directory + blob
    return bytes(image)


if __name__ == "__main__":
    img = build()
    print(len(img), "bytes")
