import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  Wallet,
  TrendingDown,
  TrendingUp,
  AlertTriangle,
  RefreshCw,
  User,
  Phone,
  ArrowRightLeft,
} from 'lucide-react';
import { getDebts, getDebtSummary, syncDebts } from '../services/api';

function formatMoney(n: number) {
  return new Intl.NumberFormat('ru-RU').format(n);
}

interface DebtRecord {
  clientName: string;
  phone: string;
  totalDebt: number;
  paid: number;
  remaining: number;
  lastPayment: string;
}

export default function DebtsPanel() {
  const [debts, setDebts] = useState<DebtRecord[]>([]);
  const [summary, setSummary] = useState({ totalDebt: 0, totalPaid: 0, totalRemaining: 0 });
  const [loading, setLoading] = useState(true);

  async function loadData() {
    setLoading(true);
    try {
      const [debtsData, summaryData] = await Promise.all([
        getDebts(),
        getDebtSummary(),
      ]);
      setDebts(debtsData);
      setSummary(summaryData);
    } catch (e) {
      console.error('Debts load error:', e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 60000);
    return () => clearInterval(interval);
  }, []);

  async function handleSync() {
    try {
      await syncDebts();
      loadData();
    } catch (e) {
      console.error('Debts sync error:', e);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Дебиторская задолженность</h2>
          <p className="text-slate-500 text-sm mt-1">
            Синхронизация MoySklad → Sales Doctor (триггер: платеж / изменение долга)
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
            <ArrowRightLeft className="w-4 h-4" />
            MoySklad → Sales Doctor
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-lg bg-red-100 flex items-center justify-center">
              <TrendingDown className="w-5 h-5 text-red-600" />
            </div>
            <div>
              <p className="text-xs text-slate-500">Общая задолженность</p>
              <p className="text-xl font-bold text-slate-900">{formatMoney(summary.totalDebt)} сум</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-lg bg-emerald-100 flex items-center justify-center">
              <TrendingUp className="w-5 h-5 text-emerald-600" />
            </div>
            <div>
              <p className="text-xs text-slate-500">Оплачено</p>
              <p className="text-xl font-bold text-slate-900">{formatMoney(summary.totalPaid)} сум</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-lg bg-amber-100 flex items-center justify-center">
              <Wallet className="w-5 h-5 text-amber-600" />
            </div>
            <div>
              <p className="text-xs text-slate-500">Остаток долга</p>
              <p className="text-xl font-bold text-slate-900">{formatMoney(summary.totalRemaining)} сум</p>
            </div>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="w-8 h-8 text-emerald-500 animate-spin" />
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="p-4 border-b border-slate-200 flex items-center justify-between">
            <h3 className="font-semibold text-slate-900">Детализация по клиентам</h3>
            <div className="flex items-center gap-1 text-xs text-slate-400">
              <RefreshCw className="w-3 h-3" />
              Обновлено: {new Date().toLocaleTimeString('ru-RU')}
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200">
                  <th className="text-left px-4 py-3 font-semibold text-slate-700">Клиент</th>
                  <th className="text-left px-4 py-3 font-semibold text-slate-700">Телефон</th>
                  <th className="text-right px-4 py-3 font-semibold text-slate-700">Общий долг</th>
                  <th className="text-right px-4 py-3 font-semibold text-slate-700">Оплачено</th>
                  <th className="text-right px-4 py-3 font-semibold text-slate-700">Остаток</th>
                  <th className="text-left px-4 py-3 font-semibold text-slate-700">Посл. платеж</th>
                  <th className="text-left px-4 py-3 font-semibold text-slate-700">Статус</th>
                </tr>
              </thead>
              <tbody>
                {debts.map((debt, i) => {
                  const percent = debt.totalDebt > 0 ? (debt.remaining / debt.totalDebt) * 100 : 0;
                  const isHigh = percent > 70;
                  return (
                    <motion.tr
                      key={debt.clientName + i}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.04 }}
                      className="border-b border-slate-100 hover:bg-slate-50 transition-colors"
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div className="w-7 h-7 rounded-full bg-slate-100 flex items-center justify-center">
                            <User className="w-3.5 h-3.5 text-slate-500" />
                          </div>
                          <span className="font-medium text-slate-900">{debt.clientName}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className="flex items-center gap-1 text-slate-500">
                          <Phone className="w-3 h-3" />
                          {debt.phone}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right font-medium text-slate-900">
                        {formatMoney(debt.totalDebt)} сум
                      </td>
                      <td className="px-4 py-3 text-right font-medium text-emerald-600">
                        {formatMoney(debt.paid)} сум
                      </td>
                      <td className="px-4 py-3 text-right font-bold text-slate-900">
                        {formatMoney(debt.remaining)} сум
                      </td>
                      <td className="px-4 py-3 text-slate-500">
                        {debt.lastPayment ? new Date(debt.lastPayment).toLocaleDateString('ru-RU') : '-'}
                      </td>
                      <td className="px-4 py-3">
                        {isHigh ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-red-50 text-red-600 border border-red-200">
                            <AlertTriangle className="w-3 h-3" />
                            Высокий риск
                          </span>
                        ) : debt.remaining > 0 ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-amber-50 text-amber-600 border border-amber-200">
                            <Wallet className="w-3 h-3" />
                            Есть долг
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-emerald-50 text-emerald-600 border border-emerald-200">
                            <TrendingUp className="w-3 h-3" />
                            Погашено
                          </span>
                        )}
                      </td>
                    </motion.tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
