# 全套重启（先停整套再按依赖顺序起）。零参数，任何目录都能跑：
#   powershell -ExecutionPolicy Bypass -File D:\AI-Novel-Forge\scripts\restart-stack.ps1
$ErrorActionPreference = "Stop"
$compose = Join-Path $PSScriptRoot '..\deploy\docker-compose.yml'
& docker compose -f $compose down
& docker compose -f $compose up -d
