import { useEffect, useState, useCallback, useRef } from "react";
import { useUser } from "@/context/UserContext";
import { useCart } from "@/context/CartContext";
import { useToast } from "@/context/ToastContext";
import {
  fetchHomepage,
  fetchSimilarProducts,
  fetchCartRecommendations,
  fetchFrequentlyBoughtTogether,
  searchProducts as searchProductsApi,
  trackInteraction,
} from "@/api/client";
import type { Product } from "@/types";
import Hero from "@/components/Hero";
import SectionHeader from "@/components/SectionHeader";
import ProductGrid from "@/components/ProductGrid";

export default function HomePage() {
  const { currentUser } = useUser();
  const { items: cartItems, addToCart } = useCart();
  const { showToast } = useToast();

  // Homepage recommendations
  const [homepage, setHomepage] = useState<Product[]>([]);
  const [homepageLoading, setHomepageLoading] = useState(true);
  const [homepageError, setHomepageError] = useState<string | null>(null);

  // Search
  const [searchResults, setSearchResults] = useState<Product[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchVisible, setSearchVisible] = useState(false);

  // Similar products
  const [similarProducts, setSimilarProducts] = useState<Product[]>([]);
  const [similarLoading, setSimilarLoading] = useState(false);
  const [similarVisible, setSimilarVisible] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);

  // Frequently bought together
  const [fbtProducts, setFbtProducts] = useState<Product[]>([]);
  const [fbtLoading, setFbtLoading] = useState(false);
  const [fbtVisible, setFbtVisible] = useState(false);

  // Cart recommendations
  const [cartRecs, setCartRecs] = useState<Product[]>([]);
  const [cartRecsLoading, setCartRecsLoading] = useState(false);
  const [cartRecsVisible, setCartRecsVisible] = useState(false);

  const similarRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLDivElement>(null);

  // Load homepage
  const loadHomepage = useCallback(async () => {
    setHomepageLoading(true);
    setHomepageError(null);
    try {
      const data = await fetchHomepage(currentUser.id);
      setHomepage(data.recommendations);
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
      .then((data) => setCartRecs(data.recommendations))
      .catch(() => setCartRecs([]))
      .finally(() => setCartRecsLoading(false));
  }, [cartItems, currentUser.id]);

  const handleAddToCart = useCallback(
    (product: Product) => {
      const added = addToCart(product);
      showToast(added ? "Added to cart!" : "Item already in cart");
      if (added) {
        trackInteraction(currentUser.id, product.product_id, "cart_add");
      }
    },
    [addToCart, showToast, currentUser.id]
  );

  const handleViewProduct = useCallback(
    async (productId: string) => {
      // Find product from current data for display
      const allProducts = [...homepage, ...searchResults];
      const source = allProducts.find((p) => p.product_id === productId);
      if (source) setSelectedProduct(source);

      // Load similar products
      setSimilarVisible(true);
      setSimilarLoading(true);
      try {
        const data = await fetchSimilarProducts(productId, currentUser.id);
        setSimilarProducts(data.recommendations);
        trackInteraction(currentUser.id, productId, "view");
      } catch {
        setSimilarProducts([]);
      } finally {
        setSimilarLoading(false);
      }

      // Load frequently bought together
      setFbtVisible(true);
      setFbtLoading(true);
      try {
        const data = await fetchFrequentlyBoughtTogether(productId);
        setFbtProducts(data.recommendations);
      } catch {
        setFbtProducts([]);
      } finally {
        setFbtLoading(false);
      }

      setTimeout(
        () => similarRef.current?.scrollIntoView({ behavior: "smooth" }),
        100
      );
    },
    [currentUser.id, homepage, searchResults]
  );

  const handleSearch = useCallback(
    async (query: string) => {
      setSearchQuery(query);
      setSearchVisible(true);
      setSearchLoading(true);
      try {
        const data = await searchProductsApi(query, currentUser.id);
        setSearchResults(data.recommendations);
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
            onViewProduct={handleViewProduct}
            onAddToCart={handleAddToCart}
            onViewSimilar={handleViewProduct}
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
          onViewProduct={handleViewProduct}
          onAddToCart={handleAddToCart}
          onViewSimilar={handleViewProduct}
        />
      </section>

      {/* Similar Products */}
      {similarVisible && (
        <section ref={similarRef} className="mb-12">
          <SectionHeader title="Similar Products">
            <button
              className="text-2xl px-3 py-1 bg-white border border-border rounded-lg hover:bg-red-500 hover:text-white hover:border-transparent transition-all duration-300"
              onClick={() => {
                setSimilarVisible(false);
                setFbtVisible(false);
              }}
            >
              &times;
            </button>
          </SectionHeader>

          {selectedProduct && (
            <div className="bg-white rounded-xl p-6 mb-6 shadow-md flex items-center gap-6">
              <div className="w-[120px] h-[120px] rounded-lg bg-gradient-to-br from-gray-100 to-gray-300 flex items-center justify-center text-5xl shrink-0">
                {CATEGORY_EMOJI[selectedProduct.category] ?? "\u{1F4E6}"}
              </div>
              <div>
                <div className="text-primary text-xs font-semibold uppercase tracking-wide mb-1">
                  {selectedProduct.category}
                </div>
                <h3 className="text-2xl font-bold mb-2">
                  {selectedProduct.name}
                </h3>
                <div className="text-xl font-bold gradient-text">
                  KES {selectedProduct.price.toLocaleString()}
                </div>
              </div>
            </div>
          )}

          <ProductGrid
            products={similarProducts}
            loading={similarLoading}
            loadingText="Loading similar products..."
            onViewProduct={handleViewProduct}
            onAddToCart={handleAddToCart}
          />
        </section>
      )}

      {/* Cart Recommendations */}
      {cartRecsVisible && (
        <section className="mb-12">
          <SectionHeader title="Complete Your Order" />
          <ProductGrid
            products={cartRecs}
            loading={cartRecsLoading}
            loadingText="Loading recommendations..."
            onViewProduct={handleViewProduct}
            onAddToCart={handleAddToCart}
          />
        </section>
      )}

      {/* Frequently Bought Together */}
      {fbtVisible && (
        <section className="mb-12">
          <SectionHeader title="Frequently Bought Together" />
          <ProductGrid
            products={fbtProducts}
            loading={fbtLoading}
            loadingText="Loading..."
            onViewProduct={handleViewProduct}
            onAddToCart={handleAddToCart}
          />
        </section>
      )}
    </main>
  );
}
