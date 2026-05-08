import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  UserCheck,
  ShoppingCart,
  TrendingUp,
  RefreshCw,
  MapPin,
  Mail,
  Users,
} from 'lucide-react';
import { getAgents, getAgentStats } from '../services/api';

function formatMoney(n: number) {
  return new Intl.NumberFormat('ru-RU').format(n);
}

interface Agent {
  id: number;
  name: string;
  email: string;
  isActive: boolean;
  ordersCount: number;
  totalSales: number;
  createdAt: string;
}

interface AgentStats {
  totalAgents: number;
  activeAgents: number;
}

export default function AgentsPanel() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [stats, setStats] = useState<AgentStats>({ totalAgents: 0, activeAgents: 0 });
  const [loading, setLoading] = useState(true);

  async function loadData() {
    setLoading(true);
    try {
      const [agentsData, statsData] = await Promise.all([
        getAgents(),
        getAgentStats(),
      ]);
      setAgents(agentsData);
      setStats(statsData);
    } catch (e) {
      console.error('Agents load error:', e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 60000);
    return () => clearInterval(interval);
  }, []);

  const topAgent = agents.length > 0
    ? agents.reduce((a, b) => (a.ordersCount > b.ordersCount ? a : b))
    : null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Agentlar boshqaruvi</h2>
          <p className="text-slate-500 text-sm mt-1">
            Sales Doctor agentlari — buyurtmalar va hududlar bo'yicha
          </p>
        </div>
        <button
          onClick={loadData}
          className="flex items-center gap-2 text-sm text-slate-600 bg-white px-3 py-2 rounded-lg border border-slate-200 hover:bg-slate-50"
        >
          <RefreshCw className="w-4 h-4" />
          Yangilash
        </button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-emerald-100 flex items-center justify-center">
              <Users className="w-5 h-5 text-emerald-600" />
            </div>
            <div>
              <p className="text-xs text-slate-500">Jami agentlar</p>
              <p className="text-2xl font-bold text-slate-900">{stats.totalAgents}</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center">
              <UserCheck className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <p className="text-xs text-slate-500">Faol agentlar</p>
              <p className="text-2xl font-bold text-slate-900">{stats.activeAgents}</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-amber-100 flex items-center justify-center">
              <TrendingUp className="w-5 h-5 text-amber-600" />
            </div>
            <div>
              <p className="text-xs text-slate-500">Eng yaxshi agent</p>
              <p className="text-sm font-bold text-slate-900 truncate max-w-[120px]">
                {topAgent ? topAgent.name : '—'}
              </p>
              {topAgent && (
                <p className="text-xs text-slate-400">{topAgent.ordersCount} ta buyurtma</p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Agents list */}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="w-8 h-8 text-emerald-500 animate-spin" />
        </div>
      ) : agents.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center shadow-sm">
          <Users className="w-12 h-12 text-slate-300 mx-auto mb-3" />
          <p className="text-slate-500 font-medium">Hali agent yo'q</p>
          <p className="text-slate-400 text-sm mt-1">
            Sozlamalardan agent rolida foydalanuvchi qo'shing
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {agents.map((agent, i) => (
            <motion.div
              key={agent.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm hover:shadow-md transition-shadow"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-emerald-100 flex items-center justify-center font-bold text-emerald-700 text-sm">
                    {agent.name.charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <h3 className="font-semibold text-slate-900 text-sm">{agent.name}</h3>
                    <div className="flex items-center gap-1 text-xs text-slate-400 mt-0.5">
                      <Mail className="w-3 h-3" />
                      {agent.email}
                    </div>
                  </div>
                </div>
                <span
                  className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                    agent.isActive
                      ? 'bg-emerald-50 text-emerald-600'
                      : 'bg-slate-100 text-slate-400'
                  }`}
                >
                  {agent.isActive ? 'Faol' : 'Nofaol'}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="bg-slate-50 rounded-lg p-3">
                  <div className="flex items-center gap-1.5 text-xs text-slate-500 mb-1">
                    <ShoppingCart className="w-3.5 h-3.5" />
                    Buyurtmalar
                  </div>
                  <p className="text-lg font-bold text-slate-900">{agent.ordersCount}</p>
                </div>
                <div className="bg-slate-50 rounded-lg p-3">
                  <div className="flex items-center gap-1.5 text-xs text-slate-500 mb-1">
                    <TrendingUp className="w-3.5 h-3.5" />
                    Savdo
                  </div>
                  <p className="text-sm font-bold text-emerald-600">
                    {formatMoney(agent.totalSales)}
                  </p>
                </div>
              </div>

              <div className="mt-3 flex items-center gap-1.5 text-xs text-slate-400">
                <MapPin className="w-3 h-3" />
                <span>Navigatsiya: Sales Doctor ilovasida</span>
              </div>
            </motion.div>
          ))}
        </div>
      )}

      {/* Info block */}
      <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-sm text-emerald-800">
        <strong>Navigatsiya haqida:</strong> Agentlar Sales Doctor mobil ilovasida hududlar bo'yicha
        mijozlarga yo'l oladi. Har bir buyurtma MoySkladga avtomatik yuboriladi.
        Qarz ma'lumotlari ham Sales Doctor va MoySkladdan sinxronlashadi.
      </div>
    </div>
  );
}
