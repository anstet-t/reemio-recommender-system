import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { useUser } from "@/context/UserContext";
import { useCart } from "@/context/CartContext";
import { useToast } from "@/context/ToastContext";
import {
  fetchSimilarProducts,
  fetchFrequentlyBoughtTogether,
  trackInteraction,
} from "@/api/client";
import type { Product } from "@/types";
import SectionHeader from "@/components/SectionHeader";
import ProductGrid from "@/components/ProductGrid";
import { getProduct, saveProduct } from "@/utils/productCache";

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

export default function ProductPage() {
  const { currentUser } = useUser();
  const { addToCart } = useCart();
  const { showToast } = useToast();
  const navigate = useNavigate();
  const { id: productId } = useParams();
  const location = useLocation();

  const [similarProducts, setSimilarProducts] = useState<Product[]>([]);
  const [similarLoading, setSimilarLoading] = useState(false);
  const [fbtProducts, setFbtProducts] = useState<Product[]>([]);
  const [fbtLoading, setFbtLoading] = useState(false);

  const product = useMemo(() => {
    const fromState = (location.state as { product?: Product } | null)?.product;
    if (fromState) return fromState;
    if (productId) return getProduct(productId);
    return null;
  }, [location.state, productId]);

  useEffect(() => {
    if (product) saveProduct(product);
  }, [product]);

  useEffect(() => {
    if (!productId) return;
    trackInteraction(currentUser.id, productId, "view");
  }, [currentUser.id, productId]);

  useEffect(() => {
    if (!productId) return;
    setSimilarLoading(true);
    fetchSimilarProducts(productId, currentUser.id)
      .then((data) => setSimilarProducts(data.recommendations))
      .catch(() => setSimilarProducts([]))
      .finally(() => setSimilarLoading(false));
  }, [currentUser.id, productId]);

  useEffect(() => {
    if (!productId) return;
    setFbtLoading(true);
    fetchFrequentlyBoughtTogether(productId)
      .then((data) => setFbtProducts(data.recommendations))
      .catch(() => setFbtProducts([]))
      .finally(() => setFbtLoading(false));
  }, [productId]);

  const handleAddToCart = useCallback(
    (item: Product) => {
      const added = addToCart(item);
      showToast(added ? "Added to cart!" : "Item already in cart");
      if (added) {
        trackInteraction(currentUser.id, item.product_id, "cart_add");
      }
    },
    [addToCart, showToast, currentUser.id]
  );

  const handleOpenProduct = useCallback(
    (item: Product) => {
      saveProduct(item);
      navigate(`/product/${item.product_id}`, { state: { product: item } });
    },
    [navigate]
  );

  if (!productId || !product) {
    return (
      <main className="max-w-[1200px] mx-auto p-8 max-sm:p-4">
        <div className="bg-white rounded-xl p-8 shadow-md text-center">
          <h2 className="text-2xl font-bold mb-2">Product not found</h2>
          <p className="text-text-secondary mb-6">
            We couldn’t load this product. Try going back to the homepage.
          </p>
          <button
            className="gradient-bg text-white px-6 py-3 rounded-lg text-sm font-semibold hover:scale-105 hover:shadow-md transition-all duration-300"
            onClick={() => navigate("/")}
          >
            Back to home
          </button>
        </div>
      </main>
    );
  }

  const score = Math.round(Math.max(0, Math.min(100, product.score * 100)));

  return (
    <main className="max-w-[1400px] mx-auto p-8 max-sm:p-4">
      <section className="mb-12">
        <div className="bg-white rounded-2xl p-8 shadow-md flex flex-col lg:flex-row gap-8 items-center">
          <div className="w-full lg:w-[340px] h-[260px] rounded-2xl bg-gradient-to-br from-gray-100 to-gray-300 flex items-center justify-center text-7xl shrink-0 overflow-hidden">
            {product.image_url ? (
              <img
                src={product.image_url}
                alt={product.name}
                className="w-full h-full object-cover"
              />
            ) : (
              CATEGORY_EMOJI[product.category] ?? "\u{1F4E6}"
            )}
          </div>
          <div className="w-full">
            <div className="text-primary text-xs font-semibold uppercase tracking-wide mb-2">
              {product.category}
            </div>
            <h1 className="text-3xl font-bold mb-3">{product.name}</h1>
            <div className="flex items-center gap-3 mb-6">
              <div className="text-3xl font-bold gradient-text">
                KES {product.price.toLocaleString()}
              </div>
              <span className="text-sm px-3 py-1 rounded-full bg-black/10 text-text-secondary">
                {score}% match
              </span>
            </div>
            <div className="flex flex-wrap gap-3">
              <button
                className="gradient-bg text-white px-6 py-3 rounded-lg text-sm font-semibold hover:scale-105 hover:shadow-md transition-all duration-300"
                onClick={() => handleAddToCart(product)}
              >
                Add to Cart
              </button>
              <button
                className="px-6 py-3 rounded-lg text-sm font-semibold border border-border text-primary hover:bg-primary hover:text-white transition-all duration-300"
                onClick={() => navigate("/")}
              >
                Back to home
              </button>
            </div>
          </div>
        </div>
      </section>

      <section className="mb-12">
        <SectionHeader title="Similar Products" />
        <ProductGrid
          products={similarProducts}
          loading={similarLoading}
          loadingText="Loading similar products..."
          onViewProduct={handleOpenProduct}
          onAddToCart={handleAddToCart}
        />
      </section>

      <section className="mb-12">
        <SectionHeader title="Frequently Bought Together" />
        <ProductGrid
          products={fbtProducts}
          loading={fbtLoading}
          loadingText="Loading..."
          onViewProduct={handleOpenProduct}
          onAddToCart={handleAddToCart}
        />
      </section>
    </main>
  );
}
