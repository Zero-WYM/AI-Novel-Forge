# 仅重启后端容器（前后端代码改完需 restart backend 才能生效）。
# 零参数，任何目录都能跑：
#   powershell -ExecutionPolicy Bypass -File D:\AI-Novel-Forge\scripts\restart-backend.ps1
$ErrorActionPreference = "Stop"
$compose = Join-Path $PSScriptRoot '..\deploy\docker-compose.yml'
& docker compose -f $compose restart backend
