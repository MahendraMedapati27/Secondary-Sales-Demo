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

// Voice functionality disabled

let productRecommendations = [];
let recommendationTimeout = null;

function initializeChat() {
    // Set up event listeners
    const messageInput = document.getElementById('messageInput');
    
    messageInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            hideProductRecommendations();
            sendMessage();
        } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault();
            navigateRecommendations(e.key === 'ArrowDown' ? 1 : -1);
        }
    });

    messageInput.addEventListener('input', function(e) {
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
        
        // Show product recommendations if user is logged in
        if (currentUser && message.length > 0) {
            clearTimeout(recommendationTimeout);
            recommendationTimeout = setTimeout(() => {
                searchProducts(message);
            }, 300); // Wait 300ms after user stops typing
        } else {
            hideProductRecommendations();
        }
    });

    // Hide recommendations when clicking outside
    document.addEventListener('click', function(e) {
        const recommendations = document.getElementById('productRecommendations');
        const input = document.getElementById('messageInput');
        if (recommendations && !recommendations.contains(e.target) && !input.contains(e.target)) {
            hideProductRecommendations();
        }
    });

    // Initialize message history
    messageHistory = [];
    
    // Load products when user is logged in
    if (currentUser) {
        loadProducts();
    }
}

async function loadProducts() {
    try {
        const response = await fetch('/enhanced-chat/api/products');
        if (response.ok) {
            const data = await response.json();
            productRecommendations = data.products || [];
        }
    } catch (error) {
        console.error('Error loading products:', error);
    }
}

function searchProducts(query) {
    if (!query || query.length < 2) {
        hideProductRecommendations();
        return;
    }
    
    const queryLower = query.toLowerCase();
    const filtered = productRecommendations.filter(product => {
        const nameMatch = product.product_name.toLowerCase().includes(queryLower);
        const codeMatch = product.product_code.toLowerCase().includes(queryLower);
        return nameMatch || codeMatch;
    }).slice(0, 5); // Show max 5 recommendations
    
    if (filtered.length > 0) {
        showProductRecommendations(filtered);
    } else {
        hideProductRecommendations();
    }
}

function showProductRecommendations(products) {
    const recommendationsDiv = document.getElementById('productRecommendations');
    const recommendationsList = document.getElementById('recommendationsList');
    
    if (!recommendationsDiv || !recommendationsList) return;
    
    let html = '';
    products.forEach((product, index) => {
        html += `
            <div class="recommendation-item p-2 border-bottom cursor-pointer" 
                 data-index="${index}"
                 onclick="selectProductRecommendation('${product.product_code}', '${product.product_name.replace(/'/g, "\\'")}')"
                 onmouseover="highlightRecommendation(${index})"
                 style="cursor: pointer; transition: background-color 0.2s;">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <strong>${product.product_name}</strong>
                        <small class="text-muted d-block">${product.product_code}</small>
                    </div>
                    <small class="text-primary">$${product.price_of_product?.toFixed(2) || '0.00'}</small>
                </div>
            </div>
        `;
    });
    
    recommendationsList.innerHTML = html;
    recommendationsDiv.style.display = 'block';
}

function hideProductRecommendations() {
    const recommendationsDiv = document.getElementById('productRecommendations');
    if (recommendationsDiv) {
        recommendationsDiv.style.display = 'none';
    }
}

function selectProductRecommendation(productCode, productName) {
    const input = document.getElementById('messageInput');
    const currentValue = input.value.trim();
    
    // If input is empty or just contains the search query, replace it
    // Otherwise, append to the current value
    if (currentValue.length < 3 || currentValue.toLowerCase().includes(productName.toLowerCase()) || currentValue.toLowerCase().includes(productCode.toLowerCase())) {
        input.value = `Order ${productCode} - ${productName}`;
    } else {
        input.value = `${currentValue}, ${productCode} - ${productName}`;
    }
    
    input.focus();
    hideProductRecommendations();
    
    // Enable send button
    document.getElementById('sendButton').disabled = false;
}

function highlightRecommendation(index) {
    const items = document.querySelectorAll('.recommendation-item');
    items.forEach((item, i) => {
        if (i === index) {
            item.style.backgroundColor = '#f0f0f0';
        } else {
            item.style.backgroundColor = '';
        }
    });
}

function navigateRecommendations(direction) {
    const items = document.querySelectorAll('.recommendation-item');
    let currentIndex = -1;
    
    items.forEach((item, index) => {
        if (item.style.backgroundColor === 'rgb(240, 240, 240)') {
            currentIndex = index;
        }
    });
    
    const newIndex = currentIndex + direction;
    if (newIndex >= 0 && newIndex < items.length) {
        items.forEach((item, index) => {
            item.style.backgroundColor = index === newIndex ? '#f0f0f0' : '';
        });
    } else if (newIndex === -1 && direction === -1) {
        // Move to input field
        document.getElementById('messageInput').focus();
    }
}

async function sendMessage(messageText = null) {
    if (isProcessing) return;
    
    const input = document.getElementById('messageInput');
    // Use provided message or get from input field
    const message = messageText !== null ? messageText.trim() : input.value.trim();
    
    if (!message) return;
    
    // Clear input and disable
    if (messageText === null) {
        input.value = '';
    }
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
            // Check if we need to animate order details with staggered effect
            let animationDelay = 0;
            if (data.animate_order_details) {
                animationDelay = addMessageWithAnimation(data.response, 'bot');
            } else {
                addMessage(data.response, 'bot');
            }
            
            // Handle interactive stock confirmation UI
            if (data.interactive_stock_confirmation && data.stocks) {
                // Pass invoice_ids, dispatch_dates, and showTable flag to the stock confirmation form
                addStockConfirmationForm(
                    data.stocks, 
                    data.invoice_ids || null, 
                    data.dispatch_dates || null,
                    data.show_stock_table || false
                );
            }
            
            // Handle product table display (before product selection form)
            if (data.show_product_table && data.products) {
                showProductTable(data.products);
            }
            
            // Handle interactive product selection UI
            if (data.interactive_product_selection && data.products) {
                // Check if change customer button should be shown (for MRs with selected customer)
                const showChangeCustomer = data.action_buttons && data.action_buttons.some(btn => btn.action === 'change_customer');
                addProductSelectionForm(data.products, showChangeCustomer);
            }
            
            // Handle company report table selection
            if (data.interactive_report_selection && data.tables) {
                showTableSelectionForm(data.tables);
            }
            
            // Handle company column selection
            if (data.show_column_selection && data.columns) {
                showColumnSelectionForm(data.table_key, data.table_name, data.columns);
            }
            
            // Handle add new customer form (before action buttons to prevent showing cancel button)
            if (data.interactive_add_customer) {
                addNewCustomerForm();
            }
            
            // Handle customer selection for MRs (before action buttons to prevent showing Add New Customer/Cancel)
            if (data.interactive_customer_selection && data.customers) {
                // Show customer table as separate message if flag is set
                if (data.show_customer_table) {
                    showCustomerTable(data.customers);
                }
                addCustomerSelectionForm(data.customers);
            }
            
            // Handle order selection for tracking orders
            if (data.interactive_order_selection && data.orders) {
                // Show orders table as separate message if flag is set
                if (data.show_orders_table) {
                    showOrdersTable(data.orders);
                }
                addOrderSelectionForm(data.orders, data.filters || null);
            }
            
            // Handle action buttons (skip if add customer form is shown, product selection is shown, customer selection is shown, order selection is shown, or report selection is shown)
            // For animated order details, delay showing action buttons until animation completes
            // Show action buttons if they exist and are not empty, and no interactive UI is active
            if (data.action_buttons && Array.isArray(data.action_buttons) && data.action_buttons.length > 0 && !data.interactive_add_customer && !data.interactive_product_selection && !data.interactive_customer_selection && !data.interactive_order_selection && !data.interactive_stock_confirmation && !data.interactive_report_selection && !data.show_column_selection) {
                if (data.animate_order_details && animationDelay > 0) {
                    // Delay action buttons to appear after animation completes
                    setTimeout(() => {
                        showActionButtons(data.action_buttons);
                    }, animationDelay + 500);
                } else {
                    showActionButtons(data.action_buttons);
                }
            }
            
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
            
            // Voice functionality disabled
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
    
    // Remove welcome message if exists (when first message is sent)
    const welcome = messagesDiv.querySelector('.text-center.text-muted');
    if (welcome) {
        welcome.remove();
    }
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender} mb-3`;
    
    const bubbleDiv = document.createElement('div');
    bubbleDiv.className = `message-bubble ${sender === 'user' ? 'user' : 'bot'}`;
    
    if (sender === 'user') {
        bubbleDiv.innerHTML = `
            <div class="d-flex justify-content-end align-items-center" style="width: 100%; gap: 8px;">
                <div class="bg-primary text-white rounded-3 px-3 py-2" style="max-width: 75%; width: fit-content; min-width: 0; font-size: 0.875rem; word-break: normal !important; overflow-wrap: anywhere !important; white-space: normal !important; overflow: hidden;">
                    ${formatMessage(message)}
                </div>
                <div class="message-avatar user-avatar">
                    <i class="fas fa-user-circle"></i>
                </div>
            </div>
        `;
    } else {
        const alertClass = type === 'error' ? 'alert-danger' : 'alert-info';
        // Check if message contains a table - if so, use wider max-width
        const hasTable = message.includes('|') && message.includes('---');
        const maxWidth = '75%'; // Match user message inner bubble width
        const tableClass = hasTable ? ' table-bubble' : '';
        
        bubbleDiv.innerHTML = `
            <div class="d-flex justify-content-start align-items-center" style="gap: 8px;">
                <div class="message-avatar bot-avatar">
                    <img src="/static/Images/Q_logo_quantum_blue-removebg-preview.png" alt="Quantum Blue Logo" class="avatar-image">
                </div>
                <div class="bg-light border rounded-3 px-3 py-2${tableClass}" style="max-width: ${maxWidth}; font-size: 0.875rem; width: auto;">
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

function addMessageWithAnimation(message, sender, type = 'normal') {
    const messagesDiv = document.getElementById('chatMessages');
    
    // Remove welcome message if exists
    const welcome = messagesDiv.querySelector('.text-center.text-muted');
    if (welcome) {
        welcome.remove();
    }
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender} mb-3`;
    
    const bubbleDiv = document.createElement('div');
    bubbleDiv.className = `message-bubble ${sender === 'user' ? 'user' : 'bot'}`;
    
    // Parse message to extract parts for staggered animation
    // For order details, we want to split by lines and animate each detail individually
    const lines = message.split('\n');
    const parts = [];
    let currentPart = [];
    let inTable = false;
    let isOrderDetails = message.includes('**Track Order') || message.includes('**Status:**');
    
    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const trimmedLine = line.trim();
        
        // Check if this is a table line
        if (trimmedLine.includes('|') && trimmedLine.split('|').length > 2) {
            if (!inTable) {
                // Start of table - save previous text parts
                if (currentPart.length > 0) {
                    // For order details, split each line into separate parts
                    if (isOrderDetails) {
                        currentPart.forEach(l => {
                            if (l.trim()) {
                                parts.push({ type: 'text', content: l });
                            }
                        });
                    } else {
                        parts.push({ type: 'text', content: currentPart.join('\n') });
                    }
                    currentPart = [];
                }
                inTable = true;
            }
            currentPart.push(line);
        } else {
            if (inTable) {
                // End of table - save table part
                if (currentPart.length > 0) {
                    parts.push({ type: 'table', content: currentPart.join('\n') });
                    currentPart = [];
                }
                inTable = false;
            }
            // For order details, we want each line to be a separate animated part
            if (isOrderDetails && trimmedLine) {
                // Each non-empty line is a separate part
                parts.push({ type: 'text', content: line });
            } else if (trimmedLine || currentPart.length > 0) {
                currentPart.push(line);
            }
        }
    }
    
    // Save remaining part
    if (currentPart.length > 0) {
        if (isOrderDetails && !inTable) {
            currentPart.forEach(l => {
                if (l.trim()) {
                    parts.push({ type: 'text', content: l });
                }
            });
        } else {
            parts.push({ type: inTable ? 'table' : 'text', content: currentPart.join('\n') });
        }
    }
    
    // Create container for animated parts
    const container = document.createElement('div');
    
    if (sender === 'bot') {
        const hasTable = message.includes('|') && message.includes('---');
        const maxWidth = '75%';
        const tableClass = hasTable ? ' table-bubble' : '';
        
        bubbleDiv.innerHTML = `
            <div class="d-flex justify-content-start align-items-center" style="gap: 8px;">
                <div class="message-avatar bot-avatar">
                    <img src="/static/Images/Q_logo_quantum_blue-removebg-preview.png" alt="Quantum Blue Logo" class="avatar-image">
                </div>
                <div class="bg-light border rounded-3 px-3 py-2${tableClass}" style="max-width: ${maxWidth}; font-size: 0.875rem; width: auto;">
                </div>
            </div>
        `;
        
        const innerDiv = bubbleDiv.querySelector('.bg-light');
        innerDiv.appendChild(container);
    } else {
        bubbleDiv.innerHTML = `
            <div class="d-flex justify-content-end align-items-center" style="width: 100%; gap: 8px;">
                <div class="bg-primary text-white rounded-3 px-3 py-2" style="max-width: 75%; width: fit-content; min-width: 0; font-size: 0.875rem; word-break: normal !important; overflow-wrap: anywhere !important; white-space: normal !important; overflow: hidden;">
                </div>
                <div class="message-avatar user-avatar">
                    <i class="fas fa-user-circle"></i>
                </div>
            </div>
        `;
        
        const innerDiv = bubbleDiv.querySelector('.bg-primary');
        innerDiv.appendChild(container);
    }
    
    messageDiv.appendChild(bubbleDiv);
    messagesDiv.appendChild(messageDiv);
    
    // Animate parts one by one
    let totalDelay = 0;
    parts.forEach((part, index) => {
        setTimeout(() => {
            const partDiv = document.createElement('div');
            partDiv.style.opacity = '0';
            partDiv.style.transform = 'translateY(10px)';
            partDiv.style.transition = 'opacity 0.5s ease-out, transform 0.5s ease-out';
            
            // Only add margin for text parts, not for tables
            if (part.type === 'text') {
                // For order details, add smaller margin between lines
                if (isOrderDetails && index < parts.length - 1) {
                    partDiv.style.marginBottom = '2px';
                } else if (!isOrderDetails && index < parts.length - 1) {
                    partDiv.style.marginBottom = '4px';
                }
            } else if (part.type === 'table') {
                partDiv.style.marginTop = '12px';
                partDiv.style.marginBottom = '0';
            }
            
            if (part.type === 'table') {
                partDiv.innerHTML = convertMarkdownTableToHTML(part.content);
            } else {
                partDiv.innerHTML = formatMessage(part.content);
            }
            
            container.appendChild(partDiv);
            
            // Trigger animation
            setTimeout(() => {
                partDiv.style.opacity = '1';
                partDiv.style.transform = 'translateY(0)';
            }, 50);
        }, totalDelay);
        
        // Shorter delay for order details (200ms) vs regular messages (400ms)
        const delay = isOrderDetails ? 200 : 400;
        totalDelay += delay;
    });
    
    // Scroll to bottom as animation progresses
    const scrollInterval = setInterval(() => {
        messagesDiv.scrollTo({
            top: messagesDiv.scrollHeight,
            behavior: 'smooth'
        });
    }, 200);
    
    // Stop scrolling interval after animation completes
    setTimeout(() => {
        clearInterval(scrollInterval);
        messagesDiv.scrollTo({
            top: messagesDiv.scrollHeight,
            behavior: 'smooth'
        });
    }, totalDelay + 500);
    
    // Add to message history
    messageHistory.push({ message, sender, timestamp: new Date() });
    
    // Trigger avatar speaking
    if (sender === 'bot' && typeof avatarSpeak === 'function' && type !== 'error') {
        setTimeout(() => {
            const wordCount = message.split(/\s+/).length;
            const estimatedDuration = Math.max(1000, Math.min(10000, (wordCount / 2.5) * 1000));
            avatarSpeak(estimatedDuration);
        }, totalDelay + 300);
    }
    
    return totalDelay; // Return total delay for action buttons timing
}

function formatMessage(message) {
    // Convert markdown tables to HTML tables first
    message = convertMarkdownTableToHTML(message);
    
    // Convert markdown bold (**text**) to HTML <strong>
    message = message.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    
    // Convert markdown italic (*text*) to HTML <em> (but not if it's part of **)
    message = message.replace(/(?<!\*)\*([^*]+?)\*(?!\*)/g, '<em>$1</em>');
    
    // Convert markdown code (`text`) to HTML <code>
    message = message.replace(/`([^`]+?)`/g, '<code style="background-color: #f4f4f4; padding: 2px 4px; border-radius: 3px; font-family: monospace;">$1</code>');
    
    // Convert markdown lists (* item) to HTML <ul><li>
    const lines = message.split('\n');
    const result = [];
    let inList = false;
    
    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const listMatch = line.match(/^[\s]*[•\*\-]\s+(.+)$/);
        
        if (listMatch) {
            if (!inList) {
                result.push('<ul style="margin: 8px 0; padding-left: 20px;">');
                inList = true;
            }
            result.push(`<li style="margin: 4px 0;">${listMatch[1]}</li>`);
        } else {
            if (inList) {
                result.push('</ul>');
                inList = false;
            }
            result.push(line);
        }
    }
    
    if (inList) {
        result.push('</ul>');
    }
    
    message = result.join('\n');
    
    // Convert line breaks to HTML (but preserve existing HTML)
    message = message.split('\n').map(line => {
        // Don't add <br> if line is empty or already contains HTML tags
        if (!line.trim() || line.match(/<[^>]+>/)) {
            return line;
        }
        return line + '<br>';
    }).join('');
    
    return message;
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
    // Set current user to enable product recommendations
    currentUser = userInfo;
    
    // Load products for recommendations
    if (currentUser) {
        loadProducts();
    }
    
    document.getElementById('userName').textContent = userInfo.name || '-';
    document.getElementById('userType').textContent = userInfo.user_type || '-';
    document.getElementById('userRole').textContent = userInfo.role || '-';
    document.getElementById('userWarehouse').textContent = userInfo.warehouse || '-';
    document.getElementById('userInfoPanel').style.display = 'block';
    
    // Show cart button for logged in users
    document.getElementById('cartButton').style.display = 'inline-block';
}

// Enhanced action buttons with better UX
function showActionButtons(buttons) {
    const messagesDiv = document.getElementById('chatMessages');
    
    // Find the last bot message
    const botMessages = messagesDiv.querySelectorAll('.message.bot');
    let lastBotMessage = null;
    
    if (botMessages.length > 0) {
        lastBotMessage = botMessages[botMessages.length - 1];
    }
    
    // If no bot message found, create one (fallback)
    if (!lastBotMessage) {
        addMessage('', 'bot');
        const botMessages = messagesDiv.querySelectorAll('.message.bot');
        if (botMessages.length > 0) {
            lastBotMessage = botMessages[botMessages.length - 1];
        }
    }
    
    if (!lastBotMessage) return; // Still no message, exit
    
    // Find the inner message bubble div (the one with bg-light class)
    const messageBubble = lastBotMessage.querySelector('.message-bubble .bg-light');
    if (!messageBubble) return; // Exit if bubble not found
    
    const buttonContainer = document.createElement('div');
    buttonContainer.className = 'action-buttons-container mt-3';
    buttonContainer.style.cssText = 'animation: slideInFromBottom 0.3s ease-out; width: 100%; max-width: 100%;';
    
    // Center buttons when there are 3 buttons
    const buttonCount = buttons.filter(b => b).length;
    const buttonRow = document.createElement('div');
    
    if (buttonCount === 3) {
        // For 3 buttons, use flexbox with justify-content-center
        buttonRow.className = 'd-flex gap-2 flex-wrap';
        buttonRow.style.cssText = 'justify-content: center; width: 100%;';
    } else {
        // For 2 or 4 buttons, use grid
        buttonRow.className = 'd-grid gap-2';
        buttonRow.style.cssText = 'grid-template-columns: repeat(2, 1fr); width: 100%;';
    }
    
    // Icon mapping for different actions
    const actionIcons = {
        'place_order': 'fas fa-shopping-cart',
        'track_order': 'fas fa-truck',
        'company_info': 'fas fa-building',
        'pending_stocks': 'fas fa-clipboard-check'
    };
    
    buttons.forEach(button => {
        if (!button) return; // Skip null buttons
        
        const btn = document.createElement('button');
        btn.className = 'btn btn-primary action-btn';
        btn.style.cssText = `
            padding: 10px 16px;
            border-radius: 10px;
            font-weight: 600;
            font-size: 0.8rem;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            border: none;
            min-width: 110px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        `;
        
        // Add icon if available
        const iconClass = actionIcons[button.action] || 'fas fa-arrow-right';
        btn.innerHTML = `<i class="${iconClass}"></i> <span>${button.text}</span>`;
        btn.setAttribute('data-action', button.action);
        
        // Store order_id if provided
        if (button.order_id) {
            btn.setAttribute('data-order-id', button.order_id);
        }
        
        // Apply custom style if provided
        if (button.style) {
            if (button.style === 'success') {
                btn.className = 'btn btn-success action-btn';
            } else if (button.style === 'danger') {
                btn.className = 'btn btn-danger action-btn';
            }
        }
        
        // Use addEventListener for better compatibility
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            // Hide the action buttons container
            const container = buttonContainer;
            if (container) {
                container.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
                container.style.opacity = '0';
                container.style.transform = 'translateY(-10px)';
                setTimeout(() => {
                    container.remove();
                }, 300);
            }
            
            // Add loading state
            this.classList.add('loading');
            this.disabled = true;
            
            // Get order_id if available
            const orderId = this.getAttribute('data-order-id');
            
            // Call handleAction with order_id if available
            if (typeof handleAction === 'function') {
                handleAction(button.action, orderId);
            } else {
                // Fallback: send message directly
                const actionMessages = {
                    'place_order': 'I want to place an order',
                    'track_order': 'I want to track an order',
                    'company_info': 'Tell me about the company'
                };
                const message = actionMessages[button.action] || button.text;
                sendMessage(message);
            }
            
            // Remove loading state after a delay
            setTimeout(() => {
                this.classList.remove('loading');
                this.disabled = false;
            }, 1000);
        });
        
        // Add hover effects
        btn.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-2px)';
            this.style.boxShadow = '0 6px 20px rgba(37, 99, 235, 0.4)';
        });
        btn.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
            this.style.boxShadow = '0 4px 12px rgba(37, 99, 235, 0.2)';
        });
        
        buttonRow.appendChild(btn);
    });
    
    buttonContainer.appendChild(buttonRow);
    messageBubble.appendChild(buttonContainer); // Append to the message bubble instead of messagesDiv
    
    // Scroll to bottom
    messagesDiv.scrollTo({
        top: messagesDiv.scrollHeight,
        behavior: 'smooth'
    });
}

function handleAction(action, orderId = null) {
    // Remove loading state from all buttons first
    document.querySelectorAll('.action-btn').forEach(btn => {
        btn.classList.remove('loading');
    });
    
    switch (action) {
        case 'place_order':
            sendMessage('I want to place an order');
            break;
        case 'track_order':
            sendMessage('I want to track an order');
            break;
        case 'view_cart':
            if (typeof viewCart === 'function') {
                viewCart();
            } else {
                sendMessage('Show me my cart');
            }
            break;
        case 'add_items':
            sendMessage('I want to add more items to my order');
            break;
        case 'company_info':
            sendMessage('Tell me about the company');
            break;
        case 'help':
            sendMessage('I need help');
            break;
        case 'change_customer':
            sendMessage('Change customer');
            break;
        case 'select_customer':
            sendMessage('Select Customer');
            break;
        case 'add_new_customer':
            sendMessage('Add New Customer');
            break;
        case 'confirm_order':
            // Check if this is distributor confirming an order (has orderId)
            if (orderId) {
                confirmOrderAction(orderId);
            } else if (typeof placeOrder === 'function') {
                placeOrder();
            } else {
                sendMessage('confirm my order');
            }
            break;
        case 'reject_order':
            // Distributor rejecting an order
            if (orderId) {
                rejectOrderAction(orderId);
            }
            break;
        case 'home':
            sendMessage('Hi');
            break;
        case 'view_stock':
            sendMessage('Show me stock status');
            break;
        case 'edit_cart':
            sendMessage('Edit cart');
            break;
        case 'place_order_final':
            sendMessage('Place order');
            break;
        case 'pending_stocks':
            sendMessage('show pending stock');
            break;
        case 'generate_report':
            sendMessage('generate report');
            break;
        case 'cancel':
            sendMessage('Cancel');
            break;
        default:
            console.log('Unknown action:', action);
            // Try to send the action as a message
            sendMessage(action);
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
            displayCartModal(data.cart_items, data.subtotal, data.tax_amount, data.grand_total);
        } else {
            addMessage('Your cart is empty.', 'bot');
        }
    } catch (error) {
        console.error('Error loading cart:', error);
        addMessage('Error loading cart. Please try again.', 'bot', 'error');
    }
}

function displayCartModal(cartItems, subtotal, taxAmount, grandTotal) {
    const cartContent = document.getElementById('cartContent');
    const cartModalElement = document.getElementById('cartModal');
    
    if (cartItems.length === 0) {
        cartContent.innerHTML = '<p class="text-muted">Your cart is empty.</p>';
    } else {
        let html = '<div class="table-responsive"><table class="table table-striped">';
        html += '<thead><tr><th>Product</th><th>Quantity</th><th>Price</th><th>Total</th><th>Action</th></tr></thead><tbody>';
        
        cartItems.forEach(item => {
            const quantity = item.paid_quantity || item.quantity || item.total_quantity || 0;
            const unitPrice = item.final_price || item.unit_price || 0;
            const itemTotal = item.total_price || (quantity * unitPrice);
            
            html += `
                <tr>
                    <td>
                        <strong>${item.product_name || item.product_code}</strong><br>
                        <small class="text-muted">${item.product_code}</small>
                        ${item.free_quantity > 0 ? `<br><small class="text-success">Free: ${item.free_quantity}</small>` : ''}
                    </td>
                    <td>
                        <div class="d-flex align-items-center justify-content-center">
                            <button class="btn btn-sm btn-outline-secondary" onclick="updateCartQuantity(${item.id}, -1)" title="Decrease Quantity">
                                <i class="fas fa-minus"></i>
                            </button>
                            <input type="number" class="form-control form-control-sm text-center mx-2" 
                                   value="${quantity}" 
                                   min="1" 
                                   style="width: 60px;"
                                   onchange="updateCartQuantityDirect(${item.id}, this.value)"
                                   id="quantity-${item.id}">
                            <button class="btn btn-sm btn-outline-secondary" onclick="updateCartQuantity(${item.id}, 1)" title="Increase Quantity">
                                <i class="fas fa-plus"></i>
                            </button>
                        </div>
                    </td>
                    <td>$${unitPrice.toFixed(2)}</td>
                    <td>$${itemTotal.toFixed(2)}</td>
                    <td>
                        <button class="btn btn-sm btn-outline-danger" onclick="removeFromCart(${item.id})" title="Remove Item">
                            <i class="fas fa-trash"></i>
                        </button>
                    </td>
                </tr>
            `;
        });
        
        html += '</tbody></table></div>';
        
        // Add subtotal, tax, and grand total with enhanced styling
        html += `
            <div class="mt-4" style="border-top: 2px solid #e5e7eb; padding-top: 20px;">
                <div class="row mb-2">
                    <div class="col-8 text-end">
                        <strong style="font-size: 1rem; color: #4b5563;">Subtotal:</strong>
                    </div>
                    <div class="col-4 text-end">
                        <span style="font-size: 1rem; color: #4b5563; font-weight: 600;">$${subtotal.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
                    </div>
                </div>
                <div class="row mb-3">
                    <div class="col-8 text-end">
                        <strong style="font-size: 1rem; color: #4b5563;">Tax (5%):</strong>
                    </div>
                    <div class="col-4 text-end">
                        <span style="font-size: 1rem; color: #4b5563; font-weight: 600;">$${taxAmount.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
                    </div>
                </div>
                <div class="row" style="background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%); padding: 15px; border-radius: 10px; margin: 0 -8px;">
                    <div class="col-8 text-end">
                        <strong style="font-size: 1.25rem; color: #1e40af;">Grand Total:</strong>
                    </div>
                    <div class="col-4 text-end">
                        <span style="font-size: 1.35rem; color: #1e40af; font-weight: 700;">$${grandTotal.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
                    </div>
                </div>
            </div>
        `;
        
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

async function updateCartQuantity(itemId, change) {
    try {
        // Get current cart to find the item
        const response = await fetch('/enhanced-chat/cart');
        const cartData = await response.json();
        
        if (!cartData.cart_items) {
            return;
        }
        
        const item = cartData.cart_items.find(i => i.id === itemId);
        if (!item) {
            return;
        }
        
        const currentQuantity = item.paid_quantity || item.quantity || item.total_quantity || 0;
        const newQuantity = currentQuantity + change;
        
        if (newQuantity < 1) {
            // If quantity would be 0 or negative, remove the item instead
            removeFromCart(itemId);
            return;
        }
        
        // Update quantity via API
        const updateResponse = await fetch(`/enhanced-chat/cart/${itemId}/quantity`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ quantity: newQuantity })
        });
        
        if (updateResponse.ok) {
            const updateData = await updateResponse.json();
            // Reload cart display with updated data
            if (updateData.cart_items) {
                displayCartModal(updateData.cart_items);
            } else {
            await viewCart();
            }
        } else {
            const error = await updateResponse.json();
            alert(error.error || error.message || 'Failed to update quantity');
        }
    } catch (error) {
        console.error('Error updating cart quantity:', error);
        alert('Error updating quantity. Please try again.');
    }
}

async function updateCartQuantityDirect(itemId, newQuantity) {
    try {
        const quantity = parseInt(newQuantity);
        if (isNaN(quantity) || quantity < 1) {
            // Reset to current value if invalid
            await viewCart();
            return;
        }
        
        // Update quantity via API
        const updateResponse = await fetch(`/enhanced-chat/cart/${itemId}/quantity`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ quantity: quantity })
        });
        
        if (updateResponse.ok) {
            const updateData = await updateResponse.json();
            // Reload cart display with updated data
            if (updateData.cart_items) {
                displayCartModal(updateData.cart_items);
            } else {
                await viewCart();
            }
        } else {
            const error = await updateResponse.json();
            alert(error.error || error.message || 'Failed to update quantity');
            // Reset to current value on error
            await viewCart();
        }
    } catch (error) {
        console.error('Error updating cart quantity:', error);
        alert('Error updating quantity. Please try again.');
        // Reset to current value on error
        await viewCart();
    }
}

async function removeFromCart(itemId) {
    try {
        const response = await fetch(`/enhanced-chat/cart/${itemId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            const data = await response.json();
            
            if (data.cart_items && data.cart_items.length > 0) {
                // Reload cart display with updated data
                displayCartModal(data.cart_items);
                // Update cart button count
                updateCartDisplay(data.cart_items);
            } else {
                // Cart is empty, close modal and show message
                const cartModalElement = document.getElementById('cartModal');
                const cartModal = bootstrap.Modal.getInstance(cartModalElement);
                if (cartModal) {
                    cartModal.hide();
                }
                const cartContent = document.getElementById('cartContent');
                if (cartContent) {
                cartContent.innerHTML = '<p class="text-muted">Your cart is empty.</p>';
                }
                updateCartDisplay([]);
                addMessage('Item removed from cart. Your cart is now empty.', 'bot');
            }
        } else {
            const error = await response.json();
            addMessage(error.error || 'Error removing item from cart.', 'bot', 'error');
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
            // Hide cart modal if it exists (legacy support)
            const cartModalElement = document.getElementById('cartModal');
            if (cartModalElement) {
                const cartModal = bootstrap.Modal.getInstance(cartModalElement);
                if (cartModal) {
                    cartModal.hide();
                }
            }
        } else {
            addMessage(data.message || 'Error placing order', 'bot', 'error');
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

function addStockConfirmationForm(stocks, invoiceIds = null, dispatchDates = null, showTable = false) {
    const messagesDiv = document.getElementById('chatMessages');
    const formDiv = document.createElement('div');
    formDiv.className = 'message bot mb-3';
    formDiv.id = 'stockConfirmationForm';
    
    let formHTML = `
        <div class="message-bubble bot">
            <div class="bg-light border rounded-3 px-3 py-3" style="max-width: 90%; font-size: 0.875rem;">
                <h6 class="mb-3"><strong>📦 Stock Confirmation Form</strong></h6>
                <form id="confirmStockForm" onsubmit="handleStockConfirmation(event)">
    `;
    
    // Add filters section (Invoice ID and Date) inside the form
    formHTML += `
                    <div class="mb-3" style="background: rgba(239, 246, 255, 0.5); padding: 12px; border-radius: 8px; border: 1px solid rgba(37, 99, 235, 0.2);">
                        <div class="row g-2">
                            <div class="col-md-6">
                                <label for="invoiceIdFilter" class="form-label" style="font-weight: 600; font-size: 0.85rem; color: #2563eb;">
                                    <i class="fas fa-filter me-2"></i>Filter by Invoice ID
                                </label>
                                <select class="form-select form-select-sm" id="invoiceIdFilter" 
                                    style="border-radius: 8px; border: 1.5px solid #e5e7eb; padding: 8px 12px; font-size: 0.875rem;">
                                    <option value="">-- All Invoices --</option>
                                    ${(invoiceIds && invoiceIds.length > 0) ? invoiceIds.map(id => `
                                        <option value="${id}">${id}</option>
                                    `).join('') : ''}
                                </select>
                            </div>
                            <div class="col-md-6">
                                <label for="dateFilter" class="form-label" style="font-weight: 600; font-size: 0.85rem; color: #2563eb;">
                                    <i class="fas fa-calendar me-2"></i>Filter by Dispatch Date
                                </label>
                                <select class="form-select form-select-sm" id="dateFilter" 
                                    style="border-radius: 8px; border: 1.5px solid #e5e7eb; padding: 8px 12px; font-size: 0.875rem;">
                                    <option value="">-- All Dates --</option>
                                    ${(dispatchDates && dispatchDates.length > 0) ? dispatchDates.map(date => `
                                        <option value="${date}">${date}</option>
                                    `).join('') : ''}
                                </select>
                            </div>
                        </div>
                    </div>
    `;
    
    // Add stock table if showTable is true
    if (showTable && stocks && stocks.length > 0) {
        formHTML += `
                    <div class="mb-3">
                        <label class="form-label"><strong>Pending Stock Arrivals:</strong></label>
                        <div style="overflow-x: auto; max-width: 100%; border: 1px solid #dee2e6; border-radius: 8px;">
                            <table class="table table-sm table-bordered table-hover mb-0" style="font-size: 0.8rem; min-width: 800px;">
                                <thead class="table-light" style="position: sticky; top: 0; z-index: 10;">
                                    <tr>
                                        <th style="padding: 8px; white-space: nowrap;">#</th>
                                        <th style="padding: 8px; white-space: nowrap;">Product Name</th>
                                        <th style="padding: 8px; white-space: nowrap;">Product Code</th>
                                        <th style="padding: 8px; white-space: nowrap;">Dispatch Date</th>
                                        <th style="padding: 8px; white-space: nowrap;">Quantity Sent</th>
                                        <th style="padding: 8px; white-space: nowrap;">Invoice ID</th>
                                        <th style="padding: 8px; white-space: nowrap;">Lot Number</th>
                                        <th style="padding: 8px; white-space: nowrap;">Expiration Date</th>
                                        <th style="padding: 8px; white-space: nowrap;">Sales Price</th>
                                        <th style="padding: 8px; white-space: nowrap;">Stock ID</th>
                                    </tr>
                                </thead>
                                <tbody id="stockTableBody">
        `;
        
        stocks.forEach((stock, index) => {
            const invoiceId = stock.invoice_id || 'N/A';
            const lotNumber = stock.lot_number || 'N/A';
            
            // Format dates (handle ISO format dates)
            let expirationDate = 'N/A';
            if (stock.expiration_date) {
                const expDate = new Date(stock.expiration_date);
                if (!isNaN(expDate.getTime())) {
                    expirationDate = expDate.toISOString().split('T')[0];
                } else {
                    expirationDate = stock.expiration_date;
                }
            }
            
            let dispatchDate = 'N/A';
            let dispatchDateFilter = '';
            if (stock.dispatch_date) {
                const dispDate = new Date(stock.dispatch_date);
                if (!isNaN(dispDate.getTime())) {
                    dispatchDate = dispDate.toISOString().split('T')[0];
                    dispatchDateFilter = dispatchDate;
                } else {
                    dispatchDate = stock.dispatch_date;
                    dispatchDateFilter = stock.dispatch_date;
                }
            }
            
            const salesPrice = stock.sales_price ? `$${parseFloat(stock.sales_price).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}` : 'N/A';
            
            formHTML += `
                                    <tr data-stock-id="${stock.id}" data-invoice-id="${stock.invoice_id || ''}" data-dispatch-date="${dispatchDateFilter}" style="cursor: pointer;" onclick="selectStockFromTable(${stock.id}, ${stock.quantity})">
                                        <td style="padding: 8px;">${index + 1}</td>
                                        <td style="padding: 8px;">${stock.product_name || 'N/A'}</td>
                                        <td style="padding: 8px;">${stock.product_code || 'N/A'}</td>
                                        <td style="padding: 8px;">${dispatchDate}</td>
                                        <td style="padding: 8px;">${stock.quantity || 0} units</td>
                                        <td style="padding: 8px;">${invoiceId}</td>
                                        <td style="padding: 8px;">${lotNumber}</td>
                                        <td style="padding: 8px;">${expirationDate}</td>
                                        <td style="padding: 8px;">${salesPrice}</td>
                                        <td style="padding: 8px;">${stock.id}</td>
                                    </tr>
            `;
        });
        
        formHTML += `
                                </tbody>
                            </table>
                        </div>
                    </div>
        `;
    }
    
    formHTML += `
                    <div class="mb-3">
                        <label for="stockSelect" class="form-label"><strong>Select Stock to Confirm:</strong></label>
                        <select class="form-select form-select-sm" id="stockSelect" name="stock_id" required>
                            <option value="">-- Select a stock item --</option>
    `;
    
    stocks.forEach((stock, index) => {
        // Include invoice_id and dispatch_date in data attribute for filtering
        const invoiceId = stock.invoice_id || '';
        let dispatchDate = '';
        if (stock.dispatch_date) {
            const dispDate = new Date(stock.dispatch_date);
            if (!isNaN(dispDate.getTime())) {
                dispatchDate = dispDate.toISOString().split('T')[0];
            } else {
                dispatchDate = stock.dispatch_date;
            }
        }
        formHTML += `
            <option value="${stock.id}" data-quantity="${stock.quantity}" data-invoice-id="${invoiceId}" data-dispatch-date="${dispatchDate}">
                ${index + 1}. ${stock.product_name} (${stock.product_code}) - Qty Sent: ${stock.quantity} units${invoiceId ? ` - Invoice: ${invoiceId}` : ''}
            </option>
        `;
    });
    
    formHTML += `
                        </select>
                    </div>
                    
                    <div class="mb-3">
                        <label for="receivedQuantity" class="form-label"><strong>Quantity Received:</strong></label>
                        <div class="input-group input-group-sm">
                            <input type="number" class="form-control" id="receivedQuantity" name="received_quantity" 
                                   min="1" placeholder="Enter quantity received (leave empty to use sent quantity)">
                            <span class="input-group-text">units</span>
                        </div>
                        <small class="text-muted">Leave empty to confirm with sent quantity</small>
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label"><strong>Adjustment Reason (if quantity differs):</strong></label>
                        <textarea class="form-control form-control-sm" id="adjustmentReason" name="adjustment_reason" 
                                  rows="2" placeholder="Enter reason for quantity adjustment (optional)"></textarea>
                    </div>
                    
                    <div class="d-flex gap-2">
                        <button type="submit" class="btn btn-success btn-sm flex-grow-1">
                            <i class="fas fa-check"></i> Confirm Stock
                        </button>
                        <button type="button" class="btn btn-outline-secondary btn-sm" onclick="clearStockForm()">
                            <i class="fas fa-eraser"></i> Clear
                        </button>
                        <button type="button" class="btn btn-outline-danger btn-sm" onclick="document.getElementById('stockConfirmationForm').remove()">
                            <i class="fas fa-times"></i> Cancel
                        </button>
                    </div>
                </form>
            </div>
        </div>
    `;
    
    formDiv.innerHTML = formHTML;
    messagesDiv.appendChild(formDiv);
    
    // Store original stocks data for filtering
    formDiv._originalStocks = stocks;
    
    // Get form elements
    const stockSelect = document.getElementById('stockSelect');
    const receivedQuantityInput = document.getElementById('receivedQuantity');
    const invoiceIdFilter = document.getElementById('invoiceIdFilter');
    const dateFilter = document.getElementById('dateFilter');
    const stockTableBody = document.getElementById('stockTableBody');
    
    // Function to filter stocks by invoice ID and date
    function filterStocks(invoiceId, date) {
        let filteredStocks = stocks;
        
        // Filter by invoice ID
        if (invoiceId && invoiceId !== '') {
            filteredStocks = filteredStocks.filter(stock => (stock.invoice_id || '') === invoiceId);
        }
        
        // Filter by date
        if (date && date !== '') {
            filteredStocks = filteredStocks.filter(stock => {
                let stockDate = stock.dispatch_date || '';
                // Convert to YYYY-MM-DD format if it's in ISO format
                if (stockDate && stockDate.includes('T')) {
                    const dateObj = new Date(stockDate);
                    if (!isNaN(dateObj.getTime())) {
                        stockDate = dateObj.toISOString().split('T')[0];
                    }
                }
                return stockDate === date || stockDate.startsWith(date);
            });
        }
        
        // Update dropdown
        if (stockSelect) {
            // Remove all options except the first (placeholder)
            while (stockSelect.options.length > 1) {
                stockSelect.remove(1);
            }
            
            // Add filtered options
            filteredStocks.forEach((stock, index) => {
                const invoiceIdValue = stock.invoice_id || '';
                const option = document.createElement('option');
                option.value = stock.id;
                option.setAttribute('data-quantity', stock.quantity);
                option.setAttribute('data-invoice-id', invoiceIdValue);
                option.setAttribute('data-dispatch-date', stock.dispatch_date || '');
                option.textContent = `${index + 1}. ${stock.product_name} (${stock.product_code}) - Qty Sent: ${stock.quantity} units${invoiceIdValue ? ` - Invoice: ${invoiceIdValue}` : ''}`;
                stockSelect.appendChild(option);
            });
            
            // Reset selection
            stockSelect.value = '';
        }
        
        // Update table
        if (stockTableBody) {
            const rows = stockTableBody.querySelectorAll('tr');
            rows.forEach(row => {
                const rowInvoiceId = row.getAttribute('data-invoice-id') || '';
                let rowDate = row.getAttribute('data-dispatch-date') || '';
                
                // Normalize date format for comparison
                if (rowDate && rowDate.includes('T')) {
                    const dateObj = new Date(rowDate);
                    if (!isNaN(dateObj.getTime())) {
                        rowDate = dateObj.toISOString().split('T')[0];
                        row.setAttribute('data-dispatch-date', rowDate);
                    }
                }
                
                let showRow = true;
                if (invoiceId && invoiceId !== '' && rowInvoiceId !== invoiceId) {
                    showRow = false;
                }
                if (date && date !== '' && rowDate !== date && !rowDate.startsWith(date)) {
                    showRow = false;
                }
                
                row.style.display = showRow ? '' : 'none';
            });
            
            // Update row numbers
            let visibleIndex = 1;
            rows.forEach(row => {
                if (row.style.display !== 'none') {
                    const firstCell = row.querySelector('td');
                    if (firstCell) {
                        firstCell.textContent = visibleIndex++;
                    }
                }
            });
        }
        
        // Reset received quantity input
        if (receivedQuantityInput) {
            receivedQuantityInput.value = '';
            receivedQuantityInput.placeholder = 'Enter quantity received (leave empty to use sent quantity)';
            receivedQuantityInput.removeAttribute('max');
        }
    }
    
    // Auto-filter stocks when invoice or date is selected
    if (invoiceIdFilter) {
        invoiceIdFilter.addEventListener('change', function() {
            const selectedInvoiceId = this.value;
            const selectedDate = dateFilter ? dateFilter.value : '';
            filterStocks(selectedInvoiceId, selectedDate);
        });
    }
    
    if (dateFilter) {
        dateFilter.addEventListener('change', function() {
            const selectedDate = this.value;
            const selectedInvoiceId = invoiceIdFilter ? invoiceIdFilter.value : '';
            filterStocks(selectedInvoiceId, selectedDate);
        });
    }
    
    // Update received quantity when stock is selected
    if (stockSelect) {
        stockSelect.addEventListener('change', function() {
            const selectedOption = this.options[this.selectedIndex];
            if (selectedOption && selectedOption.value) {
                const sentQuantity = selectedOption.getAttribute('data-quantity');
                if (receivedQuantityInput) {
                    receivedQuantityInput.placeholder = `Sent quantity: ${sentQuantity} units (leave empty to use this)`;
                    receivedQuantityInput.setAttribute('max', sentQuantity);
                }
            } else {
                if (receivedQuantityInput) {
                    receivedQuantityInput.placeholder = 'Enter quantity received (leave empty to use sent quantity)';
                    receivedQuantityInput.removeAttribute('max');
                }
            }
        });
    }
    
    // Scroll to form
    messagesDiv.scrollTo({
        top: messagesDiv.scrollHeight,
        behavior: 'smooth'
    });
}

// Function to select stock from table row click
function selectStockFromTable(stockId, quantity) {
    const stockSelect = document.getElementById('stockSelect');
    const receivedQuantityInput = document.getElementById('receivedQuantity');
    
    if (stockSelect) {
        stockSelect.value = stockId;
        // Trigger change event to update quantity input
        stockSelect.dispatchEvent(new Event('change'));
    }
    
    if (receivedQuantityInput) {
        receivedQuantityInput.focus();
    }
    
    // Scroll to the select dropdown
    if (stockSelect) {
        stockSelect.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}

async function handleStockConfirmation(event) {
    event.preventDefault();
    
    const form = event.target;
    const formData = new FormData(form);
    const stockId = formData.get('stock_id');
    const receivedQuantity = formData.get('received_quantity');
    const adjustmentReason = formData.get('adjustment_reason');
    
    if (!stockId) {
        alert('Please select a stock item to confirm.');
        return;
    }
    
    // Build confirmation message
    let confirmMessage = `confirm stock ${stockId}`;
    if (receivedQuantity) {
        confirmMessage += ` received ${receivedQuantity}`;
    }
    if (adjustmentReason) {
        confirmMessage += ` reason ${adjustmentReason}`;
    }
    
    // Disable form during submission
    form.querySelectorAll('button, input, select, textarea').forEach(el => {
        el.disabled = true;
    });
    
    // Show loading state
    const submitBtn = form.querySelector('button[type="submit"]');
    const originalText = submitBtn.innerHTML;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Confirming...';
    
    try {
        // Send confirmation message
        const response = await fetch('/enhanced-chat/message', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({ message: confirmMessage })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.error) {
            addMessage(`Error: ${data.error}`, 'bot', 'error');
        } else {
            // Remove the form
            const formDiv = document.getElementById('stockConfirmationForm');
            if (formDiv) {
                formDiv.remove();
            }
            
            // Show response
            addMessage(data.response, 'bot');
            
            // If there are more stocks, show the form again
            if (data.interactive_stock_confirmation && data.stocks) {
                // Pass invoice_ids, dispatch_dates, and showTable flag to the stock confirmation form
                addStockConfirmationForm(
                    data.stocks, 
                    data.invoice_ids || null, 
                    data.dispatch_dates || null,
                    data.show_stock_table || false
                );
            }
        }
    } catch (error) {
        console.error('Error confirming stock:', error);
        addMessage('Sorry, I encountered an error confirming the stock. Please try again.', 'bot', 'error');
        
        // Re-enable form
        form.querySelectorAll('button, input, select, textarea').forEach(el => {
            el.disabled = false;
        });
        submitBtn.innerHTML = originalText;
    }
}

function clearStockForm() {
    const form = document.getElementById('confirmStockForm');
    if (form) {
        form.reset();
    }
}

function addProductSelectionForm(products, showChangeCustomer = false) {
    const messagesDiv = document.getElementById('chatMessages');
    
    // Find the last bot message
    const botMessages = messagesDiv.querySelectorAll('.message.bot');
    let lastBotMessage = null;
    
    if (botMessages.length > 0) {
        lastBotMessage = botMessages[botMessages.length - 1];
    }
    
    if (!lastBotMessage) return; // Exit if no bot message found
    
    // Find the inner message bubble div (the one with bg-light class)
    const messageBubble = lastBotMessage.querySelector('.message-bubble .bg-light');
    if (!messageBubble) return; // Exit if bubble not found
    
    const formDiv = document.createElement('div');
    formDiv.className = 'product-selection-container mt-3';
    formDiv.id = 'productSelectionForm';
    formDiv.style.cssText = 'animation: slideInFromBottom 0.3s ease-out; width: 100%; max-width: 100%;';
    
    let formHTML = `
        <div class="card border-0 shadow-lg" style="background: linear-gradient(135deg, rgba(255, 255, 255, 0.98) 0%, rgba(249, 250, 251, 0.98) 100%); backdrop-filter: blur(20px); border-radius: 16px; padding: 24px; width: 100%; max-width: 100%; box-sizing: border-box; border: 2px solid rgba(59, 130, 246, 0.1);">
            <div class="mb-3">
                <h5 class="mb-0" style="color: #1e40af; font-weight: 400; font-size: 1.1rem;">
                    <i class="fas fa-shopping-cart me-2" style="color: #3b82f6;"></i>Product Selection
                </h5>
            </div>
            
            <form id="productSelectionFormElement" onsubmit="handleBulkProductSelection(event)">
                    <!-- Search Bar -->
                    <div class="mb-3">
                        <div class="input-group">
                            <span class="input-group-text" style="background: #dbeafe; border-radius: 8px 0 0 8px; border: 2px solid #bfdbfe; border-right: none;">
                                <i class="fas fa-search" style="color: #1e40af;"></i>
                            </span>
                            <input type="text" 
                                   class="form-control" 
                                   id="productSearchInput" 
                                   placeholder="Search products by name or code..." 
                                   onkeyup="filterProductTable()"
                                   style="background: #eff6ff; color: #1e40af; border-radius: 0 8px 8px 0; border: 2px solid #bfdbfe; border-left: none; padding: 12px; font-size: 0.95rem;"
                                   onfocus="this.style.background='#dbeafe'"
                                   onblur="this.style.background='#eff6ff'">
                        </div>
                    </div>
                    
                    <!-- Products Table -->
                    <div class="mb-3" style="max-height: 400px; overflow-y: auto; border: 2px solid #e5e7eb; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
                        <table class="table table-sm table-hover mb-0" style="font-size: 0.875rem;">
                            <thead class="table-light" style="position: sticky; top: 0; z-index: 10; background: linear-gradient(135deg, #f3f4f6 0%, #e5e7eb 100%); box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                <tr>
                                    <th style="padding: 14px; width: 45%; font-weight: 700; color: #1f2937;">Product</th>
                                    <th style="padding: 14px; width: 20%; font-weight: 700; color: #1f2937;">Price</th>
                                    <th style="padding: 14px; width: 15%; font-weight: 700; color: #1f2937;">Available</th>
                                    <th style="padding: 14px; width: 20%; font-weight: 700; color: #1f2937;">Quantity</th>
                                </tr>
                            </thead>
                            <tbody id="productTableBody" style="display: table-row-group;">
    `;
    
    products.forEach((product, index) => {
        const searchText = `${product.product_name} ${product.product_code}`.toLowerCase();
        const focSchemesJson = product.foc_schemes ? JSON.stringify(product.foc_schemes) : '[]';
        
        formHTML += `
                                <tr class="product-row" 
                                    data-product-code="${product.product_code}" 
                                    data-product-name="${product.product_name.replace(/"/g, '&quot;')}"
                                    data-search-text="${searchText}"
                                    data-price="${product.sales_price}"
                                    data-available="${product.available_for_sale}"
                                    data-foc="${product.foc || ''}"
                                    style="transition: all 0.2s;">
                                    <td style="padding: 12px;">
                                        <div style="font-weight: 600; color: #1f2937;">
                                            ${product.product_name}
                                        </div>
                                        <div style="font-size: 0.75rem; color: #6b7280; margin-top: 2px;">
                                            <i class="fas fa-barcode me-1"></i>${product.product_code}
                                        </div>
                                    </td>
                                    <td style="padding: 12px; color: #059669; font-weight: 600;">$${product.sales_price.toLocaleString()}</td>
                                    <td style="padding: 12px;">
                                        <span class="badge ${product.available_for_sale > 10 ? 'bg-success' : (product.available_for_sale > 0 ? 'bg-warning text-dark' : 'bg-danger')}" style="font-size: 0.8rem; padding: 5px 10px;">${product.available_for_sale}</span>
                                        <small class="text-muted ms-1" style="font-size: 0.7rem;">units</small>
                                    </td>
                                    <td style="padding: 12px;">
                                        <input type="number" 
                                               class="form-control form-control-sm product-quantity-input" 
                                               id="qty_${product.product_code}"
                                               data-product-foc="${product.foc || ''}"
                                               data-product-name="${product.product_name.replace(/"/g, '&quot;')}"
                                               data-foc-schemes='${focSchemesJson.replace(/'/g, "&apos;")}'
                                               min="0" 
                                               max="${product.available_for_sale}" 
                                               value="0"
                                               placeholder="0"
                                               onchange="updateSelectedProductsCount()"
                                               oninput="updateSelectedProductsCount()"
                                               style="width: 100%; min-width: 80px; max-width: 120px; text-align: center; border-radius: 8px; border: 2px solid #e5e7eb; padding: 8px 12px; font-weight: 600; font-size: 0.95rem;">
                                    </td>
                                </tr>
        `;
    });
    
    formHTML += `
                            </tbody>
                        </table>
                    </div>
                    
                    <div id="selectedProductsCount" class="mb-3 text-center p-3" style="background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%); border-radius: 10px; border: 2px dashed #3b82f6;">
                        <i class="fas fa-info-circle me-2" style="color: #2563eb;"></i>
                        <span style="color: #1e40af; font-weight: 600; font-size: 0.9rem;">Select quantities above to add products to your cart</span>
                    </div>
                    
                    <div class="d-grid gap-3 mb-3" style="grid-template-columns: repeat(2, 1fr);">
                        <button type="submit" class="btn btn-primary" 
                                style="border-radius: 10px; padding: 12px 20px; font-weight: 600; font-size: 0.9rem; background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); border: none; box-shadow: 0 3px 10px rgba(59, 130, 246, 0.3);">
                            <i class="fas fa-cart-plus me-2"></i>Add to Cart
                        </button>
                        <button type="button" class="btn" onclick="clearBulkProductForm()"
                                style="border-radius: 10px; padding: 12px 20px; font-weight: 600; font-size: 0.9rem; background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); border: none; color: white; box-shadow: 0 3px 10px rgba(59, 130, 246, 0.3);">
                            <i class="fas fa-eraser me-2"></i>Clear All
                        </button>
                        <button type="button" class="btn" onclick="viewCart()"
                                style="border-radius: 10px; padding: 12px 20px; font-weight: 600; font-size: 0.9rem; background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); border: none; color: white; box-shadow: 0 3px 10px rgba(59, 130, 246, 0.3);">
                            <i class="fas fa-shopping-cart me-2"></i>View Cart
                        </button>
                        <button type="button" class="btn" onclick="confirmCart()"
                                style="border-radius: 10px; padding: 12px 20px; font-weight: 600; font-size: 0.9rem; background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); border: none; color: white; box-shadow: 0 3px 10px rgba(59, 130, 246, 0.3);">
                            <i class="fas fa-check-circle me-2"></i>Confirm Cart
                        </button>
                    </div>
                    <div class="d-flex justify-content-center mt-2 gap-2">
                        ${showChangeCustomer ? `
                        <button type="button" class="btn btn-outline-info" onclick="handleChangeCustomer()"
                                style="border-radius: 8px; padding: 8px 14px; font-size: 0.8rem;">
                            <i class="fas fa-user-edit me-2"></i>Change Customer
                        </button>
                        ` : ''}
                        <button type="button" class="btn btn-outline-danger" onclick="this.closest('.product-selection-container').remove()"
                                style="border-radius: 8px; padding: 8px 14px; font-size: 0.8rem;">
                            <i class="fas fa-times me-2"></i>Cancel
                        </button>
                    </div>
                </form>
            </div>
        </div>
    `;
    
    formDiv.innerHTML = formHTML;
    messageBubble.appendChild(formDiv); // Append to the message bubble instead of messagesDiv
    
    // Initialize product count
    updateSelectedProductsCount();
    
    // Scroll to form
    messagesDiv.scrollTo({
        top: messagesDiv.scrollHeight,
        behavior: 'smooth'
    });
}

// Filter product table by search text
function filterProductTable() {
    const searchInput = document.getElementById('productSearchInput');
    const rows = document.querySelectorAll('#productTableBody tr.product-row');
    
    if (!searchInput) return;
    
    const searchTerm = searchInput.value.toLowerCase().trim();
    
    if (!searchTerm) {
        // Show all rows if search is empty
        rows.forEach(row => {
            row.style.display = '';
            row.style.order = '';
        });
        return;
    }
    
    // Create array of rows with match scores
    const rowsWithScores = Array.from(rows).map(row => {
        const searchText = row.getAttribute('data-search-text') || '';
        const productName = row.getAttribute('data-product-name') || '';
        const productCode = row.getAttribute('data-product-code') || '';
        
        let score = 0;
        
        // Exact code match (highest priority)
        if (productCode.toLowerCase() === searchTerm) {
            score = 1000;
        }
        // Code starts with search term
        else if (productCode.toLowerCase().startsWith(searchTerm)) {
            score = 500;
        }
        // Exact name match
        else if (productName.toLowerCase() === searchTerm) {
            score = 400;
        }
        // Name starts with search term
        else if (productName.toLowerCase().startsWith(searchTerm)) {
            score = 300;
        }
        // Contains search term in name
        else if (productName.toLowerCase().includes(searchTerm)) {
            score = 200;
        }
        // Contains search term anywhere
        else if (searchText.includes(searchTerm)) {
            score = 100;
        }
        
        return { row, score };
    });
    
    // Sort by score and update display
    rowsWithScores.sort((a, b) => b.score - a.score);
    
    rowsWithScores.forEach(({ row, score }, index) => {
        if (score > 0) {
            row.style.display = '';
            row.style.order = index;
        } else {
            row.style.display = 'none';
        }
    });
}

// Update selected products count with dynamic FOC information
function updateSelectedProductsCount() {
    const countDiv = document.getElementById('selectedProductsCount');
    if (!countDiv) return;
    
    const rows = document.querySelectorAll('#productTableBody tr');
    let count = 0;
    let focItems = [];
    
    rows.forEach(row => {
        const quantityInput = row.querySelector('.product-quantity-input');
        const quantity = parseInt(quantityInput.value) || 0;
        
        if (quantity > 0) {
            count++;
            
            // Get FOC schemes from data attribute
            const productName = quantityInput.getAttribute('data-product-name') || row.getAttribute('data-product-name') || '';
            const focSchemesAttr = quantityInput.getAttribute('data-foc-schemes');
            
            if (focSchemesAttr) {
                try {
                    const focSchemes = JSON.parse(focSchemesAttr);
                    
                    console.log('FOC Check:', {
                        productName: productName,
                        quantity: quantity,
                        focSchemes: focSchemes
                    });
                    
                    if (focSchemes && focSchemes.length > 0) {
                        // Find the best matching scheme for this quantity
                        // Start from highest tier and work down
                        let bestScheme = null;
                        let bestThreshold = 0;
                        
                        focSchemes.forEach(scheme => {
                            const buyQty = scheme.buy;
                            // If quantity meets this threshold and it's higher than current best
                            if (quantity >= buyQty && buyQty > bestThreshold) {
                                bestScheme = scheme;
                                bestThreshold = buyQty;
                            }
                        });
                        
                        if (bestScheme) {
                            const buyQty = bestScheme.buy;
                            const freeQty = bestScheme.free;
                            
                            // Calculate how many free items user will get
                            const sets = Math.floor(quantity / buyQty);
                            const totalFree = sets * freeQty;
                            
                            console.log('FOC Calculation:', {
                                bestScheme: bestScheme,
                                buyQty: buyQty,
                                freeQty: freeQty,
                                sets: sets,
                                totalFree: totalFree
                            });
                            
                            if (totalFree > 0) {
                                focItems.push({
                                    name: productName,
                                    ordered: quantity,
                                    free: totalFree,
                                    total: quantity + totalFree,
                                    scheme: `Buy ${buyQty} Get ${freeQty} Free`
                                });
                            }
                        }
                    }
                } catch (e) {
                    console.error('Error parsing FOC schemes:', e);
                }
            }
        }
    });
    
    console.log('FOC Items to display:', focItems);
    
    if (count === 0) {
        countDiv.innerHTML = '<i class="fas fa-info-circle me-2" style="color: #2563eb;"></i><span style="color: #1e40af; font-weight: 600; font-size: 0.9rem;">Select quantities above to add products to your cart</span>';
        countDiv.style.cssText = 'background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%); border-radius: 10px; border: 2px dashed #3b82f6; padding: 12px; text-align: center;';
    } else {
        let html = `<div style="background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%); border-radius: 10px; border: 2px solid #10b981; padding: 12px;">
            <div style="text-align: center; margin-bottom: ${focItems.length > 0 ? '10px' : '0'};">
                <i class="fas fa-check-circle me-2" style="color: #065f46;"></i>
                <strong style="color: #065f46; font-size: 0.95rem;">${count} product(s) selected - Ready to add to cart</strong>
            </div>`;
        
        if (focItems.length > 0) {
            html += `
                <div style="background: rgba(255, 255, 255, 0.9); border-radius: 10px; padding: 15px; margin-top: 12px; border: 2px solid #34d399; box-shadow: 0 2px 8px rgba(16, 185, 129, 0.2);">
                    <div style="color: #065f46; font-weight: 700; margin-bottom: 12px; font-size: 1rem; text-align: center;">
                        <i class="fas fa-gift me-2" style="font-size: 1.1rem;"></i>🎁 FOC Items You'll Receive FREE!
                    </div>
                    <ul style="margin: 0; padding-left: 20px; color: #047857; font-size: 0.9rem; text-align: left; line-height: 1.8;">`;
            
            focItems.forEach(item => {
                html += `<li style="margin-bottom: 6px;">
                    <strong style="color: #065f46;">${item.name}:</strong> 
                    Order ${item.ordered} units, Get <span style="color: #059669; font-weight: 700; font-size: 1.05rem; background: rgba(16, 185, 129, 0.15); padding: 2px 8px; border-radius: 4px;">${item.free} FREE</span> 
                    → Total: <strong>${item.total} units</strong>
                    <br><small style="color: #6b7280; font-size: 0.8rem; margin-left: 0px;"><i class="fas fa-tag me-1"></i>${item.scheme}</small>
                </li>`;
            });
            
            html += `</ul></div>`;
        }
        
        html += '</div>';
        countDiv.innerHTML = html;
        countDiv.style.cssText = 'text-align: center; margin-bottom: 15px;';
    }
}

// Handle bulk product selection
async function handleBulkProductSelection(event) {
    event.preventDefault();
    
    const form = event.target;
    const submitBtn = form.querySelector('button[type="submit"]');
    const originalText = submitBtn.innerHTML;
    
    const rows = document.querySelectorAll('#productTableBody tr');
    let productsToAdd = [];
    
    // Collect all products with quantity > 0
    rows.forEach(row => {
        const quantityInput = row.querySelector('.product-quantity-input');
        const quantity = parseInt(quantityInput.value) || 0;
        
        if (quantity > 0) {
            productsToAdd.push({
                code: row.getAttribute('data-product-code'),
                name: row.getAttribute('data-product-name'),
                quantity: quantity,
                price: parseFloat(row.getAttribute('data-price'))
            });
        }
    });
    
    if (productsToAdd.length === 0) {
        alert('Please enter quantities for at least one product.');
        return;
    }
    
    // Disable form and show loading
    form.querySelectorAll('button, input').forEach(el => el.disabled = true);
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Adding products...';
    
    // Add each product to cart via API (bypasses LLM to avoid misinterpretation)
    let successCount = 0;
    let failedProducts = [];
    
    for (const product of productsToAdd) {
        try {
            const response = await fetch('/enhanced-chat/cart/add', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    product_code: product.code,
                    quantity: product.quantity
                })
            });
            
            const data = await response.json();
            
            if (response.ok && data.success) {
                successCount++;
            } else {
                failedProducts.push({name: product.name, error: data.error});
            }
        } catch (error) {
            console.error(`Error adding ${product.code}:`, error);
            failedProducts.push({name: product.name, error: 'Network error'});
        }
    }
    
    // Re-enable all form controls
    form.querySelectorAll('button, input').forEach(el => {
        el.disabled = false;
    });
    submitBtn.innerHTML = originalText;
    
    // DON'T remove the product selection form - keep it visible!
    // Just clear the quantities and show success message
    
    // Clear all quantity inputs
    const quantityInputs = document.querySelectorAll('.product-quantity-input');
    quantityInputs.forEach(input => {
        input.value = 0;
    });
    
    // Update the count display
    updateSelectedProductsCount();
    
    // Show success message as a toast/notification within the form
    const countDiv = document.getElementById('selectedProductsCount');
    if (countDiv) {
        let message = successCount > 0 
            ? `Successfully added ${successCount} product(s) to cart!` 
            : 'No products were added';
        
        if (failedProducts.length > 0) {
            message += ` (${failedProducts.length} failed)`;
        }
        
        // Show success message
        countDiv.innerHTML = `
            <div style="text-align: center;">
                <i class="fas fa-check-circle me-2" style="color: #059669; font-size: 1.2rem;"></i>
                <strong style="color: #059669; font-size: 1rem;">${message}</strong>
            </div>
        `;
        countDiv.style.cssText = 'background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%); border-radius: 10px; border: 2px solid #10b981; padding: 15px; text-align: center; margin-bottom: 15px;';
        
        // Reset to default message after 3 seconds
        setTimeout(() => {
            countDiv.innerHTML = '<i class="fas fa-info-circle me-2" style="color: #2563eb;"></i><span style="color: #1e40af; font-weight: 600; font-size: 0.9rem;">Select quantities above to add products to your cart</span>';
            countDiv.style.cssText = 'background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%); border-radius: 10px; border: 2px dashed #3b82f6; padding: 12px; text-align: center;';
        }, 3000);
    }
    
    // Also add a bot message for confirmation
    addMessage(`✅ Successfully added ${successCount} product(s) to cart!`, 'bot');
    
    // Scroll to top of form to show success message
    const messagesDiv = document.getElementById('chatMessages');
    if (messagesDiv) {
        messagesDiv.scrollTo({
            top: messagesDiv.scrollHeight,
            behavior: 'smooth'
        });
    }
}

// Clear bulk product form
function clearBulkProductForm() {
    const quantityInputs = document.querySelectorAll('.product-quantity-input');
    quantityInputs.forEach(input => {
        input.value = 0;
    });
    const searchInput = document.getElementById('productSearchInput');
    if (searchInput) {
        searchInput.value = '';
        filterProductTable();
    }
    updateSelectedProductsCount();
}

// Make functions globally accessible
window.filterProductTable = filterProductTable;
window.updateSelectedProductsCount = updateSelectedProductsCount;
window.handleBulkProductSelection = handleBulkProductSelection;
window.clearBulkProductForm = clearBulkProductForm;

function increaseQuantity() {
    const quantityInput = document.getElementById('productQuantity');
    const maxQuantity = parseInt(quantityInput.getAttribute('max')) || 9999;
    const currentValue = parseInt(quantityInput.value) || 1;
    if (currentValue < maxQuantity) {
        quantityInput.value = currentValue + 1;
        updateQuantityFOC();
    }
}

function decreaseQuantity() {
    const quantityInput = document.getElementById('productQuantity');
    const currentValue = parseInt(quantityInput.value) || 1;
    if (currentValue > 1) {
        quantityInput.value = currentValue - 1;
        updateQuantityFOC();
    }
}

async function updateQuantityFOC() {
    /** Update FOC information when quantity changes */
    const productSelect = document.getElementById('productSelect');
    const quantityInput = document.getElementById('productQuantity');
    
    if (!productSelect || !quantityInput) return;
    
    const selectedOption = productSelect.options[productSelect.selectedIndex];
    if (!selectedOption || !selectedOption.value) {
        // Reset display
        updateProductPriceDisplay();
        return;
    }
    
    const productCode = selectedOption.value;
    const quantity = parseInt(quantityInput.value) || 1;
    const price = parseFloat(selectedOption.getAttribute('data-price')) || 0;
    
    try {
        // Fetch pricing with FOC information
        const response = await fetch('/chat/api/pricing', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({
                product_codes: [productCode],
                quantities: [quantity]
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            const pricing = data.pricing && data.pricing[0] ? data.pricing[0] : null;
            
            if (pricing) {
                // Update price display
                const productPriceSpan = document.getElementById('productPrice');
                const productTotalSpan = document.getElementById('productTotal');
                const paidQuantitySpan = document.getElementById('paidQuantity');
                const freeQuantitySpan = document.getElementById('freeQuantity');
                const totalQuantitySpan = document.getElementById('totalQuantity');
                const focInfoDiv = document.getElementById('focInfo');
                const focDetailsSpan = document.getElementById('focDetails');
                
                if (productPriceSpan) productPriceSpan.textContent = pricing.base_price.toFixed(2);
                if (productTotalSpan) productTotalSpan.textContent = pricing.total_amount.toFixed(2);
                
                // Update FOC information
                const freeQuantity = pricing.free_quantity || 0;
                const paidQuantity = pricing.paid_quantity || quantity;
                const totalQuantity = pricing.total_quantity || quantity;
                const schemeName = pricing.scheme_name || '';
                
                if (paidQuantitySpan) paidQuantitySpan.textContent = paidQuantity;
                if (freeQuantitySpan) freeQuantitySpan.textContent = freeQuantity;
                if (totalQuantitySpan) totalQuantitySpan.textContent = totalQuantity;
                
                // Show/hide FOC info
                if (focInfoDiv && focDetailsSpan) {
                    if (freeQuantity > 0) {
                        focDetailsSpan.innerHTML = `
                            You ordered <strong>${quantity} units</strong>.<br>
                            <strong>You'll receive ${freeQuantity} free units!</strong><br>
                            Total: <strong>${totalQuantity} units</strong> (You pay for ${paidQuantity} units)<br>
                            <small>Scheme: ${schemeName || 'FOC Applied'}</small>
                        `;
                        focInfoDiv.style.display = 'block';
                    } else {
                        focInfoDiv.style.display = 'none';
                    }
                }
            } else {
                // Fallback to basic calculation
                updateProductPriceDisplay();
            }
        } else {
            // Fallback to basic calculation
            updateProductPriceDisplay();
        }
    } catch (error) {
        console.error('Error fetching FOC information:', error);
        // Fallback to basic calculation
        updateProductPriceDisplay();
    }
}

function updateProductPriceDisplay() {
    /** Basic price display without FOC (fallback) */
    const productSelect = document.getElementById('productSelect');
    const quantityInput = document.getElementById('productQuantity');
    const productPriceSpan = document.getElementById('productPrice');
    const productTotalSpan = document.getElementById('productTotal');
    const paidQuantitySpan = document.getElementById('paidQuantity');
    const freeQuantitySpan = document.getElementById('freeQuantity');
    const totalQuantitySpan = document.getElementById('totalQuantity');
    const focInfoDiv = document.getElementById('focInfo');
    
    const selectedOption = productSelect ? productSelect.options[productSelect.selectedIndex] : null;
    if (selectedOption && selectedOption.value) {
        const price = parseFloat(selectedOption.getAttribute('data-price')) || 0;
        const quantity = parseInt(quantityInput.value) || 1;
        const total = price * quantity;
        
        if (productPriceSpan) productPriceSpan.textContent = price.toFixed(2);
        if (productTotalSpan) productTotalSpan.textContent = total.toFixed(2);
        if (paidQuantitySpan) paidQuantitySpan.textContent = quantity;
        if (freeQuantitySpan) freeQuantitySpan.textContent = '0';
        if (totalQuantitySpan) totalQuantitySpan.textContent = quantity;
        if (focInfoDiv) focInfoDiv.style.display = 'none';
    }
}

async function handleProductSelection(event) {
    event.preventDefault();
    
    const form = event.target;
    const formData = new FormData(form);
    const productCode = formData.get('product_code');
    const quantity = parseInt(formData.get('quantity'));
    
    if (!productCode || !quantity || quantity < 1) {
        alert('Please select a product and enter a valid quantity.');
        return;
    }
    
    // Get product details from select option
    const productSelect = document.getElementById('productSelect');
    const selectedOption = productSelect.options[productSelect.selectedIndex];
    const productName = selectedOption.getAttribute('data-name');
    const available = parseInt(selectedOption.getAttribute('data-available'));
    
    if (quantity > available) {
        alert(`Insufficient stock. Only ${available} units available.`);
        return;
    }
    
    // Disable form during submission
    form.querySelectorAll('button, input, select').forEach(el => {
        el.disabled = true;
    });
    
    // Show loading state
    const submitBtn = form.querySelector('button[type="submit"]');
    const originalText = submitBtn.innerHTML;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Adding...';
    
    try {
        // Add product to cart via API - include product name in message for proper identification
        const productName = selectedOption.getAttribute('data-name') || '';
        const message = productName ? 
            `add ${quantity} ${productCode} (${productName}) to cart` : 
            `add ${quantity} ${productCode} to cart`;
        
        const response = await fetch('/enhanced-chat/message', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({ 
                message: message
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.error) {
            addMessage(`Error: ${data.error}`, 'bot', 'error');
        } else {
            // Show success message
            addMessage(`✅ Added ${quantity} unit(s) of ${productName} (${productCode}) to cart!`, 'bot');
            
            // Update cart display
            if (data.cart_items) {
                updateCartDisplay(data.cart_items);
            }
            
            // DON'T remove the product selection form - keep it visible
            // User can add more products or click "Confirm Cart"
            
            // Reset form for next selection
            form.reset();
            const quantityInput = document.getElementById('productQuantity');
            if (quantityInput) {
                quantityInput.value = 1;
                updateProductPriceDisplay();
            }
        }
    } catch (error) {
        console.error('Error adding product to cart:', error);
        addMessage('Sorry, I encountered an error adding the product to cart. Please try again.', 'bot', 'error');
    } finally {
        // Re-enable form
        form.querySelectorAll('button, input, select').forEach(el => {
            el.disabled = false;
        });
        submitBtn.innerHTML = originalText;
    }
}

function clearProductForm() {
    const form = document.getElementById('productSelectionFormElement');
    if (form) {
        form.reset();
        document.getElementById('productQuantity').value = 1;
        updateProductPriceDisplay();
    }
}

// Enhanced customer selection form for MRs
function addCustomerSelectionForm(customers) {
    const messagesDiv = document.getElementById('chatMessages');
    
    // Find the last bot message
    const botMessages = messagesDiv.querySelectorAll('.message.bot');
    let lastBotMessage = null;
    
    if (botMessages.length > 0) {
        lastBotMessage = botMessages[botMessages.length - 1];
    }
    
    if (!lastBotMessage) return; // Exit if no bot message found
    
    // Find the inner message bubble div (the one with bg-light class)
    const messageBubble = lastBotMessage.querySelector('.message-bubble .bg-light');
    if (!messageBubble) return; // Exit if bubble not found
    
    const formContainer = document.createElement('div');
    formContainer.className = 'customer-selection-container mt-3';
    formContainer.style.cssText = 'animation: slideInFromBottom 0.3s ease-out; width: 100%; max-width: 100%;';
    
    const formCard = document.createElement('div');
    formCard.className = 'card border-0 shadow-sm';
    formCard.style.cssText = `
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(20px);
        border-radius: 16px;
        padding: 20px;
        width: 100%;
        box-sizing: border-box;
    `;
    
    // Create customer table first (with scrollable container)
    let tableHTML = `
        <div class="mb-3" style="overflow-x: auto; max-width: 100%;">
            <table class="table table-bordered table-hover" style="font-size: 0.875rem; margin-bottom: 0; min-width: 100%; white-space: nowrap;">
                <thead style="background-color: #f8f9fa;">
                    <tr>
                        <th style="padding: 10px; border: 1px solid #dee2e6; font-weight: 600; white-space: nowrap;">Customer Name</th>
                        <th style="padding: 10px; border: 1px solid #dee2e6; font-weight: 600; white-space: nowrap;">Customer ID</th>
                    </tr>
                </thead>
                <tbody>
                    ${customers.map(customer => `
                        <tr>
                            <td style="padding: 10px; border: 1px solid #dee2e6; white-space: nowrap;">${customer.name}</td>
                            <td style="padding: 10px; border: 1px solid #dee2e6; white-space: nowrap;">${customer.unique_id}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;
    
    formCard.innerHTML = `
        <h6 class="mb-3" style="color: #2563eb; font-weight: 600;">
            <i class="fas fa-users me-2"></i>Select Customer
        </h6>
        <form id="customerSelectionForm" onsubmit="handleCustomerSelection(event)">
            <div class="mb-3 position-relative">
                <label for="customerSearchInput" class="form-label" style="font-weight: 500;">Search for a customer:</label>
                <input type="text" class="form-control form-control-lg" id="customerSearchInput" 
                    placeholder="Type customer name or ID..." autocomplete="off"
                    style="border-radius: 10px; border: 2px solid #e5e7eb; padding: 12px; font-size: 0.95rem;">
                <input type="hidden" id="selectedCustomerId" name="customer_id" required>
                <input type="hidden" id="selectedCustomerUniqueId" name="customer_unique_id">
                
                <!-- Customer Dropdown -->
                <div id="customerDropdown" class="position-absolute w-100 bg-white border rounded shadow-lg" 
                     style="top: 100%; z-index: 1000; max-height: 300px; overflow-y: auto; display: none; margin-top: 2px;">
                    <div id="customerDropdownList"></div>
                </div>
            </div>
            <div class="d-flex gap-2">
                <button type="submit" class="btn btn-primary flex-grow-1" 
                    style="border-radius: 8px; padding: 8px 14px; font-weight: 600; font-size: 0.8rem;">
                    <i class="fas fa-check me-2"></i>Select Customer
                </button>
                <button type="button" class="btn btn-outline-secondary" onclick="this.closest('.customer-selection-container').remove()"
                    style="border-radius: 8px; padding: 8px 14px; font-size: 0.8rem;">
                    <i class="fas fa-times"></i> Cancel
                </button>
            </div>
        </form>
    `;
    
    // Store customers data for search functionality
    formCard.dataset.customers = JSON.stringify(customers);
    
    // Add event listener for customer search after form is added to DOM
    setTimeout(() => {
        const customerSearchInput = document.getElementById('customerSearchInput');
        const customerDropdown = document.getElementById('customerDropdown');
        const customerDropdownList = document.getElementById('customerDropdownList');
        
        if (customerSearchInput && customerDropdown && customerDropdownList) {
            // Search customers as user types
            customerSearchInput.addEventListener('input', function(e) {
                const query = e.target.value.trim().toLowerCase();
                
                if (query.length < 1) {
                    customerDropdown.style.display = 'none';
                    return;
                }
                
                const filtered = customers.filter(customer => {
                    const nameMatch = customer.name.toLowerCase().includes(query);
                    const idMatch = customer.unique_id.toLowerCase().includes(query);
                    return nameMatch || idMatch;
                });
                
                if (filtered.length > 0) {
                    let html = '';
                    filtered.forEach(customer => {
                        html += `
                            <div class="customer-dropdown-item p-2 border-bottom" 
                                 style="cursor: pointer; transition: background 0.2s;"
                                 onmouseover="this.style.background='#f0f9ff'"
                                 onmouseout="this.style.background='white'"
                                 onclick="selectCustomerFromDropdown('${customer.id}', '${customer.unique_id}', '${customer.name.replace(/'/g, "\\'")}')">
                                <div style="font-weight: 600; color: #1e40af;">${customer.name}</div>
                                <div style="font-size: 0.8rem; color: #6b7280;">ID: ${customer.unique_id}</div>
                            </div>
                        `;
                    });
                    customerDropdownList.innerHTML = html;
                    customerDropdown.style.display = 'block';
                } else {
                    customerDropdownList.innerHTML = '<div class="p-3 text-center text-muted">No customers found</div>';
                    customerDropdown.style.display = 'block';
                }
            });
            
            // Close dropdown when clicking outside
            document.addEventListener('click', function(e) {
                if (!customerSearchInput.contains(e.target) && !customerDropdown.contains(e.target)) {
                    customerDropdown.style.display = 'none';
                }
            });
        }
    }, 100);
    
    formContainer.appendChild(formCard);
    messageBubble.appendChild(formContainer); // Append to the message bubble instead of messagesDiv
    
    // No need to show customer details - table already shows all info
}

// Show customer table as separate message
function showCustomerTable(customers) {
    const messagesDiv = document.getElementById('chatMessages');
    
    // Find the last bot message
    const botMessages = messagesDiv.querySelectorAll('.message.bot');
    let lastBotMessage = null;
    
    if (botMessages.length > 0) {
        lastBotMessage = botMessages[botMessages.length - 1];
    }
    
    if (!lastBotMessage) return;
    
    // Find the inner message bubble div
    const messageBubble = lastBotMessage.querySelector('.message-bubble .bg-light');
    if (!messageBubble) return;
    
    // Create table container
    const tableContainer = document.createElement('div');
    tableContainer.className = 'customer-table-container mt-3 mb-3';
    tableContainer.style.cssText = 'animation: slideInFromBottom 0.3s ease-out; width: 100%; max-width: 100%; overflow-x: auto;';
    
    let tableHTML = `
        <table class="table table-bordered table-hover" style="font-size: 0.875rem; margin-bottom: 0; min-width: 100%; white-space: nowrap;">
            <thead style="background-color: #f8f9fa;">
                <tr>
                    <th style="padding: 10px; border: 1px solid #dee2e6; font-weight: 600; white-space: nowrap;">Customer Name</th>
                    <th style="padding: 10px; border: 1px solid #dee2e6; font-weight: 600; white-space: nowrap;">Customer ID</th>
                </tr>
            </thead>
            <tbody>
                ${customers.map(customer => `
                    <tr>
                        <td style="padding: 10px; border: 1px solid #dee2e6; white-space: nowrap;">${customer.name}</td>
                        <td style="padding: 10px; border: 1px solid #dee2e6; white-space: nowrap;">${customer.unique_id}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
    
    tableContainer.innerHTML = tableHTML;
    messageBubble.appendChild(tableContainer);
}

// Show product table as separate message
function showProductTable(products) {
    const messagesDiv = document.getElementById('chatMessages');
    
    // Find the last bot message
    const botMessages = messagesDiv.querySelectorAll('.message.bot');
    let lastBotMessage = null;
    
    if (botMessages.length > 0) {
        lastBotMessage = botMessages[botMessages.length - 1];
    }
    
    if (!lastBotMessage) return;
    
    // Find the inner message bubble div
    const messageBubble = lastBotMessage.querySelector('.message-bubble .bg-light');
    if (!messageBubble) return;
    
    // Create table container with rounded edges
    const tableContainer = document.createElement('div');
    tableContainer.className = 'product-table-container mt-3 mb-3';
    tableContainer.style.cssText = 'animation: slideInFromBottom 0.3s ease-out; width: 100%; max-width: 100%; overflow-x: auto; border-radius: 12px; overflow: hidden;';
    
    let tableHTML = `
        <table class="table table-bordered table-hover mb-0" style="font-size: 0.875rem; margin-bottom: 0; min-width: 100%; white-space: nowrap; border-radius: 12px; overflow: hidden;">
            <thead style="background-color: #f8f9fa;">
                <tr>
                    <th style="padding: 10px; border: 1px solid #dee2e6; font-weight: 600; white-space: nowrap;">Product Name</th>
                    <th style="padding: 10px; border: 1px solid #dee2e6; font-weight: 600; white-space: nowrap;">Price</th>
                    <th style="padding: 10px; border: 1px solid #dee2e6; font-weight: 600; white-space: nowrap;">Available Quantity</th>
                </tr>
            </thead>
            <tbody>
                ${products.map(product => `
                    <tr>
                        <td style="padding: 10px; border: 1px solid #dee2e6; white-space: nowrap;">
                            <strong>${product.product_name}</strong><br>
                            <small class="text-muted">${product.product_code}</small>
                        </td>
                        <td style="padding: 10px; border: 1px solid #dee2e6; white-space: nowrap;">$${(product.sales_price || 0).toFixed(2)}</td>
                        <td style="padding: 10px; border: 1px solid #dee2e6; white-space: nowrap;">${product.available_for_sale || 0} units</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
    
    tableContainer.innerHTML = tableHTML;
    messageBubble.appendChild(tableContainer);
    
    // Scroll to bottom
    messagesDiv.scrollTo({
        top: messagesDiv.scrollHeight,
        behavior: 'smooth'
    });
}

// Show orders table as separate message
function showOrdersTable(orders) {
    const messagesDiv = document.getElementById('chatMessages');
    
    // Find the last bot message
    const botMessages = messagesDiv.querySelectorAll('.message.bot');
    let lastBotMessage = null;
    
    if (botMessages.length > 0) {
        lastBotMessage = botMessages[botMessages.length - 1];
    }
    
    if (!lastBotMessage) return;
    
    // Find the inner message bubble div
    const messageBubble = lastBotMessage.querySelector('.message-bubble .bg-light');
    if (!messageBubble) return;
    
    // Create table container with rounded edges and proper overflow handling
    const tableContainer = document.createElement('div');
    tableContainer.className = 'orders-table-container mt-3 mb-3';
    tableContainer.style.cssText = 'animation: slideInFromBottom 0.3s ease-out; width: 100%; max-width: 100%; overflow-x: auto; box-sizing: border-box;';
    
    let tableHTML = `
        <div style="overflow-x: auto; width: 100%; border-radius: 12px; overflow: hidden;">
            <table class="table table-bordered table-hover mb-0" style="font-size: 0.875rem; margin-bottom: 0; width: 100%; min-width: 300px; white-space: nowrap;">
                <thead style="background-color: #f8f9fa;">
                    <tr>
                        <th style="padding: 10px; border: 1px solid #dee2e6; font-weight: 600; white-space: nowrap;">Order ID</th>
                    </tr>
                </thead>
                <tbody>
                    ${orders.map(order => `
                        <tr>
                            <td style="padding: 10px; border: 1px solid #dee2e6; white-space: nowrap;">${order.order_id}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;
    
    tableContainer.innerHTML = tableHTML;
    messageBubble.appendChild(tableContainer);
    
    // Scroll to bottom
    messagesDiv.scrollTo({
        top: messagesDiv.scrollHeight,
        behavior: 'smooth'
    });
}

// Add order selection form
function addOrderSelectionForm(orders, filters = null) {
    const messagesDiv = document.getElementById('chatMessages');
    
    // Find the last bot message
    const botMessages = messagesDiv.querySelectorAll('.message.bot');
    let lastBotMessage = null;
    
    if (botMessages.length > 0) {
        lastBotMessage = botMessages[botMessages.length - 1];
    }
    
    if (!lastBotMessage) return; // Exit if no bot message found
    
    // Find the inner message bubble div (the one with bg-light class)
    const messageBubble = lastBotMessage.querySelector('.message-bubble .bg-light');
    if (!messageBubble) return; // Exit if bubble not found
    
    const formContainer = document.createElement('div');
    formContainer.className = 'order-selection-container mt-3';
    formContainer.style.cssText = 'animation: slideInFromBottom 0.3s ease-out; width: 100%; max-width: 100%;';
    
    const formCard = document.createElement('div');
    formCard.className = 'card border-0 shadow-sm';
    formCard.style.cssText = `
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(20px);
        border-radius: 16px;
        padding: 20px;
        width: 100%;
        box-sizing: border-box;
    `;
    
    // Store original orders for filtering
    formContainer._originalOrders = orders;
    
    // Check if we have filters (for distributor view)
    const isDistributorView = filters && (filters.mr_names || filters.statuses || filters.dates);
    
    // Get unique values for filters
    const uniqueDates = filters?.dates || [...new Set(orders.map(o => o.order_date))].sort().reverse();
    const uniqueStatuses = filters?.statuses || [...new Set(orders.map(o => o.status || o.status_raw))].sort();
    const uniqueMRs = filters?.mr_names || [];
    
    formCard.innerHTML = `
        <h6 class="mb-3" style="color: #2563eb; font-weight: 600;">
            <i class="fas fa-${isDistributorView ? 'list-check' : 'truck'} me-2"></i>${isDistributorView ? 'Order Management Dashboard' : 'Select Order to Track'}
        </h6>
        <form id="orderSelectionForm" onsubmit="handleOrderSelection(event)">
            ${isDistributorView ? `
            <div class="mb-3">
                <label for="mrFilter" class="form-label" style="font-weight: 500;">
                    <i class="fas fa-user me-2"></i>Filter by MR Name:
                </label>
                <select class="form-select form-select-sm" id="mrFilter" 
                    style="border-radius: 8px; border: 1.5px solid #e5e7eb; padding: 8px 12px; font-size: 0.875rem;"
                    onchange="filterOrdersByAll()">
                    <option value="">-- All MRs --</option>
                    ${uniqueMRs.map(mr => `
                        <option value="${mr}">${mr}</option>
                    `).join('')}
                </select>
            </div>
            ` : ''}
            <div class="mb-3">
                <label for="dateFilter" class="form-label" style="font-weight: 500;">
                    <i class="fas fa-calendar-alt me-2"></i>Filter by Date:
                </label>
                <select class="form-select form-select-sm" id="dateFilter" 
                    style="border-radius: 8px; border: 1.5px solid #e5e7eb; padding: 8px 12px; font-size: 0.875rem;"
                    onchange="${isDistributorView ? 'filterOrdersByAll()' : 'filterOrdersByDateAndStatus()'}">
                    <option value="">-- All Dates --</option>
                    ${uniqueDates.map(date => `
                        <option value="${date}">${date}</option>
                    `).join('')}
                </select>
            </div>
            <div class="mb-3">
                <label for="statusFilter" class="form-label" style="font-weight: 500;">
                    <i class="fas fa-filter me-2"></i>Filter by Status:
                </label>
                <select class="form-select form-select-sm" id="statusFilter" 
                    style="border-radius: 8px; border: 1.5px solid #e5e7eb; padding: 8px 12px; font-size: 0.875rem;"
                    onchange="${isDistributorView ? 'filterOrdersByAll()' : 'filterOrdersByDateAndStatus()'}">
                    <option value="">-- All Statuses --</option>
                    ${uniqueStatuses.map(status => `
                        <option value="${status}">${status.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}</option>
                    `).join('')}
                </select>
            </div>
            <div class="mb-3">
                <label for="orderSelect" class="form-label" style="font-weight: 500;">
                    <i class="fas fa-box me-2"></i>Choose an order:
                </label>
                <select class="form-select form-select-lg" id="orderSelect" name="order_id" required 
                    style="border-radius: 10px; border: 2px solid #e5e7eb; padding: 12px; font-size: 0.95rem;">
                    <option value="">-- Select Order --</option>
                    ${orders.map(order => `
                        <option value="${order.order_id}" 
                            data-status="${order.status || order.status_raw}"
                            data-total="${order.total_amount}"
                            data-date="${order.order_date}"
                            data-mr="${order.mr_name || ''}">
                            ${order.order_id} - ${order.mr_name || 'N/A'} - ${order.status_display} - $${order.total_amount ? order.total_amount.toLocaleString() : '0'} - ${order.order_datetime || order.order_date}
                        </option>
                    `).join('')}
                </select>
                <small class="text-muted d-block mt-1">
                    <i class="fas fa-info-circle me-1"></i>
                    ${isDistributorView ? 'Select an order to view details and confirm/reject' : 'Select an order to track'}
                </small>
            </div>
            <div class="d-flex gap-2">
                <button type="submit" class="btn btn-primary flex-grow-1" 
                    style="border-radius: 8px; padding: 8px 14px; font-weight: 600; font-size: 0.8rem;">
                    <i class="fas fa-search me-2"></i>View Order Details
                </button>
                <button type="button" class="btn btn-outline-secondary" onclick="this.closest('.order-selection-container').remove()"
                    style="border-radius: 8px; padding: 8px 14px; font-size: 0.8rem;">
                    <i class="fas fa-times"></i> Cancel
                </button>
            </div>
        </form>
    `;
    
    formContainer.appendChild(formCard);
    messageBubble.appendChild(formContainer); // Append to the message bubble instead of messagesDiv
}

// Filter orders by all filters (MR name, date, status) - for distributors
function filterOrdersByAll() {
    const formContainer = document.querySelector('.order-selection-container');
    if (!formContainer || !formContainer._originalOrders) return;
    
    const orderSelect = document.getElementById('orderSelect');
    const mrFilter = document.getElementById('mrFilter');
    const dateFilter = document.getElementById('dateFilter');
    const statusFilter = document.getElementById('statusFilter');
    
    if (!orderSelect) return;
    
    const orders = formContainer._originalOrders;
    const selectedMR = mrFilter?.value || '';
    const selectedDate = dateFilter?.value || '';
    const selectedStatus = statusFilter?.value || '';
    
    // Filter orders by MR name, date, and status
    let filteredOrders = orders;
    if (selectedMR) {
        filteredOrders = filteredOrders.filter(order => order.mr_name === selectedMR);
    }
    if (selectedDate) {
        filteredOrders = filteredOrders.filter(order => order.order_date === selectedDate);
    }
    if (selectedStatus) {
        filteredOrders = filteredOrders.filter(order => order.status === selectedStatus);
    }
    
    // Update order dropdown options
    const currentValue = orderSelect.value;
    orderSelect.innerHTML = '<option value="">-- Select Order --</option>' + 
        filteredOrders.map(order => `
            <option value="${order.order_id}" 
                data-status="${order.status}"
                data-total="${order.total_amount}"
                data-date="${order.order_date}"
                data-mr="${order.mr_name || ''}">
                ${order.order_id} - ${order.mr_name || 'N/A'} - ${order.status_display} - $${order.total_amount ? order.total_amount.toLocaleString() : '0'} - ${order.order_datetime || order.order_date}
            </option>
        `).join('');
    
    // Restore selection if still valid
    if (currentValue && filteredOrders.some(o => o.order_id === currentValue)) {
        orderSelect.value = currentValue;
    }
}

// Filter orders by date and status (for MRs)
function filterOrdersByDateAndStatus() {
    const formContainer = document.querySelector('.order-selection-container');
    if (!formContainer || !formContainer._originalOrders) return;
    
    const orderSelect = document.getElementById('orderSelect');
    const dateFilter = document.getElementById('dateFilter');
    const statusFilter = document.getElementById('statusFilter');
    
    if (!orderSelect || !dateFilter || !statusFilter) return;
    
    const orders = formContainer._originalOrders;
    const selectedDate = dateFilter.value;
    const selectedStatus = statusFilter.value;
    
    // Filter orders by date and status
    let filteredOrders = orders;
    if (selectedDate) {
        filteredOrders = filteredOrders.filter(order => order.order_date === selectedDate);
    }
    if (selectedStatus) {
        filteredOrders = filteredOrders.filter(order => (order.status || order.status_raw) === selectedStatus);
    }
    
    // Clear and repopulate the select
    orderSelect.innerHTML = '<option value="">-- Select Order --</option>';
    filteredOrders.forEach(order => {
        const option = document.createElement('option');
        option.value = order.order_id;
        option.setAttribute('data-status', order.status_raw);
        option.setAttribute('data-total', order.total_amount);
        option.setAttribute('data-date', order.order_date);
        option.textContent = order.order_id; // Show only Order ID
        orderSelect.appendChild(option);
    });
    
    // Reset selection
    orderSelect.value = '';
}

// Make function globally accessible
window.filterOrdersByDateAndStatus = filterOrdersByDateAndStatus;

// Handle order selection
async function handleOrderSelection(event) {
    event.preventDefault();
    
    const form = event.target;
    const formData = new FormData(form);
    const orderId = formData.get('order_id');
    
    if (!orderId) {
        alert('Please select an order.');
        return;
    }
    
    // Disable form during submission
    form.querySelectorAll('button, select').forEach(el => {
        el.disabled = true;
    });
    
    // Show loading state
    const submitBtn = form.querySelector('button[type="submit"]');
    const originalText = submitBtn.innerHTML;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading...';
    
    try {
        // Check if this is distributor view (has mrFilter)
        const mrFilter = document.getElementById('mrFilter');
        const isDistributorView = mrFilter !== null;
        
        if (isDistributorView) {
            // For distributors, call API to get order details
            const response = await fetch('/enhanced-chat/select_order', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ order_id: orderId })
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to fetch order details');
            }
            
            const data = await response.json();
            
            if (data.success && data.order) {
                // Remove the order selection form
                const orderSelectionForm = form.closest('.order-selection-container');
                if (orderSelectionForm) {
                    orderSelectionForm.style.opacity = '0';
                    orderSelectionForm.style.transition = 'opacity 0.3s ease-out';
                    setTimeout(() => {
                        orderSelectionForm.remove();
                    }, 300);
                }
                
                // Display order details with confirm/reject buttons
                displayDistributorOrderDetails(data.order);
            }
        } else {
            // For MRs, send message to track the order
            const orderSelectionForm = form.closest('.order-selection-container');
            if (orderSelectionForm) {
                orderSelectionForm.style.opacity = '0';
                orderSelectionForm.style.transition = 'opacity 0.3s ease-out';
                setTimeout(() => {
                    orderSelectionForm.remove();
                }, 300);
            }
            
            await sendMessage(`track order ${orderId}`);
        }
    } catch (error) {
        console.error('Error selecting order:', error);
        alert('Error selecting order. Please try again.');
        
        // Re-enable form
        form.querySelectorAll('button, select').forEach(el => {
            el.disabled = false;
        });
        submitBtn.innerHTML = originalText;
    }
}

// Make functions globally accessible
window.handleOrderSelection = handleOrderSelection;
window.filterOrdersByAll = filterOrdersByAll;

// Display distributor order details with confirm/reject buttons
function displayDistributorOrderDetails(order) {
    // Build detailed order message
    let message = `**📦 Order Details - ${order.order_id}**\n\n`;
    message += `**MR:** ${order.mr_name} | **Area:** ${order.area}\n`;
    message += `**Contact:** ${order.mr_email} | ${order.mr_phone}\n`;
    message += `**Status:** ${order.status_display} | **Date:** ${order.order_datetime}\n\n`;
    message += `**Items Ordered:**\n`;
    
    order.items.forEach(item => {
        if (item.free_quantity > 0) {
            message += `• ${item.product_name} (${item.product_code}): **${item.total_quantity} units** (${item.quantity} paid + ${item.free_quantity} free) @ $${item.unit_price.toLocaleString()} = $${item.total_price.toLocaleString()}\n`;
        } else {
            message += `• ${item.product_name} (${item.product_code}): ${item.quantity} units @ $${item.unit_price.toLocaleString()} = $${item.total_price.toLocaleString()}\n`;
        }
    });
    
    message += `\n**💰 Total:** $${order.total_amount.toLocaleString()} | **Items:** ${order.total_items} units\n`;
    
    // Add message
    addMessage(message, 'bot');
    
    // Add confirm/reject buttons if order can be confirmed
    if (order.can_confirm) {
        const actionButtons = [
            {
                text: '✅ Confirm Order',
                action: 'confirm_order',
                style: 'success',
                order_id: order.order_id
            },
            {
                text: '❌ Reject Order',
                action: 'reject_order',
                style: 'danger',
                order_id: order.order_id
            },
            {
                text: 'View All Orders',
                action: 'track_order'
            }
        ];
        showActionButtons(actionButtons);
    } else {
        const actionButtons = [
            {
                text: 'View All Orders',
                action: 'track_order'
            },
            {
                text: 'Back to Home',
                action: 'home'
            }
        ];
        showActionButtons(actionButtons);
    }
}

// Confirm order by distributor
async function confirmOrderAction(orderId) {
    if (!confirm(`Are you sure you want to confirm order ${orderId}?`)) {
        return;
    }
    
    try {
        const response = await fetch('/enhanced-chat/confirm_order_action', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ order_id: orderId })
        });
        
        const data = await response.json();
        
        if (data.success) {
            addMessage(`✅ **Order Confirmed Successfully!**\n\n${data.message}\n\nThe stock has been moved from blocked to sold, and the MR has been notified via email.`, 'bot');
            showActionButtons([
                { text: 'View All Orders', action: 'track_order' },
                { text: 'Back to Home', action: 'home' }
            ]);
        } else {
            addMessage(`❌ Error: ${data.message}`, 'bot', 'error');
        }
    } catch (error) {
        console.error('Error confirming order:', error);
        addMessage(`❌ Error confirming order. Please try again.`, 'bot', 'error');
    }
}

// Reject order by distributor
async function rejectOrderAction(orderId) {
    const reason = prompt(`Please provide a reason for rejecting order ${orderId}:`, 'Stock unavailable');
    
    if (reason === null) {
        return; // User canceled
    }
    
    try {
        const response = await fetch('/enhanced-chat/reject_order_action', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                order_id: orderId,
                reason: reason || 'No reason provided'
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            addMessage(`❌ **Order Rejected**\n\n${data.message}\n\nThe stock has been unblocked and returned to available inventory. The MR has been notified via email.`, 'bot');
            showActionButtons([
                { text: 'View All Orders', action: 'track_order' },
                { text: 'Back to Home', action: 'home' }
            ]);
        } else {
            addMessage(`❌ Error: ${data.message}`, 'bot', 'error');
        }
    } catch (error) {
        console.error('Error rejecting order:', error);
        addMessage(`❌ Error rejecting order. Please try again.`, 'bot', 'error');
    }
}

// Make functions globally accessible
window.confirmOrderAction = confirmOrderAction;
window.rejectOrderAction = rejectOrderAction;

// Handle change customer button click
function handleChangeCustomer() {
    // Remove the product selection form first
    const productSelectionForm = document.getElementById('productSelectionForm');
    if (productSelectionForm) {
        productSelectionForm.style.opacity = '0';
        productSelectionForm.style.transition = 'opacity 0.3s ease-out';
        setTimeout(() => {
            productSelectionForm.remove();
        }, 300);
    }
    
    // Send message to trigger customer selection
    sendMessage('Change customer');
}

// Add new customer form
function addNewCustomerForm() {
    const messagesDiv = document.getElementById('chatMessages');
    
    // Find the last bot message
    const botMessages = messagesDiv.querySelectorAll('.message.bot');
    let lastBotMessage = null;
    
    if (botMessages.length > 0) {
        lastBotMessage = botMessages[botMessages.length - 1];
    }
    
    if (!lastBotMessage) return; // Exit if no bot message found
    
    // Find the inner message bubble div (the one with bg-light class)
    const messageBubble = lastBotMessage.querySelector('.message-bubble .bg-light');
    if (!messageBubble) return; // Exit if bubble not found
    
    const formContainer = document.createElement('div');
    formContainer.className = 'add-customer-container mt-3';
    formContainer.style.cssText = 'animation: slideInFromBottom 0.3s ease-out; width: 100%; max-width: 100%;';
    
    const formCard = document.createElement('div');
    formCard.className = 'card border-0 shadow-sm';
    formCard.style.cssText = `
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(20px);
        border-radius: 16px;
        padding: 20px;
        width: 100%;
        box-sizing: border-box;
    `;
    
    formCard.innerHTML = `
        <h6 class="mb-3" style="color: #2563eb; font-weight: 600;">
            <i class="fas fa-user-plus me-2"></i>Add New Customer
        </h6>
        <form id="addCustomerForm" onsubmit="handleAddNewCustomer(event)">
            <div class="mb-3">
                <label for="customerName" class="form-label" style="font-weight: 500;">Customer Name <span style="color: red;">*</span></label>
                <input type="text" class="form-control form-control-lg" id="customerName" name="name" required 
                    placeholder="Enter customer name"
                    style="border-radius: 10px; border: 2px solid #e5e7eb; padding: 12px; font-size: 0.95rem;">
            </div>
            <div class="mb-3">
                <label for="customerEmail" class="form-label" style="font-weight: 500;">Email</label>
                <input type="email" class="form-control form-control-lg" id="customerEmail" name="email" 
                    placeholder="Enter customer email (optional)"
                    style="border-radius: 10px; border: 2px solid #e5e7eb; padding: 12px; font-size: 0.95rem;">
            </div>
            <div class="mb-3">
                <label for="customerPhone" class="form-label" style="font-weight: 500;">Phone</label>
                <input type="tel" class="form-control form-control-lg" id="customerPhone" name="phone" 
                    placeholder="Enter customer phone (optional)"
                    style="border-radius: 10px; border: 2px solid #e5e7eb; padding: 12px; font-size: 0.95rem;">
            </div>
            <div class="mb-3">
                <label for="customerAddress" class="form-label" style="font-weight: 500;">Address</label>
                <textarea class="form-control form-control-lg" id="customerAddress" name="address" rows="3"
                    placeholder="Enter customer address (optional)"
                    style="border-radius: 10px; border: 2px solid #e5e7eb; padding: 12px; font-size: 0.95rem; resize: vertical;"></textarea>
            </div>
            <div class="d-flex gap-2">
                <button type="submit" class="btn btn-primary" 
                    style="border-radius: 8px; padding: 8px 14px; font-weight: 600; font-size: 0.8rem;">
                    <i class="fas fa-check me-2"></i>Add Customer
                </button>
                <button type="button" class="btn btn-outline-secondary cancel-customer-btn" onclick="this.closest('.add-customer-container').remove()"
                    style="border-radius: 8px; padding: 8px 14px; font-size: 0.8rem; transition: all 0.3s ease;">
                    <i class="fas fa-times me-2"></i>Cancel
                </button>
            </div>
        </form>
    `;
    
    formContainer.appendChild(formCard);
    messageBubble.appendChild(formContainer); // Append to the message bubble instead of messagesDiv
    
    // Scroll to bottom
    messagesDiv.scrollTo({
        top: messagesDiv.scrollHeight,
        behavior: 'smooth'
    });
}

// Select customer from dropdown
function selectCustomerFromDropdown(customerId, customerUniqueId, customerName) {
    const customerSearchInput = document.getElementById('customerSearchInput');
    const selectedCustomerIdInput = document.getElementById('selectedCustomerId');
    const selectedCustomerUniqueIdInput = document.getElementById('selectedCustomerUniqueId');
    const customerDropdown = document.getElementById('customerDropdown');
    
    if (customerSearchInput && selectedCustomerIdInput && selectedCustomerUniqueIdInput) {
        customerSearchInput.value = `${customerName} (${customerUniqueId})`;
        selectedCustomerIdInput.value = customerId;
        selectedCustomerUniqueIdInput.value = customerUniqueId;
        customerDropdown.style.display = 'none';
    }
}

// Handle customer selection
async function handleCustomerSelection(event) {
    event.preventDefault();
    
    const form = event.target;
    const formData = new FormData(form);
    const customerId = formData.get('customer_id');
    
    if (!customerId) {
        alert('Please select a customer.');
        return;
    }
    
    // Disable form during submission
    form.querySelectorAll('button, select').forEach(el => {
        el.disabled = true;
    });
    
    // Show loading state
    const submitBtn = form.querySelector('button[type="submit"]');
    const originalText = submitBtn.innerHTML;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Selecting...';
    
    try {
        const response = await fetch('/enhanced-chat/select_customer', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({ customer_id: parseInt(customerId) })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.success) {
            // Show success message first
            addMessage(`✅ ${data.message}`, 'bot');
            
            // Remove the selection form with fade out animation
            const container = form.closest('.customer-selection-container');
            if (container) {
                container.style.transition = 'opacity 0.3s ease-out, transform 0.3s ease-out';
                container.style.opacity = '0';
                container.style.transform = 'translateY(-10px)';
                setTimeout(() => {
                    if (container.parentNode) {
                        container.remove();
                    }
                }, 300);
            }
            
            // Display the bot response with product selection form directly
            if (data.response) {
                addMessage(data.response, 'bot');
            }
            
            // If products are provided, show the product selection form immediately
            if (data.products && data.interactive_product_selection) {
                // Show product table if requested
                if (data.show_product_table) {
                    showProductTable(data.products);
                }
                
                // Show interactive product selection form
                addProductSelectionForm(data.products);
            }
        } else {
            addMessage(`Error: ${data.error}`, 'bot', 'error');
            // Re-enable form
            form.querySelectorAll('button, select').forEach(el => {
                el.disabled = false;
            });
            submitBtn.innerHTML = originalText;
        }
    } catch (error) {
        console.error('Error selecting customer:', error);
        addMessage('Sorry, I encountered an error selecting the customer. Please try again.', 'bot', 'error');
        // Re-enable form
        form.querySelectorAll('button, select').forEach(el => {
            el.disabled = false;
        });
        submitBtn.innerHTML = originalText;
    }
}

// Enhanced invoice ID filter for stock confirmation
function addInvoiceIdFilter(invoiceIds) {
    const messagesDiv = document.getElementById('chatMessages');
    const filterContainer = document.createElement('div');
    filterContainer.className = 'invoice-filter-container mb-3';
    filterContainer.style.cssText = 'animation: slideInFromBottom 0.3s ease-out;';
    
    const filterCard = document.createElement('div');
    filterCard.className = 'card border-0 shadow-sm';
    filterCard.style.cssText = `
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(20px);
        border-radius: 16px;
        padding: 20px;
    `;
    
    filterCard.innerHTML = `
        <h6 class="mb-3" style="color: #2563eb; font-weight: 600;">
            <i class="fas fa-filter me-2"></i>Filter by Invoice ID
        </h6>
        <div class="d-flex gap-2 flex-wrap">
            <select class="form-select" id="invoiceIdFilter" 
                style="border-radius: 10px; border: 2px solid #e5e7eb; padding: 10px; flex: 1; min-width: 200px;">
                <option value="">-- All Invoices --</option>
                ${invoiceIds.map(id => `
                    <option value="${id}">${id}</option>
                `).join('')}
            </select>
            <button type="button" class="btn btn-primary" onclick="applyInvoiceFilter()"
                style="border-radius: 10px; padding: 10px 20px; font-weight: 600;">
                <i class="fas fa-search me-2"></i>Filter
            </button>
            <button type="button" class="btn btn-outline-secondary" onclick="this.closest('.invoice-filter-container').remove()"
                style="border-radius: 10px; padding: 10px;">
                <i class="fas fa-times"></i>
            </button>
        </div>
    `;
    
    filterContainer.appendChild(filterCard);
    messagesDiv.appendChild(filterContainer);
    
    // Scroll to bottom
    messagesDiv.scrollTo({
        top: messagesDiv.scrollHeight,
        behavior: 'smooth'
    });
}

// Apply invoice filter
function applyInvoiceFilter() {
    const invoiceIdSelect = document.getElementById('invoiceIdFilter');
    if (!invoiceIdSelect) return;
    
    const invoiceId = invoiceIdSelect.value;
    
    if (invoiceId) {
        sendMessage(`show pending stock invoice_id: ${invoiceId}`);
    } else {
        sendMessage('show pending stock');
    }
    
    // Note: Filter is now inside the stock confirmation form, so we don't remove it
    // The form will be refreshed when the new stock data is loaded
}

// Handle add new customer
async function handleAddNewCustomer(event) {
    event.preventDefault();
    
    const form = event.target;
    const formData = new FormData(form);
    const name = formData.get('name').trim();
    const email = formData.get('email')?.trim() || '';
    const phone = formData.get('phone')?.trim() || '';
    const address = formData.get('address')?.trim() || '';
    
    if (!name) {
        alert('Please enter customer name.');
        return;
    }
    
    // Disable form during submission
    form.querySelectorAll('button, input, textarea').forEach(el => {
        el.disabled = true;
    });
    
    // Show loading state
    const submitBtn = form.querySelector('button[type="submit"]');
    const originalText = submitBtn.innerHTML;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Adding...';
    
    try {
        const response = await fetch('/enhanced-chat/add_customer', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({
                name: name,
                email: email,
                phone: phone,
                address: address
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.success) {
            // Show success message first
            addMessage(`✅ ${data.message}`, 'bot');
            
            // Remove the form with fade out animation
            const container = form.closest('.add-customer-container');
            if (container) {
                container.style.transition = 'opacity 0.3s ease-out, transform 0.3s ease-out';
                container.style.opacity = '0';
                container.style.transform = 'translateY(-10px)';
                setTimeout(() => {
                    if (container.parentNode) {
                        container.remove();
                    }
                }, 300);
            }
            
            // Display the bot response with product selection form directly
            if (data.response) {
                addMessage(data.response, 'bot');
            }
            
            // If products are provided, show the product selection form immediately
            if (data.products && data.interactive_product_selection) {
                // Show product table if requested
                if (data.show_product_table) {
                    showProductTable(data.products);
                }
                
                // Show interactive product selection form
                addProductSelectionForm(data.products);
            }
        } else {
            addMessage(`Error: ${data.error}`, 'bot', 'error');
            // Re-enable form
            form.querySelectorAll('button, input, textarea').forEach(el => {
                el.disabled = false;
            });
            submitBtn.innerHTML = originalText;
        }
    } catch (error) {
        console.error('Error adding customer:', error);
        addMessage('Sorry, I encountered an error adding the customer. Please try again.', 'bot', 'error');
        // Re-enable form
        form.querySelectorAll('button, input, textarea').forEach(el => {
            el.disabled = false;
        });
        submitBtn.innerHTML = originalText;
    }
}

// Confirm Cart function - removes product selection form and shows Edit Cart / Place Order options
async function confirmCart() {
    // Remove the product selection form with fade out animation
    const formContainer = document.getElementById('productSelectionForm');
    if (formContainer) {
        formContainer.style.transition = 'opacity 0.3s ease-out, transform 0.3s ease-out';
        formContainer.style.opacity = '0';
        formContainer.style.transform = 'translateY(-10px)';
        setTimeout(() => {
            if (formContainer.parentNode) {
                formContainer.remove();
            }
        }, 300);
    }
    
    // Send message to backend to show Edit Cart / Place Order options
    await sendMessage('Confirm cart');
}

// ============= COMPANY REPORT SYSTEM =============

function showTableSelectionForm(tables) {
    console.log('Showing table selection form with tables:', tables);
    
    const messagesDiv = document.getElementById('chatMessages');
    
    // Remove any existing table selection form
    const existingForm = document.getElementById('tableSelectionForm');
    if (existingForm) {
        existingForm.remove();
    }
    
    // Create form container
    const formContainer = document.createElement('div');
    formContainer.id = 'tableSelectionForm';
    formContainer.className = 'message bot mb-3';
    formContainer.style.opacity = '0';
    formContainer.style.transform = 'translateY(20px)';
    formContainer.style.transition = 'opacity 0.5s ease-out, transform 0.5s ease-out';
    
    let formHTML = `
        <div class="message-bubble" style="width: 85% !important; max-width: none !important;">
            <div class="bg-light rounded-3 px-4 py-3 shadow-sm" style="border: 2px solid #3b82f6;">
                <h5 class="text-primary mb-3">
                    <i class="fas fa-table me-2"></i>Select Database Table
                </h5>
                
                <div class="table-selection-grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 15px; margin-bottom: 20px;">
    `;
    
    tables.forEach(table => {
        formHTML += `
            <div class="table-card" onclick="selectCompanyTable('${table.key}')" style="cursor: pointer; padding: 15px; background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%); border: 2px solid #3b82f6; border-radius: 8px; transition: all 0.3s ease;">
                <div style="font-weight: 600; color: #1e40af; margin-bottom: 5px;">
                    <i class="fas fa-database me-2"></i>${table.name}
                </div>
                <div style="font-size: 0.85rem; color: #64748b;">
                    ${table.columns.length} columns available
                </div>
            </div>
        `;
    });
    
    formHTML += `
                </div>
                
                <button type="button" class="btn btn-secondary btn-sm" onclick="cancelReportGeneration()">
                    <i class="fas fa-times me-2"></i>Cancel
                </button>
            </div>
        </div>
    `;
    
    formContainer.innerHTML = formHTML;
    messagesDiv.appendChild(formContainer);
    
    // Trigger animation
    setTimeout(() => {
        formContainer.style.opacity = '1';
        formContainer.style.transform = 'translateY(0)';
    }, 10);
    
    // Add hover effect CSS
    const style = document.createElement('style');
    style.textContent = `
        .table-card:hover {
            transform: translateY(-3px);
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3) !important;
            border-color: #2563eb !important;
            background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%) !important;
        }
    `;
    document.head.appendChild(style);
    
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function showColumnSelectionForm(tableKey, tableName, columns) {
    console.log('Showing column selection form:', tableKey, tableName, columns);
    
    const messagesDiv = document.getElementById('chatMessages');
    
    // Remove any existing forms
    const existingForm = document.getElementById('columnSelectionForm');
    if (existingForm) {
        existingForm.remove();
    }
    
    // Create form container
    const formContainer = document.createElement('div');
    formContainer.id = 'columnSelectionForm';
    formContainer.className = 'message bot mb-3';
    formContainer.style.opacity = '0';
    formContainer.style.transform = 'translateY(20px)';
    formContainer.style.transition = 'opacity 0.5s ease-out, transform 0.5s ease-out';
    
    let formHTML = `
        <div class="message-bubble" style="width: 85% !important; max-width: none !important;">
            <div class="bg-light rounded-3 px-4 py-3 shadow-sm" style="border: 2px solid #3b82f6;">
                <h5 class="text-primary mb-3">
                    <i class="fas fa-columns me-2"></i>Select Columns for ${tableName}
                </h5>
                
                <div class="mb-3">
                    <button type="button" class="btn btn-sm btn-outline-primary me-2" onclick="selectAllColumns()">
                        <i class="fas fa-check-double me-1"></i>Select All
                    </button>
                    <button type="button" class="btn btn-sm btn-outline-secondary" onclick="deselectAllColumns()">
                        <i class="fas fa-times me-1"></i>Deselect All
                    </button>
                </div>
                
                <div class="column-selection-grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; margin-bottom: 20px; max-height: 400px; overflow-y: auto; padding: 10px; background: white; border-radius: 8px;">
    `;
    
    columns.forEach(col => {
        formHTML += `
            <div class="form-check">
                <input class="form-check-input column-checkbox" type="checkbox" value="${col}" id="col_${col}" checked>
                <label class="form-check-label" for="col_${col}" style="font-size: 0.9rem; color: #1f2937;">
                    <code style="color: #2563eb; background: #eff6ff; padding: 2px 6px; border-radius: 4px;">${col}</code>
                </label>
            </div>
        `;
    });
    
    formHTML += `
                </div>
                
                <div style="background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%); border-radius: 10px; border: 2px dashed #3b82f6; padding: 12px; text-align: center; margin-bottom: 15px;">
                    <i class="fas fa-info-circle me-2" style="color: #2563eb;"></i>
                    <span style="color: #1e40af; font-weight: 600; font-size: 0.9rem;">
                        <span id="selectedColumnsCount">${columns.length}</span> columns selected
                    </span>
                </div>
                
                <div class="d-flex gap-2">
                    <button type="button" class="btn btn-primary" onclick="generateReport('${tableKey}')">
                        <i class="fas fa-file-export me-2"></i>Generate Report
                    </button>
                    <button type="button" class="btn btn-secondary" onclick="cancelReportGeneration()">
                        <i class="fas fa-times me-2"></i>Cancel
                    </button>
                </div>
            </div>
        </div>
    `;
    
    formContainer.innerHTML = formHTML;
    messagesDiv.appendChild(formContainer);
    
    // Trigger animation
    setTimeout(() => {
        formContainer.style.opacity = '1';
        formContainer.style.transform = 'translateY(0)';
    }, 10);
    
    // Add event listeners to update count
    document.querySelectorAll('.column-checkbox').forEach(checkbox => {
        checkbox.addEventListener('change', updateSelectedColumnsCount);
    });
    
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function updateSelectedColumnsCount() {
    const checkboxes = document.querySelectorAll('.column-checkbox');
    const checked = Array.from(checkboxes).filter(cb => cb.checked).length;
    const countSpan = document.getElementById('selectedColumnsCount');
    if (countSpan) {
        countSpan.textContent = checked;
    }
}

function selectAllColumns() {
    document.querySelectorAll('.column-checkbox').forEach(checkbox => {
        checkbox.checked = true;
    });
    updateSelectedColumnsCount();
}

function deselectAllColumns() {
    document.querySelectorAll('.column-checkbox').forEach(checkbox => {
        checkbox.checked = false;
    });
    updateSelectedColumnsCount();
}

async function selectCompanyTable(tableKey) {
    console.log('Selected table:', tableKey);
    
    try {
        const response = await fetch('/enhanced-chat/company/select_table', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ table_key: tableKey })
        });
        
        const data = await response.json();
        
        if (data.error) {
            console.error('Error selecting table:', data.error);
            addMessage(`Error: ${data.error}`, 'bot');
            return;
        }
        
        // Remove table selection form
        const formContainer = document.getElementById('tableSelectionForm');
        if (formContainer) {
            formContainer.remove();
        }
        
        // Show response and column selection
        if (data.response) {
            addMessage(data.response, 'bot');
        }
        
        if (data.show_column_selection && data.columns) {
            showColumnSelectionForm(data.table_key, data.table_name, data.columns);
        }
        
    } catch (error) {
        console.error('Error selecting table:', error);
        addMessage('Sorry, there was an error selecting the table. Please try again.', 'bot');
    }
}

async function generateReport(tableKey) {
    console.log('Generating report for table:', tableKey);
    
    // Get selected columns
    const checkboxes = document.querySelectorAll('.column-checkbox:checked');
    const selectedColumns = Array.from(checkboxes).map(cb => cb.value);
    
    if (selectedColumns.length === 0) {
        addMessage('❌ Please select at least one column to export.', 'bot');
        return;
    }
    
    // Show loading message
    addMessage('⏳ Generating report... This may take a moment.', 'bot');
    
    try {
        const response = await fetch('/enhanced-chat/company/generate_report', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                table_key: tableKey,
                selected_columns: selectedColumns
            })
        });
        
        const data = await response.json();
        
        // Remove column selection form
        const formContainer = document.getElementById('columnSelectionForm');
        if (formContainer) {
            formContainer.remove();
        }
        
        if (data.error) {
            addMessage(`❌ Error: ${data.error}`, 'bot');
        } else if (data.response) {
            addMessage(data.response, 'bot');
        }
        
        // Show action buttons if provided
        if (data.action_buttons && data.action_buttons.length > 0) {
            showActionButtons(data.action_buttons);
        }
        
    } catch (error) {
        console.error('Error generating report:', error);
        addMessage('❌ Sorry, there was an error generating the report. Please try again.', 'bot');
    }
}

function cancelReportGeneration() {
    // Remove any report forms
    const tableForm = document.getElementById('tableSelectionForm');
    const columnForm = document.getElementById('columnSelectionForm');
    
    if (tableForm) {
        tableForm.style.transition = 'opacity 0.3s ease-out';
        tableForm.style.opacity = '0';
        setTimeout(() => tableForm.remove(), 300);
    }
    
    if (columnForm) {
        columnForm.style.transition = 'opacity 0.3s ease-out';
        columnForm.style.opacity = '0';
        setTimeout(() => columnForm.remove(), 300);
    }
    
    addMessage('Report generation cancelled.', 'bot');
    
    // Show default action buttons
    showActionButtons([
        {'text': 'Generate Report', 'action': 'generate_report'},
        {'text': 'Help', 'action': 'help'}
    ]);
}

// Make functions globally accessible for onclick handlers
window.sendMessage = sendMessage;
window.handleAction = handleAction;
window.handleCustomerSelection = handleCustomerSelection;
window.handleAddNewCustomer = handleAddNewCustomer;
window.handleChangeCustomer = handleChangeCustomer;
window.viewCart = viewCart;
window.confirmCart = confirmCart;
window.updateCartQuantity = updateCartQuantity;
window.updateCartQuantityDirect = updateCartQuantityDirect;
window.removeFromCart = removeFromCart;
// Company report functions
window.selectCompanyTable = selectCompanyTable;
window.generateReport = generateReport;
window.selectAllColumns = selectAllColumns;
window.deselectAllColumns = deselectAllColumns;
window.cancelReportGeneration = cancelReportGeneration;
window.applyInvoiceFilter = applyInvoiceFilter;
