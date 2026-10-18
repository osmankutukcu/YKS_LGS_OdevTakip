@echo off
setlocal
cd /d "%~dp0"
where node >nul 2>&1
if errorlevel 1 (
 echo Node.js 20+ kurulu degil. Node.js'i resmi nodejs.org sitesinden kurun.
 echo Programin ana WhatsApp yontemleri etkilenmedi.
 pause
 exit /b 1
)
where npm >nul 2>&1
if errorlevel 1 (echo npm bulunamadi.&pause&exit /b 1)
echo === V25.7 Baileys bagimlilik kurulumu, SADECE izinli test ===
echo Node.js ve npm surumlerinizi kontrol edin, sonra devam edin.
node --version
npm --version
choice /M "Resmi npm deposundan sabit Baileys 7.0.0-rc14 indirilsin mi"
if errorlevel 2 exit /b 1
if not exist package-lock.json (
 call npm install --package-lock-only --ignore-scripts --no-audit --no-fund --save-exact
 if errorlevel 1 (echo Kilit dosyasi olusmadi.&pause&exit /b 1)
)
call npm ci --ignore-scripts --no-audit --no-fund
if errorlevel 1 (echo Bagimlilik kurulamadi.&pause&exit /b 1)
call node --test tests\rules.test.mjs
if errorlevel 1 (echo Test basarisiz.&pause&exit /b 1)
echo Hazir. Ana programdan Baglanti testi butonunu acabilirsiniz.
pause
