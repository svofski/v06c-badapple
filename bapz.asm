        ;
        ; Bad Apple animation player by svofski 2023
        ;
        ; vi53vtk player by Denis Grachev
        ; dzx0 by ivagor
        ; 
        .tape v06c-rom
        .project bap.rom
        .org $100

PLAYER_BASE equ $2000
player_init equ PLAYER_BASE+0
player_tick equ PLAYER_BASE+3
songe       equ PLAYER_BASE+6
        
ROW_BYTES       equ 8
ROWS            equ 48
TILE_H          equ 2
TILEMAP_SZ      equ 24 
TILE_BITS       equ 8

FIRSTCOL  equ $e0
FIRSTROW  equ $e0

SONGE_FIRST_FRAME equ 19

FIRSTCOL_B  equ $c0

        di
        xra a
        out $10
        lxi sp, $100

        mvi a, $c3
        sta 0
        lxi h, $100
        shld 1

        lxi h, vsync
        lxi d, $38
        mvi c, vsync_end - vsync + 1
copyvsync:
        mov a, m \ inx h
        stax d \ inx d
        dcr c
        jnz copyvsync

        xra a
        sta burakhi_page
        sta dzx0_finish_ctr
        sta screen_sel
        sta songe_enabled
        sta intcount
        sta kvaz_buffer_ready
        call set_screen

        lxi h, 0
        shld burakhi_sp
        shld frame_copy_cnt
        shld unpacked_frame_ptr
        shld frame_count

        lxi h, tilemap
        call zero256_aligned
        call zero256_aligned
        lxi h, framebmp
        call zero256_aligned
        call zero256_aligned

        ; init muzon
        lhld songe
        call player_init


;dzx0_finish_ctr db 0
;burakhi_sp      dw 0
;burakhi_page    db 0
;frame_copy_cnt      dw 0
;unpacked_frame_ptr  dw 0
;intcount  db 0
;screen_sel db 0
;tilemap_ptr dw 0
;bitmaps_ptr dw 0
;tile_i      db 0

        ei
        hlt

        call clrscr

        call prepare_table4x4

        ; prime the input buffer for unpacker
        call fetch_next_input_buffer

        ; fall directly into dzx0
        lxi d, packed_data_begin        ; kvas read buffer
        lxi b, unpack_buf

;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

                ;; dzx0()
                ;; 
                ;; Unpack zx0 stream packed with 256-byte sized window.
                ;; Yields every 256 bytes
dzx0:
		lxi h,0FFFFh            ; tos=-1 offset?
		push h
		inx h
		mvi a,080h
dzx0_literals:  ; Literal (copy next N bytes from compressed file)
		call dzx0_elias         ; hl = read_interlaced_elias_gamma(FALSE)
;		call dzx0_ldir          ; for (i = 0; i < length; i++) write_byte(read_byte()
		push psw
dzx0_ldir1:
		ldax d
		stax b
                inr e \ cz fetch_next_input_buffer
		inr c                   ; stay within circular buffer

		cz dzx0_yield           ;; yield every 256 bytes

		;dcx h
		;mov a,h
		;ora l
                dcr l                   ; input is 256-byte-aligned

		jnz dzx0_ldir1
		pop psw
		add a

		jc dzx0_new_offset      ; if (read_bit()) goto COPY_FROM_NEW_OFFSET
	
		; COPY_FROM_LAST_OFFSET
		call dzx0_elias         ; hl = read_interlaced_elias_gamma(FALSE) 
dzx0_copy:
		xchg                    ; hl = src, de = length
		xthl                    ; ex (sp), hl:
		                        ; tos = src
		                        ; hl = -1
		push h                  ; push -1
		dad b                   ; h = -1 + dst
		mov h, b                ; stay in the buffer!
		xchg                    ; de = dst + offset, hl = length
		push psw

                mov a, h
                ora a
                jnz dzx0_ldir_from_longbuf  ; this is incorrect, but it happens..
dzx0_ldir_from_buf:
		ldax d
		stax b
		inr e
		inr c                   ; stay within circular buffer
		cz dzx0_yield           ;; yield every 256 bytes

		;dcx h
		;mov a,h
		;ora l
                dcr l                   ; can't take more than 256 bytes from buffer

		jnz dzx0_ldir_from_buf
		;mvi h,0
		pop psw
		add a
		                        ; de = de + length
		                        ; hl = 0
		                        ; a, carry = a + a 
		xchg                    ; de = 0, hl = de + length .. discard dst
		pop h                   ; hl = old offset
		xthl                    ; offset = hl, hl = src
		xchg                    ; de = src, hl = 0?
		jnc dzx0_literals       ; if (!read_bit()) goto COPY_LITERALS
                jmp dzx0_new_offset


dzx0_ldir_from_longbuf:
		ldax d
		stax b
		inr e
		inr c                   ; stay within circular buffer
		cz dzx0_yield           ;; yield every 256 bytes

		dcx h
		mov a,h
		ora l                   ; wtf! can't copy > 256 bytes but we do
		jnz dzx0_ldir_from_longbuf
		;mvi h,0
		pop psw
	        add a
		                        ; de = de + length
		                        ; hl = 0
		                        ; a, carry = a + a 
		xchg                    ; de = 0, hl = de + length .. discard dst
		pop h                   ; hl = old offset
		xthl                    ; offset = hl, hl = src
		xchg                    ; de = src, hl = 0?
		jnc dzx0_literals       ; if (!read_bit()) goto COPY_LITERALS
		
		; COPY_FROM_NEW_OFFSET
		; Copy from new offset (repeat N bytes from new offset)
dzx0_new_offset:
		call dzx0_elias         ; hl = read_interlaced_elias_gamma()
		mov h,a                 ; h = a
		pop psw                 ; drop offset from stack
		xra a                   ; a = 0
		sub l                   ; l == 0?
		;rz                      ; return
		jz dzx0_ded
		push h                  ; offset = new offset
		; last_offset = last_offset*128-(read_byte()>>1);
		rar\ mov h,a            ; h = hi(last_offset*128)
		ldax d                  ; read_byte()
		rar\ mov l,a            ; l = read_byte()>>1
		;inx d                   ; src++
                inr e \ cz fetch_next_input_buffer
		xthl                    ; offset = hl, hl = old offset
		
		mov a,h                 ; 
		lxi h,1                 ; 
		cnc dzx0_elias_backtrack; 
		inx h
		jmp dzx0_copy
dzx0_elias:
		inr l
dzx0_elias_loop:	
		add a
		jnz dzx0_elias_skip
		ldax d
                inr e \ cz fetch_next_input_buffer
		ral
dzx0_elias_skip:
		rc
dzx0_elias_backtrack:
		dad h
		add a
		jnc dzx0_elias_loop
		jmp dzx0_elias
;dzx0_ldir:
;		push psw
;		mov a, b
;		cmp d
;		jz dzx0_ldir_from_buf

                ; reached the end of stream
dzx0_ded       
                ; notify gigachad that this stream has finished
                lxi h, dzx0_finish_ctr
                inr m
                ; idle forever: gigachad will restart the task/stream
                call dzx0_yield
                jmp $-3

                ;; get input buffer for the unpacker
                ;;
                ;; usually without disabling interrupts, because
                ;; prefetch_buf will often be ready for consumption
                ;;
fetch_next_input_buffer:
                push psw
                push b 
                push d

                lda kvaz_buffer_ready
                ora a
                cz read_from_kvaz

                lxi b, prefetch_buf
                lxi d, packed_data_begin
fpf_l1:
                ldax b \ stax d \ inr c \ inr e 
                ldax b \ stax d \ inr c \ inr e 
                ldax b \ stax d \ inr c \ inr e 
                ldax b \ stax d \ inr c \ inr e 
                ldax b \ stax d \ inr c \ inr e 
                ldax b \ stax d \ inr c \ inr e 
                ldax b \ stax d \ inr c \ inr e 
                ldax b \ stax d \ inr c \ inr e 
                jnz fpf_l1

                xra a
                sta kvaz_buffer_ready
                
                pop d
                pop b
                pop psw
                ret

                ;;
                ;; read a 256-byte buffer from kvaz OR from tail in RAM
                ;; 
                ;; it's critical to call it soon after frame interrupt
                ;; otherwise we lose interrupts rather often
                ;;
read_from_kvaz:
                push psw
                push b 
                push d
                push h
kvaz_buffer_ready   equ .+1
                mvi a, 0
                ora a
                jnz fnib_return   ;; cannot read next buffer before this one is consumed

                lxi h, 0
                di
                dad sp
                shld fetch_savesp
                
                lda burakhi_page
                ani $10
                jnz fetch_begin ; conventional ram extra page

fetch_from_ed0:
                lda burakhi_page
                ori $10
                out $10

fetch_begin:
                lhld burakhi_sp
                sphl
                lxi h, prefetch_buf ; packed_data_begin
fetch_loop:
                pop d
                mov m, e \ inr l \ mov m, d \ inr l
                pop d
                mov m, e \ inr l \ mov m, d \ inr l
                pop d
                mov m, e \ inr l \ mov m, d \ inr l
                pop d
                mov m, e \ inr l \ mov m, d \ inr l
                pop d
                mov m, e \ inr l \ mov m, d \ inr l
                pop d
                mov m, e \ inr l \ mov m, d \ inr l
                pop d
                mov m, e \ inr l \ mov m, d \ inr l
                pop d
                mov m, e \ inr l \ mov m, d \ inr l
                jnz fetch_loop

                lxi h, 0
                dad sp
                shld burakhi_sp
                mov a, h
                ora l
                jnz fetch_return

                ; next burakhi page
                lda burakhi_page
                adi $04
                sta burakhi_page
                ani $10     ; reached the end?
                jz fetch_return

                ; switch over to the remainder in conventional ram 
                lxi h, disk_remainder
                shld burakhi_sp
                
fetch_return:
                xra a
                out $10
fetch_savesp    equ . + 1
                lxi sp, 0
                ei
                mvi a, 1
                sta kvaz_buffer_ready
fnib_return:
                pop h
                pop d
                pop b
                pop psw

                ret
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;


        
        ; unpacker callback, 256 bytes ready in unpack_buf
        ; we need to assemble frame data from pieces if they cross
        ; unpack_buf bounary, then invoke unpacked_frame_cb()
dzx0_yield:
        push psw
        push b
        push d
        push h

        lda dzx0_finish_ctr
        ora a

        jnz movie_ended

        lxi b, unpack_buf           ; bc has 256 unpacked bytes

        lhld frame_copy_cnt         
        mov a, h
        ora l
        xchg                        ; de = remaining bytes in frame
        lhld unpacked_frame_ptr     ; to continue from previous call
        jnz framecopy_continue      ; continuing previous frame

framecopy_newframe:                 ; otherwise setup new frame
        lxi h, unpacked_frame       ; hl = unpacked_frame
        ldax b                      ; a = *unpack_buf
        add a                       ; double the count
        mov e, a
        mvi a, 0
        aci 0
        mov d, a                    ; de = byte count
        
        inr c                       ; unpack_buf++
        jz framecopy_done           ; 

framecopy_continue:

        xra a
        ora d
        jnz framecopy_loop

framecopy_shortloop:
        ldax b
        mov m, a \ inx h
        dcr e
        jz unpacked_frame_ready
        inr c
        jnz framecopy_shortloop
        jmp framecopy_done

framecopy_loop:
        ldax b ;\ inr c             ; a = *unpack_buf
        mov m, a \ inx h            ; *unpacked_frame_ptr++ = a, keep flags
        
        dcx d \ mov a, d \ ora e

        jz  unpacked_frame_ready    ; process frame (callee saves)

        inr c                       ; ++unpack_buf, z if buf done 
        jnz framecopy_loop
        jmp framecopy_done

        ; full bloomed frame data assembled -> pass to the next stage
unpacked_frame_ready:
        call unpacked_frame_cb        ; process and display frame

        inr c                       ; ++unpack_buf, z if buf done
        jnz framecopy_newframe

framecopy_done:
        shld unpacked_frame_ptr
        ; fallthrough if last byte processed
        xchg
        shld frame_copy_cnt

        pop h
        pop d
        pop b
        pop psw
        ret

        ;;
        ;; full frame ready in unpacked_frame
        ;;
unpacked_frame_cb:
        push b
        push d
        push h

        ; debloom unpacked frame, produces 64x48 bitmap (8 columns, 48 rows)
        call debloom_frame

        ;;
        ;; main sync point
        ;;
        ei    
        hlt
        ; prefetch input buffer from kvaz at known time to avoid losing interrupts
        call read_from_kvaz
        ; scale debloomed picture to screen page
        call fts_4xi

        ; count frames and start songe at preset time
        lhld frame_count
        inx h
        shld frame_count
        xra a
        ora h
        jnz not_starting_songe
        mvi a, SONGE_FIRST_FRAME 
        cmp l
        jnz not_starting_songe
        mvi a, 1
        sta songe_enabled

not_starting_songe:
        ; skip extra frames in case we're too quick
        call wait_vsync_and_flip

        ; return back to the frame assembly loop
        pop h
        pop d
        pop b
        ret

        ; no more frames --> pass on to the next stage in the show
movie_ended:
        di
        hlt

wait_vsync_and_flip:
        lxi h, intcount
syncwait:
        di
        mov a, m
        cpi 3
        jz synchlt    ; exact
        jp syncskip   ; too much, catch up without sync
        ei
        hlt           ; idle one frame
        jmp syncwait
synchlt:
        ei
        hlt
syncskip:
        xra a
        mov m, a

        ; flip screens
        lda screen_sel
        xri 1
        sta screen_sel
        call set_screen
        ret


        ;; vsync interrupt
        ;; this code is relocated to $0038
vsync:
        push psw
        lda intcount
        inr a
        sta intcount
        push b
set_palette_vec equ $-vsync+1 + 0x38
        call 0                        ; set palette, or return rn
        push d
        push h
        lda songe_enabled
        ora a
        cnz player_tick               ; play songe from the interrupt
        pop h
        pop d
        pop b
        pop psw
        ei
        ret
vsync_end:
        ;; end of relocated code

        ;; tilemap, bitmaps --> 64x48 bitmap (8*48 bytes)
        ;; for optimisation sake, the output bitmap is interlaced
        ;; framebmp has even lines, framebmp+256 has odd
debloom_frame:
        mvi a, TILEMAP_SZ + 1
        sta tile_i

        lxi h, tilemap
        shld tilemap_ptr

        lxi d, framebmp       ; destination, unpacked bits, 2 bitplanes for even/odd subtiles
        lxi h, bitmaps

        jmp debloom_next_tile

debloom_advance_de_1x
        mvi a, 8
        add e
        mov e, a
debloom_next_tile:

        push h

        lxi h, tile_i
        dcr m
        jz debloom_return

        xra a
        lhld tilemap_ptr
        ora m \ inx h      ; load tile, tile empty?
        shld tilemap_ptr

        pop h

        jz debloom_advance_de_1x   ;   empty -> next

        mov b, a              ; keep tile bits in b
        mvi c, TILE_BITS      ; 64px wide, 8 significant bits
debloom_nextbit:
        mov a, b
        ral
        mov b, a
        jc debloom_copy

debloom_skip:
        inr e                 ; skip to the next column
        dcr c
        jnz debloom_nextbit 
        jmp debloom_next_tile

debloom_return:
        pop h
        ret

debloom_copy:
        ; take TILE_H (2) bytes from bitmaps stream
        ; *de = *hl++
        mov a, m \ inx h \ stax d
        inr d ; -> bitplane 1, same position
        ; *de = *hl++
        mov a, m \ inx h \ stax d
        dcr d ; -> bitplane 0
        inr e ;    advance position
        
        dcr c
        jnz debloom_nextbit
        jmp debloom_next_tile

        ;; variables
dzx0_finish_ctr db 0
burakhi_sp      dw 0
burakhi_page    db 0
frame_copy_cnt      dw 0
unpacked_frame_ptr  dw 0
intcount  db 0
screen_sel db 0
tilemap_ptr dw 0
bitmaps_ptr dw 0
tile_i      db 0
frame_count dw 0
songe_enabled db 0

        ;; x4 scaler table, 256x4
        ;; 1 byte expands to 4 on screen
        ;; ----------------------------- ---- -    -
        ;; BIG WARNING
        ;; this table can only be at address 0x400, or 0x1400, ...
        ;; --------- ---- --------------   ---  - 
        .org 0x400
table4x4:   ds 1024

        ;; scale frame bitmap to screen, 2 bits --> byte, fill 2 rows in parallel
        ;; the scaler kernel in expand_mfb_4x.inc
fts_4xi:
        mvi a, ROWS >> 1
        sta fts_cnt

        lxi h, framebmp     ; source smol bitmaps (even/odd), de big
        mvi e, FIRSTROW
        mvi b, table4x >> 8

        mov c, e \ dcr c \ dcr c
ftsm_L1:
patch_b1  equ . + 1
        mvi d, FIRSTCOL
        mov b, d

        .include expand_mfb_4x.inc 
        .include expand_mfb_4x.inc 
        .include expand_mfb_4x.inc 
        .include expand_mfb_4x.inc 
        .include expand_mfb_4x.inc 
        .include expand_mfb_4x.inc 
        .include expand_mfb_4x.inc 
        .include expand_mfb_4x_last.inc 

        mvi a, -4 \ add e \ mov e, a    ; de += 4 (screen line)
        sui 2 \ mov c, a                ; bc = de + 2 (secondary line)

        mvi a, -8 \ add l \ mov l, a
        inr h                           ; hl = framebmp[even]

patch_b2  equ . + 1
        mvi d, FIRSTCOL
        mov b, d

        .include expand_mfb_4x.inc 
        .include expand_mfb_4x.inc 
        .include expand_mfb_4x.inc 
        .include expand_mfb_4x.inc 
        .include expand_mfb_4x.inc 
        .include expand_mfb_4x.inc 
        .include expand_mfb_4x.inc 
        .include expand_mfb_4x_last.inc 

        dcr h                           ; hl = framebmp[odd]

        mvi a, -4 \ add e \ mov e, a    ; de += 4
        sui 2 \ mov c, a                ; bc = de + 2 (secondary line)

fts_cnt equ . + 1
        mvi a, 0
        dcr a
        sta fts_cnt
        jnz ftsm_L1
        ret


; ---------------------------------------
; See expand_mfb_4x.inc
; ---------------------------------------
;        ; expand byte x 4 in t=280 with table[256*4]
;        ; table MUST be at address 0x400, or 0x1400, ... 
;expand_mfb_4x:
;        push h        ; 16 + 8 + 8 + 12 + 12 + 8 + 4 + 8 + 12 = 88
;
;        mov l, m
;        mvi h, table4x4>>10   ; this only works if table4x4 & 0x0300 == 0
;        dad h
;        dad h
;
;        mov a, m \ inx h \ stax d \ inr d \ stax b \ inr b  ; 48 * 4 - 8 = 184
;        mov a, m \ inx h \ stax d \ inr d \ stax b \ inr b
;        mov a, m \ inx h \ stax d \ inr d \ stax b \ inr b
;        mov a, m \       \ stax d \ inr d \ stax b \ inr b
;        pop h
;        inr l
;        ret
; ---------------------------------------


        ; calculate scale table for 256 bytes, each byte expands to 4
prepare_table4x4:
        mvi b, 0
        lxi d, table4x4
pt4x4_l2:
        mov h, b
        mvi c, 4
pt4x4_l1:
        xra a    ; 00 0f f0 ff
        dad h
        jnc $+5
        ori $f0
        dad h
        jnc $+5
        ori $0f
        stax d

        inx d
        dcr c
        jnz pt4x4_l1

        inr b
        jnz pt4x4_l2
        ret


;;;;;;;;;;;;;;;;
        ;
        ; Микро-библиотека для Вектора-06ц
        ;

        ; Очистка всей экранной области
clrscr
        di
        lxi h,0
        dad sp
        shld clrscr_ssp

        lxi sp, 0
        lxi b, 0
        lxi d, $800; $400x2 clear screens e000 and c000
_clrscr_1:
        push b
        push b
        push b
        push b
        dcx d
        mov a, d
        ora e
        jnz _clrscr_1

clrscr_ssp equ $+1
        lxi sp, 0
        ret

; xxx1 255
; xxx0 0
set_palette_e0:
        mvi a, 88h      ; настроить ППИ
        out 0

        mvi a, 255      ; сбросить прокрутку
        out 03
        mvi c, $f
set_palette_e0_loop
        mov a, c
        out 2
        ani 1
        mvi a, $ff
        jnz $+4
        xra a
        out $c
        out $c
        out $c
        out $c
        dcr c
        jp set_palette_e0_loop
        mvi a, set_palette_dummy & 255
        sta set_palette_vec
        mvi a, set_palette_dummy >> 8
        sta set_palette_vec+1
        ret 

; xx1x 255
; xx0x 0
set_palette_c0:
        mvi a, 88h      ; настроить ППИ
        out 0

        mvi a, 255      ; сбросить прокрутку
        out 03
        mvi c, $f
set_palette_c0_loop:
        mov a, c
        out 2
        ani 2
        mvi a, $ff
        jnz $+4
        xra a
        out $c
        out $c
        out $c
        out $c
        dcr c
        jp set_palette_c0_loop
        mvi a, set_palette_dummy & 255
        sta set_palette_vec
        mvi a, set_palette_dummy >> 8
        sta set_palette_vec+1
        ret

set_palette_dummy:
        ret

        ;; select screen 0 (e0) or 1 (c0)
set_screen:         
        lda screen_sel
        ora a
        mvi a, FIRSTCOL_B
        lxi h, set_palette_e0
        jnz screen_sel_b
        lxi h, set_palette_c0
        mvi a, FIRSTCOL
screen_sel_b:
        sta patch_b1 
        sta patch_b2 
        ;sta patch_b3 
        shld set_palette_vec
        ret

      ; zero block of 256 bytes at HL aligned to 256, advance HL by 256
zero256_aligned:
        xra a
        mov m, a
        inr l
        jnz $-2
        inr h
        ret

;;;;;;;;;;;;;;;;;
        
        ; align for convenience
        .org 0x100 + . & 0xff00

        ; struct { tilemap[24]; bitmaps[512]; } unpacked_frame;
unpacked_frame:
        ; tilemap / bloom map
tilemap ds TILEMAP_SZ
        ; bitmaps for bloom bits
        ;.org tilemap + TILEMAP_SZ
bitmaps ds 512 - TILEMAP_SZ

        ; fully unpacked frame ready for copying to screen
        ;.org 0x100 + . & 0xff00 -- aligned but this expr doesn't work
framebmp  ;ds ROW_BYTES * ROWS
        ds 512

        ; dzx0 unpacks here
        ; .org 0x100 + . & 0xff00 -- aligned but this expr doesn't work
unpack_buf ds 256
        ;ds 256 ; extra guard area

        ; fetch this buffer at known time to avoid losing interrupts
prefetch_buf  ds 256

        ; kvas read buffer
        ; .org 0x100 + . & 0xff00 -- aligned but this expr doesn't work
packed_data_begin:
        ds 256

        .org $1fff
        db 0
        ; remainder of the stream that didn't fit in burakhi (append badap.rem)
disk_remainder:
         

