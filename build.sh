#!/bin/sh
# Build meadow-friends.sfc: generate assets, assemble, link, fix the header checksum.
set -e
cd "$(dirname "$0")"
python3 tools/gen.py
ca65 --cpu 65816 -g -I build --bin-include-dir build -o build/main.o src/main.s
ld65 -C src/snes.cfg -o build/meadow-friends.sfc -m build/map.txt -Ln build/labels.txt build/main.o
python3 tools/checksum.py build/meadow-friends.sfc
