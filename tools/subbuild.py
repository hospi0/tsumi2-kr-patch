# -*- coding: utf-8 -*-
"""자막 텍스처 39장의 «띠»를 한국어로 다시 굽는다.

    python tools/subbuild.py <원본 texture.arc> <번역.tsv> <출력.arc> [--png 폴더]

## 확정된 픽셀 규약 (39장 전수 실측)
- IA4 는 «명도·알파»가 따로다. 원본은 **흰 글자 + 1px 검은 외곽선**이다 :
    알파 = 글자 + 외곽선 (불투명 255)  ·  명도 = 글자만 238(0xEE)  ·  그 밖은 둘 다 0
  ⛔외곽선 두께는 **1px**(팽창 1회에서 대칭차 376/5968 로 최소 — 실측). 3px 아니다.
  ⛔`work/tx/*.png` 는 «검정에 합성된 RGB»라 알파가 없다 — 알파 규약을 거기서 재면 틀린다.
- 잉크 범위 실측(TX0_0_01 첫 줄) : 명도 y 17~38 · 알파 y 16~39 · x 8~502.
- 글자 폭 상한 : **490px**(외곽선 1px 여유 포함).

## 띠·줄
- 띠 좌표는 SPRX 의 UV 에서 뽑아 `work/sublines.json` 에 있다(48 / 80 / 32 px).
- 80px 띠는 «2줄»이다. 원본 잉크 중심을 그대로 재서 그 자리에 앉힌다
  (계산으로 잡으면 어긋난다 — 원본은 띠 가운데가 아니라 살짝 아래에 있다).
"""
import os, sys, io, json, struct
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import narc, tex0

FONT = r'C:\Windows\Fonts\malgunbd.ttf'
MAXW = 490
INK = 238


def ink_centers(gray, y0, y1, nline):
    """원본 띠에서 «줄마다» 잉크 세로 중심을 잰다."""
    b = gray[y0:y1]
    rows = np.where((b > 64).sum(1) > 0)[0]
    if len(rows) == 0:
        h = y1 - y0
        return [y0 + h * (2 * i + 1) // (2 * nline) for i in range(nline)]
    if nline == 1:
        return [y0 + int(round((rows[0] + rows[-1]) / 2.0))]
    # 두 줄 : 가장 큰 빈 구간에서 자른다
    gaps = [(rows[i + 1] - rows[i], i) for i in range(len(rows) - 1)]
    _, i = max(gaps)
    a, b2 = rows[:i + 1], rows[i + 1:]
    return [y0 + int(round((a[0] + a[-1]) / 2.0)),
            y0 + int(round((b2[0] + b2[-1]) / 2.0))]


def draw_line(inten, alpha, text, cy, w, size0=27):
    """명도·알파 두 장에 한 줄을 가운데 정렬로 그린다."""
    size = size0
    while size > 8:
        f = ImageFont.truetype(FONT, size)
        bb = f.getbbox(text, stroke_width=1)
        if bb[2] - bb[0] <= MAXW and bb[3] - bb[1] <= 30:
            break
        size -= 1
    f = ImageFont.truetype(FONT, size)
    bb = f.getbbox(text, stroke_width=1)
    x = (w - (bb[2] - bb[0])) // 2 - bb[0]
    y = cy - (bb[1] + bb[3]) // 2
    ImageDraw.Draw(alpha).text((x, y), text, font=f, fill=255,
                               stroke_width=1, stroke_fill=255)
    ImageDraw.Draw(inten).text((x, y), text, font=f, fill=INK)
    return size


def main():
    src, tsv, out = sys.argv[1:4]
    pngdir = sys.argv[sys.argv.index('--png') + 1] if '--png' in sys.argv else None
    lines = json.load(open('work/sublines.json'))
    rows = [l.rstrip('\n').split('\t') for l in io.open(tsv, encoding='utf-8')][1:]
    tr = {int(r[0]): (r[1], int(r[2]), int(r[3]), r[6]) for r in rows if len(r) > 6 and r[6].strip()}

    blob = open(src, 'rb').read()
    hdr, ents = narc.parse(blob)
    byname = {e['name']: e for e in ents}
    nb = bytearray(blob)

    bytex = {}
    for n, (tex, y0, y1, txt) in sorted(tr.items()):
        bytex.setdefault(tex, []).append((n, y0, y1, txt))

    small = []
    for tex, items in sorted(bytex.items()):
        e = byname[tex]
        d, w, h, fmt, nmip, t0 = tex0.find_tex0(e['data'])
        assert fmt == 2, '%s IA4 아님' % tex
        im = tex0.ia4_to_image(d[:w * h], w, h)
        inten, alpha = im.split()
        gray = np.array(alpha)
        for n, y0, y1, txt in items:
            parts = txt.split('|')
            cys = ink_centers(gray, y0, y1, len(parts))
            # ★그 띠만 지운다 (명도 0 = 배경)
            ImageDraw.Draw(inten).rectangle([0, y0, w - 1, y1 - 1], fill=0)
            ImageDraw.Draw(alpha).rectangle([0, y0, w - 1, y1 - 1], fill=0)
            for p, cy in zip(parts, cys):
                sz = draw_line(inten, alpha, p, cy, w)
                if sz < 22:
                    small.append((n, sz, p))
        im2 = Image.merge('LA', (inten, alpha))
        raw = tex0.image_to_ia4(im2)
        assert len(raw) == w * h
        datoff = struct.unpack_from('>i', e['data'], t0 + 0x10)[0]
        data = bytearray(e['data'])
        data[t0 + datoff: t0 + datoff + w * h] = raw
        nb[e['off']:e['off'] + e['size']] = data
        if pngdir:
            os.makedirs(pngdir, exist_ok=True)
            bg = Image.new('RGB', im2.size, (0, 0, 0))
            bg.paste(im2.convert('RGB'), (0, 0), im2.split()[1])
            bg.save(os.path.join(pngdir, tex + '.png'))
    assert len(nb) == len(blob), '크기가 바뀌면 안 된다'
    open(out, 'wb').write(bytes(nb))
    print('텍스처 %d장 · 띠 %d개 -> %s' % (len(bytex), len(tr), out))
    print('바뀐 바이트 %d' % sum(1 for a, b in zip(bytes(nb), blob) if a != b))
    if small:
        print('★글자가 22px 미만으로 줄어든 줄 %d개:' % len(small))
        for n, sz, p in small:
            print('   #%-4d %2dpx  %s' % (n, sz, p))


if __name__ == '__main__':
    main()
