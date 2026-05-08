# 🔑 Demo Kirish Ma'lumotlari

## ✅ HOZIR ISHLATISH MUMKIN — Backend kerak emas!

Loyiha **avtomat mock ma'lumotlar** bilan ishlaydi. Backend yo'q bo'lsa ham demo to'liq ishlaydi.

---

## 🔑 Demo Login

**Login sahifasida "Demo ma'lumotlarni to'ldirish" tugmasini bosing!**

| | Qiymat |
|---|---|
| **Email** | `demo@example.com` |
| **Parol** | `demo123` |

---

## 🚀 Tez ishga tushirish (faqat brauzer)

### Variant 1: Build faylni ochish
```
dist/index.html
```
Faqat brauzerda oching — hamma narsa ishlaydi!

### Variant 2: Live server
```bash
npx serve dist
# yoki
python -m http.server 8080 --directory dist
```
Brauzerda: `http://localhost:8080`

### Variant 3: npm run dev
```bash
npm install
npm run dev
```
Brauzerda: `http://localhost:5173`

---

## 📊 Demo rejimda nimalar bor

| Modul | Ma'lumotlar |
|-------|-------------|
| **Buyurtmalar** | 6 ta (turli statuslarda) |
| **Ombor** | 10 ta SKU |
| **Mijozlar** | 8 ta (opt/rozniсa) |
| **Debetorlar** | 8 ta (qarz ma'lumotlari) |
| **Yetkazib berish** | 3 ta |
| **Loglar** | 12 ta |

---

## ⚠️ Mock rejim haqida

Agar backend (`localhost:8000`) ishlamasa, tizim avtomat **mock ma'lumotlar** ko'rsatadi.

Ekran yuqorisida **sariq banner** chiqadi:
> "Demo rejim: Backend ulanmagan. Mock ma'lumotlar ko'rsatilmoqda."

---

## 🖥️ Backend bilan ishga tushirish (ixtiyoriy)

Agar to'liq funksionallikni sinab ko'rmoqchi bo'lsangiz:

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python seed.py
python main.py
```

Keyin frontendni ishga tushiring:
```bash
npm run dev
```

Backend `http://localhost:8000` da ishlaydi.

---

## 🔗 API Docs (backend bilan)

Swagger UI: http://localhost:8000/docs
