export interface Order {
  id: string;
  clientName: string;
  phone: string;
  agentName: string;
  items: { sku: string; name: string; qty: number; price: number }[];
  total: number;
  status: 'Новый' | 'В обработке' | 'Отгружен' | 'Отменен' | 'В пути' | 'Доставлен';
  comment: string;
  createdAt: string;
  syncStatus: 'synced' | 'pending' | 'error';
}

export interface StockItem {
  sku: string;
  name: string;
  qty: number;
  price: number;
  warehouse: string;
  lastSync: string;
}

export interface Client {
  id: string;
  name: string;
  phone: string;
  address: string;
  location: string;
  type: 'Опт' | 'Розница';
  debt: number;
  debtLimit: number;
  lastOrder: string;
}

export interface DebtRecord {
  clientName: string;
  phone: string;
  totalDebt: number;
  paid: number;
  remaining: number;
  lastPayment: string;
}

export interface Delivery {
  orderId: string;
  clientName: string;
  address: string;
  courier: string;
  status: 'В пути' | 'Доставлен' | 'Отказ';
  dispatchedAt: string;
  deliveredAt?: string;
}

export interface LogEntry {
  id: string;
  timestamp: string;
  type: 'info' | 'warning' | 'error' | 'success';
  module: string;
  message: string;
  retryCount?: number;
}

export const orders: Order[] = [
  {
    id: 'ORD-2024-001',
    clientName: 'ООО "ТехноПром"',
    phone: '+998 90 123 45 67',
    agentName: 'Алишер Каримов',
    items: [
      { sku: 'SKU-1001', name: 'Смартфон Samsung A54', qty: 5, price: 4500000 },
      { sku: 'SKU-1002', name: 'Наушники AirPods Pro', qty: 3, price: 2800000 },
    ],
    total: 30900000,
    status: 'Отгружен',
    comment: 'Срочная доставка',
    createdAt: '2024-01-15T09:30:00',
    syncStatus: 'synced',
  },
  {
    id: 'ORD-2024-002',
    clientName: 'ИП Рахимов Д.',
    phone: '+998 91 234 56 78',
    agentName: 'Баходир Назаров',
    items: [
      { sku: 'SKU-1003', name: 'Ноутбук HP Pavilion', qty: 2, price: 8500000 },
    ],
    total: 17000000,
    status: 'В обработке',
    comment: 'Предоплата 50%',
    createdAt: '2024-01-15T11:15:00',
    syncStatus: 'synced',
  },
  {
    id: 'ORD-2024-003',
    clientName: 'ООО "МегаТрейд"',
    phone: '+998 93 345 67 89',
    agentName: 'Алишер Каримов',
    items: [
      { sku: 'SKU-1001', name: 'Смартфон Samsung A54', qty: 10, price: 4500000 },
      { sku: 'SKU-1004', name: 'Планшет iPad Air', qty: 4, price: 7200000 },
    ],
    total: 73800000,
    status: 'Новый',
    comment: 'Оптовая скидка 10%',
    createdAt: '2024-01-15T14:20:00',
    syncStatus: 'pending',
  },
  {
    id: 'ORD-2024-004',
    clientName: 'ИП Саидов М.',
    phone: '+998 94 456 78 90',
    agentName: 'Баходир Назаров',
    items: [
      { sku: 'SKU-1005', name: 'Монитор LG 27"', qty: 3, price: 3200000 },
    ],
    total: 9600000,
    status: 'В пути',
    comment: '',
    createdAt: '2024-01-15T16:45:00',
    syncStatus: 'synced',
  },
  {
    id: 'ORD-2024-005',
    clientName: 'ООО "АзияЭлектро"',
    phone: '+998 95 567 89 01',
    agentName: 'Алишер Каримов',
    items: [
      { sku: 'SKU-1006', name: 'ИБП APC 1500VA', qty: 6, price: 1800000 },
      { sku: 'SKU-1007', name: 'Кабель UTP Cat6', qty: 20, price: 85000 },
    ],
    total: 12500000,
    status: 'Доставлен',
    comment: 'Доставка выполнена',
    createdAt: '2024-01-14T10:00:00',
    syncStatus: 'synced',
  },
  {
    id: 'ORD-2024-006',
    clientName: 'ИП Хамидов А.',
    phone: '+998 90 678 90 12',
    agentName: 'Баходир Назаров',
    items: [
      { sku: 'SKU-1008', name: 'Веб-камера Logitech', qty: 8, price: 450000 },
    ],
    total: 3600000,
    status: 'Отменен',
    comment: 'Клиент отказался',
    createdAt: '2024-01-14T13:30:00',
    syncStatus: 'synced',
  },
];

export const stockItems: StockItem[] = [
  { sku: 'SKU-1001', name: 'Смартфон Samsung A54', qty: 45, price: 4500000, warehouse: 'Основной склад', lastSync: '2024-01-15T17:00:00' },
  { sku: 'SKU-1002', name: 'Наушники AirPods Pro', qty: 28, price: 2800000, warehouse: 'Основной склад', lastSync: '2024-01-15T17:00:00' },
  { sku: 'SKU-1003', name: 'Ноутбук HP Pavilion', qty: 12, price: 8500000, warehouse: 'Основной склад', lastSync: '2024-01-15T17:00:00' },
  { sku: 'SKU-1004', name: 'Планшет iPad Air', qty: 18, price: 7200000, warehouse: 'Основной склад', lastSync: '2024-01-15T17:00:00' },
  { sku: 'SKU-1005', name: 'Монитор LG 27"', qty: 7, price: 3200000, warehouse: 'Основной склад', lastSync: '2024-01-15T17:00:00' },
  { sku: 'SKU-1006', name: 'ИБП APC 1500VA', qty: 22, price: 1800000, warehouse: 'Склад №2', lastSync: '2024-01-15T17:00:00' },
  { sku: 'SKU-1007', name: 'Кабель UTP Cat6', qty: 150, price: 85000, warehouse: 'Склад №2', lastSync: '2024-01-15T17:00:00' },
  { sku: 'SKU-1008', name: 'Веб-камера Logitech', qty: 35, price: 450000, warehouse: 'Основной склад', lastSync: '2024-01-15T17:00:00' },
  { sku: 'SKU-1009', name: 'Клавиатура механическая', qty: 3, price: 650000, warehouse: 'Основной склад', lastSync: '2024-01-15T17:00:00' },
  { sku: 'SKU-1010', name: 'Мышь игровая Razer', qty: 0, price: 890000, warehouse: 'Основной склад', lastSync: '2024-01-15T17:00:00' },
];

export const clients: Client[] = [
  { id: 'CLI-001', name: 'ООО "ТехноПром"', phone: '+998 90 123 45 67', address: 'г. Ташкент, ул. Амира Темура, 45', location: '41.2995° N, 69.2401° E', type: 'Опт', debt: 12500000, debtLimit: 50000000, lastOrder: '2024-01-15' },
  { id: 'CLI-002', name: 'ИП Рахимов Д.', phone: '+998 91 234 56 78', address: 'г. Ташкент, ул. Навои, 12', location: '41.3111° N, 69.2797° E', type: 'Розница', debt: 3200000, debtLimit: 10000000, lastOrder: '2024-01-15' },
  { id: 'CLI-003', name: 'ООО "МегаТрейд"', phone: '+998 93 345 67 89', address: 'г. Ташкент, ул. Ислама Каримова, 78', location: '41.2856° N, 69.2039° E', type: 'Опт', debt: 48700000, debtLimit: 50000000, lastOrder: '2024-01-15' },
  { id: 'CLI-004', name: 'ИП Саидов М.', phone: '+998 94 456 78 90', address: 'г. Ташкент, ул. Шота Руставели, 33', location: '41.3222° N, 69.2483° E', type: 'Розница', debt: 1500000, debtLimit: 8000000, lastOrder: '2024-01-15' },
  { id: 'CLI-005', name: 'ООО "АзияЭлектро"', phone: '+998 95 567 89 01', address: 'г. Ташкент, ул. Фаргона Йули, 112', location: '41.2647° N, 69.2167° E', type: 'Опт', debt: 8900000, debtLimit: 30000000, lastOrder: '2024-01-14' },
  { id: 'CLI-006', name: 'ИП Хамидов А.', phone: '+998 90 678 90 12', address: 'г. Ташкент, ул. Бабура, 56', location: '41.3056° N, 69.2344° E', type: 'Розница', debt: 0, debtLimit: 5000000, lastOrder: '2024-01-14' },
  { id: 'CLI-007', name: 'ООО "СофтЛайн"', phone: '+998 91 789 01 23', address: 'г. Ташкент, ул. Алишера Навои, 89', location: '41.2989° N, 69.2711° E', type: 'Опт', debt: 62000000, debtLimit: 60000000, lastOrder: '2024-01-13' },
  { id: 'CLI-008', name: 'ИП Юсупов К.', phone: '+998 93 890 12 34', address: 'г. Ташкент, ул. Мукими, 21', location: '41.3122° N, 69.2589° E', type: 'Розница', debt: 2100000, debtLimit: 7000000, lastOrder: '2024-01-13' },
];

export const debts: DebtRecord[] = [
  { clientName: 'ООО "ТехноПром"', phone: '+998 90 123 45 67', totalDebt: 12500000, paid: 18400000, remaining: 12500000, lastPayment: '2024-01-10' },
  { clientName: 'ИП Рахимов Д.', phone: '+998 91 234 56 78', totalDebt: 3200000, paid: 13800000, remaining: 3200000, lastPayment: '2024-01-12' },
  { clientName: 'ООО "МегаТрейд"', phone: '+998 93 345 67 89', totalDebt: 48700000, paid: 25100000, remaining: 48700000, lastPayment: '2024-01-14' },
  { clientName: 'ИП Саидов М.', phone: '+998 94 456 78 90', totalDebt: 1500000, paid: 8100000, remaining: 1500000, lastPayment: '2024-01-11' },
  { clientName: 'ООО "АзияЭлектро"', phone: '+998 95 567 89 01', totalDebt: 8900000, paid: 36000000, remaining: 8900000, lastPayment: '2024-01-09' },
  { clientName: 'ИП Хамидов А.', phone: '+998 90 678 90 12', totalDebt: 0, paid: 3600000, remaining: 0, lastPayment: '2024-01-14' },
  { clientName: 'ООО "СофтЛайн"', phone: '+998 91 789 01 23', totalDebt: 62000000, paid: 18000000, remaining: 62000000, lastPayment: '2024-01-08' },
  { clientName: 'ИП Юсупов К.', phone: '+998 93 890 12 34', totalDebt: 2100000, paid: 7500000, remaining: 2100000, lastPayment: '2024-01-13' },
];

export const deliveries: Delivery[] = [
  { orderId: 'ORD-2024-004', clientName: 'ИП Саидов М.', address: 'г. Ташкент, ул. Шота Руставели, 33', courier: 'Рустам Алиев', status: 'В пути', dispatchedAt: '2024-01-15T10:00:00' },
  { orderId: 'ORD-2024-005', clientName: 'ООО "АзияЭлектро"', address: 'г. Ташкент, ул. Фаргона Йули, 112', courier: 'Даврон Бекмуродов', status: 'Доставлен', dispatchedAt: '2024-01-14T09:00:00', deliveredAt: '2024-01-14T14:30:00' },
  { orderId: 'ORD-2024-001', clientName: 'ООО "ТехноПром"', address: 'г. Ташкент, ул. Амира Темура, 45', courier: 'Рустам Алиев', status: 'Доставлен', dispatchedAt: '2024-01-15T08:00:00', deliveredAt: '2024-01-15T12:15:00' },
];

export const logs: LogEntry[] = [
  { id: 'LOG-001', timestamp: '2024-01-15T17:00:00', type: 'success', module: 'Stock Sync', message: 'Остатки успешно синхронизированы. 10 товаров обновлено.' },
  { id: 'LOG-002', timestamp: '2024-01-15T16:45:00', type: 'info', module: 'Order Sync', message: 'Заказ ORD-2024-004 отправлен в MoySklad. Контрагент найден.' },
  { id: 'LOG-003', timestamp: '2024-01-15T16:30:00', type: 'warning', module: 'Client Sync', message: 'Обнаружен дубликат клиента: ИП Рахимов Д. Объединение выполнено.' },
  { id: 'LOG-004', timestamp: '2024-01-15T16:15:00', type: 'error', module: 'Order Sync', message: 'Товар SKU-1010 не найден в MoySklad. Заказ ORD-2024-007 заблокирован.', retryCount: 3 },
  { id: 'LOG-005', timestamp: '2024-01-15T16:00:00', type: 'success', module: 'Debt Sync', message: 'Дебиторка синхронизирована. 8 клиентов обновлено.' },
  { id: 'LOG-006', timestamp: '2024-01-15T15:45:00', type: 'info', module: 'Delivery', message: 'Заказ ORD-2024-005 отмечен как "Доставлен" в Sales Doctor.' },
  { id: 'LOG-007', timestamp: '2024-01-15T15:30:00', type: 'warning', module: 'Order Sync', message: 'Клиент ООО "СофтЛайн" превысил лимит задолженности. Заказ требует подтверждения.' },
  { id: 'LOG-008', timestamp: '2024-01-15T15:15:00', type: 'success', module: 'Webhook', message: 'Получен webhook order.updated от MoySklad. Статус обновлен.' },
  { id: 'LOG-009', timestamp: '2024-01-15T15:00:00', type: 'error', module: 'Stock Sync', message: 'Ошибка соединения с MoySklad API. Таймаут.', retryCount: 2 },
  { id: 'LOG-010', timestamp: '2024-01-15T14:45:00', type: 'info', module: 'Client Sync', message: 'Новый клиент ИП Юсупов К. создан в MoySklad.' },
  { id: 'LOG-011', timestamp: '2024-01-15T14:30:00', type: 'success', module: 'Order Sync', message: 'Заказ ORD-2024-003 успешно создан в MoySklad. ID: 8f3a2b1c.' },
  { id: 'LOG-012', timestamp: '2024-01-15T14:15:00', type: 'warning', module: 'Stock Sync', message: 'Товар SKU-1009 низкий остаток (3 шт.). Уведомление отправлено.' },
];

export const kpiData = {
  totalOrders: 156,
  ordersToday: 6,
  totalRevenue: 487500000,
  revenueToday: 147400000,
  activeAgents: 4,
  syncErrors: 2,
  pendingSync: 1,
  lastSync: '2024-01-15T17:00:00',
};

export const agentSales = [
  { name: 'Алишер Каримов', orders: 68, revenue: 210000000, clients: 24 },
  { name: 'Баходир Назаров', orders: 52, revenue: 165000000, clients: 19 },
  { name: 'Сardор Умаров', orders: 23, revenue: 78000000, clients: 12 },
  { name: 'Нодир Алиев', orders: 13, revenue: 34500000, clients: 8 },
];

export const monthlyRevenue = [
  { month: 'Авг', revenue: 320000000, profit: 64000000 },
  { month: 'Сен', revenue: 380000000, profit: 76000000 },
  { month: 'Окт', revenue: 410000000, profit: 82000000 },
  { month: 'Ноя', revenue: 450000000, profit: 90000000 },
  { month: 'Дек', revenue: 470000000, profit: 94000000 },
  { month: 'Янв', revenue: 487500000, profit: 97500000 },
];
