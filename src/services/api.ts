import * as mock from './mockApi';

// API URL priority: localStorage > env > default
function getApiBase(): string {
  const fromStorage = localStorage.getItem('api_url');
  if (fromStorage) return fromStorage;
  const fromEnv = (import.meta as any).env?.VITE_API_URL;
  if (fromEnv) return fromEnv;
  return import.meta.env.PROD ? '' : 'http://localhost:8000';
}

let API_BASE = getApiBase();
let USE_MOCK = false;

export function isMockMode(): boolean {
  return USE_MOCK;
}

export function getApiUrl(): string {
  return API_BASE;
}

function getTenantSlug(): string {
  return localStorage.getItem('tenant_slug') || '';
}

function getAccessToken(): string | null {
  return localStorage.getItem('access_token');
}

function authNeeded(path: string): boolean {
  if (path === '/api/auth/register' || path === '/api/auth/login') return false;
  return true;
}

async function fetchJson(path: string, options?: RequestInit) {
  if (USE_MOCK) {
    throw new Error('MOCK_MODE');
  }
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string>),
  };
  const slug = getTenantSlug();
  if (slug) headers['X-Tenant-Slug'] = slug;

  const token = getAccessToken();
  if (token && authNeeded(path)) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  try {
    const res = await fetch(`${API_BASE}${path}`, {
      headers,
      ...options,
    });
    if (
      res.status === 401 &&
      typeof window !== 'undefined' &&
      path !== '/api/auth/login' &&
      path !== '/api/auth/register'
    ) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('tenant_slug');
    }
    if (!res.ok) {
      const err = await res.text();
      throw new Error(err || `HTTP ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.message === 'MOCK_MODE' || e.message?.includes('fetch') || e.message?.includes('Failed')) {
      USE_MOCK = true;
      throw new Error('MOCK_MODE');
    }
    throw e;
  }
}

// Helper: try real API, fallback to mock
async function withFallback<T>(realCall: () => Promise<T>, mockCall: () => Promise<T>): Promise<T> {
  try {
    return await realCall();
  } catch (e: any) {
    if (e.message === 'MOCK_MODE' || e.message?.includes('fetch') || e.message?.includes('Failed')) {
      USE_MOCK = true;
      return await mockCall();
    }
    throw e;
  }
}

/** MoySklad Marketplace OAuth — redirects browser to MoySklad, then back to FRONTEND_BASE callback */
export async function startMoySkladOAuth(): Promise<void> {
  if (USE_MOCK) {
    window.alert('Demo rejimida OAuth mavjud emas.');
    return;
  }
  const token = getAccessToken();
  if (!token) {
    window.alert('Avval tizimga kiring.');
    return;
  }
  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
  };
  const slug = getTenantSlug();
  if (slug) headers['X-Tenant-Slug'] = slug;

  const res = await fetch(`${API_BASE}/api/auth/moysklad/authorize-url`, { headers });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(t || `HTTP ${res.status}`);
  }
  const data = await res.json();
  if (data.url) {
    window.location.href = data.url;
  } else {
    throw new Error('No OAuth URL returned');
  }
}

// Auth
export const register = (data: unknown) =>
  withFallback(
    () => fetchJson('/api/auth/register', { method: 'POST', body: JSON.stringify(data) }),
    () => mock.mockRegister(data)
  );

export const login = (data: unknown) =>
  withFallback(
    () => fetchJson('/api/auth/login', { method: 'POST', body: JSON.stringify(data) }),
    () => mock.mockLogin(data)
  );

export const getMe = () =>
  withFallback(() => fetchJson('/api/auth/me'), () => mock.mockGetMe());

export const connectMoySklad = (data: unknown) =>
  withFallback(
    () => fetchJson('/api/auth/connect/moysklad', { method: 'POST', body: JSON.stringify(data) }),
    () => Promise.resolve({ success: true })
  );

export const connectSalesDoctor = (data: unknown) =>
  withFallback(
    () => fetchJson('/api/auth/connect/salesdoctor', { method: 'POST', body: JSON.stringify(data) }),
    () => Promise.resolve({ success: true })
  );

// Billing
export const getPlans = () =>
  withFallback(() => fetchJson('/api/billing/plans'), () => mock.mockGetPlans());

export const createPayment = (data: unknown) =>
  withFallback(
    () => fetchJson('/api/billing/subscribe', { method: 'POST', body: JSON.stringify(data) }),
    () => Promise.resolve({ success: true, payment_url: '#' })
  );

export const getBillingStatus = () =>
  withFallback(() => fetchJson('/api/billing/status'), () => mock.mockGetBillingStatus());

export const getPaymentHistory = () =>
  withFallback(() => fetchJson('/api/billing/history'), () => mock.mockGetPaymentHistory());

// Orders
export const getOrders = (params?: string) =>
  withFallback(
    () => fetchJson(`/api/orders${params ? '?' + params : ''}`),
    () => mock.mockGetOrders()
  );

export const getOrder = (id: string) =>
  withFallback(
    () => fetchJson(`/api/orders/${id}`),
    () => mock.mockGetOrders().then((o: any[]) => o.find((x: any) => x.id === id))
  );

export const syncOrder = (data: unknown) =>
  withFallback(
    () => fetchJson('/api/orders/sync', { method: 'POST', body: JSON.stringify(data) }),
    () => Promise.resolve({ success: true })
  );

export const updateOrderStatus = (id: string, status: string) =>
  withFallback(
    () => fetchJson(`/api/orders/${id}/status?status=${encodeURIComponent(status)}`, { method: 'POST' }),
    () => Promise.resolve({ success: true })
  );

// Stock
export const getStock = (params?: string) =>
  withFallback(
    () => fetchJson(`/api/stock${params ? '?' + params : ''}`),
    () => mock.mockGetStock()
  );

export const syncStock = () =>
  withFallback(
    () => fetchJson('/api/stock/sync', { method: 'POST' }),
    () => Promise.resolve({ success: true })
  );

// Clients
export const getClients = (params?: string) =>
  withFallback(
    () => fetchJson(`/api/clients${params ? '?' + params : ''}`),
    () => mock.mockGetClients()
  );

export const getClientStats = () =>
  withFallback(() => fetchJson('/api/clients/stats'), () => mock.mockGetClientStats());

export const syncClients = () =>
  withFallback(
    () => fetchJson('/api/clients/sync', { method: 'POST' }),
    () => Promise.resolve({ success: true })
  );

// Debts
export const getDebts = () =>
  withFallback(() => fetchJson('/api/debts'), () => mock.mockGetDebts());

export const getDebtSummary = () =>
  withFallback(() => fetchJson('/api/debts/summary'), () => mock.mockGetDebtSummary());

export const syncDebts = () =>
  withFallback(
    () => fetchJson('/api/debts/sync', { method: 'POST' }),
    () => Promise.resolve({ success: true })
  );

// Delivery
export const getDeliveries = (params?: string) =>
  withFallback(
    () => fetchJson(`/api/delivery${params ? '?' + params : ''}`),
    () => mock.mockGetDeliveries()
  );

export const updateDeliveryStatus = (id: number, status: string) =>
  withFallback(
    () => fetchJson(`/api/delivery/${id}/status?status=${encodeURIComponent(status)}`, { method: 'POST' }),
    () => Promise.resolve({ success: true })
  );

// Logs
export const getLogs = (params?: string) =>
  withFallback(
    () => fetchJson(`/api/logs${params ? '?' + params : ''}`),
    () => mock.mockGetLogs()
  );

export const getLogStats = () =>
  withFallback(() => fetchJson('/api/logs/stats'), () => mock.mockGetLogStats());

// Agents
export const getAgents = () =>
  withFallback(
    () => fetchJson('/api/agents'),
    () => Promise.resolve([])
  );

export const getAgentStats = () =>
  withFallback(
    () => fetchJson('/api/agents/stats'),
    () => Promise.resolve({ totalAgents: 0, activeAgents: 0 })
  );

// Health
export const getHealth = () =>
  withFallback(() => fetchJson('/health'), () => Promise.resolve({ status: 'mock' }));
