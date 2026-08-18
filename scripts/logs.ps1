# 看后端日志（最近 200 行）。任何目录下都能跑，不用参数。
# 复制这一行到 PowerShell，回车即可看到日志：
#   powershell -ExecutionPolicy Bypass -File D:\AI-Novel-Forge\scripts\logs.ps1
$ErrorActionPreference = "Stop"
$compose = Join-Path $PSScriptRoot '..\deploy\docker-compose.yml'
& docker compose -f $compose logs backend --tail=200
