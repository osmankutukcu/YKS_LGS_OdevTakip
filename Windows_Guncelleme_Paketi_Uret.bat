@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Surum numarasi version.py + setup.iss icinde esit olmali.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" publish_release.py %*
) else (
  where py >nul 2>&1
  if not errorlevel 1 (
    py -3 publish_release.py %*
  ) else (
    python publish_release.py %*
  )
)
if errorlevel 1 (
  echo [HATA] Release paketi hazirlanamadi.
  pause
  exit /b 1
)
echo [OK] Release dosyalari dist_release klasorunde.
pause
