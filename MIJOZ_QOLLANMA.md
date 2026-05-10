# MoySklad ↔ Sales Doctor Integratsiya — Mijoz Qo'llanmasi

**Versiya:** 1.0  
**Murojaat uchun:** Elmun Technologies

---

## Bu qo'llanma haqida

Ushbu hujjat integratsiya tizimini birinchi marta ishga tushirish va to'g'ri ishlayotganini tekshirish uchun yozilgan. Har bir qadamni ketma-ket bajaring — oxirida hamma narsa avtomatik ishlayotganiga ishonch hosil qilasiz.

---

## 1-BOSQICH: Tizimga kirish

### 1.1 Ro'yxatdan o'tish

Brauzerda (`https://sizning-domen.com`) saytni oching va **"Ro'yxatdan o'tish"** tugmasini bosing.

To'ldiring:

| Maydon | Misol |
|---|---|
| Kompaniya nomi | "Baraka Trade LLC" |
| Slug (qisqa nom) | "baraka-trade" *(faqat lotin harflari va chiziqcha)* |
| Email | admin@baraka-trade.uz |
| To'liq ism | Aziz Karimov |
| Parol | Kamida 8 belgili parol |

**Natija:** Tizimga avtomatik kirasiz va dashboard ochiladi.

> ⚠️ **Slug bir marta belgilanadi, keyinchalik o'zgartirib bo'lmaydi.** Diqqat bilan kiriting.

---

## 2-BOSQICH: MoySklad ulash

Sozlamalar → **"MoySklad API"** bo'limiga o'ting.

### 2.1 Token olish (MoySklad dan)

1. MoySklad ga kiring: [online.moysklad.ru](https://online.moysklad.ru)
2. **Настройки** → **Токены** → **Создать токен**
3. Tokenga nom bering (masalan: "Integration") → **Создать**
4. Ko'rsatilgan tokenni nusxa oling (**bir marta ko'rsatiladi!**)

### 2.2 Tokenni saqlash

1. Dashboard → **Sozlamalar** bo'limiga o'ting
2. **"Access Token"** maydoniga nusxa olgan tokeningizni joylashtiring
3. **"Ulash"** tugmasini bosing
4. Yashil "Ulangan" belgisi chiqishi kerak ✅

### 2.3 Webhook tekshirish

Token saqlanganidan so'ng tizim avtomatik ravishda MoySkladga webhook ro'yxatdan o'tkazadi. Tekshirish uchun:

- Sozlamalar → **"Real-time webhook"** bo'limida **"Webhook ulangan (5 ta hodisa)"** yozuvi ko'rinishi kerak ✅

Agar "Webhook ulanmagan" desa — **"Real-time webhook ulash"** tugmasini bosing.

---

## 3-BOSQICH: Sales Doctor ulash

Sozlamalar → **"Sales Doctor API"** bo'limiga o'ting.

To'ldiring:

| Maydon | Misol |
|---|---|
| Server URL | `https://sizning-sd-server.uz/api/v2/` |
| Login | SD tizimidagi loginингиз |
| Parol | SD tizimidagi parolingiz |
| Filial ID | 0 (yoki filialingiz raqami, masalan: 1, 2, 3...) |

**"Ulash"** tugmasini bosing.

> ✅ **Muvaffaqiyatli ulanganda:** "Sales Doctor ulangan" yashil belgisi chiqadi.  
> ❌ **Xatolik bo'lsa:** Login yoki parol noto'g'ri, yoki server URL oxiridagi `/` belgisi yetishmayapti.

---

## 4-BOSQICH: Sinov — Birinchi Zakaz

Bu eng muhim tekshiruv. Maqsad: **MoySklad da zakaz yaratilganda Sales Doctor da ham ko'rinishini tekshirish.**

### 4.1 MoySklad da test zakaz yarating

1. MoySklad ga kiring
2. **Продажи** → **Заказы покупателей** → **Создать**
3. To'ldiring:
   - **Контрагент:** Istalgan mijozni tanlang yoki yangi yarating
   - **Склад:** Asosiy sklad
   - **Товары:** Kamida bitta mahsulot qo'shing (miqdor va narxi bilan)
4. **Сохранить** ni bosing

### 4.2 Sales Doctor da tekshiring

MoySklad da zakazni saqlagan vaqtingizdan boshlab **10-30 soniya** ichida:

1. Sales Doctor ilovasini oching
2. **Заказы** bo'limiga o'ting
3. Yangi zakaz ko'rinishi kerak ✅

**Zakaz ma'lumotlari to'g'ri bo'lishi kerak:**
- ✅ Mijoz ismi va telefoni
- ✅ Mahsulotlar ro'yxati
- ✅ Umumiy summa

> ⚠️ Agar 1 daqiqa o'tib ham zakaz ko'rinmasa — [**8-bo'lim: Muammolarni hal qilish**](#8-muammolarni-hal-qilish) ga o'ting.

---

## 5-BOSQICH: Sklad Qoldiqlarini Tekshirish

Maqsad: MoySklad dagi sklad qoldiqlari Sales Doctor da ham ko'rinishini tekshirish.

### 5.1 MoySklad da tekshiring

1. MoySklad → **Отчеты** → **Остатки**
2. Bitta mahsulotning qoldiq miqdorini yod oling (masalan: "Mahsulot A — 150 dona")

### 5.2 Dashboard da tekshiring

1. Integratsiya dashboardiga kiring
2. **"Sklad"** bo'limini oching
3. Shu mahsulotni toping — miqdori MoySklad bilan mos bo'lishi kerak ✅

> Sklad har 60 soniyada yangilanadi. Farq bo'lsa 1-2 daqiqa kuting.

---

## 6-BOSQICH: Klientlar Sinxronini Tekshirish

### 6.1 MoySklad da yangi kontragent yarating

1. MoySklad → **Контрагенты** → **Создать**
2. Ism va telefon kiriting (masalan: "+998 90 000 00 01")
3. Saqlang

### 6.2 Dashboard da tekshiring

1. Dashboard → **"Klientlar"** bo'limini oching
2. 1-3 daqiqa ichida yangi klient ko'rinishi kerak ✅

---

## 7-BOSQICH: Loglarni Ko'rish

Dashboard → **"Loglar"** bo'limiga o'ting.

Bu yerda barcha sinxron operatsiyalari ko'rsatiladi:

| Rang | Ma'nosi |
|---|---|
| 🟢 Yashil (success) | Muvaffaqiyatli sinxron |
| 🔵 Ko'k (info) | Ma'lumot xabari |
| 🟡 Sariq (warning) | Ogohlantirish (e'tibor bering) |
| 🔴 Qizil (error) | Xato — qayta uriniladi |

**Sog'lom tizimda:** Asosan yashil loglar, ba'zan ko'k loglar ko'rinadi.

**Muammo belgisi:** Ko'p qizil loglar ketma-ket kelyapti.

---

## 8-BOSQICH: Muammolarni Hal Qilish

### ❌ Zakaz Sales Doctor da ko'rinmayapti

**1. Loglarni tekshiring:**
Dashboard → Loglar → qizil (error) yozuvlarni toping.

Keng tarqalgan xatolar:

| Xato matni | Sabab | Yechim |
|---|---|---|
| `SD credentials not configured` | SD ulanmagan | 3-bosqichni qaytaring |
| `Склад не найден` | SD da sklad sozlanmagan | SD administratoriga murojaat |
| `Товар не найден` | Mahsulot kodi SD da yo'q | SD da mahsulot `code_1C` ni tekshiring |
| `На складе товара недостаточно` | Sklad yetarli emas | Bu hol SD da normal blok |
| `HTTP 401` | Token muddati tugagan | Tokenni yangilang (2-bosqich) |

**2. Webhook ulanganini tekshiring:**
Sozlamalar → Real-time webhook → "Ulangan" ko'rinishi kerak.

**3. 5 daqiqa kuting:**
Webhook ishlamasa ham, tizim har 5 daqiqada MoySkladan yangi zakazlarni tekshiradi.

---

### ❌ Sklad qoldiqlari yangilanmayapti

1. Sozlamalar → MoySklad bo'limida "Ulangan" ko'rinishi kerak
2. 2 daqiqa kuting (sklad har 60 sek yangilanadi)
3. Hali ham ko'rinmasa — sahifani yangilang (F5)

---

### ❌ "Token expired" xatosi

1. Sozlamalar → MoySklad bo'limi
2. MoySklad dan yangi token oling (2.1-qadam)
3. Yangi tokenni kiriting va "Yangilash" bosing

---

### ❌ Sales Doctor ulanmayapti

Tekshiring:
- Server URL to'g'rimi? (`https://...` bilan boshlanadi va `/` bilan tugaydi)
- Login va parol to'g'rimi?
- Filial ID to'g'rimi? (0 = asosiy filial)

---

## 9-BOSQICH: Kundalik Monitoring

Tizim to'g'ri ishlayotganini tekshirish uchun **har kuni bir marta**:

1. Dashboard → **Loglar** → Qizil xatolar yo'qligini tekshiring
2. **Zakazlar** bo'limida bugungi zakazlar ko'rinayotganini tekshiring
3. **Sklad** bo'limida qoldiqlar yangilanganini tekshiring

> Agar hamma narsa yashil bo'lsa — tizim mukammal ishlayapti ✅

---

## Qo'shimcha Ma'lumotlar

### Sinxronizatsiya qancha vaqtda ishlaydi?

| Nima | Qachon |
|---|---|
| MoySklad zakaz yaratildi | **Bir necha soniya ichida** SD ga tushadi (webhook) |
| Sklad qoldiqlari | Har **60 soniyada** yangilanadi |
| Klientlar | Har **5 daqiqada** yangilanadi |
| Qarzlar | Har **10 daqiqada** yangilanadi |

### Muhim eslatmalar

- **Mahsulot kodlari:** MoySklad dagi mahsulot kodi (`Код`) Sales Doctor dagi `code_1C` bilan bir xil bo'lishi kerak. Aks holda zakaz yuborilmaydi.
- **Telefon formati:** Klient telefoni `+998901234567` formatida bo'lishi tavsiya etiladi.
- **Sklad nomi:** SD da sklad nomi MoySklad bilan mos bo'lishi kerak.

---

## Texnik Yordam

Muammo hal bo'lmasa:

1. **Dashboard → Loglar** bo'limidan xato matnini nusxa oling
2. Quyidagilarga yuboring: **support@elmun.uz** yoki Telegram: **@elmun_support**

Xabaringizga qo'shing:
- Xato matni (logdan)
- Qaysi qadam bajarilayotganda xato chiqdi
- Sanasi va vaqti

---

*Elmun Technologies — © 2025*
