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
    name: 'Sinov',
    badge: null,
    tagline: 'Integratsiyani bepul sinab ko\'ring',
    price_uzs: 0,
    price_rub: 0,
    features: [
      '300 ta zakaz / oy',
      'Har 5 daqiqada sinxron',
      '1 ta filial',
      'MoySklad → Sales Doctor zakazlar',
      'Qoldiqlarni ko\'rish',
      'Email yordam',
    ],
    limits: ['Qarzdorlik bloki yo\'q', 'Webhook yo\'q'],
  },
  basic: {
    name: 'Biznes',
    badge: null,
    tagline: 'O\'sib borayotgan kompaniyalar uchun',
    price_uzs: 290000,
    price_rub: 1900,
    features: [
      'Cheksiz zakazlar',
      'Har 30 soniyada sinxron',
      '5 ta filial',
      'Zakazlar avtomatik uzatiladi',
      'Agentlar uchun real vaqt qoldiq',
      'Qarzdor mijozga zakaz bloki',
      'Yetkazib berish kuzatuvi',
      'Prioritet yordam',
    ],
    limits: [],
  },
  pro: {
    name: 'Professional',
    badge: 'Eng mashhur',
    tagline: 'Faol savdo tarmoqlari uchun',
    price_uzs: 590000,
    price_rub: 3900,
    features: [
      'Cheksiz zakazlar',
      'Har 15 soniyada sinxron',
      '15 ta filial',
      'Barcha Biznes imkoniyatlari',
      'Mijozlar ikki tomonlama sinxron',
      'Kengaytirilgan hisobotlar',
      'Webhook integratsiyasi',
      'API ulanishi',
      'Telegram bildirishnomalar',
    ],
    limits: [],
  },
  enterprise: {
    name: 'Korporativ',
    badge: null,
    tagline: 'Yirik tarqatuvchi kompaniyalar uchun',
    price_uzs: 1490000,
    price_rub: 9900,
    features: [
      'Cheksiz zakazlar',
      'Har 5 soniyada sinxron (real vaqt)',
      'Cheksiz filiallar',
      'Barcha Professional imkoniyatlari',
      'Shaxsiy menejer',
      'Maxsus integratsiyalar',
      'SLA kafolati (99.9% uptime)',
      '24/7 qo\'llab-quvvatlash',
      'Onboarding va o\'rgatish',
    ],
    limits: [],
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
        <div className="mb-6">
          <h3 className="text-xl font-bold text-slate-900">Tariflar</h3>
          <p className="text-sm text-slate-500 mt-1">
            Hamma tarifda: MoySklad ↔ Sales Doctor integratsiya, zakazlar avtomatik uzatish, qoldiqlar nazorati
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {Object.entries(plans && Object.keys(plans).length > 0 ? plans : DEFAULT_PLANS).map(([key, plan]: [string, any]) => {
            const isCurrent = billing?.plan === key;
            const isPro = key === 'pro';
            const isEnterprise = key === 'enterprise';
            return (
              <div
                key={key}
                className={`relative rounded-xl border-2 p-5 flex flex-col transition-all ${
                  isCurrent
                    ? 'border-emerald-500 bg-emerald-50/60 shadow-md'
                    : isPro
                    ? 'border-amber-400 bg-amber-50/30 shadow-md'
                    : 'border-slate-200 hover:border-slate-300 hover:shadow-sm'
                }`}
              >
                {plan?.badge && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                    <span className="bg-amber-500 text-white text-xs font-bold px-3 py-1 rounded-full whitespace-nowrap shadow">
                      ⭐ {plan.badge}
                    </span>
                  </div>
                )}
                {isCurrent && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                    <span className="bg-emerald-600 text-white text-xs font-bold px-3 py-1 rounded-full whitespace-nowrap shadow">
                      ✓ Joriy tarif
                    </span>
                  </div>
                )}

                <div className="mb-3">
                  <div className="flex items-center gap-2 mb-1">
                    {key === 'free' && <Zap className="w-4 h-4 text-slate-400" />}
                    {key === 'basic' && <Zap className="w-4 h-4 text-blue-500" />}
                    {key === 'pro' && <Crown className="w-4 h-4 text-amber-500" />}
                    {isEnterprise && <Building2 className="w-4 h-4 text-purple-500" />}
                    <h4 className="font-bold text-slate-900 text-base">{plan?.name}</h4>
                  </div>
                  <p className="text-xs text-slate-500 leading-snug">{plan?.tagline}</p>
                </div>

                <div className="mb-4">
                  {plan?.price_uzs === 0 ? (
                    <p className="text-3xl font-black text-slate-900">Bepul</p>
                  ) : (
                    <>
                      <p className="text-2xl font-black text-slate-900">
                        {plan?.price_uzs?.toLocaleString('ru-RU')}
                        <span className="text-sm font-normal text-slate-500 ml-1">so'm/oy</span>
                      </p>
                      <p className="text-xs text-slate-400">≈ {plan?.price_rub?.toLocaleString('ru-RU')} ₽/oy</p>
                    </>
                  )}
                </div>

                <ul className="space-y-2 mb-5 flex-1">
                  {plan?.features?.map((f: string, i: number) => (
                    <li key={i} className="flex items-start gap-2 text-xs text-slate-700">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 mt-0.5 shrink-0" />
                      <span>{f}</span>
                    </li>
                  ))}
                  {plan?.limits?.map((f: string, i: number) => (
                    <li key={`l-${i}`} className="flex items-start gap-2 text-xs text-slate-400">
                      <span className="w-3.5 h-3.5 mt-0.5 shrink-0 flex items-center justify-center text-slate-300 font-bold">–</span>
                      <span>{f}</span>
                    </li>
                  ))}
                </ul>

                <button
                  disabled={isCurrent}
                  className={`w-full py-2.5 rounded-lg text-sm font-semibold transition-all ${
                    isCurrent
                      ? 'bg-emerald-100 text-emerald-700 cursor-default'
                      : isPro
                      ? 'bg-amber-500 hover:bg-amber-600 text-white shadow-sm'
                      : isEnterprise
                      ? 'bg-purple-600 hover:bg-purple-700 text-white'
                      : 'bg-slate-800 hover:bg-slate-900 text-white'
                  }`}
                >
                  {isCurrent ? '✓ Faol tarif' : key === 'enterprise' ? 'Bog\'lanish' : 'Tanlash'}
                </button>
              </div>
            );
          })}
        </div>

        <div className="mt-6 rounded-xl bg-gradient-to-r from-emerald-50 to-blue-50 border border-emerald-100 p-4">
          <p className="text-sm text-slate-700 font-medium mb-1">💡 Nima uchun integratsiya kerak?</p>
          <p className="text-xs text-slate-500 leading-relaxed">
            Agentlar Sales Doctorga zakaz kiritadi → zakaz avtomatik MoySkladga tushadi → omborchi ko'radi → yetkazib berish chiqadi.
            Hech qanday qo'lda ko'chirish, xato yoki vaqt yo'qotish yo'q.
          </p>
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
