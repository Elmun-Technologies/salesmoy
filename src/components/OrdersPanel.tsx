import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ShoppingCart,
  Search,
  Filter,
  ArrowRightLeft,
  CheckCircle2,
  XCircle,
  Clock,
  Truck,
  PackageCheck,
  AlertCircle,
  RotateCcw,
  RefreshCw,
} from 'lucide-react';
import { getOrders, syncOrder } from '../services/api';

const statusConfig: Record<string, { icon: React.ElementType; color: string; bg: string }> = {
  'Новый': { icon: AlertCircle, color: 'text-blue-600', bg: 'bg-blue-50 border-blue-200' },
  'В обработке': { icon: Clock, color: 'text-amber-600', bg: 'bg-amber-50 border-amber-200' },
  'Отгружен': { icon: PackageCheck, color: 'text-purple-600', bg: 'bg-purple-50 border-purple-200' },
  'В пути': { icon: Truck, color: 'text-cyan-600', bg: 'bg-cyan-50 border-cyan-200' },
  'Доставлен': { icon: CheckCircle2, color: 'text-emerald-600', bg: 'bg-emerald-50 border-emerald-200' },
  'Отменен': { icon: XCircle, color: 'text-red-600', bg: 'bg-red-50 border-red-200' },
};

const syncConfig: Record<string, { label: string; color: string; bg: string }> = {
  synced: { label: 'Синхронизирован', color: 'text-emerald-600', bg: 'bg-emerald-50' },
  pending: { label: 'В ожидании', color: 'text-amber-600', bg: 'bg-amber-50' },
  error: { label: 'Ошибка', color: 'text-red-600', bg: 'bg-red-50' },
};

function formatMoney(n: number) {
  return new Intl.NumberFormat('ru-RU').format(n);
}

interface OrderItem {
  sku: string;
  name: string;
  qty: number;
  price: number;
}

interface Order {
  id: string;
  clientName: string;
  phone: string;
  agentName: string;
  items: OrderItem[];
  total: number;
  status: string;
  comment: string;
  createdAt: string;
  syncStatus: string;
  moyskladId?: string;
}

export default function OrdersPanel() {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null);
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);

  async function loadOrders() {
    setLoading(true);
    try {
      const data = await getOrders();
      setOrders(data);
    } catch (e) {
      console.error('Orders load error:', e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadOrders();
    const interval = setInterval(loadOrders, 30000);
    return () => clearInterval(interval);
  }, []);

  const filtered = orders.filter((o) => {
    const matchesSearch =
      o.clientName?.toLowerCase().includes(search.toLowerCase()) ||
      o.id?.toLowerCase().includes(search.toLowerCase()) ||
      o.agentName?.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = statusFilter === 'all' || o.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  async function handleSync(order: Order) {
    try {
      await syncOrder({
        order_id: order.id,
        client_name: order.clientName,
        phone: order.phone,
        items: order.items,
        agent_name: order.agentName,
        comment: order.comment,
      });
      loadOrders();
    } catch (e) {
      console.error('Sync error:', e);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Синхронизация заказов</h2>
          <p className="text-slate-500 text-sm mt-1">
            Sales Doctor → MoySklad и обратно (webhook + cron)
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={loadOrders}
            className="flex items-center gap-2 text-sm text-slate-600 bg-white px-3 py-2 rounded-lg border border-slate-200 hover:bg-slate-50"
          >
            <RefreshCw className="w-4 h-4" />
            Обновить
          </button>
          <div className="flex items-center gap-2 text-sm text-emerald-600 bg-emerald-50 px-3 py-2 rounded-lg border border-emerald-200">
            <ArrowRightLeft className="w-4 h-4" />
            Двусторонняя синхронизация активна
          </div>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Поиск по клиенту, ID заказа или агенту..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-slate-400" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
          >
            <option value="all">Все статусы</option>
            <option value="Новый">Новый</option>
            <option value="В обработке">В обработке</option>
            <option value="Отгружен">Отгружен</option>
            <option value="В пути">В пути</option>
            <option value="Доставлен">Доставлен</option>
            <option value="Отменен">Отменен</option>
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
                  <th className="text-left px-4 py-3 font-semibold text-slate-700">ID</th>
                  <th className="text-left px-4 py-3 font-semibold text-slate-700">Mijoz</th>
                  <th className="text-left px-4 py-3 font-semibold text-slate-700">Manba</th>
                  <th className="text-right px-4 py-3 font-semibold text-slate-700">Summa</th>
                  <th className="text-left px-4 py-3 font-semibold text-slate-700">Status</th>
                  <th className="text-left px-4 py-3 font-semibold text-slate-700">Sinxr.</th>
                  <th className="text-left px-4 py-3 font-semibold text-slate-700">Sana</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((order) => {
                  const StatusIcon = statusConfig[order.status]?.icon || AlertCircle;
                  const sync = syncConfig[order.syncStatus] || syncConfig.pending;
                  return (
                    <tr
                      key={order.id}
                      className="border-b border-slate-100 hover:bg-slate-50 transition-colors cursor-pointer"
                      onClick={() => setSelectedOrder(order)}
                    >
                      <td className="px-4 py-3 font-mono text-slate-600">{order.id}</td>
                      <td className="px-4 py-3">
                        <div className="font-medium text-slate-900">{order.clientName}</div>
                        <div className="text-xs text-slate-400">{order.phone}</div>
                      </td>
                      <td className="px-4 py-3">
                        {order.moyskladId ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-violet-50 text-violet-700 border border-violet-200">
                            MoySklad
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-500">
                            Manual
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right font-semibold text-slate-900">
                        {formatMoney(order.total)} сум
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${statusConfig[order.status]?.bg || 'bg-slate-50'}`}
                        >
                          <StatusIcon className={`w-3.5 h-3.5 ${statusConfig[order.status]?.color || ''}`} />
                          {order.status}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${sync.bg} ${sync.color}`}>
                          {sync.label}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-500">
                        {order.createdAt ? new Date(order.createdAt).toLocaleDateString('ru-RU') : '-'}
                      </td>
                      <td className="px-4 py-3">
                        <button
                          onClick={(e) => { e.stopPropagation(); handleSync(order); }}
                          className="text-slate-400 hover:text-emerald-600 transition-colors"
                          title="Синхронизировать"
                        >
                          <RotateCcw className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <AnimatePresence>
        {selectedOrder && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4"
            onClick={() => setSelectedOrder(null)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-white rounded-xl shadow-xl max-w-lg w-full max-h-[80vh] overflow-y-auto"
            >
              <div className="p-6 border-b border-slate-200">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-bold text-slate-900">{selectedOrder.id}</h3>
                  <button
                    onClick={() => setSelectedOrder(null)}
                    className="text-slate-400 hover:text-slate-600"
                  >
                    <XCircle className="w-5 h-5" />
                  </button>
                </div>
              </div>
              <div className="p-6 space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs text-slate-400 uppercase tracking-wider">Клиент</p>
                    <p className="text-sm font-medium text-slate-900 mt-0.5">{selectedOrder.clientName}</p>
                    <p className="text-xs text-slate-500">{selectedOrder.phone}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-400 uppercase tracking-wider">Агент</p>
                    <p className="text-sm font-medium text-slate-900 mt-0.5">{selectedOrder.agentName}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-400 uppercase tracking-wider">Статус</p>
                    <p className="text-sm font-medium text-slate-900 mt-0.5">{selectedOrder.status}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-400 uppercase tracking-wider">Сумма</p>
                    <p className="text-sm font-bold text-emerald-600 mt-0.5">
                      {formatMoney(selectedOrder.total)} сум
                    </p>
                  </div>
                </div>
                <div>
                  <p className="text-xs text-slate-400 uppercase tracking-wider mb-2">Товары</p>
                  <div className="space-y-2">
                    {selectedOrder.items?.map((item: OrderItem) => (
                      <div
                        key={item.sku}
                        className="flex items-center justify-between p-3 rounded-lg bg-slate-50 border border-slate-100"
                      >
                        <div>
                          <p className="text-sm font-medium text-slate-900">{item.name}</p>
                          <p className="text-xs text-slate-400">{item.sku}</p>
                        </div>
                        <div className="text-right">
                          <p className="text-sm text-slate-900">
                            {item.qty} × {formatMoney(item.price)} сум
                          </p>
                          <p className="text-xs font-semibold text-slate-700">
                            {formatMoney(item.qty * item.price)} сум
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                {selectedOrder.comment && (
                  <div>
                    <p className="text-xs text-slate-400 uppercase tracking-wider">Комментарий</p>
                    <p className="text-sm text-slate-700 mt-0.5">{selectedOrder.comment}</p>
                  </div>
                )}
                <div className="pt-4 border-t border-slate-200 space-y-2">
                  <div className="flex items-center gap-2 text-xs text-slate-500">
                    <ShoppingCart className="w-3.5 h-3.5" />
                    <span>
                      Manba:{' '}
                      {selectedOrder.moyskladId ? (
                        <span className="text-violet-600 font-medium">MoySklad ({selectedOrder.moyskladId.slice(0, 8)}…)</span>
                      ) : (
                        <span className="text-slate-500">Qo'lda kiritilgan</span>
                      )}
                    </span>
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                  </div>
                  {selectedOrder.agentName && (
                    <div className="text-xs text-slate-400">
                      Agent: <span className="font-medium text-slate-600">{selectedOrder.agentName}</span>
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
