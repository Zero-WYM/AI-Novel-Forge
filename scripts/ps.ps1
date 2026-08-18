# 查看三容器状态。零参数，任何目录都能跑：
#   powershell -ExecutionPolicy Bypass -File D:\AI-Novel-Forge\scripts\ps.ps1
$ErrorActionPreference = "Stop"
$compose = Join-Path $PSScriptRoot '..\deploy\docker-compose.yml'
& docker compose -f $compose ps
