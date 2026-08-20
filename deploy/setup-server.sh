#!/usr/bin/env bash
# AI Novel Forge - 服务器首次部署脚本（Ubuntu 22.04/24.04 LTS）
# 用法：
#   export ZHIPU_API_KEY="sk-xxxx"
#   curl -fsSL https://raw.githubusercontent.com/Zero-WYM/AI-Novel-Forge/main/deploy/setup-server.sh | bash
# 或本地：
#   ./deploy/setup-server.sh

set -e

ZHIPU_API_KEY="${ZHIPU_API_KEY:-}"
ALLOW_OPEN_REGISTER="${ALLOW_OPEN_REGISTER:-true}"
SECRET_KEY="${SECRET_KEY:-$(openssl rand -hex 32)}"

if [ -z "$ZHIPU_API_KEY" ]; then
    echo "❌ 请先设置 ZHIPU_API_KEY 环境变量"
    echo "   export ZHIPU_API_KEY='sk-xxxx'"
    exit 1
fi

echo "==> 安装 Docker（官方源）"
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=\"$(dpkg --print-architecture)\" signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  \"$(. /etc/os-release && echo "$VERSION_CODENAME")\" stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable docker --now

echo "==> 将当前用户加入 docker 组（需重新登录生效，首次运行脚本请用 sudo）"
sudo usermod -aG docker "${USER}" || true

echo "==> 拉取代码"
if [ ! -d "AI-Novel-Forge" ]; then
    git clone https://github.com/Zero-WYM/AI-Novel-Forge.git
fi
cd AI-Novel-Forge

echo "==> 写入 .env"
cat > .env <<EOF
ZHIPU_API_KEY=${ZHIPU_API_KEY}
SECRET_KEY=${SECRET_KEY}
ALLOW_OPEN_REGISTER=${ALLOW_OPEN_REGISTER}
EOF

echo "==> 启动生产服务"
sudo docker compose -f deploy/docker-compose.prod.yml up -d --build

echo "==> 清理悬空镜像"
sudo docker image prune -f

echo ""
echo "✅ 部署完成！"
echo "   前端访问：http://$(curl -s ifconfig.me 2>/dev/null || echo '<服务器公网IP>')"
echo "   API 文档：http://$(curl -s ifconfig.me 2>/dev/null || echo '<服务器公网IP>')/docs"
echo "   SECRET_KEY 已写入 .env，请妥善保管。"
