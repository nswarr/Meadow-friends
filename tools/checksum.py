#!/usr/bin/env python3
"""Write the LoROM header checksum and its complement."""
import sys

path = sys.argv[1]
rom = bytearray(open(path, "rb").read())
base = 0x7FC0
rom[base + 0x1C:base + 0x20] = b"\xff\xff\x00\x00"
total = sum(rom) & 0xFFFF
rom[base + 0x1C:base + 0x1E] = (total ^ 0xFFFF).to_bytes(2, "little")
rom[base + 0x1E:base + 0x20] = total.to_bytes(2, "little")
open(path, "wb").write(rom)
print(f"{path}: {len(rom)} bytes, checksum ${total:04X}")
