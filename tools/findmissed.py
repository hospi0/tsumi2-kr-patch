# -*- coding: utf-8 -*-
"""번역표가 «놓친» 일본어 문자열을 찾는다.

    python tools/findmissed.py <main.dol> <번역표.tsv>

## 왜 따로 필요한가
`uitext.py` 의 추출(가나 2자 이상 · NUL 로 잘라 읽기)은 두 부류를 놓친다.

1. **가나가 1자뿐인 짧은 라벨** — `上` `下` `振動` `戻る` `完了` `進む` …
2. ★★★**고정폭 표 안의 항목** — 앞이 NUL 이 아니라 «float 데이터»라 순차 스캔이
   덩어리째 삼켜 버린다. 실제로 `0x318C70 イサ`(플레이어 이름)가 그렇게 빠져서
   파일 선택 화면 제목이 `【STAGE 0 イサ】` 로 남았다.

## 검출
- (A) **순수 문자열** : 제어바이트가 하나도 없고, cp932 로 깨끗이 풀리고,
      «글자다운 문자»(반각/가나/한자/전각)로만 되어 있고, 가나가 1자 이상.
- (B) **슬롯 정렬 스윕** : 4/8바이트 격자마다 그 자리에서 문자열을 읽어 (A) 를 적용한다.
      고정폭 표는 이걸로만 잡힌다.
⛔「풀 전체를 NUL 로 잘라 전부 문자열로 친다」는 하지 말 것 — 무작위 바이트가 희귀
  한자로 풀려 4천 건이 나온다(실측). 제어바이트 0 조건이 그 잡음을 걷어낸다.
"""
import os, sys, io

LO, HI = 0x2C0000, 0x320000


def is_kana(o):
    return 0x3040 <= o <= 0x30FF


def texty(c):
    o = ord(c)
    return (0x20 <= o < 0x7F or is_kana(o) or 0x4E00 <= o <= 0x9FFF
            or 0xFF01 <= o <= 0xFF5E
            or c in u'　、。・「」『』'
                    u'（）〜…※【】')


def read_at(d, i, hi):
    j = d.find(b'\x00', i)
    if j < 0 or j >= hi:
        return None
    seg = d[i:j]
    if not (2 <= len(seg) <= 60) or any(c < 0x20 for c in seg):
        return None
    try:
        t = seg.decode('cp932')
    except Exception:
        return None
    if not t or not all(texty(c) for c in t):
        return None
    if not any(is_kana(ord(c)) for c in t):
        return None
    return len(seg), t


def main():
    dolp, tsv = sys.argv[1], sys.argv[2]
    d = open(dolp, 'rb').read()
    hi = min(HI, len(d))
    known, kspan = set(), []
    for l in io.open(tsv, encoding='utf-8'):
        f = l.rstrip('\n').split('\t')
        if len(f) > 2 and f[1].startswith('0x'):
            o = int(f[1], 16)
            known.add(o)
            kspan.append((o, o + int(f[2])))
    found = {}
    i = LO                                   # (A) 순차
    while i < hi:
        r = read_at(d, i, hi)
        if r:
            found[i] = r
        j = d.find(b'\x00', i)
        if j < 0:
            break
        i = j + 1
        while i < hi and d[i] == 0:
            i += 1
    for step in (4, 8):                      # (B) 슬롯 정렬
        for o in range(LO, hi, step):
            r = read_at(d, o, hi)
            if r:
                found.setdefault(o, r)
    # ★슬롯 스윕은 «문자열 꼬리»를 잔뜩 짚는다 — 더 긴 문자열 안에 들어가는 시작점은 버린다.
    span = sorted([(o, o + found[o][0]) for o in found] + kspan)
    inside = set()
    end = -1
    for a, b in span:
        if a > 0 and a < end:
            inside.add(a)
        end = max(end, b)
    out = sorted(k for k in found if k not in known and k not in inside)
    for o in out:
        n, t = found[o]
        print('0x%06X\t%d\t%s' % (o, n, t))
    print('---표에 없는 일본어 문자열 %d개 (검출 %d · 꼬리중복 %d)'
          % (len(out), len(found), len(inside)))


if __name__ == '__main__':
    main()
