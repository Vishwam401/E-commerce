import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { isAxiosError } from 'axios'
import { ArrowLeft, ArrowRight, Package, Search, ShoppingCart } from 'lucide-react'
import { api, authStore, endpoints, money, type Category, type Product } from './lib'
import { Skeleton } from './components'
import { demoProductImage, featured } from './catalog-images'

function ProductImage({ product, category, detail = false }: { product: Product; category?: string; detail?: boolean }) {
  const visual = demoProductImage(product, category)
  return <div className={`catalog-image${detail ? ' detail-image' : ''}`}>
    {visual ? <><img src={`/products/${visual.image}.webp`}
      srcSet={visual.size > 360 ? `/products/${visual.image}-320.webp 320w, /products/${visual.image}.webp 600w` : undefined}
      sizes={detail ? '(max-width: 780px) 90vw, 500px' : '(max-width: 600px) 45vw, (max-width: 900px) 30vw, 285px'}
      width={visual.size} height={visual.size} loading={detail ? 'eager' : 'lazy'} decoding="async" alt={visual.alt} />
      <small className="illustration-label">Illustrative image</small></> :
      <div className="no-product-image"><Package size={32} aria-hidden="true" /><small>Image unavailable</small></div>}
  </div>
}

function Stock({ count }: { count: number }) {
  return <span className="catalog-stock"><span className={`dot ${count > 0 ? 'good' : 'bad'}`} aria-hidden="true" />{count > 0 ? `${count} in stock` : 'Out of stock'}</span>
}

function ProductGrid({ products, categories }: { products: Product[]; categories?: Map<string, string> }) {
  return <div className="catalog-grid">{products.map((product) => <article className="catalog-card" key={product.id}>
    <Link to={`/product/${product.id}`} aria-label={`View ${product.name}`}><ProductImage product={product} category={categories?.get(product.category_id || '')} /></Link>
    <div className="catalog-card-body"><Stock count={product.stock_quantity} /><h3><Link to={`/product/${product.id}`}>{product.name}</Link></h3>
      <p>{product.description || 'See the product details for availability.'}</p>
      <strong>{money(product.price)}</strong>
    </div>
  </article>)}</div>
}

function CatalogLoading() {
  return <div className="catalog-grid" role="status"><span className="sr-only">Loading catalog…</span>{Array.from({ length: 4 }, (_, index) => <div key={index} className="catalog-loading" aria-hidden="true"><div className="skeleton" /><div className="skeleton" /><div className="skeleton" /></div>)}</div>
}

function CatalogState({ title, detail, retry, reset }: { title: string; detail: string; retry?: () => void; reset?: () => void }) {
  return <div className="empty"><Package size={26} aria-hidden="true" /><h3>{title}</h3><p>{detail}</p>
    {retry && <button className="button-secondary" onClick={retry}>Retry</button>}{reset && <button className="button-secondary" onClick={reset}>Reset filters</button>}
  </div>
}

export function HomeCatalog() {
  const products = useQuery({ queryKey: ['products'], queryFn: () => endpoints.products() })
  const selected = featured.flatMap(({ name }) => (products.data || []).filter((product) => product.name === name).slice(0, 1))
  return <section className="landing-section landing-container" id="catalog">
    <div className="section-title catalog-section-title"><div className="landing-heading"><span className="eyebrow">DEMO STOREFRONT</span><h2>Featured products</h2><p>Try the storefront with catalog and stock data from the demo API.</p></div><Link to="/shop">Open catalog <ArrowRight size={16} /></Link></div>
    {products.isLoading ? <CatalogLoading /> : products.isError ? <CatalogState title="Catalog is temporarily unavailable" detail="Try loading the demo products again." retry={() => { void products.refetch() }} /> :
      <ProductGrid products={selected.length ? selected : (products.data || []).slice(0, 4)} />}
    {products.isSuccess && !products.data.length && <CatalogState title="The catalog is empty" detail="Products will appear here when they are available." />}
  </section>
}

function flattenCategories(categories: Category[]): Category[] {
  return categories.flatMap((category) => [category, ...flattenCategories(category.sub_categories || [])])
}

const catalogPageSize = 100

export function Shop() {
  const [params, setParams] = useSearchParams()
  const categoryId = params.get('category') || ''
  const [search, setSearch] = useState('')
  const [debounced, setDebounced] = useState('')
  useEffect(() => { const timer = setTimeout(() => setDebounced(search.trim()), 300); return () => clearTimeout(timer) }, [search])
  const categories = useQuery({ queryKey: ['categories'], queryFn: endpoints.categories })
  const results = useInfiniteQuery({
    queryKey: ['shop-products', debounced],
    initialPageParam: 0,
    queryFn: ({ pageParam }) => {
      const page = { skip: pageParam, limit: catalogPageSize }
      return debounced ? endpoints.searchProducts(debounced, page) : endpoints.products(page)
    },
    getNextPageParam: (lastPage, _pages, skip) => lastPage.length === catalogPageSize ? skip + catalogPageSize : undefined,
  })
  const flat = flattenCategories(categories.data || [])
  const categoryNames = new Map(flat.map(({ id, name }) => [id, name]))
  const activeCategory = flat.find(({ id }) => id === categoryId)
  const selectedIds = activeCategory ? flattenCategories([activeCategory]).map(({ id }) => id) : [categoryId]
  const found = (results.data?.pages.flat() || []).filter(({ category_id }) => !categoryId || selectedIds.includes(category_id || ''))
  const reset = () => { setSearch(''); setDebounced(''); setParams({}) }
  return <section className="page public-page catalog-page">
    <div className="public-heading"><span className="eyebrow">DEMO STOREFRONT</span><h1>Product catalog</h1><p>Explore demo products, pricing, and live stock availability.</p></div>
    <div className="catalog-controls"><label className="search"><Search size={18} aria-hidden="true" /><span className="sr-only">Search products</span><input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search products" /></label>
      {!!flat.length && <label className="category-select">Category <select value={activeCategory?.id || ''} onChange={(event) => setParams(event.target.value ? { category: event.target.value } : {})}>
        <option value="">All categories</option>{flat.map(({ id, name }) => <option key={id} value={id}>{name}</option>)}
      </select></label>}
    </div>
    {categories.isError && <p role="status">Categories are temporarily unavailable. You can still search the catalog.</p>}
    {results.isLoading ? <CatalogLoading /> : results.isError && !results.data ? <CatalogState title="Could not load the catalog" detail="Check your connection and try again." retry={() => { void results.refetch() }} /> : <>
      <p className="catalog-count" role="status">{found.length} {found.length === 1 ? 'product' : 'products'}{activeCategory ? ` in ${activeCategory.name}` : ''}{debounced ? ` matching “${debounced}”` : ''}</p>
      {found.length ? <ProductGrid products={found} categories={categoryNames} /> : <CatalogState title={debounced || categoryId ? 'No matching products' : 'The catalog is empty'} detail={results.hasNextPage ? 'Load more products to continue browsing.' : debounced || categoryId ? 'Try a different search or category.' : 'Products will appear here when they are available.'} reset={debounced || categoryId ? reset : undefined} />}
      {results.hasNextPage && <div className="catalog-pagination">
        {results.isFetchNextPageError && <p role="alert">Could not load more products. Try again.</p>}
        <button className="button-secondary" type="button" disabled={results.isFetching} onClick={() => { void results.fetchNextPage() }}>{results.isFetchingNextPage ? 'Loading products…' : 'Load more products'}</button>
      </div>}
    </>}
  </section>
}

export function ProductPage() {
  const { id = '' } = useParams()
  const categories = useQuery({ queryKey: ['categories'], queryFn: endpoints.categories })
  const query = useQuery({ queryKey: ['product', id], queryFn: () => endpoints.product(id), retry: (count, error) => !isAxiosError(error) || error.response?.status !== 404 ? count < 1 : false })
  const qc = useQueryClient(), toast = authStore((s) => s.toast), user = authStore((s) => s.user)
  const navigate = useNavigate()
  const add = useMutation({
    mutationFn: () => api.post('/api/v1/cart/items', { product_id: id, quantity: 1 }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['cart'] }); toast('Added to cart.'); if (!authStore.getState().cartOpen) authStore.getState().toggleCart() },
    onError: () => toast('Could not add this product to your cart. Please try again.', 'error'),
  })
  const product = query.data
  const categoryName = flattenCategories(categories.data || []).find((category) => category.id === product?.category_id)?.name
  return <section className="page catalog-page">
    <Link className="back" to="/shop"><ArrowLeft size={16} /> Catalog</Link>
    {query.isLoading ? <Skeleton rows={5} /> : product ? <div className="product-detail catalog-detail">
      <ProductImage product={product} category={categoryName} detail />
      <div><span className="eyebrow">PRODUCT</span><h1>{product.name}</h1><strong className="price">{money(product.price)}</strong><p>{product.description || 'Product details will appear when available.'}</p><div className="stock-line"><Stock count={product.stock_quantity} /></div>
        <button className="primary" disabled={product.stock_quantity <= 0 || add.isPending} onClick={() => user ? add.mutate() : navigate('/login', { state: { returnTo: `/product/${id}` } })}><ShoppingCart size={17} />{add.isPending ? 'Adding…' : user ? 'Add to cart' : 'Sign in to add to cart'}</button>
        <dl className="specs">{Object.entries(product.attributes || {}).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{String(value)}</dd></div>)}</dl>
      </div>
    </div> : isAxiosError(query.error) && query.error.response?.status === 404 ? <CatalogState title="Product unavailable" detail="This product may have been removed from the catalog." /> : <CatalogState title="Could not load this product" detail="Check your connection and try again." retry={() => { void query.refetch() }} />}
  </section>
}
