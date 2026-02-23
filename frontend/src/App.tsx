import { BrowserRouter, Routes, Route } from "react-router-dom";
import { UserProvider } from "@/context/UserContext";
import { CartProvider } from "@/context/CartContext";
import { ToastProvider } from "@/context/ToastContext";
import Navbar from "@/components/Navbar";
import Toast from "@/components/Toast";
import HomePage from "@/pages/HomePage";
import ProductPage from "@/pages/ProductPage";

export default function App() {
  return (
    <BrowserRouter>
      <UserProvider>
        <CartProvider>
          <ToastProvider>
            <Navbar />
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/product/:id" element={<ProductPage />} />
            </Routes>
            <Toast />
          </ToastProvider>
        </CartProvider>
      </UserProvider>
    </BrowserRouter>
  );
}
