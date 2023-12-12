	DEVICE ZXSPECTRUM48

;	org 2000h
        org PLAYER_BASE
begin:
	jp vktInit
	jp vktPlay
	dw module
	include "music\player.a80"
module:
	incbin "music\badap01.vtk"     
	savebin "player.bin",begin,$-begin

                                                                                                        

