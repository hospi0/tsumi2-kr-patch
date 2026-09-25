# -*- coding: utf-8 -*-
"""Riivolution 배포 XML 을 «원본↔빌드 바이트 차분»으로 만든다.

    python tools/mkriiv.py <원본 main.dol> <한글 main.dol> <출력.xml>

## 왜 차분인가
`main.dol` 은 디스크 FST 가 아니라 sys 영역이라 Riivolution `<file>` 로 못 바꾼다.
그래서 UI 문자열은 `<memory>` 로 «그 자리에 덮어쓴다». 손으로 목록을 적으면
번역표가 늘 때마다 어긋나므로, **빌드 결과에서 기계적으로 뽑는다.**

★★★파일 오프셋 → 메모리 주소는 **DOL 섹션마다 델타가 다르다**(`tools/dol.py`).
  ⛔단일 델타 `0x80003F20` 은 문자열 풀(섹션 11·12) 값일 뿐이다. 그걸로 만들면
  섹션 13·14 의 «이름·라벨 고정폭 표»가 BSS 에 써져 화면은 원문 그대로 남는다.
⛔`<memory>` 는 «값 그대로 덮어쓰기»다. 문자열 종단 `\\0` 까지 차분에 포함돼야 한다
  (빌더가 남는 예산을 NUL 로 채우므로 자동으로 포함된다).
"""
import os, sys, io

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dol

XML = u'''<wiidisc version="1">
  <id game="R2VJ01" />
  <options>
    <section name="죄와 벌 우주의 후계자 한글패치">
      <option name="자막 텍스처 (270줄)">
        <choice name="적용함"><patch id="patch_texture" /></choice>
      </option>
      <option name="UI 폰트 + 문구">
        <choice name="적용함"><patch id="patch_font" /><patch id="patch_ui" /></choice>
      </option>
    </section>
  </options>
  <patch id="patch_texture">
    <file external="/R2VJ01/texture.arc" disc="/texture.arc" />
  </patch>
  <patch id="patch_font">
    <file external="/R2VJ01/MsgFont.brfnt" disc="/MsgFont.brfnt" />
  </patch>
  <patch id="patch_ui">
%s
  </patch>
</wiidisc>
'''


def runs(a, b, gap=8):
    """다른 바이트 구간 목록. gap 바이트 이하로 붙은 구간은 하나로 합친다."""
    out, s, last = [], None, None
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            if s is None:
                s = i
            elif i - last > gap:
                out.append((s, last + 1)); s = i
            last = i
    if s is not None:
        out.append((s, last + 1))
    return out


def main():
    orig, kr, out = sys.argv[1:4]
    a = open(orig, 'rb').read()
    b = open(kr, 'rb').read()
    assert len(a) == len(b), 'main.dol 크기가 바뀌었다'
    secs = dol.sections(a)
    rs = runs(a, b)
    lines = []
    for s, e in rs:
        m0, m1 = dol.to_mem(secs, s), dol.to_mem(secs, e - 1)
        assert m0 is not None and m1 - m0 == e - 1 - s,             '0x%06X~0x%06X 이 섹션 경계를 넘거나 섹션 밖이다' % (s, e)
        lines.append('    <memory offset="0x%08X" value="%s" />' % (m0, b[s:e].hex().upper()))
    io.open(out, 'w', encoding='utf-8', newline='\n').write(XML % '\n'.join(lines))
    print('memory 패치 %d개 · 바뀐 바이트 %d -> %s'
          % (len(rs), sum(e - s for s, e in rs), out))


if __name__ == '__main__':
    main()
