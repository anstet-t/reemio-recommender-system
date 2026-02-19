import { useState, type FormEvent } from "react";

interface HeroProps {
  onSearch: (query: string) => void;
}

export default function Hero({ onSearch }: HeroProps) {
  const [query, setQuery] = useState("");

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = query.trim();
    if (trimmed) onSearch(trimmed);
  };

  return (
    <section className="gradient-bg rounded-xl p-16 text-center mb-12 shadow-xl max-sm:p-8">
      <h1 className="text-white text-5xl font-extrabold mb-4 leading-tight max-sm:text-3xl">
        Discover Products Made for You
      </h1>
      <p className="text-white/90 text-xl mb-8 max-sm:text-base">
        Personalized recommendations powered by AI
      </p>
      <form
        onSubmit={handleSubmit}
        className="flex items-center max-w-[600px] mx-auto bg-white rounded-full pl-5 pr-2 py-2 shadow-lg"
      >
        <svg
          className="text-text-secondary shrink-0"
          width="20"
          height="20"
          viewBox="0 0 20 20"
          fill="currentColor"
        >
          <path
            fillRule="evenodd"
            d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z"
            clipRule="evenodd"
          />
        </svg>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search products... e.g. Fridge, Notebook, Sugar"
          className="flex-1 border-none outline-none px-3 py-3 text-base bg-transparent text-text-primary min-w-0"
          autoComplete="off"
        />
        <button
          type="submit"
          className="gradient-bg text-white px-6 py-3 rounded-full text-sm font-semibold hover:scale-105 hover:shadow-md transition-all duration-300 whitespace-nowrap"
        >
          Search
        </button>
      </form>
    </section>
  );
}
