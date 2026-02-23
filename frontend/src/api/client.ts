import type { RecommendationResponse } from "@/types";
import { getSessionId } from "@/utils/sessionId";

const API_BASE = "/api/v1";

export async function fetchHomepage(
  userId: string,
  limit = 12
): Promise<RecommendationResponse> {
  const res = await fetch(
    `${API_BASE}/recommendations/homepage?user_id=${userId}&limit=${limit}`
  );
  if (!res.ok) throw new Error("Failed to load homepage recommendations");
  return res.json();
}

export async function fetchSimilarProducts(
  productId: string,
  userId: string,
  limit = 8
): Promise<RecommendationResponse> {
  const res = await fetch(
    `${API_BASE}/recommendations/product/${productId}?user_id=${userId}&limit=${limit}`
  );
  if (!res.ok) throw new Error("Failed to load similar products");
  return res.json();
}

export async function fetchCartRecommendations(
  userId: string,
  cartProductIds: string[],
  limit = 6
): Promise<RecommendationResponse> {
  const params = cartProductIds.map((id) => `cart_product_ids=${id}`).join("&");
  const res = await fetch(
    `${API_BASE}/recommendations/cart?user_id=${userId}&${params}&limit=${limit}`
  );
  if (!res.ok) throw new Error("Failed to load cart recommendations");
  return res.json();
}

export async function fetchFrequentlyBoughtTogether(
  productId: string,
  limit = 4
): Promise<RecommendationResponse> {
  const res = await fetch(
    `${API_BASE}/recommendations/frequently-bought-together/${productId}?limit=${limit}`
  );
  if (!res.ok) throw new Error("Failed to load frequently bought together");
  return res.json();
}

export async function searchProducts(
  query: string,
  userId: string,
  limit = 12
): Promise<RecommendationResponse> {
  const params = new URLSearchParams({
    query,
    limit: String(limit),
    user_id: userId,
  });
  const res = await fetch(`${API_BASE}/recommendations/search?${params}`);
  if (!res.ok) throw new Error("Failed to search products");
  return res.json();
}

export type InteractionType =
  | "view"
  | "cart_add"
  | "cart_remove"
  | "purchase"
  | "wishlist_add"
  | "search"
  | "recommendation_click"
  | "recommendation_view";

export interface TrackInteractionPayload {
  user_id: string;
  product_id?: string;
  interaction_type: InteractionType;
  search_query?: string;
  recommendation_context?: string;
  recommendation_position?: number;
  session_id?: string;
  metadata?: Record<string, unknown>;
}

export async function trackInteraction(
  payload: TrackInteractionPayload
): Promise<void> {
  try {
    const sessionId = payload.session_id ?? getSessionId();
    await fetch(`${API_BASE}/interactions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...payload,
        session_id: sessionId,
      }),
    });
  } catch {
    console.error("Failed to track interaction");
  }
}
