// Инициализация Telegram Web App
const tg = window.Telegram.WebApp;
tg.expand();

// Глобальные переменные
let currentStep = 1;
let cart = JSON.parse(localStorage.getItem('cart')) || [];
let orderData = {
    contact: {},
    delivery: {
        type: 'pickup',
        address: '',
        timeType: 'asap',
        scheduledTime: null
    },
    payment: {
        method: 'cash'
    },
    loyalty: {
        usePoints: false,
        pointsUsed: 0,
        discount: 0
    },
    notes: ''
};
let loyaltyPoints = 0;
let loyaltyLevel = null;

// Инициализация при загрузке
document.addEventListener('DOMContentLoaded', async function() {
    // Загружаем данные пользователя из Telegram
    await loadUserData();

    // Загружаем информацию о программе лояльности
    await loadLoyaltyInfo();

    // Инициализируем UI
    initUI();

    // Загружаем корзину
    loadCartData();

    // Рассчитываем итоги
    calculateTotals();
});

// Загрузка данных пользователя
async function loadUserData() {
    const user = tg.initDataUnsafe.user;
    if (user) {
        document.getElementById('name').value = user.first_name || '';
        document.getElementById('last-name').value = user.last_name || '';

        // Сохраняем в orderData
        orderData.contact.name = user.first_name;
        orderData.contact.lastName = user.last_name;
        orderData.contact.username = user.username;
        orderData.contact.userId = user.id;
    }

    // Пробуем загрузить сохраненные данные
    const savedData = localStorage.getItem('userCheckoutData');
    if (savedData) {
        const data = JSON.parse(savedData);
        if (data.phone) document.getElementById('phone').value = data.phone;
        if (data.email) document.getElementById('email').value = data.email;

        orderData.contact.phone = data.phone;
        orderData.contact.email = data.email;
    }
}

// Загрузка информации о программе лояльности
async function loadLoyaltyInfo() {
    try {
        // Пытаемся получить данные о баллах пользователя
        const response = await fetch('/api/user/loyalty', {
            headers: {
                'X-Telegram-Init-Data': tg.initData
            }
        });

        if (response.ok) {
            const data = await response.json();
            loyaltyPoints = data.points || 0;
            loyaltyLevel = data.level || null;

            // Показываем блок лояльности если есть баллы
            if (loyaltyPoints > 0) {
                showLoyaltyOptions();
            }
        }
    } catch (error) {
        console.error('Ошибка загрузки информации о лояльности:', error);
    }
}

// Инициализация UI
function initUI() {
    // Обработчики для способа доставки
    document.querySelectorAll('.delivery-option').forEach(option => {
        option.addEventListener('click', function() {
            setDeliveryType(this.dataset.type);
        });
    });

    // Обработчики для времени получения
    document.getElementById('time-asap').addEventListener('change', function() {
        setTimeType('asap');
    });

    document.getElementById('time-scheduled').addEventListener('change', function() {
        setTimeType('scheduled');
    });

    // Обработчик изменения времени
    document.getElementById('order-time').addEventListener('change', function() {
        orderData.delivery.scheduledTime = this.value;
        updateOrderSummary();
    });

    // Обработчики для способа оплаты
    document.querySelectorAll('.payment-method').forEach(method => {
        method.addEventListener('click', function() {
            setPaymentMethod(this.dataset.method);
        });
    });

    // Обработчики для полей ввода
    document.getElementById('name').addEventListener('input', function() {
        orderData.contact.name = this.value;
        validateField(this, 'name');
    });

    document.getElementById('phone').addEventListener('input', function() {
        orderData.contact.phone = this.value;
        validateField(this, 'phone');
    });

    document.getElementById('email').addEventListener('input', function() {
        orderData.contact.email = this.value;
        validateField(this, 'email');
    });

    document.getElementById('address').addEventListener('input', function() {
        orderData.delivery.address = this.value;
        validateField(this, 'address');
    });

    document.getElementById('notes').addEventListener('input', function() {
        orderData.notes = this.value;
    });

    // Инициализируем время
    const now = new Date();
    const nextHour = new Date(now.getTime() + 60 * 60 * 1000);
    const timeString = nextHour.getHours().toString().padStart(2, '0') + ':' +
                      nextHour.getMinutes().toString().padStart(2, '0');
    document.getElementById('order-time').value = timeString;
    orderData.delivery.scheduledTime = timeString;
}

// Загрузка данных корзины
function loadCartData() {
    if (cart.length === 0) {
        // Если корзина пуста, перенаправляем на главную
        window.location.href = 'index.html';
        return;
    }

    // Отображаем товары в сводке
    renderOrderItems();
}

// Отображение товаров в сводке
function renderOrderItems() {
    const container = document.getElementById('order-items-summary');
    let html = '';

    cart.forEach(item => {
        html += `
            <div class="summary-item" style="align-items: flex-start;">
                <div>
                    <div style="font-weight: 500;">${item.name}</div>
                    <div style="font-size: 14px; color: var(--text-light);">${item.price}₽ × ${item.quantity}</div>
                </div>
                <div style="font-weight: 600; color: var(--primary);">
                    ${item.price * item.quantity}₽
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

// Установка типа доставки
function setDeliveryType(type) {
    orderData.delivery.type = type;

    // Обновляем UI
    document.querySelectorAll('.delivery-option').forEach(option => {
        option.classList.remove('selected');
        if (option.dataset.type === type) {
            option.classList.add('selected');
        }
    });

    // Показываем/скрываем поле адреса
    const addressField = document.getElementById('address-field');
    if (type === 'delivery') {
        addressField.style.display = 'block';
    } else {
        addressField.style.display = 'none';
        orderData.delivery.address = '';
    }

    // Обновляем сводку
    updateOrderSummary();
    calculateTotals();
}

// Установка типа времени
function setTimeType(type) {
    orderData.delivery.timeType = type;

    const scheduledInput = document.getElementById('scheduled-time-input');
    if (type === 'scheduled') {
        scheduledInput.classList.add('show');
    } else {
        scheduledInput.classList.remove('show');
        orderData.delivery.scheduledTime = null;
    }

    updateOrderSummary();
}

// Установка способа оплаты
function setPaymentMethod(method) {
    orderData.payment.method = method;

    document.querySelectorAll('.payment-method').forEach(m => {
        m.classList.remove('selected');
        if (m.dataset.method === method) {
            m.classList.add('selected');
        }
    });

    updateOrderSummary();
}

// Показ опций лояльности
function showLoyaltyOptions() {
    const maxDiscount = Math.floor(loyaltyPoints / 100); // 100 баллов = 1₽
    const discountElement = document.getElementById('loyalty-discount');

    if (maxDiscount > 0) {
        discountElement.style.display = 'flex';
        document.getElementById('loyalty-desc').textContent =
            `Доступно баллов: ${loyaltyPoints} (${maxDiscount}₽ скидки)`;
    }
}

// Изменение использования баллов
function changeLoyaltyPoints() {
    const maxDiscount = Math.floor(loyaltyPoints / 100);
    const pointsToUse = prompt(`Сколько баллов использовать? (максимум ${loyaltyPoints}, ${maxDiscount}₽ скидки)`, loyaltyPoints);

    if (pointsToUse !== null) {
        const points = parseInt(pointsToUse);
        if (!isNaN(points) && points >= 0 && points <= loyaltyPoints) {
            orderData.loyalty.usePoints = points > 0;
            orderData.loyalty.pointsUsed = points;
            orderData.loyalty.discount = Math.floor(points / 100);

            // Обновляем отображение
            document.getElementById('loyalty-desc').textContent =
                `Использовано баллов: ${points} (${orderData.loyalty.discount}₽ скидки)`;

            // Показываем скидку в сводке
            const discountRow = document.getElementById('discount-row');
            if (orderData.loyalty.discount > 0) {
                discountRow.style.display = 'flex';
                document.getElementById('summary-discount').textContent = `-${orderData.loyalty.discount}₽`;
            } else {
                discountRow.style.display = 'none';
            }

            calculateTotals();
        } else {
            alert('Пожалуйста, введите корректное количество баллов');
        }
    }
}

// Расчет итогов
function calculateTotals() {
    // Сумма товаров
    const subtotal = cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);

    // Стоимость доставки
    let deliveryFee = 0;
    if (orderData.delivery.type === 'delivery') {
        deliveryFee = subtotal >= 500 ? 0 : 150;
    }

    // Скидка
    const discount = orderData.loyalty.discount || 0;

    // Итог
    const total = subtotal + deliveryFee - discount;

    // Обновляем UI
    document.getElementById('summary-subtotal').textContent = subtotal + '₽';
    document.getElementById('summary-delivery').textContent =
        deliveryFee === 0 ? 'Бесплатно' : deliveryFee + '₽';
    document.getElementById('summary-total').textContent = total + '₽';

    // Обновляем цену доставки в выборе
    document.getElementById('delivery-price').textContent =
        subtotal >= 500 ? 'Бесплатно' : '150₽';
}

// Обновление сводки заказа
function updateOrderSummary() {
    // Информация о доставке
    document.getElementById('order-delivery-type').textContent =
        orderData.delivery.type === 'pickup' ? 'Самовывоз' : 'Доставка';

    document.getElementById('order-address').textContent =
        orderData.delivery.type === 'pickup' ?
        'ул. Кофейная, 15' :
        (orderData.delivery.address || 'не указан');

    // Время
    let timeText = 'Как можно скорее';
    if (orderData.delivery.timeType === 'scheduled' && orderData.delivery.scheduledTime) {
        timeText = `К ${orderData.delivery.scheduledTime}`;
    }
    document.getElementById('order-time-display').textContent = timeText;

    // Оплата
    const paymentMethods = {
        'cash': 'Наличными',
        'card': 'Картой онлайн',
        'card_courier': 'Картой курьеру'
    };
    document.getElementById('order-payment').textContent =
        paymentMethods[orderData.payment.method] || 'Наличными';

    // Телефон
    document.getElementById('order-phone').textContent =
        orderData.contact.phone || 'не указан';
}

// Навигация по шагам
function nextStep() {
    // Проверяем текущий шаг
    if (!validateCurrentStep()) {
        return;
    }

    // Переходим к следующему шагу
    currentStep++;
    updateSteps();
}

function prevStep() {
    // Возвращаемся к предыдущему шагу
    currentStep--;
    updateSteps();
}

// Обновление отображения шагов
function updateSteps() {
    // Обновляем индикаторы шагов
    for (let i = 1; i <= 4; i++) {
        const indicator = document.getElementById(`step-${i}-indicator`);
        const section = document.getElementById(`section-${i}`);

        if (i === currentStep) {
            indicator.classList.add('active');
            section.style.display = 'block';
        } else {
            indicator.classList.remove('active');
            section.style.display = 'none';
        }
    }

    // Обновляем кнопки
    const backBtn = document.getElementById('back-btn');
    const nextBtn = document.getElementById('next-btn');
    const submitBtn = document.getElementById('submit-btn');

    if (currentStep === 1) {
        backBtn.style.display = 'none';
        nextBtn.style.display = 'flex';
        submitBtn.style.display = 'none';
    } else if (currentStep === 4) {
        backBtn.style.display = 'flex';
        nextBtn.style.display = 'none';
        submitBtn.style.display = 'flex';

        // Обновляем сводку перед показом
        updateOrderSummary();
        calculateTotals();
    } else {
        backBtn.style.display = 'flex';
        nextBtn.style.display = 'flex';
        submitBtn.style.display = 'none';
    }
}

// Валидация текущего шага
function validateCurrentStep() {
    let isValid = true;

    if (currentStep === 1) {
        // Проверка контактных данных
        if (!validateField(document.getElementById('name'), 'name')) isValid = false;
        if (!validateField(document.getElementById('phone'), 'phone')) isValid = false;
        if (document.getElementById('email').value &&
            !validateField(document.getElementById('email'), 'email')) isValid = false;
    } else if (currentStep === 2) {
        // Проверка доставки
        if (orderData.delivery.type === 'delivery') {
            if (!validateField(document.getElementById('address'), 'address')) isValid = false;
        }

        if (orderData.delivery.timeType === 'scheduled') {
            const timeInput = document.getElementById('order-time');
            const time = timeInput.value;

            if (!time) {
                showError('time-error', 'Выберите время');
                isValid = false;
            } else {
                const [hours, minutes] = time.split(':').map(Number);
                if (hours < 8 || hours >= 22) {
                    showError('time-error', 'Время должно быть между 08:00 и 22:00');
                    isValid = false;
                } else {
                    hideError('time-error');
                }
            }
        }
    } else if (currentStep === 4) {
        // Проверка соглашений
        if (!document.getElementById('agree-terms').checked) {
            showError('terms-error', 'Необходимо согласие с условиями');
            isValid = false;
        } else {
            hideError('terms-error');
        }

        if (!document.getElementById('agree-rules').checked) {
            showError('rules-error', 'Необходимо согласие с правилами');
            isValid = false;
        } else {
            hideError('rules-error');
        }
    }

    return isValid;
}

// Валидация поля
function validateField(input, fieldName) {
    const value = input.value.trim();
    let isValid = true;
    let errorMessage = '';

    switch (fieldName) {
        case 'name':
            if (value.length < 2) {
                errorMessage = 'Имя должно содержать минимум 2 символа';
                isValid = false;
            }
            break;

        case 'phone':
            const phoneRegex = /^(\+7|7|8)?[\s\-]?\(?[489][0-9]{2}\)?[\s\-]?[0-9]{3}[\s\-]?[0-9]{2}[\s\-]?[0-9]{2}$/;
            if (!phoneRegex.test(value.replace(/\D/g, ''))) {
                errorMessage = 'Введите корректный номер телефона';
                isValid = false;
            }
            break;

        case 'email':
            if (value) {
                const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
                if (!emailRegex.test(value)) {
                    errorMessage = 'Введите корректный email';
                    isValid = false;
                }
            }
            break;

        case 'address':
            if (value.length < 10) {
                errorMessage = 'Адрес должен содержать минимум 10 символов';
                isValid = false;
            }
            break;
    }

    if (isValid) {
        hideError(`${fieldName}-error`);
        input.style.borderColor = '';
    } else {
        showError(`${fieldName}-error`, errorMessage);
        input.style.borderColor = 'var(--error)';
    }

    return isValid;
}

// Показать ошибку
function showError(errorId, message) {
    const errorElement = document.getElementById(errorId);
    errorElement.textContent = message;
    errorElement.classList.add('show');

    // Прокрутка к ошибке
    errorElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

// Скрыть ошибку
function hideError(errorId) {
    const errorElement = document.getElementById(errorId);
    errorElement.classList.remove('show');
}

// Отправка заказа
async function submitOrder() {
    // Проверяем последний шаг
    if (!validateCurrentStep()) {
        return;
    }

    // Сохраняем данные пользователя
    if (document.getElementById('save-info').checked) {
        localStorage.setItem('userCheckoutData', JSON.stringify({
            phone: orderData.contact.phone,
            email: orderData.contact.email
        }));
    }

    // Подготавливаем данные заказа
    const orderPayload = {
        action: 'create_order',
        contact: {
            name: orderData.contact.name,
            lastName: orderData.contact.lastName,
            phone: orderData.contact.phone,
            email: orderData.contact.email,
            userId: orderData.contact.userId
        },
        delivery: {
            type: orderData.delivery.type,
            address: orderData.delivery.address,
            timeType: orderData.delivery.timeType,
            scheduledTime: orderData.delivery.scheduledTime
        },
        payment: {
            method: orderData.payment.method
        },
        loyalty: orderData.loyalty,
        notes: orderData.notes,
        items: cart.map(item => ({
            id: item.id,
            name: item.name,
            price: item.price,
            quantity: item.quantity
        })),
        total: parseFloat(document.getElementById('summary-total').textContent.replace('₽', '')),
        subtotal: parseFloat(document.getElementById('summary-subtotal').textContent.replace('₽', '')),
        deliveryFee: orderData.delivery.type === 'delivery' ?
            (parseFloat(document.getElementById('summary-subtotal').textContent.replace('₽', '')) >= 500 ? 0 : 150) : 0,
        discount: orderData.loyalty.discount || 0
    };

    try {
        // Показываем загрузку
        tg.MainButton.showProgress();

        // Отправляем заказ через Telegram Web App
        tg.sendData(JSON.stringify(orderPayload));

        // Ждем отправки
        setTimeout(() => {
            tg.MainButton.hideProgress();
            showConfirmation(orderPayload);
        }, 1000);

    } catch (error) {
        console.error('Ошибка отправки заказа:', error);
        alert('Произошла ошибка при оформлении заказа. Пожалуйста, попробуйте еще раз.');
        tg.MainButton.hideProgress();
    }
}

// Показ подтверждения
function showConfirmation(orderData) {
    // Генерируем номер заказа
    const orderNumber = '#' + Math.floor(10000 + Math.random() * 90000);

    // Обновляем информацию в модальном окне
    document.getElementById('confirmation-number').textContent = orderNumber;
    document.getElementById('confirmation-total').textContent =
        document.getElementById('summary-total').textContent;

    // Показываем модальное окно
    document.getElementById('confirmation-modal').style.display = 'flex';

    // Очищаем корзину
    localStorage.removeItem('cart');

    // Сохраняем информацию о заказе
    const orderHistory = JSON.parse(localStorage.getItem('orderHistory') || '[]');
    orderHistory.unshift({
        id: orderNumber,
        date: new Date().toISOString(),
        total: orderData.total,
        status: 'pending',
        items: orderData.items
    });
    localStorage.setItem('orderHistory', JSON.stringify(orderHistory.slice(0, 10)));
}

// Навигация назад
function goBack() {
    if (currentStep > 1) {
        prevStep();
    } else {
        window.history.back();
    }
}

// Переход на главную
function goToMain() {
    window.location.href = 'index.html';
}

// Просмотр заказа
function viewOrder() {
    window.location.href = 'orders.html';
}

// Глобальные функции для использования в HTML
window.prevStep = prevStep;
window.nextStep = nextStep;
window.submitOrder = submitOrder;
window.goBack = goBack;
window.goToMain = goToMain;
window.viewOrder = viewOrder;
window.changeLoyaltyPoints = changeLoyaltyPoints;

// Обработка сообщений от Telegram
tg.onEvent('webAppDataReceived', function(event) {
    console.log('Данные получены от бота:', event);
});

// Обработка закрытия Web App
tg.onEvent('viewportChanged', function(event) {
    if (!event.isStateStable) {
        tg.expand();
    }
});

// Обработка нажатия кнопки "Назад" в Telegram
tg.BackButton.onClick(goBack);

// Показываем кнопку "Назад" если мы не на первом шаге
if (currentStep > 1) {
    tg.BackButton.show();
}

// Дополнительные функции для оформления заказа

// Форматирование телефона
function formatPhoneNumber(phone) {
    const cleaned = phone.replace(/\D/g, '');
    const match = cleaned.match(/^(\d{1})(\d{3})(\d{3})(\d{2})(\d{2})$/);
    if (match) {
        return `+${match[1]} (${match[2]}) ${match[3]}-${match[4]}-${match[5]}`;
    }
    return phone;
}

// Автоформатирование телефона
document.getElementById('phone').addEventListener('input', function(e) {
    let value = e.target.value.replace(/\D/g, '');

    if (value.startsWith('7') || value.startsWith('8')) {
        value = '7' + value.substring(1);
    } else if (!value.startsWith('7')) {
        value = '7' + value;
    }

    if (value.length > 11) {
        value = value.substring(0, 11);
    }

    let formatted = '';
    if (value.length > 0) {
        formatted = '+7';
        if (value.length > 1) {
            formatted += ' (' + value.substring(1, 4);
        }
        if (value.length > 4) {
            formatted += ') ' + value.substring(4, 7);
        }
        if (value.length > 7) {
            formatted += '-' + value.substring(7, 9);
        }
        if (value.length > 9) {
            formatted += '-' + value.substring(9, 11);
        }
    }

    e.target.value = formatted;
    orderData.contact.phone = value;
});

// Проверка минимального заказа
function checkMinOrder() {
    const subtotal = cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
    const minOrder = 300; // Минимальный заказ

    if (subtotal < minOrder) {
        const missing = minOrder - subtotal;
        showNotification(`Минимальная сумма заказа ${minOrder}₽. Добавьте товаров на ${missing}₽`, 'warning');
        return false;
    }

    return true;
}

// Проверка времени работы
function checkWorkingHours() {
    const now = new Date();
    const hours = now.getHours();
    const minutes = now.getMinutes();

    // Время работы: 8:00 - 22:00
    if (hours < 8 || (hours === 22 && minutes > 0) || hours >= 23) {
        if (orderData.delivery.timeType === 'asap') {
            showNotification('Кофейня сейчас закрыта. Время работы: 08:00 - 22:00. Выберите время на завтра.', 'warning');

            // Автоматически переключаем на заказ ко времени
            document.getElementById('time-scheduled').checked = true;
            setTimeType('scheduled');

            // Устанавливаем время на завтра 10:00
            const tomorrow = new Date(now);
            tomorrow.setDate(tomorrow.getDate() + 1);
            tomorrow.setHours(10, 0, 0, 0);

            const timeString = tomorrow.getHours().toString().padStart(2, '0') + ':' +
                              tomorrow.getMinutes().toString().padStart(2, '0');
            document.getElementById('order-time').value = timeString;
            orderData.delivery.scheduledTime = timeString;

            return false;
        }
    }

    return true;
}

// Показать уведомление
function showNotification(message, type = 'info') {
    // Создаем элемент уведомления
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.innerHTML = `
        <div style="display: flex; align-items: center; gap: 10px;">
            <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'warning' ? 'exclamation-triangle' : 'info-circle'}"></i>
            <span>${message}</span>
        </div>
    `;

    // Стили для уведомления
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'success' ? 'var(--success)' : type === 'warning' ? 'var(--warning)' : 'var(--secondary)'};
        color: white;
        padding: 15px 20px;
        border-radius: var(--radius-md);
        box-shadow: var(--shadow-lg);
        z-index: 10000;
        animation: slideInRight 0.3s, slideOutRight 0.3s 2.7s;
        max-width: 300px;
    `;

    // Добавляем стили анимации
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideInRight {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        @keyframes slideOutRight {
            from { transform: translateX(0); opacity: 1; }
            to { transform: translateX(100%); opacity: 0; }
        }
    `;
    document.head.appendChild(style);

    // Добавляем уведомление на страницу
    document.body.appendChild(notification);

    // Удаляем через 3 секунды
    setTimeout(() => {
        if (notification.parentNode) {
            notification.parentNode.removeChild(notification);
        }
    }, 3000);
}

// Расчет времени доставки
function calculateDeliveryTime() {
    const now = new Date();
    const hours = now.getHours();

    // Время приготовления: 15-25 минут
    const prepTime = 20; // минут

    // Если заказ ко времени
    if (orderData.delivery.timeType === 'scheduled' && orderData.delivery.scheduledTime) {
        const [orderHours, orderMinutes] = orderData.delivery.scheduledTime.split(':').map(Number);
        const orderTime = new Date();
        orderTime.setHours(orderHours, orderMinutes, 0, 0);

        return orderTime;
    }

    // Если как можно скорее
    const deliveryTime = new Date(now.getTime() + prepTime * 60000);

    // Проверяем время работы
    if (deliveryTime.getHours() >= 22) {
        // Если доставка выходит за время работы, переносим на завтра
        deliveryTime.setDate(deliveryTime.getDate() + 1);
        deliveryTime.setHours(8, 0, 0, 0);

        showNotification('Доставка будет осуществлена завтра с 8:00', 'info');
    }

    return deliveryTime;
}

// Сохранение черновика заказа
function saveDraft() {
    const draft = {
        contact: orderData.contact,
        delivery: orderData.delivery,
        payment: orderData.payment,
        loyalty: orderData.loyalty,
        notes: orderData.notes,
        cart: cart,
        timestamp: new Date().toISOString()
    };

    localStorage.setItem('orderDraft', JSON.stringify(draft));
}

// Загрузка черновика заказа
function loadDraft() {
    const draft = JSON.parse(localStorage.getItem('orderDraft'));
    if (draft) {
        // Проверяем не устарел ли черновик (старше 1 часа)
        const draftTime = new Date(draft.timestamp);
        const now = new Date();
        const hoursDiff = (now - draftTime) / (1000 * 60 * 60);

        if (hoursDiff < 1) { // Черновик не старше 1 часа
            orderData.contact = draft.contact || {};
            orderData.delivery = draft.delivery || { type: 'pickup', timeType: 'asap' };
            orderData.payment = draft.payment || { method: 'cash' };
            orderData.loyalty = draft.loyalty || { usePoints: false, pointsUsed: 0, discount: 0 };
            orderData.notes = draft.notes || '';

            // Обновляем UI
            if (orderData.contact.name) {
                document.getElementById('name').value = orderData.contact.name;
            }
            if (orderData.contact.phone) {
                document.getElementById('phone').value = orderData.contact.phone;
            }
            if (orderData.contact.email) {
                document.getElementById('email').value = orderData.contact.email;
            }

            setDeliveryType(orderData.delivery.type);
            setTimeType(orderData.delivery.timeType);
            setPaymentMethod(orderData.payment.method);

            return true;
        } else {
            // Удаляем устаревший черновик
            localStorage.removeItem('orderDraft');
        }
    }

    return false;
}

// Автосохранение черновика каждые 30 секунд
setInterval(saveDraft, 30000);

// Загружаем черновик при старте
window.addEventListener('load', function() {
    if (loadDraft()) {
        showNotification('Загружен последний черновик заказа', 'info');
    }
});

// Обработка изменения способа оплаты "Картой онлайн"
document.querySelector('.payment-method[data-method="card"]').addEventListener('click', function() {
    if (orderData.delivery.type === 'pickup') {
        showNotification('Оплата картой онлайн доступна только при доставке', 'warning');
        setPaymentMethod('cash');
    }
});

// Проверка перед переходом к оплате
const originalNextStep = window.nextStep;
window.nextStep = function() {
    if (currentStep === 2) {
        // Проверяем минимальный заказ
        if (!checkMinOrder()) {
            return;
        }

        // Проверяем время работы
        if (!checkWorkingHours()) {
            return;
        }

        // Если выбран самовывоз и оплата картой онлайн
        if (orderData.delivery.type === 'pickup' && orderData.payment.method === 'card') {
            showNotification('Оплата картой онлайн доступна только при доставке', 'warning');
            setPaymentMethod('cash');
        }
    }

    originalNextStep();
};

// Обновление времени в реальном времени
function updateCurrentTime() {
    const now = new Date();
    const timeString = now.getHours().toString().padStart(2, '0') + ':' +
                      now.getMinutes().toString().padStart(2, '0');

    const timeElements = document.querySelectorAll('.current-time');
    timeElements.forEach(el => {
        if (el.querySelector('span')) {
            el.querySelector('span').textContent = timeString;
        }
    });
}

// Обновляем время каждую минуту
setInterval(updateCurrentTime, 60000);
updateCurrentTime();

// Обработка специальных предложений
function applyPromoCode() {
    const promoCode = prompt('Введите промокод:');
    if (promoCode) {
        // Здесь можно добавить проверку промокодов
        const validPromoCodes = {
            'WELCOME10': { discount: 10, type: 'percent' },
            'COFFEE20': { discount: 20, type: 'percent' },
            'SUMMER100': { discount: 100, type: 'fixed' }
        };

        if (validPromoCodes[promoCode.toUpperCase()]) {
            const promo = validPromoCodes[promoCode.toUpperCase()];
            showNotification(`Промокод применен! Скидка ${promo.discount}${promo.type === 'percent' ? '%' : '₽'}`, 'success');

            // Добавляем логику применения скидки
            // ...
        } else {
            showNotification('Промокод недействителен', 'error');
        }
    }
}

// Добавляем кнопку промокода
const promoButton = document.createElement('button');
promoButton.innerHTML = '<i class="fas fa-tag"></i> Промокод';
promoButton.style.cssText = `
    position: fixed;
    bottom: 100px;
    right: 20px;
    background: var(--secondary);
    color: white;
    border: none;
    width: 50px;
    height: 50px;
    border-radius: 50%;
    box-shadow: var(--shadow-md);
    cursor: pointer;
    z-index: 99;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    transition: all 0.3s;
`;
promoButton.addEventListener('mouseenter', () => {
    promoButton.style.transform = 'scale(1.1)';
    promoButton.style.boxShadow = 'var(--shadow-lg)';
});
promoButton.addEventListener('mouseleave', () => {
    promoButton.style.transform = 'scale(1)';
    promoButton.style.boxShadow = 'var(--shadow-md)';
});
promoButton.addEventListener('click', applyPromoCode);
document.body.appendChild(promoButton);

// Показываем кнопку только на шагах 2-4
function updatePromoButtonVisibility() {
    if (currentStep >= 2 && currentStep <= 4) {
        promoButton.style.display = 'flex';
    } else {
        promoButton.style.display = 'none';
    }
}

// Обновляем видимость кнопки при смене шага
const originalUpdateSteps = updateSteps;
updateSteps = function() {
    originalUpdateSteps();
    updatePromoButtonVisibility();
};
updatePromoButtonVisibility();