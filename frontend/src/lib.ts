import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { create } from 'zustand'

export type User = { id: string; email: string; username: string; full_name?: string; phone_number?: string; is_active: boolean; is_admin: boolean; created_at: string }
export type Product = { id: string; name: string; slug: string; description?: string; price: number; stock_quantity: number; category_id?: string; attributes: Record<string, unknown>; is_deleted?: boolean }
export type Category = { id: string; name: string; slug: string; parent_id?: string; sub_categories: Category[] }
export type Order = { id: string; total_price: number; discount_amount: number; status: string; created_at: string; coupon_code_snapshot?: string; shipping_address_snapshot?: string; items: { product_id: string; product_name: string; quantity: number; price_at_purchase: number }[] }
export type Cart = { id: string; items: { id: string; product_id: string; quantity: number; product: Pick<Product, 'id' | 'name' | 'slug' | 'price'> }[]; total_price: number; discount_amount: number; total_after_discount: number; coupon_code?: string }
export type Toast = { id: number; type: 'success' | 'error'; message: string }

const BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
export const api = axios.create({ baseURL: BASE })
let refreshing: Promise<string> | undefined
export const authStore = create<{ user?: User; access?: string; refresh?: string; cartOpen: boolean; toasts: Toast[]; setSession: (user: User, tokens?: { access_token: string; refresh_token: string }) => void; clear: () => void; toggleCart: () => void; toast: (message: string, type?: Toast['type']) => void }>((set) => ({
  access: undefined, refresh: localStorage.getItem('refresh_token') || undefined, cartOpen: false, toasts: [],
  setSession: (user, tokens) => { if (tokens) localStorage.setItem('refresh_token', tokens.refresh_token); set({ user, access: tokens?.access_token, refresh: tokens?.refresh_token }) },
  clear: () => { localStorage.removeItem('refresh_token'); set({ user: undefined, access: undefined, refresh: undefined }) },
  toggleCart: () => set((s) => ({ cartOpen: !s.cartOpen })),
  toast: (message, type = 'success') => { const id = Date.now(); set((s) => ({ toasts: [...s.toasts, { id, type, message }] })); setTimeout(() => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })), 4200) }
}))

api.interceptors.request.use((config: InternalAxiosRequestConfig) => { const token = authStore.getState().access; if (token) config.headers.Authorization = `Bearer ${token}`; return config })
api.interceptors.response.use((r) => r, async (error: AxiosError<{ detail?: string }>) => {
  const original = error.config as InternalAxiosRequestConfig & { _retried?: boolean }
  if (error.response?.status !== 401 || original?._retried || !authStore.getState().refresh) throw error
  original._retried = true
  try {
    refreshing ??= axios.post(`${BASE}/auth/refresh`, undefined, { params: { refresh_token: authStore.getState().refresh } }).then((r) => r.data.access_token).finally(() => { refreshing = undefined })
    const access = await refreshing; authStore.setState({ access }); original.headers.Authorization = `Bearer ${access}`; return api(original)
  } catch { authStore.getState().clear(); throw error }
})
export const message = (err: unknown) => axios.isAxiosError(err) ? err.response?.data?.detail || 'The service could not complete that request.' : 'The service could not complete that request.'
export const money = (n?: number) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2 }).format(n || 0)
export const date = (d?: string) => d ? new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(d)) : '—'

export const endpoints = {
  products: () => api.get<Product[]>('/api/v1/products/').then((r) => r.data), product: (id: string) => api.get<Product>(`/api/v1/products/${id}`).then((r) => r.data), categories: () => api.get<Category[]>('/api/v1/products/categories').then((r) => r.data), searchProducts: (query: string) => api.get<Product[]>('/api/v1/products/search', { params: { q: query } }).then((r) => r.data),
  cart: () => api.get<Cart>('/api/v1/cart/').then((r) => r.data), orders: () => api.get<Order[]>('/api/v1/orders/').then((r) => r.data), order: (id: string) => api.get<Order>(`/api/v1/orders/${id}`).then((r) => r.data), addresses: () => api.get<any[]>('/api/v1/addresses/').then((r) => r.data), me: () => api.get<User>('/api/v1/users/me').then((r) => r.data),
  adminProducts: () => api.get<Product[]>('/api/v1/admin/products').then((r) => r.data), adminOrders: () => api.get<Order[]>('/api/v1/admin/orders').then((r) => r.data), coupons: () => api.get<any>('/api/v1/admin/coupons').then((r) => r.data), inventory: () => api.get<any>('/api/v1/admin/inventory/report').then((r) => r.data), lowStock: () => api.get<any[]>('/api/v1/admin/inventory/low-stock').then((r) => r.data),
}
