# -*- coding: utf-8 -*-
"""`MsgFont.brfnt` — 글리프 칸을 한글로 바꿔 넣는다.

    python tools/brfnt.py info  <brfnt>
    python tools/brfnt.py dump  <brfnt> <시트번호> <out.png>
    python tools/brfnt.py patch <brfnt> <out.brfnt> "基=기" "本=본" ...

## 확정된 구조 (실측)
```
RFNT ver 0104 · 6섹션
FINF @0x10
TGLP @0x30 : cell 26x30 · baseline 21 · maxW 28 · sheetSize 32768
             시트 20장 · fmt=2(IA4) · **ncol 37 · nrow 1** · 1024x32
             데이터 = TGLP+0x8+toff
CWDH @0xA0060 : 글리프 0~732, 항목 3 B = (left, glyphWidth, charWidth)
CMAP ×3       : SJIS 코드 → 글리프 번호 (표 2개 + 스캔 1개)
```
★**글리프 g → 시트 `g//37` · 칸 `g%37` · 픽셀 x=`(g%37) * (26+1)`, y=0**
  ⛔간격은 셀폭 26 이 아니라 **27**(셀폭+1). 시트 데이터 오프셋은 «파일 절대값».
  두 가지를 다 고쳐야 맞는다 — 하나만 고치면 여전히 깨진다.
⛔한글로 바꾼 칸은 **CWDH 도 같이 고쳐야** 폭이 맞는다. 안 고치면 원래 한자 폭으로 전진한다.
"""
import os, sys, struct
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tex0

FONT = r'C:\Windows\Fonts\malgunbd.ttf'


class Brfnt(object):
    def __init__(self, path):
        self.b = bytearray(open(path, 'rb').read())
        b = self.b
        self.nsec = struct.unpack_from('>H', b, 0x0E)[0]
        self.sec = {}
        off = struct.unpack_from('>H', b, 0x0C)[0]
        for _ in range(self.nsec):
            tag = bytes(b[off:off + 4]).decode('latin1')
            sz = struct.unpack_from('>I', b, off + 4)[0]
            self.sec.setdefault(tag, []).append((off, sz))
            off += sz
        t = self.sec['TGLP'][0][0]
        (self.cw, self.chh, self.bl, self.mw, self.shsz, self.ns,
         self.fmt, self.ncol, self.nrow, self.tw, self.th, toff) = \
            struct.unpack_from('>BBBBIHHHHHHI', b, t + 8)
        # ★★★시트 데이터 오프셋은 «파일 절대값»이다 — `TGLP+8+toff` 가 아니다.
        #   ⛔56 B 어긋난 채 읽고 쓰면 글리프가 깨지고, 마지막 시트가 CWDH 를 침범해
        #     게임이 검은 화면으로 죽는다(실기 확인).
        #   검산 : data + 시트수*시트크기 == 다음 섹션(CWDH) 시작. 이게 안 맞으면 오프셋이 틀린 것.
        self.data = toff
        assert self.data + self.ns * self.shsz == t + struct.unpack_from('>I', b, t + 4)[0],             '시트 데이터 끝이 TGLP 끝과 안 맞는다'
        self.cwdh = self.sec['CWDH'][0][0]
        self.c2g = self._cmap()

    def _cmap(self):
        out = {}
        for off, sz in self.sec['CMAP']:
            f, l, ty, pad, nx = struct.unpack_from('>HHHHI', self.b, off + 8)
            if ty == 0:
                for i in range(l - f + 1):
                    out[f + i] = i
            elif ty == 1:
                for i, v in enumerate(struct.unpack_from('>%dh' % (l - f + 1), self.b, off + 0x14)):
                    if v >= 0:
                        out[f + i] = v
            elif ty == 2:
                n = struct.unpack_from('>H', self.b, off + 0x14)[0]
                pr = struct.unpack_from('>%dH' % (n * 2), self.b, off + 0x16)
                for i in range(n):
                    out[pr[i * 2]] = pr[i * 2 + 1]
        return out

    def sheet(self, n):
        d = self.b[self.data + n * self.shsz: self.data + (n + 1) * self.shsz]
        return tex0.ia4_to_image(bytes(d), self.tw, self.th)

    def put_sheet(self, n, im):
        raw = tex0.image_to_ia4(im)
        assert len(raw) == self.shsz
        self.b[self.data + n * self.shsz: self.data + (n + 1) * self.shsz] = raw

    def sjis(self, ch):
        e = ch.encode('cp932')
        return e[0] if len(e) == 1 else struct.unpack('>H', e)[0]

    def set_width(self, g, left, gw, cw):
        struct.pack_into('>bBb', self.b, self.cwdh + 0x10 + g * 3, left, gw, cw)

    def draw(self, g, ch, font_path=FONT, size=24, stroke=1):
        """글리프 칸 g 를 문자 ch 로 다시 그린다."""
        sh, col = g // self.ncol, g % self.ncol
        im = self.sheet(sh)
        # ★★★칸 간격은 «셀폭+1» = 27 이다(NW4R 규약). 셀 자체는 26x30.
        #   ⛔26 으로 잡으면 옆 칸을 물어 글자가 깨진다. 검증 : 'A'(칸25)를 27 간격으로
        #     잘라야 A 가 나온다(26 이면 '>' , 28 이면 'B').  37*27=999 <= 1024 ✓
        x0 = col * (self.cw + 1)
        # ★그 칸만 지운다
        im.paste(Image.new('LA', (self.cw, self.chh), (0, 0)), (x0, 0))
        # ★★★세로 배치는 «베이스라인 계산»이 아니라 «원본 잉크 범위»에 맞춘다.
        #   원본 한자 글리프의 잉크는 y 2~25 (높이 24). 베이스라인(21)으로 계산하면
        #   한글 잉크 높이(23)가 커서 y=-7 이 되어 위가 7px 잘린다(실기 확인).
        #   → 잉크가 INK_TOP~INK_BOT 안에 «딱» 들어가도록 크기를 줄이고 가운데 정렬한다.
        INK_TOP, INK_BOT = 2, 25
        avail_h = INK_BOT - INK_TOP + 1
        while size > 8:
            f = ImageFont.truetype(font_path, size)
            bb = f.getbbox(ch, stroke_width=stroke)
            if (bb[3] - bb[1]) <= avail_h and (bb[2] - bb[0]) <= self.cw:
                break
            size -= 1
        f = ImageFont.truetype(font_path, size)
        bb = f.getbbox(ch, stroke_width=stroke)
        w, h = bb[2] - bb[0], bb[3] - bb[1]
        px = (self.cw - w) // 2 - bb[0]
        py = INK_TOP + (avail_h - h) // 2 - bb[1]
        # ★★★원본도 «흰 글자 + 검은 외곽선»이다(불투명한데 어두운 픽셀 93개 실측).
        #   IA4 는 명도·알파가 따로이므로 두 장을 나눠 그린다 :
        #     알파 = 글자 + 외곽선 (둘 다 불투명)
        #     명도 = 글자만 흰색 — 외곽선 자리는 0(검정) 으로 남는다
        alpha = Image.new('L', (self.cw, self.chh), 0)
        inten = Image.new('L', (self.cw, self.chh), 0)
        ImageDraw.Draw(alpha).text((px, py), ch, font=f, fill=255,
                                   stroke_width=stroke, stroke_fill=255)
        ImageDraw.Draw(inten).text((px, py), ch, font=f, fill=255)
        im.paste(Image.merge('LA', (inten, alpha)), (x0, 0))
        self.put_sheet(sh, im)
        self.set_width(g, 0, self.cw, self.cw)
        return sh, col


def main():
    cmd = sys.argv[1]
    fn = Brfnt(sys.argv[2])
    if cmd == 'info':
        print('셀 %dx%d 베이스라인 %d · 시트 %d장 %dx%d fmt=%d · 칸 %dx%d · 데이터 0x%X'
              % (fn.cw, fn.chh, fn.bl, fn.ns, fn.tw, fn.th, fn.fmt, fn.ncol, fn.nrow, fn.data))
        print('CMAP %d자 · CWDH @0x%X' % (len(fn.c2g), fn.cwdh))
    elif cmd == 'dump':
        n = int(sys.argv[3])
        im = fn.sheet(n)
        bg = Image.new('RGB', im.size, (0, 0, 0))
        bg.paste(im.convert('RGB'), (0, 0), im.split()[1])
        bg.save(sys.argv[4])
        print('시트%d -> %s' % (n, sys.argv[4]))
    elif cmd == 'patch':
        out = sys.argv[3]
        for spec in sys.argv[4:]:
            src, dst = spec.split('=')
            g = fn.c2g.get(fn.sjis(src))
            if g is None:
                print('  ⛔%s 는 폰트에 없다' % src); continue
            sh, col = fn.draw(g, dst)
            print('  %s(글리프 %3d · 시트 %2d 칸 %2d) ← %s' % (src, g, sh, col, dst))
        open(out, 'wb').write(bytes(fn.b))
        print('-> %s' % out)


if __name__ == '__main__':
    main()
