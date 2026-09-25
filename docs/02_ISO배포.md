# ISO 통째 배포 (xdelta) — 2026-09-09

Riivolution 판과 별개로, **원본 ISO 를 고쳐 한글판 ISO 를 만드는** 배포 경로.
한글화 내용은 Riivolution 판과 완전히 같다.

## 왜 되는가

세 파일 모두 **원본과 바이트 크기가 같다**. FST 재구축·파일 재배치가 필요 없다.

| 파일 | 크기 | 원본 md5 | 한글 md5 |
|---|---:|---|---|
| `main.dol` (sys) | 3,254,496 | `2ee1523c…` | `9ad4d485…` |
| `texture.arc` | 88,727,360 | `ca234b93…` | `4923b63d…` |
| `MsgFont.brfnt` | 660,364 | `81448407…` | `1b722b25…` |

또 ISO 판은 `main_kr.dol` 을 통째로 넣으므로, Riivolution 이 쓰던
`<memory>` 덮어쓰기 목록이 **아예 필요 없다**(`main.dol` 이 sys 영역이라
`<file>` 로 못 바꾸는 제약이 사라지기 때문).

## ⛔ wit 로 재조립하지 말 것

`wit EXTRACT` → `wit COPY` 는 쓰지 않았다. 이 디스크는 FST 가 안 쓰는 영역이
**81.3%(3.5GB)** 인데, 재조립이 그 패딩을 원본대로 재현한다는 보장이 없다.
암호화 파티션이라 클러스터 하나만 달라도 암호문이 통째로 바뀌어
xdelta 가 수 GB 로 부푼다.

대신 **제자리 패치**를 만들었다 — `tools/wiiiso.py`(파싱·복호) + `tools/isopatch.py`.
Wii 해시 트리는 64클러스터(2MiB) 그룹 단위로 자기완결이라,
바뀐 파일이 든 그룹만 다시 구우면 나머지 디스크는 손댈 필요가 없다.

포맷 상세(파티션 헤더·타이틀 키·H0~H4·fakesign)는 메모리
`reference_wii_iso_inplace_patch` 에 정리해 뒀다.

★★★**한 클러스터를 고치면 그 그룹 64개를 전부 다시 암호화해야 한다.**
H1·H2 표를 그룹이 공유해서 해시 블록이 바뀌고, 그러면 데이터 IV 도 바뀐다.
이것이 xdelta 크기의 하한(그룹당 2MiB)이다.

## 실측

```
main.dol        클러스터   5 개 갱신
texture.arc     클러스터 248 개 갱신
MsgFont.brfnt   클러스터  15 개 갱신
→ 다시 구운 그룹 12 개 = 24 MiB   (전체 4,482 MiB 중)
→ xdelta 24,667,689 B, 생성 32초
```

## 검증 (4종 전부 통과)

1. **파이프라인 자체 검증** — 안 고친 그룹(0·100·2000·2066)을 그대로 다시 구워
   **원본 암호문과 바이트 일치**, H3 항목 일치, h3 전체 SHA1 = TMD 의 H4 일치.
   → AES·H0~H4 계산이 맞다는 증명. 본작업 전에 이걸 먼저 했다.
2. **되읽기** — 패치한 ISO 에서 세 파일을 다시 읽어 빌드본과 md5 일치.
3. **`wit VERIFY`** — 두 파티션 모두 `+OK`,
   `TICKET is well signed. TMD is fake signed. Partition is encrypted.`
4. **왕복** — 원본 + xdelta 로 재생성한 ISO 가 빌드본과 md5 일치(`36b01c89…`).
5. **`패치하기.bat` 실제 실행** — 원본 해시 확인 → 패치 → 결과 해시 확인 완주.

## 기준 원본 (Redump, disc 43190)

```
크기    4,699,979,776
CRC-32  4780998f
MD5     fd9f83599cb9962e3ba8137b19454c1f
SHA-1   cf4225060f76f3d8842a63bcdbe00313bb5cc155
```

사용자 보유본이 이것과 일치함을 확인했다.
`.rvz`/`.wbfs` 로 갖고 있으면 돌핀 [파일 변환]으로 ISO(무압축)로 되돌리면 같은 해시가 나온다.

## 만드는 법

```
python tools/isopatch.py <원본.iso> work/tsumi2_kr.iso
xdelta -e -9 -f -B 536870912 -s <원본.iso> work/tsumi2_kr.iso work/xd/tsumi2_kr.xdelta
python tools/mkisodist.py work/tsumi2_kr.iso work/xd/tsumi2_kr.xdelta patch/tsumi2_kr_iso_v0.9
```

`wit` = `C:/claude/utils/wit/wit-v3.05a-r8638-cygwin64/bin/wit.exe` (검증용).
`pycryptodome` 필요.

## 함정

- `main.dol` 은 **FST 에 없다**. boot.bin `0x420` 의 값 `<<2` 가 오프셋(`0x3E600`).
- 배포 배치는 CP949 라 **`«»` 를 못 쓴다**. `mkisodist.py` 가 `bat.encode('cp949')` 로 미리 잡는다.
- 한글 파일명 배치를 git-bash 에서 `cmd //c` 로 부르면 이름이 깨진다. PowerShell 로 부를 것.

## 남은 것

- ISO 판 **실기(USB 로더) 미검증**, 돌핀 실행도 아직 안 해 봤다.
