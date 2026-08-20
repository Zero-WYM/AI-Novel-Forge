#!/usr/bin/env bash
# AI Novel Forge 一键更新脚本（在服务器上运行）
# 用法：./deploy/redeploy.sh
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# 如果当前用户没有 Docker 权限，自动用 sudo（setup-server.sh 把用户加入 docker 组后需重新登录才生效）
DOCKER="docker"
DOCKER_COMPOSE="docker compose"
if ! "$DOCKER" info >/dev/null 2>&1; then
  if command -v sudo >/dev/null 2>&1; then
    echo "⚠️ 当前用户没有 Docker 权限，将使用 sudo 执行 docker 命令"
    DOCKER="sudo docker"
    DOCKER_COMPOSE="sudo docker compose"
  else
    echo "❌ 当前用户没有 Docker 权限，且未安装 sudo。请先运行："
    echo "   sudo usermod -aG docker \$USER && newgrp docker"
    exit 1
  fi
fi

echo "==> 拉取最新代码"
if [ -d .git ]; then
  git pull --ff-only || echo "（git pull 失败或非快进，跳过；请手动检查）"
fi

echo "==> 重建并重启生产服务"
$DOCKER_COMPOSE -f deploy/docker-compose.prod.yml up -d --build

echo "==> 清理悬空镜像"
$DOCKER image prune -f

echo ""
echo "✅ 部署完成！访问 http://<你的服务器公网IP>"
