export const siteOrigin = 'https://www.alpha-commerce.tech'

export const publicPages = {
  '/': { title: 'Alpha-Commerce | Commerce infrastructure built to scale', description: 'Manage inventory, fulfil orders, and reconcile payments with Alpha-Commerce. Explore the interactive commerce operations demo.' },
  '/demo': { title: 'Interactive Operations Demo | Alpha-Commerce', description: 'Explore the Alpha-Commerce inventory ledger, fulfilment queue, and order tracking in a read-only demo.' },
  '/shop': { title: 'Demo Product Catalog | Alpha-Commerce', description: 'Explore the demo storefront with catalog search, product pricing, and stock availability.' },
  '/pricing': { title: 'Plans and Pricing | Alpha-Commerce', description: 'Compare the proposed Starter, Growth, and Enterprise plans and contact Alpha-Commerce for availability.' },
  '/about': { title: 'About and Roadmap | Alpha-Commerce', description: 'Meet founder Vishwam Vaghasiya and learn about the Alpha-Commerce platform, infrastructure, and roadmap.' },
  '/contact': { title: 'Contact and Demo Requests | Alpha-Commerce', description: 'Request an Alpha-Commerce demo or contact the team about pricing, integrations, security, and platform support.' },
  '/privacy': { title: 'Privacy Policy | Alpha-Commerce', description: 'Learn what information Alpha-Commerce uses to run accounts, orders, payments, and support.' },
  '/terms': { title: 'Terms of Service | Alpha-Commerce', description: 'Read the terms of service for the Alpha-Commerce platform and demo.' },
  '/security': { title: 'Security and Reporting | Alpha-Commerce', description: 'Learn about the platform’s account, order, and payment protections and how to report a security issue.' },
}

export function getMetadata(path: string) {
  const normalized = path.replace(/\/$/, '') || '/'
  const page = publicPages[normalized as keyof typeof publicPages]
  return page ? { ...page, index: true } : { title: 'Alpha-Commerce', description: publicPages['/'].description, index: false }
}
