# 🚀 Deployment Guide — Sales Doctor ↔ MoySklad Integration

## Production Serverga Joylash Qo'llanmasi

---

## 1. Server Talablari

### Minimum:
- **OS:** Ubuntu 22.04 LTS
- **CPU:** 2 core
- **RAM:** 4 GB
- **Disk:** 20 GB SSD
- **Tarmoq:** Static IP, domen nomi

### Tavsiya etilgan:
- **CPU:** 4 core
- **RAM:** 8 GB
- **Disk:** 50 GB SSD

---

## 2. Server Sotib Olish (Variantlar)

| Provayder | Narx (oyiga) | Havola |
|-----------|-------------|--------|
| **DigitalOcean** | $24 | digitalocean.com |
| **Hetzner** | €10 | hetzner.com |
| **AWS Lightsail** | $10 | aws.amazon.com |
| **Linode** | $24 | linode.com |
| **Yandex Cloud** | 1500₽ | cloud.yandex.ru |

---

## 3. Domen va SSL

### Domen sotib olish:
```
your-domain.com
app.your-domain.com
api.your-domain.com
```

### SSL sertifikat (bepul — Let's Encrypt):
```bash
sudo apt install certbot
sudo certbot certonly --standalone -d your-domain.com -d api.your-domain.com
```

Sertifikatlar saqlanadi:
```
/etc/letsencrypt/live/your-domain.com/fullchain.pem
/etc/letsencrypt/live/your-domain.com/privkey.pem
```

---

## 4. Server Sozlash (Ubuntu)

### 4.1 Tizimni yangilash
```bash
sudo apt update && sudo apt upgrade -y
```

### 4.2 Docker o'rnatish
```bash
# Docker
sudo apt install apt-transport-https ca-certificates curl gnupg lsb-release -y
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-compose-plugin -y

# Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 4.3 Git o'rnatish va loyihani klonlash
```bash
sudo apt install git -y
git clone https://github.com/your-username/salesdoctor-moysklad-integration.git
cd salesdoctor-moysklad-integration
```

---

## 5. Loyihani Sozlash

### 5.1 .env faylini yaratish
```bash
cp backend/.env.example backend/.env
nano backend/.env
```

Muhim o'zgaruvchilar:
```env
APP_SECRET_KEY=your-very-secure-random-key-32-chars-min
DEBUG=false
CORS_ORIGINS=https://your-domain.com

DATABASE_URL=postgresql+asyncpg://integration_user:strong_password@db:5432/integration
REDIS_URL=redis://redis:6379/0

PUBLIC_BASE_URL=https://api.your-domain.com

# MoySklad permanent access token har bir tenant Sozlamalarda joylashtiriladi —
# bu yerda hech narsa yozish kerakmas.

# Payment providers
PAYME_MERCHANT_ID=your-payme-id
PAYME_SECRET_KEY=your-payme-secret
```

### 5.2 SSL sertifikatlarini nusxalash
```bash
sudo mkdir -p ssl
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem ssl/cert.pem
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem ssl/key.pem
sudo chmod 644 ssl/*.pem
```

### 5.3 nginx.conf'da domenni yangilash
```bash
nano nginx.conf
```

`your-domain.com` ni o'zingizning domeningiz bilan almashtiring.

---

## 6. Docker Compose Bilan Ishga Tushirish

### 6.1 Barcha servislarni ishga tushirish
```bash
docker-compose up -d --build
```

### 6.2 Ma'lumotlar bazasini ishga tushirish
```bash
# PostgreSQL container ishga tushgach, jadvallarni yaratish
docker-compose exec backend python -c "
import asyncio
from database import init_db
asyncio.run(init_db())
"
```

### 6.3 Demo ma'lumotlarni yuklash (ixtiyoriy)
```bash
docker-compose exec backend python seed.py
```

### 6.4 Statusni tekshirish
```bash
docker-compose ps
docker-compose logs -f backend
docker-compose logs -f nginx
```

---

## 7. Yangilash (Update)

### 7.1 Kodni yangilash
```bash
git pull origin main
docker-compose up -d --build
```

### 7.2 Ma'lumotlar bazasini migratsiya qilish
```bash
docker-compose exec backend python -c "
import asyncio
from database import init_db
asyncio.run(init_db())
"
```

---

## 8. Monitoring

### 8.1 Loglarni ko'rish
```bash
# Backend loglari
docker-compose logs -f --tail=100 backend

# Barcha loglar
docker-compose logs -f
```

### 8.2 Resurslarni kuzatish
```bash
# CPU, RAM
docker stats

# Disk
sudo df -h
```

### 8.3 Sentry (ixtiyoriy)
Sentry o'rnatish uchun:
```bash
pip install sentry-sdk
```

`backend/main.py` ga qo'shish:
```python
import sentry_sdk
sentry_sdk.init(
    dsn="your-sentry-dsn",
    traces_sample_rate=1.0,
)
```

---

## 9. Backup

### 9.1 Ma'lumotlar bazasini zaxiralash
```bash
# Avtomat backup (har kuni)
docker-compose exec db pg_dump -U integration_user integration > backup_$(date +%Y%m%d).sql

# Yoki cron orqali
0 2 * * * cd /path/to/project && docker-compose exec -T db pg_dump -U integration_user integration > backups/backup_$(date +\%Y\%m\%d).sql
```

### 9.2 Zaxirani tiklash
```bash
docker-compose exec -T db psql -U integration_user integration < backup_20240115.sql
```

---

## 10. Xavfsizlik

### 10.1 Firewall
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### 10.2 Fail2ban
```bash
sudo apt install fail2ban -y
sudo systemctl enable fail2ban
```

### 10.3 SSL avtomat yangilash
```bash
# Certbot avto-yangilash
sudo certbot renew --dry-run

# Cron orqali
0 12 * * * /usr/bin/certbot renew --quiet
```

---

## 11. Tekshirish

### 11.1 Health check
```bash
curl https://api.your-domain.com/health
```

Javob:
```json
{"status": "healthy", "timestamp": "2024-01-15T10:00:00"}
```

### 11.2 API Docs
```
https://api.your-domain.com/docs
```

### 11.3 Frontend
```
https://your-domain.com
```

---

## 12. Muammolar va Yechimlar

| Muammo | Sabab | Yechim |
|--------|-------|--------|
| `502 Bad Gateway` | Backend ishlamayapti | `docker-compose restart backend` |
| `Connection refused` | Port yopiq | Firewall tekshirish |
| `SSL error` | Sertifikat eskirgan | `sudo certbot renew` |
| `Database locked` | SQLite muammosi | PostgreSQL ga o'tish |
| `Memory error` | RAM yetishmayapti | Swap yaratish yoki server yangilash |

---

## 13. Aloqa

Agar muammolar bo'lsa:
- Telegram: @your_support
- Email: support@your-domain.com
- GitHub Issues: github.com/your-username/project/issues
