# Sales Doctor ↔ MoySklad Integration

MoySklad va Sales Doctor o'rtasidagi avtomatik sinxronizatsiya tizimi.

---

## Qanday ishlaydi

```
MoySklad                    Integration               Sales Doctor
─────────                   ───────────               ────────────
Zakaz yaratildi   ──────►   Webhook qabul qiladi  ──► Zakaz ko'rinadi
                            Formatlab yuboradi        Agent telefonda ko'radi

Sklad qoldig'i    ──────►   Har 15 sek sync       ──► Agent qoldig'ni ko'radi

To'lov tushdi     ──────►   Qarz hisoblaydi       ──► Klientning qarzi ko'rinadi

Status o'zgardi   ──────►   SD ga yuboradi        ──► Agent yangi status ko'radi
```

---

## Imkoniyatlar

| Funksiya | Tavsif |
|---|---|
| **Zakaz sinxroni** | MoySklad zakazlari SD ga avtomatik tushadi |
| **Real-time webhook** | MoySklad zakaz yaratganda darhol SD ga yuboriladi |
| **Sklad qoldig'i** | Har 15 sekundda yangilanadi, agent telefonda ko'radi |
| **Qarz sinxroni** | Har klient bo'yicha qarz va to'lov SD da ko'rinadi |
| **Klient sinxroni** | Ikki tomonlama, dublikatlar avtomatik birlashtiriladi |
| **Dostavka** | Status o'zgarganda MoySklad va SD da bir vaqtda yangilanadi |
| **Qarz limiti blok** | Qarz limitidan oshsa zakaz qabul qilinmaydi |
| **Tovar yo'q blok** | Sklad 0 bo'lsa zakaz qabul qilinmaydi |
| **Multi-tenant** | Bir server — ko'p kompaniya |

---

## Texnologiyalar

**Backend**
- Python 3.11 + FastAPI
- SQLAlchemy async + PostgreSQL
- httpx + tenacity (retry)
- JWT autentifikatsiya

**Frontend**
- React 18 + TypeScript
- Vite + Tailwind CSS
- Framer Motion

**Infratuzilma**
- Docker + Docker Compose
- Nginx reverse proxy
- Dokploy deployment

---

## Ishga tushirish

### Talablar
- Docker va Docker Compose
- Git

### 1. Kodni yuklab oling
```bash
git clone https://github.com/Elmun-Technologies/salesmoy.git
cd salesmoy
```

### 2. Environment sozlang
```bash
cp backend/.env.example backend/.env
nano backend/.env
```

To'ldirish kerak bo'lgan asosiy maydonlar:
```env
APP_SECRET_KEY=kamida_32_belgili_maxfiy_kalit
DB_PASSWORD=kuchli_parol
MOYSKLAD_CLIENT_ID=moysklad_app_client_id
MOYSKLAD_CLIENT_SECRET=moysklad_app_client_secret
MOYSKLAD_REDIRECT_URI=https://sizning-domen.com/api/auth/moysklad/callback
FRONTEND_BASE_URL=https://sizning-domen.com
CORS_ORIGINS=https://sizning-domen.com
```

### 3. Ishga tushiring
```bash
docker-compose -f docker-compose.dokploy.yml up -d
```

### 4. Tekshiring
```
https://sizning-domen.com        → Frontend
https://sizning-domen.com/docs   → API dokumentatsiya
https://sizning-domen.com/health → Server holati
```

---

## MoySklad Webhook sozlash

MoySklad admin panelida bir marta sozlanadi:

```
Настройки → Вебхуки → Добавить вебхук

URL:      https://sizning-domen.com/webhook/moysklad
Метод:    POST
События:  Заказ покупателя → Создание
          Заказ покупателя → Изменение
```

---

## API Endpointlar

### Autentifikatsiya
```
POST /api/auth/register          Yangi kompaniya ro'yxatdan o'tish
POST /api/auth/login             Tizimga kirish
GET  /api/auth/me                Joriy foydalanuvchi
POST /api/auth/connect/moysklad  MoySklad ulash (token)
POST /api/auth/connect/salesdoctor  Sales Doctor ulash
```

### Ma'lumotlar
```
GET  /api/orders     Zakazlar ro'yxati
GET  /api/stock      Sklad qoldig'i
GET  /api/clients    Klientlar
GET  /api/debts      Qarzlar
GET  /api/agents     Agentlar
GET  /api/logs       Sinxronizatsiya loglari
```

### Webhooklar
```
POST /webhook/moysklad      MoySklad eventlari
POST /webhook/salesdoctor   Sales Doctor eventlari
```

---

## Sinxronizatsiya jadvali

| Jarayon | Interval |
|---|---|
| Sklad qoldig'i | 15 sekund |
| Klientlar | 5 daqiqa |
| Zakazlar | 5 daqiqa |
| Qarzlar | 10 daqiqa |
| Mahsulotlar SD ga | 1 soat |

---

## Biznes qoidalar

- **Qarz limiti oshsa** → zakaz qabul qilinmaydi, log yoziladi
- **Sklad 0 bo'lsa** → zakaz qabul qilinmaydi, log yoziladi  
- **Dublikat klient** → telefon bo'yicha birlashtiriladi
- **Xatolik** → 3 marta qayta urinadi (exponential backoff)

---

## Loyiha tuzilmasi

```
salesmoy/
├── backend/
│   ├── main.py              # FastAPI app + background loops
│   ├── models.py            # SQLAlchemy modellar
│   ├── config.py            # Sozlamalar
│   ├── database.py          # DB ulanish
│   ├── routers/             # API endpointlar
│   │   ├── auth.py
│   │   ├── orders.py
│   │   ├── stock.py
│   │   ├── clients.py
│   │   ├── debts.py
│   │   ├── webhooks.py
│   │   └── agents.py
│   ├── services/
│   │   ├── sync.py          # Asosiy sinxronizatsiya logikasi
│   │   ├── moysklad.py      # MoySklad API client
│   │   └── salesdoctor.py   # Sales Doctor JSON-RPC client
│   ├── middleware/
│   │   └── tenant.py        # Multi-tenant middleware
│   └── security/
│       └── jwt_tokens.py    # JWT
├── src/                     # React frontend
├── docker-compose.yml
├── docker-compose.dokploy.yml
├── nginx.dokploy.conf
└── .env.dokploy             # Dokploy environment template
```

---

## Litsenziya

Proprietary — Elmun Technologies
