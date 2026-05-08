import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  Package,
  Search,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Warehouse,
  ArrowDownUp,
} from 'lucide-react';
import { getStock, syncStock } from '../services/api';

function formatMoney(n: number) {
  return new Intl.NumberFormat('ru-RU').format(n);
}

interface StockItem {
  sku: string;
  name: string;
  qty: number;
  price: number;
  warehouse: string;
  lastSync: string;
}

export default function StockPanel() {
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState<'name' | 'qty' | 'price'>('name');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [stockItems, setStockItems] = useState<StockItem[]>([]);
  const [loading, setLoading] = useState(true);

  async function loadStock() {
    setLoading(true);
    try {
      const data = await getStock();
      setStockItems(data);
    } catch (e) {
      console.error('Stock load error:', e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadStock();
    const interval = setInterval(loadStock, 30000);
    return () => clearInterval(interval);
  }, []);

  async function handleSync() {
    try {
      await syncStock();
      loadStock();
    } catch (e) {
      console.error('Stock sync error:', e);
    }
  }

  const filtered = stockItems
    .filter(
      (s) =>
        s.name?.toLowerCase().includes(search.toLowerCase()) ||
        s.sku?.toLowerCase().includes(search.toLowerCase())
    )
    .sort((a, b) => {
      const dir = sortDir === 'asc' ? 1 : -1;
      if (sortBy === 'name') return (a.name || '').localeCompare(b.name || '') * dir;
      if (sortBy === 'qty') return ((a.qty || 0) - (b.qty || 0)) * dir;
      return ((a.price || 0) - (b.price || 0)) * dir;
    });

  const lowStock = stockItems.filter((s) => s.qty > 0 && s.qty <= 5).length;
  const outOfStock = stockItems.filter((s) => s.qty === 0).length;

  const toggleSort = (field: 'name' | 'qty' | 'price') => {
    if (sortBy === field) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else {
      setSortBy(field);
      setSortDir('asc');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Остатки на складе</h2>
          <p className="text-slate-500 text-sm mt-1">
            Синхронизация MoySklad → Sales Doctor (каждые 10–20 сек)
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleSync}
            className="flex items-center gap-2 text-sm text-slate-600 bg-white px-3 py-2 rounded-lg border border-slate-200 hover:bg-slate-50"
          >
            <RefreshCw className="w-4 h-4" />
            Синхронизировать
          </button>
          <div className="flex items-center gap-2 text-sm text-emerald-600 bg-emerald-50 px-3 py-2 rounded-lg border border-emerald-200">
            <RefreshCw className="w-4 h-4 animate-spin" />
            Авто-синхронизация
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center">
            <Package className="w-5 h-5 text-blue-600" />
          </div>
          <div>
            <p className="text-2xl font-bold text-slate-900">{stockItems.length}</p>
            <p className="text-xs text-slate-500">Всего SKU</p>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-amber-100 flex items-center justify-center">
            <AlertTriangle className="w-5 h-5 text-amber-600" />
          </div>
          <div>
            <p className="text-2xl font-bold text-slate-900">{lowStock}</p>
            <p className="text-xs text-slate-500">Низкий остаток</p>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-red-100 flex items-center justify-center">
            <AlertTriangle className="w-5 h-5 text-red-600" />
          </div>
          <div>
            <p className="text-2xl font-bold text-slate-900">{outOfStock}</p>
            <p className="text-xs text-slate-500">Отсутствует</p>
          </div>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Поиск по SKU или названию..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="w-8 h-8 text-emerald-500 animate-spin" />
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200">
                  <th
                    className="text-left px-4 py-3 font-semibold text-slate-700 cursor-pointer hover:text-emerald-600"
                    onClick={() => toggleSort('name')}
                  >
                    <span className="flex items-center gap-1">
                      Название <ArrowDownUp className="w-3 h-3" />
                    </span>
                  </th>
                  <th className="text-left px-4 py-3 font-semibold text-slate-700">SKU</th>
                  <th
                    className="text-left px-4 py-3 font-semibold text-slate-700 cursor-pointer hover:text-emerald-600"
                    onClick={() => toggleSort('qty')}
                  >
                    <span className="flex items-center gap-1">
                      Остаток <ArrowDownUp className="w-3 h-3" />
                    </span>
                  </th>
                  <th
                    className="text-right px-4 py-3 font-semibold text-slate-700 cursor-pointer hover:text-emerald-600"
                    onClick={() => toggleSort('price')}
                  >
                    <span className="flex items-center gap-1 justify-end">
                      Цена <ArrowDownUp className="w-3 h-3" />
                    </span>
                  </th>
                  <th className="text-left px-4 py-3 font-semibold text-slate-700">Склад</th>
                  <th className="text-left px-4 py-3 font-semibold text-slate-700">Статус</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((item, i) => (
                  <motion.tr
                    key={item.sku}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.03 }}
                    className="border-b border-slate-100 hover:bg-slate-50 transition-colors"
                  >
                    <td className="px-4 py-3 font-medium text-slate-900">{item.name}</td>
                    <td className="px-4 py-3 font-mono text-slate-500">{item.sku}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`font-semibold ${
                          item.qty === 0
                            ? 'text-red-600'
                            : item.qty <= 5
                            ? 'text-amber-600'
                            : 'text-emerald-600'
                        }`}
                      >
                        {item.qty}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right font-medium text-slate-900">
                      {formatMoney(item.price)} сум
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center gap-1 text-slate-600">
                        <Warehouse className="w-3.5 h-3.5" />
                        {item.warehouse}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {item.qty === 0 ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-red-50 text-red-600 border border-red-200">
                          <AlertTriangle className="w-3 h-3" />
                          Нет в наличии
                        </span>
                      ) : item.qty <= 5 ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-amber-50 text-amber-600 border border-amber-200">
                          <AlertTriangle className="w-3 h-3" />
                          Низкий остаток
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-emerald-50 text-emerald-600 border border-emerald-200">
                          <CheckCircle2 className="w-3 h-3" />
                          В наличии
                        </span>
                      )}
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
