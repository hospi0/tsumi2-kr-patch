# -*- coding: utf-8 -*-
"""`main.dol` 섹션 표 — 파일 오프셋 ↔ 메모리 주소.

## ★★★델타는 «하나»가 아니다
전에는 `0x80003F20` 하나로 잡았다. 그건 문자열 풀이 있는 **섹션 11·12 의 값일 뿐**이다.
실제 R2VJ01 `main.dol` :

```
 sec  파일        메모리        크기      delta
  0   0x000100  0x80004000  0x0026A0  0x80003F00
  1   0x0027A0  0x8001DA20  0x2AA140  0x8001B280
  7   0x2AC8E0  0x800066A0  0x00FB60  0x7FD59DC0
  8   0x2BC440  0x80016200  0x007820  0x7FD59DC0
  9   0x2C3C60  0x802C7B60  0x000120  0x80003F00
 10   0x2C3D80  0x802C7C80  0x000020  0x80003F00
 11   0x2C3DA0  0x802C7CC0  0x014540  0x80003F20   ← UI 문자열 풀
 12   0x2D82E0  0x802DC200  0x03D160  0x80003F20
 13   0x315440  0x80460320  0x002240  0x8014AEE0
 14   0x317680  0x804634E0  0x003260  0x8014BE60   ← 이름·라벨 고정폭 표
```

⛔단일 델타로 `<memory>` 패치를 만들면 섹션 13·14 의 문자열이 **BSS 한복판에** 써진다.
  화면은 그대로 원문 — 「패치가 안 먹었다」로 보인다(실제로 `イサ` 가 안 바뀌었다).
⛔포인터 census 도 마찬가지다. 섹션마다 델타로 되돌려야 그 섹션 문자열이 잡힌다.

헤더 : `+0x00` 오프셋 18개 · `+0x48` 주소 18개 · `+0x90` 크기 18개 · `+0xD8` bss/entry.
"""
import struct


def sections(d):
    """-> [(파일오프셋, 메모리주소, 크기)] (크기 0 제외)"""
    off = struct.unpack_from('>18I', d, 0x00)
    adr = struct.unpack_from('>18I', d, 0x48)
    siz = struct.unpack_from('>18I', d, 0x90)
    return [(off[i], adr[i], siz[i]) for i in range(18) if siz[i]]


def to_mem(secs, o):
    """파일 오프셋 -> 메모리 주소. 어느 섹션에도 없으면 None."""
    for f, a, s in secs:
        if f <= o < f + s:
            return a + (o - f)
    return None


def to_file(secs, v):
    """메모리 주소 -> 파일 오프셋. 어느 섹션에도 없으면 None."""
    for f, a, s in secs:
        if a <= v < a + s:
            return f + (v - a)
    return None
