# -*- coding: utf-8 -*-
"""돌핀 프로세스에 붙어 Wii/GC RAM 을 직접 읽고 쓴다.

★Wii 는 MEM1(0x80000000, 24MB) + MEM2(0x90000000, 64MB) 두 덩이다.
  디스크 헤더 매직도 다르다 — GC 는 0x1C 의 0xC2339F3D, **Wii 는 0x18 의 0x5D1C9EA3**.

돌핀은 스크립트 API가 없다. Dolphin Memory Engine 이 쓰는 것과 같은 방법으로
«돌핀 프로세스 안에 매핑된 24MB MEM1 뷰»를 찾아 ReadProcessMemory 로 읽는다.

  from dolmem import Dolphin
  d = Dolphin()                 # 자동 부착
  d.u32(0x80000000)             # GC 주소로 읽기
  d.write(0x80345678, b'...')

★찾는 법: VirtualQueryEx 로 «크기 0x2000000 · MEM_MAPPED» 구간을 훑고,
  GC RAM 규약으로 **검증**한다 — 오프셋 0x00 에 게임ID(6자), 0x1C 에 매직 0xC2339F3D.
  크기만 보고 고르면 그래픽 버퍼 등을 잡는다.
"""
import ctypes as C
from ctypes import wintypes as W

k32 = C.WinDLL('kernel32', use_last_error=True)
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
MEM_MAPPED, MEM_COMMIT = 0x40000, 0x1000
MEM1_SIZE = 0x2000000
MAGIC = 0xC2339F3D        # GC
MAGIC_WII = 0x5D1C9EA3    # Wii
MEM2_SIZE = 0x4000000


class MEMORY_BASIC_INFORMATION64(C.Structure):
    _fields_ = [('BaseAddress', C.c_ulonglong), ('AllocationBase', C.c_ulonglong),
                ('AllocationProtect', W.DWORD), ('__alignment1', W.DWORD),
                ('RegionSize', C.c_ulonglong), ('State', W.DWORD),
                ('Protect', W.DWORD), ('Type', W.DWORD), ('__alignment2', W.DWORD)]


k32.OpenProcess.restype = W.HANDLE
k32.VirtualQueryEx.restype = C.c_size_t


def _pids(name='Dolphin.exe'):
    import subprocess
    # ⛔`text=True` 는 한국어 윈도우에서 CP949 출력을 UTF-8 로 읽어 죽는다.
    out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq ' + name, '/FO', 'CSV', '/NH'],
                         capture_output=True).stdout.decode('cp949', 'replace')
    return [int(l.split('","')[1]) for l in out.splitlines() if l.startswith('"')]


class Dolphin(object):
    def __init__(self, pid=None):
        pids = [pid] if pid else _pids()
        if not pids:
            raise SystemExit('★돌핀이 실행돼 있지 않다(Dolphin.exe)')
        for p in pids:
            h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ |
                                PROCESS_VM_WRITE | PROCESS_VM_OPERATION, False, p)
            if not h:
                continue
            base = self._find_mem1(h)
            if base:
                self.h, self.pid, self.base = h, p, base
                return
            k32.CloseHandle(h)
        raise SystemExit('★MEM1 을 못 찾았다 — 게임이 «실행 중»이어야 한다(정지 상태 아님)')

    def _find_mem1(self, h):
        mbi = MEMORY_BASIC_INFORMATION64()
        a = 0
        while a < 0x7FFFFFFFFFFF:
            if not k32.VirtualQueryEx(h, C.c_void_p(a), C.byref(mbi), C.sizeof(mbi)):
                break
            if (mbi.RegionSize == MEM1_SIZE and mbi.State == MEM_COMMIT
                    and mbi.Type == MEM_MAPPED):
                buf = (C.c_char * 0x20)()
                n = C.c_size_t()
                if k32.ReadProcessMemory(h, C.c_void_p(mbi.BaseAddress), buf, 0x20, C.byref(n)):
                    b = bytes(buf)
                    ok = (int.from_bytes(b[0x1C:0x20], 'big') == MAGIC or
                          int.from_bytes(b[0x18:0x1C], 'big') == MAGIC_WII)
                    if ok and b[:4].isalnum():
                        return mbi.BaseAddress
            a = mbi.BaseAddress + mbi.RegionSize
        return None

    # ── 기본 읽기/쓰기 (인수는 «GC 주소» 0x80xxxxxx)
    def read(self, gcaddr, size):
        off = gcaddr & 0x01FFFFFF
        buf = (C.c_char * size)()
        n = C.c_size_t()
        if not k32.ReadProcessMemory(self.h, C.c_void_p(self.base + off), buf, size, C.byref(n)):
            raise OSError('읽기 실패 0x%08X' % gcaddr)
        return bytes(buf)

    def write(self, gcaddr, data):
        off = gcaddr & 0x01FFFFFF
        n = C.c_size_t()
        if not k32.WriteProcessMemory(self.h, C.c_void_p(self.base + off),
                                      data, len(data), C.byref(n)):
            raise OSError('쓰기 실패 0x%08X' % gcaddr)

    def dump(self):
        """MEM1 24MB 통째로."""
        return self.read(0x80000000, MEM1_SIZE)

    def find_mem2(self):
        """MEM2(0x90000000, 64MB) 매핑을 따로 찾는다 — MEM1 과 다른 구간이다."""
        mbi = MEMORY_BASIC_INFORMATION64()
        a, out = 0, []
        while a < 0x7FFFFFFFFFFF:
            if not k32.VirtualQueryEx(self.h, C.c_void_p(a), C.byref(mbi), C.sizeof(mbi)):
                break
            if (mbi.RegionSize == MEM2_SIZE and mbi.State == MEM_COMMIT
                    and mbi.Type == MEM_MAPPED):
                out.append(mbi.BaseAddress)
            a = mbi.BaseAddress + mbi.RegionSize
        return out

    def raw(self, base, off, size):
        buf = (C.c_char * size)()
        n = C.c_size_t()
        if not k32.ReadProcessMemory(self.h, C.c_void_p(base + off), buf, size, C.byref(n)):
            raise OSError('읽기 실패')
        return bytes(buf)

    def u8(self, a):  return self.read(a, 1)[0]
    def u16(self, a): return int.from_bytes(self.read(a, 2), 'big')
    def u32(self, a): return int.from_bytes(self.read(a, 4), 'big')
    def s16(self, a):
        v = self.u16(a); return v - 0x10000 if v >= 0x8000 else v
    def s32(self, a):
        v = self.u32(a); return v - 0x100000000 if v >= 0x80000000 else v
    def f32(self, a):
        import struct; return struct.unpack('>f', self.read(a, 4))[0]

    def gameid(self):
        return self.read(0x80000000, 6).decode('latin1')


if __name__ == '__main__':
    d = Dolphin()
    print('부착 성공 — PID %d · MEM1 호스트주소 0x%X' % (d.pid, d.base))
    print('게임ID %s · 디스크명 %s'
          % (d.gameid(), d.read(0x80000020, 0x20).split(b'\0')[0].decode('latin1')))
