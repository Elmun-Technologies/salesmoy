import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  Shield,
  Key,
  CheckCircle2,
  Globe,
  Database,
  RefreshCw,
  CreditCard,
  Zap,
  Crown,
  Building2,
} from 'lucide-react';
import {
  getMe,
  getPlans,
  getBillingStatus,
  connectMoySklad,
  connectSalesDoctor,
  startMoySkladOAuth,
} from '../services/api';

const DEFAULT_PLANS: Record<string, any> = {
  free: {
    name: 'Бесплатный',
    price_uzs: 0,
    price_rub: 0,
    features: ['Базовая синхронизация', 'Email поддержка', '100 заказов/мес', '2 пользователя'],
  },
  basic: {
    name: 'Базовый',
    price_uzs: 290000,
    price_rub: 1900,
    features: ['Синхронизация каждые 30 сек', 'Приоритетная поддержка', '1,000 заказов/мес', '5 пользователей'],
  },
  pro: {
    name: 'Профессиональный',
    price_uzs: 590000,
    price_rub: 3900,
    features: ['Синхронизация каждые 15 сек', 'API доступ', '5,000 заказов/мес', '15 пользователей', 'Webhook'],
  },
  enterprise: {
    name: 'Корпоративный',
    price_uzs: 1490000,
    price_rub: 9900,
    features: ['Синхронизация каждые 5 сек', 'Выделенный менеджер', 'Безлимит заказы', 'Безлимит пользователи', 'Custom интеграции', 'SLA'],
  },
};

export default function SettingsPanel() {
  const [saved, setSaved] = useState(false);
  const [tenant, setTenant] = useState<any>(null);
  const [plans, setPlans] = useState<any>({});
  const [billing, setBilling] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  // Connection inputs
  const [msToken, setMsToken] = useState('');
  const [sdBaseUrl, setSdBaseUrl] = useState('');
  const [sdLogin, setSdLogin] = useState('');
  const [sdPassword, setSdPassword] = useState('');
  const [sdFilialId, setSdFilialId] = useState('0');

  useEffect(() => {
    async function load() {
      try {
        const [me, plansData, billingData] = await Promise.all([
          getMe(),
          getPlans(),
          getBillingStatus(),
        ]);
        setTenant(me.tenant);
        if (me.tenant?.salesdoctor_base_url) setSdBaseUrl(me.tenant.salesdoctor_base_url);
        if (me.tenant?.salesdoctor_login) setSdLogin(me.tenant.salesdoctor_login);
        setPlans(plansData.plans);
        setBilling(billingData);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  async function handleMoySkladMarketplaceOAuth() {
    try {
      await startMoySkladOAuth();
    } catch (e) {
      console.error(e);
      window.alert(
        e instanceof Error ? e.message : 'MoySklad OAuth xizmati sozlanmagan yoki xatolik yuz berdi'
      );
    }
  }

  async function handleConnectMoySklad() {
    try {
      await connectMoySklad({
        access_token: msToken,
        refresh_token: '',
        expires_in: 86400,
        account_id: '',
      });
      const me = await getMe();
      setTenant(me.tenant);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      console.error(e);
    }
  }

  async function handleConnectSalesDoctor() {
    try {
      await connectSalesDoctor({
        base_url: sdBaseUrl || 'https://api.salesdoctor.uz/v2',
        login: sdLogin,
        password: sdPassword,
        filial_id: parseInt(sdFilialId) || 0,
      });
      const me = await getMe();
      setTenant(me.tenant);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e: any) {
      window.alert(e?.message || 'Sales Doctor ulanishda xatolik');
      console.error(e);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <RefreshCw className="w-8 h-8 text-emerald-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Sozlamalar</h2>
        <p className="text-slate-500 text-sm mt-1">
          API ulanishlari, tariflar va integratsiya sozlamalari
        </p>
      </div>

      {/* Tenant Info */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm"
      >
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-lg bg-emerald-100 flex items-center justify-center">
            <Building2 className="w-5 h-5 text-emerald-600" />
          </div>
          <div>
            <h3 className="font-semibold text-slate-900">Kompaniya ma'lumotlari</h3>
            <p className="text-xs text-slate-500">{tenant?.name}</p>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-slate-400">Slug:</span>
            <span className="ml-2 font-medium text-slate-900">{tenant?.slug}</span>
          </div>
          <div>
            <span className="text-slate-400">Tarif:</span>
            <span className="ml-2 font-medium text-emerald-600">{billing?.plan_name || 'Bepul'}</span>
          </div>
          <div>
            <span className="text-slate-400">MoySklad:</span>
            <span className={`ml-2 font-medium ${tenant?.moysklad_connected ? 'text-emerald-600' : 'text-red-500'}`}>
              {tenant?.moysklad_connected ? 'Ulangan' : 'Ulanmagan'}
            </span>
          </div>
          <div>
            <span className="text-slate-400">Sales Doctor:</span>
            <span className={`ml-2 font-medium ${tenant?.salesdoctor_connected ? 'text-emerald-600' : 'text-red-500'}`}>
              {tenant?.salesdoctor_connected ? 'Ulangan' : 'Ulanmagan'}
            </span>
          </div>
        </div>
      </motion.div>

      {/* MoySklad Connection */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm"
      >
        <div className="flex items-center gap-3 mb-5">
          <div className="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center">
            <Database className="w-5 h-5 text-blue-600" />
          </div>
          <div>
            <h3 className="font-semibold text-slate-900">MoySklad API</h3>
            <p className="text-xs text-slate-500">https://api.moysklad.ru/api/remap/1.2</p>
          </div>
        </div>

        <div className="space-y-4">
          <p className="text-xs text-slate-500">
            Yoki qo‘lda access token kiriting (JSON dagi <code className="bg-slate-100 px-1 rounded">access_token</code>{' '}
            qiymati):
          </p>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Access Token</label>
            {tenant?.moysklad_connected && !msToken && (
              <div className="flex items-center gap-2 px-3 py-2.5 rounded-lg border border-emerald-200 bg-emerald-50 text-sm text-emerald-700 mb-2">
                <CheckCircle2 className="w-4 h-4 shrink-0" />
                Token saqlangan — yangilash uchun quyida yangi token kiriting
              </div>
            )}
            <div className="relative">
              <Key className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="password"
                value={msToken}
                onChange={(e) => setMsToken(e.target.value)}
                placeholder={tenant?.moysklad_connected ? '••••••••••••••••••••••••••••••••' : 'MoySklad API tokenini kiriting'}
                className={`w-full pl-10 pr-4 py-2.5 rounded-lg border text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${tenant?.moysklad_connected ? 'border-emerald-200 bg-emerald-50/30' : 'border-slate-200'}`}
              />
            </div>
          </div>
          <button
            onClick={handleConnectMoySklad}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
          >
            <CheckCircle2 className="w-4 h-4" />
            {tenant?.moysklad_connected ? 'Yangilash' : 'Ulash'}
          </button>
        </div>
      </motion.div>

      {/* Sales Doctor Connection */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm"
      >
        <div className="flex items-center gap-3 mb-5">
          <div className="w-10 h-10 rounded-lg bg-emerald-100 flex items-center justify-center">
            <Globe className="w-5 h-5 text-emerald-600" />
          </div>
          <div>
            <h3 className="font-semibold text-slate-900">Sales Doctor API</h3>
            <p className="text-xs text-slate-500">https://api.salesdoctor.uz/v2</p>
          </div>
        </div>

        <div className="space-y-4">
          {tenant?.salesdoctor_connected && (
            <div className="flex items-center gap-2 px-3 py-2.5 rounded-lg border border-emerald-200 bg-emerald-50 text-sm text-emerald-700">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              Sales Doctor ulangan — yangilash uchun quyida qayta kiriting
            </div>
          )}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Server URL</label>
            <div className="relative">
              <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="text"
                value={sdBaseUrl}
                onChange={(e) => setSdBaseUrl(e.target.value)}
                placeholder="https://api.salesdoctor.uz/v2"
                className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Login</label>
            <div className="relative">
              <Key className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="text"
                value={sdLogin}
                onChange={(e) => setSdLogin(e.target.value)}
                placeholder="Sales Doctor login (email yoki username)"
                className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Parol</label>
            <div className="relative">
              <Shield className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="password"
                value={sdPassword}
                onChange={(e) => setSdPassword(e.target.value)}
                placeholder="Sales Doctor paroli"
                className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Filial ID <span className="text-slate-400 font-normal">(ixtiyoriy, standart: 0)</span></label>
            <div className="relative">
              <Database className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="number"
                value={sdFilialId}
                onChange={(e) => setSdFilialId(e.target.value)}
                placeholder="0"
                className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>
          </div>
          <button
            onClick={handleConnectSalesDoctor}
            className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm font-medium transition-colors"
          >
            <CheckCircle2 className="w-4 h-4" />
            {tenant?.salesdoctor_connected ? 'Yangilash' : 'Ulash'}
          </button>
        </div>
      </motion.div>

      {/* Pricing Plans */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm"
      >
        <div className="flex items-center gap-3 mb-5">
          <div className="w-10 h-10 rounded-lg bg-amber-100 flex items-center justify-center">
            <CreditCard className="w-5 h-5 text-amber-600" />
          </div>
          <div>
            <h3 className="font-semibold text-slate-900">Tariflar</h3>
            <p className="text-xs text-slate-500">O'zingizga mos tarifni tanlang</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {Object.entries(plans && Object.keys(plans).length > 0 ? plans : DEFAULT_PLANS).map(([key, plan]: [string, any]) => (
            <div
              key={key}
              className={`rounded-xl border p-4 ${
                billing?.plan === key
                  ? 'border-emerald-500 bg-emerald-50'
                  : 'border-slate-200 hover:border-emerald-300'
              }`}
            >
              <div className="flex items-center gap-2 mb-2">
                {key === 'free' && <Zap className="w-4 h-4 text-slate-500" />}
                {key === 'basic' && <Zap className="w-4 h-4 text-blue-500" />}
                {key === 'pro' && <Crown className="w-4 h-4 text-amber-500" />}
                {key === 'enterprise' && <Crown className="w-4 h-4 text-purple-500" />}
                <h4 className="font-semibold text-slate-900">{plan?.name}</h4>
              </div>
              <p className="text-2xl font-bold text-slate-900 mb-1">
                {plan?.price_uzs?.toLocaleString('ru-RU')} <span className="text-sm font-normal text-slate-500">so'm</span>
              </p>
              <p className="text-xs text-slate-500 mb-3">/oy</p>
              <ul className="space-y-1.5 mb-4">
                {plan?.features?.map((f: string, i: number) => (
                  <li key={i} className="flex items-center gap-1.5 text-xs text-slate-600">
                    <CheckCircle2 className="w-3 h-3 text-emerald-500" />
                    {f}
                  </li>
                ))}
              </ul>
              <button
                disabled={billing?.plan === key}
                className={`w-full py-2 rounded-lg text-sm font-medium transition-colors ${
                  billing?.plan === key
                    ? 'bg-emerald-100 text-emerald-700 cursor-default'
                    : 'bg-slate-100 text-slate-700 hover:bg-emerald-600 hover:text-white'
                }`}
              >
                {billing?.plan === key ? 'Joriy tarif' : 'Tanlash'}
              </button>
            </div>
          ))}
        </div>
      </motion.div>

      {/* Business Rules */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm"
      >
        <div className="flex items-center gap-3 mb-5">
          <div className="w-10 h-10 rounded-lg bg-slate-100 flex items-center justify-center">
            <Shield className="w-5 h-5 text-slate-600" />
          </div>
          <div>
            <h3 className="font-semibold text-slate-900">Biznes qoidalar</h3>
            <p className="text-xs text-slate-500">Ma'lumotlarni qayta ishlash qoidalari</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <label className="flex items-start gap-3 p-3 rounded-lg bg-slate-50 border border-slate-100 cursor-pointer">
            <input type="checkbox" defaultChecked className="mt-0.5 rounded text-emerald-600 focus:ring-emerald-500" />
            <div>
              <p className="text-sm font-medium text-slate-900">Qarz limiti blokirovkasi</p>
              <p className="text-xs text-slate-500">Limitdan oshsa buyurtma bloklanadi</p>
            </div>
          </label>
          <label className="flex items-start gap-3 p-3 rounded-lg bg-slate-50 border border-slate-100 cursor-pointer">
            <input type="checkbox" defaultChecked className="mt-0.5 rounded text-emerald-600 focus:ring-emerald-500" />
            <div>
              <p className="text-sm font-medium text-slate-900">Ombor qoldig'ini tekshirish</p>
              <p className="text-xs text-slate-500">Tovar yo'q bo'lsa buyurtma qabul qilinmaydi</p>
            </div>
          </label>
          <label className="flex items-start gap-3 p-3 rounded-lg bg-slate-50 border border-slate-100 cursor-pointer">
            <input type="checkbox" defaultChecked className="mt-0.5 rounded text-emerald-600 focus:ring-emerald-500" />
            <div>
              <p className="text-sm font-medium text-slate-900">Dublikatlarni birlashtirish</p>
              <p className="text-xs text-slate-500">Telefon yoki nom bo'yicha avto-birlashtirish</p>
            </div>
          </label>
          <label className="flex items-start gap-3 p-3 rounded-lg bg-slate-50 border border-slate-100 cursor-pointer">
            <input type="checkbox" defaultChecked className="mt-0.5 rounded text-emerald-600 focus:ring-emerald-500" />
            <div>
              <p className="text-sm font-medium text-slate-900">Xatolarni qayta ishlash</p>
              <p className="text-xs text-slate-500">3 marta urinish (retry)</p>
            </div>
          </label>
        </div>
      </motion.div>

      {saved && (
        <div className="fixed bottom-4 right-4 bg-emerald-600 text-white px-4 py-2 rounded-lg shadow-lg text-sm font-medium">
          Saqlandi!
        </div>
      )}
    </div>
  );
}
