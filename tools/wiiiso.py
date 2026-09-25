# -*- coding: utf-8 -*-
"""Wii 디스크 이미지(ISO)를 «제자리»에서 고치기 위한 최소 도구.

왜 제자리인가:
  wit EXTRACT → COPY 로 다시 조립하면 FST 가 안 쓰는 81% 영역(패딩)을
  원본과 똑같이 재현한다는 보장이 없다. 한 클러스터라도 달라지면
  암호문이 통째로 달라져서 xdelta 가 수 GB 로 부푼다.
  그래서 «바꾼 파일이 든 클러스터 + 그 위 해시 트리»만 건드린다.

구조 (한 파티션):
  파티션 선두 0x2A4 = 티켓, 그 뒤 TMD/cert/H3/데이터 오프셋(4바이트, <<2)
  데이터 영역은 0x8000 클러스터의 연속
    0x0000..0x0400 해시 블록 (AES-CBC, IV=0)
    0x0400..0x8000 실데이터 0x7C00 (AES-CBC, IV=암호화된 해시블록[0x3D0:0x3E0])
  해시 블록 안:
    0x000..0x26C  H0 : 데이터 0x400 조각 31개의 SHA1
    0x280..0x320  H1 : 8클러스터(부분그룹)의 H0표 SHA1 8개 — 8개가 같은 표를 공유
    0x340..0x3E0  H2 : 8부분그룹(64클러스터)의 H1표 SHA1 8개 — 64개가 공유
  H3 : 64클러스터 그룹마다 H2표의 SHA1 (h3 영역, 0x18000 바이트)
  H4 : h3 영역 전체의 SHA1 → TMD 콘텐츠 레코드
"""
import struct, hashlib
from Crypto.Cipher import AES

COMMON_KEY = bytes.fromhex('ebe42a225e8593e448d9c5457381aaf7')
CLUSTER = 0x8000
DATA = 0x7C00


def be32(b, o):
    return struct.unpack_from('>I', b, o)[0]


class Partition(object):
    def __init__(self, f, off):
        self.f = f
        self.off = off                      # 이미지 안 파티션 시작(바이트)
        f.seek(off)
        hdr = f.read(0x2C0)
        self.ticket = hdr[:0x2A4]
        self.tmd_size = be32(hdr, 0x2A4)
        self.tmd_off = be32(hdr, 0x2A8) << 2
        self.cert_size = be32(hdr, 0x2AC)
        self.cert_off = be32(hdr, 0x2B0) << 2
        self.h3_off = be32(hdr, 0x2B4) << 2
        self.data_off = be32(hdr, 0x2B8) << 2
        self.data_size = be32(hdr, 0x2BC) << 2
        self.nclust = self.data_size // CLUSTER
        # 타이틀 키
        enc = self.ticket[0x1BF:0x1CF]
        iv = self.ticket[0x1DC:0x1E4] + b'\0' * 8
        self.key = AES.new(COMMON_KEY, AES.MODE_CBC, iv).decrypt(enc)

    # ---- 클러스터 단위 ----
    def raw_cluster(self, i):
        self.f.seek(self.off + self.data_off + i * CLUSTER)
        return self.f.read(CLUSTER)

    def dec_cluster(self, i):
        """(해시블록 0x400, 데이터 0x7C00) 평문으로 돌려준다."""
        raw = self.raw_cluster(i)
        h = AES.new(self.key, AES.MODE_CBC, b'\0' * 16).decrypt(raw[:0x400])
        d = AES.new(self.key, AES.MODE_CBC, raw[0x3D0:0x3E0]).decrypt(raw[0x400:])
        return h, d

    def read(self, off, size):
        """복호화된 파티션 스트림에서 읽는다(파일 오프셋은 이 좌표계다)."""
        out = bytearray()
        while size > 0:
            i, o = divmod(off, DATA)
            n = min(size, DATA - o)
            out += self.dec_cluster(i)[1][o:o + n]
            off += n; size -= n
        return bytes(out)

    # ---- FST ----
    def load_fst(self):
        boot = self.read(0, 0x440)
        fst_off = be32(boot, 0x424) << 2
        fst_size = be32(boot, 0x428) << 2
        fst = self.read(fst_off, fst_size)
        n = be32(fst, 8)
        names = fst[n * 12:]
        self.files = {}

        def name(i):
            no = be32(fst, i * 12) & 0xFFFFFF
            e = names.index(b'\0', no)
            return names[no:e].decode('shift_jis', 'replace')

        stack = [(n, '')]
        i = 1
        while i < n:
            while stack and i >= stack[-1][0]:
                stack.pop()
            typ = fst[i * 12]
            path = (stack[-1][1] if stack else '') + '/' + name(i)
            if typ:
                stack.append((be32(fst, i * 12 + 8), path))
            else:
                self.files[path] = (be32(fst, i * 12 + 4) << 2,
                                    be32(fst, i * 12 + 8))
            i += 1
        return self.files
