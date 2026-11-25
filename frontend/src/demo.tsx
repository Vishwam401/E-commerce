import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Activity, ArrowRight, Boxes, ClipboardList, LayoutDashboard } from 'lucide-react'
import { InventoryMetrics, MovementHistory, OrderQueue, OrderTimeline, orderStatuses, type StockMovement } from './operations'

const report = { total_active_products: 24, low_stock_count: 3, reorder_alert_count: 2, out_of_stock_count: 1 }
const orders = [
  { id: 'DEMO-1042', created_at: '2026-08-14T09:20:00+05:30', status: 'shipped', total_price: 4899 },
  { id: 'DEMO-1041', created_at: '2026-08-14T08:30:00+05:30', status: 'processing', total_price: 2499 },
  { id: 'DEMO-1040', created_at: '2026-08-13T16:15:00+05:30', status: 'paid', total_price: 2999 },
]

const movementHistory: Record<string, StockMovement[]> = {
  'Zenith Earbuds Premium': [
    { id: 'move-2', movement_type: 'sale', quantity_changed: -2, quantity_before: 10, quantity_after: 8, reason: 'Checkout', created_at: '2026-08-14T08:30:00+05:30' },
    { id: 'move-1', movement_type: 'restock', quantity_changed: 8, quantity_before: 2, quantity_after: 10, reason: 'Stock received', created_at: '2026-08-13T15:30:00+05:30' },
  ],
  'Nexus Keyboard Classic': [
    { id: 'move-3', movement_type: 'sale', quantity_changed: -1, quantity_before: 6, quantity_after: 5, reason: 'Checkout', created_at: '2026-08-14T09:20:00+05:30' },
  ],
}
const previewViews = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'inventory', label: 'Inventory', icon: Boxes },
  { id: 'orders', label: 'Orders', icon: ClipboardList },
  { id: 'tracking', label: 'Tracking', icon: Activity },
] as const

export function DashboardPreview({ compact = false }: { compact?: boolean }) {
  const [view, setView] = useState<(typeof previewViews)[number]['id']>('overview')
  const [product, setProduct] = useState(Object.keys(movementHistory)[0])
  const [filter, setFilter] = useState('')
  const [trackedOrder, setTrackedOrder] = useState(orders[0])
  return <div className={`dashboard-preview${compact ? ' dashboard-compact' : ''}`}>
    <div className="dashboard-top"><span><LayoutDashboard size={17} /> Operations console</span><small>Sample data</small></div>
    <div className="dashboard-switch" role="group" aria-label="Dashboard views">
      {previewViews.map(({ id, label, icon: Icon }) => <button key={id} type="button" aria-pressed={view === id} onClick={() => setView(id)}>
        <Icon size={15} aria-hidden="true" />{label}
      </button>)}
    </div>
    <div className="dashboard-content">
      {view === 'overview' && <>
        <h2>Inventory overview</h2>
        <InventoryMetrics report={report} summary />
        <div className="dashboard-shortcuts">
          <button type="button" onClick={() => setView('inventory')}><Boxes size={19} /><span>Inventory ledger<small>Inspect stock movements</small></span><ArrowRight size={15} /></button>
          <button type="button" onClick={() => setView('orders')}><ClipboardList size={19} /><span>Fulfilment queue<small>Filter order statuses</small></span><ArrowRight size={15} /></button>
        </div>
      </>}
      {view === 'inventory' && <>
        <div className="dashboard-heading"><h2>Inventory ledger</h2><label>Product <select value={product} onChange={(event) => setProduct(event.target.value)}>
          {Object.keys(movementHistory).map((name) => <option key={name}>{name}</option>)}
        </select></label></div>
        <MovementHistory movements={movementHistory[product]} />
      </>}
      {view === 'orders' && <>
        <div className="dashboard-heading"><h2>Fulfilment queue</h2><label>Order status <select value={filter} onChange={(event) => setFilter(event.target.value)}>
          <option value="">All states</option>{orderStatuses.map((status) => <option key={status}>{status}</option>)}
        </select></label></div>
        <OrderQueue orders={orders} filter={filter} />
      </>}
      {view === 'tracking' && <>
        <div className="dashboard-heading"><h2>Order tracking</h2><label>Order <select value={trackedOrder.id} onChange={(event) => {
          const order = orders.find(({ id }) => id === event.target.value)
          if (order) setTrackedOrder(order)
        }}>{orders.map(({ id }) => <option key={id}>{id}</option>)}</select></label></div>
        <OrderTimeline status={trackedOrder.status} />
      </>}
    </div>
  </div>
}

export function DemoPage() {
  return <section className="page public-page demo-page">
    <div className="public-heading">
      <span className="eyebrow">LIVE DEMO</span>
      <h1>Explore the operations console.</h1>
      <p>Filter the fulfilment queue, inspect inventory movements, and follow an order from payment to delivery. This interactive, read-only demo uses the application’s own screens with sample records.</p>
    </div>
    <DashboardPreview />
    <section className="operator-notes" aria-labelledby="demo-workflows">
      <h2 id="demo-workflows">Inside the full application</h2>
      <div className="public-card-grid">
        <article><h3>Merchant administration</h3><p>Authorized operators can manage products, categories, promotions, stock adjustments, and order status.</p></article>
        <article><h3>Live customer tracking</h3><p>Customers follow their own orders through an authenticated WebSocket connection.</p></article>
        <article><h3>Payment reconciliation</h3><p>The backend verifies Razorpay signatures and reconciles captured payments against stored transactions.</p></article>
      </div>
      <div className="public-actions"><Link className="primary" to="/shop">Explore the demo catalog <ArrowRight size={16} /></Link><Link className="button-secondary" to="/contact?topic=demo">Request a guided demo</Link></div>
    </section>
  </section>
}
