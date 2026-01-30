// Инициализация Telegram Web App
const tg = window.Telegram.WebApp;
tg.expand();
tg.BackButton.hide();

// Глобальные переменные
let cart = JSON.parse(localStorage.getItem('cart')) || [];
let products = [];
let currentCategory = 'all';
let currentFilter = 'all';
let userData = null;

// Инициализация приложения
document.addEventListener('DOMContentLoaded', async function() {
    // Загрузка данных
    await loadUserData();
    await loadProducts();
    await loadCategories();

    // Инициализация интерфейса
    initUI();
    updateCart();

    // Показать приветственное сообщение
    showNotification('Добро пожаловать в Coffee Bliss! ☕', 'success');
});

// Загрузка данных пользователя
async function loadUserData() {
    try {
        // Получаем данные пользователя из Telegram
        userData = {
            id: tg.initDataUnsafe.user?.id,
            firstName: tg.initDataUnsafe.user?.first_name,
            lastName: tg.initDataUnsafe.user?.last_name,
            username: tg.initDataUnsafe.user?.username,
            photoUrl: tg.initDataUnsafe.user?.photo_url
        };

        // Загружаем дополнительные данные с сервера
        const response = await fetch('/api/user/profile', {
            headers: {
                'X-Telegram-Init-Data': tg.initData
            }
        });

        if (response.ok) {
            const data = await response.json();
            userData = { ...userData, ...data };
        }

        // Сохраняем в localStorage
        localStorage.setItem('userData', JSON.stringify(userData));

    } catch (error) {
        console.error('Ошибка загрузки данных пользователя:', error);
    }
}

// Загрузка товаров
async function loadProducts() {
    try {
        showLoading(true);

        const response = await fetch('/api/menu');
        if (!response.ok) throw new Error('Ошибка загрузки меню');

        products = await response.json();
        renderProducts();

    } catch (error) {
        console.error('Ошибка загрузки товаров:', error);
        showNotification('Ошибка загрузки меню', 'error');
        // Используем тестовые данные
        products = getSampleProducts();
        renderProducts();
    } finally {
        showLoading(false);
    }
}

// Загрузка категорий
async function loadCategories() {
    try {
        const response = await fetch('/api/menu/categories');
        if (response.ok) {
            const categories = await response.json();
            updateCategoryFilters(categories);
        }
    } catch (error) {
        console.error('Ошибка загрузки категорий:', error);
    }
}

// Инициализация UI
function initUI() {
    // Боковое меню
    const menuBtn = document.getElementById('menu-btn');
    const closeBtn = document.getElementById('close-btn');
    const sidebar = document.getElementById('sidebar');

    menuBtn.addEventListener('click', () => {
        sidebar.classList.add('active');
    });

    closeBtn.addEventListener('click', () => {
        sidebar.classList.remove('active');
    });

    // Навигация по категориям
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        item.addEventListener('click', function(e) {
            e.preventDefault();
            const category = this.dataset.category;

            if (category) {
                setActiveCategory(category);
                sidebar.classList.remove('active');
            }
        });
    });

    // Фильтры
    const filterTags = document.querySelectorAll('.filter-tag');
    filterTags.forEach(tag => {
        tag.addEventListener('click', function() {
            setActiveFilter(this.dataset.filter);
        });
    });

    // Поиск
    const searchInput = document.getElementById('search-input');
    const clearSearch = document.getElementById('clear-search');

    searchInput.addEventListener('input', debounce(function() {
        filterProducts();
    }, 300));

    clearSearch.addEventListener('click', function() {
        searchInput.value = '';
        filterProducts();
    });

    // Корзина
    const cartBtn = document.getElementById('cart-btn');
    const closeCart = document.getElementById('close-cart');
    const cartModal = document.getElementById('cart-modal');
    const floatingCheckout = document.getElementById('floating-checkout');
    const checkoutBtn = document.getElementById('checkout-btn');
    const clearCartBtn = document.getElementById('clear-cart');

    cartBtn.addEventListener('click', () => {
        cartModal.style.display = 'flex';
        renderCart();
    });

    closeCart.addEventListener('click', () => {
        cartModal.style.display = 'none';
    });

    floatingCheckout.addEventListener('click', () => {
        cartModal.style.display = 'flex';
        renderCart();
    });

    checkoutBtn.addEventListener('click', () => {
        if (cart.length === 0) {
            showNotification('Добавьте товары в корзину', 'warning');
            return;
        }
        window.location.href = 'checkout.html';
    });

    clearCartBtn.addEventListener('click', () => {
        if (cart.length === 0) return;

        if (confirm('Очистить корзину?')) {
            cart = [];
            saveCart();
            updateCart();
            renderProducts();
            cartModal.style.display = 'none';
            showNotification('Корзина очищена', 'success');
        }
    });

    // Закрытие модалок при клике вне
    document.addEventListener('click', function(e) {
        if (e.target === cartModal) {
            cartModal.style.display = 'none';
        }
    });

    // Обновление интервала времени
    updateTimeInfo();
    setInterval(updateTimeInfo, 60000); // Каждую минуту
}

// Установка активной категории
function setActiveCategory(category) {
    currentCategory = category;

    // Обновляем активный элемент в навигации
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
        if (item.dataset.category === category) {
            item.classList.add('active');
        }
    });

    // Фильтруем товары
    filterProducts();
}

// Установка активного фильтра
function setActiveFilter(filter) {
    currentFilter = filter;

    // Обновляем активный фильтр
    document.querySelectorAll('.filter-tag').forEach(tag => {
        tag.classList.remove('active');
        if (tag.dataset.filter === filter) {
            tag.classList.add('active');
        }
    });

    // Фильтруем товары
    filterProducts();
}

// Фильтрация товаров
function filterProducts() {
    const searchTerm = document.getElementById('search-input').value.toLowerCase();

    let filtered = products;

    // Фильтр по категории
    if (currentCategory !== 'all') {
        filtered = filtered.filter(product =>
            product.category_name === currentCategory ||
            product.category === currentCategory
        );
    }

    // Фильтр по поиску
    if (searchTerm) {
        filtered = filtered.filter(product =>
            product.name.toLowerCase().includes(searchTerm) ||
            product.description?.toLowerCase().includes(searchTerm)
        );
    }

    // Фильтр по типу
    if (currentFilter !== 'all') {
        switch (currentFilter) {
            case 'popular':
                filtered = filtered.filter(p => p.popular);
                break;
            case 'new':
                filtered = filtered.filter(p => p.new);
                break;
            case 'discount':
                filtered = filtered.filter(p => p.discount_price);
                break;
        }
    }

    renderProducts(filtered);
}

// Рендеринг товаров
function renderProducts(productsToRender = products) {
    const container = document.getElementById('products-grid');

    if (productsToRender.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-search"></i>
                <h3>Товары не найдены</h3>
                <p>Попробуйте изменить поисковый запрос или выберите другую категорию</p>
            </div>
        `;
        return;
    }

    container.innerHTML = productsToRender.map(product => `
        <div class="product-card" data-id="${product.id}">
            <div class="product-image">
                ${product.image_url ? `
                    <img src="${product.image_url}" alt="${product.name}" loading="lazy">
                ` : `
                    <div style="display: flex; align-items: center; justify-content: center; height: 100%; color: white;">
                        <i class="fas fa-coffee fa-2x"></i>
                    </div>
                `}
                ${product.discount_price ? `
                    <div class="product-badge">-${Math.round((1 - product.discount_price / product.price) * 100)}%</div>
                ` : ''}
                ${product.new ? `
                    <div class="product-badge" style="background: var(--success);">NEW</div>
                ` : ''}
            </div>
            <div class="product-content">
                <div class="product-header">
                    <h3 class="product-title">${product.name}</h3>
                    <div class="product-price">
                        ${product.discount_price ? `
                            <span style="color: var(--error); text-decoration: line-through; font-size: 12px; margin-right: 4px;">
                                ${product.price}₽
                            </span>
                            <span>${product.discount_price}₽</span>
                        ` : `${product.price}₽`}
                    </div>
                </div>
                <p class="product-description">${product.description || 'Вкусный напиток'}</p>
                <div class="product-actions">
                    ${getProductControls(product)}
                </div>
            </div>
        </div>
    `).join('');

    // Добавляем обработчики событий для кнопок
    container.querySelectorAll('.add-to-cart-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const productId = parseInt(this.closest('.product-card').dataset.id);
            addToCart(productId);
        });
    });

    container.querySelectorAll('.quantity-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const productId = parseInt(this.closest('.product-card').dataset.id);
            const action = this.classList.contains('increase') ? 1 : -1;
            updateQuantity(productId, action);
        });
    });
}

// Получение контролов для товара
function getProductControls(product) {
    const cartItem = cart.find(item => item.id === product.id);
    const quantity = cartItem ? cartItem.quantity : 0;
    const price = product.discount_price || product.price;

    if (quantity === 0) {
        return `
            <button class="add-to-cart-btn">
                <i class="fas fa-plus"></i>
                Добавить
            </button>
        `;
    }

    return `
        <div class="quantity-controls">
            <button class="quantity-btn decrease" ${quantity === 1 ? 'disabled' : ''}>
                <i class="fas fa-minus"></i>
            </button>
            <span class="quantity-display">${quantity}</span>
            <button class="quantity-btn increase">
                <i class="fas fa-plus"></i>
            </button>
        </div>
        <div style="font-weight: 600; color: var(--primary);">
            ${price * quantity}₽
        </div>
    `;
}

// Добавление в корзину
function addToCart(productId) {
    const product = products.find(p => p.id === productId);
    if (!product) return;

    const price = product.discount_price || product.price;
    const existingItem = cart.find(item => item.id === productId);

    if (existingItem) {
        existingItem.quantity += 1;
    } else {
        cart.push({
            id: product.id,
            name: product.name,
            price: price,
            quantity: 1,
            image: product.image_url,
            originalPrice: product.price
        });
    }

    saveCart();
    updateCart();
    renderProducts();

    showNotification(`${product.name} добавлен в корзину`, 'success');
}

// Обновление количества
function updateQuantity(productId, delta) {
    const itemIndex = cart.findIndex(item => item.id === productId);

    if (itemIndex !== -1) {
        cart[itemIndex].quantity += delta;

        if (cart[itemIndex].quantity <= 0) {
            cart.splice(itemIndex, 1);
        }

        saveCart();
        updateCart();
        renderProducts();

        // Обновляем корзину если она открыта
        if (document.getElementById('cart-modal').style.display === 'flex') {
            renderCart();
        }
    }
}

// Сохранение корзины
function saveCart() {
    localStorage.setItem('cart', JSON.stringify(cart));
}

// Обновление отображения корзины
function updateCart() {
    const totalItems = cart.reduce((sum, item) => sum + item.quantity, 0);
    const totalPrice = cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);

    // Обновляем счетчики
    document.getElementById('cart-count').textContent = totalItems;
    document.getElementById('floating-count').textContent = totalItems;
    document.getElementById('floating-total').textContent = totalPrice;

    // Обновляем плавающую кнопку
    const floatingBtn = document.getElementById('floating-checkout');
    floatingBtn.disabled = totalItems === 0;
    floatingBtn.style.opacity = totalItems === 0 ? '0.5' : '1';
}

// Рендеринг корзины
function renderCart() {
    const container = document.getElementById('cart-body');
    const subtotal = cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
    const deliveryFee = subtotal >= 500 ? 0 : 150;
    const total = subtotal + deliveryFee;

    if (cart.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-shopping-cart"></i>
                <h3>Корзина пуста</h3>
                <p>Добавьте товары из меню</p>
            </div>
        `;
    } else {
        container.innerHTML = cart.map(item => `
            <div class="cart-item" data-id="${item.id}">
                <div class="cart-item-image">
                    ${item.image ? `
                        <img src="${item.image}" alt="${item.name}">
                    ` : `
                        <div style="display: flex; align-items: center; justify-content: center; height: 100%; color: white; background: var(--primary);">
                            <i class="fas fa-coffee"></i>
                        </div>
                    `}
                </div>
                <div class="cart-item-info">
                    <h4 class="cart-item-title">${item.name}</h4>
                    <div class="cart-item-price">${item.price}₽ × ${item.quantity} = ${item.price * item.quantity}₽</div>
                </div>
                <div class="cart-item-actions">
                    <div class="cart-item-quantity">
                        <button class="quantity-btn decrease" onclick="updateCartQuantity(${item.id}, -1)" ${item.quantity === 1 ? 'disabled' : ''}>
                            <i class="fas fa-minus"></i>
                        </button>
                        <span>${item.quantity}</span>
                        <button class="quantity-btn increase" onclick="updateCartQuantity(${item.id}, 1)">
                            <i class="fas fa-plus"></i>
                        </button>
                    </div>
                    <button class="remove-item" onclick="removeFromCart(${item.id})">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        `).join('');
    }

    // Обновляем итоги
    document.getElementById('cart-subtotal').textContent = subtotal + '₽';
    document.getElementById('cart-delivery').textContent = deliveryFee === 0 ? 'Бесплатно' : deliveryFee + '₽';
    document.getElementById('cart-total').textContent = total + '₽';

    // Обновляем кнопку оформления
    const checkoutBtn = document.getElementById('checkout-btn');
    checkoutBtn.disabled = cart.length === 0;
    checkoutBtn.style.opacity = cart.length === 0 ? '0.5' : '1';
}

// Функции для корзины (глобальные для использования в inline обработчиках)
window.updateCartQuantity = function(productId, delta) {
    updateQuantity(productId, delta);
};

window.removeFromCart = function(productId) {
    const itemIndex = cart.findIndex(item => item.id === productId);

    if (itemIndex !== -1) {
        cart.splice(itemIndex, 1);
        saveCart();
        updateCart();
        renderProducts();
        renderCart();
        showNotification('Товар удален из корзины', 'success');
    }
};

// Показать уведомление
function showNotification(message, type = 'success') {
    const notification = document.getElementById('notification');
    notification.textContent = message;
    notification.className = `notification ${type} show`;

    setTimeout(() => {
        notification.classList.remove('show');
    }, 3000);
}

// Показать/скрыть загрузку
function showLoading(show) {
    const container = document.getElementById('products-grid');

    if (show) {
        container.innerHTML = `
            <div class="loading">
                <div class="loading-spinner"></div>
            </div>
        `;
    }
}

// Debounce функция
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Обновление информации о времени
function updateTimeInfo() {
    const now = new Date();
    const hours = now.getHours();
    const minutes = now.getMinutes();

    // Обновляем время в шапке если нужно
    const timeElements = document.querySelectorAll('.current-time');
    timeElements.forEach(el => {
        el.textContent = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
    });

    // Проверяем время работы
    const openingHour = 8; // 8:00
    const closingHour = 22; // 22:00

    if (hours < openingHour || hours >= closingHour) {
        showNotification('Кофейня закрыта. Время работы: 8:00 - 22:00', 'warning');
    }
}

// Обновление фильтров категорий
function updateCategoryFilters(categories) {
    const container = document.getElementById('filter-tags');

    // Добавляем категории как фильтры
    categories.forEach(category => {
        const button = document.createElement('button');
        button.className = 'filter-tag';
        button.dataset.filter = `category_${category.name}`;
        button.innerHTML = `
            ${category.emoji || '📋'} ${category.name}
        `;

        button.addEventListener('click', function() {
            setActiveCategory(category.name);
        });

        container.appendChild(button);
    });
}

// Тестовые данные
function getSampleProducts() {
    return [
        {
            id: 1,
            name: "Капучино",
            description: "Классический капучино с молоком и воздушной пенкой",
            price: 180,
            category_name: "coffee",
            image_url: null,
            popular: true,
            new: false,
            discount_price: null
        },
        {
            id: 2,
            name: "Латте",
            description: "Нежный латте с молочной пенкой и сиропом на выбор",
            price: 190,
            category_name: "coffee",
            image_url: null,
            popular: true,
            new: false,
            discount_price: 170
        },
        // ... остальные товары
    ];
}

// Экспорт данных для внешних систем
async function exportData() {
    if (!settings.SYNC_ENABLED) return;

    try {
        const exportData = {
            cart: cart,
            user: userData,
            timestamp: new Date().toISOString()
        };

        // Отправляем данные на внешний сервер
        const response = await fetch(settings.EXTERNAL_MENU_API, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(exportData)
        });

        if (response.ok) {
            showNotification('Данные синхронизированы', 'success');
        }
    } catch (error) {
        console.error('Ошибка экспорта данных:', error);
    }
}