import { useState, useEffect } from 'react';
import { Menu } from 'lucide-react';
import Sidebar from './components/Sidebar';
import Dashboard from './components/Dashboard';
import OrdersPanel from './components/OrdersPanel';
import StockPanel from './components/StockPanel';
import ClientsPanel from './components/ClientsPanel';
import DebtsPanel from './components/DebtsPanel';
import DeliveryPanel from './components/DeliveryPanel';
import AgentsPanel from './components/AgentsPanel';
import LogsPanel from './components/LogsPanel';
import SettingsPanel from './components/SettingsPanel';
import AuthPanel from './components/AuthPanel';
import DemoIndicator from './components/DemoIndicator';

const panels: Record<string, React.ComponentType> = {
  dashboard: Dashboard,
  orders: OrdersPanel,
  stock: StockPanel,
  clients: ClientsPanel,
  debts: DebtsPanel,
  delivery: DeliveryPanel,
  agents: AgentsPanel,
  logs: LogsPanel,
  settings: SettingsPanel,
};

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [tenantSlug, setTenantSlug] = useState<string | null>(localStorage.getItem('tenant_slug'));

  useEffect(() => {
    const slug = localStorage.getItem('tenant_slug');
    if (slug) setTenantSlug(slug);
  }, []);

  const handleAuth = (slug: string) => {
    setTenantSlug(slug);
  };

  const handleLogout = () => {
    localStorage.removeItem('tenant_slug');
    localStorage.removeItem('access_token');
    setTenantSlug(null);
  };

  if (!tenantSlug) {
    return <AuthPanel onAuth={handleAuth} />;
  }

  const ActivePanel = panels[activeTab] || Dashboard;

  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        isOpen={sidebarOpen}
        setIsOpen={setSidebarOpen}
        tenantSlug={tenantSlug}
        onLogout={handleLogout}
      />

      <main className="flex-1 min-w-0">
        <header className="sticky top-0 z-30 bg-white/80 backdrop-blur-md border-b border-slate-200 px-4 py-3 lg:px-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button
                onClick={() => setSidebarOpen(true)}
                className="lg:hidden p-2 rounded-lg hover:bg-slate-100 text-slate-600"
              >
                <Menu className="w-5 h-5" />
              </button>
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                <span className="text-sm font-medium text-slate-600">Sistema onlayn</span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <DemoIndicator />
              <span className="text-xs text-slate-400 bg-slate-100 px-2 py-1 rounded">
                {tenantSlug}
              </span>
            </div>
          </div>
        </header>

        <div className="p-4 lg:p-8 max-w-7xl mx-auto">
          <ActivePanel />
        </div>
      </main>
    </div>
  );
}
