# -*- coding: utf-8 -*-
"""파일에서 Shift-JIS 문자열을 훑는다.

    python tools/sjisscan.py <파일...> [--min N] [--dump N]

★선행바이트 범위는 **`0x81~0x9F` + `0xE0~0xFC`** 로 잡는다.
  ⛔`0xE0~0xEF` 로 좁히면 `0xF0` 이상으로 시작하는 문자열이 통째로 빠진다
  (다른 프로젝트에서 갤러리 캡션 338개를 그렇게 날렸다).
후속바이트는 `0x40~0x7E` + `0x80~0xFC`.
"""
import sys, os, re

LEAD = lambda c: (0x81 <= c <= 0x9F) or (0xE0 <= c <= 0xFC)
TRAIL = lambda c: (0x40 <= c <= 0x7E) or (0x80 <= c <= 0xFC)
ASCII = lambda c: 0x20 <= c <= 0x7E


def runs(b, minjp=2):
    """(오프셋, 바이트열, 전각글자수) — 전각 글자가 minjp 개 이상인 구간만."""
    out = []
    i = 0
    n = len(b)
    while i < n:
        if LEAD(b[i]) and i + 1 < n and TRAIL(b[i + 1]):
            s = i
            jp = 0
            while i < n:
                if LEAD(b[i]) and i + 1 < n and TRAIL(b[i + 1]):
                    i += 2; jp += 1
                elif ASCII(b[i]):
                    i += 1
                else:
                    break
            if jp >= minjp:
                # ★★★가나 개수로 거른다 — 무작위 바이트도 «희귀 한자»로는 잘 풀린다.
                #   진짜 일본어 문장에는 히라가나·가타카나가 반드시 섞인다.
                try:
                    txt = b[s:i].decode('cp932')
                except Exception:
                    txt = ''
                kana = sum(1 for c in txt if '぀' <= c <= 'ヿ')
                if kana >= 2:
                    out.append((s, b[s:i], jp))
        else:
            i += 1
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    minjp = 3
    if '--min' in sys.argv:
        minjp = int(sys.argv[sys.argv.index('--min') + 1])
    dump = 12
    if '--dump' in sys.argv:
        dump = int(sys.argv[sys.argv.index('--dump') + 1])
    for p in args:
        b = open(p, 'rb').read()
        r = runs(b, minjp)
        tot = sum(x[2] for x in r)
        print('%-34s %9d B  문자열 %4d개 · 전각 %5d자' % (os.path.basename(p), len(b), len(r), tot))
        for off, s, jp in r[:dump]:
            try:
                t = s.decode('cp932')
            except Exception:
                t = s.decode('cp932', 'replace')
            print('    0x%06X %3d자  %s' % (off, jp, t[:64]))


if __name__ == '__main__':
    main()
