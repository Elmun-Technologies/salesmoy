# Currency Conversion: USD ↔ UZS

## Problem
MoySklad prices are stored in **USD**, but Sales Doctor expects prices in **UZS (Sum)**.
When syncing orders, prices were not being converted, causing incorrect amounts in Sales Doctor.

**Example of the bug:**
- MoySklad price: `24.47$`
- Sales Doctor received: `2.447 sum` ❌ (should be `310,647 sum`)

## Solution
Added automatic currency conversion when syncing from MoySklad to Sales Doctor.

### Configuration
Set the USD → UZS exchange rate in `.env`:
```env
USD_TO_UZS_RATE=12695
```

Check current rate at: https://www.uzex.uz/

### Implementation
1. **`backend/utils/currency.py`** — Conversion utility function
   ```python
   from utils.currency import convert_usd_to_uzs
   
   price_uzs = convert_usd_to_uzs(24.47)  # Returns 310,647
   ```

2. **Conversion happens at sync points:**
   - ✅ Order prices → Sales Doctor
   - ✅ Stock/product prices → Sales Doctor
   - ✅ Order retry mechanism

### Sync Flows
```
MoySklad (USD) --[convert_usd_to_uzs]--> Sales Doctor (UZS)
```

### Testing
```bash
cd backend
python3 -c "from utils.currency import convert_usd_to_uzs; print(convert_usd_to_uzs(24.47))"
# Output: 310647
```

### Future Improvements
- [ ] Add reverse conversion (UZS → USD) when syncing SD orders to MoySklad
- [ ] Support multiple currencies (EUR, RUB, etc.)
- [ ] Add dynamic exchange rate fetching from API
