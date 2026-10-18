#!/usr/bin/env python3
"""Headless libretro runner for testing the ROM.

Usage:
  run.py ROM --frames N [--core bsnes|snes9x] [--shot F[,F...]] [--press "F0-F1:PORT:BTN+BTN" ...]
         [--wav out.wav] [--ram ADDR:LEN@FRAME ...] [--out DIR]

Buttons: A B X Y L R START SELECT UP DOWN LEFT RIGHT. PORT is 1 or 2.
"""
import argparse, ctypes, os, struct, sys, wave
from ctypes import (CFUNCTYPE, POINTER, Structure, c_bool, c_char_p, c_double,
                    c_float, c_int16, c_size_t, c_uint, c_void_p)
from PIL import Image

CORES = {
    "bsnes": "/usr/lib/x86_64-linux-gnu/libretro/bsnes_mercury_accuracy_libretro.so",
    "snes9x": "/usr/lib/x86_64-linux-gnu/libretro/snes9x_libretro.so",
}
IDS = {"B": 0, "Y": 1, "SELECT": 2, "START": 3, "UP": 4, "DOWN": 5, "LEFT": 6,
       "RIGHT": 7, "A": 8, "X": 9, "L": 10, "R": 11}


class GameInfo(Structure):
    _fields_ = [("path", c_char_p), ("data", c_void_p), ("size", c_size_t), ("meta", c_char_p)]


class Geometry(Structure):
    _fields_ = [("base_width", c_uint), ("base_height", c_uint), ("max_width", c_uint),
                ("max_height", c_uint), ("aspect_ratio", c_float)]


class Timing(Structure):
    _fields_ = [("fps", c_double), ("sample_rate", c_double)]


class AVInfo(Structure):
    _fields_ = [("geometry", Geometry), ("timing", Timing)]


ENV = CFUNCTYPE(c_bool, c_uint, c_void_p)
VIDEO = CFUNCTYPE(None, c_void_p, c_uint, c_uint, c_size_t)
AUDIO = CFUNCTYPE(None, c_int16, c_int16)
AUDIO_BATCH = CFUNCTYPE(c_size_t, POINTER(c_int16), c_size_t)
POLL = CFUNCTYPE(None)
STATE = CFUNCTYPE(c_int16, c_uint, c_uint, c_uint, c_uint)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--core", default="bsnes")
    ap.add_argument("--frames", type=int, default=120)
    ap.add_argument("--shot", default="")
    ap.add_argument("--press", action="append", default=[])
    ap.add_argument("--wav", default="")
    ap.add_argument("--ram", action="append", default=[])
    ap.add_argument("--out", default="shots")
    ap.add_argument("--prefix", default="")
    ap.add_argument("--bot", default="", help="labels file: autopilot (P1 plays well, P2 mashes)")
    ap.add_argument("--log", type=int, default=600, help="bot status every N frames")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    shots = {int(s) for s in args.shot.split(",") if s}
    presses = []
    for p in args.press:
        rng, port, btns = p.split(":")
        f0, f1 = (int(v) for v in rng.split("-"))
        presses.append((f0, f1, int(port) - 1, [IDS[b] for b in btns.split("+")]))
    rams = []
    for r in args.ram:
        spec, frame = r.split("@")
        addr, ln = spec.split(":")
        rams.append((int(frame), int(addr, 16), int(ln)))

    core = ctypes.CDLL(CORES[args.core])
    st = {"fmt": 0, "frame": 0, "last": None, "audio": []}
    sysdir = ctypes.create_string_buffer(os.path.abspath(args.out).encode())
    sysdir_p = ctypes.c_char_p(ctypes.addressof(sysdir))

    def env(cmd, data):
        cmd &= 0xFFFF
        if cmd == 10:  # SET_PIXEL_FORMAT
            st["fmt"] = ctypes.cast(data, POINTER(ctypes.c_int)).contents.value
            return True
        if cmd in (9, 31):  # system / save dir
            ctypes.cast(data, POINTER(c_char_p))[0] = sysdir_p.value
            return True
        if cmd == 3:  # CAN_DUPE
            ctypes.cast(data, POINTER(c_bool))[0] = True
            return True
        if cmd == 17:  # VARIABLE_UPDATE
            ctypes.cast(data, POINTER(c_bool))[0] = False
            return True
        if cmd in (11, 16):
            return True
        return False

    def video(data, w, h, pitch):
        if not data:
            return
        buf = ctypes.string_at(data, pitch * h)
        if st["fmt"] == 1:  # XRGB8888
            img = Image.frombuffer("RGBX", (w, h), buf, "raw", "BGRX", pitch, 1).convert("RGB")
        elif st["fmt"] == 2:  # RGB565
            img = Image.frombuffer("RGB", (w, h), buf, "raw", "BGR;16", pitch, 1)
        else:  # 0RGB1555
            img = Image.frombuffer("RGB", (w, h), buf, "raw", "BGR;15", pitch, 1)
        if w >= 512 and h <= 240:
            img = img.resize((512, h * 2), Image.NEAREST)
        elif w <= 256:
            img = img.resize((w * 2, h * 2), Image.NEAREST)
        st["last"] = img

    def audio(l, r):
        st["audio"].append((l, r))

    def audio_batch(data, frames):
        st["audio"].extend(struct.unpack("<%dh" % (frames * 2), ctypes.string_at(data, frames * 4)))
        return frames

    def poll():
        pass

    def state(port, device, index, bid):
        f = st["frame"]
        if args.bot:
            ids = st["bot"].get(port, set())
            if bid == 256:
                return sum(1 << i for i in ids)
            return 1 if bid in ids else 0
        for f0, f1, p, ids in presses:
            if p == port and f0 <= f < f1:
                if bid == 256:
                    return sum(1 << i for i in ids)
                if bid in ids:
                    return 1
        return 0

    cbs = [ENV(env), VIDEO(video), AUDIO(audio), AUDIO_BATCH(audio_batch), POLL(poll), STATE(state)]
    core.retro_set_environment(cbs[0])
    core.retro_set_video_refresh(cbs[1])
    core.retro_set_audio_sample(cbs[2])
    core.retro_set_audio_sample_batch(cbs[3])
    core.retro_set_input_poll(cbs[4])
    core.retro_set_input_state(cbs[5])
    core.retro_init()
    rom = open(args.rom, "rb").read()
    rbuf = ctypes.create_string_buffer(rom, len(rom))
    gi = GameInfo(args.rom.encode(), ctypes.cast(rbuf, c_void_p), len(rom), None)
    core.retro_load_game.restype = c_bool
    if not core.retro_load_game(ctypes.byref(gi)):
        sys.exit("load failed")
    for port in (0, 1):
        core.retro_set_controller_port_device(port, 1)
    av = AVInfo()
    core.retro_get_system_av_info(ctypes.byref(av))
    core.retro_get_memory_data.restype = c_void_p
    core.retro_get_memory_size.restype = c_size_t

    bot = Bot(args.bot, core) if args.bot else None
    for f in range(args.frames):
        st["frame"] = f
        if bot:
            st["bot"] = bot.step(f, args.log)
        core.retro_run()
        if f in shots and st["last"] is not None:
            st["last"].save(os.path.join(args.out, f"{args.prefix}f{f:05d}.png"))
        for rf, addr, ln in rams:
            if rf == f:
                p = core.retro_get_memory_data(2)
                mem = ctypes.string_at(p + addr, ln)
                print(f"ram@{f} {addr:04x}: " + " ".join(f"{b:02x}" for b in mem))

    if args.wav:
        a = st["audio"]
        with wave.open(args.wav, "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(int(av.timing.sample_rate))
            w.writeframes(struct.pack("<%dh" % len(a), *a))
        peak = max((abs(v) for v in a), default=0)
        print(f"audio: {len(a)//2} frames @ {av.timing.sample_rate:.0f} Hz, peak {peak}")
    core.retro_unload_game()
    core.retro_deinit()


class Bot:
    """P1 walks to the nearest item and presses the balloon's button; P2 mashes like a toddler."""
    FACE = ["A", "B", "X", "Y"]

    def __init__(self, labels, core):
        self.lab = {}
        for line in open(labels):
            _, addr, name = line.split()
            self.lab[name.lstrip(".")] = int(addr, 16)
        self.core = core
        self.rng = __import__("random").Random(1)
        self.stats = {"pops": [0, 0], "parties": 0, "last_party": 0, "max_lag": 0}
        self.prev_prog = 0

    def ram(self):
        p = self.core.retro_get_memory_data(2)
        return ctypes.string_at(p, 0x2000)

    def step(self, f, log_every):
        m = self.ram()
        L = self.lab
        out = {0: set(), 1: set()}
        P, I = L["players"], L["items"]
        if m[L["state"]] != 2:
            if f % 40 == 0:
                out[0].add(IDS["A"])
            if f % 40 == 20:
                out[1].add(IDS["B"])
            return out
        pl = [m[P + i * 32:P + i * 32 + 32] for i in range(2)]
        lag = ((m[L["nmi_count"]] - m[L["frame"]]) & 0xFF)
        self.stats["max_lag"] = max(self.stats["max_lag"], lag)
        party = m[L["party_t"]] | (m[L["party_t"] + 1] << 8)
        if party and not self.stats["last_party"]:
            self.stats["parties"] += 1
        self.stats["last_party"] = party
        p1 = pl[0]
        if not p1[0] and f % 30 == 0:
            out[0].add(IDS["A"])
        if p1[0]:
            px, py = p1[3] + 16, p1[5] + 20
            if p1[13] in (1, 2) and f % 10 == 0:
                out[0].add(IDS[self.FACE[p1[14]]])
            best = None
            for k in range(3):
                it = m[I + k * 8:I + k * 8 + 8]
                if it[0]:
                    d = abs(it[2] + 8 - px) + abs(it[3] + 8 - py)
                    if best is None or d < best[0]:
                        best = (d, it[2] + 8, it[3] + 8)
            if best:
                _, tx, ty = best
                if tx > px + 2: out[0].add(IDS["RIGHT"])
                if tx < px - 2: out[0].add(IDS["LEFT"])
                if ty > py + 2: out[0].add(IDS["DOWN"])
                if ty < py - 2: out[0].add(IDS["UP"])
        if pl[1][0]:
            if f % 9 == 0:
                out[1].add(IDS[self.rng.choice(self.FACE)])
            if (f // 45) % 2 == 0:
                out[1].add(IDS[["UP", "DOWN", "LEFT", "RIGHT"][(f // 90) % 4]])
        if f % log_every == 0:
            q = lambda p: f"need={p[19]} unlock={p[20]} streak={p[21]} bstate={p[13]}"
            print(f"f{f:6d} prog={m[L['progress']]} tod={m[L['tod']]} parties={self.stats['parties']} "
                  f"lag={self.stats['max_lag']} | P1 {q(pl[0])} | P2 {q(pl[1])}")
        return out


if __name__ == "__main__":
    main()
