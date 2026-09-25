# -*- coding: utf-8 -*-
"""『죄와 벌 ~우주의 후계자~』(Wii · R2VJ01) 의 `.arc` = 자체 «NARC» 컨테이너 파서.

    python tools/narc.py <파일.arc> [-x 출력폴더]

## 포맷 (실측으로 확정 — 표본 5개 전부 일치)

```
+0x00  'NARC'
+0x04  u32  항목 수 n
+0x08  u32  이름표 «크기»            ← 오프셋이 아니다
+0x0C  u32  데이터 시작 오프셋
+0x10  항목 n개 × 16 B
         +0x00 u32  이름 필드 폭 (표본 전부 0x20)
         +0x04 u32  이름 오프셋 (이름표 시작 기준)
         +0x08 u32  데이터 오프셋 (데이터 시작 기준)
         +0x0C u32  크기
이름표  0x10 + n*16 부터, 크기 = +0x08
데이터  +0x0C 부터, 각 항목은 16 B 정렬
```

★검산 : 모든 표본에서 `(데이터시작) − (이름표크기) = 0x10 + n*16` 이 정확히 성립한다.
  즉 이름표는 «항목표 바로 뒤»에 붙는다. ⛔`+0x08` 을 오프셋으로 읽으면 항목표 한가운데를
  가리켜 이름이 깨진다(처음 그렇게 읽고 틀렸다).
⛔엔디언은 **빅엔디언**(Wii/PowerPC).
"""
import os, sys, struct

MAGIC = b'NARC'


def parse(blob):
    """-> (헤더dict, [{'name','off','size','data'}...])"""
    if blob[:4] != MAGIC:
        raise ValueError('NARC 아님: %r' % blob[:4])
    n, namesz, dataoff = struct.unpack_from('>3I', blob, 4)
    ent_off = 0x10
    name_off = ent_off + n * 16
    if name_off + namesz != dataoff:
        raise ValueError('구조 불일치: 이름표 끝 0x%X != 데이터 시작 0x%X'
                         % (name_off + namesz, dataoff))
    out = []
    for i in range(n):
        w, no, do, sz = struct.unpack_from('>4I', blob, ent_off + i * 16)
        s = blob.index(b'\0', name_off + no)
        out.append({'i': i, 'width': w, 'name': blob[name_off + no:s].decode('latin1'),
                    'off': dataoff + do, 'size': sz,
                    'data': blob[dataoff + do: dataoff + do + sz]})
    return {'count': n, 'namesize': namesz, 'dataoff': dataoff}, out


def magic_of(d):
    """내부 블롭의 «형식 지문» — 앞 4바이트가 인쇄 가능하면 그대로."""
    if len(d) < 4:
        return '(빈것)'
    m = d[:4]
    if all(0x20 <= c < 0x7F for c in m):
        return m.decode('latin1')
    return m.hex()


def main():
    p = sys.argv[1]
    blob = open(p, 'rb').read()
    hdr, ents = parse(blob)
    print('%s  %d B · 항목 %d · 이름표 %d B · 데이터 0x%X'
          % (os.path.basename(p), len(blob), hdr['count'], hdr['namesize'], hdr['dataoff']))
    for e in ents:
        print('  [%3d] %-28s 0x%06X %8d B  %s'
              % (e['i'], e['name'], e['off'], e['size'], magic_of(e['data'])))
    if '-x' in sys.argv:
        out = sys.argv[sys.argv.index('-x') + 1]
        os.makedirs(out, exist_ok=True)
        for e in ents:
            fn = e['name'].replace('/', '_') or ('entry%03d' % e['i'])
            open(os.path.join(out, '%03d_%s' % (e['i'], fn)), 'wb').write(e['data'])
        print('-> %s 에 %d개 기록' % (out, len(ents)))


if __name__ == '__main__':
    main()
