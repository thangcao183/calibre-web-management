---
description: How to deploy the application to production
---

# Deploy to Production

## Prerequisites
- Python 3.10+
- Calibre installed (`calibredb` available in PATH)
- Nginx installed
- Certbot installed (for SSL)

## Steps

1. Clone the repository and cd into it

2. Copy environment config
```bash
cp .env.example .env
```

3. Edit `.env` with strong credentials
```bash
nano .env
```

4. Run the start script (creates venv, installs deps, starts server)
// turbo
```bash
chmod +x start.sh && ./start.sh
```

5. Install the systemd service
```bash
sudo cp calibre-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable calibre-web
sudo systemctl start calibre-web
```

6. Setup Nginx
```bash
# Edit nginx.conf: change server_name to your domain
nano nginx.conf
sudo cp nginx.conf /etc/nginx/sites-available/calibre-web
sudo ln -s /etc/nginx/sites-available/calibre-web /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

7. Setup SSL with Let's Encrypt
```bash
sudo certbot --nginx -d your-domain.com
```

## Verify

// turbo
```bash
sudo systemctl status calibre-web
curl -I http://localhost:5000
```

## Logs

// turbo
```bash
journalctl -u calibre-web -f
```
