import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { create } from 'zustand'

export type User = { id: string; email: string; username: string; full_name?: string; phone_number?: string; is_active: boolean; is_admin: boolean; created_at: string }
export type Product = { id: string; name: string; slug: string; description?: string; price: number; stock_quantity: number; category_id?: string; attributes: Record<string, unknown>; is_deleted?: boolean }
export type Category = { id: string; name: string; slug: string; parent_id?: string; sub_categories: Category[] }
export type Order = { id: string; total_price: number; discount_amount: number; status: string; created_at: string; coupon_code_snapshot?: string; shipping_address_snapshot?: string; items: { product_id: string; product_name: string; quantity: number; price_at_purchase: number }[] }
export type Cart = { id: string; items: { id: string; product_id: string; quantity: number; product: Pick<Product, 'id' | 'name' | 'slug' | 'price'> }[]; total_price: number; discount_amount: number; total_after_discount: number; coupon_code?: string }
export type Toast = { id: number; type: 'success' | 'error'; message: string }

const BASE = import.meta.env.VITE_API_BASE_URL || (import.meta.env.PROD ? 'https://api.alpha-commerce.tech' : 'http://localhost:8000')
export const api = axios.create({ baseURL: BASE })
type SessionTokens = { access_token: string; refresh_token: string }
let refreshing: { token: string; request: Promise<SessionTokens> } | undefined
export const authStore = create<{ user?: User; access?: string; refresh?: string; cartOpen: boolean; toasts: Toast[]; setSession: (user: User, tokens: SessionTokens) => void; clear: () => void; toggleCart: () => void; toast: (message: string, type?: Toast['type']) => void }>((set) => ({
  access: undefined, refresh: typeof window === 'undefined' ? undefined : localStorage.getItem('refresh_token') || undefined, cartOpen: false, toasts: [],
  setSession: (user, tokens) => { localStorage.setItem('refresh_token', tokens.refresh_token); set({ user, access: tokens.access_token, refresh: tokens.refresh_token }) },
  clear: () => { localStorage.removeItem('refresh_token'); set({ user: undefined, access: undefined, refresh: undefined, cartOpen: false }) },
  toggleCart: () => set((s) => ({ cartOpen: !s.cartOpen })),
  toast: (message, type = 'success') => { const id = Date.now(); set((s) => ({ toasts: [...s.toasts, { id, type, message }] })); setTimeout(() => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })), 4200) }
}))

api.interceptors.request.use((config: InternalAxiosRequestConfig) => { const token = authStore.getState().access; if (token) config.headers.Authorization = `Bearer ${token}`; return config })
api.interceptors.response.use((response) => response, async (error: AxiosError) => {
  const original = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined
  const session = authStore.getState()
  const token = session.refresh
  if (error.response?.status !== 401 || !original || original._retried || !token || original.url === '/auth/login') throw error
  original._retried = true
  // A concurrent response may have already rotated the token used for this request.
  if (session.access && original.headers.Authorization !== `Bearer ${session.access}`) return api(original)
  try {
    if (refreshing?.token !== token) {
      const request = axios.post<SessionTokens>(`${BASE}/auth/refresh`, undefined, { params: { refresh_token: token } })
        .then(({ data }) => data).finally(() => { if (refreshing?.token === token) refreshing = undefined })
      refreshing = { token, request }
    }
    const tokens = await refreshing.request
    const current = authStore.getState()
    if (current.refresh === token) {
      localStorage.setItem('refresh_token', tokens.refresh_token)
      authStore.setState({ access: tokens.access_token, refresh: tokens.refresh_token })
    } else if (current.refresh !== tokens.refresh_token) {
      throw error
    }
  } catch {
    if (authStore.getState().refresh === token) authStore.getState().clear()
    throw error
  }
  return api(original)
})
export const message = (err: unknown) => axios.isAxiosError(err) ? err.response?.data?.message || err.response?.data?.detail || 'The service could not complete that request.' : 'The service could not complete that request.'
export const money = (n?: number) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2 }).format(n || 0)
export const date = (d?: string) => d ? new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(d)) : '—'

export const endpoints = {
  products: () => api.get<Product[]>('/api/v1/products/').then((r) => r.data), product: (id: string) => api.get<Product>(`/api/v1/products/${id}`).then((r) => r.data), categories: () => api.get<Category[]>('/api/v1/products/categories').then((r) => r.data), searchProducts: (query: string) => api.get<Product[]>('/api/v1/products/search', { params: { q: query } }).then((r) => r.data),
  cart: () => api.get<Cart>('/api/v1/cart/').then((r) => r.data), orders: () => api.get<Order[]>('/api/v1/orders/').then((r) => r.data), order: (id: string) => api.get<Order>(`/api/v1/orders/${id}`).then((r) => r.data), addresses: () => api.get<any[]>('/api/v1/addresses/').then((r) => r.data), me: () => api.get<User>('/api/v1/users/me').then((r) => r.data),
  adminProducts: () => api.get<Product[]>('/api/v1/admin/products').then((r) => r.data), adminOrders: () => api.get<Order[]>('/api/v1/admin/orders').then((r) => r.data), coupons: () => api.get<any>('/api/v1/admin/coupons').then((r) => r.data), inventory: () => api.get<any>('/api/v1/admin/inventory/report').then((r) => r.data), lowStock: () => api.get<any[]>('/api/v1/admin/inventory/low-stock').then((r) => r.data),
}
