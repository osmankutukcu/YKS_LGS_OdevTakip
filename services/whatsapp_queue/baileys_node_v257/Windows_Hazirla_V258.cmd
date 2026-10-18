@echo off
setlocal
cd /d "%~dp0"
title EduTrack V25.8 - Baileys Windows pilot
where node >nul 2>&1
if errorlevel 1 (echo Node.js 20+ bulunamadi. nodejs.org uzerinden yukleyin.&pause&exit /b 1)
where npm >nul 2>&1
if errorlevel 1 (echo npm bulunamadi.&pause&exit /b 1)
echo === V25.8 - Sadece bu kullanicinin profilindeki Baileys motoru kurulacak ===
node --version
npm --version
choice /M "Baileys 7.0.0-rc14 resmi npm kaynagindan indirilsin mi"
if errorlevel 2 exit /b 1
echo Paket kilidi hazirlaniyor...
call npm install --package-lock-only --ignore-scripts --no-audit --no-fund --save-exact
if errorlevel 1 (echo npm paket kilidi olusmadi - INTERNET gerekli.&pause&exit /b 1)
echo Bagimliliklar kuruluyor...
call npm ci --ignore-scripts --no-audit --no-fund
if errorlevel 1 (echo npm ci basarisiz.&pause&exit /b 1)
echo Baileys protokol dogrulama testleri...
call node --test tests\rules.test.mjs tests\bulk_rules_v258.test.mjs
if errorlevel 1 (echo Protokol testleri basarisiz.&pause&exit /b 1)
echo.
echo V25.8 kurulum hazir. Odev Takip ana penceresinden Baileys yontemini baslatabilirsiniz.
echo QR eslestirme olmadan hicbir mesaj gonderilmez.
pause
