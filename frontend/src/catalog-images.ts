import type { Product } from './lib'

export const featured = [
  { name: 'Zenith Earbuds Premium', image: 'earbuds', alt: 'Wireless earbuds in an open charging case', size: 600 },
  { name: 'Nexus Monitor Ultra', image: 'monitor', alt: 'Desktop monitor on a stand', size: 600 },
  { name: 'Nexus Keyboard Classic', image: 'keyboard', alt: 'Compact mechanical keyboard', size: 600 },
  { name: 'Quantum Mouse Plus', image: 'mouse', alt: 'Wireless ergonomic mouse', size: 600 },
]

// The public demo catalog is seeded with these brands, product types, and model names.
const demoBrands = ['Alpha', 'Quantum', 'Nexus', 'Zenith', 'Apex', 'Nova', 'Vortex', 'Horizon', 'Pinnacle', 'Aura']
const demoModels = ['Premium', 'Pro', 'Max', 'Ultra', 'Lite', 'Plus', 'Advanced', 'Elite', 'Essential', 'Classic']
const demoCategories = [
  { name: 'Electronics', folder: 'electronics', types: ['Smartphone', 'Tablet', 'Laptop', 'Smartwatch', 'Headphones', 'Speaker'] },
  { name: "Men's Clothing", folder: 'mens', types: ['T-Shirt', 'Jeans', 'Jacket', 'Sweater', 'Hoodie', 'Shorts', 'Polo Shirt', 'Formal Shirt', 'Chinos', 'Track Pants'] },
  { name: "Women's Clothing", folder: 'womens', types: ['Dress', 'Top', 'Jeans', 'Skirt', 'Sweater', 'Jacket', 'Activewear', 'T-Shirt', 'Blouse', 'Leggings'] },
  { name: 'Home & Kitchen', folder: 'home', types: ['Coffee Maker', 'Blender', 'Toaster', 'Microwave', 'Air Fryer', 'Cookware Set', 'Cutlery Set', 'Dinnerware', 'Vacuum Cleaner', 'Iron'] },
  { name: 'Sports & Outdoors', folder: 'sports', types: ['Yoga Mat', 'Dumbbells', 'Resistance Bands', 'Jump Rope', 'Water Bottle', 'Tent', 'Sleeping Bag', 'Backpack', 'Treadmill', 'Exercise Bike'] },
  { name: 'Books', folder: 'books', types: ['Fiction Novel', 'Non-Fiction', 'Sci-Fi', 'Fantasy', 'Mystery', 'Biography', 'Self-Help', 'Cookbook', 'History', 'Business'] },
  { name: 'Health & Personal Care', folder: 'health', types: ['Shampoo', 'Conditioner', 'Body Wash', 'Toothpaste', 'Toothbrush', 'Deodorant', 'Moisturizer', 'Sunscreen', 'Vitamins', 'Protein Powder'] },
  { name: 'Toys & Games', folder: 'toys', types: ['Board Game', 'Puzzle', 'Action Figure', 'Doll', 'Building Blocks', 'Remote Control Car', 'Stuffed Animal', 'Card Game', 'Educational Toy', 'Video Game'] },
  { name: 'Automotive', folder: 'auto', types: ['Car Wash Soap', 'Wax', 'Tire Inflator', 'Jump Starter', 'Dash Cam', 'Phone Mount', 'Floor Mats', 'Seat Covers', 'Air Freshener', 'Wiper Blades'] },
  { name: 'Beauty', folder: 'beauty', types: ['Lipstick', 'Foundation', 'Mascara', 'Eyeshadow Palette', 'Eyeliner', 'Blush', 'Highlighter', 'Makeup Brushes', 'Perfume', 'Nail Polish'] },
]

export function demoProductImage(product: Product, category?: string) {
  const selected = featured.find(({ name }) => product.name === name)
  if (selected) return selected

  const [brand, ...description] = product.name.split(' ')
  const model = description.pop()
  if (product.attributes?.brand !== brand || !demoBrands.includes(brand) || !model || !demoModels.includes(model)) return
  const type = description.join(' ')
  const matching = demoCategories.filter((group) => group.types.includes(type) && (!category || group.name === category))
  if (matching.length !== 1) return
  return { image: `${matching[0].folder}/${type.toLowerCase().replace(/ /g, '-')}`, alt: `Illustration of ${type.toLowerCase()}`, size: 360 }
}
