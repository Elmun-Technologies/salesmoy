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
  ChevronLeft,
  ChevronRight,
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

const PAGE_SIZE_OPTIONS = [20, 50, 100];

export default function StockPanel() {
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState<'name' | 'qty' | 'price'>('name');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [stockItems, setStockItems] = useState<StockItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);

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

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const safePage = Math.min(page, totalPages);
  const pageItems = filtered.slice((safePage - 1) * pageSize, safePage * pageSize);

  const lowStock = stockItems.filter((s) => s.qty > 0 && s.qty <= 5).length;
  const outOfStock = stockItems.filter((s) => s.qty === 0).length;

  const toggleSort = (field: 'name' | 'qty' | 'price') => {
    if (sortBy === field) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else {
      setSortBy(field);
      setSortDir('asc');
    }
    setPage(1);
  };

  // Reset to page 1 when search changes
  function handleSearch(val: string) {
    setSearch(val);
    setPage(1);
  }

  function handlePageSize(val: number) {
    setPageSize(val);
    setPage(1);
  }

  // Page number buttons (show max 5 around current)
  function pageNumbers(): (number | '...')[] {
    if (totalPages <= 7) return Array.from({ length: totalPages }, (_, i) => i + 1);
    const result: (number | '...')[] = [1];
    if (safePage > 3) result.push('...');
    for (let i = Math.max(2, safePage - 1); i <= Math.min(totalPages - 1, safePage + 1); i++) {
      result.push(i);
    }
    if (safePage < totalPages - 2) result.push('...');
    result.push(totalPages);
    return result;
  }

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
            onChange={(e) => handleSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="w-8 h-8 text-emerald-500 animate-spin" />
        </div>
      ) : (
        <>
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
                  {pageItems.map((item, i) => (
                    <motion.tr
                      key={item.sku}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: Math.min(i * 0.02, 0.3) }}
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

          {/* Pagination controls */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <span>Показать:</span>
              {PAGE_SIZE_OPTIONS.map((sz) => (
                <button
                  key={sz}
                  onClick={() => handlePageSize(sz)}
                  className={`px-3 py-1.5 rounded-lg border text-sm font-medium transition-colors ${
                    pageSize === sz
                      ? 'bg-emerald-600 text-white border-emerald-600'
                      : 'bg-white text-slate-600 border-slate-200 hover:border-emerald-400'
                  }`}
                >
                  {sz}
                </button>
              ))}
              <span className="ml-2 text-slate-400">
                {(safePage - 1) * pageSize + 1}–{Math.min(safePage * pageSize, filtered.length)} / {filtered.length}
              </span>
            </div>

            <div className="flex items-center gap-1">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={safePage === 1}
                className="p-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>

              {pageNumbers().map((n, i) =>
                n === '...' ? (
                  <span key={`dots-${i}`} className="px-2 text-slate-400 text-sm">…</span>
                ) : (
                  <button
                    key={n}
                    onClick={() => setPage(n as number)}
                    className={`w-8 h-8 rounded-lg text-sm font-medium transition-colors ${
                      safePage === n
                        ? 'bg-emerald-600 text-white'
                        : 'border border-slate-200 text-slate-600 hover:bg-slate-50'
                    }`}
                  >
                    {n}
                  </button>
                )
              )}

              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={safePage === totalPages}
                className="p-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
