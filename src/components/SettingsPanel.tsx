import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  Shield,
  Key,
  CheckCircle2,
  Globe,
  Database,
  RefreshCw,
  Building2,
  Webhook,
  AlertTriangle,
} from 'lucide-react';
import {
  getMe,
  connectMoySklad,
  connectSalesDoctor,
  startMoySkladOAuth,
  getMoySkladWebhookStatus,
  registerMoySkladWebhooks,
  unregisterMoySkladWebhooks,
} from '../services/api';

export default function SettingsPanel() {
  const [saved, setSaved] = useState(false);
  const [tenant, setTenant] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  // Connection inputs
  const [msToken, setMsToken] = useState('');
  const [sdBaseUrl, setSdBaseUrl] = useState('');
  const [sdLogin, setSdLogin] = useState('');
  const [sdPassword, setSdPassword] = useState('');
  const [sdFilialId, setSdFilialId] = useState('0');

  // MoySklad webhooks
  const [whStatus, setWhStatus] = useState<any>(null);
  const [whBusy, setWhBusy] = useState(false);

  async function refreshWebhookStatus() {
    try {
      const s = await getMoySkladWebhookStatus();
      setWhStatus(s);
    } catch (e) {
      console.error(e);
    }
  }

  async function handleRegisterWebhooks() {
    setWhBusy(true);
    try {
      const r = await registerMoySkladWebhooks();
      if (!r.success) {
        window.alert(r.error || 'Webhook ulanmadi');
      }
      await refreshWebhookStatus();
    } catch (e: any) {
      window.alert(e?.message || 'Webhook ulanishda xatolik');
    } finally {
      setWhBusy(false);
    }
  }

  async function handleUnregisterWebhooks() {
    if (!window.confirm('MoySklad webhooklarini o\'chirish? Real-time sinxron 5-daq pollingga qaytadi.')) return;
    setWhBusy(true);
    try {
      await unregisterMoySkladWebhooks();
      await refreshWebhookStatus();
    } finally {
      setWhBusy(false);
    }
  }

  useEffect(() => {
    async function load() {
      try {
        const me = await getMe();
        setTenant(me.tenant);
        if (me.tenant?.salesdoctor_base_url) setSdBaseUrl(me.tenant.salesdoctor_base_url);
        if (me.tenant?.salesdoctor_login) setSdLogin(me.tenant.salesdoctor_login);
        if (me.tenant?.moysklad_connected) {
          await refreshWebhookStatus();
        }
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
          <button
            onClick={handleMoySkladMarketplaceOAuth}
            className="flex items-center gap-2 px-4 py-2 bg-blue-100 hover:bg-blue-200 text-blue-700 rounded-lg text-sm font-medium transition-colors"
          >
            <Globe className="w-4 h-4" />
            MoySklad Marketplace OAuth orqali ulash
          </button>
          <p className="text-xs text-slate-500">
            Yoki qo’lda access token kiriting (JSON dagi <code className="bg-slate-100 px-1 rounded">access_token</code>{‘ ‘}
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

      {/* MoySklad Webhooks (real-time sync) */}
      {tenant?.moysklad_connected && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm"
        >
          <div className="flex items-center gap-3 mb-5">
            <div className="w-10 h-10 rounded-lg bg-violet-100 flex items-center justify-center">
              <Webhook className="w-5 h-5 text-violet-600" />
            </div>
            <div>
              <h3 className="font-semibold text-slate-900">Real-time webhook</h3>
              <p className="text-xs text-slate-500">MoySklad'da har bir o'zgarish bir necha sekundda SD'ga uzatiladi</p>
            </div>
          </div>

          {whStatus?.connected ? (
            <div className="flex items-center gap-2 px-3 py-2.5 rounded-lg border border-emerald-200 bg-emerald-50 text-sm text-emerald-700 mb-3">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              Webhook ulangan ({whStatus.registered_count} ta hodisa) — real-time rejim faol
            </div>
          ) : whStatus?.public_base_url ? (
            <div className="flex items-center gap-2 px-3 py-2.5 rounded-lg border border-amber-200 bg-amber-50 text-sm text-amber-700 mb-3">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              Webhook ulanmagan — hozirgi cadence: ≤5 daq polling
            </div>
          ) : (
            <div className="flex items-start gap-2 px-3 py-2.5 rounded-lg border border-red-200 bg-red-50 text-sm text-red-700 mb-3">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              <div>
                <div>Server <code className="bg-red-100 px-1 rounded">PUBLIC_BASE_URL</code> sozlanmagan.</div>
                <div className="text-xs mt-1">Admin: server <code className="bg-red-100 px-1 rounded">.env</code> faylida HTTPS bazaviy URL'ni qo'shing.</div>
              </div>
            </div>
          )}

          {whStatus?.target_url && (
            <p className="text-xs text-slate-500 mb-3 break-all">
              Webhook URL: <code className="bg-slate-100 px-1 rounded">{whStatus.target_url}</code>
            </p>
          )}

          <div className="flex gap-2">
            <button
              onClick={handleRegisterWebhooks}
              disabled={whBusy || !whStatus?.public_base_url}
              className="flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition-colors"
            >
              {whBusy ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Webhook className="w-4 h-4" />}
              {whStatus?.connected ? 'Qayta ro\'yxatdan o\'tkazish' : 'Real-time webhook ulash'}
            </button>
            {whStatus?.connected && (
              <button
                onClick={handleUnregisterWebhooks}
                disabled={whBusy}
                className="flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 rounded-lg text-sm font-medium transition-colors"
              >
                O'chirish
              </button>
            )}
            <button
              onClick={refreshWebhookStatus}
              disabled={whBusy}
              className="flex items-center gap-2 px-3 py-2 bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 rounded-lg text-sm font-medium transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${whBusy ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </motion.div>
      )}

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
