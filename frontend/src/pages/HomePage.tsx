import { useEffect, useState, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useUser } from "@/context/UserContext";
import { useCart } from "@/context/CartContext";
import { useToast } from "@/context/ToastContext";
import {
  fetchHomepage,
  fetchCartRecommendations,
  searchProducts as searchProductsApi,
  trackInteraction,
} from "@/api/client";
import type { Product } from "@/types";
import Hero from "@/components/Hero";
import SectionHeader from "@/components/SectionHeader";
import ProductGrid from "@/components/ProductGrid";
import { saveProduct } from "@/utils/productCache";

export default function HomePage() {
  const { currentUser } = useUser();
  const { items: cartItems, addToCart } = useCart();
  const { showToast } = useToast();
  const navigate = useNavigate();

  // Homepage recommendations
  const [homepage, setHomepage] = useState<Product[]>([]);
  const [homepageLoading, setHomepageLoading] = useState(true);
  const [homepageError, setHomepageError] = useState<string | null>(null);

  // Search
  const [searchResults, setSearchResults] = useState<Product[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchVisible, setSearchVisible] = useState(false);

  // Cart recommendations
  const [cartRecs, setCartRecs] = useState<Product[]>([]);
  const [cartRecsLoading, setCartRecsLoading] = useState(false);
  const [cartRecsVisible, setCartRecsVisible] = useState(false);

  const searchRef = useRef<HTMLDivElement>(null);

  // Load homepage
  const loadHomepage = useCallback(async () => {
    setHomepageLoading(true);
    setHomepageError(null);
    try {
      const data = await fetchHomepage(currentUser.id);
      setHomepage(data.recommendations);
      data.recommendations.forEach((product, index) => {
        trackInteraction({
          user_id: currentUser.id,
          product_id: product.product_id,
          interaction_type: "recommendation_view",
          recommendation_context: "homepage",
          recommendation_position: index + 1,
        });
      });
    } catch {
      setHomepageError("Error loading products. Make sure the API is running.");
    } finally {
      setHomepageLoading(false);
    }
  }, [currentUser.id]);

  useEffect(() => {
    loadHomepage();
  }, [loadHomepage]);

  // Load cart recommendations when cart changes
  useEffect(() => {
    if (cartItems.length === 0) {
      setCartRecsVisible(false);
      return;
    }

    setCartRecsVisible(true);
    setCartRecsLoading(true);
    const ids = cartItems.map((item) => item.product_id);
    fetchCartRecommendations(currentUser.id, ids)
      .then((data) => {
        setCartRecs(data.recommendations);
        data.recommendations.forEach((product, index) => {
          trackInteraction({
            user_id: currentUser.id,
            product_id: product.product_id,
            interaction_type: "recommendation_view",
            recommendation_context: "cart",
            recommendation_position: index + 1,
          });
        });
      })
      .catch(() => setCartRecs([]))
      .finally(() => setCartRecsLoading(false));
  }, [cartItems, currentUser.id]);

  const handleAddToCart = useCallback(
    (product: Product) => {
      const added = addToCart(product);
      showToast(added ? "Added to cart!" : "Item already in cart");
      if (added) {
        trackInteraction({
          user_id: currentUser.id,
          product_id: product.product_id,
          interaction_type: "cart_add",
        });
      }
    },
    [addToCart, showToast, currentUser.id]
  );

  const handleOpenProduct = useCallback(
    (product: Product, position?: number, context?: string) => {
      saveProduct(product);
      if (context) {
        trackInteraction({
          user_id: currentUser.id,
          product_id: product.product_id,
          interaction_type: "recommendation_click",
          recommendation_context: context,
          recommendation_position: position,
        });
      }
      navigate(`/product/${product.product_id}`, {
        state: { product, recContext: context, recPosition: position },
      });
    },
    [currentUser.id, navigate]
  );

  const handleSearch = useCallback(
    async (query: string) => {
      setSearchQuery(query);
      setSearchVisible(true);
      setSearchLoading(true);
      trackInteraction({
        user_id: currentUser.id,
        interaction_type: "search",
        search_query: query,
      });
      try {
        const data = await searchProductsApi(query, currentUser.id);
        setSearchResults(data.recommendations);
        data.recommendations.forEach((product, index) => {
          trackInteraction({
            user_id: currentUser.id,
            product_id: product.product_id,
            interaction_type: "recommendation_view",
            recommendation_context: "search",
            recommendation_position: index + 1,
            metadata: { resultsCount: data.recommendations.length },
          });
        });
      } catch {
        setSearchResults([]);
      } finally {
        setSearchLoading(false);
      }
      setTimeout(
        () => searchRef.current?.scrollIntoView({ behavior: "smooth" }),
        100
      );
    },
    [currentUser.id]
  );

  return (
    <main className="max-w-[1400px] mx-auto p-8 max-sm:p-4">
      <Hero onSearch={handleSearch} />

      {/* Search Results */}
      {searchVisible && (
        <section ref={searchRef} className="mb-12">
          <SectionHeader title={`Results for "${searchQuery}"`}>
            <button
              className="text-2xl px-3 py-1 bg-white border border-border rounded-lg hover:bg-red-500 hover:text-white hover:border-transparent transition-all duration-300"
              onClick={() => setSearchVisible(false)}
            >
              &times;
            </button>
          </SectionHeader>
          <ProductGrid
            products={searchResults}
            loading={searchLoading}
            loadingText="Searching..."
            emptyText="No products found. Try a different search."
            showSimilarBtn
            recommendationContext="search"
            onViewProduct={handleOpenProduct}
            onAddToCart={handleAddToCart}
            onViewSimilar={handleOpenProduct}
          />
        </section>
      )}

      {/* Popular Products */}
      <section className="mb-12">
        <SectionHeader title="Popular Products">
          <button
            className="flex items-center gap-2 px-4 py-2 bg-white border border-border rounded-lg text-sm font-medium hover:gradient-bg hover:text-white hover:border-transparent hover:-translate-y-0.5 transition-all duration-300"
            onClick={loadHomepage}
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 16 16"
              fill="currentColor"
            >
              <path d="M8 3a5 5 0 104.546 2.914.5.5 0 01.908-.417A6 6 0 118 2v1z" />
              <path d="M8 4.466V.534a.25.25 0 01.41-.192l2.36 1.966c.12.1.12.284 0 .384L8.41 4.658A.25.25 0 018 4.466z" />
            </svg>
            Refresh
          </button>
        </SectionHeader>
        <ProductGrid
          products={homepage}
          loading={homepageLoading}
          error={homepageError}
          loadingText="Loading popular products..."
          showSimilarBtn
          recommendationContext="homepage"
          onViewProduct={handleOpenProduct}
          onAddToCart={handleAddToCart}
          onViewSimilar={handleOpenProduct}
        />
      </section>

      {/* Cart Recommendations */}
      {cartRecsVisible && (
        <section className="mb-12">
          <SectionHeader title="Complete Your Order" />
          <ProductGrid
            products={cartRecs}
            loading={cartRecsLoading}
            loadingText="Loading recommendations..."
            recommendationContext="cart"
            onViewProduct={handleOpenProduct}
            onAddToCart={handleAddToCart}
          />
        </section>
      )}
    </main>
  );
}
