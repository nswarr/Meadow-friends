; Meadow Friends - a first SNES game for small hands.
;
; Walk your animal around the meadow with the d-pad to pick up fruit and
; stars. Balloons float down showing a button; press it to pop. Nothing can
; be lost: every press makes a sound and a little animation, and the balloon
; rules quietly adapt to each player.
;
; Conventions: native mode, DB = $00, D = $0000. Routines run with an 8-bit
; accumulator and 16-bit index registers (A8/I16) unless marked otherwise,
; and preserve X and Y unless they say otherwise.

.p816
.smart -

; ---------------------------------------------------------------- hardware
INIDISP  = $2100
OBSEL    = $2101
BGMODE   = $2105
BG1SC    = $2107
BG2SC    = $2108
BG12NBA  = $210B
BG1VOFS  = $210E
BG2VOFS  = $2110
VMAIN    = $2115
VMADDL   = $2116
CGADD    = $2121
TM       = $212C
TS       = $212D
SETINI   = $2133
APUIO0   = $2140
APUIO1   = $2141
APUIO2   = $2142
APUIO3   = $2143
WMDATA   = $2180
WMADDL   = $2181
NMITIMEN = $4200
WRIO     = $4201
WRMPYA   = $4202
WRMPYB   = $4203
MDMAEN   = $420B
HDMAEN   = $420C
RDNMI    = $4210
HVBJOY   = $4212
RDMPYH   = $4217
JOY1L    = $4218
JOY2L    = $421A
DMAP0    = $4300
BBAD0    = $4301
A1T0L    = $4302
A1B0     = $4304
DAS0L    = $4305

VRAM_BG1MAP = $4000
VRAM_BG2MAP = $4400
VRAM_OBJ    = $6000

; joypad word: B Y Sel St Up Dn Lt Rt | A X L R
BTN_B      = $8000
BTN_Y      = $4000
BTN_SELECT = $2000
BTN_START  = $1000
BTN_UP     = $0800
BTN_DOWN   = $0400
BTN_LEFT   = $0200
BTN_RIGHT  = $0100
BTN_A      = $0080
BTN_X      = $0040
BTN_L      = $0020
BTN_R      = $0010
BTN_FACE   = BTN_A | BTN_B | BTN_X | BTN_Y

; ---------------------------------------------------------------- sound
INST_CHIME = 0
INST_BOOP  = 1
INST_POP   = 2
INST_BOING = 3
INST_WHOO  = 4
INST_NOTE  = 5
INST_BASS  = 6
INST_SPARK = 7
V_CHIME_A  = 2
V_POP      = 4
V_WHOO     = 5
V_MEL      = 6
V_BASS     = 7

; ---------------------------------------------------------------- game
ST_TITLE     = 0
ST_TITLE_OUT = 1
ST_PLAY      = 2

SPEED = $0180          ; 1.5 px per frame
XMAX  = 224 << 8
YMIN  = 60 << 8
YMAX  = 144 << 8
HOP_LEN = 18
PARTY_LEN = 360
SLOT_ATTR = $3400      ; BG2 palette 5, priority
ATTR_FX   = $3C        ; OBJ priority 3, palette 6
ATTR_BAL  = $3E        ; OBJ priority 3, palette 7

BS_NONE   = 0
BS_ARRIVE = 1
BS_WAIT   = 2

; player record
P_ACTIVE  = 0
P_ANIMAL  = 1
P_X       = 2          ; word, 8.8
P_Y       = 4          ; word, 8.8
P_PADI    = 6          ; word, 0 or 2: index into pad arrays
P_FACE    = 8          ; $00 or $40 (h-flip)
P_ANIMT   = 9
P_HOP     = 10
P_HAPPY   = 11
P_BLINK   = 12
P_BSTATE  = 13
P_BBTN    = 14         ; 0 A, 1 B, 2 X, 3 Y
P_BOFF    = 15
P_BWIG    = 16
P_BTIMER  = 17
P_WRONG   = 18
P_NEED    = 19         ; wrong presses tolerated before any button pops
P_UNLOCK  = 20         ; how many buttons balloons may ask for
P_STREAK  = 21
P_LASTBTN = 22
P_BPOP    = 23
P_BPOPX   = 24         ; word
P_BPOPY   = 26         ; word
P_VOICE   = 28
P_HUDX    = 29
P_NUM     = 30
PSIZE     = 32

; item record
I_ACTIVE = 0
I_TYPE   = 1
I_X      = 2
I_Y      = 3
I_TIMER  = 4
I_PHASE  = 5
ISIZE    = 8
NITEMS   = 3

; particle record (positions and speeds are 12.4 fixed point)
PT_LIFE  = 0
PT_TILE  = 1           ; word
PT_ATTR  = 3
PT_FLAGS = 4
PT_T     = 5
PT_X     = 6
PT_Y     = 8
PT_VX    = 10
PT_VY    = 12
PTSIZE   = 16
NPARTS   = 32
PF_GRAV    = 1
PF_SWAY    = 2
PF_TWINKLE = 4
PF_FLUTTER = 8

.macro A8
        sep #$20
        .a8
.endmacro
.macro A16
        rep #$20
        .a16
.endmacro
; clear the hidden B accumulator so TAX/TAY with A8 see only A
.macro ZB
        xba
        lda #0
        xba
.endmacro
.macro SFX inst, note, voice
        lda #inst
        sta sfx_inst
        lda #note
        sta sfx_note
        lda #voice
        sta sfx_voice
        jsr sfx_send
.endmacro
.macro DMA_VRAM src, dst, size
        ldx #dst
        stx VMADDL
        lda #$01
        sta DMAP0
        lda #$18
        sta BBAD0
        ldx #.loword(src)
        stx A1T0L
        lda #^src
        sta A1B0
        ldx #size
        stx DAS0L
        lda #$01
        sta MDMAEN
.endmacro

; ---------------------------------------------------------------- RAM
.segment "ZEROPAGE"
nmi_count:   .res 1
nmi_ready:   .res 1
frame:       .res 2
t0:          .res 2
t1:          .res 2
t2:          .res 2
t3:          .res 2
t4:          .res 2
t5:          .res 2
t6:          .res 2
t7:          .res 2
spr_x:       .res 2
spr_y:       .res 2
spr_tile:    .res 2
spr_attr:    .res 1
spr_size:    .res 1
oam_idx:     .res 2
rng:         .res 2
state:       .res 1
bright:      .res 1
bright_target: .res 1
pal_dirty:   .res 1
bg2_reload:  .res 1
vq_count:    .res 1
sound_ok:    .res 1
sfx_seq:     .res 1
sfx_inst:    .res 1
sfx_note:    .res 1
sfx_voice:   .res 1
seq_ptr:     .res 2
seq_wait:    .res 1
seq_on:      .res 1
progress:    .res 1
party_t:     .res 2
tod:         .res 1
fade_on:     .res 1
chime_voice: .res 1
title_t:     .res 2
join_mask:   .res 1
pad:         .res 4
pad_old:     .res 4
pad_new:     .res 4
np_x:        .res 2
np_y:        .res 2
np_vx:       .res 2
np_vy:       .res 2
np_tile:     .res 2
np_attr:     .res 1
np_flags:    .res 1
np_life:     .res 1
loop_i:      .res 2

.segment "BSS"
oam_lo:   .res 512
oam_hi:   .res 32          ; must follow oam_lo: both go up in one DMA
oam_xh:   .res 128
pal_buf:  .res 512
vq_addr:  .res 128
vq_data:  .res 128
players:  .res PSIZE * 2
items:    .res ISIZE * NITEMS
parts:    .res PTSIZE * NPARTS

; ---------------------------------------------------------------- data
.segment "BANK1"
bg_tiles:  .incbin "bg_tiles.bin"
bg1_map:   .incbin "bg1_map.bin"
bg2_title: .incbin "bg2_title.bin"
bg2_play:  .incbin "bg2_play.bin"
spc_image: .incbin "spc.bin"

.segment "BANK2"
obj_tiles: .incbin "obj_tiles.bin"

.include "assets.inc"

.segment "RODATA"
zero_byte:   .word 0
pal_bg_sets: .incbin "pal_bg.bin"
pal_obj:     .incbin "pal_obj.bin"
hop_tab:     .byte 0, 2, 4, 6, 7, 8, 10, 10, 11, 11, 11, 10, 10, 8, 7, 6, 4, 2, 0
bob_tab:     .word 0, 1, 1, 2, 2, 2, 1, 1, 0, $FFFF, $FFFF, $FFFE, $FFFE, $FFFE, $FFFF, $FFFF
wig_tab:     .word 0, 1, 1, 2, 2, 1, 0, $FFFF, $FFFE, $FFFE, $FFFF, 0
             .word 1, 2, 3, 2, 0, $FFFE, $FFFD, $FFFE, 0, 2, 3, 2
sway_tab:    .word 0, 6, 11, 14, 16, 14, 11, 6, 0, .loword(-6), .loword(-11), .loword(-14)
             .word .loword(-16), .loword(-14), .loword(-11), .loword(-6)
chime_notes: .byte 36, 38, 40, 41, 43, 45, 47, 48, 50, 52
btn_mask_tab: .word BTN_A, BTN_B, BTN_X, BTN_Y
unlock_order: .byte 0, 1, 3, 2           ; A, then B, then Y, then X
invite_order: .byte 2, 0, 1, 3           ; X A B Y: around the diamond
burst_vx:    .word 40, 31, 12, .loword(-12), .loword(-31), .loword(-40), .loword(-31), .loword(-12), 12, 31
burst_vy:    .word .loword(-10), .loword(-34), .loword(-46), .loword(-46), .loword(-34), .loword(-10), 8, 14, 14, 8
ring_vx:     .word 32, 16, .loword(-16), .loword(-32), .loword(-16), 16
ring_vy:     .word 0, .loword(-28), .loword(-28), 0, 28, 28
spark_vx:    .word 18, .loword(-18), 18, .loword(-18)
spark_vy:    .word .loword(-18), .loword(-18), 10, 10

; sound sequences: inst, note, voice, then frames to the next event ($FF ends)
seq_data:
seq_join:
        .byte INST_SPARK, 48, V_CHIME_A, 5
        .byte INST_SPARK, 52, V_CHIME_A + 1, 5
        .byte INST_SPARK, 55, V_CHIME_A, $FF
seq_party:
        .byte INST_NOTE, 31, V_MEL, 0
        .byte INST_BASS, 12, V_BASS, 8
        .byte INST_NOTE, 36, V_MEL, 8
        .byte INST_NOTE, 40, V_MEL, 8
        .byte INST_NOTE, 43, V_MEL, 0
        .byte INST_BASS, 16, V_BASS, 14
        .byte INST_NOTE, 40, V_MEL, 7
        .byte INST_NOTE, 43, V_MEL, 0
        .byte INST_BASS, 19, V_BASS, 22
        .byte INST_NOTE, 45, V_MEL, 0
        .byte INST_BASS, 17, V_BASS, 8
        .byte INST_NOTE, 43, V_MEL, 8
        .byte INST_NOTE, 41, V_MEL, 8
        .byte INST_NOTE, 40, V_MEL, 0
        .byte INST_BASS, 19, V_BASS, 8
        .byte INST_NOTE, 38, V_MEL, 8
        .byte INST_NOTE, 36, V_MEL, 0
        .byte INST_BASS, 12, V_BASS, 10
        .byte INST_NOTE, 48, V_MEL, 0
        .byte INST_BASS, 24, V_BASS, $FF

; ---------------------------------------------------------------- header
.segment "HEADER"
        .byte "MEADOW FRIENDS       "   ; 21 bytes
        .byte $20                       ; LoROM, SlowROM
        .byte $00                       ; ROM only
        .byte $07                       ; 128 KB
        .byte $00                       ; no SRAM
        .byte $01                       ; North America (NTSC)
        .byte $00                       ; developer
        .byte $00                       ; version
        .word $FFFF                     ; checksum complement (patched)
        .word $0000                     ; checksum (patched)

.segment "VECTORS"
        .word 0, 0
        .word irq_stub                  ; COP
        .word irq_stub                  ; BRK
        .word irq_stub                  ; ABORT
        .word nmi                       ; NMI
        .word 0
        .word irq_stub                  ; IRQ
        .word 0, 0
        .word irq_stub                  ; COP (emulation)
        .word 0
        .word irq_stub                  ; ABORT
        .word irq_stub                  ; NMI
        .word reset                     ; RESET
        .word irq_stub                  ; IRQ/BRK

; ================================================================ boot
.segment "CODE"

irq_stub:
        .a8
        .i16
        rti

reset:
        .a8
        .i16
        sei
        clc
        xce
        rep #$38
        .a16
        .i16
        ldx #$1FFF
        txs
        lda #$0000
        tcd
        A8
        lda #$00
        pha
        plb
        lda #$80
        sta INIDISP
        stz NMITIMEN
        stz HDMAEN
        ; clear all 128 KB of WRAM (two 64 KB passes); the stack holds nothing yet
        ldx #$0000
        stx WMADDL
        stz WMADDL + 2
        lda #$08
        sta DMAP0
        lda #<WMDATA
        sta BBAD0
        ldx #.loword(zero_byte)
        stx A1T0L
        lda #^zero_byte
        sta A1B0
        ldx #$0000
        stx DAS0L
        lda #$01
        sta MDMAEN
        stx DAS0L
        sta MDMAEN

        jsr init_ppu
        jsr clear_vram
        jsr upload_spc
        DMA_VRAM bg_tiles, $0000, BG_TILES_SIZE
        DMA_VRAM bg1_map, VRAM_BG1MAP, 2048
        DMA_VRAM bg2_title, VRAM_BG2MAP, 2048
        DMA_VRAM obj_tiles, VRAM_OBJ, 16384
        jsr init_palettes

        lda #$63                ; 16x16 / 32x32 sprites, tiles at $6000
        sta OBSEL
        lda #$01                ; mode 1
        sta BGMODE
        lda #(VRAM_BG1MAP >> 8)
        sta BG1SC
        lda #(VRAM_BG2MAP >> 8)
        sta BG2SC
        stz BG12NBA
        lda #$FF                ; vertical scroll -1 lines BGs up with sprites
        sta BG1VOFS
        sta BG1VOFS
        sta BG2VOFS
        sta BG2VOFS
        lda #$13                ; BG1, BG2, sprites
        sta TM
        stz TS
        stz SETINI

        ldx #$ACE1
        stx rng
        jsr title_init
        jsr oam_clear
        jsr oam_finish
        lda #$81                ; NMI + auto joypad read
        sta NMITIMEN

main_loop:
        .a8
        .i16
        jsr wait_frame
        jsr read_pads
        A16
        inc frame
        A8
        jsr oam_clear
        lda state
        cmp #ST_PLAY
        beq :+
        jsr title_update
        bra :++
:       jsr play_update
:       jsr seq_update
        jsr bright_update
        jsr oam_finish
        lda #1
        sta nmi_ready
        bra main_loop

; ---------------------------------------------------------------- hardware setup

init_ppu:
        .a8
        .i16
        ldx #$0001
:       stz $2100,x             ; $2101-$210C
        inx
        cpx #$000D
        bne :-
:       stz $2100,x             ; scroll registers take two writes
        stz $2100,x
        inx
        cpx #$0015
        bne :-
        lda #$80
        sta VMAIN
        ldx #$001A
:       stz $2100,x             ; $211A-$2120
        stz $2100,x
        inx
        cpx #$0021
        bne :-
:       stz $2100,x             ; $2121-$2133
        inx
        cpx #$0034
        bne :-
        lda #$FF
        sta WRIO
        ldx #$0002
:       stz $4200,x             ; $4202-$420D
        inx
        cpx #$000E
        bne :-
        rts

clear_vram:
        .a8
        .i16
        lda #$80
        sta VMAIN
        ldx #$0000
        stx VMADDL
        lda #$09                ; fixed source, two registers
        sta DMAP0
        lda #$18
        sta BBAD0
        ldx #.loword(zero_byte)
        stx A1T0L
        lda #^zero_byte
        sta A1B0
        ldx #$0000
        stx DAS0L
        lda #$01
        sta MDMAEN
        stz CGADD
        lda #$08
        sta DMAP0
        lda #$22
        sta BBAD0
        ldx #512
        stx DAS0L
        lda #$01
        sta MDMAEN
        rts

init_palettes:
        .a8
        .i16
        ldx #$0000
:       lda pal_bg_sets,x
        sta pal_buf,x
        lda pal_obj,x
        sta pal_buf + 256,x
        inx
        cpx #256
        bne :-
        stz CGADD
        stz DMAP0
        lda #$22
        sta BBAD0
        ldx #pal_buf
        stx A1T0L
        stz A1B0
        ldx #512
        stx DAS0L
        lda #$01
        sta MDMAEN
        rts

; Hand the sound driver to the audio CPU's boot ROM, then wait for it to say hello.
upload_spc:
        .a8
        .i16
        stz sound_ok
        ldy #$0000
@ipl:   ldx APUIO0
        cpx #$BBAA
        beq @go
        dey
        bne @ipl
        rts
@go:    ldx #$0200
        stx APUIO2
        lda #$01
        sta APUIO1
        lda #$CC
        sta APUIO0
:       cmp APUIO0
        bne :-
        ldx #$0000
@byte:  lda f:spc_image,x
        sta APUIO1
        txa
        sta APUIO0
:       cmp APUIO0
        bne :-
        inx
        cpx #SPC_SIZE
        bne @byte
        ldy #$0200
        sty APUIO2
        stz APUIO1
        txa
        inc a
        sta APUIO0
:       cmp APUIO0
        bne :-
        ldy #$0000
:       lda APUIO1
        cmp #$5A
        beq @ok
        dey
        bne :-
        rts
@ok:    lda #1
        sta sound_ok
        stz sfx_seq
        rts

; ---------------------------------------------------------------- per-frame plumbing

nmi:
        .a8
        .i16
        rep #$30
        pha
        phx
        phy
        phb
        phd
        A8
        .i16
        lda #$00
        pha
        plb
        A16
        lda #$0000
        tcd
        A8
        lda RDNMI
        lda nmi_ready
        bne :+
        jmp @skip
:       ldx #$0000              ; sprites
        stx $2102
        stz DMAP0
        lda #$04
        sta BBAD0
        ldx #oam_lo
        stx A1T0L
        stz A1B0
        ldx #544
        stx DAS0L
        lda #$01
        sta MDMAEN
        lda pal_dirty
        beq @nopal
        stz CGADD
        stz DMAP0
        lda #$22
        sta BBAD0
        ldx #pal_buf
        stx A1T0L
        stz A1B0
        ldx #512
        stx DAS0L
        lda #$01
        sta MDMAEN
        stz pal_dirty
@nopal: lda bg2_reload
        beq @nobg2
        DMA_VRAM bg2_play, VRAM_BG2MAP, 2048
        stz bg2_reload
@nobg2: lda vq_count
        beq @novq
        lda #$80
        sta VMAIN
        ldy #$0000
:       ldx vq_addr,y
        stx VMADDL
        ldx vq_data,y
        stx $2118
        iny
        iny
        dec vq_count
        bne :-
@novq:  lda bright
        sta INIDISP
        stz nmi_ready
@skip:  inc nmi_count
        rep #$30
        pld
        plb
        ply
        plx
        pla
        rti

wait_frame:
        .a8
        .i16
        lda nmi_count
:       cmp nmi_count
        beq :-
        rts

read_pads:
        .a8
        .i16
:       lda HVBJOY
        and #$01
        bne :-
        A16
        lda pad
        sta pad_old
        lda JOY1L
        and #$FFF0
        sta pad
        lda pad_old
        eor #$FFFF
        and pad
        sta pad_new
        lda pad + 2
        sta pad_old + 2
        lda JOY2L
        and #$FFF0
        sta pad + 2
        lda pad_old + 2
        eor #$FFFF
        and pad + 2
        sta pad_new + 2
        A8
        rts

bright_update:
        .a8
        .i16
        lda bright
        cmp bright_target
        beq @done
        bcc :+
        dec bright
        rts
:       inc bright
@done:  rts

; random byte in A (xorshift16)
rand:
        .a8
        .i16
        php
        A16
        lda rng
        asl a
        asl a
        asl a
        asl a
        asl a
        asl a
        asl a
        eor rng
        sta rng
        xba
        and #$00FF
        lsr a
        eor rng
        sta rng
        xba
        and #$FF00
        eor rng
        sta rng
        plp
        rts

; A = n -> A = random 0..n-1
rand_n:
        .a8
        .i16
        pha
        jsr rand
        sta WRMPYA
        pla
        sta WRMPYB
        nop
        nop
        nop
        nop
        lda RDMPYH
        rts

; ---------------------------------------------------------------- sprites

oam_clear:
        .a8
        .i16
        ldx #$0000
        stx oam_idx
        rts

; add one sprite from spr_x (9-bit), spr_y, spr_tile (9-bit), spr_attr, spr_size (0 small / 2 large)
oam_add:
        .a8
        .i16
        phx
        phy
        ldx oam_idx
        cpx #512
        bcs @full
        lda spr_x
        sta oam_lo,x
        lda spr_y
        sta oam_lo + 1,x
        lda spr_tile
        sta oam_lo + 2,x
        lda spr_tile + 1
        and #$01
        ora spr_attr
        sta oam_lo + 3,x
        A16
        txa
        lsr a
        lsr a
        tay
        txa
        clc
        adc #4
        sta oam_idx
        A8
        lda spr_x + 1
        and #$01
        ora spr_size
        sta oam_xh,y
@full:  ply
        plx
        rts

; hide unused sprites and pack the high table
oam_finish:
        .a8
        .i16
        A16
        lda oam_idx
        lsr a
        lsr a
        tay
        A8
        ldx oam_idx
:       cpx #512
        bcs @pack
        lda #$E0
        sta oam_lo + 1,x
        lda #$00
        sta oam_xh,y
        iny
        inx
        inx
        inx
        inx
        bra :-
@pack:  ldx #$0000
        ldy #$0000
:       lda oam_xh + 3,y
        asl a
        asl a
        ora oam_xh + 2,y
        asl a
        asl a
        ora oam_xh + 1,y
        asl a
        asl a
        ora oam_xh,y
        sta oam_hi,x
        iny
        iny
        iny
        iny
        inx
        cpx #32
        bne :-
        rts

; ---------------------------------------------------------------- sound

; play sfx_inst / sfx_note on sfx_voice
sfx_send:
        .a8
        .i16
        lda sound_ok
        beq @out
        phx
        ldx #2000
:       lda APUIO0
        cmp sfx_seq
        beq @ready
        dex
        bne :-
@ready: lda sfx_inst
        sta APUIO1
        lda sfx_note
        sta APUIO2
        lda sfx_voice
        sta APUIO3
        inc sfx_seq
        lda sfx_seq
        sta APUIO0
        plx
@out:   rts

; X = offset of a sequence in seq_data
seq_start:
        .a8
        .i16
        stx seq_ptr
        stz seq_wait
        lda #1
        sta seq_on
        rts

seq_update:
        .a8
        .i16
        lda seq_on
        beq @done
        lda seq_wait
        beq :+
        dec seq_wait
        rts
:       ldy seq_ptr
@event: lda seq_data,y
        sta sfx_inst
        lda seq_data + 1,y
        sta sfx_note
        lda seq_data + 2,y
        sta sfx_voice
        jsr sfx_send
        iny
        iny
        iny
        lda seq_data,y
        cmp #$FF
        beq @end
        iny
        cmp #0
        beq @event
        dec a
        sta seq_wait
        sty seq_ptr
        rts
@end:   stz seq_on
@done:  rts

; ================================================================ title

title_init:
        .a8
        .i16
        lda #ST_TITLE
        sta state
        stz bright
        lda #15
        sta bright_target
        stz join_mask
        ldx #$0000
        stx title_t
        lda #0
        jsr player_setup
        ldx #PSIZE
        lda #1
        jsr player_setup
        rts

title_update:
        .a8
        .i16
        ldx title_t
        inx
        stx title_t
        jsr draw_title_animals
        ldx #$0000
        jsr draw_hud_player
        ldx #PSIZE
        jsr draw_hud_player
        ; any press joins that player; the first one starts the game
        A16
        lda pad_new
        A8
        beq :+
        lda #1
        tsb join_mask
:       A16
        lda pad_new + 2
        A8
        beq :+
        lda #2
        tsb join_mask
:       lda state
        cmp #ST_TITLE_OUT
        beq @out
        lda join_mask
        beq @done
        lda #ST_TITLE_OUT
        sta state
        stz bright_target
        ldx #(seq_join - seq_data)
        jsr seq_start
        rts
@out:   lda bright
        bne @done
        jsr play_init
@done:  rts

draw_title_animals:
        .a8
        .i16
        ldx #$0000
        stx loop_i
@loop:  ; x = 12 + i*40
        lda loop_i
        asl a
        asl a
        asl a
        sta t4                  ; i*8
        asl a
        asl a                   ; i*32
        clc
        adc t4
        clc
        adc #12
        sta spr_x
        stz spr_x + 1
        ; hop phase = (title_t - i*8) & 63
        lda title_t
        sec
        sbc t4
        and #63
        sta t5
        stz t6                  ; frame 0
        lda t5
        cmp #HOP_LEN
        bcs @ground
        lda #HOP_LEN
        sec
        sbc t5
        ZB
        tay
        lda hop_tab,y
        sta t7
        lda #2
        sta t6
        bra @draw
@ground:
        stz t7
@draw:  lda #108
        sec
        sbc t7
        sta spr_y
        ; tile = animal_tiles[i*3 + frame]
        lda loop_i
        asl a
        clc
        adc loop_i
        clc
        adc t6
        asl a
        ZB
        tay
        A16
        lda animal_tiles,y
        sta spr_tile
        A8
        lda loop_i
        asl a
        ora #$30
        sta spr_attr
        lda #2
        sta spr_size
        jsr oam_add
        ; shadow
        lda spr_x
        clc
        adc #8
        sta spr_x
        lda #(108 + 18)
        sta spr_y
        ldx #SHADOW_TILE
        stx spr_tile
        lda #ATTR_FX
        sta spr_attr
        stz spr_size
        jsr oam_add
        inc loop_i
        lda loop_i
        cmp #NUM_ANIMALS
        beq :+
        jmp @loop
:       rts

; ================================================================ play

play_init:
        .a8
        .i16
        lda #ST_PLAY
        sta state
        lda #15
        sta bright_target
        lda #1
        sta bg2_reload
        stz progress
.ifdef TEST_PARTY
        lda #9
        sta progress
.endif
        ldx #$0000
        stx party_t
        jsr items_reset
        lda join_mask
        and #1
        beq :+
        ldx #$0000
        jsr player_join
:       lda join_mask
        and #2
        beq :+
        ldx #PSIZE
        jsr player_join
:       rts

play_update:
        .a8
        .i16
        ldx #$0000
        jsr check_join
        ldx #PSIZE
        jsr check_join
        ldx #$0000
        jsr update_player
        ldx #PSIZE
        jsr update_player
        jsr items_update
        jsr party_update
        jsr fade_update
        jsr parts_update
        ; draw front to back
        jsr parts_draw
        ldx #$0000
        jsr draw_balloon
        ldx #PSIZE
        jsr draw_balloon
        ldx #$0000
        jsr draw_hud_player
        ldx #PSIZE
        jsr draw_hud_player
        jsr draw_animals
        jsr items_draw
        rts

; ---------------------------------------------------------------- players

; X = player record, A = player number
player_setup:
        .a8
        .i16
        sta players + P_NUM,x
        sta players + P_ANIMAL,x        ; P1 bunny, P2 puppy
        sta players + P_VOICE,x
        asl a
        sta players + P_PADI,x
        stz players + P_PADI + 1,x
        stz players + P_ACTIVE,x
        lda players + P_NUM,x
        beq :+
        lda #HUD_X2
        bra :++
:       lda #HUD_X1
:       sta players + P_HUDX,x
        rts

player_join:
        .a8
        .i16
        lda #1
        sta players + P_ACTIVE,x
        A16
        lda #(72 << 8)
        ldy players + P_NUM,x
        cpy #$0000
        beq :+
        lda #(152 << 8)
:       sta players + P_X,x
        lda #(100 << 8)
        sta players + P_Y,x
        A8
        lda #HOP_LEN
        sta players + P_HOP,x
        lda #40
        sta players + P_HAPPY,x
        lda #2
        sta players + P_NEED,x
        lda #1
        sta players + P_UNLOCK,x
        stz players + P_STREAK,x
        stz players + P_BSTATE,x
        stz players + P_BPOP,x
        stz players + P_FACE,x
        lda #$FF
        sta players + P_LASTBTN,x
        lda #120
        sta players + P_BTIMER,x
        lda #90
        sta players + P_BLINK,x
        jsr fx_ring
        phx
        ldx #(seq_join - seq_data)
        jsr seq_start
        plx
        rts

check_join:
        .a8
        .i16
        lda players + P_ACTIVE,x
        bne @done
        ldy players + P_PADI,x
        A16
        lda pad_new,y
        A8
        beq @done
        jsr player_join
@done:  rts

update_player:
        .a8
        .i16
        lda players + P_ACTIVE,x
        bne :+
        rts
:       ldy players + P_PADI,x
        A16
        lda pad,y
        sta t0                  ; held
        lda pad_new,y
        sta t1                  ; newly pressed
        stz t2                  ; bit0 moved, bit1 face right, bit2 face left
        lda t0
        bit #BTN_RIGHT
        beq @nr
        lda players + P_X,x
        clc
        adc #SPEED
        cmp #XMAX
        bcc :+
        lda #XMAX
:       sta players + P_X,x
        lda #$0003
        tsb t2
@nr:    lda t0
        bit #BTN_LEFT
        beq @nl
        lda players + P_X,x
        sec
        sbc #SPEED
        bcs :+
        lda #$0000
:       sta players + P_X,x
        lda #$0005
        tsb t2
@nl:    lda t0
        bit #BTN_UP
        beq @nu
        lda players + P_Y,x
        sec
        sbc #SPEED
        cmp #YMIN
        bcs :+
        lda #YMIN
:       sta players + P_Y,x
        lda #$0001
        tsb t2
@nu:    lda t0
        bit #BTN_DOWN
        beq @nd
        lda players + P_Y,x
        clc
        adc #SPEED
        cmp #YMAX
        bcc :+
        lda #YMAX
:       sta players + P_Y,x
        lda #$0001
        tsb t2
@nd:    A8
        ; walk cycle
        lda t2
        and #$01
        beq :+
        lda players + P_ANIMT,x
        inc a
        and #31
        sta players + P_ANIMT,x
        bra :++
:       stz players + P_ANIMT,x
:       lda t2
        and #$02
        beq :+
        stz players + P_FACE,x
:       lda t2
        and #$04
        beq :+
        lda #$40
        sta players + P_FACE,x
:       ; timers
        lda players + P_HOP,x
        beq :+
        dec players + P_HOP,x
:       lda players + P_HAPPY,x
        beq :+
        dec players + P_HAPPY,x
:       lda players + P_BWIG,x
        beq :+
        dec players + P_BWIG,x
:       lda players + P_BPOP,x
        beq :+
        dec players + P_BPOP,x
:       dec players + P_BLINK,x
        bne :+
        lda #120
        jsr rand_n
        clc
        adc #120
        sta players + P_BLINK,x
:       ; Select: next animal
        A16
        lda t1
        bit #BTN_SELECT
        A8
        beq :+
        jsr player_next_animal
:       ; face buttons: pop or hop
        A16
        lda t1
        and #BTN_FACE
        sta t3
        A8
        beq @noface
        lda players + P_BSTATE,x
        beq :+
        jsr balloon_press
        bra @noface
:       jsr hop_face
@noface:
        A16
        lda t1
        and #(BTN_L | BTN_R | BTN_START)
        sta t3
        A8
        beq :+
        jsr hop_other
:       jmp balloon_update

; hop with a note per button (t3 = new face buttons)
hop_face:
        .a8
        .i16
        lda #HOP_LEN
        sta players + P_HOP,x
        lda #14
        sta players + P_HAPPY,x
        A16
        ldy #36                 ; A: C5
        lda t3
        bit #BTN_A
        bne :+
        ldy #31                 ; B: G4
        bit #BTN_B
        bne :+
        ldy #40                 ; X: E5
        bit #BTN_X
        bne :+
        ldy #33                 ; Y: A4
:       A8
        tya
        sta sfx_note
        lda #INST_BOOP
        sta sfx_inst
        lda players + P_VOICE,x
        sta sfx_voice
        jmp sfx_send

; t3 = new L / R / Start
hop_other:
        .a8
        .i16
        lda #HOP_LEN
        sta players + P_HOP,x
        lda #14
        sta players + P_HAPPY,x
        A16
        ldy #24                 ; L: C4
        lda t3
        bit #BTN_L
        bne :+
        ldy #28                 ; R: E4
        bit #BTN_R
        bne :+
        ldy #43                 ; Start: G5
:       A8
        tya
        sta sfx_note
        lda #INST_BOOP
        sta sfx_inst
        lda players + P_VOICE,x
        sta sfx_voice
        jmp sfx_send

player_next_animal:
        .a8
        .i16
        lda players + P_ANIMAL,x
        inc a
        cmp #NUM_ANIMALS
        bcc :+
        lda #0
:       sta players + P_ANIMAL,x
        lda #HOP_LEN
        sta players + P_HOP,x
        lda #30
        sta players + P_HAPPY,x
        jsr fx_ring
        lda #INST_SPARK
        sta sfx_inst
        lda #48
        sta sfx_note
        lda players + P_VOICE,x
        sta sfx_voice
        jmp sfx_send

; ---------------------------------------------------------------- balloons

; t3 = new face buttons while this player's balloon is up
balloon_press:
        .a8
        .i16
        lda players + P_BBTN,x
        asl a
        ZB
        tay
        A16
        lda btn_mask_tab,y
        sta t4
        and t3
        beq @wrong
        lda t3
        cmp t4
        A8
        bne @forced             ; right button mashed with others: pop, no credit
        lda players + P_WRONG,x
        bne @late
        jsr skill_correct
        jmp balloon_pop
@late:  stz players + P_STREAK,x
        jmp balloon_pop
@forced:
        jsr skill_forced
        jmp balloon_pop
@wrong: A8
        inc players + P_WRONG,x
        lda players + P_WRONG,x
        cmp players + P_NEED,x
        beq @wiggle
        bcs @forced             ; enough tries: any button pops it
@wiggle:
        lda #23
        sta players + P_BWIG,x
        lda #INST_BOING
        sta sfx_inst
        lda #19
        sta sfx_note
        lda players + P_VOICE,x
        sta sfx_voice
        jmp sfx_send

skill_correct:
        .a8
        .i16
        inc players + P_STREAK,x
        lda players + P_STREAK,x
        cmp #3
        bcc :+
        stz players + P_STREAK,x
        lda players + P_UNLOCK,x
        cmp #4
        bcs :+
        inc players + P_UNLOCK,x
:       lda players + P_NEED,x
        cmp #3
        bcs :+
        inc players + P_NEED,x
:       rts

skill_forced:
        .a8
        .i16
        stz players + P_STREAK,x
        lda players + P_NEED,x
        beq :+
        dec players + P_NEED,x
:       rts

; where the balloon is drawn: t4 = x, t5 = y (signed)
balloon_pos:
        .a8
        .i16
        A16
        lda players + P_X,x
        xba
        and #$00FF
        sta t4
        lda players + P_BWIG,x
        and #$00FF
        asl a
        tay
        lda wig_tab,y
        clc
        adc t4
        sta t4
        lda players + P_BOFF,x
        and #$00FF
        sta t5
        lda players + P_Y,x
        xba
        and #$00FF
        sec
        sbc #36
        sec
        sbc t5
        sta t5
        A8
        lda players + P_BSTATE,x
        cmp #BS_WAIT
        bne :+
        A16
        lda frame
        lsr a
        lsr a
        and #$001E
        tay
        lda bob_tab,y
        clc
        adc t5
        sta t5
        A8
:       rts

; burst + confetti where the balloon is (X = player)
balloon_fx:
        .a8
        .i16
        jsr balloon_pos
        A16
        lda t4
        sta players + P_BPOPX,x
        clc
        adc #8
        sta np_x
        lda t5
        sta players + P_BPOPY,x
        clc
        adc #6
        sta np_y
        A8
        jsr fx_confetti
        lda #10
        sta players + P_BPOP,x
        stz players + P_BSTATE,x
        stz players + P_BWIG,x
        SFX INST_POP, 0, V_POP
        rts

balloon_pop:
        .a8
        .i16
        jsr balloon_fx
        lda #HOP_LEN
        sta players + P_HOP,x
        lda #45
        sta players + P_HAPPY,x
        jsr fx_heart
        lda #110
        jsr rand_n
        clc
        adc #100
        sta players + P_BTIMER,x
        jmp progress_add

balloon_update:
        .a8
        .i16
        lda players + P_BSTATE,x
        bne @up
        lda party_t
        ora party_t + 1
        bne @done
        dec players + P_BTIMER,x
        bne @done
        jmp balloon_spawn
@up:    cmp #BS_ARRIVE
        bne @done
        lda players + P_BOFF,x
        sec
        sbc #3
        bcs :+
        lda #0
:       sta players + P_BOFF,x
        bne @done
        lda #BS_WAIT
        sta players + P_BSTATE,x
@done:  rts

balloon_spawn:
        .a8
        .i16
        lda players + P_UNLOCK,x
        jsr rand_n
        sta t4
        ZB
        tay
        lda unlock_order,y
        cmp players + P_LASTBTN,x
        bne @ok
        lda players + P_UNLOCK,x
        cmp #2
        bcc @same
        iny                     ; same as last time: take the next one
        tya
        cmp players + P_UNLOCK,x
        bcc :+
        lda #0
:       ZB
        tay
@same:  lda unlock_order,y
@ok:    sta players + P_BBTN,x
        sta players + P_LASTBTN,x
        lda #BS_ARRIVE
        sta players + P_BSTATE,x
        lda #120
        sta players + P_BOFF,x
        stz players + P_WRONG,x
        SFX INST_WHOO, 36, V_WHOO
        rts

; ---------------------------------------------------------------- progress & party

; a star for the meadow: chime, fill a slot, maybe start the party (keeps X, Y)
progress_add:
        .a8
        .i16
        phx
        phy
        lda progress
        cmp #10
        bcc :+
        lda #9
:       ZB
        tay
        lda chime_notes,y
        sta sfx_note
        lda #INST_CHIME
        sta sfx_inst
        lda chime_voice
        eor #1
        sta chime_voice
        clc
        adc #V_CHIME_A
        sta sfx_voice
        jsr sfx_send
        lda party_t
        ora party_t + 1
        bne @done
        lda progress
        jsr slot_fill
        inc progress
        lda progress
        cmp #10
        bcc @done
        jsr party_start
@done:  ply
        plx
        rts

; A = slot index: queue the filled star tiles and sparkle there
slot_fill:
        .a8
        .i16
        sta t4
        stz t4 + 1
        asl a
        clc
        adc t4
        clc
        adc #SLOT_COL0
        sta t5
        stz t5 + 1
        A16
        lda t5
        clc
        adc #(VRAM_BG2MAP + SLOT_ROW * 32)
        sta t6
        lda star_slot_tiles
        ora #SLOT_ATTR
        sta t7
        A8
        jsr vq_push
        A16
        inc t6
        lda star_slot_tiles + 2
        ora #SLOT_ATTR
        sta t7
        A8
        jsr vq_push
        A16
        lda t6
        clc
        adc #31
        sta t6
        lda star_slot_tiles + 4
        ora #SLOT_ATTR
        sta t7
        A8
        jsr vq_push
        A16
        inc t6
        lda star_slot_tiles + 6
        ora #SLOT_ATTR
        sta t7
        lda t5
        asl a
        asl a
        asl a
        sta np_x
        lda #(SLOT_ROW * 8)
        sta np_y
        A8
        jsr vq_push
        jmp fx_sparkles

; t6 = VRAM word address, t7 = value
vq_push:
        .a8
        .i16
        phx
        lda vq_count
        cmp #64
        bcs @full
        asl a
        ZB
        tax
        A16
        lda t6
        sta vq_addr,x
        lda t7
        sta vq_data,x
        A8
        inc vq_count
@full:  plx
        rts

party_start:
        .a8
        .i16
        phx
        A16
        lda #PARTY_LEN
        sta party_t
        A8
        ldx #(seq_party - seq_data)
        jsr seq_start
        ldx #$0000
        jsr party_pop
        ldx #PSIZE
        jsr party_pop
        ldx #$0000
:       stz items + I_ACTIVE,x
        inx
        inx
        inx
        inx
        inx
        inx
        inx
        inx
        cpx #(ISIZE * NITEMS)
        bne :-
        plx
        rts

party_pop:
        .a8
        .i16
        lda players + P_ACTIVE,x
        beq :+
        lda players + P_BSTATE,x
        beq :+
        jsr balloon_fx
        lda #60
        sta players + P_BTIMER,x
:       rts

party_hop:
        .a8
        .i16
        lda players + P_ACTIVE,x
        beq :+
        lda #HOP_LEN
        sta players + P_HOP,x
        lda #24
        sta players + P_HAPPY,x
:       rts

party_update:
        .a8
        .i16
        A16
        lda party_t
        bne :+
        A8
        rts
:       .a16
        dec a
        sta party_t
        bne :+
        A8
        jmp party_end
:       .a16
        cmp #140
        bcc @noconf
        A8
        lda #3
        jsr rand_n
        A16
        and #$00FF
        bne @noconf
        A8
        jsr fx_party_confetti
        A16
@noconf:
        lda party_t
        and #$001F
        bne @nohop
        A8
        ldx #$0000
        jsr party_hop
        ldx #PSIZE
        jsr party_hop
        A16
@nohop: lda party_t
        cmp #200
        A8
        bne @done
        lda tod
        inc a
        and #3
        sta tod
        lda #1
        sta fade_on
@done:  rts

party_end:
        .a8
        .i16
        stz progress
        lda #1
        sta bg2_reload
        jsr items_reset
        lda #60
        sta players + P_BTIMER
        sta players + PSIZE + P_BTIMER
        rts

; move the sky and meadow colours one step toward the current time of day
fade_update:
        .a8
        .i16
        lda fade_on
        bne :+
        rts
:       lda frame
        and #$01
        beq :+
        rts
:       lda tod
        xba
        lda #0
        A16
        sta t4                  ; tod * 256
        stz t5
        ldx #$0000
@loop:  txa
        clc
        adc t4
        tay
        lda pal_bg_sets,y
        sta t6
        lda pal_buf,x
        cmp t6
        beq @next
        sta t7
        lda t7
        and #$001F
        sta t0
        lda t6
        and #$001F
        cmp t0
        beq @g
        bcc :+
        inc t7
        bra @g
:       dec t7
@g:     lda t7
        and #$03E0
        sta t0
        lda t6
        and #$03E0
        cmp t0
        beq @b
        bcc :+
        lda t7
        clc
        adc #$0020
        sta t7
        bra @b
:       lda t7
        sec
        sbc #$0020
        sta t7
@b:     lda t7
        and #$7C00
        sta t0
        lda t6
        and #$7C00
        cmp t0
        beq @st
        bcc :+
        lda t7
        clc
        adc #$0400
        sta t7
        bra @st
:       lda t7
        sec
        sbc #$0400
        sta t7
@st:    lda t7
        sta pal_buf,x
        inc t5
@next:  inx
        inx
        cpx #64
        beq :+
        jmp @loop
:       lda t5
        A8
        bne :+
        stz fade_on
:       lda #1
        sta pal_dirty
        rts

; ---------------------------------------------------------------- items

items_reset:
        .a8
        .i16
        ldx #$0000
        lda #20
:       stz items + I_ACTIVE,x
        sta items + I_TIMER,x
        clc
        adc #18
        inx
        inx
        inx
        inx
        inx
        inx
        inx
        inx
        cpx #(ISIZE * NITEMS)
        bne :-
        rts

items_update:
        .a8
        .i16
        ldx #$0000
@loop:  lda items + I_ACTIVE,x
        beq @off
        inc items + I_PHASE,x
        ldy #$0000
        jsr item_check
        ldy #PSIZE
        jsr item_check
        bra @next
@off:   lda party_t
        ora party_t + 1
        bne @next
        dec items + I_TIMER,x
        bne @next
        jsr item_spawn
@next:  A16
        txa
        clc
        adc #ISIZE
        tax
        A8
        cpx #(ISIZE * NITEMS)
        bne @loop
        rts

; X = item, Y = player: pick it up if the animal touches it
item_check:
        .a8
        .i16
        lda items + I_ACTIVE,x
        beq @no
        lda players + P_ACTIVE,y
        beq @no
        A16
        lda players + P_X,y
        xba
        and #$00FF
        clc
        adc #8
        sta t4
        lda items + I_X,x
        and #$00FF
        sta t5
        lda t4
        sec
        sbc t5
        bpl :+
        eor #$FFFF
        inc a
:       cmp #16
        bcs @no16
        lda players + P_Y,y
        xba
        and #$00FF
        clc
        adc #12
        sta t4
        lda items + I_Y,x
        and #$00FF
        sta t5
        lda t4
        sec
        sbc t5
        bpl :+
        eor #$FFFF
        inc a
:       cmp #16
        bcs @no16
        A8
        jmp item_collect
@no16:  A8
@no:    rts

item_collect:
        .a8
        .i16
        stz items + I_ACTIVE,x
        lda #40
        jsr rand_n
        clc
        adc #30
        sta items + I_TIMER,x
        A16
        lda items + I_X,x
        and #$00FF
        sta np_x
        lda items + I_Y,x
        and #$00FF
        sta np_y
        A8
        jsr fx_sparkles
        phx
        tyx
        lda #25
        sta players + P_HAPPY,x
        plx
        jmp progress_add

item_spawn:
        .a8
        .i16
        lda #4
        jsr rand_n
        sta items + I_TYPE,x
        lda #6
        sta t3
@try:   lda #208
        jsr rand_n
        clc
        adc #16
        sta items + I_X,x
        lda #88
        jsr rand_n
        clc
        adc #68
        sta items + I_Y,x
        ldy #$0000
        jsr item_near
        bcs @again
        ldy #PSIZE
        jsr item_near
        bcc @ok
@again: dec t3
        bne @try
@ok:    lda #1
        sta items + I_ACTIVE,x
        stz items + I_PHASE,x
        rts

; carry set if item X spawned close to active player Y
item_near:
        .a8
        .i16
        lda players + P_ACTIVE,y
        bne :+
        clc
        rts
:       A16
        lda players + P_X,y
        xba
        and #$00FF
        clc
        adc #8
        sta t4
        lda items + I_X,x
        and #$00FF
        sec
        sbc t4
        bpl :+
        eor #$FFFF
        inc a
:       cmp #40
        bcs @far
        lda players + P_Y,y
        xba
        and #$00FF
        clc
        adc #12
        sta t4
        lda items + I_Y,x
        and #$00FF
        sec
        sbc t4
        bpl :+
        eor #$FFFF
        inc a
:       cmp #40
        bcs @far
        A8
        sec
        rts
@far:   A8
        clc
        rts

items_draw:
        .a8
        .i16
        ldx #$0000
@loop:  lda items + I_ACTIVE,x
        beq @next
        lda items + I_X,x
        sta spr_x
        stz spr_x + 1
        lda items + I_PHASE,x
        lsr a
        lsr a
        and #$1E
        ZB
        tay
        lda bob_tab,y
        clc
        adc items + I_Y,x
        sta spr_y
        lda items + I_TYPE,x
        asl a
        ZB
        tay
        A16
        lda item_tiles,y
        sta spr_tile
        A8
        lda #ATTR_FX
        sta spr_attr
        stz spr_size
        jsr oam_add
@next:  A16
        txa
        clc
        adc #ISIZE
        tax
        A8
        cpx #(ISIZE * NITEMS)
        bne @loop
        rts

; ---------------------------------------------------------------- drawing

draw_animals:
        .a8
        .i16
        A16
        lda players + PSIZE + P_Y
        cmp players + P_Y
        A8
        bcc :+
        ldx #PSIZE              ; P2 is lower on screen: in front
        jsr draw_animal
        ldx #$0000
        jsr draw_animal
        bra :++
:       ldx #$0000
        jsr draw_animal
        ldx #PSIZE
        jsr draw_animal
:       ldx #$0000
        jsr draw_shadow
        ldx #PSIZE
        jmp draw_shadow

draw_animal:
        .a8
        .i16
        lda players + P_ACTIVE,x
        bne :+
        rts
:       lda players + P_HOP,x
        ZB
        tay
        lda hop_tab,y
        sta t4
        stz t5                  ; frame
        stz t6                  ; extra flip
        lda players + P_HAPPY,x
        bne @happy
        lda players + P_BLINK,x
        cmp #6
        bcc @happy
        lda players + P_ANIMT,x
        and #$08
        beq @pick
        lda #1
        sta t5
        inc t4                  ; bob up on the step
        lda players + P_ANIMT,x
        and #$10
        beq @pick
        lda #$40
        sta t6
        bra @pick
@happy: lda #2
        sta t5
@pick:  lda players + P_ANIMAL,x
        sta t7
        asl a
        clc
        adc t7
        clc
        adc t5
        asl a
        ZB
        tay
        A16
        lda animal_tiles,y
        sta spr_tile
        A8
        lda players + P_X + 1,x
        sta spr_x
        stz spr_x + 1
        lda players + P_Y + 1,x
        sec
        sbc t4
        sta spr_y
        lda players + P_ANIMAL,x
        asl a
        ora #$30
        ora players + P_FACE,x
        eor t6
        sta spr_attr
        lda #2
        sta spr_size
        jmp oam_add

draw_shadow:
        .a8
        .i16
        lda players + P_ACTIVE,x
        bne :+
        rts
:       lda players + P_X + 1,x
        clc
        adc #8
        sta spr_x
        stz spr_x + 1
        lda players + P_Y + 1,x
        clc
        adc #18
        sta spr_y
        ldy #SHADOW_TILE
        sty spr_tile
        lda #ATTR_FX
        sta spr_attr
        stz spr_size
        jmp oam_add

draw_balloon:
        .a8
        .i16
        lda players + P_ACTIVE,x
        bne :+
        rts
:       lda players + P_BPOP,x
        beq @noburst
        A16
        lda players + P_BPOPX,x
        sta spr_x
        lda players + P_BPOPY,x
        sta spr_y
        lda #BURST_TILE
        sta spr_tile
        A8
        lda players + P_BPOP,x
        and #$02
        asl a
        asl a
        asl a
        asl a
        asl a
        ora #ATTR_FX            ; flip every other pair of frames
        sta spr_attr
        lda #2
        sta spr_size
        jsr oam_add
@noburst:
        lda players + P_BSTATE,x
        bne :+
        rts
:       jsr balloon_pos
        A16
        lda t5
        clc
        adc #32
        A8
        bpl :+
        rts                     ; still above the screen
:       A16
        lda t4
        sta spr_x
        lda t5
        sta spr_y
        A8
        lda players + P_BBTN,x
        asl a
        ZB
        tay
        A16
        lda balloon_tiles,y
        sta spr_tile
        A8
        lda #ATTR_BAL
        sta spr_attr
        lda #2
        sta spr_size
        jmp oam_add

; light the on-screen controller: held buttons, the balloon's button, or an invitation to join
draw_hud_player:
        .a8
        .i16
        lda players + P_HUDX,x
        sta t6
        stz t6 + 1
        ldy players + P_PADI,x
        A16
        lda pad,y
        sta t0
        stz t1
        A8
        lda players + P_ACTIVE,x
        beq @invite
        lda players + P_BSTATE,x
        beq @draw
        lda frame
        and #$10
        beq @draw
        lda players + P_BBTN,x
        asl a
        ZB
        tay
        A16
        lda btn_mask_tab,y
        sta t1
        A8
        bra @draw
@invite:
        lda frame
        and #$08
        beq @draw
        lda frame
        lsr a
        lsr a
        lsr a
        lsr a
        and #$03
        ZB
        tay
        lda invite_order,y
        asl a
        ZB
        tay
        A16
        lda btn_mask_tab,y
        sta t1
        A8
@draw:  lda t6                  ; this player's animal on their controller
        clc
        adc #41
        sta spr_x
        stz spr_x + 1
        lda #(HUD_Y + 8)
        sta spr_y
        lda players + P_ANIMAL,x
        asl a
        ZB
        tay
        A16
        lda icon_tiles,y
        sta spr_tile
        A8
        lda players + P_ANIMAL,x
        asl a
        ora #$30
        sta spr_attr
        stz spr_size
        jsr oam_add
        A16
        lda t0
        ora t1
        sta t0
        A8
        ldy #$0000
@loop:  A16
        lda hud_elems,y
        and t0
        A8
        beq @next
        lda hud_elems + 2,y
        clc
        adc t6
        sta spr_x
        stz spr_x + 1
        lda hud_elems + 3,y
        clc
        adc #HUD_Y
        sta spr_y
        A16
        lda hud_elems + 4,y
        sta spr_tile
        A8
        lda hud_elems + 6,y
        ora #ATTR_BAL
        sta spr_attr
        lda hud_elems + 7,y
        sta spr_size
        jsr oam_add
@next:  iny
        iny
        iny
        iny
        iny
        iny
        iny
        iny
        cpy #(NUM_HUD_ELEMS * 8)
        bne @loop
        rts

; ---------------------------------------------------------------- particles

; spawn one particle from np_* (np_x / np_y in pixels)
fx_spawn:
        .a8
        .i16
        phx
        ldx #$0000
:       lda parts + PT_LIFE,x
        beq @found
        A16
        txa
        clc
        adc #PTSIZE
        tax
        A8
        cpx #(PTSIZE * NPARTS)
        bne :-
        plx
        rts
@found: lda np_life
        sta parts + PT_LIFE,x
        lda np_attr
        sta parts + PT_ATTR,x
        lda np_flags
        sta parts + PT_FLAGS,x
        stz parts + PT_T,x
        A16
        lda np_tile
        sta parts + PT_TILE,x
        lda np_x
        asl a
        asl a
        asl a
        asl a
        sta parts + PT_X,x
        lda np_y
        asl a
        asl a
        asl a
        asl a
        sta parts + PT_Y,x
        lda np_vx
        sta parts + PT_VX,x
        lda np_vy
        sta parts + PT_VY,x
        A8
        plx
        rts

; confetti flying out of np_x / np_y
fx_confetti:
        .a8
        .i16
        phx
        phy
        ldy #$0000
:       A16
        lda burst_vx,y
        sta np_vx
        lda burst_vy,y
        sta np_vy
        tya
        and #$000E
        tax
        lda confetti_tiles,x
        sta np_tile
        A8
        tya
        and #$02
        asl a
        asl a
        asl a
        asl a
        asl a
        ora #ATTR_FX
        sta np_attr
        lda #(PF_GRAV | PF_FLUTTER)
        sta np_flags
        lda #50
        sta np_life
        jsr fx_spawn
        iny
        iny
        cpy #20
        bne :-
        ply
        plx
        rts

fx_sparkles:
        .a8
        .i16
        phx
        phy
        ldy #$0000
:       A16
        lda spark_vx,y
        sta np_vx
        lda spark_vy,y
        sta np_vy
        lda #SPARK_TILE
        sta np_tile
        A8
        lda #ATTR_FX
        sta np_attr
        lda #PF_TWINKLE
        sta np_flags
        lda #22
        sta np_life
        jsr fx_spawn
        iny
        iny
        cpy #8
        bne :-
        ply
        plx
        rts

; sparkles around player X
fx_ring:
        .a8
        .i16
        phy
        A16
        lda players + P_X,x
        xba
        and #$00FF
        clc
        adc #8
        sta np_x
        lda players + P_Y,x
        xba
        and #$00FF
        clc
        adc #10
        sta np_y
        A8
        ldy #$0000
:       A16
        lda ring_vx,y
        sta np_vx
        lda ring_vy,y
        sta np_vy
        lda #SPARK_TILE
        sta np_tile
        A8
        lda #ATTR_FX
        sta np_attr
        lda #PF_TWINKLE
        sta np_flags
        lda #26
        sta np_life
        jsr fx_spawn
        iny
        iny
        cpy #12
        bne :-
        ply
        rts

; a heart floats up from player X
fx_heart:
        .a8
        .i16
        A16
        lda players + P_X,x
        xba
        and #$00FF
        clc
        adc #8
        sta np_x
        lda players + P_Y,x
        xba
        and #$00FF
        sec
        sbc #6
        sta np_y
        stz np_vx
        lda #.loword(-12)
        sta np_vy
        lda #HEART_TILE
        sta np_tile
        A8
        lda #ATTR_FX
        sta np_attr
        lda #PF_SWAY
        sta np_flags
        lda #40
        sta np_life
        jmp fx_spawn

fx_party_confetti:
        .a8
        .i16
        phx
        jsr rand
        A16
        and #$00FF
        sec
        sbc #8
        sta np_x
        lda #.loword(-16)
        sta np_y
        stz np_vx
        A8
        lda #10
        jsr rand_n
        A16
        and #$00FF
        clc
        adc #14
        sta np_vy
        A8
        lda #10
        jsr rand_n
        asl a
        ZB
        tax
        A16
        lda confetti_tiles,x
        sta np_tile
        A8
        jsr rand
        and #$C0
        ora #ATTR_FX
        sta np_attr
        lda #(PF_SWAY | PF_FLUTTER)
        sta np_flags
        lda #255
        sta np_life
        jsr fx_spawn
        plx
        rts

parts_update:
        .a8
        .i16
        ldx #$0000
@loop:  lda parts + PT_LIFE,x
        beq @next
        dec parts + PT_LIFE,x
        beq @next
        inc parts + PT_T,x
        lda parts + PT_FLAGS,x
        sta t4
        and #PF_FLUTTER
        beq :+
        lda parts + PT_T,x
        and #$07
        bne :+
        lda parts + PT_ATTR,x
        eor #$40
        sta parts + PT_ATTR,x
:       lda t4
        and #PF_SWAY
        beq :+
        lda parts + PT_T,x
        lsr a
        and #$1E
        ZB
        tay
        A16
        lda sway_tab,y
        sta parts + PT_VX,x
        A8
:       A16
        lda parts + PT_X,x
        clc
        adc parts + PT_VX,x
        sta parts + PT_X,x
        lda parts + PT_Y,x
        clc
        adc parts + PT_VY,x
        sta parts + PT_Y,x
        A8
        lda t4
        and #PF_GRAV
        beq :+
        A16
        lda parts + PT_VY,x
        clc
        adc #3
        sta parts + PT_VY,x
        A8
:       A16
        lda parts + PT_Y,x
        cmp #(232 * 16)
        A8
        bmi @next
        stz parts + PT_LIFE,x
@next:  A16
        txa
        clc
        adc #PTSIZE
        tax
        A8
        cpx #(PTSIZE * NPARTS)
        beq :+
        jmp @loop
:       rts

parts_draw:
        .a8
        .i16
        ldx #$0000
@loop:  lda parts + PT_LIFE,x
        bne :+
        jmp @next
:       A16
        lda parts + PT_X,x
        cmp #$8000
        ror a
        cmp #$8000
        ror a
        cmp #$8000
        ror a
        cmp #$8000
        ror a
        sta spr_x
        clc
        adc #16
        cmp #(256 + 16)
        bcs @off
        lda parts + PT_Y,x
        cmp #$8000
        ror a
        cmp #$8000
        ror a
        cmp #$8000
        ror a
        cmp #$8000
        ror a
        sta spr_y
        clc
        adc #16
        bmi @off
        lda parts + PT_TILE,x
        sta spr_tile
        A8
        lda parts + PT_FLAGS,x
        and #PF_TWINKLE
        beq :+
        lda parts + PT_T,x
        and #$04
        beq :+
        lda spr_tile
        clc
        adc #2
        sta spr_tile
:       lda parts + PT_ATTR,x
        sta spr_attr
        stz spr_size
        jsr oam_add
        bra @next
@off:   A8
@next:  A16
        txa
        clc
        adc #PTSIZE
        tax
        A8
        cpx #(PTSIZE * NPARTS)
        beq :+
        jmp @loop
:       rts
