import { useRef, useState } from 'react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertCircle, ArrowRight, Check, Menu, Minus, Plus, ShoppingBag, Trash2, X } from 'lucide-react'
import { api, authStore, endpoints, message, money, type Cart } from './lib'

export function Toasts() { const toasts = authStore((s) => s.toasts); return <div className="toast-stack">{toasts.map((t) => <div className={`toast ${t.type}`} key={t.id}>{t.type === 'error' ? <AlertCircle size={16} /> : <Check size={16} />}{t.message}</div>)}</div> }
export function Status({ value }: { value: string }) { return <span className={`status ${value.toLowerCase()}`}>{value.replace('_', ' ')}</span> }
const mainLinks = [
  ['Home', '/'], ['Platform', '/#platform'], ['Features', '/#features'], ['Live Demo', '/demo'],
  ['Pricing', '/pricing'], ['About Us', '/about'], ['Contact', '/contact'],
]

export function Header() {
  const user = authStore((state) => state.user), toggleCart = authStore((state) => state.toggleCart)
  const navigate = useNavigate(), location = useLocation(), qc = useQueryClient()
  const [openFor, setOpenFor] = useState<string>()
  const menuButton = useRef<HTMLButtonElement>(null)
  const open = openFor === location.key
  const closeMenu = () => setOpenFor(undefined)
  const logout = () => {
    const { access, clear } = authStore.getState()
    if (access) void api.post('/auth/logout', undefined, { headers: { Authorization: `Bearer ${access}` } }).catch(() => {})
    clear()
    qc.clear()
    navigate('/')
  }
  return <header className="topbar site-header" onKeyDown={(event) => {
    if (open && event.key === 'Escape') { closeMenu(); menuButton.current?.focus() }
  }}>
    <a className="skip-link" href="#main-content">Skip to content</a>
    <Link className="brand" to="/" aria-label="Alpha-Commerce home"><span aria-hidden="true">α</span> ALPHA<span className="dim">/COMMERCE</span></Link>
    <button className="menu-button" type="button" ref={menuButton} aria-label={open ? 'Close menu' : 'Open menu'} aria-controls="site-navigation" aria-expanded={open} onClick={() => setOpenFor(open ? undefined : location.key)}>
      {open ? <X size={21} /> : <Menu size={21} />}
    </button>
    <nav className={`site-nav${open ? ' is-open' : ''}`} id="site-navigation" aria-label="Main navigation">
      {mainLinks.map(([label, to]) => to.includes('#') ? <Link key={to} to={to} aria-current={`${location.pathname}${location.hash}` === to ? 'location' : undefined} onClick={closeMenu}>{label}</Link> :
        <NavLink key={to} end to={to} className={({ isActive }) => isActive && (to !== '/' || !location.hash) ? 'active' : ''} aria-current={to === '/' && location.hash ? false : undefined} onClick={closeMenu}>{label}</NavLink>)}
      <NavLink to="/shop" onClick={closeMenu}>Catalog</NavLink>
      {user && <NavLink to="/orders" onClick={closeMenu}>Orders</NavLink>}
      {user?.is_admin && <NavLink className="admin-nav" to="/admin" onClick={closeMenu}>Admin</NavLink>}
    </nav>
    <div className="nav-actions">
      {user ? <><Link className="user-chip" to="/account" aria-label="Account">{user.username.slice(0, 1).toUpperCase()}</Link><button className="text-btn" onClick={logout}>Sign out</button></> : <Link className="text-btn" to="/login">Sign in</Link>}
      <button className="cart-button" onClick={toggleCart} aria-label="Cart"><ShoppingBag size={18} /><span>Cart</span></button>
    </div>
  </header>
}

export function Footer() {
  return <footer className="site-footer"><div className="footer-grid">
    <div className="footer-brand"><Link className="brand" to="/" aria-label="Alpha-Commerce home"><span aria-hidden="true">α</span> ALPHA<span className="dim">/COMMERCE</span></Link><p>Commerce infrastructure for digital brands and retail teams.</p></div>
    <div><h2>Platform</h2><Link to="/demo">Live Demo</Link><Link to="/shop">Demo Catalog</Link><Link to="/pricing">Pricing</Link><Link to="/orders">Order Tracking</Link><a href="https://api.alpha-commerce.tech/docs">Developer APIs</a></div>
    <div><h2>Company</h2><Link to="/about">About Us</Link><Link to="/contact">Contact</Link><Link to="/contact?topic=demo">Request a Demo</Link></div>
    <div><h2>Legal</h2><Link to="/privacy">Privacy Policy</Link><Link to="/terms">Terms of Service</Link><Link to="/security">Security</Link></div>
  </div><div className="footer-bottom"><span>© Alpha-Commerce</span><a href="mailto:connect@alpha-commerce.tech">connect@alpha-commerce.tech</a></div></footer>
}

export function Skeleton({ rows = 6 }: { rows?: number }) { return <div className="skeleton-wrap">{Array.from({ length: rows }).map((_, i) => <div className="skeleton" key={i} />)}</div> }
export function CartDrawer() { const user = authStore((s) => s.user), open = authStore((s) => s.cartOpen), toggle = authStore((s) => s.toggleCart), qc = useQueryClient(), toast = authStore((s) => s.toast); const { data: cart, isLoading, isError, refetch } = useQuery({ queryKey: ['cart', user?.id], queryFn: endpoints.cart, enabled: open && !!user }); const mutate = useMutation({ mutationFn: ({ method, url, data }: any) => api({ method, url, data }), onSuccess: () => { qc.invalidateQueries({ queryKey: ['cart'] }); toast('Cart updated.') }, onError: (e) => toast(message(e), 'error') }); if (!open) return null; const c = cart as Cart | undefined; return <><div className="scrim" onClick={toggle} /><aside className="cart-drawer" aria-label="Shopping cart"><div className="drawer-head"><div><small>YOUR SESSION CART</small><h2>Cart ledger</h2></div><button className="icon-btn" aria-label="Close cart" onClick={toggle}><X /></button></div>{!user ? <div className="empty"><p>Sign in to view your cart.</p><Link className="primary" to="/login" onClick={toggle}>Sign in</Link></div> : isLoading ? <Skeleton rows={4} /> : isError ? <div className="empty"><p>Could not load your cart.</p><button className="button-secondary" onClick={() => { void refetch() }}>Retry</button></div> : !c?.items.length ? <div className="empty">Your cart is ready when you are.<br /><Link to="/shop" onClick={toggle}>Browse the catalog <ArrowRight size={15} /></Link></div> : <><div className="cart-items">{c.items.map((i) => <div className="cart-row" key={i.id}><div><b>{i.product.name}</b><code>{money(i.product.price)}</code></div><div className="quantity"><button aria-label={`Decrease quantity of ${i.product.name}`} onClick={() => mutate.mutate({ method: 'patch', url: `/api/v1/cart/items/${i.id}/decrease` })}><Minus size={13} /></button><span>{i.quantity}</span><button aria-label={`Increase quantity of ${i.product.name}`} onClick={() => mutate.mutate({ method: 'put', url: `/api/v1/cart/items/${i.id}`, data: { quantity: i.quantity + 1 } })}><Plus size={13} /></button></div><button className="delete" aria-label={`Remove ${i.product.name}`} onClick={() => mutate.mutate({ method: 'delete', url: `/api/v1/cart/items/${i.id}` })}><Trash2 size={15} /></button></div>)}</div><Coupon cart={c} /><div className="totals"><span>Subtotal <code>{money(c.total_price + (c.discount_amount || 0))}</code></span>{c.discount_amount > 0 && <span className="discount">Coupon · {c.coupon_code} <code>−{money(c.discount_amount)}</code></span>}<strong>Final total <code>{money(c.total_after_discount || c.total_price)}</code></strong></div><Link className="primary full" onClick={toggle} to="/checkout">Secure checkout <ArrowRight size={16} /></Link><button className="clear-cart" onClick={() => mutate.mutate({ method: 'delete', url: '/api/v1/cart/' })}>Clear cart</button></>}</aside></> }
function Coupon({ cart }: { cart: Cart }) { const qc = useQueryClient(), toast = authStore((s) => s.toast); const mutation = useMutation({ mutationFn: (code?: string) => code ? api.post('/api/v1/cart/apply-coupon', { code }) : api.delete('/api/v1/cart/remove-coupon'), onSuccess: () => { qc.invalidateQueries({ queryKey: ['cart'] }); toast('Coupon updated.') }, onError: (e) => toast(message(e), 'error') }); const submit = (e: React.FormEvent<HTMLFormElement>) => { e.preventDefault(); mutation.mutate(String(new FormData(e.currentTarget).get('code'))) }; return cart.coupon_code ? <button className="coupon-applied" onClick={() => mutation.mutate(undefined)}>{cart.coupon_code} applied <X size={14} /></button> : <form onSubmit={submit} className="coupon"><input name="code" aria-label="Coupon code" placeholder="PROMO CODE" required /><button>Apply</button></form> }
