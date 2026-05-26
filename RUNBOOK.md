# Mijozga topshirish va Deploy Runbook

Bu fayl loyihani **birinchi marta production'ga olib chiqish** uchun.
Har bir qadam alohida ishlatiladi, oraliq xatolar bo'lsa shu yerga qayting.

---

## 1. Production'ga deploy oldidan tekshiruv

```bash
# Backend syntax tekshiruvi
python3 -c "import ast; [ast.parse(open(f).read()) for f in ['backend/main.py','backend/models.py','backend/database.py','backend/services/sync.py','backend/services/salesdoctor.py','backend/services/moysklad.py','backend/routers/orders.py','backend/routers/auth.py','backend/routers/webhooks.py']]"

# Frontend build
npx vite build
```

Ikkalasi ham xatosiz o'tishi kerak.

---

## 2. Production DB backup (MAJBURIY)

Migratsiyalar dublikatlarni o'chiradi (Order'lar moysklad_id bo'yicha). Backup'siz yangilanmang.

**PostgreSQL:**
```bash
pg_dump -h <db-host> -U integration_user integration > backup_$(date +%Y%m%d_%H%M%S).sql
```

**SQLite:**
```bash
cp /path/to/integration.db /path/to/backup_$(date +%Y%m%d_%H%M%S).db
```

Backup faylini xavfsiz joyda saqlang. Migratsiya muvaffaqiyatsiz bo'lsa, shundan qaytariladi.

---

## 3. Environment variables

`backend/.env.example` ga qarang. Production'da quyidagilar **majburiy**:

```env
APP_SECRET_KEY=<kamida 32 belgili tasodifiy satr — turg'un bo'lishi shart>
DATABASE_URL=postgresql+asyncpg://integration_user:STRONG_PWD@db:5432/integration
REDIS_URL=redis://redis:6379/0
PUBLIC_BASE_URL=https://app.pipely.uz
CORS_ORIGINS=https://app.pipely.uz
DEBUG=false
```

**MUHIM:** `APP_SECRET_KEY` o'zgarsa, DB'da saqlangan SalesDoctor parollari ochilmaydi.
Operator parolni Settings panelidan qayta kiritishi kerak. Bir marta o'rnatib, abadiy saqlang.

Ixtiyoriy:
- `SD_VERIFY_SSL=true` — Sales Doctor sertifikati to'g'rilangan bo'lsa
- `SYNC_STALE_AFTER_MINUTES=10` — `/api/health` qancha vaqtdan keyin "stale" deb belgilashi (default 10)
- `MOYSKLAD_TOKEN` — dev/test uchun global token. Prod'da har tenant o'z tokenini Settings'da joylashtiradi.

---

## 4. Deploy (Docker Compose)

```bash
git pull origin main
docker compose -f docker-compose.dokploy.yml down
docker compose -f docker-compose.dokploy.yml up -d --build
```

Birinchi marta ishga tushganda `database._patch_schema()` avtomatik:
- `tenants` jadvaliga yangi ustunlarni qo'shadi (`salesdoctor_token_obtained_at`, `last_successful_sync_at`)
- `orders` jadvalidan `(tenant_id, moysklad_id)` dublikatlarini o'chiradi (eng yangisi qoladi)
- `orders` ga unique index qo'yadi

---

## 5. Deploy sog'lig'ini tekshirish

```bash
# Server ishga tushdimi?
curl -fsS https://app.pipely.uz/api/health | jq

# Kutilgan javob:
# {
#   "status": "healthy",   // yoki "degraded" agar tenant sinxron stale bo'lsa
#   "services": { "api": "ok", "database": "ok" },
#   "tenants": { "active": 1, "fully_connected": 1, "stale_count": 0, ... }
# }
```

Agar `stale_count > 0` bo'lsa, sinxron 10 daqiqadan beri tushmagan — Logs panelida muammoni qidiring.

---

## 6. Tenant onboarding

1. Browser'da `https://app.pipely.uz` ochish
2. Email/parol bilan ro'yxatdan o'tish
3. **Sozlamalar** > **MoySklad** > Permanent token joylashtirish
   - MoySklad'da: Sozlamalar > Доступ к API > Создать токен
   - Token avtomatik validatsiya qilinadi va webhook'lar ro'yxatdan o'tadi
4. **Sozlamalar** > **Sales Doctor** > Login/parol + base URL kiritish
5. Dashboard'da today/yesterday raqamlari ko'rinishi kerak

---

## 7. Birinchi sutka monitoring

Birinchi 24 soat davomida har 4 soatda tekshirish:

```bash
curl -s https://app.pipely.uz/api/health | jq '.tenants'
```

Va Logs panelida ERROR yo'qligini.

---

## 8. Backup strategiyasi (mijoz uchun)

Mijozga aytib qo'ying:
- **Har kuni** DB backup oling (cron'da)
- **Haftada bir marta** `APP_SECRET_KEY` backup'i ham bor ekanligini tekshiring
- Restore qilishni **kvartalda** test qiling

Cron misol (PostgreSQL):
```cron
0 3 * * * pg_dump -h db -U integration_user integration | gzip > /backups/integration_$(date +\%Y\%m\%d).sql.gz
0 4 * * 0 find /backups -name 'integration_*.sql.gz' -mtime +30 -delete
```

---

## 9. Yangi versiya chiqarganda

```bash
# DB backup
pg_dump ... > backup.sql

# Pull va restart
git pull
docker compose -f docker-compose.dokploy.yml up -d --build

# Health tekshirish
curl https://app.pipely.uz/api/health
```

`_patch_schema()` har deploy'da idempotent — agar ustun mavjud bo'lsa, qo'shilmaydi. Xavfsiz.

---

## 10. Rollback (deploy noto'g'ri bo'lsa)

```bash
# Backup'ni qayta tiklash
psql -h db -U integration_user integration < backup.sql

# Oldingi versiyani qaytarish
git reset --hard <oldingi-commit>
docker compose -f docker-compose.dokploy.yml up -d --build
```

---

## 11. Tushunarsiz holatlar

| Belgi | Sabab | Yechim |
|-------|-------|--------|
| Health: `stale_count > 0` | Tenant sinxroni 10 daq'dan ko'p turibdi | Logs panelida ERROR'ni qidiring |
| Tenant MS ulanmagan | Permanent token bekor qilingan | Sozlamalar'dan yangi token joylashtirish |
| SD `401`/auth error | Login/parol o'zgargan | Sozlamalar > Sales Doctor'dan qayta ulash |
| Order'lar kelmayapti, log'da xato yo'q | Webhook'lar o'chgan | Sozlamalar > Webhook > "Qayta ro'yxatdan o'tkazish" |
| Valyuta kursi `12695` qotib qolgan | UZEX/CBR uzilgan | Log'da ERROR bo'ladi; `usd_to_uzs_rate` env'ni yangilang |
