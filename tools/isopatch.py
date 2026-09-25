# -*- coding: utf-8 -*-
"""원본 ISO 를 복사한 뒤 «건드린 클러스터만» 고쳐 한글판 ISO 를 만든다.

    python tools/isopatch.py <원본.iso> <출력.iso>

⛔wit EXTRACT→COPY 로 재조립하지 말 것. FST 가 안 쓰는 81% 패딩을 원본대로
  재현한다는 보장이 없고, 한 클러스터만 달라도 암호문이 통째로 바뀌어
  xdelta 가 수 GB 가 된다. 여기서는 «파일이 든 64클러스터 그룹»만 다시 굽는다.

해시 트리는 64클러스터 그룹 단위로 «자기완결»이다(H0→H1→H2→H3 항목 하나).
그래서 그룹 하나를 통째로 다시 계산하면 나머지 디스크는 손댈 필요가 없다.
"""
import os, sys, shutil, struct, hashlib
from Crypto.Cipher import AES

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wiiiso
from wiiiso import CLUSTER, DATA

GROUP = 64          # H3 항목 하나가 덮는 클러스터 수
SUB = 8             # H1 항목 하나가 덮는 클러스터 수


def rebuild_group(part, f, g, patches):
    """그룹 g(클러스터 64개)를 평문에서 다시 굽고 H2표의 SHA1(=H3 항목)을 준다."""
    base = g * GROUP
    n = min(GROUP, part.nclust - base)
    data = []
    for i in range(n):
        data.append(bytearray(part.dec_cluster(base + i)[1]))
    # 패치 적용
    for off, blob in patches:
        i, o = divmod(off, DATA)
        i -= base
        data[i][o:o + len(blob)] = blob
    # H0
    h0 = []
    for d in data:
        t = bytearray(0x400)
        for k in range(31):
            t[k * 20:(k + 1) * 20] = hashlib.sha1(bytes(d[k * 0x400:(k + 1) * 0x400])).digest()
        h0.append(t)
    # H1 : 부분그룹(8개)마다 그 8개의 H0표 SHA1
    for s in range((n + SUB - 1) // SUB):
        tab = bytearray(160)
        for k in range(SUB):
            j = s * SUB + k
            if j < n:
                tab[k * 20:(k + 1) * 20] = hashlib.sha1(bytes(h0[j][0:0x26C])).digest()
        for k in range(SUB):
            j = s * SUB + k
            if j < n:
                h0[j][0x280:0x320] = tab
    # H2 : 그룹 안 부분그룹 8개의 H1표 SHA1
    h2 = bytearray(160)
    for s in range(SUB):
        j = s * SUB
        if j < n:
            h2[s * 20:(s + 1) * 20] = hashlib.sha1(bytes(h0[j][0x280:0x320])).digest()
    for j in range(n):
        h0[j][0x340:0x3E0] = h2
    # 암호화해서 되쓰기
    for i in range(n):
        eh = AES.new(part.key, AES.MODE_CBC, b'\0' * 16).encrypt(bytes(h0[i]))
        ed = AES.new(part.key, AES.MODE_CBC, eh[0x3D0:0x3E0]).encrypt(bytes(data[i]))
        f.seek(part.off + part.data_off + (base + i) * CLUSTER)
        f.write(eh + ed)
    return hashlib.sha1(bytes(h2)).digest()


def fakesign(f, part):
    """TMD 서명을 0 으로 지우고 예비 칸을 돌려 SHA1 이 00 으로 시작하게 만든다."""
    f.seek(part.off + part.tmd_off)
    tmd = bytearray(f.read(part.tmd_size))
    tmd[0x004:0x104] = b'\0' * 0x100
    for v in range(1 << 24):
        struct.pack_into('>I', tmd, 0x1C6, v)
        if hashlib.sha1(bytes(tmd[0x140:])).digest()[0] == 0:
            f.seek(part.off + part.tmd_off)
            f.write(bytes(tmd))
            return v
    raise RuntimeError('fakesign 실패')


def main(src, dst, repl):
    if os.path.abspath(src) != os.path.abspath(dst):
        print('복사 중 …', dst)
        shutil.copyfile(src, dst)
    f = open(dst, 'r+b')
    part = wiiiso.Partition(f, 0xF800000)
    fs = part.load_fst()
    boot = part.read(0, 0x440)
    dol_off = wiiiso.be32(boot, 0x420) << 2

    # (평문 오프셋, 새 내용) 목록
    jobs = []
    for path, newfile in repl:
        blob = open(newfile, 'rb').read()
        if path == '/main.dol':
            off, size = dol_off, 3254496
        else:
            off, size = fs[path]
        if len(blob) != size:
            raise SystemExit('%s 크기가 다르다: %d != %d' % (path, len(blob), size))
        old = part.read(off, size)
        if old == blob:
            print('  %-16s 변경 없음' % path); continue
        jobs.append((off, blob, old, path))

    # 클러스터 단위로 «실제로 달라진 것»만 모은다
    groups = {}
    for off, blob, old, path in jobs:
        n, o = 0, 0
        while o < len(blob):
            ci = (off + o) // DATA
            nxt = min(len(blob), (ci + 1) * DATA - off)
            if old[o:nxt] != blob[o:nxt]:
                groups.setdefault(ci // GROUP, []).append((off + o, blob[o:nxt]))
                n += 1
            o = nxt
        print('  %-16s 클러스터 %d 개 갱신' % (path, n))

    print('다시 구울 그룹 %d 개 (=%d MiB)' % (len(groups), len(groups) * GROUP * CLUSTER // 2**20))
    f.seek(part.off + part.h3_off)
    h3 = bytearray(f.read(0x18000))
    for k, g in enumerate(sorted(groups)):
        h3[g * 20:(g + 1) * 20] = rebuild_group(part, f, g, groups[g])
        if (k + 1) % 20 == 0:
            print('   %d/%d' % (k + 1, len(groups)))
    f.seek(part.off + part.h3_off)
    f.write(bytes(h3))

    # H4 = h3 영역 전체의 SHA1 → TMD 콘텐츠 레코드
    h4 = hashlib.sha1(bytes(h3)).digest()
    f.seek(part.off + part.tmd_off)
    tmd = bytearray(f.read(part.tmd_size))
    tmd[0x1E4 + 0x10:0x1E4 + 0x24] = h4
    f.seek(part.off + part.tmd_off)
    f.write(bytes(tmd))
    v = fakesign(f, part)
    print('H4 %s / fakesign 0x%06X' % (h4.hex(), v))
    f.close()


if __name__ == '__main__':
    W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work')
    main(sys.argv[1], sys.argv[2], [
        ('/main.dol',      os.path.join(W, 'main_kr.dol')),
        ('/texture.arc',   os.path.join(W, 'texture_kr.arc')),
        ('/MsgFont.brfnt', os.path.join(W, 'MsgFont_kr.brfnt')),
    ])
