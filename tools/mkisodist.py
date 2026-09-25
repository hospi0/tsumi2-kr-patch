# -*- coding: utf-8 -*-
"""ISO 통째 배포판(xdelta) 폴더를 만든다.

    python tools/mkisodist.py <한글 ISO> <xdelta 파일> <출력폴더>

⛔이 파일은 **Write 도구로 직접** 만들 것. bash heredoc 은 백슬래시를 먹어서
  `%~dp0xdelta.exe` 같은 경로가 깨진다(mkinstaller.py 에서 실제로 겪었다).
★배치는 **CP949 + CRLF**. 설명서는 일본어 원제(継) 때문에 UTF-8(BOM).
★원본 ISO 는 Redump 표준 덤프 하나만 받는다 — 해시를 배치가 직접 검사한다.
★4.4GB MD5 는 certutil 로 1분쯤 걸린다. 그래도 검사한다: 엉뚱한 덤프에
  패치하면 조용히 망가진 ISO 가 나온다.
"""
import io, os, sys, hashlib

MD5_SRC = 'fd9f83599cb9962e3ba8137b19454c1f'   # Redump / disc 43190
SHA1_SRC = 'cf4225060f76f3d8842a63bcdbe00313bb5cc155'
CRC_SRC = '4780998f'

BAT = r'''@echo off
chcp 949 >nul
setlocal enabledelayedexpansion
title 죄와 벌 ~우주의 후계자~ 한글패치 v0.9 (ISO)
cd /d "%~dp0"

echo ==========================================================
echo   죄와 벌 ~우주의 후계자~ (Wii / R2VJ01) 한글패치 v0.9
echo     자막 270줄 + UI 299행 전량 한글화  ^| ISO 통째 패치
echo ==========================================================
echo.

set "SRC=%~1"
if not "%SRC%"=="" goto GOTSRC
for %%F in ("원본넣는곳\*.iso") do set "SRC=%%~fF"
if "%SRC%"=="" goto NOSRC

:GOTSRC
if not exist "%SRC%" goto NOSRC
echo   원본 : %SRC%
echo.

echo [1/3] 원본 확인 ^(4.4GB 라 1분쯤 걸립니다^)
call :MD5 "%SRC%" H
if /i not "!H!"=="__MD5SRC__" (
  echo   [실패] 원본 ISO 가 Redump 표준 덤프와 다릅니다.
  echo          지금  : !H!
  echo          기대값: __MD5SRC__
  echo.
  echo   .rvz / .wbfs / 스크럽본은 그대로 쓸 수 없습니다.
  echo   돌핀에서 [파일 변환] 으로 "ISO(무압축)" 로 되돌린 뒤 다시 시도하세요.
  goto ERR
)
echo   확인 완료.
echo.

echo [2/3] 패치 적용 ^(빈 공간이 4.4GB 이상 필요합니다^)
set "DST=%~dp0죄와 벌 우주의 후계자 (한글판).iso"
"%~dp0xdelta.exe" -d -f -s "%SRC%" "%~dp0tsumi2_kr.xdelta" "%DST%"
if errorlevel 1 goto ERR
echo   적용 완료.
echo.

echo [3/3] 결과 확인
call :MD5 "%DST%" H
if /i not "!H!"=="__MD5DST__" (
  echo   [실패] 결과 ISO 해시가 다릅니다 : !H!
  goto ERR
)
echo   확인 완료.
echo.
echo   만들어진 파일 :
echo     %DST%
echo.
echo   돌핀 목록에 넣고 그냥 실행하면 됩니다. 별도 설정이 필요 없습니다.
goto END

:NOSRC
echo [실패] 원본 ISO 를 찾지 못했습니다.
echo.
echo   두 가지 방법 중 하나로 알려주세요.
echo     1) 원본 ISO 파일을 이 "패치하기.bat" 위에 끌어다 놓기
echo     2) "원본넣는곳" 폴더에 원본 ISO 를 넣고 다시 실행하기
echo.
echo   원본은 Redump 표준 덤프여야 합니다.
echo     크기  4,699,979,776 바이트
echo     MD5   __MD5SRC__
goto ERR

:MD5
rem [MD5] certutil 출력은 [해시 제목:] [해시값] [CertUtil: 완료] 세 줄.
rem   findstr /v ":" 가 이미 첫 줄과 끝 줄을 걸러 해시값 한 줄만 남긴다.
rem   [주의] 여기에 skip=1 을 또 걸면 그 한 줄까지 건너뛰어 빈 값이 나온다(실제로 그랬다).
set "_H="
for /f "delims=" %%A in ('certutil -hashfile "%~1" MD5 ^| findstr /v ":"') do if not defined _H set "_H=%%A"
set "_H=%_H: =%"
set "%~2=%_H%"
goto :eof

:ERR
echo.
echo   *** 패치를 중단했습니다. ***
:END
echo.
pause
'''

README = u'''죄와 벌 ~우주의 후계자~  (Wii / R2VJ01)  한글패치 v0.9  [ISO 패치판]
====================================================================

■ 무엇이 한글화됐나
  - 컷신 자막 270줄 전부 (구운 텍스처 39장을 다시 그렸습니다)
  - 메뉴·옵션·튜토리얼·시스템 메시지 299행 전부

■ 이 판은 무엇인가
  ISO 를 통째로 고쳐 «한글판 ISO» 를 만들어 줍니다.
  돌핀 목록에 넣고 그냥 실행하면 되고, Riivolution 설정이 필요 없습니다.
  USB 로더로 실기에서 돌릴 때도 이 판을 쓰면 됩니다.

  (Riivolution 판을 따로 배포합니다. 원본을 안 건드리고 켜고 끄고 싶다면
   그쪽을 쓰세요. 한글화 내용은 완전히 같습니다.)

■ 필요한 원본
  Redump 표준 덤프 한 가지만 받습니다.
      파일명 예 : Tsumi to Batsu - Sora no Koukeisha (Japan).iso
      크기      : 4,699,979,776 바이트
      CRC-32    : __CRCSRC__
      MD5       : __MD5SRC__
      SHA-1     : __SHA1SRC__

  .rvz / .wbfs / .nkit 으로 갖고 있다면 먼저 ISO 로 되돌리세요.
  돌핀에서 게임 우클릭 - [파일 변환] - 형식 «ISO», 압축 «없음» 이면 됩니다.
  되돌린 ISO 는 위 해시와 같아집니다.

■ 패치 방법
  1. 원본 ISO 를 "패치하기.bat" 위에 끌어다 놓습니다.
     (또는 "원본넣는곳" 폴더에 넣고 "패치하기.bat" 을 실행)
  2. 원본 해시 확인 → 패치 → 결과 해시 확인까지 자동입니다.
  3. 이 폴더에 "죄와 벌 우주의 후계자 (한글판).iso" 가 생깁니다.

  ※ 4.4GB 짜리를 새로 만들기 때문에 빈 공간이 4.4GB 이상 필요하고,
     해시 검사에 1~2분 걸립니다.

■ 어떻게 만들어졌나
  디스크의 암호화 파티션을 «바뀐 파일이 든 클러스터 그룹만» 다시 구웠습니다.
  손댄 곳은 24MiB 뿐이고, 나머지는 원본과 바이트 단위로 같습니다.
  해시 트리(H0~H4)를 다시 계산했고 TMD 는 fake sign 했습니다.
  wit VERIFY 로 두 파티션 모두 +OK 를 확인했습니다.

■ 알려진 것
  - 이름 입력 화면의 글자표(A~Z, 0~9)와 스코어 표기는 원문 그대로입니다.
  - 게임 로고·버튼 그림(FILE NEW / OK! / CANCEL 등)은 그림이라 원문입니다.

■ 해시 (MD5)
  원본 ISO   __MD5SRC__
  한글 ISO   __MD5DST__
  xdelta     __MD5PAT__
'''


def md5file(p):
    m = hashlib.md5()
    with open(p, 'rb') as f:
        while True:
            b = f.read(1 << 24)
            if not b:
                break
            m.update(b)
    return m.hexdigest()


def main():
    iso, xd, out = sys.argv[1], sys.argv[2], sys.argv[3]
    for d in (out, os.path.join(out, u'원본넣는곳')):
        if not os.path.isdir(d):
            os.makedirs(d)
    rep = {'__MD5SRC__': MD5_SRC, '__SHA1SRC__': SHA1_SRC, '__CRCSRC__': CRC_SRC,
           '__MD5DST__': md5file(iso), '__MD5PAT__': md5file(xd)}
    bat, rd = BAT, README
    for k, v in rep.items():
        bat = bat.replace(k, v)
        rd = rd.replace(k, v)
    io.open(os.path.join(out, u'패치하기.bat'), 'w',
            encoding='cp949', newline='\r\n').write(bat)
    io.open(os.path.join(out, u'읽어주세요.txt'), 'w',
            encoding='utf-8-sig', newline='\r\n').write(rd)
    io.open(os.path.join(out, u'원본넣는곳', u'여기에 원본 ISO 를 넣으세요.txt'), 'w',
            encoding='utf-8-sig', newline='\r\n').write(
        u'원본 ISO 를 이 폴더에 넣고 위의 "패치하기.bat" 을 실행하세요.\r\n'
        u'MD5 %s\r\n' % MD5_SRC)
    print(u'배포판 -> %s' % out)
    for k, v in sorted(rep.items()):
        print('  %s %s' % (k, v))


if __name__ == '__main__':
    main()
