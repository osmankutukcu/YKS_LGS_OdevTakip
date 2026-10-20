@echo off
setlocal EnableExtensions
cd /d "%~dp0" || exit /b 2
title KocPilot 360 - Baileys Windows kurulum

where node >nul 2>&1
if errorlevel 1 (echo HATA: Node.js 20+ bulunamadi.&exit /b 10)
where npm >nul 2>&1
if errorlevel 1 (echo HATA: npm bulunamadi.&exit /b 11)
for /f %%v in ('node -p "process.versions.node.split('.')[0]" 2^>nul') do set "NODE_MAJOR=%%v"
if not defined NODE_MAJOR (echo HATA: Node.js surumu okunamadi.&exit /b 12)
if %NODE_MAJOR% LSS 20 (echo HATA: En az Node.js 20 gereklidir.&exit /b 13)

if not "%BAILEYS_SETUP_APPROVED%"=="1" (
  echo Onay olmadan indirme ve kurulum baslatilmaz.
  choice /M "Sabit Baileys paketi npm uzerinden indirilsin mi"
  if errorlevel 2 exit /b 14
)

echo Asama 1/3 - npm kilit dosyasi denetleniyor...
if not exist "package-lock.json" (
  call npm install --package-lock-only --ignore-scripts --no-audit --no-fund --save-exact
  if errorlevel 1 (echo HATA: Kilit dosyasi olusturulamadi.&exit /b 21)
)
echo Asama 2/3 - Sabit bagimliliklar kuruluyor (npm scripts kapali)...
call npm ci --ignore-scripts --no-audit --no-fund
if errorlevel 1 (echo HATA: Bagimliliklar kurulamadi; internet/izin kontrol edin.&exit /b 22)
echo Asama 3/3 - Gonderimsiz protokol testleri...
call node --test tests\rules.test.mjs tests\bulk_rules_v258.test.mjs
if errorlevel 1 (echo HATA: Protokol testleri basarisiz.&exit /b 23)
echo KURULUM_BASARILI - WhatsApp QR eslestirme henuz yapilmadi.
exit /b 0
