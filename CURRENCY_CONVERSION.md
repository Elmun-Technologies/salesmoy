# Currency Conversion: USD ↔ UZS

## Problem
MoySklad prices are stored in **USD**, but Sales Doctor expects prices in **UZS (Sum)**.
When syncing orders, prices were not being converted, causing incorrect amounts in Sales Doctor.

**Example of the bug:**
- MoySklad price: `24.47$`
- Sales Doctor received: `2.447 sum` ❌ (should be `310,647 sum`)

## Solution
Added automatic currency conversion with **live daily rate updates** when syncing from MoySklad to Sales Doctor.

### Configuration
Set default exchange rate in `.env`:
```env
USD_TO_UZS_RATE=12695
```

### How It Works
The system uses **two-tier rate management**:

1. **Live rates (UZEX API)**
   - Automatically fetches daily rate from Uzbekistan Exchange
   - Cached per day to minimize API calls
   - Provides most accurate pricing

2. **Fallback rate (config)**
   - If live fetch fails, uses `USD_TO_UZS_RATE` from `.env`
   - Ensures conversions never fail

**Update frequency:** Once per calendar day (automatic)

### Implementation
1. **`backend/services/exchange_rate.py`** — Rate fetching & caching
   ```python
   from services.exchange_rate import get_usd_to_uzs_rate
   
   rate = await get_usd_to_uzs_rate()  # Fetches or uses cache
   ```

2. **`backend/utils/currency.py`** — Conversion utilities
   ```python
   from utils.currency import convert_usd_to_uzs, convert_usd_to_uzs_with_live_rate
   
   # Sync-friendly: converts with live rate (async)
   price_uzs = await convert_usd_to_uzs_with_live_rate(24.47)  # 310,647
   
   # Direct: converts with provided/default rate (sync)
   price_uzs = convert_usd_to_uzs(24.47, rate=12695)  # 310,647
   ```

3. **Conversion happens at all sync points:**
   - ✅ Order prices → Sales Doctor
   - ✅ Stock/product prices → Sales Doctor
   - ✅ Order retry mechanism

### Sync Flows
```
Daily:
  UZEX ──→ Cache (per-date)
            ↓
            Live rate

MoySklad (USD) ──[live rate]──→ Sales Doctor (UZS)
   24.47$        ×12,695    →  310,647 sum
```

### Testing
```bash
cd backend

# Test cache (both should use same rate if called same day)
python3 << 'EOF'
import asyncio
from services.exchange_rate import get_usd_to_uzs_rate

async def test():
    rate1 = await get_usd_to_uzs_rate()
    rate2 = await get_usd_to_uzs_rate()
    print(f"Rate (call 1): {rate1}")
    print(f"Rate (call 2): {rate2} (cached)")

asyncio.run(test())
EOF

# Test conversion
python3 -c "from utils.currency import convert_usd_to_uzs; print(f'24.47$ = {convert_usd_to_uzs(24.47):,} sum')"
# Output: 24.47$ = 310,647 sum
```

### Manual Rate Update
If you need to test with a specific rate or bypass live fetch:
```bash
python3 << 'EOF'
from services.exchange_rate import clear_rate_cache
clear_rate_cache()  # Force refresh on next call
EOF
```

### Monitoring
Check system logs for exchange rate updates:
```bash
# Live rate fetched successfully
grep "Exchange rate USD→UZS" /var/log/app.log

# Fallback to config default
grep "Could not fetch exchange rate" /var/log/app.log
```

### Future Improvements
- [ ] Add reverse conversion (UZS → USD) when syncing SD orders to MoySklad
- [ ] Support multiple currencies (EUR, RUB, GBP, etc.)
- [ ] Admin dashboard for exchange rate history
- [ ] Manual rate override via UI
