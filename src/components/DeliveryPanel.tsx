import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  Truck,
  MapPin,
  User,
  Clock,
  CheckCircle2,
  XCircle,
  Navigation,
  PackageCheck,
  ArrowRightLeft,
  Filter,
  RefreshCw,
} from 'lucide-react';
import { getDeliveries } from '../services/api';

interface Delivery {
  orderId: string;
  clientName: string;
  address: string;
  courier: string;
  status: string;
  dispatchedAt: string;
  deliveredAt?: string;
}

export default function DeliveryPanel() {
  const [statusFilter, setStatusFilter] = useState('all');
  const [deliveries, setDeliveries] = useState<Delivery[]>([]);
  const [loading, setLoading] = useState(true);

  async function loadData() {
    setLoading(true);
    try {
      const data = await getDeliveries();
      setDeliveries(data);
    } catch (e) {
      console.error('Delivery load error:', e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 30000);
    return () => clearInterval(interval);
  }, []);

  const filtered = deliveries.filter(
    (d) => statusFilter === 'all' || d.status === statusFilter
  );

  const statusConfig: Record<string, { icon: React.ElementType; color: string; bg: string; label: string }> = {
    'В пути': { icon: Navigation, color: 'text-cyan-600', bg: 'bg-cyan-50 border-cyan-200', label: 'В пути' },
    'Доставлен': { icon: CheckCircle2, color: 'text-emerald-600', bg: 'bg-emerald-50 border-emerald-200', label: 'Доставлен' },
    'Отказ': { icon: XCircle, color: 'text-red-600', bg: 'bg-red-50 border-red-200', label: 'Отказ' },
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Доставка</h2>
          <p className="text-slate-500 text-sm mt-1">
            MoySklad "Отгрузка" → Sales Doctor курьеру. Статус обратно в MoySklad.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={loadData}
            className="flex items-center gap-2 text-sm text-slate-600 bg-white px-3 py-2 rounded-lg border border-slate-200 hover:bg-slate-50"
          >
            <RefreshCw className="w-4 h-4" />
            Обновить
          </button>
          <div className="flex items-center gap-2 text-sm text-emerald-600 bg-emerald-50 px-3 py-2 rounded-lg border border-emerald-200">
            <ArrowRightLeft className="w-4 h-4" />
            Двусторонняя
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-cyan-100 flex items-center justify-center">
            <Navigation className="w-5 h-5 text-cyan-600" />
          </div>
          <div>
            <p className="text-2xl font-bold text-slate-900">
              {deliveries.filter((d) => d.status === 'В пути').length}
            </p>
            <p className="text-xs text-slate-500">В пути</p>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-emerald-100 flex items-center justify-center">
            <PackageCheck className="w-5 h-5 text-emerald-600" />
          </div>
          <div>
            <p className="text-2xl font-bold text-slate-900">
              {deliveries.filter((d) => d.status === 'Доставлен').length}
            </p>
            <p className="text-xs text-slate-500">Доставлено</p>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-red-100 flex items-center justify-center">
            <XCircle className="w-5 h-5 text-red-600" />
          </div>
          <div>
            <p className="text-2xl font-bold text-slate-900">
              {deliveries.filter((d) => d.status === 'Отказ').length}
            </p>
            <p className="text-xs text-slate-500">Отказ</p>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Filter className="w-4 h-4 text-slate-400" />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-2.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
        >
          <option value="all">Все статусы</option>
          <option value="В пути">В пути</option>
          <option value="Доставлен">Доставлен</option>
          <option value="Отказ">Отказ</option>
        </select>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="w-8 h-8 text-emerald-500 animate-spin" />
        </div>
      ) : (
        <div className="space-y-4">
          {filtered.map((delivery, i) => {
            const StatusIcon = statusConfig[delivery.status]?.icon || Truck;
            return (
              <motion.div
                key={delivery.orderId}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm"
              >
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <span className="font-mono text-sm text-slate-500">{delivery.orderId}</span>
                      <span
                        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${statusConfig[delivery.status]?.bg}`}
                      >
                        <StatusIcon className={`w-3.5 h-3.5 ${statusConfig[delivery.status]?.color}`} />
                        {delivery.status}
                      </span>
                    </div>
                    <h4 className="font-semibold text-slate-900">{delivery.clientName}</h4>
                    <div className="flex items-center gap-2 mt-1 text-sm text-slate-500">
                      <MapPin className="w-3.5 h-3.5" />
                      {delivery.address}
                    </div>
                  </div>

                  <div className="flex items-center gap-6">
                    <div className="text-sm">
                      <div className="flex items-center gap-1.5 text-slate-500 mb-1">
                        <User className="w-3.5 h-3.5" />
                        Курьер
                      </div>
                      <p className="font-medium text-slate-900">{delivery.courier}</p>
                    </div>
                    <div className="text-sm">
                      <div className="flex items-center gap-1.5 text-slate-500 mb-1">
                        <Clock className="w-3.5 h-3.5" />
                        Отгружен
                      </div>
                      <p className="font-medium text-slate-900">
                        {delivery.dispatchedAt ? new Date(delivery.dispatchedAt).toLocaleTimeString('ru-RU', {
                          hour: '2-digit',
                          minute: '2-digit',
                        }) : '-'}
                      </p>
                    </div>
                    {delivery.deliveredAt && (
                      <div className="text-sm">
                        <div className="flex items-center gap-1.5 text-slate-500 mb-1">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          Доставлен
                        </div>
                        <p className="font-medium text-emerald-600">
                          {new Date(delivery.deliveredAt).toLocaleTimeString('ru-RU', {
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </p>
                      </div>
                    )}
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-slate-100 flex items-center gap-4 text-xs text-slate-400">
                  <span className="flex items-center gap-1">
                    <Truck className="w-3 h-3" />
                    MoySklad → Отгрузка создана
                  </span>
                  <span>→</span>
                  <span className="flex items-center gap-1">
                    <User className="w-3 h-3" />
                    Курьер получил
                  </span>
                  <span>→</span>
                  <span className="flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" />
                    Статус обновлен в MoySklad
                  </span>
                </div>
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
}
