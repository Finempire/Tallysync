// src/api/client.ts
import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' }
})

// JWT interceptor
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true
      try {
        const refreshToken = localStorage.getItem('refresh_token')
        const { data } = await axios.post('/api/v1/auth/refresh/', { refresh: refreshToken })
        localStorage.setItem('access_token', data.access)
        originalRequest.headers.Authorization = `Bearer ${data.access}`
        return api(originalRequest)
      } catch {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

// Auth API
export const authApi = {
  login: (email: string, password: string) => api.post('/auth/login/', { email, password }),
  register: (data: any) => api.post('/auth/register/', data),
  getProfile: () => api.get('/auth/profile/'),
  updateProfile: (data: any) => api.patch('/auth/profile/', data),
  changePassword: (data: any) => api.post('/auth/change-password/', data),
}

// Companies API
export const companiesApi = {
  list: () => api.get('/companies/'),
  create: (data: any) => api.post('/companies/', data),
  get: (id: number) => api.get(`/companies/${id}/`),
  update: (id: number, data: any) => api.patch(`/companies/${id}/`, data),
  delete: (id: number) => api.delete(`/companies/${id}/`),
  getLedgers: (companyId: number) => api.get(`/companies/${companyId}/ledgers/`),
  getMappingRules: (companyId: number) => api.get(`/companies/${companyId}/mapping-rules/`),
  createMappingRule: (companyId: number, data: any) => api.post(`/companies/${companyId}/mapping-rules/`, data),
}

// Bank Statements API
export const bankStatementsApi = {
  listAccounts: () => api.get('/bank-statements/accounts/'),
  createAccount: (data: any) => api.post('/bank-statements/accounts/', data),
  uploadStatement: (data: FormData) => api.post('/bank-statements/upload/', data, { headers: { 'Content-Type': 'multipart/form-data' } }),
  listStatements: () => api.get('/bank-statements/'),
  getTransactions: (statementId: number) => api.get(`/bank-statements/${statementId}/transactions/`),
  mapTransactions: (data: any) => api.post('/bank-statements/transactions/map/', data),
  approveTransactions: (data: any) => api.post('/bank-statements/transactions/approve/', data),
  autoMapTransactions: (data: any) => api.post('/bank-statements/transactions/auto-map/', data),
  generateVouchers: (data: any) => api.post('/bank-statements/generate-vouchers/', data),
  pushVouchers: (data: any) => api.post('/bank-statements/push-vouchers/', data),
  deleteStatement: (id: number) => api.delete(`/bank-statements/${id}/`),
}

// Vouchers API
export const vouchersApi = {
  list: (params?: any) => api.get('/vouchers/', { params }),
  create: (data: any) => api.post('/vouchers/', data),
  update: (id: number, data: any) => api.patch(`/vouchers/${id}/`, data),
  get: (id: number) => api.get(`/vouchers/${id}/`),
  delete: (id: number) => api.delete(`/vouchers/${id}/`),
  approve: (id: number) => api.post(`/vouchers/${id}/approve/`),
  bulkApprove: (ids: number[]) => api.post('/vouchers/bulk-approve/', { voucher_ids: ids }),
  pushToTally: (id: number) => api.post(`/vouchers/${id}/push-tally/`),
  bulkPushToTally: (ids: number[]) => api.post('/vouchers/bulk-push-tally/', { voucher_ids: ids }),
  getXmlPreview: (id: number) => api.get(`/vouchers/${id}/xml-preview/`),
  // Settings & Import
  getSettings: (companyId: number, type: string) => api.get('/vouchers/settings/', { params: { company_id: companyId, type } }),
  updateSettings: (companyId: number, type: string, data: any) => api.put('/vouchers/settings/', data, { params: { company_id: companyId, type } }),
  import: (data: FormData) => api.post('/vouchers/import/', data, { headers: { 'Content-Type': 'multipart/form-data' } }),
  downloadTemplate: (type: string) => api.get('/vouchers/template/', { params: { type }, responseType: 'blob' }),
}

// Sales Import Workflow API (Suvit-style multi-step)
export const salesImportApi = {
  // Step 1: Upload
  upload: (data: FormData) => api.post('/vouchers/sales-import/upload/', data, { headers: { 'Content-Type': 'multipart/form-data' } }),
  get: (id: number) => api.get(`/vouchers/sales-import/${id}/`),

  // Step 2: Field Mapping
  getFieldMapping: (id: number) => api.get(`/vouchers/sales-import/${id}/field-mapping/`),
  saveFieldMapping: (id: number, mapping: any) => api.post(`/vouchers/sales-import/${id}/field-mapping/`, { mapping }),
  getPreview: (id: number) => api.get(`/vouchers/sales-import/${id}/preview/`),

  // Step 3: GST Config
  getGSTConfig: (id: number) => api.get(`/vouchers/sales-import/${id}/gst-config/`),
  saveGSTConfig: (id: number, config: any) => api.post(`/vouchers/sales-import/${id}/gst-config/`, { config }),

  // Step 4: Ledger Mapping
  getLedgerMapping: (id: number) => api.get(`/vouchers/sales-import/${id}/ledger-mapping/`),
  saveLedgerMapping: (id: number, mapping: any) => api.post(`/vouchers/sales-import/${id}/ledger-mapping/`, { mapping }),

  // Step 5: Processing Screen
  getRows: (id: number, status?: string) => api.get(`/vouchers/sales-import/${id}/rows/`, { params: status ? { status } : {} }),
  updateRow: (id: number, rowId: number, data: any) => api.patch(`/vouchers/sales-import/${id}/rows/${rowId}/`, data),
  bulkUpdate: (id: number, rowIds: number[], updates: any) => api.post(`/vouchers/sales-import/${id}/bulk-update/`, { row_ids: rowIds, updates }),

  // Master Creation
  createParty: (id: number, data: any) => api.post(`/vouchers/sales-import/${id}/create-party/`, data),
  createItem: (id: number, data: any) => api.post(`/vouchers/sales-import/${id}/create-item/`, data),

  // Processing & Tally Push
  process: (id: number, rowIds?: number[]) => api.post(`/vouchers/sales-import/${id}/process/`, { row_ids: rowIds }),
  pushToTally: (id: number, rowIds?: number[]) => api.post(`/vouchers/sales-import/${id}/push-tally/`, { row_ids: rowIds }),
}

// Tally Connector API
export const tallyApi = {
  listConnectors: () => api.get('/tally/connectors/'),
  createConnector: (data: any) => api.post('/tally/connectors/', data),
  // Direct Tally Connection (no desktop connector needed)
  getStatus: () => api.get('/tally/direct/status/'),
  getCompanies: () => api.get('/tally/direct/companies/'),
  getLedgers: (company: string) => api.get('/tally/direct/ledgers/', { params: { company } }),
  syncLedgers: (company: string) => api.post('/tally/direct/sync-ledgers/', { company }),
  getVoucherTypes: (company: string) => api.get('/tally/direct/voucher-types/', { params: { company } }),
}

// GST API
export const gstApi = {
  listEInvoices: () => api.get('/gst/einvoices/'),
  generateEInvoice: (id: number) => api.post(`/gst/einvoices/${id}/generate/`),
  cancelEInvoice: (id: number, reason: string) => api.post(`/gst/einvoices/${id}/cancel/`, { reason }),
  getGSTR1Summary: (companyId: number, period: string) => api.get(`/gst/${companyId}/gstr1-summary/`, { params: { period } }),
  computeGSTR3B: (companyId: number, period: string) => api.post(`/gst/${companyId}/gstr3b-compute/`, { period }),
  reconcileGSTR2B: (companyId: number, period: string) => api.post(`/gst/${companyId}/reconcile/`, { period }),
}

// Invoices API
export const invoicesApi = {
  upload: (data: FormData) => api.post('/invoices/upload/', data, { headers: { 'Content-Type': 'multipart/form-data' } }),
  bulkUpload: (data: FormData) => api.post('/invoices/bulk-upload/', data, { headers: { 'Content-Type': 'multipart/form-data' } }),
  list: (params?: any) => api.get('/invoices/', { params }),
  get: (id: number) => api.get(`/invoices/${id}/`),
  approve: (id: number, data: any) => api.post(`/invoices/${id}/approve/`, data),
  createVoucher: (id: number) => api.post(`/invoices/${id}/create-voucher/`),
}

// Payroll API
export const payrollApi = {
  listEmployees: (params?: any) => api.get('/payroll/employees/', { params }),
  createEmployee: (data: any) => api.post('/payroll/employees/', data),
  getEmployee: (id: number) => api.get(`/payroll/employees/${id}/`),
  updateEmployee: (id: number, data: any) => api.patch(`/payroll/employees/${id}/`, data),
  listSalaryStructures: () => api.get('/payroll/salary-structures/'),
  processPayroll: (companyId: number, month: number, year: number) => api.post(`/payroll/${companyId}/process/`, { month, year }),
  listPayrollRuns: () => api.get('/payroll/runs/'),
  getPayslips: (payrollId: number) => api.get(`/payroll/runs/${payrollId}/payslips/`),
  exportToTally: (payrollId: number) => api.post(`/payroll/runs/${payrollId}/export-tally/`),
}

// Reports API
export const reportsApi = {
  getDashboardStats: (companyId: number) => api.get(`/reports/${companyId}/dashboard/`),
  getTrends: (companyId: number, days?: number) => api.get(`/reports/${companyId}/trends/`, { params: { days } }),
  getCashFlowForecast: (companyId: number, days?: number) => api.get(`/reports/${companyId}/cash-flow-forecast/`, { params: { days } }),
  generateReport: (companyId: number, data: any) => api.post(`/reports/${companyId}/generate/`, data),
  listReports: (companyId: number) => api.get(`/reports/${companyId}/reports/`),
}

// Notifications API
export const notificationsApi = {
  list: () => api.get('/notifications/'),
  markRead: (id: number) => api.post(`/notifications/${id}/read/`),
  markAllRead: () => api.post('/notifications/read-all/'),
  getPreferences: () => api.get('/notifications/preferences/'),
  updatePreferences: (data: any) => api.patch('/notifications/preferences/', data),
  getUnreadCount: () => api.get('/notifications/unread-count/'),
  getComplianceReminders: (companyId: number) => api.get(`/notifications/${companyId}/compliance-reminders/`),
}

export default api
