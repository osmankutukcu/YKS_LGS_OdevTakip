#requires -Version 5.1
# V25.5 - Standalone Windows DPAPI synthetic checks. No student data, no WhatsApp, no network.
# This script does NOT enable any sending method or access the application database.
[CmdletBinding()]
param(
    [switch]$VerifyChild,
    [string]$PayloadFile = '',
    [string]$ResultFile = '',
    [string]$Expected = ''
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Get-Entropy {
    return [System.Text.Encoding]::UTF8.GetBytes('OdevTakip-V25.5-Offline-DPAPI-Test-Only')
}
function Dpapi-Protect([byte[]]$plain, [byte[]]$entropy) {
    return [System.Security.Cryptography.ProtectedData]::Protect(
        $plain, $entropy, [System.Security.Cryptography.DataProtectionScope]::CurrentUser)
}
function Dpapi-Unprotect([byte[]]$cipher, [byte[]]$entropy) {
    return [System.Security.Cryptography.ProtectedData]::Unprotect(
        $cipher, $entropy, [System.Security.Cryptography.DataProtectionScope]::CurrentUser)
}
function Fail-Test([string]$message) {
    throw [System.InvalidOperationException]::new($message)
}

# Fail before creating any files on non-Windows systems.
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
    Write-Output 'Yalnizca Windows uzerinde calisir. WhatsApp gonderimi KAPALI.'
    exit 2
}
try { Add-Type -AssemblyName System.Security -ErrorAction Stop } catch {
    Write-Output 'Windows DPAPI bileseni yuklenemedi. Test basarisiz.'
    exit 2
}

# A separate PowerShell process can verify the same-user DPAPI sealed marker.
if ($VerifyChild) {
    try {
        if (-not $PayloadFile -or -not $ResultFile -or -not $Expected) { Fail-Test 'Eksik test parametresi' }
        $record = Get-Content -LiteralPath $PayloadFile -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($record.version -ne 'V25.5') { Fail-Test 'Uyumsuz test dosyasi' }
        $cipher = [Convert]::FromBase64String([string]$record.ciphertext)
        $decoded = Dpapi-Unprotect $cipher (Get-Entropy)
        $actual = [System.Text.Encoding]::UTF8.GetString($decoded)
        if ($actual -ne $Expected) { Fail-Test 'Oturum verisi eslesmedi' }
        [System.IO.File]::WriteAllText($ResultFile, 'PASS', [System.Text.Encoding]::ASCII)
        exit 0
    } catch { exit 3 }
}

$checks = New-Object 'System.Collections.Generic.List[string]'
$tempDir = $null
$hadFailure = $false
$reportWritten = $false
$reportDir = $null
try {
    $local = [Environment]::GetFolderPath('LocalApplicationData')
    if ([string]::IsNullOrWhiteSpace($local)) { Fail-Test 'Yerel Windows veri klasoru bulunamadi' }
    $base = Join-Path $local 'OdevTakip'
    $tempRoot = Join-Path $base 'Guvenlik_Test_Gecici_V255'
    $reportDir = Join-Path $base 'Guvenlik_Raporlari_V255'
    [void][System.IO.Directory]::CreateDirectory($tempRoot)
    [void][System.IO.Directory]::CreateDirectory($reportDir)
    $tempDir = Join-Path $tempRoot ([Guid]::NewGuid().ToString('N'))
    [void][System.IO.Directory]::CreateDirectory($tempDir)

    $marker = 'V255-SYNTHETIC-' + [Guid]::NewGuid().ToString('N')
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($marker)
    $entropy = Get-Entropy
    $cipher = Dpapi-Protect $bytes $entropy
    $plain = Dpapi-Unprotect $cipher $entropy
    if ([System.Text.Encoding]::UTF8.GetString($plain) -ne $marker) {
        Fail-Test 'DPAPI ayni oturum testi basarisiz'
    }
    $checks.Add('DPAPI_CURRENT_USER_ROUNDTRIP')

    $wrong = [System.Text.Encoding]::UTF8.GetBytes('Wrong-Test-Entropy-V255')
    $denied = $false
    try { $unused = Dpapi-Unprotect $cipher $wrong } catch { $denied = $true }
    if (-not $denied) { Fail-Test 'Yanlis amacla cozum engellenmedi' }
    $checks.Add('WRONG_PURPOSE_DENIED')

    [byte[]]$tampered = [byte[]]$cipher.Clone()
    $tampered[0] = $tampered[0] -bxor 255
    $denied = $false
    try { $unused = Dpapi-Unprotect $tampered $entropy } catch { $denied = $true }
    if (-not $denied) { Fail-Test 'Bozulmus sifreli veri engellenmedi' }
    $checks.Add('TAMPERED_CIPHERTEXT_DENIED')

    $encFile = Join-Path $tempDir 'synthetic_encrypted.json'
    $resultFile = Join-Path $tempDir 'child_verification.txt'
    $envelope = @{ version = 'V25.5'; ciphertext = [Convert]::ToBase64String($cipher) } | ConvertTo-Json -Compress
    if ($envelope.Contains($marker)) { Fail-Test 'Sentetik acik metin disari sizdi' }
    [System.IO.File]::WriteAllText($encFile, $envelope, [System.Text.Encoding]::UTF8)
    $onDisk = [System.IO.File]::ReadAllText($encFile, [System.Text.Encoding]::UTF8)
    if ($onDisk.Contains($marker)) { Fail-Test 'Sentetik acik metin diskte' }
    $checks.Add('NO_PLAINTEXT_IN_TEST_FILE')

    $childExe = Join-Path $PSHOME 'powershell.exe'
    if (-not [System.IO.File]::Exists($childExe)) { Fail-Test 'PowerShell alt islemi bulunamadi' }
    & $childExe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $PSCommandPath `
        -VerifyChild -PayloadFile $encFile -ResultFile $resultFile -Expected $marker 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0 -or -not [System.IO.File]::Exists($resultFile)) {
        Fail-Test 'Ayni Windows kullanicisinda yeniden acma kontrolu basarisiz'
    }
    if ([System.IO.File]::ReadAllText($resultFile).Trim() -ne 'PASS') {
        Fail-Test 'Alt islem dogrulamasi basarisiz'
    }
    $checks.Add('SAME_USER_SECOND_PROCESS_ROUNDTRIP')

} catch {
    $hadFailure = $true
} finally {
    # Synthetic test payload is deleted even on failure.
    if ($null -ne $tempDir -and [System.IO.Directory]::Exists($tempDir)) {
        try { [System.IO.Directory]::Delete($tempDir, $true) } catch { $hadFailure = $true }
    }
}

$status = if (-not $hadFailure -and $checks.Count -eq 5) { 'PASS_SYNTHETIC_DPAPI_ONLY' } else { 'FAIL_CLOSED' }
$description = if ($status -eq 'PASS_SYNTHETIC_DPAPI_ONLY') {
    'Windows DPAPI sentetik testi basarili. Iki kullanici testi, uygulamanin Python kasasi, WhatsApp baglantisi ve gercek gonderim DOGRULANMADI.'
} else {
    'Test tamamlanamadi veya bir kontrol basarisiz. Arka plan WhatsApp baglantisi KAPALI kalir.'
}
$record = [ordered]@{
    version = 'V25.5'
    test_type = 'powershell_dpapi_synthetic_only'
    result = $status
    completed_checks = @($checks.ToArray())
    checks_expected = 5
    distinct_windows_users_verified = $false
    python_v250_v254_modules_tested = $false
    personal_whatsapp_connected = $false
    real_messages_sent = 0
    baileys_enabled = $false
    message_queue_changed = $false
    student_or_parent_data_read = $false
    description = $description
}
try {
    if ([string]::IsNullOrWhiteSpace($reportDir)) { Fail-Test 'Rapor klasoru bulunamadi' }
    $id = [DateTime]::UtcNow.ToString('yyyyMMdd_HHmmss') + '_' + [Guid]::NewGuid().ToString('N').Substring(0,8)
    $jsonPath = Join-Path $reportDir ('V25_5_RAPOR_' + $id + '.json')
    $textPath = Join-Path $reportDir ('V25_5_RAPOR_' + $id + '.txt')
    $json = $record | ConvertTo-Json -Depth 5
    [System.IO.File]::WriteAllText($jsonPath, $json, [System.Text.Encoding]::UTF8)
    $text = @(
        'ODEV TAKIP V25.5 - WINDOWS DPAPI ON TEST'
        ('SONUC: ' + $status)
        ('Sentetik kontroller: ' + $checks.Count + '/5')
        $description
        'Iki farkli Windows kullanicisi ile test: YAPILMADI'
        'V25.0-V25.4 Python kasa/kuyruk uygulamasi: BU TESTTE CALISTIRILMADI'
        'WhatsApp baglantisi veya gercek mesaj gonderimi: YAPILMADI'
        'Baileys: KAPALI'
        'Gercek veli veya ogrenci verisi: OKUNMADI'
    ) -join [Environment]::NewLine
    [System.IO.File]::WriteAllText($textPath, $text, [System.Text.Encoding]::UTF8)
    $reportWritten = $true
    Write-Output (('SONUC: ' + $status))
    Write-Output ('Kontrol sayisi: ' + $checks.Count + '/5')
    Write-Output ('Rapor: ' + $textPath)
} catch {
    Write-Output 'Rapor dosyasi yazilamadi; basari onayi VERILMEDI.'
    exit 2
}
if ($status -eq 'PASS_SYNTHETIC_DPAPI_ONLY' -and $reportWritten) { exit 0 }
exit 2
