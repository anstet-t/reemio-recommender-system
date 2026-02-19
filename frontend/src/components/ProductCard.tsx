import type { Product } from "@/types";

const CATEGORY_EMOJI: Record<string, string> = {
  Electronics: "\u{1F4F1}",
  Clothing: "\u{1F455}",
  Home: "\u{1F3E0}",
  Sports: "\u26BD",
  Books: "\u{1F4DA}",
  Beauty: "\u{1F484}",
  Toys: "\u{1F9F8}",
  Food: "\u{1F354}",
  Furniture: "\u{1FA91}",
  Garden: "\u{1F331}",
};

function getEmoji(category: string) {
  return CATEGORY_EMOJI[category] ?? "\u{1F4E6}";
}

interface ProductCardProps {
  product: Product;
  onViewProduct?: (productId: string) => void;
  onAddToCart?: (product: Product) => void;
  onViewSimilar?: (productId: string) => void;
  showSimilarBtn?: boolean;
}

export default function ProductCard({
  product,
  onViewProduct,
  onAddToCart,
  onViewSimilar,
  showSimilarBtn = false,
}: ProductCardProps) {
  const score = Math.round(Math.max(0, Math.min(100, product.score * 100)));

  return (
    <div
      className="bg-white rounded-xl overflow-hidden shadow-md hover:shadow-xl hover:-translate-y-2 transition-all duration-300 cursor-pointer relative"
      onClick={() => onViewProduct?.(product.product_id)}
    >
      <div className="w-full h-70 bg-gradient-to-br from-gray-100 to-gray-300 flex items-center justify-center text-6xl">
        {product.image_url ? (
          <img
            src={product.image_url}
            alt={product.name}
            className="w-full h-full object-cover"
          />
        ) : (
          getEmoji(product.category)
        )}
      </div>

      <div className="absolute top-3 right-3 bg-black/75 backdrop-blur-sm text-white px-3 py-1 rounded-full text-xs font-semibold">
        {score}% match
      </div>

      <div className="p-5">
        <div className="text-primary text-xs font-semibold uppercase tracking-wide mb-2">
          {product.category}
        </div>
        <div className="text-lg font-semibold text-text-primary mb-3 line-clamp-2">
          {product.name}
        </div>
        <div className="flex justify-between items-center">
          <div className="text-2xl font-bold gradient-text">
            KES {product.price.toLocaleString()}
          </div>
          <button
            className="gradient-bg text-white px-4 py-2 rounded-lg text-sm font-semibold hover:scale-105 hover:shadow-md transition-all duration-300"
            onClick={(e) => {
              e.stopPropagation();
              onAddToCart?.(product);
            }}
          >
            Add to Cart
          </button>
        </div>
        {showSimilarBtn && (
          <button
            className="mt-2 w-full py-2 bg-bg-secondary border border-border text-primary rounded-lg text-sm font-semibold hover:bg-primary hover:text-white transition-all duration-300"
            onClick={(e) => {
              e.stopPropagation();
              onViewSimilar?.(product.product_id);
            }}
          >
            View Similar
          </button>
        )}
      </div>
    </div>
  );
}
