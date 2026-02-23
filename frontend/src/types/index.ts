export interface Product {
  product_id: string;
  name: string;
  category: string;
  price: number;
  score: number;
  image_url?: string;
}

export interface RecommendationResponse {
  recommendations: Product[];
  request_id: string;
  context: string;
  user_id: string;
  generated_at: string;
}

export interface User {
  id: string;
  name: string;
}

export const USERS: User[] = [
  { id: "e2870a70-c59d-402c-9bbc-cc5d1c155782", name: "Mwende Kavuu" },
  { id: "b8355b11-784f-467b-b611-216fdb6dcd91", name: "Otieno Ochieng" },
  { id: "69b2bf41-1e9f-4753-95c8-43788297e692", name: "Akinyi Adhiambo" },
  { id: "f2de971c-12dd-4394-8557-87160be804d4", name: "Kipchoge Korir" },
  { id: "ea4b669f-04f5-493b-94ba-f0a9dcb4ce43", name: "Nyambura Wangari" },
  { id: "c36fa92e-61f7-4e92-ab2a-7636f87dfa65", name: "Omondi Onyango" },
];
