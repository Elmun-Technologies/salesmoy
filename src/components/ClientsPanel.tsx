import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  Users,
  Search,
  MapPin,
  Phone,
  Building2,
  User,
  ArrowRightLeft,
  CheckCircle2,
  AlertTriangle,
  Merge,
  RefreshCw,
} from 'lucide-react';
import { getClients, syncClients, getClientStats } from '../services/api';

function formatMoney(n: number) {
  return new Intl.NumberFormat('ru-RU').format(n);
}

interface Client {
  id: string;
  name: string;
  phone: string;
  address: string;
  location: string;
  type: string;
  debt: number;
  debtLimit: number;
  lastOrder: string;
}

export default function ClientsPanel() {
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [clients, setClients] = useState<Client[]>([]);
  const [stats, setStats] = useState({ total: 0, wholesale: 0, retail: 0, debtRisk: 0 });
  const [loading, setLoading] = useState(true);

  async function loadData() {
    setLoading(true);
    try {
      const [clientsData, statsData] = await Promise.all([
        getClients(),
        getClientStats(),
      ]);
      setClients(clientsData);
      setStats(statsData);
    } catch (e) {
      console.error('Clients load error:', e);
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
      await syncClients();
      loadData();
    } catch (e) {
      console.error('Clients sync error:', e);
    }
  }

  const filtered = clients.filter((c) => {
    const matchesSearch =
      c.name?.toLowerCase().includes(search.toLowerCase()) ||
      c.phone?.includes(search);
    const matchesType = typeFilter === 'all' || c.type === typeFilter;
    return matchesSearch && matchesType;
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Синхронизация клиентов</h2>
          <p className="text-slate-500 text-sm mt-1">
            Двусторонняя синхронизация: Sales Doctor ↔ MoySklad
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
            Двусторонняя
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center">
            <Users className="w-5 h-5 text-blue-600" />
          </div>
          <div>
            <p className="text-2xl font-bold text-slate-900">{stats.total}</p>
            <p className="text-xs text-slate-500">Всего клиентов</p>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-purple-100 flex items-center justify-center">
            <Building2 className="w-5 h-5 text-purple-600" />
          </div>
          <div>
            <p className="text-2xl font-bold text-slate-900">{stats.wholesale}</p>
            <p className="text-xs text-slate-500">Оптовики</p>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-emerald-100 flex items-center justify-center">
            <User className="w-5 h-5 text-emerald-600" />
          </div>
          <div>
            <p className="text-2xl font-bold text-slate-900">{stats.retail}</p>
            <p className="text-xs text-slate-500">Розница</p>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-red-100 flex items-center justify-center">
            <AlertTriangle className="w-5 h-5 text-red-600" />
          </div>
          <div>
            <p className="text-2xl font-bold text-slate-900">{stats.debtRisk}</p>
            <p className="text-xs text-slate-500">Риск долга</p>
          </div>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Поиск по имени или телефону..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
        </div>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="px-3 py-2.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
        >
          <option value="all">Все типы</option>
          <option value="Опт">Опт</option>
          <option value="Розница">Розница</option>
        </select>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="w-8 h-8 text-emerald-500 animate-spin" />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filtered.map((client, i) => {
            const debtPercent = client.debtLimit > 0 ? (client.debt / client.debtLimit) * 100 : 0;
            const isRisk = debtPercent > 80;
            return (
              <motion.div
                key={client.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm hover:shadow-md transition-shadow"
              >
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h4 className="font-semibold text-slate-900">{client.name}</h4>
                    <div className="flex items-center gap-2 mt-1">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${
                          client.type === 'Опт'
                            ? 'bg-purple-50 text-purple-600 border border-purple-200'
                            : 'bg-emerald-50 text-emerald-600 border border-emerald-200'
                        }`}
                      >
                        {client.type === 'Опт' ? <Building2 className="w-3 h-3" /> : <User className="w-3 h-3" />}
                        {client.type}
                      </span>
                      <span className="text-xs text-slate-400">ID: {client.id}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-1 text-emerald-600">
                    <CheckCircle2 className="w-4 h-4" />
                    <span className="text-xs font-medium">Синхр.</span>
                  </div>
                </div>

                <div className="space-y-2 text-sm">
                  <div className="flex items-center gap-2 text-slate-600">
                    <Phone className="w-3.5 h-3.5 text-slate-400" />
                    {client.phone}
                  </div>
                  <div className="flex items-center gap-2 text-slate-600">
                    <MapPin className="w-3.5 h-3.5 text-slate-400" />
                    {client.address}
                  </div>
                  <div className="flex items-center gap-2 text-slate-600">
                    <MapPin className="w-3.5 h-3.5 text-slate-400" />
                    {client.location}
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-slate-100">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs text-slate-500">Задолженность</span>
                    <span className={`text-xs font-semibold ${isRisk ? 'text-red-600' : 'text-slate-700'}`}>
                      {formatMoney(client.debt)} / {formatMoney(client.debtLimit)} сум
                    </span>
                  </div>
                  <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${
                        isRisk ? 'bg-red-500' : debtPercent > 50 ? 'bg-amber-500' : 'bg-emerald-500'
                      }`}
                      style={{ width: `${Math.min(debtPercent, 100)}%` }}
                    />
                  </div>
                  {isRisk && (
                    <div className="flex items-center gap-1 mt-2 text-xs text-red-600">
                      <AlertTriangle className="w-3 h-3" />
                      Превышен лимит задолженности
                    </div>
                  )}
                </div>

                <div className="mt-3 flex items-center gap-2 text-xs text-slate-400">
                  <Merge className="w-3 h-3" />
                  Дубликат проверка: телефон + имя
                </div>
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
}
