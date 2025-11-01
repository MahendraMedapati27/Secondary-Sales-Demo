let isProcessing = false;
let messageHistory = [];
let currentUser = null;
let cartItems = [];
let currentOrderSummary = null;
let typingTimeout = null;

// Initialize chat
document.addEventListener('DOMContentLoaded', function() {
    initializeChat();
});

function initializeChat() {
    // Set up event listeners
    document.getElementById('messageInput').addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    document.getElementById('messageInput').addEventListener('input', function(e) {
        const sendButton = document.getElementById('sendButton');
        const message = e.target.value.trim();
        sendButton.disabled = !message || isProcessing;
        
        // Notify avatar that user is typing
        if (window.setUserTyping) {
            window.setUserTyping(true);
        }
        
        // Clear existing timeout
        if (typingTimeout) {
            clearTimeout(typingTimeout);
        }
        
        // Set timeout to stop typing animation after user stops
        typingTimeout = setTimeout(() => {
            if (window.setUserTyping) {
                window.setUserTyping(false);
            }
        }, 1500); // 1.5 seconds after last keystroke
    });

    // Initialize message history
    messageHistory = [];
}

async function sendMessage() {
    if (isProcessing) return;
    
    const input = document.getElementById('messageInput');
    const message = input.value.trim();
    
    if (!message) return;
    
    // Clear input and disable
    input.value = '';
    isProcessing = true;
    toggleUI(false);
    
    // Notify avatar that user stopped typing
    if (window.setUserTyping) {
        window.setUserTyping(false);
    }
    if (typingTimeout) {
        clearTimeout(typingTimeout);
        typingTimeout = null;
    }
    
    // Add user message to chat
    addMessage(message, 'user');
    
    // Jump animation removed - avatar stays in natural standing pose
    
    // Show typing indicator
    showTypingIndicator();
    
    try {
        const response = await fetch('/enhanced-chat/message', {
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
            addMessage(`Error: ${data.error}`, 'bot', 'error');
        } else {
            // Handle user info display
            if (data.user_info) {
                displayUserInfo(data.user_info);
            }
            
            // Add bot response (avatar speaking will be triggered by addMessage)
            addMessage(data.response, 'bot');
            
            // Handle action buttons - REMOVED: No longer showing action buttons
            // if (data.action_buttons) {
            //     showActionButtons(data.action_buttons);
            // }
            
            // Handle cart items
            if (data.cart_items) {
                updateCartDisplay(data.cart_items);
            }
            
            // Handle order summary
            if (data.order_summary) {
                currentOrderSummary = data.order_summary;
            }
            
            // Handle recent orders
            if (data.recent_orders) {
                displayRecentOrders(data.recent_orders);
            }
            
            // Handle order details
            if (data.order_details) {
                displayOrderDetails(data.order_details);
            }
        }
    } catch (error) {
        console.error('Error:', error);
        const errorMsg = 'Sorry, I encountered an error. Please try again.';
        addMessage(errorMsg, 'bot', 'error');
        
        // Don't make avatar speak for errors
    } finally {
        hideTypingIndicator();
        isProcessing = false;
        toggleUI(true);
    }
}

function addMessage(message, sender, type = 'normal') {
    const messagesDiv = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender} mb-3`;
    
    const bubbleDiv = document.createElement('div');
    bubbleDiv.className = `message-bubble ${sender === 'user' ? 'user' : 'bot'}`;
    
    if (sender === 'user') {
        bubbleDiv.innerHTML = `
            <div class="d-flex justify-content-end">
                <div class="bg-primary text-white rounded-3 px-3 py-2" style="max-width: 70%; font-size: 0.875rem;">
                    ${formatMessage(message)}
                </div>
            </div>
        `;
    } else {
        const alertClass = type === 'error' ? 'alert-danger' : 'alert-info';
        // Check if message contains a table - if so, use wider max-width
        const hasTable = message.includes('|') && message.includes('---');
        const maxWidth = hasTable ? '95%' : '70%';
        const tableClass = hasTable ? ' table-bubble' : '';
        
        bubbleDiv.innerHTML = `
            <div class="d-flex justify-content-start">
                <div class="bg-light border rounded-3 px-3 py-2${tableClass}" style="max-width: ${maxWidth}; font-size: 0.875rem; width: 100%;">
                    ${formatMessage(message)}
                </div>
            </div>
        `;
    }
    
    messageDiv.appendChild(bubbleDiv);
    messagesDiv.appendChild(messageDiv);
    
    // Scroll to bottom with smooth behavior
    messagesDiv.scrollTo({
        top: messagesDiv.scrollHeight,
        behavior: 'smooth'
    });
    
    // Add to message history
    messageHistory.push({ message, sender, timestamp: new Date() });
    
    // Trigger avatar speaking for bot messages (if avatar is loaded)
    if (sender === 'bot' && typeof avatarSpeak === 'function' && type !== 'error') {
        // Small delay to ensure message is displayed first
        setTimeout(() => {
            const wordCount = message.split(/\s+/).length;
            // Convert seconds to milliseconds for avatarSpeak
            const estimatedDuration = Math.max(1000, Math.min(10000, (wordCount / 2.5) * 1000));
            avatarSpeak(estimatedDuration);
        }, 100);
    }
}

function formatMessage(message) {
    // Convert markdown tables to HTML tables
    message = convertMarkdownTableToHTML(message);
    
    // Convert line breaks to HTML
    return message.replace(/\n/g, '<br>');
}

function convertMarkdownTableToHTML(message) {
    // Split message into lines
    const lines = message.split('\n');
    const result = [];
    let inTable = false;
    let tableLines = [];
    
    for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();
        
        // Check if this line starts a table (contains |)
        if (line.includes('|') && line.split('|').length > 2) {
            if (!inTable) {
                inTable = true;
                tableLines = [];
            }
            tableLines.push(line);
        } else if (inTable) {
            // End of table, convert it
            if (tableLines.length > 0) {
                result.push(convertTableToHTML(tableLines));
                tableLines = [];
            }
            inTable = false;
            result.push(line);
        } else {
            result.push(line);
        }
    }
    
    // Handle table at end of message
    if (inTable && tableLines.length > 0) {
        result.push(convertTableToHTML(tableLines));
    }
    
    return result.join('\n');
}

function convertTableToHTML(tableLines) {
    if (tableLines.length < 2) return tableLines.join('\n');
    
    // Remove empty lines and filter out separator lines
    const dataLines = tableLines.filter(line => 
        line.trim() && 
        !line.match(/^\s*\|[\s\-\|]+\|\s*$/) // Not a separator line
    );
    
    if (dataLines.length === 0) return tableLines.join('\n');
    
    let html = '<div class="table-responsive" style="overflow-x: auto; width: 100%;"><table class="table table-striped table-bordered table-hover" style="width: 100%; min-width: 650px; margin: 0;">';
    
    // Process each line
    dataLines.forEach((line, index) => {
        // Clean up the line and split by |
        const cells = line.split('|').map(cell => cell.trim()).filter(cell => cell !== '');
        
        if (cells.length === 0) return;
        
        if (index === 0) {
            // Header row
            html += '<thead><tr>';
            cells.forEach(cell => {
                html += `<th style="padding: 6px 8px; font-size: 0.75rem; white-space: nowrap;">${cell}</th>`;
            });
            html += '</tr></thead><tbody>';
        } else {
            // Data row
            html += '<tr>';
            cells.forEach((cell, cellIndex) => {
                const isNumeric = /^\$?[\d,]+\.?\d*$/.test(cell.trim());
                const alignment = isNumeric ? 'text-end' : 'text-start';
                // First column (product name) can wrap, others stay compact
                const wrapStyle = cellIndex === 0 ? 'white-space: normal; word-break: break-word; max-width: 200px;' : 'white-space: nowrap;';
                html += `<td class="${alignment}" style="padding: 6px 8px; font-size: 0.75rem; ${wrapStyle}">${cell}</td>`;
            });
            html += '</tr>';
        }
    });
    
    html += '</tbody></table></div>';
    return html;
}

function showTypingIndicator() {
    document.getElementById('typingIndicator').style.display = 'block';
}

function hideTypingIndicator() {
    document.getElementById('typingIndicator').style.display = 'none';
}

function toggleUI(enabled) {
    document.getElementById('messageInput').disabled = !enabled;
    document.getElementById('sendButton').disabled = !enabled || !document.getElementById('messageInput').value.trim();
}

function displayUserInfo(userInfo) {
    currentUser = userInfo;
    document.getElementById('userName').textContent = userInfo.name || '-';
    document.getElementById('userType').textContent = userInfo.user_type || '-';
    document.getElementById('userRole').textContent = userInfo.role || '-';
    document.getElementById('userWarehouse').textContent = userInfo.warehouse || '-';
    document.getElementById('userInfoPanel').style.display = 'block';
    
    // Show cart button for logged in users
    document.getElementById('cartButton').style.display = 'inline-block';
}

// REMOVED: Action buttons section has been removed per user request
// function showActionButtons(buttons) {
//     const buttonContainer = document.getElementById('buttonContainer');
//     buttonContainer.innerHTML = '';
//     
//     buttons.forEach(button => {
//         const btn = document.createElement('button');
//         btn.className = 'btn btn-outline-primary btn-sm';
//         btn.textContent = button.text;
//         btn.onclick = () => handleAction(button.action);
//         buttonContainer.appendChild(btn);
//     });
//     
//     document.getElementById('actionButtons').style.display = 'block';
// }

function handleAction(action) {
    switch (action) {
        case 'place_order':
            sendMessage('I want to place an order');
            break;
        case 'track_order':
            sendMessage('I want to track an order');
            break;
        case 'view_cart':
            viewCart();
            break;
        case 'add_items':
            sendMessage('I want to add more items to my order');
            break;
        case 'view_products':
            sendMessage('Show me available products');
            break;
        case 'company_info':
            sendMessage('Tell me about the company');
            break;
        case 'help':
            sendMessage('I need help');
            break;
        default:
            console.log('Unknown action:', action);
    }
}

function updateCartDisplay(cartItems) {
    this.cartItems = cartItems;
    // Update cart button with item count
    const cartButton = document.getElementById('cartButton');
    if (cartItems.length > 0) {
        cartButton.innerHTML = `<i class="fas fa-shopping-cart"></i> Cart (${cartItems.length})`;
    } else {
        cartButton.innerHTML = `<i class="fas fa-shopping-cart"></i> Cart`;
    }
}

async function viewCart() {
    try {
        const response = await fetch('/enhanced-chat/cart');
        const data = await response.json();
        
        if (data.cart_items) {
            displayCartModal(data.cart_items);
        } else {
            addMessage('Your cart is empty.', 'bot');
        }
    } catch (error) {
        console.error('Error loading cart:', error);
        addMessage('Error loading cart. Please try again.', 'bot', 'error');
    }
}

function displayCartModal(cartItems) {
    const cartContent = document.getElementById('cartContent');
    const cartModalElement = document.getElementById('cartModal');
    
    if (cartItems.length === 0) {
        cartContent.innerHTML = '<p class="text-muted">Your cart is empty.</p>';
    } else {
        let html = '<div class="table-responsive"><table class="table table-striped">';
        html += '<thead><tr><th>Product</th><th>Quantity</th><th>Price</th><th>Total</th><th>Action</th></tr></thead><tbody>';
        
        let totalAmount = 0;
        cartItems.forEach(item => {
            const itemTotal = item.quantity * item.final_price;
            totalAmount += itemTotal;
            
            html += `
                <tr>
                    <td>
                        <strong>${item.product_name}</strong><br>
                        <small class="text-muted">${item.product_code}</small>
                    </td>
                    <td>${item.quantity}</td>
                    <td>$${item.final_price.toFixed(2)}</td>
                    <td>$${itemTotal.toFixed(2)}</td>
                    <td>
                        <button class="btn btn-sm btn-outline-danger" onclick="removeFromCart(${item.id})">
                            <i class="fas fa-trash"></i>
                        </button>
                    </td>
                </tr>
            `;
        });
        
        html += '</tbody></table></div>';
        html += `<div class="text-end"><h5>Total: $${totalAmount.toFixed(2)}</h5></div>`;
        
        cartContent.innerHTML = html;
    }
    
    // Get existing modal instance or create a new one
    let cartModal = bootstrap.Modal.getInstance(cartModalElement);
    if (!cartModal) {
        cartModal = new bootstrap.Modal(cartModalElement, {
            backdrop: true,
            keyboard: true
        });
    }
    
    // Clear any previous event listeners to prevent duplicates
    cartModalElement.removeEventListener('hidden.bs.modal', handleCartModalClose);
    
    // Add close event handler to clean up
    cartModalElement.addEventListener('hidden.bs.modal', handleCartModalClose, { once: true });
    
    // Show modal
    cartModal.show();
}

// Handle cart modal close event
function handleCartModalClose(event) {
    // Clean up: clear the cart content when modal is closed
    const cartContent = document.getElementById('cartContent');
    if (cartContent) {
        // Optional: clear content when modal closes (or keep it for next open)
        // cartContent.innerHTML = '';
    }
    console.log('Cart modal closed successfully');
}

async function removeFromCart(itemId) {
    try {
        const response = await fetch(`/enhanced-chat/cart/${itemId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            const data = await response.json();
            const cartContent = document.getElementById('cartContent');
            const cartModalElement = document.getElementById('cartModal');
            
            if (data.cart_items && data.cart_items.length > 0) {
                // Update cart content in place without recreating modal
                let html = '<div class="table-responsive"><table class="table table-striped">';
                html += '<thead><tr><th>Product</th><th>Quantity</th><th>Price</th><th>Total</th><th>Action</th></tr></thead><tbody>';
                
                let totalAmount = 0;
                data.cart_items.forEach(item => {
                    const itemTotal = item.quantity * item.final_price;
                    totalAmount += itemTotal;
                    
                    html += `
                        <tr>
                            <td>
                                <strong>${item.product_name}</strong><br>
                                <small class="text-muted">${item.product_code}</small>
                            </td>
                            <td>${item.quantity}</td>
                            <td>$${item.final_price.toFixed(2)}</td>
                            <td>$${itemTotal.toFixed(2)}</td>
                            <td>
                                <button class="btn btn-sm btn-outline-danger" onclick="removeFromCart(${item.id})">
                                    <i class="fas fa-trash"></i>
                                </button>
                            </td>
                        </tr>
                    `;
                });
                
                html += '</tbody></table></div>';
                html += `<div class="text-end"><h5>Total: $${totalAmount.toFixed(2)}</h5></div>`;
                cartContent.innerHTML = html;
                
                // Update cart button count
                updateCartDisplay(data.cart_items);
            } else {
                // Cart is empty, close modal and show message
                const cartModal = bootstrap.Modal.getInstance(cartModalElement);
                if (cartModal) {
                    cartModal.hide();
                }
                cartContent.innerHTML = '<p class="text-muted">Your cart is empty.</p>';
                updateCartDisplay([]);
                addMessage('Item removed from cart. Your cart is now empty.', 'bot');
            }
        } else {
            addMessage('Error removing item from cart.', 'bot', 'error');
        }
    } catch (error) {
        console.error('Error removing from cart:', error);
        addMessage('Error removing item from cart.', 'bot', 'error');
    }
}

async function placeOrder() {
    try {
        const response = await fetch('/enhanced-chat/place_order', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            addMessage(data.message, 'bot');
            if (data.order_id) {
                addMessage(`Order ID: ${data.order_id}`, 'bot');
            }
            // Hide cart modal
            const cartModal = bootstrap.Modal.getInstance(document.getElementById('cartModal'));
            cartModal.hide();
        } else {
            addMessage(data.message, 'bot', 'error');
        }
    } catch (error) {
        console.error('Error placing order:', error);
        addMessage('Error placing order. Please try again.', 'bot', 'error');
    }
}

function displayRecentOrders(orders) {
    let message = 'Here are your recent orders:\n\n';
    orders.forEach(order => {
        message += `• ${order.order_id} - ${order.status} - $${order.total_amount} (${order.order_date})\n`;
    });
    addMessage(message, 'bot');
}

function displayOrderDetails(orderDetails) {
    let message = `Order Details for ${orderDetails.order_id}:\n\n`;
    message += `Status: ${orderDetails.status}\n`;
    message += `Stage: ${orderDetails.order_stage}\n`;
    message += `Total Amount: $${orderDetails.total_amount}\n`;
    message += `Order Date: ${orderDetails.order_date}\n`;
    message += `Warehouse: ${orderDetails.warehouse_location}\n\n`;
    
    if (orderDetails.items && orderDetails.items.length > 0) {
        message += 'Items:\n';
        orderDetails.items.forEach(item => {
            message += `• ${item.product_name} - Qty: ${item.quantity} - $${item.total_price}\n`;
        });
    }
    
    addMessage(message, 'bot');
}

function clearChat() {
    const messagesDiv = document.getElementById('chatMessages');
    messagesDiv.innerHTML = `
        <div class="text-center text-muted py-5">
            <i class="fas fa-robot fa-3x mb-3"></i>
            <h4>Welcome to RB (Powered by Quantum Blue AI)</h4>
            <p>Your intelligent assistant for orders, tracking, and more!</p>
        </div>
    `;
    
    // Reset state
    messageHistory = [];
    currentUser = null;
    cartItems = [];
    currentOrderSummary = null;
    
    // Hide panels
    document.getElementById('userInfoPanel').style.display = 'none';
    // document.getElementById('actionButtons').style.display = 'none'; // REMOVED: actionButtons no longer exists
    document.getElementById('cartButton').style.display = 'none';
    
    // Reset input placeholder
    document.getElementById('messageInput').placeholder = 'Enter your unique ID to start...';
}

// Utility functions
function formatCurrency(amount) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD'
    }).format(amount);
}

function formatDate(dateString) {
    return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}
