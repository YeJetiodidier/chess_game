$PYTHON = "C:\Users\ANOS\AppData\Local\Programs\Python\Python313\python.exe"
$URL    = "https://files.pythonhosted.org/packages/3d/6c/f26ed528d197859cf8a634bbfafc3bc136f5590b6620df179d1858a34fdc/torch-2.15.0-cp313-cp313-win_amd64.whl"
$WHL    = "torch-2.15.0-cp313-cp313-win_amd64.whl"
$EXPECT_HASH = "e079089d36401261ebe145504309d0114fb9a00529eac4b33048221d2376a15c"
$TOTAL_BYTES = 132887552   # 126.7 MB

while ($true) {
    $current = (Get-Item $WHL -ErrorAction SilentlyContinue).Length
    if ($current -ge $TOTAL_BYTES) { break }
    $mb = [math]::Round($current/1MB, 1)
    Write-Host "[$([datetime]::Now.ToString('HH:mm:ss'))] Downloading... ${mb} MB / 126.7 MB"
    curl.exe -L -C - --retry 5 --retry-delay 3 -o $WHL $URL
    if ($LASTEXITCODE -eq 0) { break }
    Write-Host "Connection dropped, retrying in 5s..."
    Start-Sleep 5
}

Write-Host ""
Write-Host "Verifying SHA-256..."
$hash = (Get-FileHash $WHL -Algorithm SHA256).Hash.ToLower()
if ($hash -ne $EXPECT_HASH) {
    Write-Host "ERROR: Hash mismatch! Got $hash"
    Write-Host "Expected $EXPECT_HASH"
    exit 1
}

Write-Host "Hash OK. Installing..."
& $PYTHON -m pip install --no-index --find-links . torch
Write-Host ""
Write-Host "Done! Now run:"
Write-Host "  & '$PYTHON' train.py --data data.npz --epochs 5"
Write-Host "  & '$PYTHON' predict.py --model model.pt"

