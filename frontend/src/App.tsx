import { useEffect, useState } from 'react'
import { Link, Navigate, Outlet, Route, Routes, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { motion, useReducedMotion } from 'framer-motion'
import { Activity, ArrowLeft, ArrowRight, Check, CheckCircle2, ChevronRight, CreditCard, FilePenLine, FolderTree, HelpCircle, Layers, MapPin, Package, Plus, RefreshCw, RotateCcw, Search, Server, Shield, ShoppingCart, SlidersHorizontal, Sparkles, XCircle, Zap } from 'lucide-react'
import { api, authStore, date, endpoints, message, money, type Category, type Product } from './lib'
import { CartDrawer, Footer, Header, Skeleton, Status, Toasts } from './components'
import { AdminHome, AdminOrders, AdminProducts, Coupons, Inventory } from './admin'

const q = { products: ['products'], categories: ['categories'], addresses: ['addresses'], orders: ['orders'], profile: ['profile'], adminProducts: ['admin-products'], adminOrders: ['admin-orders'], coupons: ['coupons'], inventory: ['inventory'], lowStock: ['low-stock'] }
const field = (label: string, name: string, type = 'text', required = true, value?: string | number) => <label className="field"><span>{label}</span><input name={name} type={type} defaultValue={value} required={required} /></label>
const clean = (form: HTMLFormElement) => Object.fromEntries(new FormData(form).entries())

export function App() { return <><Header /><main><Routes><Route path="/" element={<Home />} /><Route path="/shop" element={<Shop />} /><Route path="/pricing" element={<PricingPage />} /><Route path="/product/:id" element={<ProductPage />} /><Route path="/privacy" element={<Privacy />} /><Route path="/terms" element={<Terms />} /><Route path="/contact" element={<Contact />} /><Route path="/login" element={<Login />} /><Route path="/register" element={<Register />} /><Route path="/forgot-password" element={<Forgot />} /><Route path="/reset-password" element={<Reset />} /><Route path="/verify" element={<Verify />} /><Route path="/check-email" element={<CheckEmail />} /><Route element={<RequireAuth />}><Route path="/checkout" element={<Checkout />} /><Route path="/orders" element={<Orders />} /><Route path="/orders/:id" element={<OrderDetail />} /><Route path="/orders/:id/track" element={<TrackOrder />} /><Route path="/account" element={<Account />} /><Route path="/addresses" element={<Addresses />} /></Route><Route element={<RequireAdmin />}><Route path="/admin" element={<AdminHome />} /><Route path="/admin/products" element={<AdminProducts />} /><Route path="/admin/orders" element={<AdminOrders />} /><Route path="/admin/coupons" element={<Coupons />} /><Route path="/admin/inventory" element={<Inventory />} /></Route><Route path="*" element={<NotFound />} /></Routes></main><Footer /><CartDrawer /><Toasts /></> }

const featuredProductNames = ['Zenith Earbuds Premium', 'Nexus Monitor Ultra', 'Nexus Keyboard Classic', 'Quantum Mouse Plus']
function Home() {
  const { data: products, isLoading } = useQuery({ queryKey: q.products, queryFn: endpoints.products });
  const { data: categories } = useQuery({ queryKey: q.categories, queryFn: endpoints.categories });
  const featuredProducts = [...(products || [])].sort((a, b) => {
    const aIndex = featuredProductNames.indexOf(a.name), bIndex = featuredProductNames.indexOf(b.name);
    return (aIndex === -1 ? featuredProductNames.length : aIndex) - (bIndex === -1 ? featuredProductNames.length : bIndex)
  });

  return <>
    <section className="hero">
      <div className="eyebrow"><Activity size={14} /> ASYNC COMMERCE, OBSERVABLE</div>
      <h1>The store is only<br /><em>the interface.</em></h1>
      <p>Alpha-Commerce is an enterprise-grade async commerce engine: real-time inventory synchronization, distributed order pipeline, secure payment verification, and an immutable stock ledger built for modern scale.</p>
      <div className="hero-actions">
        <Link className="primary" to="/shop">Browse catalog <ArrowRight size={17} /></Link>
        <Link className="outline" to="/pricing">Commercial plans <ChevronRight size={17} /></Link>
      </div>
      <div className="system-strip">
        <span><b>JWT</b> AUTH</span>
        <span><b>WS</b> TRACKING</span>
        <span><b>RQ</b> QUEUED</span>
        <span><b>₹</b> PAYMENTS</span>
      </div>
    </section>

    <section className="trusted-by">
      <span className="eyebrow">TRUSTED COMMERCE INFRASTRUCTURE</span>
      <p>Powering fast-growing digital brands &amp; modern retail merchants</p>
      <div className="brand-logos">
        <span>ZENITH AUDIO</span>
        <span>NEXUS TECH</span>
        <span>HORIZON LABS</span>
        <span>APEX APPAREL</span>
        <span>QUANTUM GEAR</span>
      </div>
    </section>

    <section className="features-section">
      <div className="features-header">
        <span className="eyebrow">HIGH-PERFORMANCE ARCHITECTURE</span>
        <h2>Engineered for Zero Data Race &amp; Sub-millisecond Events</h2>
        <p>Traditional e-commerce platforms struggle with flash-sale race conditions and slow batch reconciliation. Alpha-Commerce re-engineers every layer from database locking to push notifications.</p>
      </div>
      <div className="features-grid">
        <div className="feature-card">
          <div className="feature-icon"><Shield size={24} /></div>
          <h3>Zero-Oversell Stock Ledger</h3>
          <p>Strict distributed row-level locking ensures that two simultaneous checkouts never claim the same physical inventory unit, preserving auditability.</p>
        </div>
        <div className="feature-card">
          <div className="feature-icon"><Zap size={24} /></div>
          <h3>Authenticated WebSocket Stream</h3>
          <p>Real-time order state events, package tracking, and payment receipts push directly to customer browsers without poll fatigue or stale cache.</p>
        </div>
        <div className="feature-card">
          <div className="feature-icon"><Layers size={24} /></div>
          <h3>Multi-Gateway Reconciliation</h3>
          <p>Asynchronous webhook pipelines verify signatures, handle refunds, and settle orders with Razorpay, UPI, and major payment rails seamlessly.</p>
        </div>
      </div>
    </section>

    <section className="home-section">
      <div className="section-title">
        <div><span className="eyebrow">COLLECTION INDEX</span><h2>In stock, in sync.</h2></div>
        <Link to="/shop">Open catalog <ArrowRight size={16} /></Link>
      </div>
      <CategoryRail categories={categories || []} />
      {isLoading ? <Skeleton rows={4} /> : <ProductGrid products={featuredProducts} />}
    </section>

    <PricingSection isPreview={true} />
    <FAQSection />
    <CtaBanner />
  </>
}

function CategoryRail({ categories }: { categories: Category[] }) { return <div className="category-rail">{categories.map((c) => <Link to={`/shop?category=${c.id}`} key={c.id}><FolderTree size={19} /><span>{c.name}</span><small>{c.sub_categories?.length || 0} groups</small></Link>)}</div> }
function ProductGrid({ products }: { products: Product[] }) { return <div className="product-grid">{products.map((p, i) => <article className="product-card" key={p.id}><div className={`product-art art-${i % 4}`}><span>{p.name.slice(0, 1)}</span><small>{p.stock_quantity} units available</small></div><div className="product-info"><code>SKU / {p.slug}</code><h3>{p.name}</h3><p>{p.description || 'Product details available in the catalog.'}</p><div><strong>{money(p.price)}</strong><Link to={`/product/${p.id}`}>View <ArrowRight size={15} /></Link></div></div></article>)}</div> }

function PricingSection({ isPreview = false }: { isPreview?: boolean }) {
  return <section className="pricing-section">
    <div className="pricing-header">
      <span className="eyebrow">COMMERCIAL TIERS</span>
      <h2>Transparent, Scale-Ready Pricing</h2>
      <p>Whether you're launching your first digital brand or processing millions in monthly gross merchandise volume.</p>
    </div>
    <div className="pricing-grid">
      <div className="pricing-card">
        <div className="card-head">
          <h3>Starter</h3>
          <p className="card-desc">For emerging merchants launching their online catalog.</p>
          <div className="price-row"><strong>₹0</strong><span>/ month + 1.5%</span></div>
        </div>
        <ul>
          <li><CheckCircle2 size={16} /> Unlimited products &amp; orders</li>
          <li><CheckCircle2 size={16} /> Standard webhook delivery</li>
          <li><CheckCircle2 size={16} /> Razorpay &amp; UPI gateway integration</li>
          <li><CheckCircle2 size={16} /> Community &amp; email support</li>
        </ul>
        <Link className="outline full" to="/register">Get started free</Link>
      </div>

      <div className="pricing-card featured">
        <span className="popular-badge">MOST POPULAR</span>
        <div className="card-head">
          <h3>Growth</h3>
          <p className="card-desc">For high-velocity DTC brands needing real-time sync.</p>
          <div className="price-row"><strong>₹2,499</strong><span>/ month + 0.5%</span></div>
        </div>
        <ul>
          <li><CheckCircle2 size={16} /> Everything in Starter</li>
          <li><CheckCircle2 size={16} /> Real-time WebSocket order channel</li>
          <li><CheckCircle2 size={16} /> Immutable inventory audit ledger</li>
          <li><CheckCircle2 size={16} /> Custom domain &amp; SSL included</li>
          <li><CheckCircle2 size={16} /> Priority 24/7 developer support</li>
        </ul>
        <Link className="primary full" to="/contact">Upgrade to Growth</Link>
      </div>

      <div className="pricing-card">
        <div className="card-head">
          <h3>Enterprise</h3>
          <p className="card-desc">For high-volume retail networks with dedicated SLA.</p>
          <div className="price-row"><strong>Custom</strong><span>volume pricing</span></div>
        </div>
        <ul>
          <li><CheckCircle2 size={16} /> Dedicated isolated database clusters</li>
          <li><CheckCircle2 size={16} /> 99.99% Uptime Service Level Agreement</li>
          <li><CheckCircle2 size={16} /> Multi-warehouse distributed routing</li>
          <li><CheckCircle2 size={16} /> Custom payment &amp; ERP integrations</li>
        </ul>
        <Link className="outline full" to="/contact">Talk to enterprise sales</Link>
      </div>
    </div>
  </section>
}

function PricingPage() {
  return <section className="page">
    <div className="page-heading">
      <div>
        <span className="eyebrow">COMMERCIAL INFRASTRUCTURE</span>
        <h1>Pricing built for<br />sustainable scale.</h1>
      </div>
      <Link className="primary" to="/contact">Contact sales <ArrowRight size={16} /></Link>
    </div>
    <PricingSection />
    <FAQSection />
    <CtaBanner />
  </section>
}

function FAQSection() {
  const faqs = [
    { q: 'How does the zero-oversell inventory ledger work?', a: 'Alpha-Commerce uses transactional row-level locks on PostgreSQL with Redis-backed queueing. During high-concurrency checkouts, inventory claims are serialized so stock counts never fall below zero.' },
    { q: 'What payment methods can my customers use?', a: 'We natively support Razorpay, UPI QR, major debit/credit cards, Netbanking, and digital wallets with automated asynchronous webhook verification.' },
    { q: 'Can I connect my own custom domain?', a: 'Yes. On all plans, you can map your custom domain (e.g., store.yourbrand.com) with automated TLS/SSL certificate provisioning.' },
    { q: 'Is there a contract or setup fee?', a: 'No setup fees or long-term contracts. You can upgrade, downgrade, or cancel your subscription at any time directly from the admin console.' },
  ];
  return <section className="faq-section">
    <div className="faq-header">
      <span className="eyebrow">FREQUENTLY ASKED QUESTIONS</span>
      <h2>Everything you need to know</h2>
      <p>Clear answers about our technology, pricing, and infrastructure capabilities.</p>
    </div>
    <div className="faq-grid">
      {faqs.map((f) => <article key={f.q} className="faq-card">
        <h3>{f.q}</h3>
        <p>{f.a}</p>
      </article>)}
    </div>
  </section>
}

function CtaBanner() {
  return <section className="cta-banner">
    <span className="eyebrow">GET STARTED TODAY</span>
    <h2>Ready to modernize your commerce engine?</h2>
    <p>Deploy a high-performance, real-time storefront backed by an immutable ledger in minutes.</p>
    <div className="cta-buttons">
      <Link className="primary" to="/shop">Browse live storefront <ArrowRight size={16} /></Link>
      <Link className="outline" to="/contact">Talk to sales <ChevronRight size={16} /></Link>
    </div>
  </section>
}

function Shop() { const [params, setParams] = useSearchParams(); const categoryId = params.get('category') || ''; const [search, setSearch] = useState(''); const [debounced, setDebounced] = useState(''); useEffect(() => { const t = setTimeout(() => setDebounced(search.trim()), 300); return () => clearTimeout(t) }, [search]); const { data: categories } = useQuery({ queryKey: q.categories, queryFn: endpoints.categories }); const searching = debounced.length > 0; const { data, isLoading, isError } = useQuery({ queryKey: searching ? ['product-search', debounced] : q.products, queryFn: () => searching ? endpoints.searchProducts(debounced) : endpoints.products() }); const activeCategory = categories?.find((c) => c.id === categoryId); const found = (data || []).filter((p) => !categoryId || p.category_id === categoryId); return <section className="page"><div className="page-heading"><div><span className="eyebrow">CATALOG / LIVE API</span><h1>Find your next<br />useful thing.</h1></div><div className="search"><Search size={18} /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search products" /></div></div>{categories && categories.length > 0 && <div className="category-rail"><button className={!categoryId ? 'active' : ''} onClick={() => setParams({})}>All</button>{categories.map((c) => <button key={c.id} className={categoryId === c.id ? 'active' : ''} onClick={() => setParams({ category: c.id })}>{c.name}</button>)}</div>}<div className="catalog-toolbar"><span>{found.length} products {searching ? `matched "${debounced}"` : 'returned'}{activeCategory ? ` in ${activeCategory.name}` : ''}</span><button><SlidersHorizontal size={16} /> {searching ? 'Full-text ranked' : 'Filtered at source'}</button></div>{isLoading ? <Skeleton rows={8} /> : isError ? <ApiError /> : found.length === 0 ? <Empty title="No matches." text="Try a different search term or category." to="/shop" label="Reset" /> : <ProductGrid products={found} />}</section> }
function ProductPage() { const { id = '' } = useParams(); const { data: p, isLoading } = useQuery({ queryKey: ['product', id], queryFn: () => endpoints.product(id) }); const qc = useQueryClient(), toast = authStore((s) => s.toast); const add = useMutation({ mutationFn: () => api.post('/api/v1/cart/items', { product_id: id, quantity: 1 }), onSuccess: () => { qc.invalidateQueries({ queryKey: ['cart'] }); toast('Added to cart.'); authStore.getState().toggleCart() }, onError: (e) => toast(message(e), 'error') }); if (isLoading) return <section className="page"><Skeleton rows={6} /></section>; if (!p) return <NotFound />; return <section className="page"><Link className="back" to="/shop"><ArrowLeft size={16} /> Catalog</Link><div className="product-detail"><div className="product-visual"><span>{p.name.slice(0, 1)}</span><code>INVENTORY / {p.stock_quantity} UNITS</code></div><div><span className="eyebrow">PRODUCT / {p.slug}</span><h1>{p.name}</h1><strong className="price">{money(p.price)}</strong><p>{p.description || 'No product description was supplied.'}</p><div className="stock-line"><span className={p.stock_quantity ? 'dot good' : 'dot bad'} />{p.stock_quantity ? `${p.stock_quantity} units currently available` : 'Out of stock'}</div><button className="primary" disabled={!p.stock_quantity || add.isPending} onClick={() => add.mutate()}><ShoppingCart size={17} /> Add to cart</button><dl className="specs">{Object.entries(p.attributes || {}).map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{String(v)}</dd></div>)}</dl></div></div></section> }

function LegalPage({ eyebrow, title, intro, sections }: { eyebrow: string; title: string; intro: string; sections: { title: string; text: string }[] }) { return <section className="page legal-page"><div className="legal-heading"><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{intro}</p><small>Last updated: August 14, 2026</small></div><div className="legal-sections">{sections.map((section) => <article key={section.title}><h2>{section.title}</h2><p>{section.text}</p></article>)}</div></section> }
function Privacy() { return <LegalPage eyebrow="LEGAL / PRIVACY" title="Privacy policy." intro="This policy explains how Alpha-Commerce handles information when you use our platform and related services." sections={[{ title: 'Data collection', text: 'We collect account, order, payment-verification, device, and support information needed to operate the service, complete transactions, prevent fraud, and meet applicable legal obligations. We do not sell personal information.' }, { title: 'Cookie policy', text: 'We use essential cookies and local storage to maintain secure sessions, remember service preferences, and protect the platform. Where analytics or optional cookies are introduced, we will provide the appropriate notice and controls.' }, { title: 'Security measures', text: 'We use access controls, encryption in transit, audit logging, and operational safeguards designed to protect personal information. No online system is completely risk-free; please notify us promptly if you suspect unauthorized account activity.' }]} /> }
function Terms() { return <LegalPage eyebrow="LEGAL / TERMS" title="Terms of service." intro="These terms govern your access to Alpha-Commerce and the services made available through this platform." sections={[{ title: 'Use of service', text: 'You may use Alpha-Commerce only in compliance with applicable law and these terms. You must not interfere with platform security, misuse APIs, attempt unauthorized access, or use the service for fraudulent activity.' }, { title: 'User accounts', text: 'You are responsible for maintaining accurate account information and safeguarding your credentials. You must promptly notify us of unauthorized use. We may suspend access where necessary to protect customers, merchants, or the platform.' }, { title: 'Merchant agreements', text: 'Merchants are responsible for the accuracy, availability, fulfillment, and legal compliance of their catalog and commercial activity. Additional merchant terms, payment-provider rules, and applicable tax obligations may apply.' }]} /> }
function Contact() { return <section className="page contact-page"><div className="legal-heading"><span className="eyebrow">SUPPORT / CONTACT</span><h1>Talk to our team.</h1><p>For platform, account, security, or commercial questions, reach the Alpha-Commerce support desk.</p></div><div className="contact-grid"><article className="contact-card"><code>OFFICIAL SUPPORT</code><a href="mailto:connect@alpha-commerce.tech">connect@alpha-commerce.tech</a><p>We respond to operational and account requests during business hours.</p><dl><div><dt>Hours</dt><dd>Monday–Friday, 09:00–18:00 IST</dd></div><div><dt>Coverage</dt><dd>Platform, merchant, and security support</dd></div></dl></article><form className="contact-form" action="mailto:connect@alpha-commerce.tech" method="post" encType="text/plain"><label className="field"><span>Your email</span><input type="email" name="email" autoComplete="email" required /></label><label className="field"><span>Message</span><textarea name="message" placeholder="How can we help?" required /></label><button className="primary" type="submit">Open email draft <ArrowRight size={17} /></button></form></div></section> }

function AuthShell({ title, note, children }: { title: string; note: string; children: React.ReactNode }) { return <section className="auth"><div className="auth-aside"><Link className="brand" to="/"><span>α</span> ALPHA<span className="dim">/COMMERCE</span></Link><div><code>IDENTITY SERVICE / v1</code><h2>Access the system behind the storefront.</h2><p>Authentication is handled by short-lived access tokens and refresh rotation.</p></div><small>SECURE SESSION · JWT BEARER</small></div><div className="auth-form"><span className="eyebrow">ACCOUNT ACCESS</span><h1>{title}</h1><p>{note}</p>{children}</div></section> }
function Login() { const nav = useNavigate(), toast = authStore((s) => s.toast); const submit = useMutation({ mutationFn: (data: any) => api.post('/auth/login', new URLSearchParams({ username: data.username, password: data.password }), { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }), onSuccess: async ({ data }) => { try { authStore.setState({ access: data.access_token, refresh: data.refresh_token }); localStorage.setItem('refresh_token', data.refresh_token); const user = await endpoints.me(); authStore.getState().setSession(user, data); nav(user.is_admin ? '/admin' : '/shop') } catch (e) { authStore.getState().clear(); toast(message(e), 'error') } }, onError: (e) => toast(message(e), 'error') }); return <AuthShell title="Sign in." note="Your shopping session and admin access share one identity."><form onSubmit={(e) => { e.preventDefault(); submit.mutate(clean(e.currentTarget)) }}><>{field('Email or username', 'username')}{field('Password', 'password', 'password')}</><button className="primary full">{submit.isPending ? 'Checking credentials…' : 'Sign in'} <ArrowRight size={17} /></button></form><div className="auth-links"><Link to="/forgot-password">Forgot password?</Link><span>New here? <Link to="/register">Create an account</Link></span></div></AuthShell> }
function Register() { const nav = useNavigate(), toast = authStore((s) => s.toast); const reg = useMutation({ mutationFn: (d: any) => api.post('/auth/register', d), onSuccess: (_, d) => nav(`/check-email?email=${encodeURIComponent(d.email)}`), onError: (e) => toast(message(e), 'error') }); return <AuthShell title="Create an account." note="We’ll send a verification link before your session can be activated."><form onSubmit={(e) => { e.preventDefault(); reg.mutate(clean(e.currentTarget)) }} className="two-col">{field('Full name', 'full_name', 'text', false)}{field('Phone number', 'phone_number', 'tel', false)}{field('Email', 'email', 'email')}{field('Username', 'username')}{field('Password', 'password', 'password')}<button className="primary full">Create & verify <ArrowRight size={17} /></button></form><div className="auth-links"><span>Already registered? <Link to="/login">Sign in</Link></span></div></AuthShell> }
function CheckEmail() { const [params] = useSearchParams(), toast = authStore((s) => s.toast); const resend = useMutation({ mutationFn: () => api.post('/auth/resend-verification', undefined, { params: { email: params.get('email') } }), onSuccess: () => toast('Verification message sent.') }); return <AuthShell title="Check your inbox." note={`We sent a verification link to ${params.get('email') || 'your email address'}. Activate your account, then come back to sign in.`}><button className="outline full" onClick={() => resend.mutate()}>Resend verification <RefreshCw size={16} /></button><div className="auth-links"><Link to="/login">Return to sign in</Link></div></AuthShell> }
function Forgot() { return <PasswordAction title="Reset your password." note="Tell us where to send the reset link." url="/auth/forgot-password" fields={[['Email', 'email', 'email']]} /> }
function Reset() { const [params] = useSearchParams(); return <PasswordAction title="Set a new password." note="Choose a strong password to secure your account." url="/auth/reset-password" fields={[["Email", "email", "email"], ['New password', 'new_password', 'password']]} extra={{ token: params.get('token') || '' }} /> }
function PasswordAction({ title, note, url, fields, extra = {} }: any) { const nav = useNavigate(), toast = authStore((s) => s.toast); const mutation = useMutation({ mutationFn: (d: any) => api.post(url, d), onSuccess: () => { toast('Request completed.'); nav('/login') }, onError: (e) => toast(message(e), 'error') }); return <AuthShell title={title} note={note}><form onSubmit={(e) => { e.preventDefault(); mutation.mutate({ ...clean(e.currentTarget), ...extra }) }}>{fields.map(([l, n, t]: string[]) => field(l, n, t))}<button className="primary full">Continue <ArrowRight size={17} /></button></form></AuthShell> }
function Verify() { const [params] = useSearchParams(), toast = authStore((s) => s.toast); const query = useQuery({ queryKey: ['verify', params.get('token')], queryFn: () => api.get('/auth/verify', { params: { token: params.get('token') } }), retry: false }); useEffect(() => { if (query.isSuccess) toast('Email verified. You can sign in now.') }, [query.isSuccess]); return <AuthShell title={query.isSuccess ? 'Email verified.' : 'Verifying email…'} note={query.isError ? message(query.error) : 'Your account activation is being confirmed by the identity service.'}><Link className="primary full" to="/login">Continue to sign in <ArrowRight size={17} /></Link></AuthShell> }

function RequireAuth() { return authStore((s) => s.user) ? <Outlet /> : <Navigate to="/login" replace /> }
function RequireAdmin() { const u = authStore((s) => s.user); return u?.is_admin ? <Outlet /> : <Navigate to="/" replace /> }

function Checkout() { const { data: addresses, isLoading } = useQuery({ queryKey: q.addresses, queryFn: endpoints.addresses }); const [selected, setSelected] = useState(''); const [coupon, setCoupon] = useState(''); const toast = authStore((s) => s.toast); const checkout = useMutation({ mutationFn: () => api.post('/api/v1/orders/checkout', { address_id: selected, coupon_code: coupon || undefined }), onSuccess: ({ data }) => { const Razorpay = (window as any).Razorpay; const pd = data.payment_details || {}; if (!Razorpay) { toast('Checkout order created. Add VITE_RAZORPAY_KEY_ID to open the payment widget.', 'success'); return } new Razorpay({ key: pd.key || import.meta.env.VITE_RAZORPAY_KEY_ID, order_id: pd.razorpay_order_id, amount: pd.amount, currency: pd.currency || 'INR', name: 'Alpha-Commerce', handler: (response: any) => verify.mutate(response) }).open() }, onError: (e) => toast(message(e), 'error') }); const nav = useNavigate(); const verify = useMutation({ mutationFn: (data: any) => api.post('/api/v1/orders/verify-payment', data), onSuccess: ({ data }) => { toast('Payment verified. Order recorded.'); nav(`/orders/${data.id || data.order_id}`) }, onError: (e) => toast(message(e), 'error') }); return <section className="page checkout"><Link className="back" to="/shop"><ArrowLeft size={16} /> Keep shopping</Link><div className="page-heading"><div><span className="eyebrow">CHECKOUT / RAZORPAY</span><h1>Where should it<br />be delivered?</h1></div></div>{isLoading ? <Skeleton rows={3} /> : <><div className="address-list">{(addresses || []).map((a) => <button className={`address-card ${selected === a.id ? 'selected' : ''}`} onClick={() => setSelected(a.id)} key={a.id}><MapPin size={19} /><b>{a.full_name}{a.is_default && <small> DEFAULT</small>}</b><span>{a.house_no}, {a.area}, {a.city}, {a.state} — {a.pincode}</span><span>{a.phone_number}</span></button>)}<Link className="add-address" to="/addresses"><Plus /> Add a delivery address</Link></div><div className="checkout-action"><label className="field"><span>Coupon code (optional)</span><input value={coupon} onChange={(e) => setCoupon(e.target.value)} placeholder="ALPHA10" /></label><button className="primary" disabled={!selected || checkout.isPending} onClick={() => checkout.mutate()}><CreditCard size={17} /> {checkout.isPending ? 'Creating secure order…' : 'Continue to payment'}</button></div></>}</section> }
function Orders() { const { data, isLoading, isError } = useQuery({ queryKey: q.orders, queryFn: endpoints.orders }); return <section className="page"><div className="page-heading"><div><span className="eyebrow">ORDER HISTORY</span><h1>Everything you’ve<br />set in motion.</h1></div></div>{isLoading ? <Skeleton rows={5} /> : isError ? <ApiError /> : !data?.length ? <Empty title="No orders yet." text="Your first order will show up here the moment you check out." to="/shop" label="Browse the catalog" /> : <div className="data-table order-table"><div className="table-head"><span>ORDER ID</span><span>CREATED</span><span>STATUS</span><span>TOTAL</span><span /></div>{data.map((o) => <div className="table-row" key={o.id}><code>{o.id.slice(0, 8)}…</code><span>{date(o.created_at)}</span><Status value={o.status} /><code>{money(o.total_price)}</code><Link to={`/orders/${o.id}`}>Open <ArrowRight size={14} /></Link></div>)}</div>}</section> }
function OrderDetail() { const { id = '' } = useParams(), qc = useQueryClient(), toast = authStore((s) => s.toast); const { data: order, isLoading } = useQuery({ queryKey: ['order', id], queryFn: () => endpoints.order(id) }); const cancel = useMutation({ mutationFn: () => api.patch(`/api/v1/orders/${id}/cancel`), onSuccess: () => { qc.invalidateQueries({ queryKey: ['order', id] }); qc.invalidateQueries({ queryKey: q.orders }); toast('Cancellation request processed.') }, onError: (e) => toast(message(e), 'error') }); if (isLoading) return <section className="page"><Skeleton /></section>; if (!order) return <NotFound />; return <section className="page"><Link className="back" to="/orders"><ArrowLeft size={16} /> Order history</Link><div className="order-header"><div><span className="eyebrow">ORDER RECEIPT</span><h1><code>{order.id.slice(0, 13)}…</code></h1><p>Created {date(order.created_at)}</p></div><Status value={order.status} /></div><div className="receipt-grid"><div className="receipt"><h3>Items in this order</h3>{order.items.map((i) => <div className="receipt-item" key={i.product_id}><span><b>{i.product_name}</b><small>{i.quantity} × {money(i.price_at_purchase)}</small></span><code>{money(i.price_at_purchase * i.quantity)}</code></div>)}<strong>Total paid <code>{money(order.total_price)}</code></strong></div><aside className="order-actions"><Link className="primary full" to={`/orders/${id}/track`}><Activity size={17} /> Track live status</Link>{['pending', 'paid', 'processing'].includes(order.status.toLowerCase()) && <button className="outline full danger" onClick={() => cancel.mutate()}><XCircle size={17} /> Cancel order</button>}<p>Order events are delivered to this page via a token-authenticated connection.</p></aside></div></section> }
function TrackOrder() { const { id = '' } = useParams(), reduced = useReducedMotion(), toast = authStore((s) => s.toast); const [status, setStatus] = useState('pending'); const { data: order } = useQuery({ queryKey: ['order', id], queryFn: () => endpoints.order(id) }); useEffect(() => { if (order) setStatus(order.status) }, [order]); useEffect(() => { const token = authStore.getState().access; if (!token) return; const base = (import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8000').replace(/\/$/, ''); const ws = new WebSocket(`${base}/api/v1/ws/orders/${id}?token=${token}`); ws.onmessage = (event) => { try { const data = JSON.parse(event.data); if (data.status || data.type === 'status_update') { setStatus(data.status || data.new_status); toast(`Order status changed to ${data.status || data.new_status}.`) } } catch { /* Ignore malformed WebSocket messages. */ } }; const heartbeat = setInterval(() => ws.readyState === WebSocket.OPEN && ws.send('ping'), 25_000); return () => { clearInterval(heartbeat); ws.close() } }, [id]); const stages = ['pending', 'paid', 'processing', 'shipped', 'delivered']; const idx = stages.indexOf(status.toLowerCase()); return <section className="page tracking"><Link className="back" to={`/orders/${id}`}><ArrowLeft size={16} /> Order receipt</Link><span className="eyebrow"><Activity size={14} /> LIVE ORDER CHANNEL</span><h1>Order in motion.</h1><p className="tracking-id">ORDER / {id}</p><div className="socket-state"><span className="dot good" /> Authenticated WebSocket session active <code>ws/orders</code></div><div className="timeline">{stages.map((s, i) => <motion.div key={s} className={`stage ${i <= idx ? 'complete' : ''} ${status.toLowerCase() === 'cancelled' ? 'cancelled' : ''}`} initial={false} animate={{ opacity: i <= idx ? 1 : .35, y: i === idx && !reduced ? [0, -5, 0] : 0 }} transition={{ duration: .45 }}><div className="stage-mark">{i < idx ? <Check size={16} /> : <span>{String(i + 1).padStart(2, '0')}</span>}</div><div><Status value={s} /><h3>{s === 'pending' ? 'Order recorded' : s === 'paid' ? 'Payment confirmed' : s === 'processing' ? 'Being prepared' : s === 'shipped' ? 'Out for delivery' : 'Delivered'}</h3><p>{i === idx ? 'Latest event received in real time.' : i < idx ? 'Event committed to the order stream.' : 'Waiting for the next order event.'}</p></div></motion.div>)}</div>{status.toLowerCase() === 'cancelled' && <div className="cancel-note">This order was cancelled. No further fulfilment events will arrive.</div>}</section> }

function Account() { const user = authStore((s) => s.user); const qc = useQueryClient(), toast = authStore((s) => s.toast); const edit = useMutation({ mutationFn: (d: any) => api.patch('/api/v1/users/me', d), onSuccess: ({ data }) => { authStore.getState().setSession(data); qc.invalidateQueries({ queryKey: q.profile }); toast('Profile saved.') }, onError: (e) => toast(message(e), 'error') }); if (!user) return null; return <section className="page account"><div className="page-heading"><div><span className="eyebrow">ACCOUNT / IDENTITY</span><h1>Profile settings.</h1></div><Link className="outline" to="/addresses"><MapPin size={16} /> Address book</Link></div><form className="profile-form" onSubmit={(e) => { e.preventDefault(); edit.mutate(clean(e.currentTarget)) }}><div className="profile-avatar">{user.username.slice(0, 1).toUpperCase()}</div><div><code>ACCOUNT ID / {user.id}</code><h2>{user.full_name || user.username}</h2><p>{user.is_admin ? 'Administrator access enabled' : 'Customer account'}</p></div><div className="form-grid">{field('Full name', 'full_name', 'text', false, user.full_name)}{field('Email', 'email', 'email', false, user.email)}{field('Phone number', 'phone_number', 'tel', false, user.phone_number)}<button className="primary">Save profile <FilePenLine size={16} /></button></div></form></section> }
function Addresses() { const list = useQuery({ queryKey: q.addresses, queryFn: endpoints.addresses }); const [edit, setEdit] = useState<any>(); return <section className="page"><div className="page-heading"><div><span className="eyebrow">ADDRESS BOOK</span><h1>Delivery locations.</h1></div><button className="primary" onClick={() => setEdit({})}><Plus size={16} /> Add address</button></div>{list.isLoading ? <Skeleton rows={4} /> : <div className="addresses">{list.data?.map((a) => <AddressCard key={a.id} address={a} edit={() => setEdit(a)} />)}{!list.data?.length && <Empty title="No delivery locations." text="Add an address before you proceed to secure checkout." />}</div>}{edit && <AddressForm address={edit} close={() => setEdit(undefined)} />}</section> }
function AddressCard({ address, edit }: any) { const qc = useQueryClient(), toast = authStore((s) => s.toast); const action = useMutation({ mutationFn: (mode: string) => mode === 'default' ? api.patch(`/api/v1/addresses/${address.id}/default`) : api.delete(`/api/v1/addresses/${address.id}`), onSuccess: () => { qc.invalidateQueries({ queryKey: q.addresses }); toast('Address book updated.') }, onError: (e) => toast(message(e), 'error') }); return <article className="address-entry"><MapPin /><div><b>{address.full_name} {address.is_default && <small>DEFAULT</small>}</b><p>{address.house_no}, {address.area}, {address.city}, {address.state} — {address.pincode}<br />{address.phone_number}</p></div><div><button className="text-btn" onClick={edit}>Edit</button>{!address.is_default && <button className="text-btn" onClick={() => action.mutate('default')}>Set default</button>}<button className="text-btn danger" onClick={() => action.mutate('delete')}>Delete</button></div></article> }
function AddressForm({ address, close }: any) { const qc = useQueryClient(), toast = authStore((s) => s.toast); const mutation = useMutation({ mutationFn: (d: any) => address.id ? api.patch(`/api/v1/addresses/${address.id}`, d) : api.post('/api/v1/addresses/', d), onSuccess: () => { qc.invalidateQueries({ queryKey: q.addresses }); toast('Address saved.'); close() }, onError: (e) => toast(message(e), 'error') }); return <div className="modal-layer"><form className="modal-form wide" onSubmit={(e) => { e.preventDefault(); mutation.mutate(clean(e.currentTarget)) }}><button className="modal-close" type="button" onClick={close}>×</button><span className="eyebrow">DELIVERY DETAILS</span><h2>{address.id ? 'Edit address' : 'New address'}</h2><div className="two-col">{field('Full name', 'full_name', 'text', true, address.full_name)}{field('Phone number', 'phone_number', 'tel', true, address.phone_number)}{field('House / flat no.', 'house_no', 'text', true, address.house_no)}{field('Area / locality', 'area', 'text', true, address.area)}{field('City', 'city', 'text', true, address.city)}{field('State', 'state', 'text', true, address.state)}{field('Pincode', 'pincode', 'text', true, address.pincode)}<label className="field"><span>Address type</span><select name="address_type" defaultValue={address.address_type || 'home'}><option value="home">Home</option><option value="office">Office</option><option value="other">Other</option></select></label></div><button className="primary full">Save address</button></form></div> }
function Empty({ title, text, to, label }: { title: string; text: string; to?: string; label?: string }) { return <div className="empty"><Package size={26} /><h3>{title}</h3><p>{text}</p>{to && <Link className="primary" to={to}>{label} <ArrowRight size={15} /></Link>}</div> }
function ApiError() { return <div className="empty"><RotateCcw size={26} /><h3>The API is not reachable.</h3><p>Check VITE_API_BASE_URL, then retry the request. The interface never substitutes fake catalog data.</p></div> }
function NotFound() { return <section className="page"><Empty title="This route has no record." text="The page you requested doesn’t exist in the Alpha-Commerce interface." to="/" label="Return home" /></section> }
