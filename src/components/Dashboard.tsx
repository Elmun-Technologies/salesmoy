import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  ShoppingCart,
  TrendingUp,
  Users,
  AlertTriangle,
  RefreshCw,
  Clock,
  Package,
  Wallet,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import { getOrders, getStock, getClients, getDebts, getLogs } from '../services/api';

const COLORS = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'];

function formatMoney(n: number) {
  return new Intl.NumberFormat('ru-RU').format(n);
}

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
  color,
  delay,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  sub?: string;
  color: string;
  delay: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.4 }}
      className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm hover:shadow-md transition-shadow"
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-slate-500 text-sm font-medium">{label}</p>
          <p className="text-2xl font-bold text-slate-900 mt-1">{value}</p>
          {sub && <p className="text-xs text-slate-400 mt-1">{sub}</p>}
        </div>
        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${color}`}>
          <Icon className="w-5 h-5 text-white" />
        </div>
      </div>
    </motion.div>
  );
}

export default function Dashboard() {
  const [syncTime, setSyncTime] = useState<Date | null>(null);
  const [stats, setStats] = useState({
    totalOrders: 0,
    ordersToday: 0,
    totalRevenue: 0,
    revenueToday: 0,
    activeAgents: 4,
    syncErrors: 0,
    pendingSync: 0,
    lowStock: 0,
    debtRisk: 0,
  });
  const [statusData, setStatusData] = useState<{name: string; value: number}[]>([]);
  const [agentSales, setAgentSales] = useState<any[]>([]);
  const [monthlyRevenue, setMonthlyRevenue] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const [orders, stock, clients, , logs] = await Promise.all([
          getOrders(),
          getStock(),
          getClients(),
          getDebts(),
          getLogs(),
        ]);

        // Use the user's local date (not UTC) — for UZ (UTC+5) UTC midnight
        // happens at 05:00 local, so orders placed before dawn would otherwise
        // be classified as yesterday.
        const now = new Date();
        const isSameLocalDay = (iso?: string) => {
          if (!iso) return false;
          const d = new Date(iso);
          if (Number.isNaN(d.getTime())) return false;
          return (
            d.getFullYear() === now.getFullYear() &&
            d.getMonth() === now.getMonth() &&
            d.getDate() === now.getDate()
          );
        };
        const todayOrders = orders.filter((o: any) => isSameLocalDay(o.createdAt));
        const revenueToday = todayOrders.reduce((sum: number, o: any) => sum + (o.total || 0), 0);
        const totalRevenue = orders.reduce((sum: number, o: any) => sum + (o.total || 0), 0);
        const lowStock = stock.filter((s: any) => s.qty > 0 && s.qty <= 5).length;
        const debtRisk = clients.filter((c: any) => c.debt > c.debtLimit * 0.8).length;
        const errors = logs.filter((l: any) => l.type === 'error').length;
        const pending = orders.filter((o: any) => o.syncStatus === 'pending').length;

        // Status distribution
        const statuses = ['Новый', 'В обработке', 'Отгружен', 'В пути', 'Доставлен', 'Отменен'];
        const statusCounts = statuses.map((s) => ({
          name: s,
          value: orders.filter((o: any) => o.status === s).length,
        }));

        // Agent sales aggregation
        const agentMap: Record<string, { orders: number; revenue: number; clients: Set<string> }> = {};
        orders.forEach((o: any) => {
          const a = o.agentName || 'Unknown';
          if (!agentMap[a]) agentMap[a] = { orders: 0, revenue: 0, clients: new Set() };
          agentMap[a].orders++;
          agentMap[a].revenue += o.total || 0;
          agentMap[a].clients.add(o.clientName);
        });
        const agents = Object.entries(agentMap)
          .map(([name, d]) => ({ name, orders: d.orders, revenue: d.revenue, clients: d.clients.size }))
          .sort((a, b) => b.revenue - a.revenue);

        // Real last-sync time: timestamp of the most recent log entry.
        // Logs are written by every sync loop iteration (success or error),
        // so this reflects whether the background loop is actually running.
        const newestLogTs = logs
          .map((l: any) => l.timestamp)
          .filter(Boolean)
          .map((t: string) => new Date(t))
          .filter((d: Date) => !Number.isNaN(d.getTime()))
          .sort((a: Date, b: Date) => b.getTime() - a.getTime())[0];
        setSyncTime(newestLogTs ?? null);

        setStats({
          totalOrders: orders.length,
          ordersToday: todayOrders.length,
          totalRevenue,
          revenueToday,
          activeAgents: Object.keys(agentMap).length || 4,
          syncErrors: errors,
          pendingSync: pending,
          lowStock,
          debtRisk,
        });
        setStatusData(statusCounts);
        setAgentSales(agents);

        // Monthly revenue mock (until we have historical data)
        setMonthlyRevenue([
          { month: 'Авг', revenue: 320000000, profit: 64000000 },
          { month: 'Сен', revenue: 380000000, profit: 76000000 },
          { month: 'Окт', revenue: 410000000, profit: 82000000 },
          { month: 'Ноя', revenue: 450000000, profit: 90000000 },
          { month: 'Дек', revenue: 470000000, profit: 94000000 },
          { month: 'Янв', revenue: totalRevenue || 487500000, profit: Math.round((totalRevenue || 487500000) * 0.2) },
        ]);
      } catch (e) {
        console.error('Dashboard load error:', e);
      } finally {
        setLoading(false);
      }
    }
    loadData();
    const interval = setInterval(loadData, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <RefreshCw className="w-8 h-8 text-emerald-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Дашборд интеграции</h2>
          <p className="text-slate-500 text-sm mt-1">
            Обзор синхронизации Sales Doctor ↔ MoySklad
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm text-slate-500 bg-white px-3 py-2 rounded-lg border border-slate-200">
          <Clock className="w-4 h-4" />
          {syncTime
            ? `Последняя синхронизация: ${syncTime.toLocaleString('ru-RU')}`
            : 'Последняя синхронизация: нет данных'}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={ShoppingCart}
          label="Заказов сегодня"
          value={String(stats.ordersToday)}
          sub={`Всего: ${stats.totalOrders}`}
          color="bg-emerald-500"
          delay={0}
        />
        <StatCard
          icon={TrendingUp}
          label="Выручка сегодня"
          value={`${formatMoney(stats.revenueToday)} сум`}
          sub={`Всего: ${formatMoney(stats.totalRevenue)} сум`}
          color="bg-blue-500"
          delay={0.1}
        />
        <StatCard
          icon={Users}
          label="Активные агенты"
          value={String(stats.activeAgents)}
          sub="Агенты в поле"
          color="bg-amber-500"
          delay={0.2}
        />
        <StatCard
          icon={AlertTriangle}
          label="Ошибки синхронизации"
          value={String(stats.syncErrors)}
          sub={`${stats.pendingSync} в ожидании`}
          color="bg-red-500"
          delay={0.3}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="lg:col-span-2 bg-white rounded-xl border border-slate-200 p-6 shadow-sm"
        >
          <h3 className="text-lg font-semibold text-slate-900 mb-4">Динамика выручки и прибыли</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={monthlyRevenue}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="month" stroke="#64748b" fontSize={12} />
              <YAxis stroke="#64748b" fontSize={12} tickFormatter={(v) => `${(v as number) / 1000000}M`} />
              <Tooltip
                formatter={(value) => [`${formatMoney(Number(value))} сум`, '']}
                contentStyle={{ borderRadius: 8, border: '1px solid #e2e8f0' }}
              />
              <Bar dataKey="revenue" name="Выручка" fill="#10b981" radius={[4, 4, 0, 0]} />
              <Bar dataKey="profit" name="Прибыль" fill="#3b82f6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm"
        >
          <h3 className="text-lg font-semibold text-slate-900 mb-4">Статусы заказов</h3>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie
                data={statusData}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={90}
                paddingAngle={4}
                dataKey="value"
              >
                {statusData.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
          <div className="grid grid-cols-2 gap-2 mt-2">
            {statusData.map((s, i) => (
              <div key={s.name} className="flex items-center gap-2 text-xs">
                <div
                  className="w-2.5 h-2.5 rounded-full"
                  style={{ backgroundColor: COLORS[i % COLORS.length] }}
                />
                <span className="text-slate-600">{s.name}</span>
                <span className="font-semibold text-slate-900">{s.value}</span>
              </div>
            ))}
          </div>
        </motion.div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6 }}
          className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm"
        >
          <h3 className="text-lg font-semibold text-slate-900 mb-4">Продажи по агентам</h3>
          <div className="space-y-4">
            {agentSales.map((agent, i) => (
              <div key={agent.name} className="flex items-center gap-4">
                <div className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center text-sm font-bold text-slate-600">
                  {i + 1}
                </div>
                <div className="flex-1">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium text-slate-900">{agent.name}</span>
                    <span className="text-sm font-semibold text-emerald-600">
                      {formatMoney(agent.revenue)} сум
                    </span>
                  </div>
                  <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${agent.revenue > 0 ? (agent.revenue / Math.max(...agentSales.map(a => a.revenue))) * 100 : 0}%` }}
                      transition={{ delay: 0.8 + i * 0.1, duration: 0.6 }}
                      className="h-full bg-emerald-500 rounded-full"
                    />
                  </div>
                  <div className="flex items-center gap-4 mt-1 text-xs text-slate-400">
                    <span>{agent.orders} заказов</span>
                    <span>{agent.clients} клиентов</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.7 }}
          className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm"
        >
          <h3 className="text-lg font-semibold text-slate-900 mb-4">Бизнес-правила</h3>
          <div className="space-y-3">
            <div className="flex items-start gap-3 p-3 rounded-lg bg-red-50 border border-red-100">
              <AlertTriangle className="w-5 h-5 text-red-500 mt-0.5 shrink-0" />
              <div>
                <p className="text-sm font-medium text-red-800">Лимит задолженности</p>
                <p className="text-xs text-red-600 mt-0.5">
                  {stats.debtRisk} клиентов приближаются к лимиту. Заказы блокируются при превышении.
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3 p-3 rounded-lg bg-amber-50 border border-amber-100">
              <Package className="w-5 h-5 text-amber-500 mt-0.5 shrink-0" />
              <div>
                <p className="text-sm font-medium text-amber-800">Проверка остатков</p>
                <p className="text-xs text-amber-600 mt-0.5">
                  {stats.lowStock} товаров с низким остатком. Синхронизация каждые 10-20 сек.
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3 p-3 rounded-lg bg-blue-50 border border-blue-100">
              <RefreshCw className="w-5 h-5 text-blue-500 mt-0.5 shrink-0" />
              <div>
                <p className="text-sm font-medium text-blue-800">Дубликаты клиентов</p>
                <p className="text-xs text-blue-600 mt-0.5">
                  Автоматическое объединение по телефону или имени. Проверка при каждой синхронизации.
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3 p-3 rounded-lg bg-emerald-50 border border-emerald-100">
              <Wallet className="w-5 h-5 text-emerald-500 mt-0.5 shrink-0" />
              <div>
                <p className="text-sm font-medium text-emerald-800">Дебиторка</p>
                <p className="text-xs text-emerald-600 mt-0.5">
                  Автоматическая синхронизация платежей и остатков долга. Обновление каждые 10 минут.
                </p>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
