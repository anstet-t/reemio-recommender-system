import type { Product } from "@/types";

const CACHE_KEY = "product_cache";

type ProductCache = Record<string, Product>;

function readCache(): ProductCache {
  if (typeof sessionStorage === "undefined") return {};
  try {
    const raw = sessionStorage.getItem(CACHE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as ProductCache;
    if (!parsed || typeof parsed !== "object") return {};
    return parsed;
  } catch {
    return {};
  }
}

function writeCache(cache: ProductCache) {
  if (typeof sessionStorage === "undefined") return;
  try {
    sessionStorage.setItem(CACHE_KEY, JSON.stringify(cache));
  } catch {
    // Best-effort cache; ignore failures
  }
}

export function saveProduct(product: Product) {
  const cache = readCache();
  cache[product.product_id] = product;
  writeCache(cache);
}

export function getProduct(productId: string): Product | null {
  const cache = readCache();
  return cache[productId] ?? null;
}
