$adb = "C:\Users\PC\AppData\Local\Android\Sdk\platform-tools\adb.exe"

Write-Host "Setting up adb reverse tunnel..." -ForegroundColor Cyan
& $adb reverse tcp:8000 tcp:8000
$tunnelCheck = & $adb reverse --list
if ($tunnelCheck -match "tcp:8000") {
    Write-Host "Tunnel active: Android 127.0.0.1:8000 -> PC :8000" -ForegroundColor Green
} else {
    Write-Host "WARNING: Tunnel may have failed. Is the device connected?" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Starting Django dev server..." -ForegroundColor Cyan
$env:DJANGO_SETTINGS_MODULE = "config.settings.development"
$env:PYTHONIOENCODING = "utf-8"
python manage.py runserver 0.0.0.0:8000
