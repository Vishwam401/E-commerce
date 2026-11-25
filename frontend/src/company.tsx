import { useState, type FormEvent } from 'react'
import { useMutation } from '@tanstack/react-query'
import { ArrowRight, Mail } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from './lib'

const supportEmail = 'connect@alpha-commerce.tech'
const topics = [
  { value: 'demo', label: 'Request a demo' },
  { value: 'growth', label: 'Growth plan' },
  { value: 'enterprise', label: 'Enterprise and integrations' },
  { value: 'support', label: 'Platform support' },
  { value: 'security', label: 'Security report' },
  { value: 'other', label: 'Other' },
] as const

export function About() {
  return <section className="page public-page">
    <div className="public-heading"><span className="eyebrow">ABOUT ALPHA-COMMERCE</span><h1>Commerce operations in one place.</h1><p>Alpha-Commerce is an early-stage commerce platform for digital brands, direct-to-consumer merchants, and retail teams managing online stock and fulfilment.</p></div>
    <div className="public-card-grid">
      <article><h2>What we’re building</h2><p>A single workflow for managing products, protecting stock during checkout, verifying payments, and giving customers live order updates.</p></article>
      <article><h2>Why it matters</h2><p>When stock, payments, and order status are tracked in separate systems, merchants have to piece together what happened. Alpha-Commerce keeps inventory and order changes traceable from checkout through delivery.</p></article>
      <article><h2>Founder and contact</h2><p>Vishwam Vaghasiya founded Alpha-Commerce. The storefront and read-only operations demo are available for evaluation.</p><p><a href="https://www.linkedin.com/in/vishwam-vaghasiya/">Vishwam on LinkedIn</a><br /><a href="https://github.com/Vishwam401">Vishwam on GitHub</a><br /><a href={`mailto:${supportEmail}`}>{supportEmail}</a></p></article>
    </div>
    <section className="operator-notes"><h2>Technology and infrastructure</h2><p>The React storefront connects to FastAPI, PostgreSQL, Redis, and Celery. Razorpay handles checkout. The public frontend runs on Vercel, and the API runs on Oracle Cloud Infrastructure using Docker Compose.</p><Link className="button-secondary" to="/#platform">Explore the architecture <ArrowRight size={16} /></Link></section>
    <section className="operator-notes"><h2>Product roadmap</h2><p>The public project roadmap includes two planned storefront improvements.</p><div className="public-card-grid roadmap-grid">
      <article><span className="roadmap-status">Planned</span><h3>Product reviews and ratings</h3><p>Let shoppers share feedback on products.</p></article>
      <article><span className="roadmap-status">Planned</span><h3>Wishlists and saved items</h3><p>Let shoppers keep a list of products to revisit.</p></article>
    </div></section>
  </section>
}

export function Contact() {
  const [params] = useSearchParams()
  const initialTopic = topics.find(({ value }) => value === params.get('topic'))?.value || 'other'
  return <section className="page public-page contact-page">
    <div className="public-heading"><span className="eyebrow">CONTACT</span><h1>Talk to Alpha-Commerce.</h1><p>Request a walkthrough or get in touch about plans, support, and integrations.</p></div>
    <div className="contact-grid">
      <article className="contact-card"><Mail size={23} aria-hidden="true" /><h2>Email us</h2><a href={`mailto:${supportEmail}`}>{supportEmail}</a><p>For security reports, share a description and a way to reach you. Keep passwords, payment details, and access tokens out of your message.</p></article>
      <ContactForm key={initialTopic} initialTopic={initialTopic} />
    </div>
  </section>
}

function ContactForm({ initialTopic }: { initialTopic: (typeof topics)[number]['value'] }) {
  const [validation, setValidation] = useState('')
  const submission = useMutation({ mutationFn: (values: Record<string, FormDataEntryValue>) => api.post('/api/v1/contact', values, { timeout: 20_000 }) })
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (submission.isPending) return
    const form = event.currentTarget
    const values = Object.fromEntries(new FormData(form))
    if (String(values.name).trim().length < 2 || String(values.message).trim().length < 10) {
      submission.reset()
      setValidation('Enter a name and a message of at least 10 characters.')
      return
    }
    setValidation('')
    submission.mutate(values, { onSuccess: () => form.reset() })
  }
  const lastMessage = submission.variables
  const emailDraft = lastMessage ? `mailto:${supportEmail}?subject=${encodeURIComponent(topics.find(({ value }) => value === lastMessage.topic)?.label || 'Alpha-Commerce inquiry')}&body=${encodeURIComponent(`Name: ${lastMessage.name}\nEmail: ${lastMessage.email}\n\n${lastMessage.message}`)}` : undefined
  return <form className="contact-form" onSubmit={submit} aria-busy={submission.isPending}>
    <h2>Send a message</h2>
    <fieldset disabled={submission.isPending}>
      <label className="field"><span>Name</span><input name="name" autoComplete="name" required minLength={2} maxLength={100} /></label>
      <label className="field"><span>Email</span><input name="email" type="email" autoComplete="email" required maxLength={254} /></label>
      <label className="field"><span>Topic</span><select name="topic" defaultValue={initialTopic}>{topics.map(({ label, value }) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label className="field"><span>Message</span><textarea name="message" required minLength={10} maxLength={2000} rows={5} /></label>
      <button className="primary" type="submit">{submission.isPending ? 'Sending…' : 'Send message'} <ArrowRight size={16} /></button>
    </fieldset>
    {validation && <p className="form-error" role="alert">{validation}</p>}
    {submission.isSuccess && <p className="form-success" role="status">Your message was sent.</p>}
    {submission.isError && <p className="form-error" role="alert">We couldn’t send your message. Try again or <a href={emailDraft}>open an email draft</a> and send it from your email app.</p>}
  </form>
}

type LegalSection = { title: string; text: string }
function InformationPage({ title, intro, sections }: { title: string; intro: string; sections: LegalSection[] }) {
  return <section className="page public-page legal-page">
    <div className="public-heading"><h1>{title}</h1><p>{intro}</p></div>
    <div className="legal-sections">{sections.map(({ title: section, text }) => <article key={section}><h2>{section}</h2><p>{text}</p></article>)}</div>
    <p className="legal-contact">Questions about {title.toLowerCase()}? <a href={`mailto:${supportEmail}`}>{supportEmail}</a></p>
  </section>
}

export function Privacy() {
  return <InformationPage title="Privacy policy" intro="This policy describes the information used to operate Alpha-Commerce." sections={[
    { title: 'Information you provide', text: 'Account information includes your username and email, as well as any profile details you provide. If you use checkout, the platform records order details and the shipping address you select. If you contact us, we receive the name, email address, topic, and message you provide.' },
    { title: 'Payments', text: 'Razorpay processes the payment details entered in its checkout widget. Alpha-Commerce stores transaction references and payment status for order verification and reconciliation.' },
    { title: 'Sessions', text: 'The storefront uses browser local storage to retain your session refresh token. Sign out to remove it from the browser.' },
  ]} />
}

export function Terms() {
  return <InformationPage title="Terms of service" intro="These terms describe permitted use of the Alpha-Commerce platform." sections={[
    { title: 'Use of service', text: 'Use Alpha-Commerce in compliance with applicable law. Keep your account details accurate and your credentials secure. Unauthorized access, interference with the platform, and fraudulent activity are prohibited.' },
    { title: 'Demo and commercial plans', text: 'The public console uses sample data for evaluation. Proposed plan prices are for discussion, and commercial terms are subject to a separate agreement.' },
    { title: 'Merchant responsibilities', text: 'Merchants are responsible for the accuracy, availability, fulfilment, and legal compliance of their catalogs and sales. Payment-provider terms and applicable tax obligations may also apply.' },
  ]} />
}

export function Security() {
  return <InformationPage title="Security" intro="The platform protects access to customer accounts, operations, and payment workflows." sections={[
    { title: 'Account and admin access', text: 'The API requires authenticated sessions for account actions and checks administrator permissions before allowing restricted operations.' },
    { title: 'Order and payment protection', text: 'Order tracking checks that the authenticated account owns the order. The backend verifies Razorpay payment and webhook signatures before applying payment updates.' },
    { title: 'Reporting an issue', text: 'Email us with a description of the issue and a way to contact you. Keep credentials, payment data, and access tokens out of your report.' },
  ]} />
}
