// Fallback mock data when backend is not available

import {
  orders as mockOrders,
  stockItems as mockStock,
  clients as mockClients,
  debts as mockDebts,
  deliveries as mockDeliveries,
  logs as mockLogs,
} from '../data/mockData';

const DEMO_TENANT = {
  tenant: {
    id: 1,
    name: "Demo Kompaniya",
    slug: "demo",
    plan: "pro",
    moysklad_connected: true,
    salesdoctor_connected: true,
  }
};

const DEMO_BILLING = {
  plan: "pro",
  plan_name: "Профессиональный",
  is_trial: true,
  limits: {
    max_orders_monthly: 5000,
    max_users: 15,
    sync_interval_seconds: 15,
  },
  features: ["Синхронизация каждые 15 сек", "API доступ", "Расширенные отчеты", "Webhook"],
};

const PLANS = {
  free: { name: "Бесплатный", price_uzs: 0, features: ["Базовая синхронизация", "Email поддержка"] },
  basic: { name: "Базовый", price_uzs: 290000, features: ["Синхронизация каждые 30 сек", "Приоритетная поддержка", "Отчеты"] },
  pro: { name: "Профессиональный", price_uzs: 590000, features: ["Синхронизация каждые 15 сек", "API доступ", "Расширенные отчеты", "Webhook"] },
  enterprise: { name: "Корпоративный", price_uzs: 1490000, features: ["Синхронизация каждые 5 сек", "Выделенный менеджер", "Custom интеграции", "SLA"] },
};

export const mockLogin = async (data: any) => {
  await delay(500);
  if (data.email === 'demo@example.com' && data.password === 'demo123') {
    return {
      access_token: 'mock-jwt-token',
      token_type: 'bearer',
      ...DEMO_TENANT,
      user: { id: 1, email: 'demo@example.com', full_name: 'Demo Admin', role: 'admin' },
    };
  }
  throw new Error('Noto\'g\'ri login yoki parol');
};

export const mockRegister = async (_data: any) => {
  await delay(800);
  return {
    access_token: 'mock-jwt-token',
    token_type: 'bearer',
    ...DEMO_TENANT,
    message: 'Registration successful',
  };
};

export const mockGetMe = async () => DEMO_TENANT;
export const mockGetPlans = async () => ({ plans: PLANS });
export const mockGetBillingStatus = async () => DEMO_BILLING;
export const mockGetPaymentHistory = async () => [];

export const mockGetOrders = async () => mockOrders.map(o => ({
  id: o.id,
  clientName: o.clientName,
  phone: o.phone,
  agentName: o.agentName,
  items: o.items,
  total: o.total,
  status: o.status,
  comment: o.comment,
  createdAt: o.createdAt,
  syncStatus: o.syncStatus,
}));

export const mockGetStock = async () => mockStock.map(s => ({
  sku: s.sku,
  name: s.name,
  qty: s.qty,
  price: s.price,
  warehouse: s.warehouse,
  lastSync: s.lastSync,
}));

export const mockGetClients = async () => mockClients.map(c => ({
  id: c.id,
  name: c.name,
  phone: c.phone,
  address: c.address,
  location: c.location,
  type: c.type,
  debt: c.debt,
  debtLimit: c.debtLimit,
  lastOrder: c.lastOrder,
}));

export const mockGetClientStats = async () => ({
  total: mockClients.length,
  wholesale: mockClients.filter(c => c.type === 'Опт').length,
  retail: mockClients.filter(c => c.type === 'Розница').length,
  debtRisk: mockClients.filter(c => c.debt > c.debtLimit * 0.8).length,
});

export const mockGetDebts = async () => mockDebts.map(d => ({
  clientName: d.clientName,
  phone: d.phone,
  totalDebt: d.totalDebt,
  paid: d.paid,
  remaining: d.remaining,
  lastPayment: d.lastPayment,
}));

export const mockGetDebtSummary = async () => ({
  totalDebt: mockDebts.reduce((s, d) => s + d.totalDebt, 0),
  totalPaid: mockDebts.reduce((s, d) => s + d.paid, 0),
  totalRemaining: mockDebts.reduce((s, d) => s + d.remaining, 0),
});

export const mockGetDeliveries = async () => mockDeliveries.map(d => ({
  orderId: d.orderId,
  clientName: d.clientName,
  address: d.address,
  courier: d.courier,
  status: d.status,
  dispatchedAt: d.dispatchedAt,
  deliveredAt: d.deliveredAt,
}));

export const mockGetLogs = async () => mockLogs.map(l => ({
  id: l.id,
  timestamp: l.timestamp,
  type: l.type,
  module: l.module,
  message: l.message,
  retryCount: l.retryCount,
}));

export const mockGetLogStats = async () => ({
  total: mockLogs.length,
  success: mockLogs.filter(l => l.type === 'success').length,
  error: mockLogs.filter(l => l.type === 'error').length,
  warning: mockLogs.filter(l => l.type === 'warning').length,
});

function delay(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms));
}
