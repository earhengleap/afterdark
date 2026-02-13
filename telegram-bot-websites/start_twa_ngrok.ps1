param(
  [int]$Port = 5000,
  [string]$NgrokPath = "ngrok",
  [string]$MenuText = "Open Vault",
  [switch]$ConfigureMenu
)

Write-Host "Starting Mini App backend on port $Port..."
Start-Process -FilePath "python" -ArgumentList "telegram-bot-websites/server.py" -WindowStyle Normal

Start-Sleep -Seconds 2

Write-Host "Starting ngrok tunnel..."
Start-Process -FilePath $NgrokPath -ArgumentList "http $Port" -WindowStyle Normal

Write-Host "Waiting for ngrok API..."
$publicUrl = $null
for($i=0; $i -lt 30; $i++) {
  Start-Sleep -Seconds 1
  try {
    $resp = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -Method Get -ErrorAction Stop
    $httpsTunnel = $resp.tunnels | Where-Object { $_.proto -eq "https" } | Select-Object -First 1
    if($httpsTunnel) {
      $publicUrl = $httpsTunnel.public_url
      break
    }
  } catch {
    # keep waiting
  }
}

if(-not $publicUrl) {
  Write-Host "Could not detect ngrok URL. Open http://127.0.0.1:4040 manually."
  exit 1
}

Write-Host "Mini App public URL: $publicUrl"

if($ConfigureMenu) {
  Write-Host "Configuring bot menu button..."
  python telegram-bot-websites/configure_twa.py --url $publicUrl --text $MenuText
}
