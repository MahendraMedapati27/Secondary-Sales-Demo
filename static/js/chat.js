let isProcessing = false;
let messageHistory = [];
let selectedProducts = []; // Track selected products for multi-selection
let cartState = {}; // Store cart state for persistence
let productPricing = {}; // Cache for product pricing data

// Send message on Enter key
document.getElementById('messageInput').addEventListener('keypress', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

// Add input validation
document.getElementById('messageInput').addEventListener('input', function(e) {
    const sendButton = document.getElementById('sendButton');
    const message = e.target.value.trim();
    sendButton.disabled = !message || isProcessing;
});

async function sendMessage() {
    if (isProcessing) return;
    
    const input = document.getElementById('messageInput');
    const message = input.value.trim();
    
    if (!message) return;
    
    // Clear input and disable
    input.value = '';
    isProcessing = true;
    toggleUI(false);
    
    // Add user message to chat
    addMessage(message, 'user');
    
    // Show typing indicator with animation
    showTypingIndicator();
    
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
            addMessage(`Error: ${data.error}`, 'bot', [], 'error');
        } else {
            // Handle warehouse options for onboarding
            if (data.warehouse_options) {
                addMessage(data.response, 'bot');
                showWarehouseOptions(data.warehouse_options);
            } else {
                // Update the last user message if clean message is available
                if (data.user_message) {
                    const messagesDiv = document.getElementById('chatMessages');
                    const lastUserMessage = messagesDiv.querySelector('.message.user:last-child');
                    if (lastUserMessage) {
                        const bubble = lastUserMessage.querySelector('.message-bubble');
                        if (bubble) {
                            bubble.innerHTML = formatMessage(data.user_message);
                        }
                    }
                }
                
                addMessage(data.response, 'bot', data.data_sources);
                
                // Show intent classification if available
                if (data.intent) {
                    showIntentInfo(data.intent, data.confidence);
                }
                
                // Debug: Log the full response data
                console.log('Full response data:', data);
                
                // Check for interactive elements in the response
                console.log('About to call parseInteractiveElements with:', { intent: data.intent, responseLength: data.response.length });
                parseInteractiveElements(data.response, data.intent);
                console.log('parseInteractiveElements call completed');
                
                // Debug: Log when we should show buttons
                if (data.intent === 'PLACE_ORDER') {
                    console.log('PLACE_ORDER intent detected, checking for products...');
                    // Products are now dynamically loaded from database
                    console.log('Response received, checking for product information...');
                }
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
        
        addMessage(errorMessage, 'bot', [], 'error');
    } finally {
        hideTypingIndicator();
        isProcessing = false;
        toggleUI(true);
        input.focus();
    }
}

function addMessage(text, sender, sources = [], messageType = 'normal') {
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
    bubble.innerHTML = formatMessage(text);
    
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
    messageHistory.push({
        text: text,
        sender: sender,
        timestamp: new Date(),
        sources: sources
    });
}

function formatMessage(text) {
    // Convert markdown tables to HTML
    if (text.includes('|')) {
        text = convertMarkdownTable(text);
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
        text = text.replace(/Total Amount: \$([0-9,]+\.?\d*)/g, '<div class="alert alert-warning mb-2"><strong><i class="fas fa-dollar-sign"></i> Total Amount:</strong> <span class="h5 text-success">$$1</span></div>');
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

function convertMarkdownTable(text) {
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

function toggleUI(enabled) {
    document.getElementById('messageInput').disabled = !enabled;
    document.getElementById('sendButton').disabled = !enabled;
}

function showTypingIndicator() {
    const indicator = document.getElementById('typingIndicator');
    indicator.style.display = 'block';
    indicator.innerHTML = '<i class="fas fa-circle-notch fa-spin"></i> AI is thinking...';
}

function hideTypingIndicator() {
    const indicator = document.getElementById('typingIndicator');
    indicator.style.display = 'none';
}

async function clearChat() {
    if (!confirm('Export and email the conversation to you and the admin, then delete it?')) return;
    try {
        const response = await fetch('/chat/clear', {
            method: 'POST',
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || 'Failed to clear');
        }
        showNotification('Conversation exported and cleared.', 'success');
    } catch (e) {
        console.error('Clear error:', e);
        showNotification('Failed to export and clear conversation.', 'error');
    }
    const messagesDiv = document.getElementById('chatMessages');
    messagesDiv.innerHTML = `
        <div class="text-center text-muted py-5">
            <i class="fas fa-robot fa-3x mb-3"></i>
            <p>Chat cleared! How can I help you today?</p>
        </div>
    `;
    messageHistory = [];
}

// exportConversation removed; handled by clearChat

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

// Show warehouse options during onboarding
function showWarehouseOptions(warehouseOptions) {
    const messagesDiv = document.getElementById('chatMessages');
    const optionsDiv = document.createElement('div');
    optionsDiv.className = 'warehouse-options mt-3';
    optionsDiv.innerHTML = '<p class="mb-2"><strong>Select your warehouse location:</strong></p>';
    
    warehouseOptions.forEach(warehouse => {
        const button = document.createElement('button');
        button.className = 'btn btn-outline-primary btn-sm me-2 mb-2';
        button.textContent = warehouse;
        button.onclick = () => selectWarehouse(warehouse);
        optionsDiv.appendChild(button);
    });
    
    messagesDiv.appendChild(optionsDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function selectWarehouse(warehouse) {
    // Remove warehouse options
    const optionsDiv = document.querySelector('.warehouse-options');
    if (optionsDiv) optionsDiv.remove();
    
    // Send warehouse selection
    document.getElementById('messageInput').value = warehouse;
    sendMessage();
}

// Show intent classification info
function showIntentInfo(intent, confidence) {
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

// Parse interactive elements from bot response
function parseInteractiveElements(response, intent) {
    console.log('=== parseInteractiveElements called ===');
    console.log('Intent:', intent);
    console.log('Response length:', response.length);
    
    const messagesDiv = document.getElementById('chatMessages');
    
    // Find the last bot message (not intent-info or other elements)
    const allMessages = messagesDiv.querySelectorAll('.message.bot');
    const lastBotMessage = allMessages[allMessages.length - 1];
    
    console.log('Messages div:', messagesDiv);
    console.log('All bot messages found:', allMessages.length);
    console.log('Last bot message:', lastBotMessage);
    console.log('Last bot message classes:', lastBotMessage ? lastBotMessage.classList : 'null');
    
    if (!lastBotMessage) {
        console.log('Early return: no bot message found');
        return;
    }
    
    console.log('Parsing interactive elements for intent:', intent);
    console.log('Response preview:', response.substring(0, 200) + '...');
    
    // Remove any existing interactive buttons first
    clearExistingInteractiveButtons();
    
    // Debug: Check what patterns are found in the response
    console.log('Checking response patterns:');
    console.log('Contains Quick Product Selection:', response.includes('Quick Product Selection'));
    console.log('Contains Available:', response.includes('Available:'));
    console.log('Contains QB:', response.includes('QB'));
    // Products are now dynamically loaded from database - no hardcoded checks needed
    console.log('Checking response for product information...');
    console.log('Contains AI:', response.includes('AI'));
    
        // Show product selection for PLACE_ORDER intent when user wants to place order
        if (intent === 'PLACE_ORDER' && (
            response.includes('select') || 
            response.includes('choose') || 
            response.includes('available products') ||
            response.includes('Quick Product Selection') ||
            response.includes('which products') ||
            response.includes('what products') ||
            response.includes('product name') ||
            response.includes('quantities') ||
            response.includes('Ready to Place Your Order') ||
            response.includes('Available Products') ||
            response.includes('How to Order') ||
            (response.includes('order') && !response.includes('Order Placed Successfully') &&
            !response.includes('Order ID:') &&
            !response.includes('Total Amount:') &&
            !response.includes('Status:'))
        )) {
            console.log('PLACE_ORDER intent with product selection request - showing product selection buttons');
            showProductSelectionButtonsInline(response, lastBotMessage);
            return;
        }
    
    // Check for product selection patterns - more flexible detection
    if ((intent === undefined || intent === null) && (
        response.includes('Quick Product Selection') || 
        response.includes('🛒') ||
        response.includes('Available:') ||
        response.includes('QB') ||
        response.includes('Quantum') ||
        response.includes('Neural') ||
        response.includes('AI') ||
        response.includes('product name') ||
        response.includes('which products') ||
        response.includes('what you')
    )) {
        console.log('Showing product selection buttons based on content');
        showProductSelectionButtonsInline(response, lastBotMessage);
    } else {
        console.log('Product selection conditions not met');
    }
    
    // Check for order tracking patterns
    if (intent === 'TRACK_ORDER' && response.includes('Order') && response.includes('QB')) {
        showOrderTrackingButtonsInline(response, lastBotMessage);
    } else if (intent === 'TRACK_ORDER' && (response.includes('track') || response.includes('order'))) {
        // Show buttons when bot asks about tracking
        console.log('Bot asking about order tracking - showing buttons');
        showOrderTrackingButtonsInline(response, lastBotMessage);
    }
    
    // Check for quantity selection patterns
    if (response.includes('quantity') && response.includes('units')) {
        showQuantitySelectionButtonsInline(response, lastBotMessage);
    }
}

// Show product selection buttons
function showProductSelectionButtons(response) {
    const messagesDiv = document.getElementById('chatMessages');
    const buttonsDiv = document.createElement('div');
    buttonsDiv.className = 'interactive-buttons mt-3';
    
    // Extract product information dynamically from response
    // Products are now fetched from database - check for product codes or common patterns
    const productLines = response.split('\n').filter(line => 
        line.includes('(') && line.includes(')') || // Product codes in parentheses
        line.includes('$') || // Price information
        line.includes('Available:') || // Stock information
        /RB\d+|BD-\d+|QB\d+/.test(line) // Product code patterns
    );
    
    buttonsDiv.innerHTML = '<h6 class="mb-3"><i class="fas fa-shopping-cart"></i> Quick Product Selection:</h6>';
    
    productLines.forEach((line, index) => {
        // Try multiple regex patterns to match different formats
        let match = line.match(/(\d+)\.\s*(.+?)\s*\((.+?)\)\s*-\s*\$([\d,]+\.?\d*)\s*-\s*Available:\s*(\d+)/);
        if (!match) {
            // Try alternative format without numbering
            match = line.match(/(.+?)\s*\((.+?)\)\s*-\s*\$([\d,]+\.?\d*)\s*-\s*Available:\s*(\d+)/);
            if (match) {
                match = [match[0], '', match[1], match[2], match[3], match[4]]; // Add empty num
            }
        }
        
        if (match) {
            const [, num, name, code, price, available] = match;
            const button = document.createElement('button');
            button.className = `btn btn-outline-primary btn-sm me-2 mb-2 product-btn ${available === '0' ? 'disabled' : ''}`;
            button.innerHTML = `
                <div class="product-info">
                    <strong>${name}</strong><br>
                    <small>${code} - $${price}</small><br>
                    <span class="badge ${available === '0' ? 'bg-danger' : 'bg-success'}">${available === '0' ? 'Out of Stock' : `Available: ${available}`}</span>
                </div>
            `;
            button.onclick = () => selectProduct(name, code, price, available);
            button.disabled = available === '0';
            buttonsDiv.appendChild(button);
        }
    });
    
    messagesDiv.appendChild(buttonsDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

// Clear existing interactive buttons
function clearExistingInteractiveButtons() {
    const existingButtons = document.querySelectorAll('.interactive-buttons');
    existingButtons.forEach(btn => btn.remove());
}

// Fetch real product data from database
async function fetchProductData() {
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
        // Return empty array to force user to refresh or try again
        // This prevents showing incorrect hardcoded quantities
        return [];
    }
}

// Fetch real-time pricing for products
async function fetchProductPricing(products) {
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
                productPricing[item.product_code] = item;
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

// Calculate total price with dynamic pricing
async function calculateTotalPrice(products) {
    if (products.length === 0) return 0;
    
    try {
        const pricingData = await fetchProductPricing(products);
        let total = 0;
        
        products.forEach(product => {
            const pricing = pricingData.pricing.find(p => p.product_code === product.code);
            if (pricing) {
                total += pricing.total_amount;
            } else {
                // Fallback to base price if no pricing data
                total += parseFloat(product.price.replace(',', '')) * product.quantity;
            }
        });
        
        return total;
    } catch (error) {
        console.error('Error calculating total price:', error);
        // Fallback calculation
        return products.reduce((total, product) => {
            return total + (parseFloat(product.price.replace(',', '')) * product.quantity);
        }, 0);
    }
}

// Show product selection buttons inline with the message
async function showProductSelectionButtonsInline(response, messageElement) {
    console.log('=== showProductSelectionButtonsInline called ===');
    console.log('Response preview:', response.substring(0, 100) + '...');
    console.log('Message element:', messageElement);
    
    try {
        // Restore previous selections if any
        selectedProducts = cartState.selectedProducts || [];
        
        const buttonsDiv = document.createElement('div');
        buttonsDiv.className = 'interactive-buttons mt-3';
        
        // Create multi-product selection interface
        console.log('Creating multi-product selection interface');
        buttonsDiv.innerHTML = `
            <h6 class="mb-3"><i class="fas fa-shopping-cart"></i> Select Products for Your Order:</h6>
            <p class="text-muted small mb-3">Click on products to add them to your cart. You can select multiple products.</p>
        `;
        
        // Fetch real product data from database
        const dbProducts = await fetchProductData();
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
            button.onclick = () => toggleProductSelection(product);
            button.disabled = product.available === '0';
            buttonsDiv.appendChild(button);
            console.log(`Selectable button ${index + 1} created and appended`);
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
        
        addToCartBtn.onclick = () => addSelectedProductsToCart();
        clearCartBtn.onclick = () => clearCart();
        
        // Append buttons to the message element
        console.log('Appending multi-product selection to message element');
        console.log('Buttons div content length:', buttonsDiv.innerHTML.length);
        console.log('Number of elements created:', buttonsDiv.children.length);
        
        if (messageElement) {
            messageElement.appendChild(buttonsDiv);
            messageElement.scrollIntoView({ behavior: 'smooth' });
            console.log('Multi-product selection interface appended successfully');
            
            // Restore button states and cart display after DOM is ready
            setTimeout(() => {
                selectedProducts.forEach(product => {
                    updateProductButtonState(product.code, true);
                });
                updateCartDisplay();
            }, 100);
        } else {
            console.error('Message element is null or undefined');
        }
        
    } catch (error) {
        console.error('Error in showProductSelectionButtonsInline:', error);
    }
}

// Show order tracking buttons inline
function showOrderTrackingButtonsInline(response, messageElement) {
    const buttonsDiv = document.createElement('div');
    buttonsDiv.className = 'interactive-buttons mt-3';
    
    // Extract order IDs from response
    const orderMatches = response.match(/QB[A-Z0-9]+/g);
    
    if (orderMatches && orderMatches.length > 0) {
        buttonsDiv.innerHTML = '<h6 class="mb-3"><i class="fas fa-truck"></i> Select Order to Track:</h6>';
        
        orderMatches.forEach(orderId => {
            const button = document.createElement('button');
            button.className = 'btn btn-outline-info btn-sm me-2 mb-2 order-btn';
            button.innerHTML = `<i class="fas fa-box"></i> ${orderId}`;
            button.onclick = () => trackOrderInline(orderId);
            buttonsDiv.appendChild(button);
        });
    } else {
        // Show generic tracking interface
        buttonsDiv.innerHTML = `
            <h6 class="mb-3"><i class="fas fa-truck"></i> Order Tracking:</h6>
            <div class="alert alert-info">
                <p class="mb-2">Track your orders by providing:</p>
                <div class="d-flex gap-2 flex-wrap">
                    <button class="btn btn-outline-primary btn-sm" onclick="trackByOrderId()">
                        <i class="fas fa-receipt"></i> Order ID
                    </button>
                    <button class="btn btn-outline-primary btn-sm" onclick="trackByEmail()">
                        <i class="fas fa-envelope"></i> Email
                    </button>
                    <button class="btn btn-outline-primary btn-sm" onclick="trackByPhone()">
                        <i class="fas fa-phone"></i> Phone
                    </button>
                </div>
            </div>
        `;
    }
    
    // Append buttons to the message element
    messageElement.appendChild(buttonsDiv);
    messageElement.scrollIntoView({ behavior: 'smooth' });
}

// Track by order ID
function trackByOrderId() {
    const orderId = prompt('Please enter your Order ID (e.g., QB202510245496F4F1):');
    if (orderId) {
        document.getElementById('messageInput').value = `Track order ${orderId}`;
        sendMessage();
    }
}

// Track by email
function trackByEmail() {
    const email = prompt('Please enter your email address:');
    if (email) {
        document.getElementById('messageInput').value = `Track orders for email ${email}`;
        sendMessage();
    }
}

// Track by phone
function trackByPhone() {
    const phone = prompt('Please enter your phone number:');
    if (phone) {
        document.getElementById('messageInput').value = `Track orders for phone ${phone}`;
        sendMessage();
    }
}

// Show quantity selection buttons inline
function showQuantitySelectionButtonsInline(response, messageElement) {
    const buttonsDiv = document.createElement('div');
    buttonsDiv.className = 'interactive-buttons mt-3';
    
    buttonsDiv.innerHTML = '<h6 class="mb-3"><i class="fas fa-calculator"></i> Quick Quantity Selection:</h6>';
    
    const quantities = [1, 5, 10, 25, 50, 100];
    quantities.forEach(qty => {
        const button = document.createElement('button');
        button.className = 'btn btn-outline-secondary btn-sm me-2 mb-2 quantity-btn';
        button.textContent = qty;
        button.onclick = () => selectQuantity(qty);
        buttonsDiv.appendChild(button);
    });
    
    // Append buttons to the message element
    messageElement.appendChild(buttonsDiv);
    messageElement.scrollIntoView({ behavior: 'smooth' });
}

// Toggle product selection for multi-select
async function toggleProductSelection(product) {
    const existingIndex = selectedProducts.findIndex(p => p.code === product.code);
    
    if (existingIndex > -1) {
        // Remove from selection
        selectedProducts.splice(existingIndex, 1);
        updateProductButtonState(product.code, false);
    } else {
        // Add to selection with default quantity 1
        selectedProducts.push({
            ...product,
            quantity: 1
        });
        updateProductButtonState(product.code, true);
    }
    
    // Save state
    cartState.selectedProducts = [...selectedProducts];
    updateCartDisplay();
    
    // Immediately sync with backend when products are selected/deselected
    if (selectedProducts.length > 0) {
        try {
            console.log('Syncing selected products with backend:', selectedProducts);
            const response = await fetch('/chat/api/update-cart', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ 
                    selected_products: selectedProducts,
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

// Update product button visual state
function updateProductButtonState(productCode, isSelected) {
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

// Update cart display with dynamic pricing
async function updateCartDisplay() {
    const cartItemsDiv = document.getElementById('cart-items');
    const addToCartBtn = document.getElementById('add-to-cart-btn');
    
    if (!cartItemsDiv || !addToCartBtn) return;
    
    if (selectedProducts.length === 0) {
        cartItemsDiv.innerHTML = 'No products selected';
        addToCartBtn.disabled = true;
    } else {
        try {
            // Fetch dynamic pricing
            const pricingData = await fetchProductPricing(selectedProducts);
            let cartHTML = '';
            let totalAmount = 0;
            
            selectedProducts.forEach((product, index) => {
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
                    <div class="cart-item mb-3 p-2 border rounded">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <div>
                                <strong>${product.name}</strong> (${product.code})<br>
                                <small class="text-muted">Selected: ${product.quantity} | Total: ${totalQuantity} ${freeQuantity > 0 ? `(You get ${freeQuantity} free)` : ''}</small>
                            </div>
                            <div class="d-flex align-items-center">
                                <button class="btn btn-sm btn-outline-secondary me-1" onclick="decreaseQuantity(${index})">-</button>
                                <span class="mx-2">${product.quantity}</span>
                                <button class="btn btn-sm btn-outline-secondary me-2" onclick="increaseQuantity(${index}, ${product.available})">+</button>
                                <button class="btn btn-sm btn-outline-danger" onclick="removeProduct(${index})">×</button>
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
            selectedProducts.forEach((product, index) => {
                cartHTML += `
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <div>
                            <strong>${product.name}</strong> (${product.code})<br>
                            <small class="text-muted">$${product.price} each</small>
                        </div>
                        <div class="d-flex align-items-center">
                            <button class="btn btn-sm btn-outline-secondary me-1" onclick="decreaseQuantity(${index})">-</button>
                            <span class="mx-2">${product.quantity}</span>
                            <button class="btn btn-sm btn-outline-secondary me-2" onclick="increaseQuantity(${index}, ${product.available})">+</button>
                            <button class="btn btn-sm btn-outline-danger" onclick="removeProduct(${index})">×</button>
                        </div>
                    </div>
                `;
            });
            cartItemsDiv.innerHTML = cartHTML;
            addToCartBtn.disabled = false;
        }
    }
}

// Increase product quantity
async function increaseQuantity(index, maxAvailable) {
    if (selectedProducts[index].quantity < maxAvailable) {
        selectedProducts[index].quantity++;
        cartState.selectedProducts = [...selectedProducts];
        updateCartDisplay();
        
        // Sync with backend
        await syncCartWithBackend();
    }
}

// Decrease product quantity
async function decreaseQuantity(index) {
    if (selectedProducts[index].quantity > 1) {
        selectedProducts[index].quantity--;
        cartState.selectedProducts = [...selectedProducts];
        updateCartDisplay();
        
        // Sync with backend
        await syncCartWithBackend();
    }
}

// Sync cart with backend
async function syncCartWithBackend() {
    if (selectedProducts.length > 0) {
        try {
            console.log('Syncing cart with backend:', selectedProducts);
            const response = await fetch('/chat/api/update-cart', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ 
                    selected_products: selectedProducts,
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

// Remove product from selection
async function removeProduct(index) {
    const product = selectedProducts[index];
    selectedProducts.splice(index, 1);
    updateProductButtonState(product.code, false);
    cartState.selectedProducts = [...selectedProducts];
    updateCartDisplay();
    
    // Sync with backend
    await syncCartWithBackend();
}

// Clear cart
function clearCart() {
    // Reset all product buttons
    selectedProducts.forEach(product => {
        updateProductButtonState(product.code, false);
    });
    selectedProducts = [];
    cartState.selectedProducts = [];
    updateCartDisplay();
}

// Add selected products to cart and proceed
async function addSelectedProductsToCart() {
    if (selectedProducts.length === 0) return;
    
    // Remove existing interactive buttons
    clearExistingInteractiveButtons();
    
    // First, send the selected products to the backend to update the cart
    try {
        console.log('Sending selected products to backend:', selectedProducts);
        const response = await fetch('/chat/api/update-cart', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({ 
                selected_products: selectedProducts,
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
        const pricingData = await fetchProductPricing(selectedProducts);
        let totalPrice = 0;
        let orderText = 'I would like to add these products to my cart:\n';
        
        let orderSummaryHTML = `
            <div class="alert alert-success">
                <h6><i class="fas fa-shopping-cart"></i> Products Added to Cart:</h6>
                <div class="mb-2">
        `;
        
        selectedProducts.forEach((product, index) => {
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
                    <button class="btn btn-success btn-sm me-2" onclick="confirmOrder()">
                        <i class="fas fa-check"></i> Confirm Order
                    </button>
                    <button class="btn btn-outline-secondary btn-sm" onclick="modifyOrder()">
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
        
        selectedProducts.forEach(product => {
            const productTotal = parseFloat(product.price.replace(',', '')) * product.quantity;
            totalPrice += productTotal;
            orderText += `- ${product.quantity}x ${product.name} (${product.code}) - $${productTotal.toFixed(2)}\n`;
        });
        
        orderText += `\nTotal: $${totalPrice.toFixed(2)}`;
        
        orderSummaryDiv.innerHTML = `
            <div class="alert alert-success">
                <h6><i class="fas fa-check-circle"></i> Order Summary:</h6>
                <div class="mb-2">
                    ${selectedProducts.map(product => `
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
                    <button class="btn btn-success btn-sm me-2" onclick="confirmOrder()">
                        <i class="fas fa-check"></i> Confirm Order
                    </button>
                    <button class="btn btn-outline-secondary btn-sm" onclick="modifyOrder()">
                        <i class="fas fa-edit"></i> Modify Order
                    </button>
                </div>
            </div>
        `;
        
        messagesDiv.appendChild(orderSummaryDiv);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }
}

// Update product quantities after selection
async function updateProductQuantities() {
    try {
        const productQuantities = {};
        selectedProducts.forEach(product => {
            productQuantities[product.code] = product.quantity;
        });
        
        const response = await fetch('/chat/api/update-quantities', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({ product_quantities: productQuantities })
        });
        
        if (response.ok) {
            console.log('Product quantities updated successfully');
            // Refresh product data to show updated quantities
            await refreshProductData();
        }
    } catch (error) {
        console.error('Error updating product quantities:', error);
    }
}

// Refresh product data from database
async function refreshProductData() {
    try {
        const dbProducts = await fetchProductData();
        console.log('Refreshed product data:', dbProducts);
        
        // Only update if we have product data and buttons exist
        if (dbProducts && dbProducts.length > 0) {
            // Update product buttons with new quantities
            dbProducts.forEach(dbProduct => {
                const button = document.getElementById(`product-${dbProduct.product_code}`);
                if (button) {
                    const badge = button.querySelector('.badge');
                    if (badge) {
                        const available = dbProduct.available_for_sale;
                        if (available === 0) {
                            badge.className = 'badge bg-danger';
                            badge.textContent = 'Out of Stock';
                            button.disabled = true;
                            button.classList.add('disabled');
                        } else {
                            badge.className = 'badge bg-success';
                            badge.textContent = `Available: ${available}`;
                            button.disabled = false;
                            button.classList.remove('disabled');
                        }
                    }
                }
            });
        }
    } catch (error) {
        console.error('Error refreshing product data:', error);
    }
}

// Confirm order
async function confirmOrder() {
    // Remove order summary
    const orderSummary = document.querySelector('.order-summary');
    if (orderSummary) orderSummary.remove();
    
    // Update product quantities in database
    await updateProductQuantities();
    
    // Send the selected products to the backend first
    if (selectedProducts.length > 0) {
        try {
            // Send selected products to backend to update order session
            const response = await fetch('/chat/api/update-cart', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ 
                    selected_products: selectedProducts,
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
    selectedProducts = [];
    cartState.selectedProducts = [];
    
    // Refresh product data to show updated quantities
    await refreshProductData();
    
    document.getElementById('messageInput').value = orderMessage.trim();
    sendMessage();
}

// Modify order
async function modifyOrder() {
    // Remove order summary
    const orderSummary = document.querySelector('.order-summary');
    if (orderSummary) orderSummary.remove();
    
    // Show product selection again with refreshed data
    const messagesDiv = document.getElementById('chatMessages');
    const lastBotMessage = messagesDiv.querySelectorAll('.message.bot')[messagesDiv.querySelectorAll('.message.bot').length - 1];
    if (lastBotMessage) {
        // Clear any existing product selection interface
        clearExistingInteractiveButtons();
        // Show fresh product selection with current quantities
        await showProductSelectionButtonsInline('', lastBotMessage);
    }
}

// Inline order tracking handler
function trackOrderInline(orderId) {
    // Remove existing interactive buttons
    clearExistingInteractiveButtons();
    
    // Send tracking message
    document.getElementById('messageInput').value = `Track order ${orderId}`;
    sendMessage();
}

// Inline add to cart handler
function addToCartInline(name, code, price) {
    const quantityInput = document.getElementById('quantityInput');
    const quantity = quantityInput ? quantityInput.value : 1;
    
    // Remove quantity selection
    const quantityDiv = document.querySelector('.quantity-selection');
    if (quantityDiv) quantityDiv.remove();
    
    // Send message to bot
    const message = `${quantity} ${name.toLowerCase()}`;
    document.getElementById('messageInput').value = message;
    sendMessage();
}

// Show generic product buttons when specific product list is not detected
async function showGenericProductButtons() {
    const messagesDiv = document.getElementById('chatMessages');
    const buttonsDiv = document.createElement('div');
    buttonsDiv.className = 'interactive-buttons mt-3';
    
    buttonsDiv.innerHTML = '<h6 class="mb-3"><i class="fas fa-shopping-cart"></i> Available Products:</h6>';
    
    // Load products dynamically from API
    try {
        const response = await fetch('/enhanced-chat/api/products');
        if (response.ok) {
            const data = await response.json();
            const products = data.products || [];
            
            if (products.length === 0) {
                buttonsDiv.innerHTML += '<p class="text-muted">No products available at the moment.</p>';
                messagesDiv.appendChild(buttonsDiv);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
                return;
            }
            
            // Display products dynamically
            products.slice(0, 5).forEach(product => {
                const button = document.createElement('button');
                button.className = `btn btn-outline-primary btn-sm me-2 mb-2 product-btn ${product.available_for_sale === 0 ? 'disabled' : ''}`;
                button.innerHTML = `
                    <div class="product-info">
                        <strong>${product.product_name}</strong><br>
                        <small>${product.product_code} - $${(product.sales_price || product.price_of_product || 0).toFixed(2)}</small><br>
                        <span class="badge ${product.available_for_sale === 0 ? 'bg-danger' : 'bg-success'}">${product.available_for_sale === 0 ? 'Out of Stock' : `Available: ${product.available_for_sale}`}</span>
                    </div>
                `;
                button.onclick = () => selectProduct(product.product_name, product.product_code, product.sales_price || product.price_of_product, product.available_for_sale);
                button.disabled = product.available_for_sale === 0;
                buttonsDiv.appendChild(button);
            });
        } else {
            // Fallback: show message that products couldn't be loaded
            buttonsDiv.innerHTML += '<p class="text-muted">Unable to load products. Please try again later.</p>';
        }
    } catch (error) {
        console.error('Error loading products:', error);
        buttonsDiv.innerHTML += '<p class="text-muted">Unable to load products. Please try again later.</p>';
    }
    
    messagesDiv.appendChild(buttonsDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

// Show order tracking buttons
function showOrderTrackingButtons(response) {
    const messagesDiv = document.getElementById('chatMessages');
    const buttonsDiv = document.createElement('div');
    buttonsDiv.className = 'interactive-buttons mt-3';
    
    // Extract order IDs from response
    const orderMatches = response.match(/QB[A-Z0-9]+/g);
    
    if (orderMatches && orderMatches.length > 0) {
        buttonsDiv.innerHTML = '<h6 class="mb-3"><i class="fas fa-truck"></i> Select Order to Track:</h6>';
        
        orderMatches.forEach(orderId => {
            const button = document.createElement('button');
            button.className = 'btn btn-outline-info btn-sm me-2 mb-2 order-btn';
            button.innerHTML = `
                <i class="fas fa-box"></i> ${orderId}
            `;
            button.onclick = () => trackOrder(orderId);
            buttonsDiv.appendChild(button);
        });
        
        messagesDiv.appendChild(buttonsDiv);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }
}

// Show quantity selection buttons
function showQuantitySelectionButtons(response) {
    const messagesDiv = document.getElementById('chatMessages');
    const buttonsDiv = document.createElement('div');
    buttonsDiv.className = 'interactive-buttons mt-3';
    
    buttonsDiv.innerHTML = '<h6 class="mb-3"><i class="fas fa-calculator"></i> Quick Quantity Selection:</h6>';
    
    const quantities = [1, 5, 10, 25, 50, 100];
    quantities.forEach(qty => {
        const button = document.createElement('button');
        button.className = 'btn btn-outline-secondary btn-sm me-2 mb-2 quantity-btn';
        button.textContent = qty;
        button.onclick = () => selectQuantity(qty);
        buttonsDiv.appendChild(button);
    });
    
    messagesDiv.appendChild(buttonsDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

// Product selection handler
function selectProduct(name, code, price, available) {
    if (available === '0') return;
    
    // Remove existing product buttons
    const buttonsDiv = document.querySelector('.interactive-buttons');
    if (buttonsDiv) buttonsDiv.remove();
    
    // Show quantity selection
    const messagesDiv = document.getElementById('chatMessages');
    const quantityDiv = document.createElement('div');
    quantityDiv.className = 'quantity-selection mt-3';
    quantityDiv.innerHTML = `
        <div class="alert alert-info">
            <h6><i class="fas fa-shopping-cart"></i> Selected: ${name} (${code})</h6>
            <p class="mb-2">Price: $${price} | Available: ${available}</p>
            <div class="input-group" style="max-width: 200px;">
                <input type="number" id="quantityInput" class="form-control" min="1" max="${available}" value="1" placeholder="Quantity">
                <button class="btn btn-primary" onclick="addToCart('${name}', '${code}', '${price}')">
                    <i class="fas fa-plus"></i> Add to Cart
                </button>
            </div>
        </div>
    `;
    
    messagesDiv.appendChild(quantityDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

// Quantity selection handler
function selectQuantity(quantity) {
    const quantityInput = document.getElementById('quantityInput');
    if (quantityInput) {
        quantityInput.value = quantity;
    }
}

// Add to cart handler
function addToCart(name, code, price) {
    const quantityInput = document.getElementById('quantityInput');
    const quantity = quantityInput ? quantityInput.value : 1;
    
    // Remove quantity selection
    const quantityDiv = document.querySelector('.quantity-selection');
    if (quantityDiv) quantityDiv.remove();
    
    // Send message to bot
    const message = `${quantity} ${name.toLowerCase()}`;
    document.getElementById('messageInput').value = message;
    sendMessage();
}

// Order tracking handler
function trackOrder(orderId) {
    // Remove order buttons
    const buttonsDiv = document.querySelector('.interactive-buttons');
    if (buttonsDiv) buttonsDiv.remove();
    
    // Send tracking message
    document.getElementById('messageInput').value = `Track order ${orderId}`;
    sendMessage();
}

// Load conversation history on page load
window.addEventListener('load', async function() {
    try {
        const response = await fetch('/chat/history');
        const data = await response.json();
        
        if (data.conversations && data.conversations.length > 0) {
            // Show last 10 conversations
            data.conversations.slice(0, 10).reverse().forEach(conv => {
                addMessage(conv.user_message, 'user');
                addMessage(conv.bot_response, 'bot', conv.data_sources);
            });
        }
        
        // Debug controls removed - buttons now appear contextually
    } catch (error) {
        console.error('Failed to load history:', error);
    }
});

// Debug functions removed - buttons now appear contextually in conversation flow