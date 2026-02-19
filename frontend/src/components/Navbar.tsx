import { useState } from "react";
import { useUser } from "@/context/UserContext";
import { useCart } from "@/context/CartContext";
import { USERS } from "@/types";
import CartSidebar from "./CartSidebar";

export default function Navbar() {
  const { currentUser, setCurrentUser } = useUser();
  const { items } = useCart();
  const [cartOpen, setCartOpen] = useState(false);

  return (
    <>
      <nav className="bg-white border-b border-border sticky top-0 z-100 shadow-sm">
        <div className="max-w-[1400px] mx-auto px-8 py-4 flex justify-between items-center max-sm:px-4">
          <div className="flex items-center gap-3 text-2xl font-bold gradient-text">
            <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
              <rect width="32" height="32" rx="8" fill="url(#gradient)" />
              <path
                d="M10 12L16 8L22 12V20L16 24L10 20V12Z"
                stroke="white"
                strokeWidth="2"
                fill="none"
              />
              <defs>
                <linearGradient
                  id="gradient"
                  x1="0"
                  y1="0"
                  x2="32"
                  y2="32"
                >
                  <stop offset="0%" stopColor="#667eea" />
                  <stop offset="100%" stopColor="#764ba2" />
                </linearGradient>
              </defs>
            </svg>
            <span>Reemio</span>
          </div>

          <div className="flex items-center gap-6">
            <a
              href="/docs"
              target="_blank"
              rel="noopener noreferrer"
              className="px-4 py-2 bg-bg-secondary border border-border rounded-lg text-text-primary text-sm font-medium hover:gradient-bg hover:text-white hover:border-transparent hover:-translate-y-0.5 transition-all duration-300 no-underline"
            >
              API Docs
            </a>

            <div className="flex items-center gap-2">
              <label
                htmlFor="userId"
                className="text-text-secondary text-sm font-medium"
              >
                User:
              </label>
              <select
                id="userId"
                value={currentUser.id}
                onChange={(e) => {
                  const user = USERS.find((u) => u.id === e.target.value);
                  if (user) setCurrentUser(user);
                }}
                className="px-4 py-2 border border-border rounded-lg bg-white text-text-primary text-sm cursor-pointer hover:border-primary transition-all duration-300"
              >
                {USERS.map((user) => (
                  <option key={user.id} value={user.id}>
                    {user.name}
                  </option>
                ))}
              </select>
            </div>

            <button
              className="relative p-3 bg-bg-secondary rounded-lg hover:gradient-bg hover:text-white hover:-translate-y-0.5 transition-all duration-300"
              onClick={() => setCartOpen(true)}
            >
              <svg
                width="20"
                height="20"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path d="M3 1a1 1 0 000 2h1.22l.305 1.222a.997.997 0 00.01.042l1.358 5.43-.893.892C3.74 11.846 4.632 14 6.414 14H15a1 1 0 000-2H6.414l1-1H14a1 1 0 00.894-.553l3-6A1 1 0 0017 3H6.28l-.31-1.243A1 1 0 005 1H3zM16 16.5a1.5 1.5 0 11-3 0 1.5 1.5 0 013 0zM6.5 18a1.5 1.5 0 100-3 1.5 1.5 0 000 3z" />
              </svg>
              <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs font-semibold px-1.5 py-0.5 rounded-full min-w-[20px] text-center">
                {items.length}
              </span>
            </button>
          </div>
        </div>
      </nav>

      <CartSidebar open={cartOpen} onClose={() => setCartOpen(false)} />
    </>
  );
}
