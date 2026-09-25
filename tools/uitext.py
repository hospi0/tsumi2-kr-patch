# -*- coding: utf-8 -*-
"""`main.dol` 의 UI·시스템 문자열 풀을 추출한다.

    python tools/uitext.py <main.dol> [출력.tsv]

## 확정된 구조 (메모리 실측으로 대조)
- 문자열 풀 : 파일 오프셋 **`0x2C0000 ~ 0x320000`** (메모리 `0x802C0000~` 에 대응)
- 인코딩    : **Shift-JIS**, `\\0` 종단
- 제어코드  : **`0x01` + RGB 3바이트** (글자 색). `0x0A` = 줄바꿈. `%s`/`%d` = 런타임 치환
  ⛔`0x01` 뒤 3바이트는 «글자가 아니다» — 토큰 `{01:RRGGBB}` 로 보존한다.

## 산출물
`번호 · 오프셋 · 바이트수 · 원문(토큰화) · 화면문자수 · 번역`
⛔원문 열은 절대 수정하지 않는다. 번역은 마지막 열에만.
"""
import os, sys, io, re

LO, HI = 0x2C0000, 0x320000
LEAD = lambda c: (0x81 <= c <= 0x9F) or (0xE0 <= c <= 0xFC)
TRAIL = lambda c: (0x40 <= c <= 0x7E) or (0x80 <= c <= 0xFC)


def tokenize(b):
    """바이트열 -> (표시문자열, 화면문자수). 제어코드는 {..} 토큰으로."""
    out, cells, i = [], 0, 0
    while i < len(b):
        c = b[i]
        if c == 0x01 and i + 3 < len(b):
            out.append('{01:%02X%02X%02X}' % (b[i + 1], b[i + 2], b[i + 3])); i += 4; continue
        if c == 0x0A:
            out.append('|'); i += 1; continue
        if c < 0x20:
            out.append('{%02X}' % c); i += 1; continue
        if LEAD(c) and i + 1 < len(b) and TRAIL(b[i + 1]):
            try:
                out.append(b[i:i + 2].decode('cp932'))
            except Exception:
                out.append('{%02X%02X}' % (c, b[i + 1]))
            cells += 2; i += 2; continue
        out.append(chr(c)); cells += 1; i += 1
    return ''.join(out), cells


def strings(d):
    """풀 안의 `\\0` 종단 문자열 — 일본어가 든 것만."""
    out, i = [], LO
    while i < min(HI, len(d)):
        j = d.find(b'\0', i)
        if j < 0:
            break
        seg = d[i:j]
        if len(seg) >= 2:
            txt, cells = tokenize(seg)
            # ★★★«가나 2자 이상» 이라야 진짜 일본어 문장이다.
            #   ⛔한자·전각기호만으로 거르면 코드·데이터가 희귀 한자로 풀려 수천 건 오탐(실측 6,000건).
            plain = re.sub(r'\{[^}]*\}|\|', '', txt)
            kana = sum(1 for ch in plain if '぀' <= ch <= 'ヿ')
            if kana >= 2:
                out.append((i, len(seg), txt, cells))
        i = j + 1
        while i < len(d) and d[i] == 0:
            i += 1
    return out


def main():
    p = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join('my files', '추출', '01_UI.tsv')
    d = open(p, 'rb').read()
    rows = strings(d)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with io.open(out, 'w', encoding='utf-8', newline='') as f:
        f.write('번호\t오프셋\t바이트\t화면문자\t원문\t번역\n')
        for k, (off, n, txt, cells) in enumerate(rows, 1):
            f.write('%d\t0x%06X\t%d\t%d\t%s\t\n' % (k, off, n, cells, txt))
    chars = set()
    for _, _, t, _ in rows:
        chars |= {c for c in re.sub(r'\{[^}]*\}|\|', '', t)}
    print('문자열 %d개 · 총 %d B · 서로 다른 문자 %d종' %
          (len(rows), sum(r[1] for r in rows), len(chars)))
    print('-> %s' % out)


if __name__ == '__main__':
    main()
