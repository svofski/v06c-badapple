#!/bin/bash
set -e

PASM=../prettyasm/main.js
BIN2WAV=../bin2wav/bin2wav.js
ZX0=./tools/zx0.exe
PNG2DB=./tools/png2db-arzak.py
BADAPPY=./tools/badap.py

ZX0_ORG=4000
PLAYER_ORG=2000

RSOUND="-DRSOUND=0"
PLAYER="-DPLAYER_BASE=\$$PLAYER_ORG"

MAIN=bapz
ROM=$MAIN-raw.rom
ROMZ=$MAIN.rom
WAV=$MAIN.wav
ROM_ZX0=$MAIN.zx0
DZX0_BIN=dzx0-fwd.$ZX0_ORG
RELOC=reloc-zx0
RELOC_BIN=$RELOC.0100
EDD=badap.edd

rm -f $ROM_ZX0 $ROM


#$PASM $RSOUND $MAIN.asm -o $ROM
$PASM $PLAYER $MAIN.asm -o $ROM

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

cat $ROM muzon/player.bin badap.rem >y$ROM
ls -l y$ROM

#$ZX0 -c $ROM $ROM_ZX0
#ROM_ZX0_SZ=`cat $ROM_ZX0 | wc -c`
#echo "$ROM_ZX0: $ROM_ZX0_SZ octets"
#
#$PASM -Ddzx0_org=0x$ZX0_ORG dzx0-fwd.asm -o $DZX0_BIN
#DZX0_SZ=`cat $DZX0_BIN | wc -c`
#echo "$DZX0_BIN: $DZX0_SZ octets"
#
#$PASM -Ddst=0x$ZX0_ORG -Ddzx_sz=$DZX0_SZ -Ddata_sz=$ROM_ZX0_SZ $RELOC.asm -o $RELOC_BIN
#RELOC_SZ=`cat $RELOC_BIN | wc -c`
#echo "$RELOC_BIN: $RELOC_SZ octets"
#
#cat $RELOC_BIN $DZX0_BIN $ROM_ZX0 > $ROMZ
#
##$BIN2WAV -m v06c-turbo $ROMZ $WAV
#$BIN2WAV -c 5 -m v06c-turbo $ROMZ $WAV
