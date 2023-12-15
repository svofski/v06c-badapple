#!/bin/bash
set -e

PASM=../prettyasm/main.js
FDDUTIL=../fddutil/fddutil.js
BIN2WAV=../bin2wav/bin2wav.js
ZX0=./tools/zx0.exe
PNG2DB=./tools/png2db-arzak.py
BADAPPY=./tools/badap.py

ZX0_ORG=4000
PLAYER_ORG=2000

PLAYER="-DPLAYER_BASE=\$$PLAYER_ORG"
LOADER="-DWITH_LOADER=1"

MAIN=bapz
ROM=$MAIN-raw.rom
ROMZ=$MAIN.rom
WAV=$MAIN.wav
ROM_ZX0=$MAIN.zx0
DZX0_BIN=dzx0-fwd.$ZX0_ORG
RELOC=reloc-zx0
RELOC_BIN=$RELOC.0100
EDD=badap.edd     # zx0 compressed stream padded to 256K
WLZ=badap.wlz     # zx0 compressed stream
WITHPLAYER=y$ROM
FDD=badaps.fdd    # the main product is in this floppy image

rm -f $ROM_ZX0 $ROM


$PASM $LOADER $PLAYER $MAIN.asm -o $ROM

ROM_SZ=`cat $ROM | wc -c`
echo "$ROM: $ROM_SZ octets"

# animation data
if ! test -a $EDD ; then
    $BADAPPY
fi

if ! test -a $EDD ; then
    echo "$BADAPPY did not produce $EDD, problem"
    exit 1
fi

# muzon
cd muzon/music
./vt2vi53Converter.exe badap01.vt2 3
cd ..
./sjasmplus.exe main.asm -DPLAYER_BASE="$PLAYER_ORG"h --lst=player.lst
cd ..

# if we had a kvaz remainder like for 25fps, but not now
#cat $ROM badap.rem >y$ROM

cat $ROM muzon/player.bin badap.rem >$WITHPLAYER
ls -l $WITHPLAYER

# loader
#$PASM loader.asm -o loader.com
cp $WITHPLAYER badap.com

cat <<TOHERE >initial.sub
BADAP

TOHERE

# fdd
$FDDUTIL -r ryba.fdd -i badap.com -i badap.wlz -i initial.sub -o $FDD

