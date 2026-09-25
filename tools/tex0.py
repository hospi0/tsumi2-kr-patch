# -*- coding: utf-8 -*-
"""BRRES(`bres`) 안의 TEX0 텍스처를 뽑아 PNG 로 편다 / PNG 를 다시 TEX0 로 굽는다.

    python tools/tex0.py list  <arc>              아카이브의 TEX0 목록
    python tools/tex0.py dump  <arc> <출력폴더> [접두]

## 확정된 포맷 (실측)
```
bres 헤더 : 'bres' BOM(FEFF) ver size rootoff(0x10) nsec
TEX0      : 'TEX0' +0x04 size · +0x08 ver(3) · +0x0C outer
            +0x10 dataoff(TEX0 시작 기준) · +0x14 nameoff
            +0x1C u16 w · +0x1E u16 h · +0x20 u32 fmt · +0x24 u32 nmip
```
자막 텍스처는 **512×512 · fmt=2(IA4) · mip=1**. 폰트(`MsgFont.brfnt`)와 같은 IA4 다.

## IA4 (GX)
1바이트 = **상위 4비트 alpha · 하위 4비트 intensity**. 타일은 **8×4**.
⛔타일 순서를 무시하고 선형으로 읽으면 그림이 8×4 블록으로 흩어진다.
"""
import os, sys, struct
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def find_tex0(blob):
    """(데이터, w, h, fmt, nmip, TEX0오프셋) — 없으면 None."""
    i = blob.find(b'TEX0')
    if i < 0:
        return None
    sz, ver, outer, datoff, nameoff, d2, w, h, fmt, nmip = \
        struct.unpack_from('>IIiiiiHHII', blob, i + 4)
    return blob[i + datoff:], w, h, fmt, nmip, i


def ia4_to_image(d, w, h):
    im = Image.new('LA', (w, h))
    px = im.load()
    p = 0
    for ty in range(0, h, 4):
        for tx in range(0, w, 8):
            for y in range(4):
                for x in range(8):
                    v = d[p]; p += 1
                    px[tx + x, ty + y] = (int((v & 0xF) * 255 / 15),
                                          int(((v >> 4) & 0xF) * 255 / 15))
    return im


def image_to_ia4(im):
    """LA 이미지를 IA4 바이트열로. (되넣기용 — 왕복 검증 필수)"""
    w, h = im.size
    px = im.convert('LA').load()
    out = bytearray()
    for ty in range(0, h, 4):
        for tx in range(0, w, 8):
            for y in range(4):
                for x in range(8):
                    i, a = px[tx + x, ty + y]
                    out.append(((a >> 4) << 4) | (i >> 4))
    return bytes(out)


def main():
    import narc
    cmd, arc = sys.argv[1], sys.argv[2]
    hdr, ents = narc.parse(open(arc, 'rb').read())
    pre = sys.argv[4] if len(sys.argv) > 4 else ''
    rows = []
    for e in ents:
        if pre and not e['name'].startswith(pre):
            continue
        t = find_tex0(e['data'])
        if not t:
            continue
        d, w, h, fmt, nmip, off = t
        rows.append((e['name'], w, h, fmt, nmip, e['size'], d))
    if cmd == 'list':
        print('TEX0 %d개' % len(rows))
        for n, w, h, fmt, nm, sz, _ in rows:
            print('  %-20s %4dx%-4d fmt=%d mip=%d  %8dB' % (n, w, h, fmt, nm, sz))
    elif cmd == 'dump':
        out = sys.argv[3]
        os.makedirs(out, exist_ok=True)
        for n, w, h, fmt, nm, sz, d in rows:
            if fmt != 2:
                print('  ⛔%s fmt=%d — IA4 아님, 건너뜀' % (n, fmt)); continue
            im = ia4_to_image(d, w, h)
            bg = Image.new('RGB', (w, h), (0, 0, 0))
            bg.paste(im.convert('RGB'), (0, 0), im.split()[1])
            bg.save(os.path.join(out, n + '.png'))
        print('-> %s 에 %d장' % (out, len(rows)))


if __name__ == '__main__':
    main()
