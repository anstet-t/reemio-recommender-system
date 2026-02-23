import type { Product } from "@/types";
import ProductCard from "./ProductCard";

interface ProductGridProps {
  products: Product[];
  loading?: boolean;
  error?: string | null;
  loadingText?: string;
  emptyText?: string;
  showSimilarBtn?: boolean;
  recommendationContext?: string;
  onViewProduct?: (product: Product, position?: number, context?: string) => void;
  onAddToCart?: (product: Product) => void;
  onViewSimilar?: (product: Product, position?: number, context?: string) => void;
}

export default function ProductGrid({
  products,
  loading = false,
  error = null,
  loadingText = "Loading...",
  emptyText = "No products available",
  showSimilarBtn = false,
  recommendationContext,
  onViewProduct,
  onAddToCart,
  onViewSimilar,
}: ProductGridProps) {
  if (loading) {
    return (
      <div className="text-center py-16 text-text-secondary text-lg">
        {loadingText}
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-16 text-red-500 text-lg">{error}</div>
    );
  }

  if (products.length === 0) {
    return (
      <div className="text-center py-16 text-text-secondary text-lg">
        {emptyText}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-6">
      {products.map((product, index) => (
        <ProductCard
          key={product.product_id}
          product={product}
          showSimilarBtn={showSimilarBtn}
          onViewProduct={(item) =>
            onViewProduct?.(item, index + 1, recommendationContext)
          }
          onAddToCart={onAddToCart}
          onViewSimilar={(item) =>
            onViewSimilar?.(item, index + 1, recommendationContext)
          }
        />
      ))}
    </div>
  );
}
