#!/usr/bin/env bash
# AI Novel Forge 一键更新脚本（在服务器上运行）
# 用法：./deploy/redeploy.sh
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> 拉取最新代码"
if [ -d .git ]; then
  git pull --ff-only || echo "（git pull 失败或非快进，跳过；请手动检查）"
fi

echo "==> 重建并重启生产服务"
docker compose -f deploy/docker-compose.prod.yml up -d --build

echo "==> 清理悬空镜像"
docker image prune -f

echo ""
echo "✅ 部署完成！访问 http://<你的服务器公网IP>"
