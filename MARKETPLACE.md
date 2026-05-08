# 🏪 Marketplace'ga Chiqarish Qo'llanmasi

## Sales Doctor ↔ MoySklad Integration

---

## 1. MoySklad Marketplace

### 1.1 Ro'yxatdan o'tish

1. **Partner dasturiga ariza**
   - Sayt: https://partner.moysklad.ru/
   - "Стать партнером" tugmasini bosing
   - Kompaniya ma'lumotlarini to'ldiring

2. **Kerakli hujjatlar:**
   - [ ] Kompaniya ro'yxatdan o'tish guvohnomasi
   - [ ] INN / KPP
   - [ ] Bank rekvizitlari
   - [ ] Sayt yoki ilova namoyishi

### 1.2 Ilova (Application) Ro'yxatdan O'tkazish

**MoySklad Developer Console:**
```
https://online.moysklad.ru/api/apps/
```

**Kerakli ma'lumotlar:**
- Ilova nomi: "Sales Doctor Sync"
- Tavsif: "Sales Doctor bilan avtomat sinxronizatsiya"
- Turi: "Server-side"
- OAuth redirect URI: `https://api.your-domain.com/api/auth/moysklad/callback`

### 1.3 OAuth Sozlamalari

```python
# backend/config.py
MOYSKLAD_CLIENT_ID = "your-client-id"
MOYSKLAD_CLIENT_SECRET = "your-client-secret"
MOYSKLAD_REDIRECT_URI = "https://api.your-domain.com/api/auth/moysklad/callback"
```

**OAuth Flow:**
```
1. Foydalanuvchi "Ulash" tugmasini bosadi
2. MoySkladga yo'naltiriladi
3. Ruxsat beradi
4. Callback URL ga code keladi
5. Code → Access Token almashinuvi
6. Token saqlanadi (tenant.moysklad_access_token)
```

### 1.4 Moderatsiya

- Ariza yuborish: 3-10 kun
- Tekshirish: MoySklad jamoasi
- Natija: Email orqali xabar

### 1.5 Narxlar Siyosati

**MoySklad komissiyasi:** 20-30%

**Sizning daromadingiz:**

| Tarif | Narxi | MoySklad komissiyasi | Sizning daromadingiz |
|-------|-------|---------------------|---------------------|
| Basic | 1,900₽ | 570₽ (30%) | 1,330₽ |
| Pro | 3,900₽ | 1,170₽ (30%) | 2,730₽ |
| Enterprise | 9,900₽ | 2,970₽ (30%) | 6,930₽ |

---

## 2. Sales Doctor Marketplace

### 2.1 Bog'lanish

1. **Sales Doctor supportiga murojaat:**
   - Email: support@salesdoctor.uz
   - Telegram: @salesdoctor_support

2. **Ariza yuborish:**
   - Kompaniya haqida ma'lumot
   - Integratsiya tavsifi
   - API dokumentatsiyasi

### 2.2 Sertifikatlash

- API testlari
- Xavfsizlik tekshiruvi
- UX/UI baholash

### 2.3 Narxlar

| Tarif | Narxi (so'm) | Komissiya | Sizning daromadingiz |
|-------|-------------|-----------|---------------------|
| Basic | 390,000 | 78,000 (20%) | 312,000 |
| Pro | 790,000 | 158,000 (20%) | 632,000 |
| Enterprise | 1,990,000 | 398,000 (20%) | 1,592,000 |

---

## 3. O'zbekiston Bozori (Mustaqil)

### 3.1 Marketing Rejasi

**1-oy — Beta test:**
- 10 ta kompaniyaga bepul berish
- Feedback yig'ish
- Xatolarni tuzatish

**2-oy — Soft Launch:**
- Telegram kanal ochish
- YouTube video yuklash
- Target reklama (Instagram, Facebook)

**3-oy — Full Launch:**
- Webinar o'tkazish
- Hamkorlik (Sales Doctor, MoySklad)
- PR maqolalar

### 3.2 Reklama Byudjeti

| Kanal | Byudjet (oyiga) | Kutilayotgan natija |
|-------|----------------|---------------------|
| Instagram Target | $200 | 50 ta lead |
| Google Ads | $150 | 30 ta lead |
| Telegram kanallar | $100 | 20 ta lead |
| YouTube | $50 | 10 ta lead |
| **Jami** | **$500** | **110 ta lead** |

### 3.3 Konversiya

- Lead → Trial: 30% (33 ta)
- Trial → Paid: 40% (13 ta)
- O'rtacha chek: 590,000 so'm
- **Oylik daromad: ~7,670,000 so'm**

---

## 4. To'lov Tizimlari

### 4.1 Payme (O'zbekiston)

**Ro'yxatdan o'tish:**
- https://payme.uz/business
- Merchant ID olish
- Secret key olish

**Integratsiya:**
```python
# backend/payments/payme.py

class PaymePayment:
    def create_payment(self, amount, order_id):
        return {
            "merchant_id": PAYME_MERCHANT_ID,
            "amount": amount * 100,  # tiyin
            "order_id": order_id,
        }
```

### 4.2 Click (O'zbekiston)

**Ro'yxatdan o'tish:**
- https://click.uz/uz/business
- Service ID olish

### 4.3 YooKassa (Rossiya)

**Ro'yxatdan o'tish:**
- https://yookassa.ru/join/
- Shop ID va Secret Key olish

---

## 5. Hujjatlar Paketi

### 5.1 Foydalanuvchi Qo'llanmasi (User Guide)

```
docs/
├── user-guide/
│   ├── 01-registration.md
│   ├── 02-connect-moysklad.md
│   ├── 03-connect-salesdoctor.md
│   ├── 04-first-sync.md
│   ├── 05-orders.md
│   ├── 06-stock.md
│   ├── 07-clients.md
│   ├── 08-debts.md
│   ├── 09-delivery.md
│   └── 10-troubleshooting.md
```

### 5.2 API Dokumentatsiyasi

Avtomat yaratiladi:
```
https://api.your-domain.com/docs
```

### 5.3 Video Qo'llanma

- YouTube kanal ochish
- 5-10 ta qisqa video yuklash:
  1. "Integratsiyani ulanish"
  2. "Birinchi buyurtma"
  3. "Ombor sinxronizatsiyasi"
  4. "Debetor hisoboti"
  5. "Yetkazib berish"

---

## 6. Qo'llab-quvvatlash (Support)

### 6.1 Kanallar

| Kanal | Javob vaqti |
|-------|-------------|
| Telegram bot | 5 daqiqa |
| Email | 2 soat |
| Telefon | 15 daqiqa |
| Video qo'ng'iroq | By appointment |

### 6.2 SLA

| Tarif | Qo'llab-quvvatlash | Javob vaqti |
|-------|-------------------|-------------|
| Basic | Email | 24 soat |
| Pro | Email + Chat | 4 soat |
| Enterprise | Dedicated manager | 1 soat |

---

## 7. Metrikalar va Monitoring

### 7.1 Kutilayotgan Metrikalar

| Metrika | 1-oy | 3-oy | 6-oy | 12-oy |
|---------|------|------|------|-------|
| Ro'yxatdan o'tgan | 50 | 200 | 500 | 1000 |
| Faol foydalanuvchi | 20 | 80 | 200 | 400 |
| To'lov qilgan | 5 | 30 | 100 | 250 |
| Oylik daromad | $500 | $3,000 | $10,000 | $25,000 |

### 7.2 Monitoring Asboblari

- **Sentry** — Xatolarni kuzatish
- **Grafana** — Metrikalar
- **UptimeRobot** — Server holati
- **Google Analytics** — Foydalanuvchi harakatlari

---

## 8. Xavfsizlik Tekshiruvi

### 8.1 Ro'yxat (Security Checklist)

- [ ] SSL sertifikat (HTTPS)
- [ ] CORS sozlamalari
- [ ] Rate limiting
- [ ] SQL injection himoyasi
- [ ] XSS himoyasi
- [ ] CSRF tokenlari
- [ ] Parol hashlash (bcrypt)
- [ ] JWT tokenlari
- [ ] API kalitlari xavfsiz saqlash
- [ ] Loglarni tozalash (PII)

### 8.2 Pentest (ixtiyoriy)

Xavfsizlik tekshiruvi uchun:
- OWASP ZAP
- Burp Suite
- Nmap

---

## 9. Yakuniy Tekshiruv Ro'yxati

### 9.1 Marketplace'ga chiqishdan oldin

- [ ] Backend production serverga joylangan
- [ ] SSL sertifikat o'rnatilgan
- [ ] Domen nomi sotib olingan
- [ ] To'lov tizimi ulangan
- [ ] MoySklad OAuth sozlangan
- [ ] Sales Doctor API kaliti bor
- [ ] User Guide yozilgan
- [ ] Video qo'llanma yuklangan
- [ ] Support kanallari tayyor
- [ ] Monitoring o'rnatilgan
- [ ] Backup tizimi sozlangan
- [ ] Xavfsizlik tekshiruvi o'tkazilgan

### 9.2 Ariza Yuborish

**MoySklad:**
```
To: partner@moysklad.ru
Subject: Application for Marketplace — Sales Doctor Sync

Attachments:
- Application form
- Screenshots
- User Guide
- API Docs
- Video demo
```

---

## 10. Keyingi Bosqichlar

| Bosqich | Vaqt | Vazifa |
|---------|------|--------|
| 1 | 1 hafta | Server sozlash, deploy |
| 2 | 1 hafta | Beta test (10 kompaniya) |
| 3 | 2 hafta | MoySklad marketplace ariza |
| 4 | 2 hafta | Sales Doctor hamkorlik |
| 5 | Doimiy | Marketing, support, yangilanish |
