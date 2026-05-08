import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  FileText,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Info,
  RotateCcw,
  Filter,
  Search,
  Clock,
  RefreshCw,
} from 'lucide-react';
import { getLogs, getLogStats } from '../services/api';

const typeConfig: Record<string, { icon: React.ElementType; color: string; bg: string; label: string }> = {
  success: { icon: CheckCircle2, color: 'text-emerald-600', bg: 'bg-emerald-50 border-emerald-200', label: 'Успех' },
  info: { icon: Info, color: 'text-blue-600', bg: 'bg-blue-50 border-blue-200', label: 'Инфо' },
  warning: { icon: AlertTriangle, color: 'text-amber-600', bg: 'bg-amber-50 border-amber-200', label: 'Предупр.' },
  error: { icon: XCircle, color: 'text-red-600', bg: 'bg-red-50 border-red-200', label: 'Ошибка' },
};

interface LogEntry {
  id: string;
  timestamp: string;
  type: string;
  module: string;
  message: string;
  retryCount?: number;
}

export default function LogsPanel() {
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [stats, setStats] = useState({ total: 0, success: 0, error: 0, warning: 0 });
  const [loading, setLoading] = useState(true);

  async function loadData() {
    setLoading(true);
    try {
      const [logsData, statsData] = await Promise.all([
        getLogs(),
        getLogStats(),
      ]);
      setLogs(logsData);
      setStats(statsData);
    } catch (e) {
      console.error('Logs load error:', e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 30000);
    return () => clearInterval(interval);
  }, []);

  const filtered = logs.filter((l) => {
    const matchesSearch = l.message?.toLowerCase().includes(search.toLowerCase()) || l.module?.toLowerCase().includes(search.toLowerCase());
    const matchesType = typeFilter === 'all' || l.type === typeFilter;
    return matchesSearch && matchesType;
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Логи и ошибки</h2>
          <p className="text-slate-500 text-sm mt-1">
            Логирование всех операций синхронизации. Retry: 3 попытки.
          </p>
        </div>
        <button
          onClick={loadData}
          className="flex items-center gap-2 text-sm text-slate-600 bg-white px-3 py-2 rounded-lg border border-slate-200 hover:bg-slate-50"
        >
          <RefreshCw className="w-4 h-4" />
          Обновить
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-slate-100 flex items-center justify-center">
            <FileText className="w-5 h-5 text-slate-600" />
          </div>
          <div>
            <p className="text-2xl font-bold text-slate-900">{stats.total}</p>
            <p className="text-xs text-slate-500">Всего записей</p>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-emerald-100 flex items-center justify-center">
            <CheckCircle2 className="w-5 h-5 text-emerald-600" />
          </div>
          <div>
            <p className="text-2xl font-bold text-slate-900">{stats.success}</p>
            <p className="text-xs text-slate-500">Успешно</p>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-amber-100 flex items-center justify-center">
            <AlertTriangle className="w-5 h-5 text-amber-600" />
          </div>
          <div>
            <p className="text-2xl font-bold text-slate-900">{stats.warning}</p>
            <p className="text-xs text-slate-500">Предупреждения</p>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-red-100 flex items-center justify-center">
            <XCircle className="w-5 h-5 text-red-600" />
          </div>
          <div>
            <p className="text-2xl font-bold text-slate-900">{stats.error}</p>
            <p className="text-xs text-slate-500">Ошибки</p>
          </div>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Поиск по сообщению или модулю..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-slate-400" />
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="px-3 py-2.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
          >
            <option value="all">Все типы</option>
            <option value="success">Успех</option>
            <option value="info">Инфо</option>
            <option value="warning">Предупреждение</option>
            <option value="error">Ошибка</option>
          </select>
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
                  <th className="text-left px-4 py-3 font-semibold text-slate-700">Время</th>
                  <th className="text-left px-4 py-3 font-semibold text-slate-700">Тип</th>
                  <th className="text-left px-4 py-3 font-semibold text-slate-700">Модуль</th>
                  <th className="text-left px-4 py-3 font-semibold text-slate-700">Сообщение</th>
                  <th className="text-left px-4 py-3 font-semibold text-slate-700">Retry</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((log, i) => {
                  const TypeIcon = typeConfig[log.type]?.icon || Info;
                  return (
                    <motion.tr
                      key={log.id}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.02 }}
                      className="border-b border-slate-100 hover:bg-slate-50 transition-colors"
                    >
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span className="flex items-center gap-1 text-slate-500">
                          <Clock className="w-3 h-3" />
                          {log.timestamp ? new Date(log.timestamp).toLocaleTimeString('ru-RU') : '-'}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium border ${typeConfig[log.type]?.bg}`}
                        >
                          <TypeIcon className={`w-3 h-3 ${typeConfig[log.type]?.color}`} />
                          {typeConfig[log.type]?.label}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-medium text-slate-700">{log.module}</td>
                      <td className="px-4 py-3 text-slate-600">{log.message}</td>
                      <td className="px-4 py-3">
                        {log.retryCount !== undefined ? (
                          <span className="inline-flex items-center gap-1 text-amber-600">
                            <RotateCcw className="w-3 h-3" />
                            {log.retryCount}/3
                          </span>
                        ) : (
                          <span className="text-slate-300">—</span>
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
