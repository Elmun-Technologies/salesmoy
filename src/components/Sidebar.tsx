import {
  LayoutDashboard,
  ShoppingCart,
  Package,
  Users,
  Wallet,
  Truck,
  UserCheck,
  FileText,
  Settings,
  RefreshCw,
  Shield,
  LogOut,
} from 'lucide-react';

interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  isOpen: boolean;
  setIsOpen: (v: boolean) => void;
  tenantSlug: string;
  onLogout: () => void;
}

const menuItems = [
  { id: 'dashboard', label: 'Дашборд', icon: LayoutDashboard },
  { id: 'orders', label: 'Buyurtmalar', icon: ShoppingCart },
  { id: 'stock', label: 'Qoldiqlar', icon: Package },
  { id: 'clients', label: 'Mijozlar', icon: Users },
  { id: 'debts', label: 'Qarzdorlik', icon: Wallet },
  { id: 'delivery', label: 'Yetkazib berish', icon: Truck },
  { id: 'agents', label: 'Agentlar', icon: UserCheck },
  { id: 'logs', label: 'Loglar', icon: FileText },
  { id: 'settings', label: 'Sozlamalar', icon: Settings },
];

export default function Sidebar({ activeTab, setActiveTab, isOpen, setIsOpen, tenantSlug, onLogout }: SidebarProps) {
  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/30 z-40 lg:hidden"
          onClick={() => setIsOpen(false)}
        />
      )}
      <aside
        className={`fixed lg:static inset-y-0 left-0 z-50 w-64 bg-slate-900 text-white flex flex-col transition-transform duration-300 ${
          isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
      >
        <div className="p-6 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-500 flex items-center justify-center">
              <RefreshCw className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="font-bold text-lg leading-tight">Sales Doctor</h1>
              <p className="text-xs text-slate-400">↔ MoySklad</p>
            </div>
          </div>
        </div>

        <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
          {menuItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => {
                  setActiveTab(item.id);
                  setIsOpen(false);
                }}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/20'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800'
                }`}
              >
                <Icon className="w-5 h-5" />
                {item.label}
              </button>
            );
          })}
        </nav>

        <div className="p-4 border-t border-slate-800 space-y-2">
          <div className="px-4 py-2 text-xs text-slate-500">
            Kompaniya: <span className="text-emerald-400 font-medium">{tenantSlug}</span>
          </div>
          <button
            onClick={onLogout}
            className="w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium text-slate-400 hover:text-white hover:bg-slate-800 transition-all"
          >
            <LogOut className="w-5 h-5" />
            Chiqish
          </button>
          <div className="flex items-center gap-3 px-4 py-3 rounded-lg bg-slate-800/50">
            <div className="w-8 h-8 rounded-full bg-emerald-500/20 flex items-center justify-center">
              <Shield className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="text-sm">
              <p className="text-white font-medium">API Connected</p>
              <p className="text-slate-400 text-xs">MoySklad + Sales Doctor</p>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
