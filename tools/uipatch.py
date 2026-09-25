# -*- coding: utf-8 -*-
"""UI 번역을 «폰트 글리프 + main.dol 문자열» 로 함께 되넣는다.

    python tools/uipatch.py <trans.tsv> <main.dol> <MsgFont.brfnt> <out.dol> <out.brfnt>

## 설계
게임은 Shift-JIS 코드로 글자를 그린다. 한글 코드는 없으므로 **원문에 안 쓰이는
폰트 글자(«기증자» 코드)의 칸을 한글로 덮어쓰고**, 번역문에는 그 코드를 써 넣는다.

- 한글 1자 = 기증자 SJIS 2바이트. 원문 가나·한자도 2바이트라 예산은 대체로 맞는다.
- 문자열은 NUL 종단이고 **자리에 그대로** 되넣는다 — 원본 길이를 넘으면 안 된다.
- 기증자 선정은 `protected()` 참조. ⛔«번역표에 없는 글자 = 자유»가 아니다.

## 산출물 검증
- 번역문에 배정 못 한 글자가 있으면 **실패시킨다**(조용히 건너뛰지 않는다).
- 되넣기 후 «원본 길이 초과» 0건을 확인한다.
- 배정표를 `<out.brfnt 이름>_charmap.txt` 로 같이 남긴다.
"""
import os, sys, io, re, struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from brfnt import Brfnt
import uitext
import dol


def sjis_code(ch):
    e = ch.encode('cp932')
    return e[0] if len(e) == 1 else struct.unpack('>H', e)[0]


def code_bytes(c):
    return bytes([c]) if c < 0x100 else struct.pack('>H', c)


def plain_of(txt):
    return re.sub(r'\{[^}]*\}|\|', '', txt)


def ref_starts(d, lo=0x2C0000, hi=0x320000):
    """★«게임이 실제로 쓰는» 문자열 시작 오프셋.

    ⛔풀 안의 NUL 종단 덩어리를 전부 문자열로 치면 2만 개가 나오고(무작위 바이트가
      희귀 한자로 풀린다) 폰트 733칸이 «전부 사용중»으로 잡혀 기증자가 0이 된다.
    판정은 «참조»로 한다 :
      ① 데이터의 32비트 포인터가 가리키는 곳
      ② PowerPC `lis` + `addi`/`ori` 로 만들어지는 즉시 주소
    ★★★주소 → 오프셋 되돌리기는 **DOL 섹션마다 델타가 다르다**(`tools/dol.py`).
      ⛔단일 `0x80003F20` 으로 하면 섹션 13·14(이름·라벨 고정폭 표)가 통째로 안 잡힌다.
    그리고 **바로 앞 바이트가 NUL** 인 것만 남긴다 — ②는 문자열 «중간»을 잔뜩 짚는다
    (이 걸러내기 하나로 «표에 없는 진짜 문자열»이 420개에서 3개로 줄었다).
    """
    hi = min(hi, len(d))
    secs = dol.sections(d)

    def back(v):
        o = dol.to_file(secs, v)
        return o if (o is not None and lo <= o < hi) else None

    out = set()
    for i in range(0, len(d) - 4, 4):
        o = back(struct.unpack_from('>I', d, i)[0])
        if o is not None:
            out.add(o)
    up = {}
    for i in range(0, len(d) - 4, 4):
        w = struct.unpack_from('>I', d, i)[0]
        op = w >> 26
        if op == 15:                       # lis rD, imm
            if ((w >> 16) & 31) == 0:
                up[(w >> 21) & 31] = (w & 0xFFFF) << 16
        elif op == 14:                     # addi rD, rA, simm
            rA, imm = (w >> 16) & 31, w & 0xFFFF
            if rA in up:
                o = back(up[rA] + (imm - 0x10000 if imm >= 0x8000 else imm))
                if o is not None:
                    out.add(o)
        elif op == 24:                     # ori rA, rS, uimm
            rS, imm = (w >> 21) & 31, w & 0xFFFF
            if rS in up:
                o = back(up[rS] | imm)
                if o is not None:
                    out.add(o)
    return {o for o in out if o > 0 and d[o - 1] == 0}


def is_kana(c):
    return u'぀' <= c <= u'ヿ'


def is_wide(c):
    return (u'！' <= c <= u'～'
            or c in u'　、。・「」『』'
                    u'（）〜ー…‥※°℃')


def protected(d, rows, fontchars):
    """★한글로 덮으면 «안 되는» 폰트 칸.

    ⛔번역표에 없는 글자라고 자유가 아니다. 지켜야 할 것 :
      ① **가나 전부** — `0x2F53AA` 부터 «이름입력 문자표»(ぁ~ん / ァ~ヶ)가 통째로
         들어 있다. 덮으면 이름 입력 화면이 깨진다.
      ② **전각 영숫자·기호 전부** — 이름·스코어·스테이지 표기에 쓰인다.
      ③ 아직 «원문 그대로» 남는 문자열이 쓰는 글자.
      ④ 내 번역문이 쓰는 비한글 글자.
    ⇒ 기증자로 쓸 수 있는 건 사실상 **참조되지 않는 한자 칸**뿐이다.
    """
    prot = set(c for c in fontchars if is_kana(c) or is_wide(c))
    troff = set(int(r[1], 16) for r in rows if len(r) > 5 and r[5].strip())
    for r in rows:
        if not (len(r) > 5 and r[5].strip()):
            prot |= set(plain_of(r[4]))                      # (3)
        else:
            prot |= set(c for c in plain_of(r[5])            # (4)
                        if not (u'가' <= c <= u'힣') and ord(c) >= 0x80)
    for s in sorted(ref_starts(d)):                          # (3)
        if s in troff:
            continue
        j = d.find(b'\x00', s)
        if j < 0 or j - s > 400:
            continue
        txt, _ = uitext.tokenize(d[s:j])
        pl = plain_of(txt)
        if pl and all(ord(c) >= 0x20 for c in pl) and any(is_kana(c) for c in pl):
            prot |= set(pl)
    return prot & fontchars


def detok(txt, hang2code):
    """번역문(토큰 포함) -> 바이트열. 한글은 기증자 코드로."""
    out = bytearray()
    i = 0
    while i < len(txt):
        if txt[i] == '{':
            j = txt.index('}', i)
            tok = txt[i + 1:j]
            if tok.startswith('01:'):
                out += bytes([0x01]) + bytes.fromhex(tok[3:])
            else:
                out += bytes.fromhex(tok)
            i = j + 1
            continue
        if txt[i] == '|':
            out.append(0x0A)
            i += 1
            continue
        ch = txt[i]
        if u'가' <= ch <= u'힣':
            if ch not in hang2code:
                raise KeyError(ch)
            out += code_bytes(hang2code[ch])
        else:
            out += ch.encode('cp932')
        i += 1
    return bytes(out)


def main():
    tsv, dolp, fntp, outdol, outfnt = sys.argv[1:6]
    allrows = [l.rstrip('\n').split('\t') for l in io.open(tsv, encoding='utf-8')][1:]
    rows = [r for r in allrows if len(r) > 5 and r[5].strip()]
    need = sorted(set(c for r in rows for c in r[5] if u'가' <= c <= u'힣'))
    print('번역 %d행 · 필요한 한글 음절 %d종' % (len(rows), len(need)))

    fn = Brfnt(fntp)
    fontchars = set()
    for code in fn.c2g:
        try:
            fontchars.add(code_bytes(code).decode('cp932'))
        except Exception:
            pass
    dolb = open(dolp, 'rb').read()
    prot = protected(dolb, allrows, fontchars)
    donors = []
    for code, g in sorted(fn.c2g.items()):
        try:
            ch = code_bytes(code).decode('cp932')
        except Exception:
            continue
        if ch in prot or ord(ch) < 0x80:
            continue
        donors.append((code, g, ch))
    print('기증자 후보 %d칸 (폰트 %d - 보호 %d - 반각 %d)'
          % (len(donors), len(fn.c2g), len(prot),
             sum(1 for c in fn.c2g if c < 0x100)))
    if len(need) > len(donors):
        raise SystemExit('★칸 부족 : 한글 %d 종 > 기증자 %d 칸' % (len(need), len(donors)))

    hang2code = {}
    for ch, (code, g, src) in zip(need, donors):
        fn.draw(g, ch)
        hang2code[ch] = code
    open(outfnt, 'wb').write(bytes(fn.b))
    print('폰트 : %d칸 교체 -> %s' % (len(need), outfnt))
    io.open(os.path.splitext(outfnt)[0] + '_charmap.txt', 'w', encoding='utf-8').write(
        '\n'.join('%04X\t%s' % (hang2code[c], c) for c in need) + '\n')

    d = bytearray(dolb)
    over, done = [], 0
    for r in rows:
        off, orig_len = int(r[1], 16), int(r[2])
        try:
            b = detok(r[5], hang2code)
        except KeyError as e:
            raise SystemExit('★배정 못 한 글자 %r (행 %s)' % (e.args[0], r[0]))
        if len(b) > orig_len:
            over.append((r[0], orig_len, len(b), r[5][:40]))
            continue
        d[off:off + orig_len] = b + b'\x00' * (orig_len - len(b))
        done += 1
    if over:
        print('★예산 초과 %d행:' % len(over))
        for k, a, bb, t in over:
            print('   행%-4s %d -> %d B  %s' % (k, a, bb, t))
        raise SystemExit('되넣기 중단')
    open(outdol, 'wb').write(bytes(d))
    print('main.dol : %d행 되넣기 -> %s' % (done, outdol))


if __name__ == '__main__':
    main()
