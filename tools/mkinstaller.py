# -*- coding: utf-8 -*-
"""배포용 설치 배치(`설치.bat`) 를 만든다.

    python tools/mkinstaller.py <출력폴더>

⛔이 파일은 **Write 도구로 직접** 만들 것. bash heredoc 은 백슬래시를 먹어서
  `\\texture.arc` 가 탭 문자로 바뀐다(실제로 한 번 깨졌다).
★배치는 **CP949 + CRLF** 로 써야 한글이 안 깨진다.
★xdelta 는 반드시  로 부를 것 — 현재 폴더 검색에 기대면
  환경에 따라 「명령을 찾을 수 없음」이 난다(실측).
★원본·결과 MD5 를 배치 안에서 검사한다 — 잘못된 원본에 패치하면 조용히 망가진다.
"""
import io, os, sys, hashlib

MD5_TEX_SRC = 'ca234b931fd4b82286e14120f553f02d'
MD5_TEX_DST = '4923b63d633354e50987b84f885d3b82'
MD5_FNT_SRC = '814484075241d09a43693780c37580f5'
MD5_FNT_DST = '1b722b25fe41a6f067c7be1a1568397a'

BAT = r'''@echo off
chcp 949 >nul
setlocal enabledelayedexpansion
title 죄와 벌 ~우주의 후계자~ 한글패치 v0.9 설치
cd /d "%~dp0"

echo ==========================================================
echo   죄와 벌 ~우주의 후계자~ (Wii / R2VJ01) 한글패치 v0.9
echo     자막 270줄 + UI 299행 전량 한글화
echo ==========================================================
echo.

set "SRC=원본넣는곳"
if not exist "%SRC%\texture.arc" goto NOSRC
if not exist "%SRC%\MsgFont.brfnt" goto NOSRC

echo [1/4] 원본 파일 확인
call :MD5 "%SRC%\texture.arc" H
if /i not "!H!"=="__TEXSRC__" (
  echo   [실패] texture.arc 가 원본과 다릅니다.
  echo          지금  : !H!
  echo          기대값: __TEXSRC__
  goto ERR
)
call :MD5 "%SRC%\MsgFont.brfnt" H
if /i not "!H!"=="__FNTSRC__" (
  echo   [실패] MsgFont.brfnt 가 원본과 다릅니다.
  echo          지금  : !H!
  echo          기대값: __FNTSRC__
  goto ERR
)
echo   확인 완료.
echo.

echo [2/4] 패치 적용 ^(texture.arc 는 85MB 라 조금 걸립니다^)
if exist R2VJ01 rd /s /q R2VJ01
mkdir R2VJ01
"%~dp0xdelta.exe" -d -f -s "%SRC%\texture.arc" texture.arc.xdelta "R2VJ01\texture.arc"
if errorlevel 1 goto ERR
"%~dp0xdelta.exe" -d -f -s "%SRC%\MsgFont.brfnt" MsgFont.brfnt.xdelta "R2VJ01\MsgFont.brfnt"
if errorlevel 1 goto ERR
echo   적용 완료.
echo.

echo [3/4] 결과 확인
set ERRCNT=0
call :MD5 "R2VJ01\texture.arc" H
if /i not "!H!"=="__TEXDST__" (echo   [경고] texture.arc 해시 불일치 : !H! & set /a ERRCNT+=1)
call :MD5 "R2VJ01\MsgFont.brfnt" H
if /i not "!H!"=="__FNTDST__" (echo   [경고] MsgFont.brfnt 해시 불일치 : !H! & set /a ERRCNT+=1)
if !ERRCNT! gtr 0 goto ERR
echo   확인 완료.
echo.

echo [4/4] 돌핀에 설치
set "DEST=%APPDATA%\Dolphin Emulator\Load\Riivolution"
if not exist "%APPDATA%\Dolphin Emulator" (
  echo   돌핀 설정 폴더를 못 찾았습니다.
  goto MANUAL
)
choice /c YN /m "  %DEST% 에 복사할까요"
if errorlevel 2 goto MANUAL
if not exist "%DEST%\riivolution" mkdir "%DEST%\riivolution"
if not exist "%DEST%\R2VJ01" mkdir "%DEST%\R2VJ01"
copy /y "riivolution\tsumi2_kr.xml" "%DEST%\riivolution\" >nul
copy /y "R2VJ01\texture.arc" "%DEST%\R2VJ01\" >nul
copy /y "R2VJ01\MsgFont.brfnt" "%DEST%\R2VJ01\" >nul
echo.
echo   설치 완료.
echo   돌핀에서 게임 우클릭 - [Riivolution 패치 시작] 을 고르고
echo   "죄와 벌 우주의 후계자 한글패치" 항목을 켜서 실행하세요.
goto END

:MANUAL
echo.
echo   [손으로 설치] 돌핀의
echo     %%APPDATA%%\Dolphin Emulator\Load\Riivolution\
echo   안에 아래를 그대로 넣으세요.
echo     riivolution\tsumi2_kr.xml
echo     R2VJ01\texture.arc
echo     R2VJ01\MsgFont.brfnt
goto END

:NOSRC
echo [실패] 원본 파일이 없습니다.
echo.
echo   "원본넣는곳" 폴더에 아래 두 파일을 넣고 다시 실행하세요.
echo       texture.arc
echo       MsgFont.brfnt
echo.
echo   꺼내는 법 : 돌핀에서 게임 우클릭 - [속성] - [파일 시스템] 탭 -
echo               Partition 1 - files 안에서 두 파일을 각각 우클릭해
echo               [파일 추출] 을 고르면 됩니다.
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
echo   *** 설치를 중단했습니다. ***
:END
echo.
pause
'''

README = u'''죄와 벌 ~우주의 후계자~  (Wii / R2VJ01)  한글패치 v0.9
================================================================

■ 무엇이 한글화됐나
  - 컷신 자막 270줄 전부 (구운 텍스처 39장을 다시 그렸습니다)
  - 메뉴·옵션·튜토리얼·시스템 메시지 299행 전부

■ 필요한 것
  - 돌핀(Dolphin) 에뮬레이터
  - 『罪と罰 宇宙の後継者』 일본판 디스크 이미지 (R2VJ01)

■ 설치 방법
  1. 돌핀에서 게임을 우클릭 - [속성] - [파일 시스템] 탭을 엽니다.
  2. Partition 1 - files 안에서 아래 두 파일을 각각 우클릭해
     [파일 추출] 로 꺼내, 이 폴더의 "원본넣는곳" 에 넣습니다.
         texture.arc
         MsgFont.brfnt
  3. "설치.bat" 을 실행합니다.
     원본 해시를 확인하고, 패치를 적용하고, 돌핀 폴더에 복사까지 합니다.
  4. 돌핀에서 게임 우클릭 - [Riivolution 패치 시작] 을 고르고
     "죄와 벌 우주의 후계자 한글패치" 를 켠 뒤 실행합니다.

■ 디스크 이미지를 고치지 않습니다
  Riivolution 방식이라 원본 ISO/WBFS 는 그대로 둡니다.
  패치를 빼려면 돌핀의 Riivolution 목록에서 끄기만 하면 됩니다.
  실기(Wii + Riivolution) 에서도 같은 파일을 씁니다.

■ 알려진 것
  - 이름 입력 화면의 글자표(A~Z, 0~9)와 스코어 표기는 원문 그대로입니다.
  - 게임 로고·버튼 그림(FILE NEW / OK! / CANCEL 등)은 그림이라 원문입니다.

■ 해시 (MD5)
  texture.arc      원본 __TEXSRC__
                   한글 __TEXDST__
  MsgFont.brfnt    원본 __FNTSRC__
                   한글 __FNTDST__
'''


def main():
    out = sys.argv[1]
    rep = {'__TEXSRC__': MD5_TEX_SRC, '__TEXDST__': MD5_TEX_DST,
           '__FNTSRC__': MD5_FNT_SRC, '__FNTDST__': MD5_FNT_DST}
    bat, rd = BAT, README
    for k, v in rep.items():
        bat = bat.replace(k, v)
        rd = rd.replace(k, v)
    io.open(os.path.join(out, '설치.bat'), 'w', encoding='cp949', newline='\r\n').write(bat)
    # ★일본어 원제(継)는 CP949 에 없다 -> 설명서는 UTF-8(BOM). 배치만 CP949.
    io.open(os.path.join(out, '읽어주세요.txt'), 'w',
            encoding='utf-8-sig', newline='\r\n').write(rd)
    print('설치.bat · 읽어주세요.txt (cp949/CRLF) -> %s' % out)


if __name__ == '__main__':
    main()
