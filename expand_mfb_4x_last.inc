        ; expand byte x 4 in t=280 with table[256*4]
        ; table MUST be at address 0x400, or 0x1400, ... 
        push h        ; 16 + 8 + 8 + 12 + 12 + 8 + 4 + 8 + 12 = 88

        mov l, m
        mvi h, table4x4>>10   ; this only works if table4x4 & 0x0300 == 0
        dad h
        dad h

        mov a, m \ inx h \ stax d \ inr d \ stax b \ inr b  ; 48 * 4 = 192
        mov a, m \ inx h \ stax d \ inr d \ stax b \ inr b
        mov a, m \ inx h \ stax d \ inr d \ stax b \ inr b
        mov a, m \       \ stax d \         stax b
        pop h
        inr l

