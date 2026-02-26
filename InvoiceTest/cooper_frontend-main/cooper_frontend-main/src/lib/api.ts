// Force relative path if env var is pointing to localhost, effectively ignoring local environment overrides
// that break network access.
const envBaseUrl = import.meta.env.VITE_API_BASE_URL;
const isLocalhost = envBaseUrl && (envBaseUrl.includes('localhost') || envBaseUrl.includes('127.0.0.1'));
export const API_BASE_URL = (envBaseUrl && !isLocalhost) ? envBaseUrl : '/';

// API Endpoints
export const API_ENDPOINTS = {
  // Auth endpoints
  LOGIN: 'api/auth/login/',
  LOGOUT: 'api/auth/logout/',
  REFRESH: 'api/auth/refresh/',

  // Invoice endpoints
  INVOICES: 'api/sales/all-invoices/',
  INVOICE_DETAILS: (id: string) => `api/sales/invoices/${id}/`,
  UPLOAD_INVOICES: 'api/sales/upload-invoice-excel/',
  UPLOAD_PART_MAP: 'api/sales/upload-part-map-excel/',
  AVAILABLE_INVOICES: 'api/sales/available-invoices/',
  BALANCE_HISTORY: 'api/sales/invoice-balance-history/',

  // Sales endpoints
  SALES_INVOICES: '/api/sales/invoices/',
  SALES_INVOICE_DETAILS: (id: string) => `/api/sales/invoices/${id}/`,

  // Retail endpoints
  CREATE_RETAIL_INVOICE: 'api/retail/invoice/create/',
  VIEW_RECONCILED_INVOICES: 'api/retail/invoice-entry-consumptions/',
  INPUTTED_ENTRIES: 'api/retail/invoice-entries/',

  // Reconciliation endpoints
  RECONCILIATIONS: '/reconciliations/',
  RECONCILIATION_DETAILS: (id: string) => `/reconciliations/${id}/`,

  // Dashboard endpoints
  DASHBOARD_STATS: 'api/sales/dashboard/',
  DASHBOARD_SUMMARY: '/dashboard/summary/',

  // Export endpoints
  EXPORT_RECONCILIATIONS: 'api/retail/retail-invoice-combined/export/',

  // Part History endpoints
  PART_HISTORY: (partNumber: string) => `api/sales/parts/${partNumber}/history/`,
  PART_HISTORY_EXPORT: (partNumber: string) => `api/sales/parts/${partNumber}/export/`,
  EXPORT_STOCK_LEDGER: 'api/sales/export-stock-ledger/',

  // Bulk Upload endpoints
  BULK_TEMPLATE: 'api/retail/bulk-template/',
  BULK_UPLOAD: 'api/retail/bulk-upload/',
  BULK_PREVIEW: 'api/retail/bulk-preview/',
  BULK_COMMIT: 'api/retail/bulk-upload-commit/',
} as const;

// API Client configuration
export const API_CONFIG = {
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
} as const;

// Helper function to build full API URLs
export const buildApiUrl = (endpoint: string): string => {
  const baseUrl = API_BASE_URL.endsWith('/') ? API_BASE_URL : `${API_BASE_URL}/`;
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint.slice(1) : endpoint;
  return `${baseUrl}${cleanEndpoint}`;
};