from random import randint

def chunker(seq, size):
    return (seq[pos:pos + size] for pos in range(0, len(seq), size))

# msb first
def bitstream(bytes):
    for b in bytes:
        for i in range(8):
            yield (b & 0x80) >> 7
            b <<= 1

def bytestream(bits):
    for ch in chunker(bits, 8):
        byte = 0
        for bit in reversed(ch):
            byte = (byte >> 1) | ((bit&1) << 7)
        yield byte


# rle: 
#  0    x x x x x x x x  8 unpacked bits verbatim
#  1 0  n n n n n n n n  (n+1) zeros
#  1 1  n n n n n n n n  (n+1) ones
def rle(bytes):
    value = 0
    stream = []
    lastbit = 0
    run = []
    runtype = 0 # 0 = packed 0, 1 = packed 1, 2 = unpacked
    
    allequal = True
    flush = False

    for bit in bitstream(bytes):
        if allequal:
            if bit == lastbit:
                run.append(bit)                
                if len(run) == 256:
                    chunk = [1, bit] + [x for x in bitstream([len(run) - 1])]
                    stream += chunk
                    #print "Flushed chunk: ", chunk
                    run = []
            else:
                # if run is longer than 8 bits, flush it as packed
                if len(run) > 7:
                    chunk = [1, lastbit] + [x for x in bitstream([len(run) - 1])]
                    stream += chunk
                    #print "Flushed chunk: ", chunk
                    allequal = True # be optimistic, expect single inversion
                    run = [bit]     # and reinit the run
                else:
                    allequal = False
        
        if not allequal:
            # unpacked run
            run.append(bit)
            if len(run) == 8:
                chunk = [0] + run
                stream += chunk
                #print "Flushed chunk: ", chunk
                run = []
                allequal = True # optimism
        lastbit = bit

    if len(run) > 0:
        if allequal:
            stream += [1, lastbit] + [x for x in bitstream([len(run) - 1])]
        else:
            for i in range(8 - len(run)):
                run.append(0)
            stream += [0] + run

    return bytestream(stream)

def getmode(bitstream):
    b1 = next(bitstream)
    if b1 == 0:
        return 0
    else:
        b2 = next(bitstream)
        return (b1 << 1) | b2

def getbits(bitstream, n):
    return [next(bitstream) for x in xrange(n)]

def getbyte(bitstream):
    return next(bytestream(getbits(bitstream, 8)))

def unrle(bytes):
    run = []
    stream = bitstream(bytes)

    outstream = []
    try:
        while True:
            mode = getmode(stream)
            if mode == 0:
                #print "unpacked bits=",
                bits = getbits(stream, 8)
                #print bits
            else:
                npacked = getbyte(stream) + 1
                bits = [mode & 1] * npacked
                #print "packed ", mode & 1, npacked, bits
            outstream += bits
    except StopIteration:
        pass
    return bytestream(outstream)


def rlespans(b):
    eqspans = []
    i = 1
    eqstart = 0
    eqlen = 0
    while i < len(b):
        while i < len(b) and b[i-1] == b[i]:
            eqlen += 1
            i += 1
        if eqlen > 0:
            # flush nonequals
            neqstart = 0
            if len(eqspans) > 0:
                neqstart = eqspans[-1][2] + 1
            #print(i, "neq", neqstart, eqstart - neqstart)
            if eqstart - neqstart > 0:
                eqspans.append([0, neqstart, eqstart - 1])
            eqspans.append([1, eqstart,eqstart + eqlen])
        eqlen = 0
        eqstart = i
        i += 1

    neqstart = 0
    if len(eqspans) > 0:
        neqstart = eqspans[-1][2] + 1
    if len(b) - neqstart > 0:
        eqspans.append([0, neqstart, len(b) - 1])

    return eqspans

#x = [0]*100 + [1]*100
#print(rlespans(x))
#x = [1, 0, 0, 1, 0, 0, 0, 1, 1, 1, 1, 0, 1, 0]
#print(x, rlespans(x))
#x = [1, 0, 1, 0, 1, 1, 2, 3, 4]
#print(x, rlespans(x))

def encode_spans(b, spans):
    stream = []
    for s in spans:
        slen = s[2] - s[1] + 1
        if s[0] == 1: 
            while slen > 0:
                run = min(0x7f, slen)
                stream += [0x80 | run, b[s[1]]]
                slen -= 128
        else:
            while slen > 0:
                run = min(0x7f, slen)
                stream += [run] + list(b[s[1]:s[1] + run + 1])
                slen -= 128

    return stream

def brle2(x):
    return encode_spans(x, rlespans(x))
             
def witch_encode(b):
    stream = []
    i = 0
    while i < len(b):
        bitmap = b[i]
        color = 255 if bitmap & 1 == 1 else 0 # run colour
        runlen = 0
        i += 1
        while i < len(b) and b[i] == color and runlen < 255:
            runlen += 1
            i += 1
        stream += [bitmap, runlen]
    return stream

# 0,count
# everything else is singular
def witch0_encode(b):
    stream = []
    i = 0
    longruns = 0
    runs = [0] * 256
    while i < len(b):
        if b[i] == 0:
            i += 1
            runlen = 0
            while i < len(b) and b[i] == 0 and runlen < 255:
                runlen += 1
                i += 1
            stream += [0, runlen]
            if i < len(b) and b[i] == 0 and runlen == 255:
                longruns += 1

            runs[runlen] = runs[runlen] + 1  # stats
        else:
            stream += [b[i]]
            i += 1
    #print(f"witch0: {longruns} longruns")
    #print(runs, " median=", runs[128])
    return stream

def witch0_decode(encoded):
    stream = []
    i = 0
    while i < len(encoded):
        b = encoded[i]
        if b > 0:
            stream += [b]
            i += 1
        else:
            i += 1
            count = encoded[i]
            stream += [0] * (count + 1)
            i += 1
    return stream

def witch_decode(encoded):
    stream = []
    for pair in chunker(encoded, 2):
        bitmap = pair[0]
        fill = 255 * (bitmap & 1)
        stream += [bitmap] + [fill] * pair[1]
    return stream


# byte rle: 
# 0xxx xxxx following byte repeats x times
# 1xxx xxxx x unpacked bytes follow

def brle(bytes):
    run = []
    packed = True
    lastbyte = -1
    stream = []
    could = 0
    for byte in bytes:
        if packed:
            if byte == lastbyte or len(run) == 0:
                run.append(byte)
                if len(run) == 128:
                    stream += [127] + [byte]
                    run = []
            else:
                if len(run) > 2:
                    stream += [len(run)-1] + [lastbyte]
                    packed = True
                    run = [byte]
                else:
                    packed = False
                    could = 0
        if not packed:
            run.append(byte)
            if byte != lastbyte:
                could = 0
            if byte == lastbyte:
                could += 1
                if could > 2:
                    unpacked_run = run[:len(run)-could]
                    stream += [0x80 | (len(unpacked_run)-1)] + unpacked_run
                    packed = True
                    run = run[-could:]
                    #print "breaking up: unp=%s newrun=%s" % (repr(unpacked_run), repr(run))
                    could = 0
            elif len(run) == 127:
                stream += [0xfe] + run
                packed = True
                run = []

        lastbyte = byte

    if len(run) > 0:
        if packed:
            stream += [len(run)-1] + [lastbyte]
        else:
            stream += [0x80 | (len(run)-1)] + run
    stream += [0xff]
    return stream

def unbrle(stream):
    output = []
    while True:
        byte = next(stream)
        #print "byte = ", hex(byte)
        if byte == 0xff:
            break
        if byte & 0x80 == 0x80:
            for i in xrange((byte & 0x7f) + 1):
                output.append(next(stream))
        else:
            output += [next(stream)] * ((byte & 0x7f) + 1)

    return output

def test():
    global packed, unpacked
    input = range(10) + [0]*8 + range(10) + [255]*8 + [0x55]
    packed = rle(input)
    print("packed=", [hex(x) for x in packed])
    packed = rle(input)
    unpacked = unrle(packed)
    print("unpacked=", [x for x in unpacked])
    #print [x for x in rle([0]*100)]

def vsum(vectors):
    result = [0] * len(vectors[0])
    for i in range(len(result)):
        for j in range(len(vectors)):
            result[i] += vectors[j][i]

    return result

def vor(vectors):
    result = [0] * len(vectors[0])
    for i in range(len(result)):
        for j in range(len(vectors)):
            result[i] |= vectors[j][i]

    return result


rle3_hist = {}

# 0, 80 invalid
def rle3_encode(x):
    global rle3_hist
    output = []
    spans = []
    i = 1
    current = [0,0]
    while i < len(x) + 1:
        if i != len(x) and x[i] == x[i - 1]:
            current[1] = i
        else:
            if current[1] - current[0] > 0:
                spans += [current]
            current = [i, i]
        i += 1

    i = 0
    for s in spans:
        #print('span:', s[1]-s[0]+1)
        if s[1] - s[0] + 1 < 3:  # ignore shitty short spans
            continue

        if s[0] > i:
            neqlen = s[0] - i

            start = i
            while neqlen > 0:
                wrlen = min(127, neqlen)

                seq = ''.join([f'{x:02x}' for x in [wrlen] + x[start : start + wrlen]])
                n = 0
                try:
                    n = rle3_hist[seq]
                except:
                    pass
                n += 1
                rle3_hist[seq] = n

                output += [wrlen] + x[start : start + wrlen]
                start = start + wrlen
                neqlen -= wrlen

        eqlen = s[1] - s[0] + 1

        repeat = x[s[0]]
        while eqlen > 0:
            wrlen = min(127, eqlen)
            output += [0x80 | wrlen] + [repeat]
            eqlen -= wrlen
        i = s[1] + 1
    
    neqlen = len(x) - i
    start = i
    while neqlen > 0:
        wrlen = min(127, neqlen)
        output += [wrlen] + x[start : start + wrlen]
        start = start + wrlen
        neqlen -= wrlen
    #print('rle3_encode: ', x, '->', output, neqlen)
    return output

def rle3_dumphist():
    itms = list(rle3_hist.items())
    i = [[x[0],x[1] * len(x[0])//2] for x in itms]
    i.sort(key = lambda x: x[1], reverse=True)
    print(i[:20])

rle3_stupid = 0

def rle3_get_stupid():
    global rle3_stupid
    return rle3_stupid

def rle3_reset_stupid():
    global rle3_stupid
    rle3_stupid = 0

def rle3_decode(x):
    global rle3_stupid
    #print('rle3_decode: x=', x)
    output = []
    i = 0
    while i < len(x):
        num = x[i]
        if num & 0x80 == 0x80:
            if num == 1:
                rle3_stupid += 1
            output += [x[i + 1]] * (num & 0x7f)
            i += 2
        else:
            i += 1
            end = i + num
            while i < end:
                output += [x[i]]
                i += 1

    return output

# returns counts:
#  [taken from src, put into dst]
def rle3_decode_chunk(src, dst, dst_ofs = 0):
    s0 = src[0]
    if s0 & 0x80 == 0x80:
        count = s0 & 0x7f
        value = src[1]
        for n in range(count):
            dst[dst_ofs + n] = value
        result = [2, count]
    else:
        count = s0
        for n in range(count):
            dst[dst_ofs + n] = src[n + 1]
        result = [count + 1, count]

    return result


def copy_encode(src):
    return src[:]

def copy_decode(src):
    return src[:]

def autorle_encode(x):
    i = 0
    repeat = 0
    output = []
    while i < len(x):
        if i > 0 and x[i] == x[i - 1] and repeat < 255:
            repeat += 1
            if repeat < 2:
                output += [x[i]]
        else:
            if repeat >= 1:
                output += [repeat - 1]
            repeat = 0
            output += [x[i]]
        i += 1
    if repeat > 0:
        output += [repeat - 1]
    return output
            
def autorle_decode(x):
    output = []
    i = 0
    repeat = 0
    skip = True # skip x[0]
    while i < len(x):
        #print(x[i], repeat)
        if repeat == 1:
            for n in range(x[i]):
                output += [x[i - 1]]
            repeat = 0
            skip = True
        else:
            output += [x[i]]
            if not skip and x[i] == x[i-1]:
                repeat += 1
            else:
                repeat = 0
            skip = False
        i += 1
    return output


#x = [0] * 20 + [1] * 20
x = [1, 0, 0, 1, 0, 0, 0, 1, 1, 1, 1, 0, 1, 0]
#x = [randint(0,256) for x in range(228)]
encoded = autorle_encode(x)
print('source=', x)
print('encoded=', encoded)
decoded = autorle_decode(encoded)
print('decoded=', decoded)
#print('equals=', x == decoded)

#x = [0]*10 + [1]*10
##print(x, brle2(x))
##print(x, brle(x))
#print(x, rle3(x))

#x = [1, 0, 0, 1, 0, 0, 0, 1, 1, 1, 1, 0, 1, 0]
#print(x, brle2(x))
#print(x, brle(x))
#print(x, rle3_encode(x))
#print(rle3_decode(rle3_encode(x)))
#x = [1, 0, 1, 0, 1, 1, 2, 3, 4]
#print(x, rle3(x))
    
#print(encode_spans(x, rlespans(x)))

def bw_transform(s):
    n = len(s)
    m = sorted([s[i:n]+s[0:i] for i in range(n)])
    I = m.index(s)
    #L = ''.join([q[-1] for q in m])
    L = bytes([q[-1] for q in m])
    return (I, L)

print(bw_transform(bytes('a simple burrows-wheeler transform', 'ascii')))

