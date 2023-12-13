#!/bin/env python3

#
# Bad Apple animation codec for Vector-06c by svofski 2023
#
# ****************************************************************
# ******************************************  ********************
# *****************************************   ********************
# ****************************************     *******************
# ****************************************      ******************
# ****************************************       *****************
# *****************************************          *************
# **************************************              ************
# ************************************                ************
# ***********************************                  ***********
# **********************************                   ***********
# **********************************                   ***********
# *********************************                    ***********
# *********************************                     **********
# *********************************                     **********
# *********************************                     **********
# *********************************                      *********
# **********************************                     *********
# ***********************************                    *********
# ************************************                   *********
# ***********************************                    *********
# ************************************                    ********
# ************************************                    ********
# *************************************                   ********
# *************************************                   ********
# **************************************                  ********
# **************************************                   *******
# **************************************               * * *******
# ***************************************               * ********
# ***************************************               * ********
# **************************************                **********
# **************************************                **********
# *******************     *************                * *********
# *****************       ***********                 ************
# *****************        **********                *************
# *****************        **********                *************
# *****************        **********                *************
# *****************             ****                 *************
# ******************                                  ************
# ******************                                  ************
# *********************                               *  *********
# ***********************                               **********
# ***********************                              ***********
# ***********************                              ***********
# ***********************                              ***********
# ***********************                               **********
# **********************                                **********
# **********************                                 *********


import sys
import os
from subprocess import Popen, PIPE
from PIL import Image
from os import listdir
from os.path import getsize
import numpy as np
from utils import *
from time import sleep
from zipfile import ZipFile
from io import BytesIO

from random import random, shuffle

TOOLS = './tools/'
SALVADOR = TOOLS + 'salvador.exe'

srcpath='ivagor-frames'

SAVE_TILES_SEPARATELY = False
PRINT_DUMPS = False

# write halved length, e.g. 2 = 4 bytes long frame
HALFLENGTH = True
WRITELEN = True

# just for the log/visual monitoring
HSCALE=1

TRIM_FAT_FIRST = True
USE_RLE3 = True
FRAME_W = 64
FRAME_H = 48
HALF_FRAMERATE = True
INTERLACE = False
TILE_H = 2
TILE_BITS = 8

DIFF_TRIM = 12
LOSSY_PROMOTION_LIMIT = 0 # 88 #0 #88 # 68 still fits but not sure if gives visible benefits

rle_encode = copy_encode
rle_decode = copy_decode

if INTERLACE:
    FRAME_H = FRAME_H // 2

row_bytes = FRAME_W // 8
tilemap_size = max(1, row_bytes // 8) * FRAME_H // TILE_H

print(f'INTERLACE={INTERLACE} FRAME_W={FRAME_W} FRAME_H={FRAME_H} tilemap_size={tilemap_size}')

def make_megastream_from_zip():
    megastream=[]
    
    i = 0
    
    frame_h = FRAME_H
    if INTERLACE:
        frame_h *= 2 # double fields for interlace

    with ZipFile(srcpath + '/frames.zip') as zipf:
        for fname in zipf.namelist():
            bmp = zipf.read(fname)
            bmpbytes = BytesIO()
            bmpbytes.write(bmp)
            src = Image.open(bmpbytes)
            img = src.resize([FRAME_W, frame_h])
            data = list(img.getdata()) 
            megastream += list(bytestream(data))
            i += 1
            if i % 10 == 0:
                print(fname, end='\r')
    
    
    b = bytes(megastream)
    out = open('megastream.bin', 'wb')
    out.write(b)
    out.close()

    print(f'created megastream.bin: {getsize("megastream.bin")} bytes')

def make_megastream():
    megastream=[]
    
    i = 0
    
    frame_h = FRAME_H
    if INTERLACE:
        frame_h *= 2 # double fields for interlace

    # raw megastream = 10094592 bytes, salvador -w 256 -> 1453803
    for f in listdir(srcpath):
        src = Image.open(srcpath + '/' + f)
        img = src.resize([FRAME_W, frame_h])
        data = list(img.getdata()) 
        megastream += list(bytestream(data))
        i += 1
        if i % 10 == 0:
            print(f, end='\r')
    
    
    b = bytes(megastream)
    out = open('megastream.bin', 'wb')
    out.write(b)
    out.close()

    print(f'created megastream.bin: {getsize("megastream.bin")} bytes')

# upconvert by 138/125
def upconvert(inputframes):
    k = 125/138
    u = 0
    framebytes = FRAME_W * FRAME_H // 8
    # fuck efficiency
    allframes = list(chunker(inputframes, framebytes))
    noutframes = 0
    stream = []
    while u < len(allframes):
        stream += list(allframes[int(u)])
        u += k
        noutframes += 1

    print(f'upconvert 138/125: {len(allframes)} -> {noutframes}')

    b = bytes(stream)
    out = open('upconverted.bin', 'wb')
    out.write(b)
    out.close()

    print(f'created upconverted.bin: {getsize("upconverted.bin")} bytes')

    return stream


# 5/6 or 5/12 if half = true
def frc(inputframes, half = False, interlace = False):
    frame_h = FRAME_H
    if interlace:
        frame_h *= 2

    framebytes = FRAME_W * frame_h // 8
    stream = []
    srcframes = 0
    nframes = 0
    nfields = 0
    for i, frame in enumerate(chunker(inputframes, framebytes)):
        srcframes += 1
        if (srcframes + 1) % 6 == 0:
            continue
        nframes += 1
        if half and nframes & 1 == 0:
            continue
        if interlace:
            # odd/even
            lines = list(chunker(frame, row_bytes))
            pairs = list(chunker(lines, 2))
            f = [p[nfields & 1] for p in pairs]
            field = [x for sublist in f for x in sublist]
            stream += field
            nfields += 1
        else:
            stream += frame
    print(f"frc: {srcframes} down to {nframes}: {nframes/srcframes}")

    return stream

prev_trim = []


def trim_diff2(diff, sendback, maxdiff = 32, nframe = -1):
    global prev_trim

    # squeeze groups of tile_h rows by or-ring
    vsqueezed = [vor(col) for col in chunker(list(chunker(diff, row_bytes)), TILE_H)]

    # mask centre of frame by zeroing out diffs
    #squeezed_h = len(vsqueezed)
    #centre_h = squeezed_h // 2
    #centre_w = row_bytes // 2
    #for y in range(centre_h):
    #    for x in range(centre_w):
    #        vsqueezed[y + squeezed_h // 4][x + row_bytes // 4] = 0

    flatsqueezed = []
    for row in vsqueezed:
        flatsqueezed += row

    # discard peripheral stuff
    non0i = [i for i,x in enumerate(flatsqueezed) if x != 0]
    #print(f'diffsize={len(non0i)} prev_trim={len(prev_trim)} len(vsq)={len(vsqueezed)} feq: {flatsqueezed == diff}')
    #print(f'non: {non0i}')

    # previous frame catch-up: equal balance of random picks from previous frame with fattest current
    s = set(prev_trim)
    prev_trim = list(s)
    shuffle(prev_trim)
    part = max(len(prev_trim), maxdiff)
    for i in prev_trim[:part]:
        try:
            non0i.remove(i) # ensure that they stay by excluding them from the non0i vector
        except:
            pass
    prev_trim = prev_trim[part:]

    if TRIM_FAT_FIRST:
        # sort new diff by fatness: positions with the most number of bits are kept
        # positions with small number of bits are first to discard
        fatness = []
        for i in non0i:
            y = i // row_bytes
            x = i % row_bytes
            fat = 0
            for r in range(TILE_H):
                idx = (y * TILE_H + r) * row_bytes + x
                fat += bin(diff[idx]).count('1')
            fatness += [[fat, i]]
        fatness.sort(key = lambda x: x[0], reverse=True)

        # take only the indices
        sortednon = [x[1] for x in fatness]
    else:
        sortednon = non0i

    #
    # for lossy compression (LOSSY_PROMOTION_LIMIT > 0)
    #
    # promote some frames based on amount of diff data
    # also it's possible to explicitly specify which frames require promotion

    # upgrade some frames to be more equal than others
    #print(f'frame {nframe}: sortednon: {len(sortednon)}')
    #if nframe == 205:
    #    maxdiff = 100500
    #if len(sortednon[maxdiff:]) > DIFF_TRIM:
    #    print('too lossy')
    #    maxdiff += 12
    if len(sortednon) > LOSSY_PROMOTION_LIMIT:
        if LOSSY_PROMOTION_LIMIT > 0:
            print('too lossy, promoted to I-frame')
        maxdiff = 100500

    # leave the fattest maxdiffs, null out remainder and save it for the next frame
    for i in sortednon[maxdiff:]:
        y = i // row_bytes
        x = i % row_bytes
        for r in range(TILE_H):
            idx = (y * TILE_H + r) * row_bytes + x
            sendback[idx] ^= diff[idx]
            diff[idx] = 0
            
        # for prev_trim use squeezed coordinates
        pidx = y * row_bytes + x
        prev_trim += [pidx]

    #print('excess: ', len(sortednon[maxdiff:]))

    #print('diff after trim:' , diff)
    #for y in range(FRAME_H):
    #    s = f'{y*row_bytes:4}: '
    #    for x in range(row_bytes):
    #        s += f'{bin(diff[y * row_bytes + x]).count("1"):4} '
    #    print(s)

def diff_frames(rawdata):
    framebytes = FRAME_W * FRAME_H // 8
    prevfields = [(),()]
    prevframe = None
    stream = []
    for i, frame in enumerate(chunker(rawdata, framebytes)):
        if prevframe == None:
            prevframe = frame
            prevfields = [list(frame), list(frame)]
            continue
        if INTERLACE:
            prevframe = prevfields[i & 1]
        diff = [x ^ y for x, y in zip(prevframe, frame)]

        #print(f'frame={i}: ', end='')
        trim_diff2(diff, frame, DIFF_TRIM, nframe=i)

        if INTERLACE:
            prevfields[i & 1] = frame
        prevframe = frame
        stream += diff
    return stream

max_frame_bytes = 0

bloomhist={}

def dump_bloomhist():
    print(f'unique tile bitmaps: {len(bloomhist)}')

    itms = list(bloomhist.items())
    itms.sort(key = lambda x: x[1], reverse=True)
    print('most frequent tile bitmaps: ', itms[:20])

# tile_w in bytes
# tile_h in rows
def bloom_frame(diffdata, framedata, tilesbitmaps = None, frame_w=FRAME_W, frame_h=FRAME_H, tile_w = 1, tile_h = TILE_H):
    global max_frame_bytes, tilemap_size

    i = 0
    tilemap = []
    bitmap = []

    row = 0

    # 1) squeeze each tile_h rows in 1 by summing
    vsqueezed = [vsum(col) for col in chunker(list(chunker(diffdata, row_bytes)), tile_h)]
    # make all > 0 into bit weights
    bitweights = [ [int(bool(x)) * (0x80 >> (i % 8)) for i, x in enumerate(row)] for row in vsqueezed]

    tilemap = [sum(x) for x in bitweights]

    for i,tile in enumerate(tilemap):
        frameofs = tile_h * i * tile_w * row_bytes
        for x in range(8):
            if tile & 0x80 != 0:
                key = []
                for y in range(tile_h):
                    bitmap += [framedata[x + frameofs + y * row_bytes]]
                    #print([framedata[x + frameofs + y * row_bytes]], end=',')
                    key += [framedata[x + frameofs + y * row_bytes]]
                k = ''.join([f'{x:02x}' for x in key])
                n = 0
                try:
                    n = bloomhist[k]
                except:
                    pass
                n += 1
                bloomhist[k] = n

            tile <<= 1

    #print('tilemap size=', tilemap_size, ' vs ', len(tilemap))
    result = tilemap + bitmap
    if tilesbitmaps != None:
        tilesbitmaps[0] += tilemap
        tilesbitmaps[1] += bitmap

    max_frame_bytes = max(max_frame_bytes, len(result))

    return tilemap + bitmap

def bloom_encode(diffdata, framedata, frame_w=FRAME_W, frame_h=FRAME_H):
    stream = []
    diffenum = chunker(diffdata, frame_w * frame_h // 8)
    dataenum = chunker(framedata, frame_w * frame_h // 8)
    for i, frm in enumerate(zip(diffenum, dataenum)):
        tiled = bloom_frame(frm[0],frm[1])
        stream += tiled

    print(f'bloom: max frame bytes={max_frame_bytes}')
    return stream

def wloom_encode(diffdata, framedata, frame_w=FRAME_W, frame_h=FRAME_H, dbfile=None):
    stream = []
    diffenum = chunker(diffdata, frame_w * frame_h // 8)
    dataenum = chunker(framedata, frame_w * frame_h // 8)
    maxlen = 0
    rle3_reset_stupid()
    tiles = []
    bitmaps = []
    nframes = 0
    for i, frm in enumerate(zip(diffenum, dataenum)):
        nframes = i + 1
        tiled = bloom_frame(frm[0], frm[1], tilesbitmaps=[tiles, bitmaps])

        if USE_RLE3:
            witched = rle_encode(tiled)
        else:
            witched = witch0_encode(tiled)

        if WRITELEN:
            length = len(witched)
            maxlen = max(maxlen, length)
            if HALFLENGTH:
                if length & 1 == 1:
                    length += 1
                    if USE_RLE3:
                        witched += [0]
                    else:
                        witched += [1]  # alignment padding with non-repeated byte
                wrlen = length // 2
            else:
                wrlen = length
            frame_data = [wrlen] + witched
        else:
            frame_data = witched

        #print(f'writing frame {i} stream pos={len(stream)}')
        stream += frame_data

        #with open(f'framedata/framedata{i:04}.bin', 'wb') as fdata:
        #    fdata.write(bytes(tiled))

        if dbfile != None:
            asm = ','.join([f'${x:02x}' for x in frame_data])
            dbfile.write(f'frame{i:04}: db {asm}\n')

        # verify
        #if USE_RLE3:
        #    try:
        #        dewitched = rle_decode(witched[:length])
        #    except:
        #        print('shitcock')
        #        print('source: ', repr(tiled))
        #        print('rle: ', repr(witched[:length]))
        #else:
        #    dewitched = witch0_decode(witched[:length])
        #if tiled != dewitched:
        #    if tiled != dewitched[:-1]:
        #        print(f'tiled={tiled}\nwitched={witched}\ndewit={dewitched}')

        # dump raw frame data
        #print(' '.join([f'{x:02x}' for x in tiled]))

    if SAVE_TILES_SEPARATELY:
        with open('tiles.bin', 'wb') as to:
            #tiles = rle_encode(tiles)
            to.write(bytes(tiles))
            print(f'wrote tiles.bin: len(tiles) bytes')

    #with open('tiles_t.bin', 'wb') as to:
    #    transposed = np.array(tiles).reshape(nframes,tilemap_size).transpose().reshape(1,len(tiles)).tolist()
    #    rletiles = rle_encode(transposed[0])
    #    to.write(bytes(rletiles))

    
    if SAVE_TILES_SEPARATELY:
        with open('bitmaps.bin', 'wb') as bo:
            #bitmaps = rle_encode(bitmaps)
            bo.write(bytes(bitmaps))

    #print(f'rle3_hist:')
    #rle3_dumphist()
    dump_bloomhist()

    print(f'wloom: max frame bytes={max_frame_bytes}')
    print(f'wloom: max record length={maxlen}')
    #print(f'wloom: rle3 stupid rate={rle3_get_stupid()}')
    return stream

def make_twitch():
    b = open('megastream.bin', 'rb').read()

    # 1 upconvert by 138/125 to match source bpm
    upconverted = upconvert(b)

    # w decimate down by 5/12 
    decimated = frc(upconverted, HALF_FRAMERATE, INTERLACE)
    with open('megastream.frc', 'wb') as out:
        out.write(bytes(decimated));

    differences = diff_frames(decimated)
    with open('megastream.diff', 'wb') as out:
        out.write(bytes(differences))

    dbfile = open('megastream.inc', 'w')
    wloom = wloom_encode(differences, decimated[FRAME_H*FRAME_W//8:], dbfile=dbfile)
    with open('megastream.wloom', 'wb') as out:
        out.write(bytes(wloom))

# prototype wloom decoder
# unwitch0 -> debloom -> diff
def play_tw0():
    global tilemap_size
    frame_w = FRAME_W
    frame_h = FRAME_H
    tile_h = TILE_H

    data = None
    with open('megastream.wloom', 'rb') as fi:
        data = fi.read()

    lastframe = [0] * (row_bytes * frame_h)
    lastfield = [list(lastframe), list(lastframe)]

    frameno = 0
    buf = [0]*512
    i = 0
    while i < len(data):
        print(f'\033[Hframe: {frameno} i: {i}')
        if INTERLACE:
            lastframe = lastfield[frameno & 1]
        # frame starts
        len2 = data[i]
        if HALFLENGTH:
            len2 = data[i] * 2
        if USE_RLE3:
            buf = rle_decode(data[i + 1:i + len2 + 1])
            i += len2 + 1
        else:
            last = i + len2
            i += 1
            bufi = 0
            while i <= last:
                # de-rle one frame
                b = data[i]
                if b > 0:
                    buf[bufi] = b
                    bufi += 1
                    i += 1
                else:
                    i += 1
                    count = data[i]
                    i += 1
                    for n in range(count + 1):
                        buf[bufi] = b
                        bufi += 1

        #print(f'frame: {frameno}\n{buf[:bufi]} ({bufi})')
        frameno += 1

        # debloom the frame
        bits_i = tilemap_size
        frame_pos = 0
        for tile in buf[0:tilemap_size]:
            for n in range(TILE_BITS):
                if tile & 0x80:
                    for y in range(tile_h):
                        lastframe[frame_pos + n + row_bytes * y] = buf[bits_i]
                        bits_i += 1
                tile <<= 1
            frame_pos += row_bytes * tile_h

        if PRINT_DUMPS:
            print('tilemap_bitmap:')
            for x in range(bits_i):
                if (x % 16) == 0:
                    print(f'{x:04x} ', end='')
                print(f'{buf[x]:02x} ', end='')
                if (x + 1) % 16 == 0:
                    print()
            print()
            print('lastframe:')
            for x in range(len(lastframe)):
                if (x % 16) == 0:
                    print(f'{x:04x} ', end='')
                print(f'{lastframe[x]:02x} ', end='')
                if (x + 1) % 16 == 0:
                    print()
            print()

        # print frame
        for y in range(frame_h):
            frame_pos = y * row_bytes
            for field in range(2):
                if INTERLACE:
                    lastframe = lastfield[1 - field]
                for x in range(row_bytes):
                    bitmap = lastframe[x + frame_pos]
                    for n in range(8):
                        if bitmap & 0x80 != 0:
                            print("*" * HSCALE, end='')
                        else:
                            print(" " * HSCALE, end='')
                        bitmap <<= 1 
                print()
                if not INTERLACE:
                    break
        #sleep(0.04 * (1 + int(HALF_FRAMERATE)))

def print_frame(lastframe):
    # print frame
    for y in range(FRAME_H):
        frame_pos = y * row_bytes
        for x in range(row_bytes):
            bitmap = lastframe[x + frame_pos]
            for n in range(8):
                if bitmap & 0x80 != 0:
                    print("*" * HSCALE, end='')
                else:
                    print(" " * HSCALE, end='')
                bitmap <<= 1 
        print()

def kvazify():
    cname = 'megastream.wloom'
    zname = 'megastream.wloomz'
    with Popen([SALVADOR, "-v", "-classic", "-w 256", cname, zname], stdout=PIPE) as proc:
        print(proc.stdout.read())
    
    with open('megastream.wloomz', 'rb') as ff:
        fwd = bytes(ff.read())

    # wlz is for loading from disk
    with open('badap.wlz', 'wb') as wlz:
        rev = list(fwd[:256*1024])
        wlz.write(bytes(rev))

    # edd is the same but padded to 256K with zeros for emulator compatibility
    with open('badap.edd', 'wb') as edd:
        rev = list(fwd[:256*1024])
        if len(rev) < 256*1024:
            rev = rev + [0] * (256*1024 - len(rev))
        edd.write(bytes(rev))

    # this is only for 25fps version, remainder to be put in the main ram
    with open('badap.rem', 'wb') as fuu:
        rev = list(fwd[256*1024:])
        fuu.write(bytes(rev))


    with open('megastream.zmoolw', 'wb') as rf:
        rf.write(bytes(rev))

#frame = [0]*8*47 + [1,1,0,0,0,0,0,0]
#print(twitch_frame(frame, 64, 48, 1, 2))

# tilemap
# frame 64x48 
# ivagor tile: 8x2
# tiles: 8x24 = 192 bit = 24 bytes
# frame: tilemap: fixed 192 bytes + [bitmaps]

try:
    sz = getsize('megastream.bin')
except:
    print(f'could not stat megastream.bin, creating new')
    make_megastream_from_zip()

make_twitch()
#play_tw0()
kvazify()

