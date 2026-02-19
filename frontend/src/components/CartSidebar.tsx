import { useCart } from "@/context/CartContext";
import { useUser } from "@/context/UserContext";
import { useToast } from "@/context/ToastContext";
import { trackInteraction } from "@/api/client";

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

interface CartSidebarProps {
  open: boolean;
  onClose: () => void;
}

export default function CartSidebar({ open, onClose }: CartSidebarProps) {
  const { items, removeFromCart, clearCart, total } = useCart();
  const { currentUser } = useUser();
  const { showToast } = useToast();

  const handleCheckout = () => {
    if (items.length === 0) {
      showToast("Your cart is empty");
      return;
    }
    items.forEach((item) => {
      trackInteraction(currentUser.id, item.product_id, "purchase");
    });
    showToast("Order placed successfully!");
    clearCart();
    onClose();
  };

  return (
    <>
      {/* Overlay */}
      {open && (
        <div
          className="fixed inset-0 bg-black/50 backdrop-blur-sm z-[999] transition-opacity duration-300"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <div
        className={`fixed top-0 right-0 w-[400px] max-w-full h-screen bg-white shadow-xl z-[1000] flex flex-col transition-transform duration-300 ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="p-6 border-b border-border flex justify-between items-center">
          <h3 className="text-2xl font-bold">Shopping Cart</h3>
          <button
            className="text-2xl px-3 py-1 bg-white border border-border rounded-lg hover:bg-red-500 hover:text-white hover:border-transparent transition-all duration-300"
            onClick={onClose}
          >
            &times;
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          {items.length === 0 ? (
            <div className="text-center text-text-secondary py-12">
              Your cart is empty
            </div>
          ) : (
            items.map((item) => (
              <div
                key={item.product_id}
                className="flex gap-4 p-4 bg-bg-secondary rounded-lg mb-4"
              >
                <div className="w-20 h-20 rounded-lg bg-gradient-to-br from-gray-100 to-gray-300 flex items-center justify-center text-3xl shrink-0">
                  {CATEGORY_EMOJI[item.category] ?? "\u{1F4E6}"}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-semibold truncate">{item.name}</div>
                  <div className="text-xs text-text-secondary mb-2">
                    {item.category}
                  </div>
                  <div className="text-xl font-bold text-primary">
                    KES {item.price.toLocaleString()}
                  </div>
                </div>
                <button
                  className="text-red-500 text-xl self-start hover:text-red-700"
                  onClick={() => removeFromCart(item.product_id)}
                >
                  &times;
                </button>
              </div>
            ))
          )}
        </div>

        <div className="p-6 border-t border-border">
          <div className="flex justify-between text-xl font-bold mb-4">
            <span>Total:</span>
            <span>KES {total.toLocaleString()}</span>
          </div>
          <button
            className="w-full py-4 gradient-bg text-white rounded-lg font-semibold hover:-translate-y-0.5 hover:shadow-md transition-all duration-300"
            onClick={handleCheckout}
          >
            Proceed to Checkout
          </button>
        </div>
      </div>
    </>
  );
}
