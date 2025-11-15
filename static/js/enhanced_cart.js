/**
 * Enhanced Cart Management System
 * Professional order management with improved state handling
 */

class EnhancedCartManager {
    constructor() {
        this.cartState = {
            items: [],
            totalAmount: 0,
            itemCount: 0,
            status: 'idle',
            cartId: null,
            lastUpdated: null
        };
        this.isProcessing = false;
        this.messageHistory = [];
        this.productPricing = {};
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.loadCartState();
        console.log('Enhanced Cart Manager initialized');
    }

    setupEventListeners() {
        // Message input handling
        const messageInput = document.getElementById('messageInput');
        if (messageInput) {
            messageInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });

            messageInput.addEventListener('input', (e) => {
                const sendButton = document.getElementById('sendButton');
                const message = e.target.value.trim();
                if (sendButton) {
                    sendButton.disabled = !message || this.isProcessing;
                }
            });
        }

        // Send button
        const sendButton = document.getElementById('sendButton');
        if (sendButton) {
            sendButton.addEventListener('click', () => this.sendMessage());
        }
    }

    async sendMessage() {
        if (this.isProcessing) return;
        
        const input = document.getElementById('messageInput');
        const message = input.value.trim();
        
        if (!message) return;
        
        // Clear input and disable
        input.value = '';
        this.isProcessing = true;
        this.toggleUI(false);
        
        // Add user message to chat
        this.addMessage(message, 'user');
        
        // Show typing indicator
        this.showTypingIndicator();
        
        try {
            const response = await fetch('/chat/message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ message: message })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.error) {
                this.addMessage(`Error: ${data.error}`, 'bot', [], 'error');
            } else {
                // Handle warehouse options for onboarding
                if (data.warehouse_options) {
                    this.addMessage(data.response, 'bot');
                    this.showWarehouseOptions(data.warehouse_options);
                } else {
                    // Update the last user message if clean message is available
                    if (data.user_message) {
                        this.updateLastUserMessage(data.user_message);
                    }
                    
                    this.addMessage(data.response, 'bot', data.data_sources);
                    
                    // Show intent classification if available
                    if (data.intent) {
                        this.showIntentInfo(data.intent, data.confidence);
                    }
                    
                    // Handle interactive elements
                    this.parseInteractiveElements(data.response, data.intent);
                }
            }
        } catch (error) {
            console.error('Error:', error);
            let errorMessage = 'Connection error. Please check your internet connection.';
            
            if (error.name === 'TypeError' && error.message.includes('fetch')) {
                errorMessage = 'Network error. Please check your connection and try again.';
            } else if (error.message.includes('HTTP error')) {
                errorMessage = 'Server error. Please try again later.';
            }
            
            this.addMessage(errorMessage, 'bot', [], 'error');
        } finally {
            this.hideTypingIndicator();
            this.isProcessing = false;
            this.toggleUI(true);
            input.focus();
        }
    }

    addMessage(text, sender, sources = [], messageType = 'normal') {
        const messagesDiv = document.getElementById('chatMessages');
        
        // Remove welcome message if exists
        const welcome = messagesDiv.querySelector('.text-center');
        if (welcome) welcome.remove();
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;
        
        if (messageType === 'error') {
            messageDiv.classList.add('error-message');
        }
        
        const bubble = document.createElement('div');
        bubble.className = 'message-bubble';
        
        // Process markdown-like formatting
        bubble.innerHTML = this.formatMessage(text);
        
        messageDiv.appendChild(bubble);
        
        // Add timestamp
        const time = document.createElement('div');
        time.className = 'message-time';
        time.textContent = new Date().toLocaleTimeString();
        messageDiv.appendChild(time);
        
        // Add sources if available
        if (sources && sources.length > 0) {
            const sourcesDiv = document.createElement('div');
            sourcesDiv.className = 'text-muted small mt-1';
            sourcesDiv.innerHTML = '<i class="fas fa-database"></i> Sources: ' + sources.join(', ');
            messageDiv.appendChild(sourcesDiv);
        }
        
        messagesDiv.appendChild(messageDiv);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
        
        // Store in message history
        this.messageHistory.push({
            text: text,
            sender: sender,
            timestamp: new Date(),
            sources: sources
        });
    }

    formatMessage(text) {
        // Convert markdown tables to HTML
        if (text.includes('|')) {
            text = this.convertMarkdownTable(text);
        }
        
        // Convert bold **text**
        text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        
        // Convert italic *text*
        text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');
        
        // Convert line breaks
        text = text.replace(/\n/g, '<br>');
        
        // Enhance order confirmations
        if (text.includes('Order Placed Successfully') || text.includes('Order ID:')) {
            text = text.replace(/Order Placed Successfully!/g, '<div class="alert alert-success mb-2"><h5><i class="fas fa-check-circle"></i> Order Placed Successfully!</h5></div>');
            text = text.replace(/Order ID: ([A-Z0-9]+)/g, '<div class="alert alert-info mb-2"><strong><i class="fas fa-receipt"></i> Order ID:</strong> <code>$1</code></div>');
            text = text.replace(/Total Amount: ([0-9,]+\.?\d*)\s*MMK/g, '<div class="alert alert-warning mb-2"><strong><i class="fas fa-coins"></i> Total Amount:</strong> <span class="h5 text-success">$1 MMK</span></div>');
            text = text.replace(/Status: ([A-Za-z]+)/g, '<div class="alert alert-primary mb-2"><strong><i class="fas fa-info-circle"></i> Status:</strong> <span class="badge bg-success">$1</span></div>');
        }
        
        // Enhance order confirmation messages with product details
        if (text.includes('I confirm my order with the following details')) {
            // Style the main heading
            text = text.replace(/I confirm my order with the following details:/g, '<div class="alert alert-primary mb-3"><h6><i class="fas fa-shopping-cart"></i> <strong>Order Confirmation</strong></h6></div>');
            
            // Style total amount with better visibility
            text = text.replace(/Total Order Amount: \$([0-9,]+\.?\d*)/g, '<div class="alert alert-success mt-3"><h5><i class="fas fa-calculator"></i> <strong>Total Order Amount:</strong> <span class="h4 text-success">$$$1</span></h5></div>');
        }
        
        // Enhance error messages
        if (text.includes('Error:') || text.includes('Server error')) {
            text = text.replace(/Error: (.*)/g, '<div class="alert alert-danger"><i class="fas fa-exclamation-triangle"></i> <strong>Error:</strong> $1</div>');
        }
        
        return text;
    }

    convertMarkdownTable(text) {
        const lines = text.split('\n');
        let tableHTML = '<div class="table-responsive mt-3"><table class="table table-striped table-sm">';
        let inTable = false;
        
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trim();
            
            if (line.includes('|')) {
                const cells = line.split('|').filter(cell => cell.trim());
                
                if (i === 0 || !inTable) {
                    // Header row
                    tableHTML += '<thead><tr>';
                    cells.forEach(cell => {
                        tableHTML += `<th>${cell.trim()}</th>`;
                    });
                    tableHTML += '</tr></thead><tbody>';
                    inTable = true;
                } else if (line.includes('---')) {
                    // Separator row, skip
                    continue;
                } else {
                    // Data row
                    tableHTML += '<tr>';
                    cells.forEach(cell => {
                        tableHTML += `<td>${cell.trim()}</td>`;
                    });
                    tableHTML += '</tr>';
                }
            } else if (inTable) {
                tableHTML += '</tbody></table></div>';
                inTable = false;
            }
        }
        
        if (inTable) {
            tableHTML += '</tbody></table></div>';
        }
        
        return tableHTML;
    }

    toggleUI(enabled) {
        const messageInput = document.getElementById('messageInput');
        const sendButton = document.getElementById('sendButton');
        
        if (messageInput) messageInput.disabled = !enabled;
        if (sendButton) sendButton.disabled = !enabled;
    }

    showTypingIndicator() {
        const indicator = document.getElementById('typingIndicator');
        if (indicator) {
            indicator.style.display = 'block';
            indicator.innerHTML = '<i class="fas fa-circle-notch fa-spin"></i> AI is thinking...';
        }
    }

    hideTypingIndicator() {
        const indicator = document.getElementById('typingIndicator');
        if (indicator) {
            indicator.style.display = 'none';
        }
    }

    updateLastUserMessage(cleanMessage) {
        const messagesDiv = document.getElementById('chatMessages');
        const lastUserMessage = messagesDiv.querySelector('.message.user:last-child');
        if (lastUserMessage) {
            const bubble = lastUserMessage.querySelector('.message-bubble');
            if (bubble) {
                bubble.innerHTML = this.formatMessage(cleanMessage);
            }
        }
    }

    showIntentInfo(intent, confidence) {
        const intentMap = {
            'PLACE_ORDER': { icon: '🛒', label: 'Order Placement', color: 'success' },
            'CALCULATE_COST': { icon: '💰', label: 'Cost Calculation', color: 'warning' },
            'TRACK_ORDER': { icon: '📦', label: 'Order Tracking', color: 'info' },
            'COMPANY_INFO': { icon: '🏢', label: 'Company Info', color: 'primary' },
            'WEB_SEARCH': { icon: '🔍', label: 'Web Search', color: 'warning' },
            'OTHER': { icon: '💬', label: 'General Chat', color: 'secondary' }
        };
        
        const intentInfo = intentMap[intent] || { icon: '❓', label: 'Unknown', color: 'secondary' };
        
        const messagesDiv = document.getElementById('chatMessages');
        const intentDiv = document.createElement('div');
        intentDiv.className = `intent-info alert alert-${intentInfo.color} alert-sm mt-2`;
        intentDiv.innerHTML = `
            <small>
                <i class="fas fa-brain"></i> 
                Intent: ${intentInfo.icon} ${intentInfo.label} 
                (${Math.round(confidence * 100)}% confidence)
            </small>
        `;
        
        messagesDiv.appendChild(intentDiv);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }

    parseInteractiveElements(response, intent) {
        console.log('=== parseInteractiveElements called ===');
        console.log('Intent:', intent);
        console.log('Response length:', response.length);
        
        const messagesDiv = document.getElementById('chatMessages');
        
        // Find the last bot message
        const allMessages = messagesDiv.querySelectorAll('.message.bot');
        const lastBotMessage = allMessages[allMessages.length - 1];
        
        if (!lastBotMessage) {
            console.log('Early return: no bot message found');
            return;
        }
        
        // Remove any existing interactive buttons first
        this.clearExistingInteractiveButtons();
        
        // Show product selection if needed
        if (intent === 'PLACE_ORDER' && (
            response.includes('select') || 
            response.includes('choose') || 
            response.includes('available products') ||
            response.includes('Quick Product Selection') ||
            response.includes('which products') ||
            response.includes('what products') ||
            response.includes('product name') ||
            response.includes('quantities') ||
            (response.includes('order') && !response.includes('Order Placed Successfully') &&
            !response.includes('Order ID:') &&
            !response.includes('Total Amount:') &&
            !response.includes('Status:'))
        )) {
            console.log('PLACE_ORDER intent with product selection request - showing product selection buttons');
            this.showProductSelectionInterface(lastBotMessage);
            return;
        }
        
        // Check for product selection patterns
        if ((intent === undefined || intent === null) && (
            response.includes('Quick Product Selection') || 
            response.includes('🛒') ||
            response.includes('Available:') ||
            response.includes('QB') ||
            // Products are now dynamically loaded - no hardcoded product names
            false ||
            response.includes('AI') ||
            response.includes('product name') ||
            response.includes('which products') ||
            response.includes('what you')
        )) {
            console.log('Showing product selection buttons based on content');
            this.showProductSelectionInterface(lastBotMessage);
        }
    }

    clearExistingInteractiveButtons() {
        const existingButtons = document.querySelectorAll('.interactive-buttons');
        existingButtons.forEach(btn => btn.remove());
    }

    async showProductSelectionInterface(messageElement) {
        console.log('=== showProductSelectionInterface called ===');
        
        try {
            const buttonsDiv = document.createElement('div');
            buttonsDiv.className = 'interactive-buttons mt-3';
            
            // Create enhanced product selection interface
            buttonsDiv.innerHTML = `
                <h6 class="mb-3"><i class="fas fa-shopping-cart"></i> Select Products for Your Order:</h6>
                <p class="text-muted small mb-3">Click on products to add them to your cart. You can select multiple products.</p>
            `;
            
            // Fetch real product data from database
            const dbProducts = await this.fetchProductData();
            console.log('Fetched products from database:', dbProducts);
            
            // Check if we have product data
            if (!dbProducts || dbProducts.length === 0) {
                buttonsDiv.innerHTML = `
                    <div class="alert alert-warning">
                        <h6><i class="fas fa-exclamation-triangle"></i> Unable to Load Products</h6>
                        <p class="mb-2">There was an error loading product information. Please try refreshing the page or contact support.</p>
                        <button class="btn btn-outline-primary btn-sm" onclick="location.reload()">
                            <i class="fas fa-refresh"></i> Refresh Page
                        </button>
                    </div>
                `;
                messageElement.appendChild(buttonsDiv);
                return;
            }
            
            // Convert database products to interface format
            const products = dbProducts.map(dbProduct => ({
                name: dbProduct.product_name,
                code: dbProduct.product_code,
                price: dbProduct.price_of_product.toFixed(2),
                available: dbProduct.available_for_sale.toString()
            }));
            
            console.log('Converted products for interface:', products);
            
            products.forEach((product, index) => {
                console.log(`Creating selectable button ${index + 1} for:`, product.name);
                const button = document.createElement('button');
                button.className = `btn btn-outline-primary btn-sm me-2 mb-2 product-select-btn ${product.available === '0' ? 'disabled' : ''}`;
                button.id = `product-${product.code}`;
                button.innerHTML = `
                    <div class="product-info">
                        <strong>${product.name}</strong><br>
                        <small>${product.code} - $${product.price}</small><br>
                        <span class="badge ${product.available === '0' ? 'bg-danger' : 'bg-success'}">${product.available === '0' ? 'Out of Stock' : `Available: ${product.available}`}</span>
                    </div>
                `;
                button.onclick = () => this.toggleProductSelection(product);
                button.disabled = product.available === '0';
                buttonsDiv.appendChild(button);
            });
            
            // Add cart summary and action buttons
            const cartDiv = document.createElement('div');
            cartDiv.className = 'cart-summary mt-3';
            cartDiv.innerHTML = `
                <div class="alert alert-info">
                    <h6><i class="fas fa-shopping-cart"></i> Your Cart:</h6>
                    <div id="cart-items">No products selected</div>
                    <div class="mt-2">
                        <button id="add-to-cart-btn" class="btn btn-success btn-sm me-2" disabled>
                            <i class="fas fa-plus"></i> Add Selected to Cart
                        </button>
                        <button id="clear-cart-btn" class="btn btn-outline-secondary btn-sm">
                            <i class="fas fa-trash"></i> Clear Cart
                        </button>
                    </div>
                </div>
            `;
            buttonsDiv.appendChild(cartDiv);
            
            // Add event listeners for cart actions
            const addToCartBtn = cartDiv.querySelector('#add-to-cart-btn');
            const clearCartBtn = cartDiv.querySelector('#clear-cart-btn');
            
            addToCartBtn.onclick = () => this.addSelectedProductsToCart();
            clearCartBtn.onclick = () => this.clearCart();
            
            // Append buttons to the message element
            messageElement.appendChild(buttonsDiv);
            messageElement.scrollIntoView({ behavior: 'smooth' });
            
            // Restore button states and cart display after DOM is ready
            setTimeout(() => {
                this.cartState.items.forEach(item => {
                    this.updateProductButtonState(item.code, true);
                });
                this.updateCartDisplay();
            }, 100);
            
        } catch (error) {
            console.error('Error in showProductSelectionInterface:', error);
        }
    }

    async fetchProductData() {
        try {
            console.log('Fetching real product data from database');
            
            const response = await fetch('/chat/api/products', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const productData = await response.json();
            console.log('Product data received:', productData);
            
            return productData.products || [];
        } catch (error) {
            console.error('Error fetching product data:', error);
            return [];
        }
    }

    async toggleProductSelection(product) {
        const existingIndex = this.cartState.items.findIndex(p => p.code === product.code);
        
        if (existingIndex > -1) {
            // Remove from selection
            this.cartState.items.splice(existingIndex, 1);
            this.updateProductButtonState(product.code, false);
        } else {
            // Add to selection with default quantity 1
            this.cartState.items.push({
                ...product,
                quantity: 1
            });
            this.updateProductButtonState(product.code, true);
        }
        
        this.updateCartDisplay();
        
        // Immediately sync with backend when products are selected/deselected
        if (this.cartState.items.length > 0) {
            try {
                console.log('Syncing selected products with backend:', this.cartState.items);
                const response = await fetch('/chat/api/update-cart', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify({ 
                        selected_products: this.cartState.items,
                        action: 'update_cart'
                    })
                });
                
                if (response.ok) {
                    console.log('Cart synced successfully with backend');
                } else {
                    console.error('Failed to sync cart with backend');
                }
            } catch (error) {
                console.error('Error syncing cart with backend:', error);
            }
        }
    }

    updateProductButtonState(productCode, isSelected) {
        const button = document.getElementById(`product-${productCode}`);
        if (button) {
            if (isSelected) {
                button.classList.remove('btn-outline-primary');
                button.classList.add('btn-primary');
            } else {
                button.classList.remove('btn-primary');
                button.classList.add('btn-outline-primary');
            }
        }
    }

    async updateCartDisplay() {
        const cartItemsDiv = document.getElementById('cart-items');
        const addToCartBtn = document.getElementById('add-to-cart-btn');
        
        if (!cartItemsDiv || !addToCartBtn) return;
        
        if (this.cartState.items.length === 0) {
            cartItemsDiv.innerHTML = 'No products selected';
            addToCartBtn.disabled = true;
        } else {
            try {
                // Fetch dynamic pricing
                const pricingData = await this.fetchProductPricing(this.cartState.items);
                let cartHTML = '';
                let totalAmount = 0;
                
                this.cartState.items.forEach((product, index) => {
                    const pricing = pricingData.pricing.find(p => p.product_code === product.code);
                    const basePrice = pricing ? pricing.base_price : parseFloat(product.price.replace(',', ''));
                    const finalPrice = pricing ? pricing.final_price : basePrice;
                    const discount = pricing ? pricing.discount_percentage : 0;
                    const discountAmount = pricing ? pricing.discount_amount : 0;
                    const scheme = pricing ? pricing.scheme_name : null;
                    const itemTotal = pricing ? pricing.total_amount : (finalPrice * product.quantity);
                    const totalQuantity = pricing ? pricing.total_quantity : product.quantity;
                    const paidQuantity = pricing ? pricing.paid_quantity : product.quantity;
                    const freeQuantity = pricing ? pricing.free_quantity : 0;
                    
                    totalAmount += itemTotal;
                    
                    cartHTML += `
                        <div class="cart-item mb-3 p-2 border rounded ${freeQuantity > 0 ? 'border-success' : ''}">
                            ${freeQuantity > 0 ? `
                                <div class="alert alert-success alert-sm mb-2 p-2">
                                    <strong><i class="fas fa-gift"></i> FOC Applied!</strong> You'll get <strong>${freeQuantity} free units</strong> with this order!
                                </div>
                            ` : ''}
                            <div class="d-flex justify-content-between align-items-center mb-2">
                                <div>
                                    <strong>${product.name}</strong> (${product.code})<br>
                                    <small class="text-muted">
                                        Ordered: ${product.quantity} units
                                        ${freeQuantity > 0 ? `<br><span class="text-success"><i class="fas fa-gift"></i> Free: ${freeQuantity} units</span>` : ''}
                                        ${freeQuantity > 0 ? `<br><strong>Total You'll Receive: ${totalQuantity} units</strong>` : ''}
                                    </small>
                                </div>
                                <div class="d-flex align-items-center">
                                    <button class="btn btn-sm btn-outline-secondary me-1" onclick="cartManager.decreaseQuantity(${index})">-</button>
                                    <span class="mx-2">${product.quantity}</span>
                                    <button class="btn btn-sm btn-outline-secondary me-2" onclick="cartManager.increaseQuantity(${index}, ${product.available})">+</button>
                                    <button class="btn btn-sm btn-outline-danger" onclick="cartManager.removeProduct(${index})">×</button>
                                </div>
                            </div>
                            <div class="pricing-details">
                                <div class="d-flex justify-content-between">
                                    <span>Base Price:</span>
                                    <span>$${basePrice.toFixed(2)} each</span>
                                </div>
                                ${discount > 0 ? `
                                    <div class="d-flex justify-content-between text-success">
                                        <span><i class="fas fa-tag"></i> Discount (${discount}%):</span>
                                        <span>-$${discountAmount.toFixed(2)} each</span>
                                    </div>
                                ` : ''}
                                ${scheme ? `
                                    <div class="d-flex justify-content-between text-info">
                                        <span><i class="fas fa-gift"></i> Scheme:</span>
                                        <span>${scheme}</span>
                                    </div>
                                ` : ''}
                                <div class="d-flex justify-content-between fw-bold">
                                    <span>Final Price:</span>
                                    <span>$${finalPrice.toFixed(2)} each</span>
                                </div>
                                ${freeQuantity > 0 ? `
                                    <div class="d-flex justify-content-between text-warning">
                                        <span><i class="fas fa-gift"></i> You Pay For:</span>
                                        <span>${paidQuantity} items</span>
                                    </div>
                                ` : ''}
                                <div class="d-flex justify-content-between fw-bold text-primary">
                                    <span>Item Total:</span>
                                    <span>$${itemTotal.toFixed(2)}</span>
                                </div>
                            </div>
                        </div>
                    `;
                });
                
                // Add total summary
                cartHTML += `
                    <div class="total-summary mt-3 p-2 bg-light rounded">
                        <div class="d-flex justify-content-between fw-bold h5">
                            <span>Total Amount:</span>
                            <span class="text-success">$${totalAmount.toFixed(2)}</span>
                        </div>
                    </div>
                `;
                
                cartItemsDiv.innerHTML = cartHTML;
                addToCartBtn.disabled = false;
            } catch (error) {
                console.error('Error updating cart display:', error);
                // Fallback to simple display
                let cartHTML = '';
                this.cartState.items.forEach((product, index) => {
                    cartHTML += `
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <div>
                                <strong>${product.name}</strong> (${product.code})<br>
                                <small class="text-muted">$${product.price} each</small>
                            </div>
                            <div class="d-flex align-items-center">
                                <button class="btn btn-sm btn-outline-secondary me-1" onclick="cartManager.decreaseQuantity(${index})">-</button>
                                <span class="mx-2">${product.quantity}</span>
                                <button class="btn btn-sm btn-outline-secondary me-2" onclick="cartManager.increaseQuantity(${index}, ${product.available})">+</button>
                                <button class="btn btn-sm btn-outline-danger" onclick="cartManager.removeProduct(${index})">×</button>
                            </div>
                        </div>
                    `;
                });
                cartItemsDiv.innerHTML = cartHTML;
                addToCartBtn.disabled = false;
            }
        }
    }

    async fetchProductPricing(products) {
        try {
            const productCodes = products.map(p => p.code);
            console.log('Fetching pricing for products:', productCodes);
            
            const response = await fetch('/chat/api/pricing', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ 
                    product_codes: productCodes,
                    quantities: products.map(p => p.quantity)
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const pricingData = await response.json();
            console.log('Pricing data received:', pricingData);
            
            // Cache the pricing data
            if (pricingData.pricing) {
                pricingData.pricing.forEach(item => {
                    this.productPricing[item.product_code] = item;
                });
            }
            
            return pricingData;
        } catch (error) {
            console.error('Error fetching pricing:', error);
            // Return fallback pricing if API fails
            return {
                pricing: products.map(product => ({
                    product_code: product.code,
                    base_price: parseFloat(product.price.replace(',', '')),
                    final_price: parseFloat(product.price.replace(',', '')),
                    discount_percentage: 0,
                    discount_amount: 0,
                    scheme_name: null,
                    total_amount: parseFloat(product.price.replace(',', '')) * product.quantity,
                    total_quantity: product.quantity,
                    paid_quantity: product.quantity,
                    free_quantity: 0
                }))
            };
        }
    }

    async increaseQuantity(index, maxAvailable) {
        if (this.cartState.items[index].quantity < maxAvailable) {
            this.cartState.items[index].quantity++;
            await this.updateCartDisplay();
            
            // Check for FOC eligibility and show notification
            await this.checkAndNotifyFOC(index);
            
            // Sync with backend
            await this.syncCartWithBackend();
        }
    }

    async decreaseQuantity(index) {
        if (this.cartState.items[index].quantity > 1) {
            this.cartState.items[index].quantity--;
            await this.updateCartDisplay();
            
            // Check for FOC eligibility and show notification
            await this.checkAndNotifyFOC(index);
            
            // Sync with backend
            await this.syncCartWithBackend();
        }
    }
    
    async checkAndNotifyFOC(index) {
        /** Check if quantity matches FOC thresholds and show notification */
        try {
            const product = this.cartState.items[index];
            const quantity = product.quantity;
            
            // Fetch pricing to get FOC information
            const pricingData = await this.fetchProductPricing([product]);
            const pricing = pricingData.pricing.find(p => p.product_code === product.code);
            
            if (pricing && pricing.free_quantity > 0) {
                // Show FOC notification
                this.showFOCNotification(product, pricing);
            }
        } catch (error) {
            console.error('Error checking FOC:', error);
        }
    }
    
    showFOCNotification(product, pricing) {
        /** Show FOC notification when quantity matches thresholds */
        // Remove existing notification for this product
        const existingNotification = document.getElementById(`foc-notification-${product.code}`);
        if (existingNotification) {
            existingNotification.remove();
        }
        
        if (pricing.free_quantity > 0) {
            const messagesDiv = document.getElementById('chatMessages');
            const notificationDiv = document.createElement('div');
            notificationDiv.id = `foc-notification-${product.code}`;
            notificationDiv.className = 'alert alert-success alert-dismissible fade show mt-2';
            notificationDiv.innerHTML = `
                <strong><i class="fas fa-gift"></i> Free Product Alert!</strong><br>
                You've selected <strong>${pricing.paid_quantity} units</strong> of <strong>${product.name}</strong>.<br>
                <strong>You'll receive ${pricing.free_quantity} free units!</strong> (Total: ${pricing.total_quantity} units)<br>
                <small class="text-muted">Scheme: ${pricing.scheme_name || 'FOC Scheme Applied'}</small>
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            `;
            
            // Append to last bot message or create new notification area
            const lastBotMessage = messagesDiv.querySelector('.message.bot:last-child');
            if (lastBotMessage) {
                lastBotMessage.appendChild(notificationDiv);
            } else {
                messagesDiv.appendChild(notificationDiv);
            }
            
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
            
            // Auto-remove after 10 seconds
            setTimeout(() => {
                if (notificationDiv.parentNode) {
                    notificationDiv.remove();
                }
            }, 10000);
        }
    }

    // Sync cart with backend
    async syncCartWithBackend() {
        if (this.cartState.items.length > 0) {
            try {
                console.log('Syncing cart with backend:', this.cartState.items);
                const response = await fetch('/chat/api/update-cart', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify({ 
                        selected_products: this.cartState.items,
                        action: 'update_cart'
                    })
                });
                
                if (response.ok) {
                    console.log('Cart synced successfully with backend');
                } else {
                    console.error('Failed to sync cart with backend');
                }
            } catch (error) {
                console.error('Error syncing cart with backend:', error);
            }
        }
    }

    async removeProduct(index) {
        const product = this.cartState.items[index];
        this.cartState.items.splice(index, 1);
        this.updateProductButtonState(product.code, false);
        this.updateCartDisplay();
        
        // Sync with backend
        await this.syncCartWithBackend();
    }

    clearCart() {
        // Reset all product buttons
        this.cartState.items.forEach(product => {
            this.updateProductButtonState(product.code, false);
        });
        this.cartState.items = [];
        this.updateCartDisplay();
    }

    async addSelectedProductsToCart() {
        if (this.cartState.items.length === 0) return;
        
        // Remove existing interactive buttons
        this.clearExistingInteractiveButtons();
        
        // First, send the selected products to the backend to update the cart
        try {
            console.log('Sending selected products to backend:', this.cartState.items);
            const response = await fetch('/chat/api/update-cart', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ 
                    selected_products: this.cartState.items,
                    action: 'update_cart'
                })
            });
            
            if (response.ok) {
                console.log('Cart updated successfully in backend');
            } else {
                console.error('Failed to update cart in backend');
            }
        } catch (error) {
            console.error('Error updating cart in backend:', error);
        }
        
        // Create order summary with dynamic pricing
        const messagesDiv = document.getElementById('chatMessages');
        const orderSummaryDiv = document.createElement('div');
        orderSummaryDiv.className = 'order-summary mt-3';
        
        try {
            // Fetch dynamic pricing
            const pricingData = await this.fetchProductPricing(this.cartState.items);
            let totalPrice = 0;
            let orderText = 'I would like to order:\n';
            
            let orderSummaryHTML = `
                <div class="alert alert-success">
                    <h6><i class="fas fa-check-circle"></i> Order Summary:</h6>
                    <div class="mb-2">
            `;
            
            this.cartState.items.forEach((product, index) => {
                const pricing = pricingData.pricing.find(p => p.product_code === product.code);
                const basePrice = parseFloat(product.price.replace(',', ''));
                const finalPrice = pricing ? pricing.final_price : basePrice;
                const discount = pricing ? pricing.discount_percentage : 0;
                const discountAmount = pricing ? pricing.discount_amount : 0;
                const scheme = pricing ? pricing.scheme_name : null;
                const itemTotal = pricing ? pricing.total_amount : (finalPrice * product.quantity);
                const totalQuantity = pricing ? pricing.total_quantity : product.quantity;
                const paidQuantity = pricing ? pricing.paid_quantity : product.quantity;
                const freeQuantity = pricing ? pricing.free_quantity : 0;
                
                totalPrice += itemTotal;
                orderText += `- ${product.quantity}x ${product.name} (${product.code}) ${freeQuantity > 0 ? `+ ${freeQuantity} free` : ''} - $${itemTotal.toFixed(2)}\n`;
                
                orderSummaryHTML += `
                    <div class="order-item mb-3 p-2 border rounded">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <div>
                                <strong>${totalQuantity}x ${product.name}</strong><br>
                                <small class="text-muted">${product.code} ${freeQuantity > 0 ? `(${freeQuantity} free)` : ''}</small>
                            </div>
                            <div class="text-end">
                                <div class="fw-bold text-primary">$${itemTotal.toFixed(2)}</div>
                            </div>
                        </div>
                        <div class="pricing-breakdown small">
                            <div class="d-flex justify-content-between">
                                <span>Base Price:</span>
                                <span>$${basePrice.toFixed(2)} each</span>
                            </div>
                            ${discount > 0 ? `
                                <div class="d-flex justify-content-between text-success">
                                    <span><i class="fas fa-tag"></i> Discount (${discount}%):</span>
                                    <span>-$${discountAmount.toFixed(2)} each</span>
                                </div>
                            ` : ''}
                            ${scheme ? `
                                <div class="d-flex justify-content-between text-info">
                                    <span><i class="fas fa-gift"></i> Scheme:</span>
                                    <span>${scheme}</span>
                                </div>
                            ` : ''}
                            <div class="d-flex justify-content-between fw-bold">
                                <span>Final Price:</span>
                                <span>$${finalPrice.toFixed(2)} each</span>
                            </div>
                            ${freeQuantity > 0 ? `
                                <div class="d-flex justify-content-between text-warning">
                                    <span><i class="fas fa-gift"></i> You Pay For:</span>
                                    <span>${paidQuantity} items</span>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                `;
            });
            
            orderText += `\nTotal: $${totalPrice.toFixed(2)}`;
            
            orderSummaryHTML += `
                    </div>
                    <hr>
                    <div class="d-flex justify-content-between fw-bold h5">
                        <span>Total Amount:</span>
                        <span class="text-success">$${totalPrice.toFixed(2)}</span>
                    </div>
                    <div class="mt-3">
                        <button class="btn btn-success btn-sm me-2" onclick="cartManager.confirmOrder()">
                            <i class="fas fa-check"></i> Confirm Order
                        </button>
                        <button class="btn btn-outline-secondary btn-sm" onclick="cartManager.modifyOrder()">
                            <i class="fas fa-edit"></i> Modify Order
                        </button>
                    </div>
                </div>
            `;
            
            orderSummaryDiv.innerHTML = orderSummaryHTML;
            messagesDiv.appendChild(orderSummaryDiv);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
            
        } catch (error) {
            console.error('Error creating order summary:', error);
            // Fallback to simple summary
            let totalPrice = 0;
            let orderText = 'I would like to order:\n';
            
            this.cartState.items.forEach(product => {
                const productTotal = parseFloat(product.price.replace(',', '')) * product.quantity;
                totalPrice += productTotal;
                orderText += `- ${product.quantity}x ${product.name} (${product.code}) - $${productTotal.toFixed(2)}\n`;
            });
            
            orderText += `\nTotal: $${totalPrice.toFixed(2)}`;
            
            orderSummaryDiv.innerHTML = `
                <div class="alert alert-success">
                    <h6><i class="fas fa-check-circle"></i> Order Summary:</h6>
                    <div class="mb-2">
                        ${this.cartState.items.map(product => `
                            <div class="d-flex justify-content-between">
                                <span>${product.quantity}x ${product.name} (${product.code})</span>
                                <span>$${(parseFloat(product.price.replace(',', '')) * product.quantity).toFixed(2)}</span>
                            </div>
                        `).join('')}
                        <hr>
                        <div class="d-flex justify-content-between fw-bold">
                            <span>Total:</span>
                            <span>$${totalPrice.toFixed(2)}</span>
                        </div>
                    </div>
                    <div class="mt-2">
                        <button class="btn btn-success btn-sm me-2" onclick="cartManager.confirmOrder()">
                            <i class="fas fa-check"></i> Confirm Order
                        </button>
                        <button class="btn btn-outline-secondary btn-sm" onclick="cartManager.modifyOrder()">
                            <i class="fas fa-edit"></i> Modify Order
                        </button>
                    </div>
                </div>
            `;
            
            messagesDiv.appendChild(orderSummaryDiv);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }
    }

    async confirmOrder() {
        // Remove order summary
        const orderSummary = document.querySelector('.order-summary');
        if (orderSummary) orderSummary.remove();
        
        // Send the selected products to the backend first
        if (this.cartState.items.length > 0) {
            try {
                // Send selected products to backend to update order session
                const response = await fetch('/chat/api/update-cart', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify({ 
                        selected_products: this.cartState.items,
                        action: 'update_cart'
                    })
                });
                
                if (response.ok) {
                    console.log('Cart updated successfully');
                } else {
                    console.error('Failed to update cart');
                }
            } catch (error) {
                console.error('Error updating cart:', error);
            }
        }
        
        // Send professional order confirmation message
        let orderMessage = 'I would like to confirm my order. Please process the items in my cart.';
        
        // Clear cart state after confirming order
        this.cartState.items = [];
        
        document.getElementById('messageInput').value = orderMessage.trim();
        this.sendMessage();
    }

    async modifyOrder() {
        // Remove order summary
        const orderSummary = document.querySelector('.order-summary');
        if (orderSummary) orderSummary.remove();
        
        // Show product selection again with refreshed data
        const messagesDiv = document.getElementById('chatMessages');
        const lastBotMessage = messagesDiv.querySelectorAll('.message.bot')[messagesDiv.querySelectorAll('.message.bot').length - 1];
        if (lastBotMessage) {
            // Clear any existing product selection interface
            this.clearExistingInteractiveButtons();
            // Show fresh product selection with current quantities
            await this.showProductSelectionInterface(lastBotMessage);
        }
    }

    loadCartState() {
        // Load cart state from session storage if available
        const savedState = sessionStorage.getItem('cartState');
        if (savedState) {
            try {
                this.cartState = JSON.parse(savedState);
            } catch (error) {
                console.error('Error loading cart state:', error);
            }
        }
    }

    saveCartState() {
        // Save cart state to session storage
        try {
            sessionStorage.setItem('cartState', JSON.stringify(this.cartState));
        } catch (error) {
            console.error('Error saving cart state:', error);
        }
    }

    showWarehouseOptions(warehouseOptions) {
        const messagesDiv = document.getElementById('chatMessages');
        const optionsDiv = document.createElement('div');
        optionsDiv.className = 'warehouse-options mt-3';
        optionsDiv.innerHTML = '<p class="mb-2"><strong>Select your warehouse location:</strong></p>';
        
        warehouseOptions.forEach(warehouse => {
            const button = document.createElement('button');
            button.className = 'btn btn-outline-primary btn-sm me-2 mb-2';
            button.textContent = warehouse;
            button.onclick = () => this.selectWarehouse(warehouse);
            optionsDiv.appendChild(button);
        });
        
        messagesDiv.appendChild(optionsDiv);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }

    selectWarehouse(warehouse) {
        // Remove warehouse options
        const optionsDiv = document.querySelector('.warehouse-options');
        if (optionsDiv) optionsDiv.remove();
        
        // Send warehouse selection
        document.getElementById('messageInput').value = warehouse;
        this.sendMessage();
    }
}

// Initialize the enhanced cart manager
let cartManager;

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    cartManager = new EnhancedCartManager();
    
    // Load conversation history
    loadConversationHistory();
});

async function loadConversationHistory() {
    try {
        const response = await fetch('/chat/history');
        const data = await response.json();
        
        if (data.conversations && data.conversations.length > 0) {
            // Show last 10 conversations
            data.conversations.slice(0, 10).reverse().forEach(conv => {
                cartManager.addMessage(conv.user_message, 'user');
                cartManager.addMessage(conv.bot_response, 'bot', conv.data_sources);
            });
        }
    } catch (error) {
        console.error('Failed to load history:', error);
    }
}

// Global functions for backward compatibility
function sendMessage() {
    if (cartManager) {
        cartManager.sendMessage();
    }
}

function clearChat() {
    if (!confirm('Export and email the conversation to you and the admin, then delete it?')) return;
    
    fetch('/chat/clear', {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(response => response.json())
    .then(data => {
        if (response.ok) {
            showNotification('Conversation exported and cleared.', 'success');
        } else {
            throw new Error(data.error || 'Failed to clear');
        }
    })
    .catch(e => {
        console.error('Clear error:', e);
        showNotification('Failed to export and clear conversation.', 'error');
    });
    
    const messagesDiv = document.getElementById('chatMessages');
    messagesDiv.innerHTML = `
        <div class="text-center text-muted py-5">
            <i class="fas fa-robot fa-3x mb-3"></i>
            <p>Chat cleared! How can I help you today?</p>
        </div>
    `;
    cartManager.messageHistory = [];
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show position-fixed`;
    notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(notification);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 5000);
}
