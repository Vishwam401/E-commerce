import { useEffect, useState } from 'react'
import { Link, Navigate, Outlet, Route, Routes, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Activity, ArrowLeft, ArrowRight, CreditCard, FilePenLine, MapPin, Package, Plus, RefreshCw, RotateCcw, XCircle } from 'lucide-react'
import { api, authStore, date, endpoints, message, money } from './lib'
import { CartDrawer, Footer, Header, Skeleton, Status, Toasts } from './components'
import { AdminHome, AdminOrders, AdminProducts, Coupons, Inventory } from './admin'
import { HomeCatalog, ProductPage, Shop } from './catalog'
import { About, Contact, Privacy, Security, Terms } from './company'
import { DemoPage } from './demo'
import { Home, PricingPage } from './marketing'
import { OrderTimeline } from './operations'
import { getMetadata, siteOrigin } from './metadata'
import { loadRazorpay, type PaymentReceipt } from './payment'

const q = { addresses: ['addresses'], orders: ['orders'], profile: ['profile'] }
const field = (label: string, name: string, type = 'text', required = true, value?: string | number) => <label className="field"><span>{label}</span><input name={name} type={type} defaultValue={value} required={required} /></label>
const clean = (form: HTMLFormElement) => Object.fromEntries(new FormData(form).entries())

export function App() {
  return <>
    <PageEffects />
    <Header />
    <main id="main-content" tabIndex={-1}>
      <Routes>
        <Route path="/" element={<Home catalog={<HomeCatalog />} />} />
        <Route path="/demo" element={<DemoPage />} />
        <Route path="/shop" element={<Shop />} />
        <Route path="/pricing" element={<PricingPage />} />
        <Route path="/product/:id" element={<ProductPage />} />
        <Route path="/about" element={<About />} />
        <Route path="/privacy" element={<Privacy />} />
        <Route path="/terms" element={<Terms />} />
        <Route path="/security" element={<Security />} />
        <Route path="/contact" element={<Contact />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/forgot-password" element={<Forgot />} />
        <Route path="/reset-password" element={<Reset />} />
        <Route path="/verify" element={<Verify />} />
        <Route path="/check-email" element={<CheckEmail />} />
        <Route element={<RequireAuth />}>
          <Route path="/checkout" element={<Checkout />} />
          <Route path="/orders" element={<Orders />} />
          <Route path="/orders/:id" element={<OrderDetail />} />
          <Route path="/orders/:id/track" element={<TrackOrder />} />
          <Route path="/account" element={<Account />} />
          <Route path="/addresses" element={<Addresses />} />
        </Route>
        <Route element={<RequireAdmin />}>
          <Route path="/admin" element={<AdminHome />} />
          <Route path="/admin/products" element={<AdminProducts />} />
          <Route path="/admin/orders" element={<AdminOrders />} />
          <Route path="/admin/coupons" element={<Coupons />} />
          <Route path="/admin/inventory" element={<Inventory />} />
        </Route>
        <Route path="*" element={<NotFound />} />
      </Routes>
    </main>
    <Footer /><CartDrawer /><Toasts />
  </>
}

function PageEffects() {
  const { pathname, hash } = useLocation()
  useEffect(() => {
    const { refresh, user } = authStore.getState()
    if (!refresh || user) return
    let active = true
    endpoints.me().then((restored) => {
      const current = authStore.getState()
      if (active && current.refresh && !current.user) authStore.setState({ user: restored })
    }).catch(() => {
      const current = authStore.getState()
      if (active && current.refresh && !current.user) current.clear()
    })
    return () => { active = false }
  }, [])
  useEffect(() => {
    const { title, description, index } = getMetadata(pathname)
    document.title = title
    document.querySelector('meta[name="description"]')?.setAttribute('content', description)
    document.querySelector('meta[property="og:title"]')?.setAttribute('content', title)
    document.querySelector('meta[property="og:description"]')?.setAttribute('content', description)
    document.querySelector('meta[property="og:url"]')?.setAttribute('content', new URL(pathname, siteOrigin).href)
    document.querySelector('meta[name="robots"]')?.setAttribute('content', index ? 'index,follow' : 'noindex,follow')
    document.querySelector('link[rel="canonical"]')?.setAttribute('href', new URL(pathname, siteOrigin).href)
  }, [pathname])
  useEffect(() => {
    const target = hash && document.getElementById(hash.slice(1))
    if (target) target.scrollIntoView()
    else window.scrollTo(0, 0)
  }, [pathname, hash])
  return null
}

function AuthShell({ title, note, children }: { title: string; note: string; children: React.ReactNode }) { return <section className="auth"><div className="auth-aside"><Link className="brand" to="/"><span>α</span> ALPHA<span className="dim">/COMMERCE</span></Link><div><code>IDENTITY SERVICE / v1</code><h2>Access the system behind the storefront.</h2><p>Authentication is handled by short-lived access tokens and refresh rotation.</p></div><small>SECURE SESSION · JWT BEARER</small></div><div className="auth-form"><span className="eyebrow">ACCOUNT ACCESS</span><h1>{title}</h1><p>{note}</p>{children}</div></section> }
function Login() { const nav = useNavigate(), location = useLocation(), toast = authStore((s) => s.toast); const submit = useMutation({ mutationFn: (data: any) => api.post('/auth/login', new URLSearchParams({ username: data.username, password: data.password }), { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }), onSuccess: async ({ data }) => { try { authStore.setState({ access: data.access_token, refresh: data.refresh_token }); localStorage.setItem('refresh_token', data.refresh_token); const user = await endpoints.me(); authStore.getState().setSession(user, data); const returnTo: unknown = location.state?.returnTo; nav(typeof returnTo === 'string' && /^\/(?![/\\])/.test(returnTo) ? returnTo : user.is_admin ? '/admin' : '/shop', { replace: true }) } catch (e) { authStore.getState().clear(); toast(message(e), 'error') } }, onError: (e) => toast(message(e), 'error') }); return <AuthShell title="Sign in." note="Your shopping session and admin access share one identity."><form onSubmit={(e) => { e.preventDefault(); submit.mutate(clean(e.currentTarget)) }}><>{field('Email or username', 'username')}{field('Password', 'password', 'password')}</><button className="primary full">{submit.isPending ? 'Checking credentials…' : 'Sign in'} <ArrowRight size={17} /></button></form><div className="auth-links"><Link to="/forgot-password">Forgot password?</Link><span>New here? <Link to="/register">Create an account</Link></span></div></AuthShell> }
function Register() {
  const navigate = useNavigate(), toast = authStore((state) => state.toast)
  const register = useMutation({
    mutationFn: (values: Record<string, FormDataEntryValue>) => api.post('/auth/register', values),
    onSuccess: (_, values) => navigate(`/check-email?email=${encodeURIComponent(String(values.email))}`),
    onError: (error) => toast(message(error), 'error'),
  })
  return <AuthShell title="Create an account." note="We’ll send a verification link before your session can be activated.">
    <form onSubmit={(event) => {
      event.preventDefault()
      const values = clean(event.currentTarget)
      for (const name of ['full_name', 'phone_number']) {
        if (!String(values[name]).trim()) delete values[name]
      }
      register.mutate(values)
    }} className="two-col">
      {field('Full name', 'full_name', 'text', false)}{field('Phone number', 'phone_number', 'tel', false)}
      <label className="field"><span>Email</span><input type="email" name="email" autoComplete="email" required /></label>
      <label className="field"><span>Username</span><input name="username" autoComplete="username" required pattern="[A-Za-z0-9_]{3,50}" title="Use 3–50 letters, numbers, or underscores." /></label>
      <label className="field full"><span>Password</span><input name="password" type="password" autoComplete="new-password" required minLength={8} maxLength={50}
        pattern="(?=.*[A-Z])(?=.*[a-z])(?=.*[0-9])(?=.*[@$!%*?&]).{8,50}" aria-describedby="register-password-help" />
        <small id="register-password-help">Use 8–50 characters with an uppercase letter, a lowercase letter, a number, and one of @$!%*?&amp;.</small></label>
      <button className="primary full" disabled={register.isPending}>{register.isPending ? 'Creating account…' : 'Create & verify'} <ArrowRight size={17} /></button>
    </form>
    <div className="auth-links"><span>Already registered? <Link to="/login">Sign in</Link></span></div>
  </AuthShell>
}
function CheckEmail() { const [params] = useSearchParams(), toast = authStore((s) => s.toast); const resend = useMutation({ mutationFn: () => api.post('/auth/resend-verification', undefined, { params: { email: params.get('email') } }), onSuccess: () => toast('Verification message sent.') }); return <AuthShell title="Check your inbox." note={`We sent a verification link to ${params.get('email') || 'your email address'}. Activate your account, then come back to sign in.`}><button className="button-secondary full" onClick={() => resend.mutate()}>Resend verification <RefreshCw size={16} /></button><div className="auth-links"><Link to="/login">Return to sign in</Link></div></AuthShell> }
function Forgot() { return <PasswordAction title="Reset your password." note="Tell us where to send the reset link." url="/auth/forgot-password" fields={[['Email', 'email', 'email']]} /> }
function Reset() { const [params] = useSearchParams(); return <PasswordAction title="Set a new password." note="Choose a strong password to secure your account." url="/auth/reset-password" fields={[["Email", "email", "email"], ['New password', 'new_password', 'password']]} extra={{ token: params.get('token') || '' }} /> }
function PasswordAction({ title, note, url, fields, extra = {} }: any) { const nav = useNavigate(), toast = authStore((s) => s.toast); const mutation = useMutation({ mutationFn: (d: any) => api.post(url, d), onSuccess: () => { toast('Request completed.'); nav('/login') }, onError: (e) => toast(message(e), 'error') }); return <AuthShell title={title} note={note}><form onSubmit={(e) => { e.preventDefault(); mutation.mutate({ ...clean(e.currentTarget), ...extra }) }}>{fields.map(([l, n, t]: string[]) => field(l, n, t))}<button className="primary full">Continue <ArrowRight size={17} /></button></form></AuthShell> }
function Verify() { const [params] = useSearchParams(), toast = authStore((s) => s.toast); const query = useQuery({ queryKey: ['verify', params.get('token')], queryFn: () => api.get('/auth/verify', { params: { token: params.get('token') } }), retry: false }); useEffect(() => { if (query.isSuccess) toast('Email verified. You can sign in now.') }, [query.isSuccess]); return <AuthShell title={query.isSuccess ? 'Email verified.' : 'Verifying email…'} note={query.isError ? message(query.error) : 'Your account activation is being confirmed by the identity service.'}><Link className="primary full" to="/login">Continue to sign in <ArrowRight size={17} /></Link></AuthShell> }

function RequireAuth() {
  const user = authStore((state) => state.user), refresh = authStore((state) => state.refresh)
  const { pathname } = useLocation()
  if (user) return <Outlet />
  if (refresh) return <section className="page" aria-label="Restoring your session"><Skeleton rows={3} /></section>
  return <Navigate to="/login" replace state={{ returnTo: pathname }} />
}

function RequireAdmin() {
  const user = authStore((state) => state.user), refresh = authStore((state) => state.refresh)
  if (user?.is_admin) return <Outlet />
  if (!user && refresh) return <section className="page" aria-label="Restoring your session"><Skeleton rows={3} /></section>
  return <Navigate to="/" replace />
}

function Checkout() {
  const { data: addresses, isLoading } = useQuery({ queryKey: q.addresses, queryFn: endpoints.addresses })
  const [selected, setSelected] = useState('')
  const toast = authStore((state) => state.toast), navigate = useNavigate(), qc = useQueryClient()
  const verify = useMutation({
    mutationFn: (receipt: PaymentReceipt) => api.post('/api/v1/orders/verify-payment', receipt),
    onSuccess: ({ data }) => { toast('Payment verified. Order recorded.'); navigate(`/orders/${data.id || data.order_id}`) },
    onError: (error) => toast(message(error), 'error'),
  })
  const checkout = useMutation({
    mutationFn: async () => {
      const Razorpay = await loadRazorpay()
      const { data } = await api.post('/api/v1/orders/checkout', { address_id: selected })
      return { Razorpay, payment: data.payment_details }
    },
    onSuccess: ({ Razorpay, payment }) => {
      qc.invalidateQueries({ queryKey: ['cart'] })
      new Razorpay({
        key: payment.key || import.meta.env.VITE_RAZORPAY_KEY_ID, order_id: payment.razorpay_order_id,
        amount: payment.amount, currency: payment.currency || 'INR', name: 'Alpha-Commerce',
        handler: (receipt) => verify.mutate(receipt),
      }).open()
    },
    onError: (error) => toast(error instanceof Error && error.message === 'Payment checkout could not load.' ? error.message : message(error), 'error'),
  })
  return <section className="page checkout">
    <Link className="back" to="/shop"><ArrowLeft size={16} /> Keep shopping</Link>
    <div className="page-heading"><div><span className="eyebrow">CHECKOUT / RAZORPAY</span><h1>Choose a delivery address.</h1></div></div>
    {isLoading ? <Skeleton rows={3} /> : <>
      <div className="address-list">{(addresses || []).map((address) => <button type="button" className={`address-card${selected === address.id ? ' selected' : ''}`} aria-pressed={selected === address.id} onClick={() => setSelected(address.id)} key={address.id}>
        <MapPin size={19} /><b>{address.full_name}{address.is_default && <small> DEFAULT</small>}</b><span>{address.house_no}, {address.area}, {address.city}, {address.state} — {address.pincode}</span><span>{address.phone_number}</span>
      </button>)}<Link className="add-address" to="/addresses"><Plus /> Add a delivery address</Link></div>
      <div className="checkout-action"><p>Apply any coupon in your cart before continuing.</p><button className="primary" disabled={!selected || checkout.isPending || verify.isPending} onClick={() => checkout.mutate()}><CreditCard size={17} /> {verify.isPending ? 'Verifying payment…' : checkout.isPending ? 'Preparing checkout…' : 'Continue to payment'}</button></div>
    </>}
  </section>
}
function Orders() { const { data, isLoading, isError } = useQuery({ queryKey: q.orders, queryFn: endpoints.orders }); return <section className="page"><div className="page-heading"><div><span className="eyebrow">ORDER HISTORY</span><h1>Everything you’ve<br />set in motion.</h1></div></div>{isLoading ? <Skeleton rows={5} /> : isError ? <ApiError /> : !data?.length ? <Empty title="No orders yet." text="Your first order will show up here the moment you check out." to="/shop" label="Browse the catalog" /> : <div className="data-table order-table"><div className="table-head"><span>ORDER ID</span><span>CREATED</span><span>STATUS</span><span>TOTAL</span><span /></div>{data.map((o) => <div className="table-row" key={o.id}><code>{o.id.slice(0, 8)}…</code><span>{date(o.created_at)}</span><Status value={o.status} /><code>{money(o.total_price)}</code><Link to={`/orders/${o.id}`}>Open <ArrowRight size={14} /></Link></div>)}</div>}</section> }
function OrderDetail() { const { id = '' } = useParams(), qc = useQueryClient(), toast = authStore((s) => s.toast); const { data: order, isLoading } = useQuery({ queryKey: ['order', id], queryFn: () => endpoints.order(id) }); const cancel = useMutation({ mutationFn: () => api.patch(`/api/v1/orders/${id}/cancel`), onSuccess: () => { qc.invalidateQueries({ queryKey: ['order', id] }); qc.invalidateQueries({ queryKey: q.orders }); toast('Cancellation request processed.') }, onError: (e) => toast(message(e), 'error') }); if (isLoading) return <section className="page"><Skeleton /></section>; if (!order) return <NotFound />; return <section className="page"><Link className="back" to="/orders"><ArrowLeft size={16} /> Order history</Link><div className="order-header"><div><span className="eyebrow">ORDER RECEIPT</span><h1><code>{order.id.slice(0, 13)}…</code></h1><p>Created {date(order.created_at)}</p></div><Status value={order.status} /></div><div className="receipt-grid"><div className="receipt"><h3>Items in this order</h3>{order.items.map((i) => <div className="receipt-item" key={i.product_id}><span><b>{i.product_name}</b><small>{i.quantity} × {money(i.price_at_purchase)}</small></span><code>{money(i.price_at_purchase * i.quantity)}</code></div>)}<strong>Total paid <code>{money(order.total_price)}</code></strong></div><aside className="order-actions"><Link className="primary full" to={`/orders/${id}/track`}><Activity size={17} /> Track live status</Link>{['pending', 'paid', 'processing'].includes(order.status.toLowerCase()) && <button className="button-secondary full danger" onClick={() => cancel.mutate()}><XCircle size={17} /> Cancel order</button>}<p>Order events are delivered to this page via a token-authenticated connection.</p></aside></div></section> }
function TrackOrder() {
  const { id = '' } = useParams()
  return <OrderTracking key={id} id={id} />
}

function OrderTracking({ id }: { id: string }) {
  const token = authStore((state) => state.access), toast = authStore((state) => state.toast)
  const order = useQuery({ queryKey: ['order', id], queryFn: () => endpoints.order(id) })
  const [status, setStatus] = useState<string>()
  const [connected, setConnected] = useState(false)
  const hasOrder = !!order.data
  useEffect(() => {
    if (!token || !hasOrder) return
    const defaultBase = (api.defaults.baseURL || 'http://localhost:8000').replace(/^http/, 'ws')
    const base = (import.meta.env.VITE_WS_BASE_URL || defaultBase).replace(/\/$/, '')
    const socket = new WebSocket(`${base}/api/v1/ws/orders/${id}?token=${encodeURIComponent(token)}`)
    const ping = () => { if (socket.readyState === WebSocket.OPEN) socket.send('ping') }
    socket.onopen = ping
    socket.onclose = () => setConnected(false)
    socket.onerror = () => setConnected(false)
    socket.onmessage = (event) => {
      try {
        const update = JSON.parse(event.data)
        if (update.type === 'pong') { setConnected(true); return }
        const next = update.status || update.new_status
        if (typeof next === 'string') { setStatus(next); toast(`Order status changed to ${next}.`) }
      } catch { /* Ignore malformed WebSocket messages. */ }
    }
    const heartbeat = setInterval(ping, 25_000)
    return () => { clearInterval(heartbeat); socket.onclose = null; socket.onerror = null; socket.onmessage = null; socket.close() }
  }, [id, token, hasOrder, toast])
  return <section className="page tracking">
    <Link className="back" to={`/orders/${id}`}><ArrowLeft size={16} /> Order receipt</Link>
    <span className="eyebrow"><Activity size={14} /> ORDER TRACKING</span><h1>Track your order.</h1>
    {order.isLoading ? <Skeleton rows={4} /> : order.data ? <>
      <p className="tracking-id">ORDER / {id}</p>
      <div className="socket-state" role="status"><span className={`dot${connected ? ' good' : ''}`} />{connected ? 'Live updates connected' : 'Showing the last known order status'}</div>
      <OrderTimeline status={status || order.data.status} live={connected} />
    </> : <ApiError />}
  </section>
}

function Account() { const user = authStore((s) => s.user); const qc = useQueryClient(), toast = authStore((s) => s.toast); const edit = useMutation({ mutationFn: (d: any) => api.patch('/api/v1/users/me', d), onSuccess: ({ data }) => { authStore.setState({ user: data }); qc.invalidateQueries({ queryKey: q.profile }); toast('Profile saved.') }, onError: (e) => toast(message(e), 'error') }); if (!user) return null; return <section className="page account"><div className="page-heading"><div><span className="eyebrow">ACCOUNT / IDENTITY</span><h1>Profile settings.</h1></div><Link className="button-secondary" to="/addresses"><MapPin size={16} /> Address book</Link></div><form className="profile-form" onSubmit={(e) => { e.preventDefault(); edit.mutate(clean(e.currentTarget)) }}><div className="profile-avatar">{user.username.slice(0, 1).toUpperCase()}</div><div><code>ACCOUNT ID / {user.id}</code><h2>{user.full_name || user.username}</h2><p>{user.is_admin ? 'Administrator access enabled' : 'Customer account'}</p></div><div className="form-grid">{field('Full name', 'full_name', 'text', false, user.full_name)}{field('Email', 'email', 'email', false, user.email)}{field('Phone number', 'phone_number', 'tel', false, user.phone_number)}<button className="primary">Save profile <FilePenLine size={16} /></button></div></form></section> }
function Addresses() { const list = useQuery({ queryKey: q.addresses, queryFn: endpoints.addresses }); const [edit, setEdit] = useState<any>(); return <section className="page"><div className="page-heading"><div><span className="eyebrow">ADDRESS BOOK</span><h1>Delivery locations.</h1></div><button className="primary" onClick={() => setEdit({})}><Plus size={16} /> Add address</button></div>{list.isLoading ? <Skeleton rows={4} /> : <div className="addresses">{list.data?.map((a) => <AddressCard key={a.id} address={a} edit={() => setEdit(a)} />)}{!list.data?.length && <Empty title="No delivery locations." text="Add an address before you proceed to secure checkout." />}</div>}{edit && <AddressForm address={edit} close={() => setEdit(undefined)} />}</section> }
function AddressCard({ address, edit }: any) { const qc = useQueryClient(), toast = authStore((s) => s.toast); const action = useMutation({ mutationFn: (mode: string) => mode === 'default' ? api.patch(`/api/v1/addresses/${address.id}/default`) : api.delete(`/api/v1/addresses/${address.id}`), onSuccess: () => { qc.invalidateQueries({ queryKey: q.addresses }); toast('Address book updated.') }, onError: (e) => toast(message(e), 'error') }); return <article className="address-entry"><MapPin /><div><b>{address.full_name} {address.is_default && <small>DEFAULT</small>}</b><p>{address.house_no}, {address.area}, {address.city}, {address.state} — {address.pincode}<br />{address.phone_number}</p></div><div><button className="text-btn" onClick={edit}>Edit</button>{!address.is_default && <button className="text-btn" onClick={() => action.mutate('default')}>Set default</button>}<button className="text-btn danger" onClick={() => action.mutate('delete')}>Delete</button></div></article> }
function AddressForm({ address, close }: any) { const qc = useQueryClient(), toast = authStore((s) => s.toast); const mutation = useMutation({ mutationFn: (d: any) => address.id ? api.patch(`/api/v1/addresses/${address.id}`, d) : api.post('/api/v1/addresses/', d), onSuccess: () => { qc.invalidateQueries({ queryKey: q.addresses }); toast('Address saved.'); close() }, onError: (e) => toast(message(e), 'error') }); return <div className="modal-layer"><form className="modal-form wide" onSubmit={(e) => { e.preventDefault(); mutation.mutate(clean(e.currentTarget)) }}><button className="modal-close" type="button" onClick={close}>×</button><span className="eyebrow">DELIVERY DETAILS</span><h2>{address.id ? 'Edit address' : 'New address'}</h2><div className="two-col">{field('Full name', 'full_name', 'text', true, address.full_name)}{field('Phone number', 'phone_number', 'tel', true, address.phone_number)}{field('House / flat no.', 'house_no', 'text', true, address.house_no)}{field('Area / locality', 'area', 'text', true, address.area)}{field('City', 'city', 'text', true, address.city)}{field('State', 'state', 'text', true, address.state)}{field('Pincode', 'pincode', 'text', true, address.pincode)}<label className="field"><span>Address type</span><select name="address_type" defaultValue={address.address_type || 'home'}><option value="home">Home</option><option value="office">Office</option><option value="other">Other</option></select></label></div><button className="primary full">Save address</button></form></div> }
function Empty({ title, text, to, label }: { title: string; text: string; to?: string; label?: string }) { return <div className="empty"><Package size={26} /><h3>{title}</h3><p>{text}</p>{to && <Link className="primary" to={to}>{label} <ArrowRight size={15} /></Link>}</div> }
function ApiError() { return <div className="empty"><RotateCcw size={26} /><h3>The API is not reachable.</h3><p>Check VITE_API_BASE_URL, then retry the request. The interface never substitutes fake catalog data.</p></div> }
function NotFound() { return <section className="page"><Empty title="This route has no record." text="The page you requested doesn’t exist in the Alpha-Commerce interface." to="/" label="Return home" /></section> }
