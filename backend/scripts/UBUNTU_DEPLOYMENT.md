# Ubuntu 部署指南

本文档介绍如何在 Ubuntu 服务器上部署 OnlineWorld 后端服务。

## 问题说明

如果你遇到以下错误：

```
Failed to find attribute 'app' in 'app'
```

这是因为 gunicorn 命令使用了错误的模块路径。正确的命令应该是：

```bash
# ❌ 错误
gunicorn app:app

# ✅ 正确
gunicorn app.main:app
```

## 快速开始

### 方法 1：使用部署脚本（推荐）

```bash
cd /root/website/OnlineWorld/backend

# 添加执行权限
chmod +x scripts/deploy.sh

# 启动服务
./scripts/deploy.sh start

# 查看状态
./scripts/deploy.sh status

# 查看日志
./scripts/deploy.sh logs

# 重启服务
./scripts/deploy.sh restart

# 停止服务
./scripts/deploy.sh stop
```

### 方法 2：使用 systemd（生产环境推荐）

```bash
# 1. 复制服务文件到 systemd 目录
sudo cp scripts/onlineworld.service /etc/systemd/system/

# 2. 根据需要编辑服务文件（修改路径、用户等）
sudo nano /etc/systemd/system/onlineworld.service

# 3. 重新加载 systemd
sudo systemctl daemon-reload

# 4. 启动服务
sudo systemctl start onlineworld

# 5. 设置开机自启
sudo systemctl enable onlineworld

# 6. 查看状态
sudo systemctl status onlineworld

# 7. 查看日志
sudo journalctl -u onlineworld -f

# 8. 重启服务
sudo systemctl restart onlineworld

# 9. 停止服务
sudo systemctl stop onlineworld
```

### 方法 3：手动启动

```bash
cd /root/website/OnlineWorld/backend

# 激活虚拟环境
source venv/bin/activate

# 使用 uvicorn（开发环境）
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 或使用 gunicorn（生产环境）
gunicorn app.main:app \
    --bind 0.0.0.0:8000 \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker
```

## 安装步骤

### 1. 安装系统依赖

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv nginx
```

### 2. 创建虚拟环境

```bash
cd /root/website/OnlineWorld/backend
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
```

### 3. 安装项目依赖

```bash
pip install -r requirements.txt
```

### 4. 安装 gunicorn 和 uvicorn

```bash
pip install gunicorn uvicorn[standard]
```

### 5. 配置环境变量（可选）

```bash
# 创建 .env 文件
cat > .env << EOF
APP_NAME=OnlineWorld
DEBUG=false
DATABASE_URL=sqlite:///./onlineworld.db
EOF
```

### 6. 测试运行

```bash
# 使用部署脚本启动
./scripts/deploy.sh start

# 或手动启动
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 7. 配置 Nginx（可选，用于生产环境）

```bash
# 创建 Nginx 配置文件
sudo nano /etc/nginx/sites-available/onlineworld
```

添加以下配置：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

启用配置：

```bash
sudo ln -s /etc/nginx/sites-available/onlineworld /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## 常见问题

### 1. 端口被占用

如果 8000 端口被占用，可以修改绑定端口：

```bash
# 修改部署脚本中的 BIND 变量
BIND="0.0.0.0:8080"

# 或手动指定
gunicorn app.main:app --bind 0.0.0.0:8080
```

### 2. 权限问题

确保脚本有执行权限：

```bash
chmod +x scripts/deploy.sh
chmod +x scripts/start_auto_scheduler.sh
```

### 3. 虚拟环境路径错误

如果虚拟环境路径不同，请修改部署脚本中的 `VENV_DIR` 变量。

### 4. 工作进程数调整

根据服务器配置调整工作进程数：

```bash
# 一般规则：工作进程数 = (CPU 核心数 * 2) + 1
# 在部署脚本中修改 WORKERS 变量
WORKERS=4
```

### 5. 查看实时日志

```bash
# 使用部署脚本
./scripts/deploy.sh logs

# 或直接查看日志文件
tail -f .gunicorn.error.log
tail -f .gunicorn.log

# systemd 方式
sudo journalctl -u onlineworld -f
```

## 性能优化

### 1. 调整工作进程和线程

```bash
# 在 deploy.sh 中修改
WORKERS=4      # 根据 CPU 核心数调整
THREADS=2      # 每个工作进程的线程数
```

### 2. 启用 Gzip 压缩（Nginx）

```nginx
gzip on;
gzip_vary on;
gzip_min_length 1024;
gzip_types text/plain text/css text/xml text/javascript 
           application/x-javascript application/xml+rss 
           application/json application/javascript;
```

### 3. 配置 SSL（推荐）

```bash
# 使用 Let's Encrypt
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## 监控和维护

### 查看服务状态

```bash
# 部署脚本
./scripts/deploy.sh status

# systemd
sudo systemctl status onlineworld
```

### 重启服务

```bash
# 部署脚本
./scripts/deploy.sh restart

# systemd
sudo systemctl restart onlineworld
```

### 查看进程信息

```bash
ps aux | grep gunicorn
ps aux | grep onlineworld
```

### 查看端口占用

```bash
netstat -tulpn | grep 8000
ss -tulpn | grep 8000
```

## 自动化调度器

如果要运行自动调度器（每小时执行任务）：

```bash
cd /root/website/OnlineWorld/backend

# 启动自动调度器
./scripts/start_auto_scheduler.sh

# 查看调度器状态
./scripts/start_auto_scheduler.sh --status

# 查看调度器日志
./scripts/start_auto_scheduler.sh --logs
```

## 安全建议

1. **使用防火墙**：
   ```bash
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   sudo ufw enable
   ```

2. **定期更新系统**：
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

3. **使用非 root 用户运行服务**：
   ```bash
   sudo useradd -r -s /bin/false onlineworld
   sudo chown -R onlineworld:onlineworld /root/website/OnlineWorld
   ```

4. **配置日志轮转**：
   ```bash
   sudo nano /etc/logrotate.d/onlineworld
   ```

## 备份和恢复

### 备份数据库

```bash
cp /root/website/OnlineWorld/backend/*.db /backup/
```

### 恢复数据库

```bash
cp /backup/*.db /root/website/OnlineWorld/backend/
```

## 联系支持

如有问题，请查看：
- 错误日志：`.gunicorn.error.log`
- 访问日志：`.gunicorn.log`
- 系统日志：`sudo journalctl -u onlineworld`
