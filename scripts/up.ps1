# 全套启动（postgres → backend → frontend）。零参数，任何目录都能跑：
#   powershell -ExecutionPolicy Bypass -File D:\AI-Novel-Forge\scripts\up.ps1
$ErrorActionPreference = "Stop"
$compose = Join-Path $PSScriptRoot '..\deploy\docker-compose.yml'
& docker compose -f $compose up -d
