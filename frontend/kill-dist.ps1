Get-Process | Where-Object { $_.Path -like '*MineContext*' } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3
Remove-Item -Path 'D:\JiShou\MineContext\frontend\dist' -Recurse -Force -ErrorAction SilentlyContinue
Write-Host 'Done'
