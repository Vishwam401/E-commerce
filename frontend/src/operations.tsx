import { Check } from 'lucide-react'
import { Status } from './components'
import { date, money, type Order } from './lib'

export type InventoryReport = {
  total_active_products: number
  out_of_stock_count: number
  low_stock_count: number
  reorder_alert_count: number
}

export type StockMovement = {
  id: string
  movement_type: string
  quantity_changed: number
  quantity_before: number
  quantity_after: number
  reason?: string | null
  created_at: string
}

export function InventoryMetrics({ report, summary = false }: { report: InventoryReport; summary?: boolean }) {
  const metrics = [
    ['Active products', report.total_active_products],
    ['Low stock', report.low_stock_count],
    ['Reorder alerts', report.reorder_alert_count],
  ] as const
  return <div className={`kpis${summary ? '' : ' inventory-kpis'}`}>
    {metrics.map(([label, value]) => <div key={label}><code>{label.toUpperCase()}</code><strong>{value}</strong></div>)}
    {summary && <div><code>OUT OF STOCK</code><strong>{report.out_of_stock_count}</strong></div>}
  </div>
}

export const orderStages = [
  ['pending', 'Order recorded'],
  ['paid', 'Payment confirmed'],
  ['processing', 'Being prepared'],
  ['shipped', 'Out for delivery'],
  ['delivered', 'Delivered'],
] as const

export const orderStatuses = [...orderStages.map(([status]) => status), 'cancelled']

export function OrderQueue({ orders, filter, update }: {
  orders: Pick<Order, 'id' | 'status' | 'created_at' | 'total_price'>[]
  filter: string
  update?: (id: string, status: string) => void
}) {
  const visible = orders.filter((order) => !filter || order.status.toLowerCase() === filter)
  if (!visible.length) return <div className="empty">No orders match this status.</div>
  return <div className="data-table operations-table" role="region" aria-label="Fulfilment queue" tabIndex={0}>
    <table>
      <thead><tr><th scope="col">Order</th><th scope="col">Placed</th><th scope="col">Status</th><th scope="col">Total</th>{update && <th scope="col">Transition</th>}</tr></thead>
      <tbody>{visible.map((order) => <tr key={order.id}>
        <th scope="row"><code>{order.id.length > 9 ? `${order.id.slice(0, 9)}…` : order.id}</code></th>
        <td>{date(order.created_at)}</td>
        <td><Status value={order.status} /></td>
        <td><code>{money(order.total_price)}</code></td>
        {update && <td><select aria-label={`Status for order ${order.id.slice(0, 9)}`} value={order.status.toLowerCase()} onChange={(event) => update(order.id, event.target.value)}>
          {orderStatuses.map((status) => <option key={status}>{status}</option>)}
        </select></td>}
      </tr>)}</tbody>
    </table>
  </div>
}

export function MovementHistory({ movements }: { movements: StockMovement[] }) {
  if (!movements.length) return <div className="empty">No stock movements recorded.</div>
  return <div className="data-table operations-table" role="region" aria-label="Stock movements" tabIndex={0}>
    <table>
      <thead><tr><th scope="col">Time</th><th scope="col">Event</th><th scope="col">Before → After</th><th scope="col">Note</th></tr></thead>
      <tbody>{movements.map((movement) => <tr key={movement.id}>
        <td><code>{date(movement.created_at)}</code></td>
        <td><Status value={movement.movement_type} /></td>
        <td><code className={movement.quantity_changed >= 0 ? 'positive' : 'critical'}>{movement.quantity_before} → {movement.quantity_after} <small>({movement.quantity_changed > 0 ? '+' : ''}{movement.quantity_changed})</small></code></td>
        <td>{movement.reason || '—'}</td>
      </tr>)}</tbody>
    </table>
  </div>
}

export function OrderTimeline({ status, live = false }: { status: string; live?: boolean }) {
  const current = orderStages.findIndex(([stage]) => stage === status.toLowerCase())
  return <>
    <div className="timeline">{orderStages.map(([stage, title], index) => <div key={stage}
      className={`stage${index <= current ? ' complete' : ''}${index === current && live ? ' current-live' : ''}`}>
      <div className="stage-mark" aria-hidden="true">{index < current ? <Check size={16} /> : index + 1}</div>
      <div aria-current={index === current ? 'step' : undefined}>
        <Status value={stage} /><h3>{title}</h3>
        {index === current && <p>Current order status</p>}
      </div>
    </div>)}</div>
    {status.toLowerCase() === 'cancelled' && <p className="cancel-note">This order was cancelled.</p>}
  </>
}
