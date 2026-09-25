# -*- coding: utf-8 -*-
"""자막 텍스처의 «한 줄 띠»를 한글로 다시 그린다.

    python tools/subtex.py <texture.arc> <TX이름> <줄번호> <높이> "<한국어>" [출력.arc]

## 자막 배치 (SPRX 로 확정)
- 자막 한 줄 = 텍스처의 **48픽셀 띠**(2줄짜리는 80px). 줄 n 은 `y = n*48 ~ (n+1)*48`.
- ⛔**띠 경계를 넘으면 다음 줄에 침범한다.** PoC 에서 `y=18~52` 상자가 둘째 줄 위에
  흰 선으로 나타났다. 그리기·지우기 모두 그 줄의 띠 «안에서만».

## 원본 픽셀 규약 (TX0_0_01 첫 줄 실측)
- intensity : 0(외곽선) / 238≈최대(글자)
- alpha     : 0(투명) / 255(불투명) — 외곽선도 «불투명 검정»이다
- 글자는 띠 안 `y 14~42`(높이 28) · `x 7~505` 에 들어간다 — 가운데 정렬
"""
import os, sys, struct
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import narc, tex0

FONT = r'C:\Windows\Fonts\malgunbd.ttf'
MAXW = 498          # 원본 글자 폭 상한(실측 x 7~505)


def render_line(text, bandw, bandh, font_path=FONT, stroke=3, target_h=28):
    """(intensity, alpha) 두 장의 L 이미지. 흰 글자 + 불투명 검은 외곽선."""
    size = target_h
    while size > 8:
        f = ImageFont.truetype(font_path, size)
        box = f.getbbox(text, stroke_width=stroke)
        if box[2] - box[0] <= MAXW:
            break
        size -= 1
    f = ImageFont.truetype(font_path, size)
    box = f.getbbox(text, stroke_width=stroke)
    tw, th = box[2] - box[0], box[3] - box[1]
    x = (bandw - tw) // 2 - box[0]
    y = (bandh - th) // 2 - box[1]
    inten = Image.new('L', (bandw, bandh), 0)
    alpha = Image.new('L', (bandw, bandh), 0)
    # 알파 : 글자 + 외곽선 전부 불투명
    ImageDraw.Draw(alpha).text((x, y), text, font=f, fill=255,
                               stroke_width=stroke, stroke_fill=255)
    # 명도 : 글자만 흰색(외곽선 자리는 0 = 검정)
    ImageDraw.Draw(inten).text((x, y), text, font=f, fill=255)
    return inten, alpha, size


def patch(arcpath, texname, line, bandh, text, out):
    blob = open(arcpath, 'rb').read()
    hdr, ents = narc.parse(blob)
    e = [x for x in ents if x['name'] == texname][0]
    d, w, h, fmt, nmip, t0 = tex0.find_tex0(e['data'])
    assert fmt == 2, 'IA4 아님'
    im = tex0.ia4_to_image(d[:w * h], w, h)
    y0 = line * 48
    assert y0 + bandh <= h, '띠가 텍스처를 벗어난다'
    inten, alpha, size = render_line(text, w, bandh)
    # ★그 띠만 지우고 그린다
    im.paste(Image.merge('LA', (inten, alpha)), (0, y0))
    raw = tex0.image_to_ia4(im)
    assert len(raw) == w * h
    datoff = struct.unpack_from('>i', e['data'], t0 + 0x10)[0]
    data = bytearray(e['data'])
    data[t0 + datoff: t0 + datoff + w * h] = raw
    nb = bytearray(blob)
    nb[e['off']:e['off'] + e['size']] = data
    assert len(nb) == len(blob), '크기가 바뀌면 안 된다'
    open(out, 'wb').write(bytes(nb))
    return size, sum(1 for a, b in zip(bytes(nb), blob) if a != b)


if __name__ == '__main__':
    arc, name, line, bandh, text = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
    out = sys.argv[6] if len(sys.argv) > 6 else 'work/texture_poc.arc'
    size, diff = patch(arc, name, line, bandh, text, out)
    print('%s 줄%d ← %r  (글자 %dpx · 바뀐 바이트 %d)' % (name, line, text, size, diff))
    print('-> %s' % out)
