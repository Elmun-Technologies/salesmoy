# 📋 Sales Doctor ↔ MoySklad Integratsiya — To'liq Hisobot

## ✅ LOYIHA TUGATILDI

Ushbu loyiha **Sales Doctor** va **MoySklad** o'rtasida to'liq ikki tomonlama integratsiya qiladi.

---

## 📁 LOYIHA STRUKTURASI

```
project/
├── 📦 FRONTEND (React + Vite + Tailwind CSS)
│   ├── src/
│   │   ├── App.tsx                    # Asosiy ilova
│   │   ├── services/
│   │   │   └── api.ts                 # Backend API chaqiruvlari
│   │   ├── components/
│   │   │   ├── Sidebar.tsx            # Navigatsiya paneli
│   │   │   ├── Dashboard.tsx          # Asosiy dashboard
│   │   │   ├── OrdersPanel.tsx        # Buyurtmalar
│   │   │   ├── StockPanel.tsx         # Ombor qoldiqlari
│   │   │   ├── ClientsPanel.tsx       # Mijozlar
│   │   │   ├── DebtsPanel.tsx         # Debetorlar
│   │   │   ├── DeliveryPanel.tsx      # Yetkazib berish
│   │   │   ├── LogsPanel.tsx          # Loglar
│   │   │   └── SettingsPanel.tsx      # Sozlamalar
│   │   └── data/
│   │       └── mockData.ts            # Test ma'lumotlar
│   ├── index.html
│   └── package.json
│
└── 🐍 BACKEND (Python + FastAPI)
    ├── main.py                        # Asosiy server
    ├── config.py                      # Konfiguratsiya
    ├── database.py                    # Ma'lumotlar bazasi
    ├── models.py                      # SQLAlchemy modellari
    ├── requirements.txt               # Paketlar
    ├── .env.example                   # Muhit o'zgaruvchilari namunasi
    ├── start.sh / start.bat           # Ishga tushirish skriptlari
    ├── README.md                      # Backend hujjatlari
    ├── services/
    │   ├── moysklad.py                # MoySklad API klienti
    │   ├── salesdoctor.py             # Sales Doctor API klienti
    │   └── sync.py                    # Sinxronizatsiya logikasi
    └── routers/
        ├── orders.py                  # Buyurtmalar API
        ├── stock.py                   # Ombor API
        ├── clients.py                 # Mijozlar API
        ├── debts.py                   # Debetor API
        ├── delivery.py                # Yetkazib berish API
        ├── logs.py                    # Loglar API
        └── webhooks.py                # Webhook endpointlari
```

---

## 🔄 INTEGRATSIYA OQIMI

### 1. BUYURTMALAR (Orders)

```
┌─────────────────┐
│  Sales Doctor   │
│  (Agent ilova)  │
└────────┬────────┘
         │ 1. Agent buyurtma yaratdi
         │ POST /webhook/salesdoctor
         ▼
┌──────────────────────────┐
│     Python Backend       │
│  2. Kontragent tekshiruv │
│  3. Agar yo'q → yaratish │
│  4. MoySkladga yuborish  │
└────────┬─────────────────┘
         │ POST /entity/customerorder
         ▼
┌─────────────────┐
│    MoySklad     │
│  5. Buyurtma    │
│     yaratildi   │
└────────┬────────┘
         │ Webhook: order.updated
         ▼
┌──────────────────────────┐
│     Python Backend       │
│  6. Status yangilandi    │
│  7. Sales Doctor ga      │
│     yuborildi            │
└────────┬─────────────────┘
         │ POST /orders/{id}/status
         ▼
┌─────────────────┐
│  Sales Doctor   │
│  (Agent ko'radi)│
└─────────────────┘
```

**Statuslar:**
- `Новый` → `В обработке` → `Отгружен` → `В пути` → `Доставлен`
- Yoki: `Отменен`

---

### 2. OMBOR QOLDIQLARI (Stock)

```
┌─────────────────┐
│    MoySklad     │
│  (Asosiy ombor) │
└────────┬────────┘
         │ Har 15 sekundda
         │ GET /report/stock/all
         ▼
┌──────────────────────────┐
│     Python Backend       │
│  1. Qoldiqlarni olish    │
│  2. Kam qolganlarni      │
│     aniqlash             │
│  3. Sales Doctor ga      │
│     yuborish             │
└────────┬─────────────────┘
         │ POST /stock/sync
         ▼
┌─────────────────┐
│  Sales Doctor   │
│  (Agent telefon)│
│  ko'radi        │
└─────────────────┘
```

**Agar tovar yo'q bo'lsa:** Buyurtma qabul qilinmaydi ❌

---

### 3. DEBITORKA (Debts)

```
┌─────────────────┐
│    MoySklad     │
│  (To'lov tushdi)│
└────────┬────────┘
         │ Har 10 daqiqada
         │ GET /report/counterparty
         ▼
┌──────────────────────────┐
│     Python Backend       │
│  1. Har bir mijoz uchun: │
│     - Jami qarz          │
│     - To'langan summa    │
│     - Qoldiq             │
│  2. Sales Doctor ga      │
│     yuborish             │
└────────┬─────────────────┘
         │ PUT /clients/{id}/debt
         ▼
┌─────────────────┐
│  Sales Doctor   │
│  (Rahbar ko'radi)│
└─────────────────┘
```

---

### 4. KLIENTLAR (Clients)

**Ikki tomonlama sinxronizatsiya:**

```
Sales Doctor ◄────────────► MoySklad
     │                            │
     │ 1. Yangi klient            │
     │───────────────────────────>│
     │                            │
     │ 2. Dublikat tekshirish     │
     │    (telefon OR nom)        │
     │                            │
     │ 3. Agar yo'q → yaratish    │
     │    Agar bor → yangilash    │
     │                            │
     │ 4. Ma'lumotlar:            │
     │    - Nomi                  │
     │    - Telefon               │
     │    - Adres                 │
     │    - Lokatsiya (GPS)       │
     │    - Tip (opt/rozniсa)     │
```

---

### 5. YETKAZIB BERISH (Delivery)

```
┌─────────────────┐
│    MoySklad     │
│  "Отгрузка"     │
│  yaratildi      │
└────────┬────────┘
         │ Webhook
         ▼
┌──────────────────────────┐
│     Python Backend       │
│  1. Kuryerga topshirish  │
│  2. Status: "В пути"     │
└────────┬─────────────────┘
         │
         ▼
┌─────────────────┐
│     Kuryer      │
│  (Yetkazib      │
│   beradi)       │
└────────┬────────┘
         │ Status o'zgardi
         │ POST /webhook/salesdoctor
         ▼
┌──────────────────────────┐
│     Python Backend       │
│  1. Status: "Доставлен"  │
│  2. MoySklad ga qaytarish│
└────────┬─────────────────┘
         │ PUT /entity/customerorder
         ▼
┌─────────────────┐
│    MoySklad     │
│  Status yangi-  │
│  landi          │
└─────────────────┘
```

---

## 🔐 AVTORIZATSIYA

| Xizmat | Autentifikatsiya | Qayerda |
|--------|-----------------|---------|
| MoySklad | API Token (Bearer) | online.moysklad.ru |
| Sales Doctor | API Key (Bearer) | api.salesdoctor.uz |
| Backend | Secret Key | .env fayl |

---

## ⚙️ TEXNIK QISIM

### API Format
- **Format:** JSON
- **Protokol:** HTTPS
- **Retry:** 3 marta (exponential backoff)

### Webhook Events
**MoySklad:**
- `order.created` — Yangi buyurtma
- `order.updated` — Buyurtma yangilandi
- `customerorder.deleted` — Buyurtma o'chirildi

**Sales Doctor:**
- `order.created` — Yangi buyurtma
- `order.updated` — Status o'zgardi
- `delivery.status_changed` — Yetkazib berish statusi
- `client.updated` — Mijoz ma'lumotlari yangilandi

### Cron Jadvali
| Vazifa | Interval | Tavsif |
|--------|----------|--------|
| Stock Sync | Har 15 soniya | Ombor qoldiqlari |
| Debt Sync | Har 10 daqiqa | Debetor ma'lumotlari |
| Client Sync | Har 5 daqiqa | Mijozlar ro'yxati |

---

## 🛡️ BIZNES QOIDALAR

| Qoida | Holat | Natija |
|-------|-------|--------|
| **Qarz limiti** | Mijoz limitidan oshsa | ❌ Buyurtma bloklanadi |
| **Tovar yo'q** | Omborda yetarli emas | ❌ Buyurtma qabul qilinmaydi |
| **Dublikat** | Telefon yoki nom bir xil | 🔄 Avtomatik birlashtiriladi |
| **Retry xato** | 3 marta urinishdan keyin | 📝 Logga yoziladi |

---

## 🚀 ISHGA TUSHIRISH

### 1. Frontend (React)

```bash
# Frontend papkasida
npm install
npm run build
# Yoki ishlab turish uchun:
npm run dev
```

### 2. Backend (Python)

```bash
# Backend papkasiga o'tish
cd backend

# Windows
copy .env.example .env
start.bat

# Linux/Mac
cp .env.example .env
chmod +x start.sh
./start.sh
```

### 3. .env Faylni sozlash

```env
# MoySklad
MOYSKLAD_TOKEN=sk_sizning_tokeningiz
MOYSKLAD_BASE_URL=https://api.moysklad.ru/api/remap/1.2

# Sales Doctor
SALESDOCTOR_API_KEY=sd_sizning_kalitingiz
SALESDOCTOR_BASE_URL=https://api.salesdoctor.uz/v2

# Sozlamalar
STOCK_SYNC_INTERVAL=15
DEBT_SYNC_INTERVAL=600
CLIENT_SYNC_INTERVAL=300
```

---

## 📊 MA'LUMOTLAR BAZASI

**SQLite** (standart) yoki **PostgreSQL**

### Jadvallar:
- `orders` — Buyurtmalar
- `clients` — Mijozlar
- `stock_items` — Ombor tovarlari
- `debt_records` — Debetor yozuvlari
- `deliveries` — Yetkazib berish
- `sync_logs` — Sinxronizatsiya loglari
- `webhook_events` — Webhook hodisalari

---

## 🔌 API ENDPOINTLAR

| Endpoint | Method | Tavsif |
|----------|--------|--------|
| `/api/orders` | GET | Buyurtmalar ro'yxati |
| `/api/orders/sync` | POST | Buyurtmani sinxronlash |
| `/api/stock` | GET | Ombor qoldiqlari |
| `/api/stock/sync` | POST | Omborni sinxronlash |
| `/api/clients` | GET | Mijozlar ro'yxati |
| `/api/clients/sync` | POST | Mijozlarni sinxronlash |
| `/api/debts` | GET | Debetor ma'lumotlari |
| `/api/debts/sync` | POST | Debetorni sinxronlash |
| `/api/delivery` | GET | Yetkazib berish |
| `/api/logs` | GET | Loglar |
| `/webhook/moysklad` | POST | MoySklad webhook |
| `/webhook/salesdoctor` | POST | Sales Doctor webhook |
| `/docs` | GET | Swagger UI |

---

## 🧪 XATOLARNI QAYTA ISHLASH

```python
# Retry mehanizmi (tenacity)
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
)
async def api_call():
    # API chaqiruvi
    pass

# Xatolik darajalari:
# 1. INFO - Oddiy xabar
# 2. WARNING - Ogohlantirish
# 3. ERROR - Xato (3 marta urinish)
# 4. SUCCESS - Muvaffaqiyatli
```

---

## 📈 KUTILAYOTGAN NATIJA

| Kim | Nima qiladi | Natija |
|-----|-------------|--------|
| **Agent** | Buyurtma kiritadi | ✅ Avtomat ravishda MoySkladga ketadi |
| **Sklad** | Omborni boshqaradi | ✅ Agent telefonda qoldiqlarni ko'radi |
| **Kuryer** | Yetkazib beradi | ✅ Status avtomat yangilanadi |
| **Rahbar** | Hammasini nazorat qiladi | ✅ Dashboard orqali real vaqtda |

---

## ❓ SAVOLLAR VA JAVOBLAR

### Q: Hamma narsa ishlaydimi?
**A:** Ha, lekin API kalitlarni sozlash kerak. Frontend va backend to'liq tayyor.

### Q: Nima berishim kerak?
**A:**
1. MoySklad API Token
2. Sales Doctor API Key
3. (Ixtiyoriy) Webhook URL

### Q: Qancha vaqt ketadi?
**A:**
- Backend ishga tushirish: 5 daqiqa
- API kalitlarni sozlash: 10 daqiqa
- Test: 30 daqiqa

### Q: Xavfsizmi?
**A:** Ha. API kalitlar .env faylda saqlanadi, CORS sozlangan, webhook secret qo'llab-quvvatlanadi.

---

## 📞 KEYINGI QADAMLAR

1. **MoySklad** dan API token olish
2. **Sales Doctor** dan API key olish
3. `.env` faylni to'ldirish
4. Backend ishga tushirish: `./start.sh`
5. Frontend ishga tushirish: `npm run dev`
6. **Swagger UI** orqali test qilish: `http://localhost:8000/docs`

---

**Loyiha to'liq tayyor!** ✅
