export type PaymentReceipt = { razorpay_order_id: string; razorpay_payment_id: string; razorpay_signature: string }

type RazorpayCheckout = new (config: {
  key: string
  order_id: string
  amount: number
  currency: string
  name: string
  handler: (receipt: PaymentReceipt) => void
}) => { open: () => void }

const razorpayWindow = () => window as Window & { Razorpay?: RazorpayCheckout }
let loading: Promise<RazorpayCheckout> | undefined

export function loadRazorpay(): Promise<RazorpayCheckout> {
  const existing = razorpayWindow().Razorpay
  if (existing) return Promise.resolve(existing)
  loading ??= new Promise<RazorpayCheckout>((resolve, reject) => {
    const script = document.createElement('script')
    script.src = 'https://checkout.razorpay.com/v1/checkout.js'
    const failed = () => { script.remove(); reject(new Error('Payment checkout could not load.')) }
    const timeout = window.setTimeout(failed, 15_000)
    script.onload = () => {
      window.clearTimeout(timeout)
      const checkout = razorpayWindow().Razorpay
      if (checkout) resolve(checkout)
      else failed()
    }
    script.onerror = () => { window.clearTimeout(timeout); failed() }
    document.head.append(script)
  }).finally(() => { loading = undefined })
  return loading
}
