const API_BASE_URL = '/api/v1';

const state = {
    currentUser: '805b5c8c-ac76-4422-803b-80151c911fd3',
    cart: [],
    selectedProduct: null
};

const elements = {
    userId: document.getElementById('userId'),
    cartBtn: document.getElementById('cartBtn'),
    cartCount: document.querySelector('.cart-count'),
    cartSidebar: document.getElementById('cartSidebar'),
    cartItems: document.getElementById('cartItems'),
    cartTotal: document.getElementById('cartTotal'),
    closeCart: document.getElementById('closeCart'),
    overlay: document.getElementById('overlay'),
    homepageProducts: document.getElementById('homepageProducts'),
    refreshHomepage: document.getElementById('refreshHomepage'),
    similarSection: document.getElementById('similarSection'),
    similarProducts: document.getElementById('similarProducts'),
    selectedProduct: document.getElementById('selectedProduct'),
    closeSimilar: document.getElementById('closeSimilar'),
    cartSection: document.getElementById('cartSection'),
    cartProducts: document.getElementById('cartProducts'),
    frequentlyBoughtSection: document.getElementById('frequentlyBoughtSection'),
    frequentlyBoughtProducts: document.getElementById('frequentlyBoughtProducts'),
    checkoutBtn: document.getElementById('checkoutBtn'),
    toast: document.getElementById('toast'),
    searchForm: document.getElementById('searchForm'),
    searchInput: document.getElementById('searchInput'),
    searchSection: document.getElementById('searchSection'),
    searchProducts: document.getElementById('searchProducts'),
    searchHeading: document.getElementById('searchHeading'),
    closeSearch: document.getElementById('closeSearch')
};

function showToast(message) {
    elements.toast.textContent = message;
    elements.toast.classList.add('show');
    setTimeout(() => {
        elements.toast.classList.remove('show');
    }, 3000);
}

function updateCartUI() {
    elements.cartCount.textContent = state.cart.length;

    if (state.cart.length === 0) {
        elements.cartItems.innerHTML = '<div class="empty-cart">Your cart is empty</div>';
        elements.cartTotal.textContent = '$0.00';
        elements.cartSection.style.display = 'none';
        return;
    }

    const total = state.cart.reduce((sum, item) => sum + item.price, 0);
    elements.cartTotal.textContent = `KES ${total.toLocaleString()}`;

    elements.cartItems.innerHTML = state.cart.map(item => `
        <div class="cart-item">
            <div class="cart-item-image">${getProductEmoji(item.category)}</div>
            <div class="cart-item-info">
                <div class="cart-item-name">${item.name}</div>
                <div class="cart-item-category">${item.category}</div>
                <div class="cart-item-price">KES ${item.price.toLocaleString()}</div>
            </div>
            <button class="remove-from-cart" onclick="removeFromCart('${item.product_id}')">×</button>
        </div>
    `).join('');

    loadCartRecommendations();
}

function addToCart(product) {
    const existingItem = state.cart.find(item => item.product_id === product.product_id);
    if (existingItem) {
        showToast('Item already in cart');
        return;
    }

    state.cart.push(product);
    updateCartUI();
    showToast('Added to cart!');

    trackInteraction(product.product_id, 'cart_add');
}

function removeFromCart(productId) {
    state.cart = state.cart.filter(item => item.product_id !== productId);
    updateCartUI();
    showToast('Removed from cart');
}

function toggleCart() {
    elements.cartSidebar.classList.toggle('open');
    elements.overlay.classList.toggle('active');
}

function getProductEmoji(category) {
    const emojis = {
        'Electronics': '📱',
        'Clothing': '👕',
        'Home': '🏠',
        'Sports': '⚽',
        'Books': '📚',
        'Beauty': '💄',
        'Toys': '🧸',
        'Food': '🍔',
        'Furniture': '🪑',
        'Garden': '🌱'
    };
    return emojis[category] || '📦';
}

function renderProduct(product, showSimilarBtn = false) {
    const scorePercentage = Math.round(Math.max(0, Math.min(100, product.score * 100)));

    return `
        <div class="product-card" onclick="viewProduct('${product.product_id}')">
            <div class="product-image">
                ${product.image_url ? `<img src="${product.image_url}" alt="${product.name}">` : getProductEmoji(product.category)}
            </div>
            <div class="product-score">
                ${scorePercentage}% match
            </div>
            <div class="product-info">
                <div class="product-category">${product.category}</div>
                <div class="product-name">${product.name}</div>
                <div class="product-footer">
                    <div class="product-price">KES ${product.price.toLocaleString()}</div>
                    <button class="add-to-cart-btn" onclick="event.stopPropagation(); addToCart(${JSON.stringify(product).replace(/"/g, '&quot;')})">
                        Add to Cart
                    </button>
                </div>
                ${showSimilarBtn ? `
                    <button class="view-similar-btn" onclick="event.stopPropagation(); loadSimilarProducts('${product.product_id}')">
                        View Similar
                    </button>
                ` : ''}
            </div>
        </div>
    `;
}

async function loadHomepageRecommendations() {
    elements.homepageProducts.innerHTML = '<div class="loading">Loading popular products...</div>';

    try {
        const response = await fetch(`${API_BASE_URL}/recommendations/homepage?user_id=${state.currentUser}&limit=12`);
        const data = await response.json();

        if (data.recommendations.length === 0) {
            elements.homepageProducts.innerHTML = '<div class="loading">No products available</div>';
            return;
        }

        elements.homepageProducts.innerHTML = data.recommendations
            .map(product => renderProduct(product, true))
            .join('');
    } catch (error) {
        console.error('Error loading products:', error);
        elements.homepageProducts.innerHTML = '<div class="loading">Error loading products. Make sure the API is running.</div>';
    }
}

async function loadSimilarProducts(productId) {
    elements.similarSection.style.display = 'block';
    elements.similarProducts.innerHTML = '<div class="loading">Loading similar products...</div>';

    try {
        const response = await fetch(`${API_BASE_URL}/recommendations/product/${productId}?user_id=${state.currentUser}&limit=8`);
        const data = await response.json();

        const productResponse = await fetch(`${API_BASE_URL}/recommendations/homepage?user_id=${state.currentUser}&limit=50`);
        const productData = await productResponse.json();
        const sourceProduct = productData.recommendations ? productData.recommendations.find(p => p.product_id === productId) : null;

        if (sourceProduct) {
            elements.selectedProduct.innerHTML = `
                <div class="selected-product-image">${getProductEmoji(sourceProduct.category)}</div>
                <div class="selected-product-info">
                    <div class="product-category">${sourceProduct.category}</div>
                    <h3>${sourceProduct.name}</h3>
                    <div class="product-price">KES ${sourceProduct.price.toLocaleString()}</div>
                </div>
            `;
        }

        elements.similarProducts.innerHTML = data.recommendations
            .map(product => renderProduct(product))
            .join('');

        elements.similarSection.scrollIntoView({ behavior: 'smooth' });

        trackInteraction(productId, 'view');
    } catch (error) {
        console.error('Error loading similar products:', error);
        elements.similarProducts.innerHTML = '<div class="loading">Error loading similar products</div>';
    }
}

async function loadCartRecommendations() {
    if (state.cart.length === 0) {
        elements.cartSection.style.display = 'none';
        return;
    }

    elements.cartSection.style.display = 'block';
    elements.cartProducts.innerHTML = '<div class="loading">Loading recommendations...</div>';

    try {
        const cartIds = state.cart.map(item => item.product_id);
        const queryParams = cartIds.map(id => `cart_product_ids=${id}`).join('&');

        const response = await fetch(`${API_BASE_URL}/recommendations/cart?user_id=${state.currentUser}&${queryParams}&limit=6`);
        const data = await response.json();

        elements.cartProducts.innerHTML = data.recommendations
            .map(product => renderProduct(product))
            .join('');
    } catch (error) {
        console.error('Error loading cart recommendations:', error);
        elements.cartProducts.innerHTML = '<div class="loading">Error loading recommendations</div>';
    }
}

async function loadFrequentlyBoughtTogether(productId) {
    elements.frequentlyBoughtSection.style.display = 'block';
    elements.frequentlyBoughtProducts.innerHTML = '<div class="loading">Loading...</div>';

    try {
        const response = await fetch(`${API_BASE_URL}/recommendations/frequently-bought-together/${productId}?limit=4`);
        const data = await response.json();

        elements.frequentlyBoughtProducts.innerHTML = data.recommendations
            .map(product => renderProduct(product))
            .join('');

        elements.frequentlyBoughtSection.scrollIntoView({ behavior: 'smooth' });
    } catch (error) {
        console.error('Error loading frequently bought together:', error);
        elements.frequentlyBoughtProducts.innerHTML = '<div class="loading">Error loading recommendations</div>';
    }
}

async function searchProducts(query) {
    elements.searchSection.style.display = 'block';
    elements.searchProducts.innerHTML = '<div class="loading">Searching...</div>';
    elements.searchHeading.textContent = `Results for "${query}"`;

    try {
        const params = new URLSearchParams({ query, limit: '12', user_id: state.currentUser });
        const response = await fetch(`${API_BASE_URL}/recommendations/search?${params}`);
        const data = await response.json();

        if (data.recommendations.length === 0) {
            elements.searchProducts.innerHTML = '<div class="loading">No products found. Try a different search.</div>';
            return;
        }

        elements.searchProducts.innerHTML = data.recommendations
            .map(product => renderProduct(product, true))
            .join('');

        elements.searchSection.scrollIntoView({ behavior: 'smooth' });
    } catch (error) {
        console.error('Error searching products:', error);
        elements.searchProducts.innerHTML = '<div class="loading">Error searching products. Make sure the API is running.</div>';
    }
}

async function trackInteraction(productId, interactionType) {
    try {
        await fetch(`${API_BASE_URL}/interactions`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user_id: state.currentUser,
                product_id: productId,
                interaction_type: interactionType
            })
        });
    } catch (error) {
        console.error('Error tracking interaction:', error);
    }
}

function viewProduct(productId) {
    loadSimilarProducts(productId);
    loadFrequentlyBoughtTogether(productId);
}

if (elements.userId) {
    elements.userId.addEventListener('change', (e) => {
        state.currentUser = e.target.value;
        loadHomepageRecommendations();
        showToast(`Switched to ${e.target.value}`);
    });
}

elements.cartBtn.addEventListener('click', toggleCart);
elements.closeCart.addEventListener('click', toggleCart);
elements.overlay.addEventListener('click', () => {
    toggleCart();
});

elements.refreshHomepage.addEventListener('click', loadHomepageRecommendations);

elements.closeSimilar.addEventListener('click', () => {
    elements.similarSection.style.display = 'none';
    elements.frequentlyBoughtSection.style.display = 'none';
});

elements.searchForm.addEventListener('submit', () => {
    const query = elements.searchInput.value.trim();
    if (query) searchProducts(query);
});

elements.closeSearch.addEventListener('click', () => {
    elements.searchSection.style.display = 'none';
    elements.searchInput.value = '';
});

elements.checkoutBtn.addEventListener('click', () => {
    if (state.cart.length === 0) {
        showToast('Your cart is empty');
        return;
    }

    state.cart.forEach(item => {
        trackInteraction(item.product_id, 'purchase');
    });

    showToast('Order placed successfully!');
    state.cart = [];
    updateCartUI();
    toggleCart();
});

loadHomepageRecommendations();
