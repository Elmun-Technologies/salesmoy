# Sales Doctor ↔ MoySklad Integration

**Ko'p-ijarachilik (multi-tenant) SaaS platformasi** — [MoySklad](https://moysklad.ru) va [Sales Doctor](https://salesdoctor.uz) o'rtasida real-vaqt sinxronizatsiyasi. Har bir kompaniya bir marta ro'yxatdan o'tadi, o'z API akkauntlarini ulaydi va to'liq ajratilgan ma'lumot pipeliniga ega bo'ladi — zakazlar, sklad, klientlar, qarzlar va dostavkalar ikki tizim o'rtasida avtomatik ravishda oqib turadi.

---

## Mundarija

- [Umumiy ko'rinish](#umumiy-ko'rinish)
- [Arxitektura](#arxitektura)
- [Texnologiyalar](#texnologiyalar)
- [Imkoniyatlar](#imkoniyatlar)
- [Ma'lumot oqimi](#ma'lumot-oqimi)
- [Loyiha tuzilmasi](#loyiha-tuzilmasi)
- [Lokal ishga tushirish](#lokal-ishga-tushirish)
- [Environment o'zgaruvchilari](#environment-o'zgaruvchilari)
- [API endpointlar](#api-endpointlar)
- [Yangi tenant onboarding](#yangi-tenant-onboarding)
- [Fon sinxronizatsiya jadvali](#fon-sinxronizatsiya-jadvali)
- [Webhook oqimi](#webhook-oqimi)
- [Docker bilan deploy](#docker-bilan-deploy)
- [Ma'lumotlar bazasi sxemasi](#ma'lumotlar-bazasi-sxemasi)

---

## Umumiy ko'rinish

```
MoySklad (CRM/ERP)  ←──────────────────────→  Sales Doctor (Dala Savdosi)
  Zakazlar / Yuk xatlar                          Zakazlar / Klientlar
  Kontragentlar                                  Agentlar / Sklad
  Sklad / Narxlar
                      ┌──────────────────┐
                      │   Ushbu Backend  │
                      │  FastAPI + PG    │
                      │  4 uvicorn wkr   │
                      └──────────────────┘
                              ▲
                      React SPA Dashboard
```

Menejer **MoySklad** da zakaz yaratganda, u avtomatik ravishda **Sales Doctor** da to'g'ri sklad, narx turi, klient va mahsulot kodlari bilan paydo bo'ladi — va aksincha. Sklad qoldiqlari, klient qarzlari va dostavka statuslari ikkala platformada bir xil bo'lib turadi.

---

## Arxitektura

| Qatlam | Texnologiya |
|---|---|
| API Server | FastAPI 0.109, uvicorn 4 ta worker |
| Ma'lumotlar bazasi | PostgreSQL 15 (lokal dev uchun SQLite) |
| Kesh / Navbat | Redis 7 |
| Fon sinxroni | `asyncio` sikllar + `fcntl.flock` lider tanlash |
| Real-vaqt eventlar | MoySklad webhooklari → `/api/webhook/moysklad` |
| Autentifikatsiya | JWT (HS256, 7 kunlik tokenlar) + MoySklad OAuth2 |
| Multi-tenancy | Satr darajasida izolyatsiya (har bir jadvalda `tenant_id`) |
| Frontend | React 19, Vite, Tailwind CSS 4, Recharts |
| Reverse Proxy | Nginx + Traefik (Let's Encrypt TLS) |
| Container | Docker + Docker Compose |

### Lider Worker Tanlash

4 ta uvicorn worker = 4 ta process ishlaydi. Fon sinxronizatsiya tasklari (sklad, qarzlar, klientlar, zakazlar) **faqat bir marta** ishga tushishi kerak — 4 tasi emas. `/tmp/salesmoy_sync_leader.lock` faylida blokirovkasiz `fcntl.flock` orqali aynan bir worker lock oladi va barcha fon sikllarni boshlaydi. U process o'lsa, keyingi restart avtomatik lock oladi.

---

## Texnologiyalar

### Backend
- **FastAPI** — asinxron REST API
- **SQLAlchemy 2.0** — to'liq multi-tenant satr izolyatsiyasi bilan async ORM
- **asyncpg** — PostgreSQL async drayver
- **httpx** — MoySklad va Sales Doctor API lari uchun async HTTP client
- **tenacity** — barcha API chaqiruvlarida qayta urinish (3 ta urinish, eksponensial kutish)
- **passlib + bcrypt** — parol hashlash
- **PyJWT** — kirish tokenlari va OAuth state tokenlari
- **pydantic-settings** — `.env` dan type-safe konfiguratsiya

### Frontend
- **React 19** TypeScript bilan
- **Vite 7** (`vite-plugin-singlefile` orqali bitta fayl build)
- **Tailwind CSS 4**
- **Recharts** — dashboard grafiklar
- **Framer Motion** — UI animatsiyalar
- **Lucide React** — ikonlar

---

## Imkoniyatlar

### Asosiy Sinxronizatsiya
- **Zakazlar** — MoySklad → Sales Doctor real-vaqtda (webhook) + 5 daqiqalik polling fallback
- **Zakazlar** — Sales Doctor → MoySklad (teskari sinxron)
- **Sklad** — MoySklad sklad qoldiqlari → Sales Doctor har 60 sekundda
- **Klientlar / Kontragentlar** — ikki tomonlama sinxron har 5 daqiqada
- **Qarzlar** — MoySklad kontragent qarz hisobotlari → Sales Doctor har 10 daqiqada
- **Dostavkalar** — MoySklad da yuk xati (отгрузка) yaratilsa Sales Doctor da status yangilanadi

### Ishonchlilik
- **PENDING zakazlarni qayta urinish** — SD mavjud bo'lmaganda zakaz kelgan bo'lsa, keyingi sinxron siklida qayta uriniladi
- **Idempotent webhooklar** — takroriy eventlar xavfsiz e'tiborga olinmaydi
- **Xatoda qayta urinish** — barcha API chaqiruvlari eksponensial kutish bilan 3 martaga qadar qayta urinadi
- **Session rollback xavfsizligi** — xato yozilishidan oldin DB session rollback qilinadi, SQLAlchemy holati buzilmaydi

### Multi-Tenancy
- Har bir tenant to'liq ajratilgan ma'lumotlarga ega — cross-tenant ma'lumot sızıntısı yo'q
- Har bir tenant uchun alohida MoySklad OAuth tokeni, Sales Doctor credential va filial ID
- `moysklad_account_id` bo'yicha webhook marshrutlash — har bir tenant eventlari faqat o'z pipeliniga boradi
- **Webhooklarni avtomatik ro'yxatdan o'tkazish** — tenant MoySklad ni ulashida webhooklar avtomatik ro'yxatdan o'tadi

### Dashboard (React SPA)
- **Zakazlar paneli** — status, sinxron holati, klient, summa
- **Sklad paneli** — MoySklad dan real-vaqt qoldiqlar
- **Klientlar paneli** — ikki tizimdan birlashtirgan ko'rinish
- **Qarzlar paneli** — klient bo'yicha qoldiq qarzlar
- **Dostavka paneli** — jo'natmalarni kuzatish
- **Agentlar paneli** — dala savdo agentlari ro'yxati
- **Loglar paneli** — vaqt tamg'alari bilan to'liq sinxron faoliyat logi
- **Sozlamalar paneli** — MoySklad va Sales Doctor ni ulash

---

## Ma'lumot Oqimi

### Yangi Zakaz: MoySklad → Sales Doctor

```
1. Menejer MoySklad da zakaz yaratadi
2. MoySklad POST /api/webhook/moysklad ga yuboradi
3. Backend accountId bo'yicha eventni marshrutlaydi → tenant topiladi
4. Pozitsiyalar kengaytirilgan holda to'liq zakaz olinadi (agent, holat, mahsulotlar)
5. Telefon bo'yicha klient topiladi → topilmasa yangi yaratiladi
6. Mahsulot kodlari moslashtiriladi (MS kodi → SD code_1C)
7. SD setOrder payloadi quriladi: sklad, narx turi, klient, agent, mahsulotlar
8. SD setOrder API chaqiriladi
9. Zakaz DB ga sync_status=SYNCED bilan saqlanadi
10. Muvaffaqiyat logi yoziladi
```

Agar 8-qadamda SD mavjud bo'lmasa, zakaz `sync_status=PENDING` bilan saqlanadi va keyingi 5 daqiqalik polling siklida qayta uriniladi.

### Sklad Sinxroni

```
MoySklad /report/stock/all (sahifalangan, barcha satrlar)
    → Moslashtiradi: nom, SKU, miqdor, narx, sklad
    → DB dagi StockItem ni upsert qiladi (tenant_id + sku bo'yicha)
    → Sales Doctor ga yuboradi (ulangan bo'lsa)
Har 60 sekundda har bir tenant uchun
```

### Yuk Xati → Dostavka Statusi

```
1. Ombor xodimi MoySklad da yuk xati (отгрузка) yaratadi
2. MoySklad demand.CREATE webhook yuboradi
3. Backend yuk xatini customerOrder kengaytirish bilan oladi
4. Bog'liq zakaz topiladi
5. Zakaz statusi "Отгружен" ga yangilanadi — DB va Sales Doctor da ham
```

---

## Loyiha Tuzilmasi

```
├── backend/
│   ├── main.py                  # FastAPI ilovasi, lifespan, fon sikllar
│   ├── config.py                # Sozlamalar (pydantic-settings, .env)
│   ├── database.py              # SQLAlchemy engine + session factory
│   ├── models.py                # Barcha DB modellari (Tenant, Order, Client ...)
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── .env.example
│   ├── routers/
│   │   ├── auth.py              # Ro'yxatdan o'tish, login, MoySklad OAuth, SD ulash
│   │   ├── orders.py            # Zakaz CRUD + status yangilash
│   │   ├── stock.py             # Sklad qoldiqlari API
│   │   ├── clients.py           # Klient boshqaruvi
│   │   ├── debts.py             # Qarz hisobotlari
│   │   ├── delivery.py          # Dostavka kuzatish
│   │   ├── agents.py            # Savdo agentlari
│   │   ├── logs.py              # Sinxron faoliyat loglari
│   │   ├── webhooks.py          # MoySklad va SD webhook qabul qiluvchi + boshqaruv
│   │   └── billing.py           # (disabled)
│   ├── services/
│   │   ├── sync.py              # SyncService — barcha sinxron logikasi
│   │   ├── moysklad.py          # MoySkladClient (httpx + tenacity)
│   │   ├── salesdoctor.py       # SalesDoctorClient (JSON-RPC + tenacity)
│   │   └── moysklad_oauth.py    # OAuth2 token almashinuvi
│   ├── security/
│   │   └── jwt_tokens.py        # Kirish + OAuth state tokenlarini yaratish/dekod
│   └── middleware/
│       └── tenant.py            # JWT → request.state.tenant_id
├── src/                         # React frontend
│   ├── App.tsx
│   ├── components/              # Dashboard panellari
│   └── services/
│       └── api.ts               # Type-safe API klient
├── docker-compose.yml           # PostgreSQL + Redis + Backend + Frontend + Nginx
├── nginx.conf                   # Reverse proxy konfiguratsiyasi
├── vite.config.ts
└── package.json
```

---

## Lokal Ishga Tushirish

### Talablar
- Python 3.11+
- Node.js 20+
- (Ixtiyoriy) PostgreSQL — lokal dev uchun SQLite ishlaydi

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env              # o'z ma'lumotlaringiz bilan to'ldiring
python -c "import asyncio; from database import init_db; asyncio.run(init_db())"

uvicorn main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### Frontend

```bash
# loyiha ildizidan
npm install
npm run dev
```

UI: http://localhost:5173

---

## Environment O'zgaruvchilari

`backend/.env.example` ni `backend/.env` ga ko'chiring va to'ldiring:

| O'zgaruvchi | Kerakmi | Tavsif |
|---|---|---|
| `APP_SECRET_KEY` | ✅ | JWT imzolash kaliti — minimum 32 belgi, hech kimga bermang |
| `DATABASE_URL` | ✅ | `sqlite+aiosqlite:///./integration.db` (dev) yoki `postgresql+asyncpg://...` (prod) |
| `REDIS_URL` | ✅ | `redis://localhost:6379/0` |
| `PUBLIC_BASE_URL` | ✅ prod | Ushbu serverning HTTPS URL — MoySklad webhooklarini avtomatik ro'yxatdan o'tkazish uchun |
| `FRONTEND_BASE_URL` | ✅ | OAuth dan so'ng foydalanuvchi shu yerga yo'naltiriladi |
| `CORS_ORIGINS` | ✅ | Vergul bilan ajratilgan ruxsat etilgan originlar |
| `MOYSKLAD_CLIENT_ID` | Faqat OAuth | MoySklad Marketplace ilova Client ID |
| `MOYSKLAD_CLIENT_SECRET` | Faqat OAuth | MoySklad Marketplace ilova Client Secret |
| `MOYSKLAD_REDIRECT_URI` | Faqat OAuth | MoySklad developer konsolindagi sozlamalar bilan mos kelishi kerak |
| `MOYSKLAD_TOKEN` | Faqat dev | Ishlab chiqish/test uchun global token |
| `MOYSKLAD_BASE_URL` | | Standart: `https://api.moysklad.ru/api/remap/1.2` |
| `STOCK_SYNC_INTERVAL` | | Sklad sinxronlari orasidagi soniyalar. Standart: `60` |
| `DEBT_SYNC_INTERVAL` | | Qarz sinxronlari orasidagi soniyalar. Standart: `600` |
| `CLIENT_SYNC_INTERVAL` | | Klient sinxronlari orasidagi soniyalar. Standart: `300` |
| `ORDER_SYNC_INTERVAL` | | Buyurtma sinxronlari orasidagi soniyalar. Standart: `60` |
| `INITIAL_ORDER_LOOKBACK_DAYS` | | Dastlabki buyurtma sinxronida nechta kun orqaga qarash. Standart: `1` (webhook'lar real-time ishlaydi, bu xavfsizlik tarmog'i) |
| `FORCE_PRICE_CURRENCY` | | `USD` — MoySklad isoCode'ni e'tiborga olmasdan barcha narxlarni USD deb hisoblash |
| `DEBUG` | | `true` — hot reload va batafsil logging yoqiladi |
| `TEST_MODE` | | `true` — barcha fon sinxron tasklari o'chiriladi |

> **Sales Doctor credential lari** bazada har bir tenant uchun alohida saqlanadi (`.env` da emas) va har bir tenant `POST /api/auth/connect/salesdoctor` chaqirganda o'rnatiladi.

---

## API Endpointlar

### Autentifikatsiya

| Metod | Endpoint | Tavsif |
|---|---|---|
| `POST` | `/api/auth/register` | Yangi kompaniya ro'yxatdan o'tkazish — tenant + admin yaratadi |
| `POST` | `/api/auth/login` | Email/parol bilan kirish → JWT |
| `GET` | `/api/auth/me` | Joriy tenant ma'lumotlari |
| `GET` | `/api/auth/moysklad/authorize-url` | MoySklad OAuth URL ni olish (Marketplace) |
| `GET` | `/api/auth/moysklad/callback` | OAuth callback — token saqlaydi + webhooklarni avtomatik ro'yxatdan o'tkazadi |
| `POST` | `/api/auth/connect/moysklad` | Token qo'lda kiritish — saqlaydi + webhooklarni avtomatik ro'yxatdan o'tkazadi |
| `POST` | `/api/auth/connect/salesdoctor` | Sales Doctor ni login/parol bilan ulash |

### Zakazlar

| Metod | Endpoint | Tavsif |
|---|---|---|
| `GET` | `/api/orders` | Zakazlar ro'yxati (sahifalangan, status bo'yicha filter) |
| `GET` | `/api/orders/{id}` | Bitta zakaz ma'lumotlari |
| `POST` | `/api/orders/{id}/sync` | Bitta zakaz uchun sinxronni qo'lda ishga tushirish |
| `PATCH` | `/api/orders/{id}/status` | Zakaz statusini yangilash |

### Sklad

| Metod | Endpoint | Tavsif |
|---|---|---|
| `GET` | `/api/stock` | Tenant uchun barcha sklad elementlari |
| `POST` | `/api/stock/sync` | MoySklad dan darhol sklad sinxronini ishga tushirish |

### Klientlar

| Metod | Endpoint | Tavsif |
|---|---|---|
| `GET` | `/api/clients` | Klientlar ro'yxati |
| `POST` | `/api/clients` | Klient yaratish |
| `PUT` | `/api/clients/{id}` | Klientni yangilash |
| `DELETE` | `/api/clients/{id}` | Klientni deaktivlash |

### Qarzlar

| Metod | Endpoint | Tavsif |
|---|---|---|
| `GET` | `/api/debts` | Barcha qarz yozuvlari |
| `POST` | `/api/debts/sync` | MoySklad dan qarz sinxronini ishga tushirish |

### Dostavka

| Metod | Endpoint | Tavsif |
|---|---|---|
| `GET` | `/api/delivery` | Barcha dostavkalar |
| `PATCH` | `/api/delivery/{id}/status` | Dostavka statusini yangilash |

### Loglar

| Metod | Endpoint | Tavsif |
|---|---|---|
| `GET` | `/api/logs` | Sinxron faoliyat logi (yangilari avval) |
| `DELETE` | `/api/logs` | Tenant uchun loglarni tozalash |

### Webhooklar (ochiq — autentifikatsiyasiz)

| Metod | Endpoint | Tavsif |
|---|---|---|
| `POST` | `/api/webhook/moysklad` | MoySklad eventlarini qabul qiladi (accountId bo'yicha marshrutlash) |
| `POST` | `/api/webhook/salesdoctor` | Sales Doctor eventlarini qabul qiladi |

### Webhook Boshqaruvi (autentifikatsiya talab etiladi)

| Metod | Endpoint | Tavsif |
|---|---|---|
| `GET` | `/api/integrations/moysklad/webhook/status` | Ro'yxatdan o'tgan webhooklarni ko'rish |
| `POST` | `/api/integrations/moysklad/webhook/register` | Webhooklarni ro'yxatdan o'tkazish/yangilash |
| `DELETE` | `/api/integrations/moysklad/webhook/unregister` | Barcha webhooklarni o'chirish |

### Health

| Metod | Endpoint | Tavsif |
|---|---|---|
| `GET` | `/health` yoki `/api/health` | Server ishlayaptimi tekshirish |

---

## Yangi Tenant Onboarding

Yangi mijoz 3 qadamda o'zi ro'yxatdan o'tadi — admin aralashuvi shart emas:

```
1-qadam — Ro'yxatdan o'tish
POST /api/auth/register
{
  "company_name": "Mening Kompaniyam LLC",
  "slug": "mening-kompaniyam",
  "email": "admin@mening-kompaniyam.uz",
  "password": "xavfsiz-parol",
  "full_name": "Ism Familiya"
}
→ JWT access_token qaytaradi
→ 14 kunlik bepul sinov avtomatik boshlanadi

2-qadam — MoySklad ulash
A variant (OAuth): GET /api/auth/moysklad/authorize-url
  → URL ni brauzerda oching → foydalanuvchi tasdiqlaydi
  → callback webhooklarni avtomatik ro'yxatdan o'tkazadi

B variant (Token): POST /api/auth/connect/moysklad
  { "access_token": "Bearer ms-tokeningiz" }
  → Webhooklar darhol ro'yxatdan o'tadi

3-qadam — Sales Doctor ulash
POST /api/auth/connect/salesdoctor
{
  "login": "sd-login",
  "password": "sd-parol",
  "base_url": "https://sizning-sd-server/api/v2/",
  "filial_id": 1
}
→ Tayyor. Real-vaqt sinxron ishlaydi.
```

2-qadamdan so'ng backend avtomatik ravishda:
1. `moysklad_account_id` ni oladi va saqlaydi (webhook marshrutlash uchun kerak)
2. 5 ta webhook ro'yxatdan o'tkazadi: `customerorder` CREATE/UPDATE, `counterparty` CREATE/UPDATE, `demand` CREATE

---

## Fon Sinxronizatsiya Jadvali

| Sikl | Interval | Nima qiladi |
|---|---|---|
| Sklad Sinxroni | 60 s | MoySklad dan barcha sklad ma'lumotlarini tortib SD ga yuboradi |
| Zakaz Sinxroni | 60 s | MS dan yangi zakazlarni tortadi (`INITIAL_ORDER_LOOKBACK_DAYS` orqaga, standart 1 kun) → SD ga yuboradi; PENDING zakazlarni qayta urinib ko'radi. Real-time uchun webhook ishlatiladi |
| Klient Sinxroni | 300 s (5 min) | Ikki tomonlama klient/kontragent sinxroni |
| Qarz Sinxroni | 600 s (10 min) | Klient bo'yicha MoySklad dan qarz hisobotlarini tortadi |

Barcha sikllar **faqat lider workerda** ishlaydi (`fcntl.flock` orqali). Qolgan 3 ta worker faqat HTTP so'rovlarini qabul qiladi.

---

## Webhook Oqimi

MoySklad webhook eventlari `accountId` bo'yicha marshrutlanadi:

```
MoySklad
    │  POST /api/webhook/moysklad
    │  { "accountId": "abc123", "events": [...] }
    ▼
Backend: SELECT tenant WHERE moysklad_account_id = 'abc123'
    │
    ├─ customerorder.CREATE  → process_moysklad_order()
    │                           → DB ga saqlaydi + Sales Doctor ga yuboradi
    │
    ├─ customerorder.UPDATE  → holat o'zgardimi?
    │   (updatedFields: state)  → update_order_status_from_moysklad()
    │
    ├─ counterparty.CREATE/UPDATE → klientni DB ga va SD ga sinxronlaydi
    │
    └─ demand.CREATE         → bog'liq customerOrder ni topadi
                               → MS + SD da "Отгружен" statusini o'rnatadi
```

---

## Docker bilan Deploy

### 1. Klonlash va sozlash

```bash
git clone https://github.com/Elmun-Technologies/salesmoy.git
cd salesmoy
cp backend/.env.example backend/.env
# backend/.env ni production qiymatlari bilan tahrirlang
```

### 2. Production uchun majburiy `.env` qiymatlari

```env
APP_SECRET_KEY=<tasodifiy-64-belgili-satr>
DATABASE_URL=postgresql+asyncpg://integration_user:PAROL@db:5432/integration
DB_PASSWORD=<kuchli-db-paroli>
REDIS_URL=redis://redis:6379/0
PUBLIC_BASE_URL=https://app.pipely.uz
FRONTEND_BASE_URL=https://app.pipely.uz
CORS_ORIGINS=https://app.pipely.uz
MOYSKLAD_CLIENT_ID=<ms-ilova-client-id>
MOYSKLAD_CLIENT_SECRET=<ms-ilova-client-secret>
MOYSKLAD_REDIRECT_URI=https://app.pipely.uz/api/auth/moysklad/callback
DEBUG=false
```

### 3. Build va ishga tushirish

```bash
docker compose up -d --build
```

Ishga tushadigan servislar:
- `integration_db` — PostgreSQL 15
- `integration_redis` — Redis 7
- `integration_backend` — FastAPI (4 ta worker, ichki port 8000)
- `integration_frontend` — React SPA (statik fayllar)
- `integration_nginx` — Nginx reverse proxy (port 8080 + Traefik labellar)

### 4. Traefik TLS

Nginx konteynerida Traefik uchun Let's Encrypt sertifikat avtomatik olish labellari mavjud. Traefik `dokploy-network` tashqi tarmog'ida ishlayotgan va `letsencrypt` sertifikat resolver sozlangiga ishonch hosil qiling.

### 5. Health tekshirish

```bash
curl https://app.pipely.uz/health
# {"status":"healthy","timestamp":"..."}
```

---

## Ma'lumotlar Bazasi Sxemasi

```
tenants          — kompaniya akkauntlari (slug, reja, MS/SD tokenlari, accountId)
users            — har bir tenant uchun admin/menejer/agent akkauntlari
orders           — sinxronlangan zakazlar (moysklad_id, salesdoctor_id, sync_status)
clients          — ikki tizimdan klientlar
stock_items      — sklad bo'yicha joriy qoldiqlar
debt_records     — klient qarz balanslari
deliveries       — jo'natmalarni kuzatish
sync_logs        — barcha sinxron operatsiyalarning to'liq audit izi
webhook_events   — xom webhook payloadlari (debugging va replay uchun)
```

Barcha jadvallar to'liq satr darajasida ma'lumot izolyatsiyasi uchun `tenant_id` FK ni o'z ichiga oladi.

**Sinxron holat qiymatlari** (`orders.sync_status`):
- `pending` — DB ga saqlangan, Sales Doctor ga hali yuborilmagan
- `synced` — ikki tizimga ham muvaffaqiyatli yuborilgan
- `error` — qayta urinishlardan keyin push muvaffaqiyatsiz bo'lgan (`sync_logs` ga qarang)

---

## Biznes Qoidalari

| Holat | Xatti-harakat |
|---|---|
| SD mavjud emas — zakaz keldi | `sync_status=PENDING` bilan saqlanadi, keyingi siklda qayta uriniladi |
| Sklad yetarli emas (SD) | SD setOrder rad etadi, log yoziladi, `sync_status=ERROR` |
| Klient topilmadi | Telefon bo'yicha yangi klient yaratiladi, keyin zakaz yuboriladi |
| API xatosi | 3 martagacha eksponensial kutish bilan qayta uriniladi (2s → 4s → 10s) |
| Webhook bo'sh accountId | E'tiborga olinmaydi, log yoziladi |
| Noma'lum accountId | E'tiborga olinmaydi (boshqa kompaniyaning webhooks) |

---

## Litsenziya

Proprietary — © 2025 Elmun Technologies. Barcha huquqlar himoyalangan.
