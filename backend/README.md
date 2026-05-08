# Sales Doctor ↔ MoySklad Integration Backend

## 🚀 Быстрый старт

### 1. Установка зависимостей

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Настройка окружения

```bash
cp .env.example .env
# Отредактируйте .env файл, добавьте свои API ключи
```

### 3. Запуск сервера

```bash
python main.py
```

Или через uvicorn напрямую:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. API документация

После запуска откройте:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## 📁 Структура проекта

```
backend/
├── main.py                 # FastAPI приложение
├── config.py               # Конфигурация
├── database.py             # База данных (SQLAlchemy)
├── models.py               # Модели данных
├── requirements.txt        # Зависимости
├── .env.example            # Пример переменных окружения
├── services/
│   ├── moysklad.py         # MoySklad API клиент
│   ├── salesdoctor.py      # Sales Doctor API клиент
│   └── sync.py             # Логика синхронизации
└── routers/
    ├── orders.py           # API заказов
    ├── stock.py            # API остатков
    ├── clients.py          # API клиентов
    ├── debts.py            # API дебиторки
    ├── delivery.py         # API доставки
    ├── logs.py             # API логов
    └── webhooks.py         # Webhook endpoints
```

---

## 🔌 API Endpoints

### Заказы
- `GET /api/orders` — Список заказов
- `GET /api/orders/{id}` — Детали заказа
- `POST /api/orders/sync` — Синхронизировать заказ в MoySklad
- `POST /api/orders/{id}/status` — Обновить статус

### Остатки
- `GET /api/stock` — Список товаров
- `POST /api/stock/sync` — Запустить синхронизацию остатков

### Клиенты
- `GET /api/clients` — Список клиентов
- `GET /api/clients/stats` — Статистика
- `POST /api/clients/sync` — Синхронизировать клиентов

### Дебиторка
- `GET /api/debts` — Список долгов
- `GET /api/debts/summary` — Сводка
- `POST /api/debts/sync` — Синхронизировать дебиторку

### Доставка
- `GET /api/delivery` — Список доставок
- `POST /api/delivery/{id}/status` — Обновить статус доставки

### Логи
- `GET /api/logs` — Список логов
- `GET /api/logs/stats` — Статистика логов
- `POST /api/logs/clear` — Очистить логи

### Webhooks
- `POST /webhook/moysklad` — Webhook от MoySklad
- `POST /webhook/salesdoctor` — Webhook от Sales Doctor
- `GET /webhook/health` — Проверка webhook

---

## ⚙️ Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `MOYSKLAD_TOKEN` | API токен MoySklad | — |
| `MOYSKLAD_BASE_URL` | URL API MoySklad | https://api.moysklad.ru/api/remap/1.2 |
| `SALESDOCTOR_API_KEY` | API ключ Sales Doctor | — |
| `SALESDOCTOR_BASE_URL` | URL API Sales Doctor | https://api.salesdoctor.uz/v2 |
| `STOCK_SYNC_INTERVAL` | Интервал синхронизации остатков (сек) | 15 |
| `DEBT_SYNC_INTERVAL` | Интервал синхронизации дебиторки (сек) | 600 |
| `CLIENT_SYNC_INTERVAL` | Интервал синхронизации клиентов (сек) | 300 |
| `DATABASE_URL` | URL базы данных | sqlite:///./integration.db |
| `CORS_ORIGINS` | Разрешенные origins для CORS | http://localhost:5173 |

---

## 🔄 Фоновые задачи (Background Tasks)

Сервер автоматически запускает:

1. **Синхронизация остатков** — каждые `STOCK_SYNC_INTERVAL` секунд
2. **Синхронизация дебиторки** — каждые `DEBT_SYNC_INTERVAL` секунд
3. **Синхронизация клиентов** — каждые `CLIENT_SYNC_INTERVAL` секунд

---

## 🛡️ Бизнес-правила

- **Лимит задолженности** — заказ блокируется при превышении
- **Проверка остатков** — заказ принимается только при наличии товара
- **Дубликаты клиентов** — автоматическое объединение по телефону/имени
- **Retry при ошибках** — 3 попытки с экспоненциальной задержкой

---

## 🧪 Тестирование

```bash
pytest
```

---

## 📞 Поддержка

При возникновении проблем проверьте:
1. Логи сервера
2. Таблицу `sync_logs` в базе данных
3. Доступность API MoySklad и Sales Doctor
