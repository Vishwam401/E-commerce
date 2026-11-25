import { Activity, ArrowDown, ArrowRight, Boxes, Check, ClipboardList, Code2, Database, DatabaseZap, Layers, LockKeyhole, Radio, Server, ShieldCheck, Store, Webhook, Workflow } from 'lucide-react'
import { Link } from 'react-router-dom'
import { DashboardPreview } from './demo'

const features = [
  { icon: Boxes, title: 'Inventory synchronization', text: 'Stock quantities are updated transactionally. Catalog edits and stock adjustments invalidate cached catalog records.' },
  { icon: LockKeyhole, title: 'Oversell protection', text: 'PostgreSQL checks and deducts available stock in one operation so simultaneous checkouts cannot claim the same units.' },
  { icon: ClipboardList, title: 'Append-only stock ledger', text: 'Review before-and-after quantities for each recorded stock movement to investigate discrepancies.' },
  { icon: Workflow, title: 'Background order work', text: 'Celery sends payment and order notifications in the background so email delivery does not hold up order updates.' },
  { icon: Radio, title: 'Live order updates', text: 'An authenticated WebSocket channel pushes fulfilment changes to the customer who owns the order.' },
  { icon: ShieldCheck, title: 'Payment verification', text: 'The backend checks Razorpay payment signatures before recording payment confirmation.' },
  { icon: Webhook, title: 'Webhook reconciliation', text: 'Verified Razorpay capture events reconcile against stored transactions and update the associated order.' },
  { icon: Layers, title: 'Role-based access', text: 'Customer accounts and restricted admin routes keep operational controls behind authorization.' },
  { icon: Code2, title: 'Developer APIs', text: 'FastAPI exposes documented endpoints for catalog, cart, orders, and administration.' },
]

export function Home({ catalog }: { catalog: React.ReactNode }) {
  return <>
    <section className="hero commerce-hero">
      <div className="landing-container hero-layout">
        <div className="hero-copy">
          <div className="eyebrow"><Activity size={15} aria-hidden="true" /> COMMERCE OPERATIONS PLATFORM</div>
          <h1>Commerce infrastructure <em>built to scale.</em></h1>
          <p>Alpha-Commerce gives digital brands and retail teams one place to manage inventory, fulfil orders, and reconcile payments. Give customers live order updates and keep a traceable record of every stock movement.</p>
          <div className="hero-actions"><Link className="primary" to="/demo">Explore Live Demo <ArrowRight size={17} /></Link><Link className="button-secondary" to="/pricing">View Pricing</Link></div>
        </div>
        <DashboardPreview compact />
      </div>
    </section>
    <section className="demo-brands" aria-labelledby="demo-brands-heading">
      <div className="landing-container">
        <h2 id="demo-brands-heading">Demo catalog brands</h2>
        <p>These fictional brands illustrate storefront and inventory workflows.</p>
        <ul>{['Zenith Audio', 'Nexus Tech', 'Horizon Labs', 'Apex Apparel', 'Quantum Gear'].map((brand) => <li key={brand}>{brand}</li>)}</ul>
      </div>
    </section>
    <section className="landing-section landing-container" id="features">
      <div className="landing-heading"><span className="eyebrow">FEATURES</span><h2>From stock to fulfilment</h2><p>Track inventory changes, confirm payment, and keep shoppers informed as an order moves through fulfilment.</p></div>
      <div className="public-card-grid">{features.map(({ icon: Icon, title, text }) => <article key={title}><Icon size={23} aria-hidden="true" /><h3>{title}</h3><p>{text}</p></article>)}</div>
    </section>
    <Architecture />
    {catalog}
    <section className="cta-banner">
      <h2>See how it fits your store</h2>
      <p>Explore the console yourself or ask us to walk through your inventory and fulfilment workflow.</p>
      <div className="cta-buttons"><Link className="primary" to="/demo">Explore Live Demo <ArrowRight size={16} /></Link><Link className="button-secondary" to="/contact?topic=demo">Request a guided demo</Link></div>
    </section>
  </>
}

function Architecture() {
  return <section className="architecture landing-section" id="platform">
    <div className="landing-container">
      <div className="landing-heading"><span className="eyebrow">PLATFORM ARCHITECTURE</span><h2>How the application runs</h2><p>The public React storefront runs on Vercel. The API runs on Oracle Cloud Infrastructure, where Docker Compose defines the backend services.</p></div>
      <div className="architecture-diagram" aria-label="React connects to FastAPI through Caddy over HTTPS and WebSocket. FastAPI uses PostgreSQL, Redis, and Razorpay. Redis queues notification jobs for Celery.">
        <div className="architecture-node architecture-center"><Store size={23} aria-hidden="true" /><div><strong>React frontend</strong><small>Storefront and operations console on Vercel</small></div></div>
        <div className="architecture-connector"><ArrowDown size={18} aria-hidden="true" /> HTTPS &amp; authenticated WebSocket via Caddy</div>
        <div className="architecture-backend">
          <div className="architecture-node architecture-center"><Server size={23} aria-hidden="true" /><div><strong>FastAPI</strong><small>Catalog, checkout, inventory, and orders on OCI</small></div></div>
          <div className="architecture-connector"><ArrowDown size={18} aria-hidden="true" /> Persists records, queues jobs, and reconciles payments</div>
          <div className="architecture-branches">
            <div className="architecture-node"><Database size={22} aria-hidden="true" /><div><strong>PostgreSQL</strong><small>Orders and stock ledger</small></div></div>
            <div className="architecture-node"><DatabaseZap size={22} aria-hidden="true" /><div><strong>Redis → Celery</strong><small>Cache, task broker, and email workers</small></div></div>
            <div className="architecture-node"><Webhook size={22} aria-hidden="true" /><div><strong>Razorpay</strong><small>Checkout and signed webhooks</small></div></div>
          </div>
        </div>
      </div>
    </div>
  </section>
}

const plans = [
  { name: 'Starter', price: '₹0', unit: 'per month', fee: 'Proposed 1.5% platform transaction fee', text: 'For merchants evaluating catalog and checkout workflows.', scope: ['Catalog, cart, and Razorpay checkout', 'Order history and tracking', 'Demo account registration'], cta: 'Create demo account', to: '/register' },
  { name: 'Growth', price: '₹2,499', unit: 'per month', fee: 'Proposed 0.5% platform transaction fee', text: 'For brands reviewing how to manage stock and fulfilment.', scope: ['Starter workflows', 'Inventory ledger and low-stock views', 'Fulfilment queue and role-based admin'], cta: 'Ask about Growth', to: '/contact?topic=growth' },
  { name: 'Enterprise', price: 'Custom', unit: 'pricing', fee: 'Transaction fees discussed with sales', text: 'For retailers with integration or deployment requirements.', scope: ['Growth workflows', 'API and integration discussion', 'Deployment requirements review'], cta: 'Talk to enterprise sales', to: '/contact?topic=enterprise' },
]

export function PricingPage() {
  return <section className="page public-page">
    <div className="public-heading"><span className="eyebrow">PRICING</span><h1>Choose a plan to discuss.</h1><p>Explore the demo today. The figures below are proposals for future commercial plans. Contact us to discuss availability.</p></div>
    <div className="pricing-grid commercial-grid">{plans.map((plan) => <article className="pricing-card" key={plan.name}>
      <div className="card-head"><h2>{plan.name}</h2><p className="card-desc">{plan.text}</p><div className="price-row"><strong>{plan.price}</strong><span>{plan.unit}</span></div><p className="plan-fee">{plan.fee}</p></div>
      <ul>{plan.scope.map((item) => <li key={item}><Check size={16} aria-hidden="true" />{item}</li>)}</ul>
      <Link className="button-secondary full" to={plan.to}>{plan.cta} <ArrowRight size={15} /></Link>
    </article>)}</div>
    <p className="pricing-explainer">A platform transaction fee would be a percentage of the order amount. Payment-provider fees are separate and depend on the merchant’s Razorpay agreement. Send us your requirements to confirm availability and terms.</p>
  </section>
}
