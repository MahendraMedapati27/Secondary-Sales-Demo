let isProcessing = false;
let messageHistory = [];
let typingTimeout = null;
let currentUser = null;
let cartItems = [];
let currentOrderSummary = null;
let productRecommendations = [];
let recommendationTimeout = null;

// Initialize chat
document.addEventListener('DOMContentLoaded', function() {
    initializeChat();
});

// Voice functionality disabled

// Initialize language on page load
function initializeLanguage() {
    // Wait for i18n to be loaded
    if (typeof i18n !== 'undefined') {
        const savedLang = localStorage.getItem('preferredLanguage') || 'en';
        document.getElementById('languageSelector').value = savedLang;
        i18n.changeLanguage(savedLang).then(() => {
            if (typeof updateAllUITexts === 'function') {
                updateAllUITexts();
            }
        });
    } else {
        // Retry after a short delay
        setTimeout(initializeLanguage, 100);
    }
}

function initializeChat() {
    // Initialize language first
    initializeLanguage();
    // Set up event listeners
    const messageInput = document.getElementById('messageInput');
    const sendButton = document.getElementById('sendButton');
    
    // Ensure sendMessage is globally available
    window.sendMessage = sendMessage;
    
    // Add click event listener to send button
    if (sendButton) {
        sendButton.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            console.log('Send button clicked, isProcessing:', isProcessing, 'message:', messageInput.value.trim());
            if (!isProcessing && messageInput && messageInput.value.trim()) {
                sendMessage();
            } else {
                console.log('Cannot send: isProcessing =', isProcessing, 'message =', messageInput ? messageInput.value.trim() : 'no input');
            }
        });
    } else {
        console.error('Send button not found!');
    }
    
    // Also ensure onclick works as fallback
    if (sendButton && !sendButton.onclick) {
        sendButton.onclick = function(e) {
            e.preventDefault();
            e.stopPropagation();
            if (!isProcessing && messageInput && messageInput.value.trim()) {
                sendMessage();
            }
        };
    }
    
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
        
        // Show recent searches when input is focused and empty
        if (message.length === 0 && document.activeElement === messageInput) {
            showRecentSearches(messageInput);
        } else {
            closeRecentSearches();
        }
    });
    
    // Show recent searches on focus
    messageInput.addEventListener('focus', function() {
        if (this.value.trim().length === 0 && recentSearches.length > 0) {
            showRecentSearches(this);
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
    
    // Setup keyboard navigation
    setupKeyboardNavigation();
    
    // Update quick stats
    if (currentUser) {
        updateQuickStats();
        setInterval(updateQuickStats, 60000); // Update every minute
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
                    </div>
                    <small class="text-primary">${(product.price_of_product || 0).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})} MMK</small>
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
    if (currentValue.length < 3 || currentValue.toLowerCase().includes(productName.toLowerCase())) {
        input.value = `Order ${productName}`;
    } else {
        input.value = `${currentValue}, ${productName}`;
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
    if (isProcessing) {
        console.log('Message sending already in progress');
        return;
    }
    
    const input = document.getElementById('messageInput');
    if (!input) {
        console.error('Message input not found');
        return;
    }
    
    // Use provided message or get from input field
    const message = messageText !== null ? messageText.trim() : input.value.trim();
    
    if (!message) {
        console.log('No message to send');
        return;
    }
    
    console.log('Sending message:', message);
    
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
    
    // Add to recent searches if it's a search-like query
    if (message.length > 2 && !message.startsWith('I want') && !message.startsWith('Show') && !message.startsWith('Track')) {
        addToRecentSearches(message);
    }
    
    // Jump animation removed - avatar stays in natural standing pose
    
    // Show typing indicator
    showTypingIndicator();
    
    // Show loading state (but make it less intrusive - just show typing indicator)
    let loadingOverlay = null;
    // Don't block the entire messages div - just use typing indicator which is already shown
    
    try {
        // Get current language preference
        const languageSelector = document.getElementById('languageSelector');
        const currentLanguage = languageSelector ? languageSelector.value : (localStorage.getItem('preferredLanguage') || 'en');
        
        const response = await fetch('/enhanced-chat/message', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({ 
                message: message,
                language: currentLanguage  // Send language preference for real-time translation
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Hide loading immediately after response
        if (loadingOverlay) {
            hideLoading(loadingOverlay);
            loadingOverlay = null;
        }
        
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
                // Add a small delay to ensure message is fully rendered before adding form
                setTimeout(() => {
                    addOrderSelectionForm(data.orders, data.filters || null);
                }, 200);
            }
            
            // Handle product search interface
            if (data.interactive_product_search && data.products) {
                setTimeout(() => {
                    showProductSearchInterface(data.products);
                }, 200);
            }
            
            // Handle action buttons (skip if add customer form is shown, product selection is shown, customer selection is shown, order selection is shown, or report selection is shown)
            // For animated order details, delay showing action buttons until animation completes
            // Show action buttons if they exist and are not empty, and no interactive UI is active
            if (data.action_buttons && Array.isArray(data.action_buttons) && data.action_buttons.length > 0 && !data.interactive_add_customer && !data.interactive_product_selection && !data.interactive_customer_selection && !data.interactive_order_selection && !data.interactive_stock_confirmation && !data.interactive_report_selection && !data.show_column_selection && !data.interactive_product_search) {
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
        console.error('Error sending message:', error);
        if (loadingOverlay) {
            hideLoading(loadingOverlay);
        }
        const errorMsg = 'Sorry, I encountered an error. Please try again.';
        addMessage(errorMsg, 'bot', 'error');
        
        // Don't make avatar speak for errors
    } finally {
        hideTypingIndicator();
        isProcessing = false;
        toggleUI(true);
    }
}

// Clean text for TTS (remove markdown, tables, special characters)
function cleanTextForTTS(text) {
    if (!text) return '';
    
    // Remove markdown headers
    text = text.replace(/^#{1,6}\s+/gm, '');
    
    // Remove markdown bold/italic
    text = text.replace(/\*\*(.*?)\*\*/g, '$1');
    text = text.replace(/\*(.*?)\*/g, '$1');
    text = text.replace(/__(.*?)__/g, '$1');
    text = text.replace(/_(.*?)_/g, '$1');
    
    // Remove markdown links
    text = text.replace(/\[([^\]]+)\]\([^\)]+\)/g, '$1');
    
    // Remove markdown code blocks
    text = text.replace(/```[\s\S]*?```/g, '');
    text = text.replace(/`([^`]+)`/g, '$1');
    
    // Remove markdown tables (lines with |)
    const lines = text.split('\n');
    const cleanedLines = lines.filter(line => {
        const trimmed = line.trim();
        // Skip table rows (lines with multiple |)
        if (trimmed.includes('|') && trimmed.split('|').length > 2) {
            return false;
        }
        // Skip table separators
        if (trimmed.match(/^[\s\|\-:]+$/)) {
            return false;
        }
        return true;
    });
    text = cleanedLines.join('\n');
    
    // Remove extra whitespace
    text = text.replace(/\n{3,}/g, '\n\n');
    text = text.replace(/[ \t]+/g, ' ');
    text = text.trim();
    
    // Limit length (TTS has character limits)
    if (text.length > 4000) {
        text = text.substring(0, 4000) + '...';
    }
    
    return text;
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
                <div class="bg-primary text-white rounded-3 px-3 py-2" style="max-width: 100%; width: 100%; font-size: 0.875rem; word-break: normal !important; overflow-wrap: anywhere !important; white-space: normal !important; overflow: hidden;">
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
                <div class="bg-light border rounded-3 px-3 py-2${tableClass}" style="max-width: 100%; font-size: 0.875rem; width: 100%;">
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
    if (sender === 'bot' && type !== 'error') {
        // Get current language for TTS
        const languageSelector = document.getElementById('languageSelector');
        const currentLanguage = languageSelector ? languageSelector.value : (localStorage.getItem('preferredLanguage') || 'en');
        
        // Clean message text for TTS (remove markdown, tables, etc.)
        const cleanText = cleanTextForTTS(message);
        
        // Voice/Speech feature DISABLED
        // TTS calls disabled - no voice output
        // if (typeof speakText === 'function' && cleanText) {
        //     // Small delay to ensure message is displayed first
        //     setTimeout(() => {
        //         console.log('[CHAT] 🎤 Triggering TTS for bot response');
        //         speakText(cleanText, currentLanguage);
        //     }, 300);
        // } else if (typeof avatarSpeak === 'function') {
        //     // Fallback to avatar animation only
        //     setTimeout(() => {
        //         const wordCount = message.split(/\s+/).length;
        //         const estimatedDuration = Math.max(1000, Math.min(10000, (wordCount / 2.5) * 1000));
        //         avatarSpeak(estimatedDuration);
        //     }, 100);
        // }
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
                <div class="bg-light border rounded-3 px-3 py-2${tableClass}" style="max-width: 100%; font-size: 0.875rem; width: 100%;">
                </div>
            </div>
        `;
        
        const innerDiv = bubbleDiv.querySelector('.bg-light');
        innerDiv.appendChild(container);
    } else {
        bubbleDiv.innerHTML = `
            <div class="d-flex justify-content-end align-items-center" style="width: 100%; gap: 8px;">
                <div class="bg-primary text-white rounded-3 px-3 py-2" style="max-width: 100%; width: 100%; font-size: 0.875rem; word-break: normal !important; overflow-wrap: anywhere !important; white-space: normal !important; overflow: hidden;">
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
    const input = document.getElementById('messageInput');
    const button = document.getElementById('sendButton');
    
    if (input) {
        input.disabled = !enabled;
    }
    
    if (button) {
        // Only disable button if UI is disabled OR input is empty
        const inputValue = input ? input.value.trim() : '';
        button.disabled = !enabled || !inputValue;
    }
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
    document.getElementById('userArea').textContent = userInfo.warehouse || userInfo.area || '-';
    document.getElementById('userInfoPanel').style.display = 'block';
    
    // Update toggle icon and button to show up arrow when panel is visible
    const icon = document.getElementById('userInfoToggleIcon');
    const btn = document.getElementById('userInfoToggleBtn');
    if (icon) {
        icon.classList.remove('fa-chevron-down');
        icon.classList.add('fa-chevron-up');
    }
    if (btn) {
        btn.classList.add('active');
    }
    
    // Show cart button for logged in users
    document.getElementById('cartButton').style.display = 'inline-block';
}

// Enhanced action buttons with better UX
function showActionButtons(buttons) {
    const messagesDiv = document.getElementById('chatMessages');
    
    // Remove any existing action buttons to prevent duplicates
    const existingButtons = messagesDiv.querySelectorAll('.action-buttons-container');
    existingButtons.forEach(btn => btn.remove());
    
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
    // Also check for product details container
    let messageBubble = lastBotMessage.querySelector('.message-bubble .bg-light');
    if (!messageBubble) {
        // Try to find product details container
        messageBubble = lastBotMessage.querySelector('.product-details');
        if (!messageBubble) {
            // Try to find any content div in the message bubble
            messageBubble = lastBotMessage.querySelector('.message-bubble > div > div');
        }
    }
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
        'open_order': 'fas fa-folder-open',
        'company_info': 'fas fa-building',
        'product_info': 'fas fa-info-circle',
        'pending_stocks': 'fas fa-clipboard-check',
        'print_order': 'fas fa-print',
        'export_excel': 'fas fa-file-excel',
        'bulk_action': 'fas fa-tasks'
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
        
        // Translate button text if translation function is available
        let buttonText = button.text;
        if (typeof t !== 'undefined' && button.action) {
            // Try to get translation for the action
            const translationKey = `buttons.${button.action}`;
            const translated = t(translationKey);
            // Only use translation if it's different from the key (meaning translation exists)
            if (translated && translated !== translationKey) {
                buttonText = translated;
            }
        }
        
        btn.innerHTML = `<i class="${iconClass}"></i> <span>${buttonText}</span>`;
        btn.setAttribute('data-action', button.action);
        
        // Store order_id if provided
        if (button.order_id) {
            btn.setAttribute('data-order-id', button.order_id);
        }
        
        // Store template_id if provided
        if (button.template_id) {
            btn.setAttribute('data-template-id', button.template_id);
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
            
            // Prevent double-clicks
            if (btn.disabled) {
                return;
            }
            btn.disabled = true;
            setTimeout(() => {
                btn.disabled = false;
            }, 1000);
            
            // If custom onclick is provided, execute it and return
            if (button.onclick) {
                try {
                    eval(button.onclick);
                } catch (err) {
                    console.error('Error executing custom onclick:', err);
                }
                return;
            }
            
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
            
            // Get order_id and template_id if available
            const orderId = this.getAttribute('data-order-id');
            const templateId = this.getAttribute('data-template-id');
            
            // Call handleAction with order_id and template_id if available
            if (typeof handleAction === 'function') {
                handleAction(button.action, orderId, templateId);
            } else {
                // Fallback: send message directly (use translations)
                const t_func = (typeof t !== 'undefined') ? t : (key) => key;
                const actionMessages = {
                    'place_order': t_func('messages.placeOrder'),
                    'track_order': t_func('messages.trackOrder'),
                    'company_info': t_func('messages.companyInfo'),
                    'product_info': t_func('buttons.productInfo'),
                    'print_order': null // Handled by onclick
                };
                const message = actionMessages[button.action] || button.text;
                if (message) {
                sendMessage(message);
                }
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

function handleAction(action, orderId = null, templateId = null) {
    // Remove loading state from all buttons first
    document.querySelectorAll('.action-btn').forEach(btn => {
        btn.classList.remove('loading');
    });
    
    // Get translation function
    const t_func = (typeof t !== 'undefined') ? t : (key) => key;
    
    switch (action) {
        case 'place_order':
            sendMessage(t_func('messages.placeOrder'));
            break;
        case 'track_order':
            sendMessage(t_func('messages.trackOrder'));
            break;
        case 'open_order':
            // View Open Order button - same functionality as track order
            sendMessage(t_func('messages.trackOrder'));
            break;
        case 'product_info':
            // Send message to backend to get proper response with action buttons
            sendMessage(t_func('buttons.productInfo'));
            break;
        case 'view_cart':
            if (typeof viewCart === 'function') {
                viewCart();
            } else {
                sendMessage(t_func('messages.showCart'));
            }
            break;
        case 'add_items':
            sendMessage(t_func('messages.addMoreItems'));
            break;
        case 'company_info':
            sendMessage(t_func('messages.companyInfo'));
            break;
        case 'help':
            sendMessage(t_func('messages.needHelp'));
            break;
        case 'change_customer':
            sendMessage(t_func('messages.changeCustomer'));
            break;
        case 'select_customer':
            sendMessage(t_func('messages.selectCustomer'));
            break;
        case 'add_new_customer':
            sendMessage(t_func('messages.addNewCustomer'));
            break;
        case 'confirm_order':
            // Check if this is distributor confirming an order (has orderId)
            if (orderId) {
                confirmOrderAction(orderId);
            } else if (typeof placeOrder === 'function') {
                placeOrder();
            } else {
                sendMessage(t_func('messages.confirmOrder'));
            }
            break;
        case 'reject_order':
            // Distributor rejecting an order
            if (orderId) {
                rejectOrderAction(orderId);
            }
            break;
        case 'cancel_order':
            // MR canceling their own order
            if (orderId) {
                cancelOrderAction(orderId);
            }
            break;
        case 'home':
            sendMessage('Hi');
            break;
        case 'view_stock':
            sendMessage(t_func('messages.showStock'));
            break;
        case 'edit_cart':
            sendMessage(t_func('messages.editCart'));
            break;
        case 'place_order_final':
            sendMessage(t_func('messages.placeOrderFinal'));
            break;
        case 'pending_stocks':
            sendMessage(t_func('messages.showPendingStock'));
            break;
        case 'generate_report':
            sendMessage(t_func('messages.generateReport'));
            break;
        case 'cancel':
            // Show action buttons when cancel is clicked
            showActionButtons([
                {'text': (typeof t !== 'undefined') ? t('buttons.placeOrder') : 'Place Order', 'action': 'place_order'},
                {'text': (typeof t !== 'undefined') ? t('buttons.viewOrder') : 'View Open Order', 'action': 'open_order'},
                {'text': (typeof t !== 'undefined') ? t('buttons.productInfo') : 'Product Info', 'action': 'product_info'},
                {'text': (typeof t !== 'undefined') ? t('buttons.companyInfo') : 'Company Info', 'action': 'company_info'}
            ]);
            break;
        case 'load_template':
            if (templateId) {
                loadOrderTemplate(templateId);
            } else {
                // If no templateId, show template selection
                showOrderTemplates();
            }
            break;
        case 'manage_templates':
            showOrderTemplates();
            break;
        case 'delete_template':
            // Show delete template interface
            showDeleteTemplateInterface();
            break;
        case 'cancel':
            // Hide action buttons and show default action buttons
            const actionButtons = document.querySelectorAll('.action-buttons-container');
            actionButtons.forEach(container => {
                container.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
                container.style.opacity = '0';
                container.style.transform = 'translateY(-10px)';
                setTimeout(() => {
                    container.remove();
                }, 300);
            });
            // Show default action buttons
            setTimeout(() => {
            showActionButtons([
                {'text': 'Place Order', 'action': 'place_order'},
                {'text': 'View Open Order', 'action': 'open_order'},
                    {'text': 'Company Info', 'action': 'company_info'},
                    {'text': 'Product Info', 'action': 'product_info'}
                ]);
            }, 350);
            break;
        case 'advanced_search':
            const searchQuery = prompt('Enter search query:');
            if (searchQuery) {
                performAdvancedSearch(searchQuery);
            }
            break;
        case 'delivery_dashboard':
            if (typeof showDeliveryPartnerDashboard === 'function') {
                showDeliveryPartnerDashboard();
            } else {
                sendMessage('Show my delivery orders');
            }
            break;
        case 'track_orders':
            // Alias for delivery dashboard
            if (typeof showDeliveryPartnerDashboard === 'function') {
                showDeliveryPartnerDashboard();
            } else {
                sendMessage('Show my delivery orders');
            }
            break;
        default:
            console.log('Unknown action:', action);
            // Try to send the action as a message
            sendMessage(action);
    }
}

function updateCartDisplay(cartItemsParam) {
    cartItems = cartItemsParam;
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
    
    // Calculate totals if not provided
    if (subtotal === undefined || taxAmount === undefined || grandTotal === undefined) {
        subtotal = 0;
        cartItems.forEach(item => {
            const itemTotal = item.total_price || (item.unit_price || item.final_price || 0) * (item.quantity || item.paid_quantity || 0);
            subtotal += itemTotal || 0;
        });
        taxAmount = subtotal * 0.05; // 5% tax
        grandTotal = subtotal + taxAmount;
    }
    
    // Ensure values are numbers
    subtotal = Number(subtotal) || 0;
    taxAmount = Number(taxAmount) || 0;
    grandTotal = Number(grandTotal) || 0;
    
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
                        <strong>${item.product_name || item.product_code}</strong>
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
                    <td>${unitPrice.toLocaleString('en-US')} MMK</td>
                    <td>${itemTotal.toLocaleString('en-US')} MMK</td>
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
                        <span style="font-size: 1rem; color: #4b5563; font-weight: 600;">${subtotal.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})} MMK</span>
                    </div>
                </div>
                <div class="row mb-3">
                    <div class="col-8 text-end">
                        <strong style="font-size: 1rem; color: #4b5563;">Tax (5%):</strong>
                    </div>
                    <div class="col-4 text-end">
                        <span style="font-size: 1rem; color: #4b5563; font-weight: 600;">${taxAmount.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})} MMK</span>
                    </div>
                </div>
                <div class="row" style="background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%); padding: 15px; border-radius: 10px; margin: 0 -8px;">
                    <div class="col-8 text-end">
                        <strong style="font-size: 1.25rem; color: #1e40af;">Grand Total:</strong>
                    </div>
                    <div class="col-4 text-end">
                        <span style="font-size: 1.35rem; color: #1e40af; font-weight: 700;">${grandTotal.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})} MMK</span>
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
            // Update cart display immediately with response data
            if (updateData.cart_items && updateData.cart_items.length > 0) {
                displayCartModal(updateData.cart_items, updateData.subtotal, updateData.tax_amount, updateData.grand_total);
                updateCartDisplay(updateData.cart_items);
            } else {
                // Cart is empty
                const cartModalElement = document.getElementById('cartModal');
                const cartModal = bootstrap.Modal.getInstance(cartModalElement);
                if (cartModal) {
                    cartModal.hide();
                }
                updateCartDisplay([]);
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
            // Update cart display immediately with response data
            if (updateData.cart_items && updateData.cart_items.length > 0) {
                displayCartModal(updateData.cart_items, updateData.subtotal, updateData.tax_amount, updateData.grand_total);
                updateCartDisplay(updateData.cart_items);
            } else {
                // Cart is empty
                const cartModalElement = document.getElementById('cartModal');
                const cartModal = bootstrap.Modal.getInstance(cartModalElement);
                if (cartModal) {
                    cartModal.hide();
                }
                updateCartDisplay([]);
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
                // Calculate totals if not provided
                let subtotal = data.subtotal;
                let taxAmount = data.tax_amount;
                let grandTotal = data.grand_total;
                
                if (subtotal === undefined) {
                    subtotal = data.cart_items.reduce((sum, item) => sum + (item.total_price || 0), 0);
                    taxAmount = subtotal * 0.05;
                    grandTotal = subtotal + taxAmount;
                }
                
                // Update cart display immediately with response data
                displayCartModal(data.cart_items, subtotal, taxAmount, grandTotal);
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
            // Don't show error message if cart is empty - just reload cart
            if (error.error && !error.error.includes('empty')) {
                addMessage(error.error || 'Error removing item from cart.', 'bot', 'error');
            } else {
                // Reload cart to show updated state
                await viewCart();
            }
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
            // Don't display order ID separately - it's already in the order summary message
            // if (data.order_id) {
            //     addMessage(`Order ID: ${data.order_id}`, 'bot');
            // }
            // Hide cart modal if it exists (legacy support)
            const cartModalElement = document.getElementById('cartModal');
            if (cartModalElement) {
                const cartModal = bootstrap.Modal.getInstance(cartModalElement);
                if (cartModal) {
                    cartModal.hide();
                }
            }
        } else {
            // Check if customer selection is required
            if (data.requires_customer_selection) {
                addMessage(data.message || 'Please select a customer before placing an order.', 'bot', 'error');
                // Show action buttons to help user select customer
                setTimeout(() => {
                    showActionButtons([
                        {'text': 'Place Order', 'action': 'place_order'},
                        {'text': 'View Open Order', 'action': 'open_order'},
                        {'text': 'Company Info', 'action': 'company_info'},
                        {'text': 'Product Info', 'action': 'product_info'}
                    ]);
                }, 300);
        } else {
            addMessage(data.message || 'Error placing order', 'bot', 'error');
            }
        }
    } catch (error) {
        console.error('Error placing order:', error);
        addMessage('Error placing order. Please try again.', 'bot', 'error');
    }
}

function displayRecentOrders(orders) {
    let message = 'Here are your recent orders:\n\n';
    orders.forEach(order => {
        message += `• ${order.order_id} - ${order.status} - ${order.total_amount.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})} MMK (${order.order_date})\n`;
    });
    addMessage(message, 'bot');
}

function displayOrderDetails(orderDetails) {
    try {
        if (!orderDetails) {
            console.error('displayOrderDetails: Order data is missing');
            addMessage('Error: Order data is missing. Please try again.', 'bot', 'error');
            return;
        }

        const messagesDiv = document.getElementById('chatMessages');
        if (!messagesDiv) {
            console.error('displayOrderDetails: Chat messages container not found');
            return;
        }

        // Helper function to format dates safely
        const formatOrFallback = (value) => {
            if (!value) return 'Not available';
            try {
                if (typeof value === 'string' && value.includes('T')) {
                    // ISO format
                    const date = new Date(value);
                    if (!isNaN(date.getTime())) {
                        return formatDate(value);
                    }
                }
                return formatDate(value);
            } catch (e) {
                return value;
            }
        };

        // Helper function to get status badge HTML
        function getStatusBadge(status) {
            const statusLower = (status || '').toLowerCase();
            let badgeClass = 'pending';
            let badgeText = status ? status.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase()) : 'Unknown';
            
            if (statusLower.includes('confirm')) badgeClass = 'confirmed';
            else if (statusLower.includes('reject')) badgeClass = 'rejected';
            else if (statusLower.includes('cancel')) badgeClass = 'cancelled';
            else if (statusLower.includes('draft')) badgeClass = 'draft';
            else if (statusLower.includes('dispatch')) badgeClass = 'dispatched';
            else if (statusLower.includes('deliver')) badgeClass = 'delivered';
            
            return `<span class="order-status-badge ${badgeClass}">${badgeText}</span>`;
        }

        // Get timeline data
        const placedAt = orderDetails.placed_at || orderDetails.order_datetime || orderDetails.created_at || orderDetails.order_date;
        const confirmedAt = orderDetails.distributor_confirmed_at;
        const deliveredAt = orderDetails.delivered_at;
        const lastUpdatedAt = orderDetails.last_updated_at;
        
        // Check if order is cancelled
        const orderStatus = (orderDetails.status || orderDetails.status_display || '').toLowerCase();
        const isCancelled = orderStatus.includes('cancel');

        // Build initial message
        let message = `**📦 Order Details - ${orderDetails.order_id || 'Unknown'}**\n\n`;
        
        // Add pending order notice if applicable
        if (orderDetails.is_fulfilled_pending_order && orderDetails.pending_source_orders && orderDetails.pending_source_orders.length > 0) {
            message += `⚠️ **This order was created by fulfilling a previous pending order.**\n\n`;
            orderDetails.pending_source_orders.forEach(p => {
                message += `• Original Order ID: **${p.original_order_id || 'N/A'}** (placed on ${p.original_order_date ? formatOrFallback(p.original_order_date) : 'N/A'})\n`;
                message += `  - Product: ${p.product_name} (${p.product_code})\n`;
                message += `  - Requested Quantity: ${p.requested_quantity} units\n`;
            });
            message += `\n`;
        }

        // Add message first
        addMessage(message, 'bot');

        // Find the last bot message to add table
        const botMessages = messagesDiv.querySelectorAll('.message.bot');
        const lastBotMessage = botMessages[botMessages.length - 1];

        if (!lastBotMessage) {
            console.error('displayOrderDetails: Could not find last bot message');
            return;
        }

        // Find message bubble for table
        let messageBubbleForTable = lastBotMessage.querySelector('.message-bubble .bg-light');
        if (!messageBubbleForTable) {
            messageBubbleForTable = lastBotMessage.querySelector('.message-bubble');
        }
        if (!messageBubbleForTable) {
            messageBubbleForTable = lastBotMessage.querySelector('.bg-light');
        }
        if (!messageBubbleForTable) {
            messageBubbleForTable = lastBotMessage;
        }

        if (messageBubbleForTable) {
            // Create timeline and status table container
            const timelineTableContainer = document.createElement('div');
            timelineTableContainer.className = 'order-timeline-table mt-3 mb-3';
            timelineTableContainer.style.cssText = 'width: 100%; overflow-x: auto;';

            // Build timeline and status table
            let timelineTableHTML = `
                <div style="overflow-x: auto; width: 100%; max-width: 100%; box-sizing: border-box; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 15px;">
                    <table class="table table-bordered table-hover mb-0" style="font-size: 0.875rem; margin-bottom: 0; width: 100%; min-width: 700px; table-layout: auto;">
                        <thead style="background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%); color: white;">
                            <tr>
                                <th style="padding: 12px; border: 1px solid #1e40af; font-weight: 600; text-align: left; min-width: 180px;">Event</th>
                                <th style="padding: 12px; border: 1px solid #1e40af; font-weight: 600; text-align: left; min-width: 250px;">Date & Time</th>
                                <th style="padding: 12px; border: 1px solid #1e40af; font-weight: 600; text-align: center; min-width: 120px; white-space: nowrap;">Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr style="background-color: #f8f9fa;">
                                <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: 600; white-space: nowrap;">
                                    <i class="fas fa-shopping-cart me-2" style="color: #2563eb;"></i>Order Placed
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6;">
                                    ${placedAt ? formatOrFallback(placedAt) : 'Not available'}
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6; text-align: center; white-space: nowrap;">
                                    <span style="color: #10b981; font-weight: 600;">✓ Completed</span>
                                </td>
                            </tr>
                            ${!isCancelled ? `
                            <tr style="background-color: ${confirmedAt ? '#f0fdf4' : '#fff7ed'};">
                                <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: 600; white-space: nowrap;">
                                    <i class="fas fa-check-circle me-2" style="color: ${confirmedAt ? '#10b981' : '#f59e0b'};"></i>Dealer Confirmed
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6;">
                                    ${confirmedAt ? formatOrFallback(confirmedAt) : 'Not yet confirmed by dealer'}
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6; text-align: center; white-space: nowrap;">
                                    ${confirmedAt ? '<span style="color: #10b981; font-weight: 600;">✓ Completed</span>' : '<span style="color: #f59e0b; font-weight: 600;">⏳ Pending</span>'}
                                </td>
                            </tr>
                            <tr style="background-color: ${deliveredAt ? '#f0fdf4' : '#fff7ed'};">
                                <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: 600; white-space: nowrap;">
                                    <i class="fas fa-truck me-2" style="color: ${deliveredAt ? '#10b981' : '#f59e0b'};"></i>Delivered to Customer
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6;">
                                    ${deliveredAt ? formatOrFallback(deliveredAt) : 'Not yet delivered'}
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6; text-align: center; white-space: nowrap;">
                                    ${deliveredAt ? '<span style="color: #10b981; font-weight: 600;">✓ Completed</span>' : '<span style="color: #f59e0b; font-weight: 600;">⏳ Pending</span>'}
                                </td>
                            </tr>
                            ` : ''}
                            ${lastUpdatedAt ? `
                            <tr style="background-color: #f8f9fa;">
                                <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: 600; white-space: nowrap;">
                                    <i class="fas fa-clock me-2" style="color: #6b7280;"></i>Last Updated
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6;">
                                    ${formatOrFallback(lastUpdatedAt)}
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6; text-align: center; white-space: nowrap;">
                                    <span style="color: #6b7280;">-</span>
                                </td>
                            </tr>
                            ` : ''}
                        </tbody>
                    </table>
                </div>
            `;

            timelineTableContainer.innerHTML = timelineTableHTML;
            messageBubbleForTable.appendChild(timelineTableContainer);

            // Create order information table
            const infoTableContainer = document.createElement('div');
            infoTableContainer.className = 'order-info-table mt-3 mb-3';
            infoTableContainer.style.cssText = 'width: 100%; overflow-x: auto;';

            let infoTableHTML = `
                <div style="overflow-x: auto; width: 100%; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 15px;">
                    <table class="table table-bordered table-hover mb-0" style="font-size: 0.875rem; margin-bottom: 0; width: 100%; min-width: 500px;">
                        <thead style="background: linear-gradient(135deg, #059669 0%, #047857 100%); color: white;">
                            <tr>
                                <th style="padding: 12px; border: 1px solid #065f46; font-weight: 600; text-align: left; width: 40%;">Information</th>
                                <th style="padding: 12px; border: 1px solid #065f46; font-weight: 600; text-align: left; width: 60%;">Details</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: 600;">
                                    <i class="fas fa-info-circle me-2" style="color: #059669;"></i>Status
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6;">
                                    ${getStatusBadge(orderDetails.status_display || orderDetails.status)}
                                </td>
                            </tr>
                            ${orderDetails.order_stage ? `
                            <tr>
                                <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: 600;">
                                    <i class="fas fa-layer-group me-2" style="color: #059669;"></i>Order Stage
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6;">
                                    ${orderDetails.order_stage}
                                </td>
                            </tr>
                            ` : ''}
                            ${typeof orderDetails.total_amount === 'number' ? `
                            <tr>
                                <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: 600;">
                                    <i class="fas fa-money-bill-wave me-2" style="color: #059669;"></i>Total Amount
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6;">
                                    <strong style="color: #059669;">${orderDetails.total_amount.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})} MMK</strong>
                                </td>
                            </tr>
                            ` : ''}
                            ${orderDetails.order_date ? `
                            <tr>
                                <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: 600;">
                                    <i class="fas fa-calendar me-2" style="color: #059669;"></i>Order Date
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6;">
                                    ${orderDetails.order_date}
                                </td>
                            </tr>
                            ` : ''}
                            ${orderDetails.area ? `
                            <tr>
                                <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: 600;">
                                    <i class="fas fa-map-marker-alt me-2" style="color: #059669;"></i>Area
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6;">
                                    ${orderDetails.area}
                                </td>
                            </tr>
                            ` : ''}
                            ${orderDetails.customer_name ? `
                            <tr>
                                <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: 600;">
                                    <i class="fas fa-user me-2" style="color: #059669;"></i>Customer
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6;">
                                    ${orderDetails.customer_name}
                                </td>
                            </tr>
                            ` : ''}
                        </tbody>
                    </table>
                </div>
            `;

            infoTableContainer.innerHTML = infoTableHTML;
            messageBubbleForTable.appendChild(infoTableContainer);

            // Add items table if items exist
            if (orderDetails.items && orderDetails.items.length > 0) {
                const itemsTableContainer = document.createElement('div');
                itemsTableContainer.className = 'order-items-table mt-3 mb-3';
                itemsTableContainer.style.cssText = 'width: 100%; overflow-x: auto;';

                let itemsTableHTML = `
                    <div style="overflow-x: auto; width: 100%; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                        <table class="table table-bordered table-hover mb-0" style="font-size: 0.875rem; margin-bottom: 0; width: 100%; min-width: 500px;">
                            <thead style="background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%); color: white;">
                                <tr>
                                    <th style="padding: 12px; border: 1px solid #5b21b6; font-weight: 600; text-align: left;">Product Name</th>
                                    <th style="padding: 12px; border: 1px solid #5b21b6; font-weight: 600; text-align: center;">Quantity</th>
                                    <th style="padding: 12px; border: 1px solid #5b21b6; font-weight: 600; text-align: right;">Total Price</th>
                                </tr>
                            </thead>
                            <tbody>
                `;

                orderDetails.items.forEach((item, index) => {
                    const rowColor = index % 2 === 0 ? '#f8f9fa' : '#ffffff';
                    const lineTotal = typeof item.total_price === 'number'
                        ? item.total_price.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})
                        : item.total_price || '0.00';
                    
                    itemsTableHTML += `
                        <tr style="background-color: ${rowColor};">
                            <td style="padding: 12px; border: 1px solid #dee2e6;">
                                <strong>${item.product_name || 'Unknown Product'}</strong>
                            </td>
                            <td style="padding: 12px; border: 1px solid #dee2e6; text-align: center;">
                                ${item.quantity || 0} units
                            </td>
                            <td style="padding: 12px; border: 1px solid #dee2e6; text-align: right;">
                                <strong>${lineTotal} MMK</strong>
                            </td>
                        </tr>
                    `;
                });

                itemsTableHTML += `
                            </tbody>
                        </table>
                    </div>
                `;

                itemsTableContainer.innerHTML = itemsTableHTML;
                messageBubbleForTable.appendChild(itemsTableContainer);
            }

            // Scroll to bottom
            messagesDiv.scrollTo({
                top: messagesDiv.scrollHeight,
                behavior: 'smooth'
            });
        }
    } catch (error) {
        console.error('Error displaying order details:', error);
        addMessage('Error displaying order details. Please try again.', 'bot', 'error');
    }
}

function resetChat() {
    const messagesDiv = document.getElementById('chatMessages');
    messagesDiv.innerHTML = `
        <div class="text-center text-muted py-5">
            <i class="fas fa-robot fa-3x mb-3"></i>
            <h4>Welcome to HV (Powered by Quantum Blue AI)</h4>
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
    document.getElementById('cartButton').style.display = 'none';
    
    // Show action buttons to start new conversation
    showActionButtons([
        {'text': 'Place Order', 'action': 'place_order'},
        {'text': 'View Open Order', 'action': 'open_order'},
        {'text': 'Product Info', 'action': 'product_info'},
        {'text': 'Company Info', 'action': 'company_info'}
    ]);
    
    // Reset input placeholder
    document.getElementById('messageInput').placeholder = 'Enter your unique ID to start...';
}

// Utility functions
function formatCurrency(amount) {
    return new Intl.NumberFormat('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(amount) + ' MMK';
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

function addStockConfirmationForm(stocks, invoiceIds = null, invoiceDates = null, showTable = false) {
    const messagesDiv = document.getElementById('chatMessages');
    const formDiv = document.createElement('div');
    formDiv.className = 'message bot mb-3';
    formDiv.id = 'stockConfirmationForm';
    
    let formHTML = `
        <div class="message-bubble bot">
            <div class="bg-light border rounded-3 px-3 py-3" style="max-width: 100%; width: 100%; font-size: 0.875rem;">
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
                                    <i class="fas fa-calendar me-2"></i>Filter by Invoice Date
                                </label>
                                <select class="form-select form-select-sm" id="dateFilter" 
                                    style="border-radius: 8px; border: 1.5px solid #e5e7eb; padding: 8px 12px; font-size: 0.875rem;">
                                    <option value="">-- All Dates --</option>
                                    ${((invoiceDates || dispatchDates) && (invoiceDates || dispatchDates).length > 0) ? (invoiceDates || dispatchDates).map(date => `
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
                                        <th style="padding: 8px; white-space: nowrap;">Invoice Date</th>
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
            // Check both expiry_date (from database) and expiration_date (legacy)
            let expirationDate = 'N/A';
            const expiryDateValue = stock.expiry_date || stock.expiration_date;
            if (expiryDateValue) {
                const expDate = new Date(expiryDateValue);
                if (!isNaN(expDate.getTime())) {
                    expirationDate = expDate.toISOString().split('T')[0];
                } else {
                    expirationDate = expiryDateValue;
                }
            }
            
            let invoiceDate = 'N/A';
            let invoiceDateFilter = '';
            if (stock.dispatch_date || stock.invoice_date) {
                const dateValue = stock.invoice_date || stock.dispatch_date;
                const invDate = new Date(dateValue);
                if (!isNaN(invDate.getTime())) {
                    invoiceDate = invDate.toISOString().split('T')[0];
                    invoiceDateFilter = invoiceDate;
                } else {
                    invoiceDate = dateValue;
                    invoiceDateFilter = dateValue;
                }
            }
            
            const salesPrice = stock.sales_price ? `${parseFloat(stock.sales_price).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})} MMK` : 'N/A';
            
            formHTML += `
                                    <tr data-stock-id="${stock.id}" data-invoice-id="${stock.invoice_id || ''}" data-invoice-date="${invoiceDateFilter}" style="cursor: pointer;" onclick="selectStockFromTable(${stock.id}, ${stock.quantity})">
                                        <td style="padding: 8px;">${index + 1}</td>
                                        <td style="padding: 8px;">${stock.product_name || 'N/A'}</td>
                                        <td style="padding: 8px;">${invoiceDate}</td>
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
        // Include invoice_id and invoice_date in data attribute for filtering
        const invoiceId = stock.invoice_id || '';
        let invoiceDate = '';
        if (stock.dispatch_date || stock.invoice_date) {
            const dateValue = stock.invoice_date || stock.dispatch_date;
            const invDate = new Date(dateValue);
            if (!isNaN(invDate.getTime())) {
                invoiceDate = invDate.toISOString().split('T')[0];
            } else {
                invoiceDate = dateValue;
            }
        }
        formHTML += `
            <option value="${stock.id}" data-quantity="${stock.quantity}" data-invoice-id="${invoiceId}" data-invoice-date="${invoiceDate}">
                ${index + 1}. ${stock.product_name} - Qty Sent: ${stock.quantity} units${invoiceId ? ` - Invoice: ${invoiceId}` : ''}
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
                option.textContent = `${index + 1}. ${stock.product_name} - Qty Sent: ${stock.quantity} units${invoiceIdValue ? ` - Invoice: ${invoiceIdValue}` : ''}`;
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
                    <!-- Search Bar with Favorites Filter -->
                    <div class="mb-3">
                        <div class="d-flex align-items-center justify-content-between mb-2">
                            <label class="form-label mb-0" style="font-weight: 500;">Search products:</label>
                            <div class="form-check">
                                <input class="form-check-input" type="checkbox" id="productFavoriteFilterCheckbox" 
                                       onchange="filterProductTable()"
                                       style="cursor: pointer;">
                                <label class="form-check-label" for="productFavoriteFilterCheckbox" style="cursor: pointer; font-size: 0.875rem; font-weight: 500;">
                                    <i class="fas fa-star" style="color: #fbbf24;"></i> Favorites Only
                                </label>
                            </div>
                        </div>
                        <div class="input-group">
                            <span class="input-group-text" style="background: #dbeafe; border-radius: 8px 0 0 8px; border: 2px solid #bfdbfe; border-right: none;">
                                <i class="fas fa-search" style="color: #1e40af;"></i>
                            </span>
                            <input type="text" 
                                   class="form-control" 
                                   id="productSearchInput" 
                                   placeholder="Search products by name..." 
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
                                            <span>${product.product_name}</span>
                                        </div>
                                    </td>
                                    <td style="padding: 12px; color: #059669; font-weight: 600;">${product.sales_price.toLocaleString()} MMK</td>
                                    <td style="padding: 12px;">
                                        <span class="badge ${product.available_for_sale > 10 ? 'bg-success' : (product.available_for_sale > 0 ? 'bg-warning text-dark' : 'bg-danger')}" style="font-size: 0.8rem; padding: 5px 10px;">${product.available_for_sale}</span>
                                        <small class="text-muted ms-1" style="font-size: 0.7rem;">units</small>
                                    </td>
                                    <td style="padding: 12px;">
                                        <div>
                                            <input type="number" 
                                                   class="form-control form-control-sm product-quantity-input" 
                                                   id="qty_${product.product_code}"
                                                   data-product-foc="${product.foc || ''}"
                                                   data-product-name="${product.product_name.replace(/"/g, '&quot;')}"
                                                   data-foc-schemes='${focSchemesJson.replace(/'/g, "&apos;")}'
                                                   data-product-code="${product.product_code}"
                                                   min="0" 
                                                   max="${product.available_for_sale}" 
                                                   value="0"
                                                   placeholder="0"
                                                   onchange="updateSelectedProductsCount(); checkFOCNotification(this)"
                                                   oninput="updateSelectedProductsCount(); checkFOCNotification(this)"
                                                   style="width: 100%; min-width: 80px; max-width: 120px; text-align: center; border-radius: 8px; border: 2px solid #e5e7eb; padding: 8px 12px; font-weight: 600; font-size: 0.95rem;">
                                            <div id="foc-notification-${product.product_code}" class="foc-notification" style="display: none; margin-top: 4px; font-size: 0.75rem; color: #059669; font-weight: 600;"></div>
                                        </div>
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
                        <button type="button" class="btn" onclick="showOrderTemplates()"
                                style="border-radius: 10px; padding: 12px 20px; font-weight: 600; font-size: 0.9rem; background: linear-gradient(135deg, #10b981 0%, #059669 100%); border: none; color: white; box-shadow: 0 3px 10px rgba(16, 185, 129, 0.3);">
                            <i class="fas fa-file-alt me-2"></i>Order Templates
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

// Update product form star icons after favorite toggle
function updateProductFormStars() {
    // Find all product form tables in the page
    const productFormTables = document.querySelectorAll('#productTableBody tr.product-row');
    
    productFormTables.forEach(row => {
        const favoriteBtn = row.querySelector('.favorite-btn');
        if (favoriteBtn) {
            // Extract product code from onclick attribute
            const onclickAttr = favoriteBtn.getAttribute('onclick');
            if (onclickAttr) {
                // Try to match the product code from the onclick string
                const match = onclickAttr.match(/'products',\s*'([^']+)'/);
                if (match && match[1]) {
                    const productCode = match[1];
                    const isFav = isFavorite('products', productCode);
                    const starIcon = favoriteBtn.querySelector('i');
                    if (starIcon) {
                        if (isFav) {
                            starIcon.className = 'fas fa-star';
                            starIcon.style.color = '#fbbf24';
                            favoriteBtn.classList.add('active');
                            favoriteBtn.setAttribute('title', 'Remove from favorites');
                        } else {
                            starIcon.className = 'far fa-star';
                            starIcon.style.color = '#6b7280';
                            favoriteBtn.classList.remove('active');
                            favoriteBtn.setAttribute('title', 'Add to favorites');
                        }
                    }
                }
            }
        }
    });
}

// Make it globally accessible
window.updateProductFormStars = updateProductFormStars;

// Filter product table by search text and favorites
function filterProductTable() {
    const searchInput = document.getElementById('productSearchInput');
    const favoriteCheckbox = document.getElementById('productFavoriteFilterCheckbox');
    const rows = document.querySelectorAll('#productTableBody tr.product-row');
    
    if (!searchInput) return;
    
    const searchTerm = searchInput.value.toLowerCase().trim();
    const showFavoritesOnly = favoriteCheckbox && favoriteCheckbox.checked;
    
    // Create array of rows with match scores
    const rowsWithScores = Array.from(rows).map(row => {
        const productCode = row.getAttribute('data-product-code') || '';
        
        // Check favorite filter first
        if (showFavoritesOnly && !isFavorite('products', productCode)) {
            return { row, score: 0 };
        }
        
        // If no search term and not filtering by favorites, show all
        if (!searchTerm && !showFavoritesOnly) {
            return { row, score: 1 };
        }
        
        // If no search term but filtering by favorites, show if favorite
        if (!searchTerm && showFavoritesOnly) {
            return { row, score: isFavorite('products', productCode) ? 1 : 0 };
        }
        
        // Apply search filter
        const searchText = row.getAttribute('data-search-text') || '';
        const productName = row.getAttribute('data-product-name') || '';
        
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
    
    // Store customers data for filtering
    formCard.dataset.customers = JSON.stringify(customers);
    
    formCard.innerHTML = `
        <h6 class="mb-3" style="color: #2563eb; font-weight: 600;">
            <i class="fas fa-users me-2"></i>Select Customer
        </h6>
        <form id="customerSelectionForm" onsubmit="handleCustomerSelection(event)">
            <div class="mb-3 position-relative">
                <div class="d-flex align-items-center justify-content-between mb-2">
                    <label for="customerSearchInput" class="form-label mb-0" style="font-weight: 500;">Search for a customer:</label>
                    <div class="form-check">
                        <input class="form-check-input" type="checkbox" id="favoriteFilterCheckbox" 
                               onchange="filterCustomerSearch()"
                               style="cursor: pointer;">
                        <label class="form-check-label" for="favoriteFilterCheckbox" style="cursor: pointer; font-size: 0.875rem; font-weight: 500;">
                            <i class="fas fa-star" style="color: #fbbf24;"></i> Favorites Only
                        </label>
                    </div>
                </div>
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
    
    // Add event listener for customer search after form is added to DOM
    setTimeout(() => {
        const customerSearchInput = document.getElementById('customerSearchInput');
        const customerDropdown = document.getElementById('customerDropdown');
        const customerDropdownList = document.getElementById('customerDropdownList');
        
        if (customerSearchInput && customerDropdown && customerDropdownList) {
            // Search customers as user types
            customerSearchInput.addEventListener('input', function(e) {
                filterCustomerSearch();
            });
            
            // Function to filter customer search (make it accessible globally)
            function filterCustomerSearch() {
                const query = customerSearchInput.value.trim().toLowerCase();
                const favoriteCheckbox = document.getElementById('favoriteFilterCheckbox');
                const showFavoritesOnly = favoriteCheckbox && favoriteCheckbox.checked;
                
                if (query.length < 1 && !showFavoritesOnly) {
                    customerDropdown.style.display = 'none';
                    return;
                }
                
                // Filter customers based on search query and favorite filter
                const filtered = customers.filter(customer => {
                    // Apply favorite filter if checkbox is checked
                    if (showFavoritesOnly && !isFavorite('customers', customer.unique_id)) {
                        return false;
                    }
                    // Apply search query if there is one
                    if (query.length > 0) {
                    const nameMatch = customer.name.toLowerCase().includes(query);
                    const idMatch = customer.unique_id.toLowerCase().includes(query);
                    return nameMatch || idMatch;
                    }
                    // If no query but favorites only, show all favorites
                    return true;
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
            }
            
            // Make function globally accessible
            window.filterCustomerSearch = filterCustomerSearch;
            
            // Show dropdown when input is focused (if favorites checkbox is checked)
            customerSearchInput.addEventListener('focus', function(e) {
                const favoriteCheckbox = document.getElementById('favoriteFilterCheckbox');
                if (favoriteCheckbox && favoriteCheckbox.checked) {
                    filterCustomerSearch();
                }
            });
            
            // Close dropdown when clicking outside
            const favoriteCheckbox = document.getElementById('favoriteFilterCheckbox');
            document.addEventListener('click', function(e) {
                if (!customerSearchInput.contains(e.target) && 
                    !customerDropdown.contains(e.target) && 
                    !(favoriteCheckbox && favoriteCheckbox.contains(e.target))) {
                    customerDropdown.style.display = 'none';
                }
            });
        }
    }, 100);
    
    formContainer.appendChild(formCard);
    messageBubble.appendChild(formContainer); // Append to the message bubble instead of messagesDiv
    
    // Store reference to customers for filtering
    formContainer._customers = customers;
    
    // No need to show customer details - table already shows all info
}

// Update customer table star icons after favorite toggle
function updateCustomerTableStars() {
    // Find all customer tables in the page
    const customerTables = document.querySelectorAll('.customer-table-container table tbody');
    
    customerTables.forEach(tableBody => {
        const rows = tableBody.querySelectorAll('tr');
        rows.forEach(row => {
            const favoriteBtn = row.querySelector('.favorite-btn');
            if (favoriteBtn) {
                // Extract customer ID from onclick attribute
                const onclickAttr = favoriteBtn.getAttribute('onclick');
                if (onclickAttr) {
                    // Try to match the customer ID from the onclick string
                    const match = onclickAttr.match(/'customers',\s*'([^']+)'/);
                    if (match && match[1]) {
                        const customerId = match[1];
                        const isFav = isFavorite('customers', customerId);
                        const starIcon = favoriteBtn.querySelector('i');
                        if (starIcon) {
                            if (isFav) {
                                starIcon.className = 'fas fa-star';
                                starIcon.style.color = '#fbbf24';
                                favoriteBtn.classList.add('active');
                                favoriteBtn.setAttribute('title', 'Remove from favorites');
                            } else {
                                starIcon.className = 'far fa-star';
                                starIcon.style.color = '#6b7280';
                                favoriteBtn.classList.remove('active');
                                favoriteBtn.setAttribute('title', 'Add to favorites');
                            }
                        }
                    }
                }
            }
        });
    });
}

// Make it globally accessible
window.updateCustomerTableStars = updateCustomerTableStars;

// Keep filterCustomerTable for backward compatibility (if used elsewhere)
function filterCustomerTable() {
    updateCustomerTableStars();
}

// Update product table star icons after favorite toggle
function updateProductTableStars() {
    // Find all product tables in the page
    const productTables = document.querySelectorAll('.product-table-container table tbody');
    
    productTables.forEach(tableBody => {
        const rows = tableBody.querySelectorAll('tr');
        rows.forEach(row => {
            const favoriteBtn = row.querySelector('.favorite-btn');
            if (favoriteBtn) {
                // Extract product code from onclick attribute
                const onclickAttr = favoriteBtn.getAttribute('onclick');
                if (onclickAttr) {
                    // Try to match the product code from the onclick string
                    const match = onclickAttr.match(/'products',\s*'([^']+)'/);
                    if (match && match[1]) {
                        const productCode = match[1];
                        const isFav = isFavorite('products', productCode);
                        const starIcon = favoriteBtn.querySelector('i');
                        if (starIcon) {
                            if (isFav) {
                                starIcon.className = 'fas fa-star';
                                starIcon.style.color = '#fbbf24';
                                favoriteBtn.classList.add('active');
                                favoriteBtn.setAttribute('title', 'Remove from favorites');
                            } else {
                                starIcon.className = 'far fa-star';
                                starIcon.style.color = '#6b7280';
                                favoriteBtn.classList.remove('active');
                                favoriteBtn.setAttribute('title', 'Add to favorites');
                            }
                        }
                    }
                }
            }
        });
    });
}

// Make it globally accessible
window.updateProductTableStars = updateProductTableStars;

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
    
    // Add vertical scroll if more than 5 customers
    const hasScroll = customers.length > 5;
    const scrollStyle = hasScroll ? 'max-height: 280px; overflow-y: auto; overflow-x: auto;' : 'overflow-x: auto;';
    tableContainer.style.cssText = `animation: slideInFromBottom 0.3s ease-out; width: 100%; max-width: 100%; ${scrollStyle} border-radius: 12px; border: 1px solid #dee2e6;`;
    
    let tableHTML = `
        <table class="table table-bordered table-hover mb-0" style="font-size: 0.875rem; margin-bottom: 0; min-width: 100%; white-space: nowrap;">
            <thead style="background-color: #f8f9fa; ${hasScroll ? 'position: sticky; top: 0; z-index: 10;' : ''}">
                <tr>
                    <th style="padding: 10px; border: 1px solid #dee2e6; font-weight: 600; white-space: nowrap; background-color: #f8f9fa;">Customer Name</th>
                    <th style="padding: 10px; border: 1px solid #dee2e6; font-weight: 600; white-space: nowrap; background-color: #f8f9fa;">Customer ID</th>
                </tr>
            </thead>
            <tbody>
                ${customers.map(customer => {
                    const isFav = isFavorite('customers', customer.unique_id);
                    return `
                    <tr>
                        <td style="padding: 10px; border: 1px solid #dee2e6; white-space: nowrap;">
                            <div class="d-flex align-items-center gap-2">
                                <button class="favorite-btn ${isFav ? 'active' : ''}" 
                                        onclick="event.stopPropagation(); toggleFavorite('customers', '${customer.unique_id}', '${customer.name.replace(/'/g, "\\'")}'); updateCustomerTableStars();"
                                        title="${isFav ? 'Remove from favorites' : 'Add to favorites'}"
                                        style="background: transparent; border: none; padding: 4px; cursor: pointer;">
                                    <i class="${isFav ? 'fas' : 'far'} fa-star" style="color: ${isFav ? '#fbbf24' : '#6b7280'}; font-size: 1.1rem;"></i>
                                </button>
                                <span>${customer.name}</span>
                            </div>
                        </td>
                        <td style="padding: 10px; border: 1px solid #dee2e6; white-space: nowrap;">${customer.unique_id}</td>
                    </tr>
                `;
                }).join('')}
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
    
    // Add vertical scroll if more than 5 products
    const hasScroll = products.length > 5;
    const scrollStyle = hasScroll ? 'max-height: 280px; overflow-y: auto; overflow-x: auto;' : 'overflow-x: auto;';
    tableContainer.style.cssText = `animation: slideInFromBottom 0.3s ease-out; width: 100%; max-width: 100%; ${scrollStyle} border-radius: 12px; border: 1px solid #dee2e6;`;
    
    let tableHTML = `
        <table class="table table-bordered table-hover mb-0" style="font-size: 0.875rem; margin-bottom: 0; min-width: 100%; white-space: nowrap;">
            <thead style="background-color: #f8f9fa; ${hasScroll ? 'position: sticky; top: 0; z-index: 10;' : ''}">
                <tr>
                    <th style="padding: 10px; border: 1px solid #dee2e6; font-weight: 600; white-space: nowrap; background-color: #f8f9fa;">Product Name</th>
                    <th style="padding: 10px; border: 1px solid #dee2e6; font-weight: 600; white-space: nowrap; background-color: #f8f9fa;">Price</th>
                    <th style="padding: 10px; border: 1px solid #dee2e6; font-weight: 600; white-space: nowrap; background-color: #f8f9fa;">Available Quantity</th>
                </tr>
            </thead>
            <tbody>
                ${products.map(product => {
                    const isFav = isFavorite('products', product.product_code);
                    return `
                    <tr>
                        <td style="padding: 10px; border: 1px solid #dee2e6; white-space: nowrap;">
                            <div class="d-flex align-items-center gap-2">
                                <button class="favorite-btn ${isFav ? 'active' : ''}" 
                                        onclick="event.stopPropagation(); toggleFavorite('products', '${product.product_code}', '${product.product_name.replace(/'/g, "\\'")}'); updateProductTableStars();"
                                        title="${isFav ? 'Remove from favorites' : 'Add to favorites'}"
                                        style="background: transparent; border: none; padding: 4px; cursor: pointer;">
                                    <i class="${isFav ? 'fas' : 'far'} fa-star" style="color: ${isFav ? '#fbbf24' : '#6b7280'}; font-size: 1.1rem;"></i>
                                </button>
                            <strong>${product.product_name}</strong>
                            </div>
                        </td>
                        <td style="padding: 10px; border: 1px solid #dee2e6; white-space: nowrap;">${(product.sales_price || 0).toLocaleString('en-US')} MMK</td>
                        <td style="padding: 10px; border: 1px solid #dee2e6; white-space: nowrap;">${product.available_for_sale || 0} units</td>
                    </tr>
                `;
                }).join('')}
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
    tableContainer.style.cssText = 'animation: slideInFromBottom 0.3s ease-out; width: 100%; max-width: 100%; box-sizing: border-box;';
    
    let tableHTML = `
        <div style="width: 100%; border-radius: 12px; overflow: hidden; border: 1px solid #dee2e6;">
            <table class="table table-bordered table-hover mb-0" style="font-size: 0.875rem; margin-bottom: 0; width: 100%; min-width: 300px; white-space: nowrap;">
                <thead style="background-color: #f8f9fa; position: sticky; top: 0; z-index: 10;">
                    <tr>
                        <th style="padding: 10px; border: 1px solid #dee2e6; font-weight: 600; white-space: nowrap; background-color: #f8f9fa;">${(typeof t !== 'undefined') ? t('labels.orderId') : 'Order ID'}</th>
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
    
    if (!messagesDiv) {
        console.error('addOrderSelectionForm: Chat messages container not found');
        return;
    }
    
    // Find the last bot message
    const botMessages = messagesDiv.querySelectorAll('.message.bot');
    let lastBotMessage = null;
    
    if (botMessages.length > 0) {
        lastBotMessage = botMessages[botMessages.length - 1];
    }
    
    if (!lastBotMessage) {
        console.error('addOrderSelectionForm: No bot message found');
        return; // Exit if no bot message found
    }
    
    // Find the inner message bubble div (the one with bg-light class)
    // Try multiple selectors to find the message content area
    let messageBubble = lastBotMessage.querySelector('.message-bubble .bg-light');
    if (!messageBubble) {
        messageBubble = lastBotMessage.querySelector('.message-bubble .d-flex .bg-light');
    }
    if (!messageBubble) {
        messageBubble = lastBotMessage.querySelector('.bg-light');
    }
    if (!messageBubble) {
        // Try to find the message-bubble itself and append directly
        const bubbleDiv = lastBotMessage.querySelector('.message-bubble');
        if (bubbleDiv) {
            // Find or create a wrapper div inside the bubble
            let wrapper = bubbleDiv.querySelector('.d-flex');
            if (!wrapper) {
                wrapper = document.createElement('div');
                wrapper.className = 'd-flex justify-content-start align-items-center';
                wrapper.style.cssText = 'gap: 8px; width: 100%;';
                bubbleDiv.appendChild(wrapper);
            }
            // Create content div if it doesn't exist
            let contentDiv = wrapper.querySelector('.bg-light');
            if (!contentDiv) {
                contentDiv = document.createElement('div');
                contentDiv.className = 'bg-light border rounded-3 px-3 py-2';
                contentDiv.style.cssText = 'max-width: 100%; font-size: 0.875rem; width: 100%;';
                wrapper.appendChild(contentDiv);
            }
            messageBubble = contentDiv;
        }
    }
    
    if (!messageBubble) {
        console.error('addOrderSelectionForm: Could not find message bubble element');
        console.log('Last bot message:', lastBotMessage);
        console.log('Last bot message HTML:', lastBotMessage.innerHTML.substring(0, 500));
        return; // Exit if bubble not found
    }
    
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
    
    // Check if we have filters (for distributor view or MR view)
    // Distributor view has mr_names filter, MR view has customers filter
    const isDistributorView = filters && filters.mr_names && filters.mr_names.length > 0;
    const isMRView = filters && filters.customers && filters.customers.length > 0; // MR view has customer filter
    
    // Get unique values for filters
    const uniqueDates = filters?.dates || [...new Set(orders.map(o => o.order_date))].sort().reverse();
    const uniqueStatuses = filters?.statuses || [...new Set(orders.map(o => o.status || o.status_raw))].sort();
    const uniqueMRs = filters?.mr_names || [];
    const uniqueCustomers = filters?.customers || [];
    
    // Get translations
    const t_func = (typeof t !== 'undefined') ? t : (key) => key;
    const orderManagementLabel = t_func('labels.orderManagementDashboard');
    const selectOrderLabel = t_func('labels.selectOrderToTrack');
    
    formCard.innerHTML = `
        <h6 class="mb-3" style="color: #2563eb; font-weight: 600;">
            <i class="fas fa-${isDistributorView ? 'list-check' : 'truck'} me-2"></i>${isDistributorView ? orderManagementLabel : selectOrderLabel}
        </h6>
        <form id="orderSelectionForm" onsubmit="handleOrderSelection(event)">
            ${isDistributorView ? `
            <div class="mb-3">
                <label for="mrFilter" class="form-label" style="font-weight: 500;">
                    <i class="fas fa-user me-2"></i>${t_func('labels.filterByMRName')}
                </label>
                <select class="form-select form-select-sm" id="mrFilter" 
                    style="border-radius: 8px; border: 1.5px solid #e5e7eb; padding: 8px 12px; font-size: 0.875rem;"
                    onchange="if(typeof filterOrdersByAll === 'function') filterOrdersByAll(); else console.error('filterOrdersByAll not found');">
                    <option value="">${t_func('labels.allMRs')}</option>
                    ${uniqueMRs.map(mr => `
                        <option value="${mr}">${mr}</option>
                    `).join('')}
                </select>
            </div>
            ` : ''}
            ${isMRView && uniqueCustomers.length > 0 ? `
            <div class="mb-3">
                <label for="customerFilter" class="form-label" style="font-weight: 500;">
                    <i class="fas fa-users me-2"></i>${t_func('labels.filterByCustomer')}
                </label>
                <select class="form-select form-select-sm" id="customerFilter" 
                    style="border-radius: 8px; border: 1.5px solid #e5e7eb; padding: 8px 12px; font-size: 0.875rem;"
                    onchange="if(typeof filterOrdersByDateAndStatus === 'function') filterOrdersByDateAndStatus(); else console.error('filterOrdersByDateAndStatus not found');">
                    <option value="">${t_func('labels.allCustomers')}</option>
                    ${uniqueCustomers.map(customer => `
                        <option value="${customer}">${customer}</option>
                    `).join('')}
                </select>
            </div>
            ` : ''}
            <div class="mb-3">
                <label for="dateFilter" class="form-label" style="font-weight: 500;">
                    <i class="fas fa-calendar-alt me-2"></i>${t_func('labels.filterByDate')}
                </label>
                <select class="form-select form-select-sm" id="dateFilter" 
                    style="border-radius: 8px; border: 1.5px solid #e5e7eb; padding: 8px 12px; font-size: 0.875rem;"
                    onchange="${isDistributorView ? 'if(typeof filterOrdersByAll === \'function\') filterOrdersByAll(); else console.error(\'filterOrdersByAll not found\');' : 'if(typeof filterOrdersByDateAndStatus === \'function\') filterOrdersByDateAndStatus(); else console.error(\'filterOrdersByDateAndStatus not found\');'}">
                    <option value="">${t_func('labels.allDates')}</option>
                    ${uniqueDates.map(date => `
                        <option value="${date}">${date}</option>
                    `).join('')}
                </select>
            </div>
            <div class="mb-3">
                <label for="statusFilter" class="form-label" style="font-weight: 500;">
                    <i class="fas fa-filter me-2"></i>${t_func('labels.filterByStatus')}
                </label>
                <select class="form-select form-select-sm" id="statusFilter" 
                    style="border-radius: 8px; border: 1.5px solid #e5e7eb; padding: 8px 12px; font-size: 0.875rem;"
                    onchange="${isDistributorView ? 'if(typeof filterOrdersByAll === \'function\') filterOrdersByAll(); else console.error(\'filterOrdersByAll not found\');' : 'if(typeof filterOrdersByDateAndStatus === \'function\') filterOrdersByDateAndStatus(); else console.error(\'filterOrdersByDateAndStatus not found\');'}">
                    <option value="">${t_func('labels.allStatuses')}</option>
                    ${uniqueStatuses.map(status => `
                        <option value="${status}">${status.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}</option>
                    `).join('')}
                </select>
            </div>
            <div class="mb-3">
                <label for="orderSelect" class="form-label" style="font-weight: 500;">
                    <i class="fas fa-box me-2"></i>${t_func('labels.chooseAnOrder')}
                </label>
                <div id="orderListContainer" style="max-height: 400px; overflow-y: auto; overflow-x: hidden; border: 2px solid #e5e7eb; border-radius: 10px; padding: 8px; display: none;">
                    ${orders.map((order, index) => {
                        const status = order.status || order.status_raw || 'pending';
                        const statusLower = status.toLowerCase();
                        let badgeClass = 'pending';
                        if (statusLower.includes('confirm')) badgeClass = 'confirmed';
                        else if (statusLower.includes('reject')) badgeClass = 'rejected';
                        else if (statusLower.includes('cancel')) badgeClass = 'cancelled';
                        else if (statusLower.includes('draft')) badgeClass = 'draft';
                        else if (statusLower.includes('dispatch')) badgeClass = 'dispatched';
                        else if (statusLower.includes('deliver')) badgeClass = 'delivered';
                        
                        const statusDisplay = order.status_display || status.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
                        return `
                        <div class="order-item-row mb-2 p-2 border rounded" 
                             data-order-id="${String(order.order_id || '').replace(/"/g, '&quot;')}"
                             data-status="${String(status || '').replace(/"/g, '&quot;')}"
                             data-total="${order.total_amount || 0}"
                             data-date="${String(order.order_date || '').replace(/"/g, '&quot;')}"
                             data-mr="${String(order.mr_name || '').replace(/"/g, '&quot;')}"
                             data-customer="${String(order.customer_name || '').replace(/"/g, '&quot;')}"
                             data-customer-id="${String(order.customer_id || '').replace(/"/g, '&quot;')}"
                             style="cursor: pointer; transition: all 0.2s;"
                             onmouseover="this.style.backgroundColor='#f0f0f0'" 
                             onmouseout="this.style.backgroundColor=''"
                             onclick="handleOrderSelectionFromList('${String(order.order_id || '').replace(/'/g, "\\'")}');">
                            <div class="d-flex justify-content-between align-items-center">
                                <div>
                                    <strong>${order.order_id}</strong>
                                    ${order.customer_name ? ` | ${order.customer_name}` : ''}
                                    ${order.mr_name ? ` | MR: ${order.mr_name}` : ''}
                                </div>
                                <div class="d-flex align-items-center gap-2">
                                    <span class="order-status-badge ${badgeClass}">${statusDisplay}</span>
                                    <span>${order.total_amount ? (order.total_amount.toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 0}) + ' MMK') : '0 MMK'}</span>
                                    <span class="text-muted small">${order.order_date}</span>
                                    <button class="btn btn-sm btn-outline-primary" 
                                            onclick="event.stopPropagation(); handleOrderSelectionFromList('${String(order.order_id || '').replace(/'/g, "\\'")}');" 
                                            title="${t_func('labels.viewOrderDetails')}"
                                            style="padding: 2px 8px; font-size: 0.75rem;">
                                        <i class="fas fa-eye"></i> ${t_func('labels.viewOrderDetails')}
                                    </button>
                                </div>
                            </div>
                            ${isDistributorView ? '' : `
                            <label class="d-flex justify-content-between align-items-center" style="cursor: pointer; margin: 0;" onclick="handleOrderSelectionFromList('${String(order.order_id || '').replace(/'/g, "\\'")}')">
                                <div>
                                    <strong>${order.order_id}</strong>
                                    ${order.customer_name ? ` | ${order.customer_name}` : ''}
                                </div>
                                <div class="d-flex align-items-center gap-2">
                                    <span class="order-status-badge ${badgeClass}">${statusDisplay}</span>
                                    <span>${order.total_amount ? (order.total_amount.toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 0}) + ' MMK') : '0 MMK'}</span>
                                    <span class="text-muted small">${order.order_date}</span>
                                </div>
                            </label>
                            `}
                        </div>
                    `;
                    }).join('')}
                </div>
                <select class="form-select form-select-lg" id="orderSelect" name="order_id" required 
                     style="border-radius: 10px; border: 2px solid #e5e7eb; padding: 12px; font-size: 0.95rem; max-height: 400px; overflow-y: auto; overflow-x: hidden; display: block;">
                      <option value="">${t_func('labels.selectOrder')}</option>
                    ${orders.map((order, index) => {
                        const status = order.status || order.status_raw || 'pending';
                        const statusLower = status.toLowerCase();
                        let badgeClass = 'pending';
                        if (statusLower.includes('confirm')) badgeClass = 'confirmed';
                        else if (statusLower.includes('reject')) badgeClass = 'rejected';
                        else if (statusLower.includes('cancel')) badgeClass = 'cancelled';
                        else if (statusLower.includes('draft')) badgeClass = 'draft';
                        else if (statusLower.includes('dispatch')) badgeClass = 'dispatched';
                        else if (statusLower.includes('deliver')) badgeClass = 'delivered';
                        
                        const statusDisplay = order.status_display || status.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
                        return `
                        <option value="${order.order_id}" 
                            data-status="${status}"
                            data-total="${order.total_amount}"
                            data-date="${order.order_date}"
                            data-mr="${order.mr_name || ''}"
                            data-customer="${order.customer_name || ''}"
                            data-customer-id="${order.customer_id || ''}"
                            data-index="${index}">
                            ${order.order_id}${order.customer_name ? ' | ' + order.customer_name : ''} | [${statusDisplay}] | ${order.total_amount ? (order.total_amount.toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 0}) + ' MMK') : '0 MMK'} | ${order.order_date}
                        </option>
                    `;
                    }).join('')}
                </select>
                <small class="text-muted d-block mt-1">
                    <i class="fas fa-info-circle me-1"></i>
                    ${isDistributorView ? t_func('messages.selectOrderFromDropdown') : t_func('messages.selectOrderToTrack')}
                </small>
            </div>
            <div class="d-flex gap-2">
                ${isDistributorView ? `
                <button type="submit" class="btn btn-primary flex-grow-1" 
                    style="border-radius: 8px; padding: 8px 14px; font-weight: 600; font-size: 0.8rem;">
                    <i class="fas fa-search me-2"></i>${t_func('labels.viewOrderDetails')}
                </button>
                ` : `
                <button type="submit" class="btn btn-primary flex-grow-1" 
                    style="border-radius: 8px; padding: 8px 14px; font-weight: 600; font-size: 0.8rem;">
                    <i class="fas fa-search me-2"></i>${t_func('labels.viewOrderDetails')}
                </button>
                `}
                <button type="button" class="btn btn-outline-secondary" onclick="this.closest('.order-selection-container').remove(); closeRecentSearches();"
                    style="border-radius: 8px; padding: 8px 14px; font-size: 0.8rem;">
                    <i class="fas fa-times"></i> ${t_func('labels.cancel')}
                </button>
            </div>
        </form>
    `;
    
    formContainer.appendChild(formCard);
    messageBubble.appendChild(formContainer); // Append to the message bubble instead of messagesDiv
    
    // Ensure form is visible
    formContainer.style.display = 'block';
    formContainer.style.visibility = 'visible';
    formContainer.style.opacity = '1';
    
    
    // Add event listeners directly to filter elements (more reliable than inline handlers)
    setTimeout(() => {
        const mrFilter = formContainer.querySelector('#mrFilter');
        const customerFilter = formContainer.querySelector('#customerFilter');
        const dateFilter = formContainer.querySelector('#dateFilter');
        const statusFilter = formContainer.querySelector('#statusFilter');
        
        if (mrFilter) {
            mrFilter.addEventListener('change', function() {
                console.log('MR filter changed:', this.value);
                if (typeof filterOrdersByAll === 'function') {
                    filterOrdersByAll();
                } else {
                    console.error('filterOrdersByAll function not found');
                }
            });
        }
        
        if (customerFilter) {
            customerFilter.addEventListener('change', function() {
                console.log('Customer filter changed:', this.value);
                if (typeof filterOrdersByDateAndStatus === 'function') {
                    filterOrdersByDateAndStatus();
                } else {
                    console.error('filterOrdersByDateAndStatus function not found');
                }
            });
        }
        
        if (dateFilter) {
            dateFilter.addEventListener('change', function() {
                console.log('Date filter changed:', this.value);
                if (isDistributorView) {
                    if (typeof filterOrdersByAll === 'function') {
                        filterOrdersByAll();
                    } else {
                        console.error('filterOrdersByAll function not found');
                    }
                } else {
                    if (typeof filterOrdersByDateAndStatus === 'function') {
                        filterOrdersByDateAndStatus();
                    } else {
                        console.error('filterOrdersByDateAndStatus function not found');
                    }
                }
            });
        }
        
        if (statusFilter) {
            statusFilter.addEventListener('change', function() {
                console.log('Status filter changed:', this.value);
                if (isDistributorView) {
                    if (typeof filterOrdersByAll === 'function') {
                        filterOrdersByAll();
                    } else {
                        console.error('filterOrdersByAll function not found');
                    }
                } else {
                    if (typeof filterOrdersByDateAndStatus === 'function') {
                        filterOrdersByDateAndStatus();
                    } else {
                        console.error('filterOrdersByDateAndStatus function not found');
                    }
                }
            });
        }
        
        console.log('addOrderSelectionForm: Event listeners attached', {
            mrFilter: !!mrFilter,
            customerFilter: !!customerFilter,
            dateFilter: !!dateFilter,
            statusFilter: !!statusFilter
        });
    }, 100);
    
    // Scroll to show the form
    setTimeout(() => {
        formContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }, 200);
    
    console.log('addOrderSelectionForm: Form added successfully', {
        ordersCount: orders.length,
        hasFilters: !!filters,
        formContainer: formContainer
    });
}

// Filter orders by all filters (MR name, date, status) - for distributors
function filterOrdersByAll() {
    try {
        const formContainer = document.querySelector('.order-selection-container');
        if (!formContainer || !formContainer._originalOrders) {
            console.warn('filterOrdersByAll: Form container or orders not found');
            return;
        }
        
        const orderList = document.getElementById('orderListContainer');
        const orderSelect = document.getElementById('orderSelect');
        const mrFilter = document.getElementById('mrFilter');
        const dateFilter = document.getElementById('dateFilter');
        const statusFilter = document.getElementById('statusFilter');
        
        if (!orderList && !orderSelect) {
            console.warn('filterOrdersByAll: Order list or select element not found');
            return;
        }
    
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
        // Normalize status for comparison (handle both raw status and display status)
        filteredOrders = filteredOrders.filter(order => {
            const orderStatus = order.status || order.status_raw || '';
            const normalizedOrderStatus = orderStatus.toLowerCase().replace(/\s+/g, '_');
            const normalizedSelectedStatus = selectedStatus.toLowerCase().replace(/\s+/g, '_');
            return normalizedOrderStatus === normalizedSelectedStatus || orderStatus === selectedStatus;
        });
    }
    
        // Update order list (for distributor view)
        if (orderList) {
            orderList.innerHTML = filteredOrders.map((order, index) => {
                const status = order.status || order.status_raw || 'pending';
                const statusLower = status.toLowerCase();
                let badgeClass = 'pending';
                if (statusLower.includes('confirm')) badgeClass = 'confirmed';
                else if (statusLower.includes('reject')) badgeClass = 'rejected';
                else if (statusLower.includes('cancel')) badgeClass = 'cancelled';
                else if (statusLower.includes('draft')) badgeClass = 'draft';
                else if (statusLower.includes('dispatch')) badgeClass = 'dispatched';
                else if (statusLower.includes('deliver')) badgeClass = 'delivered';
                
                const statusDisplay = order.status_display || status.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
                
                return `
                <div class="order-item-row mb-2 p-2 border rounded" 
                     data-order-id="${String(order.order_id || '').replace(/"/g, '&quot;')}"
                     data-status="${String(status || '').replace(/"/g, '&quot;')}"
                     data-total="${order.total_amount || 0}"
                     data-date="${String(order.order_date || '').replace(/"/g, '&quot;')}"
                     data-mr="${String(order.mr_name || '').replace(/"/g, '&quot;')}"
                     data-customer="${String(order.customer_name || '').replace(/"/g, '&quot;')}"
                     data-customer-id="${String(order.customer_id || '').replace(/"/g, '&quot;')}"
                     style="cursor: pointer; transition: all 0.2s;"
                     onmouseover="this.style.backgroundColor='#f0f0f0'" 
                     onmouseout="this.style.backgroundColor=''"
                     onclick="handleOrderSelectionFromList('${String(order.order_id || '').replace(/'/g, "\\'")}');">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <strong>${order.order_id}</strong>
                            ${order.customer_name ? ` | ${order.customer_name}` : ''}
                            ${order.mr_name ? ` | MR: ${order.mr_name}` : ''}
                        </div>
                        <div class="d-flex align-items-center gap-2">
                            <span class="order-status-badge ${badgeClass}">${statusDisplay}</span>
                            <span>${order.total_amount ? (order.total_amount.toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 0}) + ' MMK') : '0 MMK'}</span>
                            <span class="text-muted small">${order.order_date}</span>
                            <button class="btn btn-sm btn-outline-primary" 
                                    onclick="event.stopPropagation(); handleOrderSelectionFromList('${String(order.order_id || '').replace(/'/g, "\\'")}');" 
                                    title="View Order Details"
                                    style="padding: 2px 8px; font-size: 0.75rem;">
                                <i class="fas fa-eye"></i> View
                            </button>
                        </div>
                    </div>
                </div>
                `;
            }).join('');
        }
        
        // Update order select dropdown (for MR view)
        if (orderSelect) {
    const currentValue = orderSelect.value;
    orderSelect.innerHTML = '<option value="">-- Select Order --</option>' + 
                filteredOrders.map((order, index) => {
                    const status = order.status || order.status_raw || 'pending';
                    const statusLower = status.toLowerCase();
                    let badgeClass = 'pending';
                    if (statusLower.includes('confirm')) badgeClass = 'confirmed';
                    else if (statusLower.includes('reject')) badgeClass = 'rejected';
                    else if (statusLower.includes('cancel')) badgeClass = 'cancelled';
                    else if (statusLower.includes('draft')) badgeClass = 'draft';
                    else if (statusLower.includes('dispatch')) badgeClass = 'dispatched';
                    else if (statusLower.includes('deliver')) badgeClass = 'delivered';
                    
                    const statusDisplay = order.status_display || status.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
                    return `
            <option value="${order.order_id}" 
                        data-status="${status}"
                data-total="${order.total_amount}"
                data-date="${order.order_date}"
                        data-mr="${order.mr_name || ''}"
                        data-customer="${order.customer_name || ''}"
                        data-customer-id="${order.customer_id || ''}"
                        data-index="${index}">
                        ${order.order_id}${order.customer_name ? ' | ' + order.customer_name : ''} | [${statusDisplay}] | ${order.total_amount ? (order.total_amount.toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 0}) + ' MMK') : '0 MMK'} | ${order.order_date}
            </option>
                `;
                }).join('');
            
            // Restore selection if it still exists
            if (currentValue) {
                const option = orderSelect.querySelector(`option[value="${currentValue}"]`);
                if (option) {
            orderSelect.value = currentValue;
                }
            }
        }
        
        console.log('filterOrdersByAll: Filtered orders', {
            total: orders.length,
            filtered: filteredOrders.length,
            selectedMR: selectedMR,
            selectedDate: selectedDate,
            selectedStatus: selectedStatus
        });
    } catch (error) {
        console.error('filterOrdersByAll error:', error);
    }
}

// Filter orders by date, status, and customer (for MRs)
function filterOrdersByDateAndStatus() {
    try {
        const formContainer = document.querySelector('.order-selection-container');
        if (!formContainer || !formContainer._originalOrders) {
            console.warn('filterOrdersByDateAndStatus: Form container or orders not found');
            return;
        }
        
        const orderSelect = document.getElementById('orderSelect');
        const dateFilter = document.getElementById('dateFilter');
        const statusFilter = document.getElementById('statusFilter');
        const customerFilter = document.getElementById('customerFilter');
        
        if (!orderSelect || !dateFilter || !statusFilter) {
            console.warn('filterOrdersByDateAndStatus: Required elements not found', {
                orderSelect: !!orderSelect,
                dateFilter: !!dateFilter,
                statusFilter: !!statusFilter
            });
            return;
        }
    
    const orders = formContainer._originalOrders;
    const selectedDate = dateFilter.value;
    const selectedStatus = statusFilter.value;
    const selectedCustomer = customerFilter?.value || '';
    
    // Filter orders by date, status, and customer
    let filteredOrders = orders;
    if (selectedDate) {
        filteredOrders = filteredOrders.filter(order => order.order_date === selectedDate);
    }
    if (selectedStatus) {
        // Normalize status for comparison (handle both raw status and display status)
        filteredOrders = filteredOrders.filter(order => {
            const orderStatus = order.status || order.status_raw || '';
            const normalizedOrderStatus = orderStatus.toLowerCase().replace(/\s+/g, '_');
            const normalizedSelectedStatus = selectedStatus.toLowerCase().replace(/\s+/g, '_');
            return normalizedOrderStatus === normalizedSelectedStatus || orderStatus === selectedStatus;
        });
    }
    if (selectedCustomer) {
        filteredOrders = filteredOrders.filter(order => order.customer_name === selectedCustomer);
    }
    
    // Clear and repopulate the select
    orderSelect.innerHTML = '<option value="">-- Select Order --</option>';
    filteredOrders.forEach(order => {
        const option = document.createElement('option');
        option.value = order.order_id;
        option.setAttribute('data-status', order.status || order.status_raw);
        option.setAttribute('data-total', order.total_amount);
        option.setAttribute('data-date', order.order_date);
        option.setAttribute('data-customer', order.customer_name || '');
        option.setAttribute('data-customer-id', order.customer_id || '');
        option.textContent = `${order.order_id}${order.customer_name ? ' - ' + order.customer_name : ''} - ${order.status_display || (order.status || order.status_raw)} - ${order.total_amount ? (order.total_amount.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' MMK') : '0 MMK'} - ${order.order_date}`;
        orderSelect.appendChild(option);
    });
    
        // Reset selection
        orderSelect.value = '';
        
        console.log('filterOrdersByDateAndStatus: Filtered orders', {
            total: orders.length,
            filtered: filteredOrders.length,
            selectedDate: selectedDate,
            selectedStatus: selectedStatus,
            selectedCustomer: selectedCustomer
        });
    } catch (error) {
        console.error('filterOrdersByDateAndStatus error:', error);
    }
}

// Make functions globally accessible (do this before form creation)
window.filterOrdersByDateAndStatus = filterOrdersByDateAndStatus;
window.filterOrdersByAll = filterOrdersByAll;

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
            // For MRs, call API to get order details
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
                
                // Display order details for MR
                displayMROrderDetails(data.order);
            } else {
                throw new Error(data.error || 'Failed to fetch order details');
            }
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
// filterOrdersByAll and filterOrdersByDateAndStatus are already exposed above

// Display MR order details with enhanced tabular format
function displayMROrderDetails(order) {
    try {
        if (!order) {
            console.error('displayMROrderDetails: Order data is missing');
            addMessage('Error: Order data is missing. Please try again.', 'bot', 'error');
            return;
        }
        
        const messagesDiv = document.getElementById('chatMessages');
        if (!messagesDiv) {
            console.error('displayMROrderDetails: Chat messages container not found');
            return;
        }
        
        // Helper function to get status badge HTML
        function getStatusBadge(status) {
            const statusLower = (status || '').toLowerCase();
            let badgeClass = 'pending';
            let badgeText = status ? status.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase()) : 'Unknown';
            
            if (statusLower.includes('confirm')) badgeClass = 'confirmed';
            else if (statusLower.includes('reject')) badgeClass = 'rejected';
            else if (statusLower.includes('cancel')) badgeClass = 'cancelled';
            else if (statusLower.includes('draft')) badgeClass = 'draft';
            else if (statusLower.includes('dispatch')) badgeClass = 'dispatched';
            else if (statusLower.includes('deliver')) badgeClass = 'delivered';
            
            return `<span class="order-status-badge ${badgeClass}">${badgeText}</span>`;
        }
        
        // Get translations (declare once at function level)
        const t_func = (typeof t !== 'undefined') ? t : (key) => key;
        const orderDetailsLabel = t_func('labels.orderDetails');
        const orderInfoLabel = t_func('labels.orderInformation');
        const statusLabel = t_func('labels.status');
        const dateLabel = t_func('labels.date');
        const totalItemsLabel = t_func('labels.totalItems');
        const totalAmountLabel = t_func('labels.totalAmount');
        const customerLabel = t_func('labels.customer');
        const unitsLabel = t_func('labels.units');
        const productNameLabel = t_func('labels.productName');
        const quantityLabel = t_func('labels.quantity');
        const focLabel = t_func('labels.foc');
        const unitPriceLabel = t_func('labels.unitPrice');
        const totalPriceLabel = t_func('labels.totalPrice');
        
        // Helper function to format dates safely
        const formatOrFallback = (value) => {
            if (!value) return 'Not available';
            try {
                if (typeof value === 'string' && value.includes('T')) {
                    // ISO format
                    const date = new Date(value);
                    if (!isNaN(date.getTime())) {
                        return formatDate(value);
                    }
                }
                return formatDate(value);
            } catch (e) {
                return value;
            }
        };

        // Get timeline data
        const placedAt = order.placed_at || order.order_datetime || order.created_at || order.order_date;
        const confirmedAt = order.distributor_confirmed_at;
        const deliveredAt = order.delivered_at;
        const lastUpdatedAt = order.last_updated_at;
        
        // Check if order is cancelled
        const orderStatus = (order.status || order.status_display || '').toLowerCase();
        const isCancelled = orderStatus.includes('cancel');

        // Create main message container
        let message = `**📦 ${orderDetailsLabel} - ${order.order_id || 'Unknown'}**\n\n`;
        
        // Add pending order notice if applicable
        if (order.is_fulfilled_pending_order && order.pending_source_orders && order.pending_source_orders.length > 0) {
            message += `⚠️ **This order was created by fulfilling a previous pending order.**\n\n`;
            order.pending_source_orders.forEach(p => {
                message += `• Original Order ID: **${p.original_order_id || 'N/A'}** (placed on ${p.original_order_date ? formatOrFallback(p.original_order_date) : 'N/A'})\n`;
                message += `  - Product: ${p.product_name} (${p.product_code})\n`;
                message += `  - Requested Quantity: ${p.requested_quantity} units\n`;
            });
            message += `\n`;
        }
        
        // Add message first
        addMessage(message, 'bot');
        
        // Find the last bot message to add table and copy button
        const botMessages = messagesDiv.querySelectorAll('.message.bot');
        const lastBotMessage = botMessages[botMessages.length - 1];
        
        if (!lastBotMessage) {
            console.error('displayMROrderDetails: Could not find last bot message');
            return;
        }
        
        // Add copy button to the order title
        const messageBubble = lastBotMessage.querySelector('.message-bubble .bg-light');
        if (messageBubble) {
            const titleElement = messageBubble.querySelector('strong');
            if (titleElement && order.order_id) {
                const copyBtn = document.createElement('button');
                copyBtn.className = 'copy-btn';
                copyBtn.innerHTML = '<i class="fas fa-copy"></i>';
                copyBtn.title = 'Copy Order ID';
                copyBtn.onclick = function() { copyToClipboard(order.order_id, this); };
                copyBtn.style.cssText = 'margin-left: 8px; display: inline-flex; align-items: center; gap: 4px; padding: 4px 8px; background: rgba(37, 99, 235, 0.1); border: 1px solid rgba(37, 99, 235, 0.3); border-radius: 6px; color: #2563eb; font-size: 0.75rem; cursor: pointer; transition: all 0.2s;';
                titleElement.parentNode.insertBefore(copyBtn, titleElement.nextSibling);
            }
        }
        
        // Try multiple selectors to find the message bubble for table
        let messageBubbleForTable = lastBotMessage.querySelector('.message-bubble .bg-light');
        if (!messageBubbleForTable) {
            messageBubbleForTable = lastBotMessage.querySelector('.message-bubble');
        }
        if (!messageBubbleForTable) {
            messageBubbleForTable = lastBotMessage.querySelector('.bg-light');
        }
        if (!messageBubbleForTable) {
            messageBubbleForTable = lastBotMessage;
        }
        
        if (messageBubbleForTable) {
            // Add data attribute for print functionality
            messageBubbleForTable.setAttribute('data-order-id', order.order_id || '');
            
            // Create timeline and status table container (FIRST TABLE - at the top)
            const timelineTableContainer = document.createElement('div');
            timelineTableContainer.className = 'order-timeline-table mt-3 mb-3';
            timelineTableContainer.style.cssText = 'width: 100%; overflow-x: auto;';

            // Build timeline and status table
            let timelineTableHTML = `
                <div style="overflow-x: auto; width: 100%; max-width: 100%; box-sizing: border-box; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 15px;">
                    <table class="table table-bordered table-hover mb-0" style="font-size: 0.875rem; margin-bottom: 0; width: 100%; min-width: 700px; table-layout: auto;">
                        <thead style="background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%); color: white;">
                            <tr>
                                <th style="padding: 12px; border: 1px solid #1e40af; font-weight: 600; text-align: left; min-width: 180px;">Event</th>
                                <th style="padding: 12px; border: 1px solid #1e40af; font-weight: 600; text-align: left; min-width: 250px;">Date & Time</th>
                                <th style="padding: 12px; border: 1px solid #1e40af; font-weight: 600; text-align: center; min-width: 120px; white-space: nowrap;">Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr style="background-color: #f8f9fa;">
                                <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: 600; white-space: nowrap;">
                                    <i class="fas fa-shopping-cart me-2" style="color: #2563eb;"></i>Order Placed
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6;">
                                    ${placedAt ? formatOrFallback(placedAt) : 'Not available'}
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6; text-align: center; white-space: nowrap;">
                                    <span style="color: #10b981; font-weight: 600;">✓ Completed</span>
                                </td>
                            </tr>
                            ${!isCancelled ? `
                            <tr style="background-color: ${confirmedAt ? '#f0fdf4' : '#fff7ed'};">
                                <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: 600; white-space: nowrap;">
                                    <i class="fas fa-check-circle me-2" style="color: ${confirmedAt ? '#10b981' : '#f59e0b'};"></i>Dealer Confirmed
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6;">
                                    ${confirmedAt ? formatOrFallback(confirmedAt) : 'Not yet confirmed by dealer'}
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6; text-align: center; white-space: nowrap;">
                                    ${confirmedAt ? '<span style="color: #10b981; font-weight: 600;">✓ Completed</span>' : '<span style="color: #f59e0b; font-weight: 600;">⏳ Pending</span>'}
                                </td>
                            </tr>
                            <tr style="background-color: ${deliveredAt ? '#f0fdf4' : '#fff7ed'};">
                                <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: 600; white-space: nowrap;">
                                    <i class="fas fa-truck me-2" style="color: ${deliveredAt ? '#10b981' : '#f59e0b'};"></i>Delivered to Customer
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6;">
                                    ${deliveredAt ? formatOrFallback(deliveredAt) : 'Not yet delivered'}
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6; text-align: center; white-space: nowrap;">
                                    ${deliveredAt ? '<span style="color: #10b981; font-weight: 600;">✓ Completed</span>' : '<span style="color: #f59e0b; font-weight: 600;">⏳ Pending</span>'}
                                </td>
                            </tr>
                            ` : ''}
                            ${lastUpdatedAt ? `
                            <tr style="background-color: #f8f9fa;">
                                <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: 600; white-space: nowrap;">
                                    <i class="fas fa-clock me-2" style="color: #6b7280;"></i>Last Updated
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6;">
                                    ${formatOrFallback(lastUpdatedAt)}
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6; text-align: center; white-space: nowrap;">
                                    <span style="color: #6b7280;">-</span>
                                </td>
                            </tr>
                            ` : ''}
                        </tbody>
                    </table>
                </div>
            `;

            timelineTableContainer.innerHTML = timelineTableHTML;
            messageBubbleForTable.appendChild(timelineTableContainer);

            // Create order information table (SECOND TABLE)
            const infoTableContainer = document.createElement('div');
            infoTableContainer.className = 'order-info-table mt-3 mb-3';
            infoTableContainer.style.cssText = 'width: 100%; overflow-x: auto;';

            let infoTableHTML = `
                <div style="overflow-x: auto; width: 100%; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 15px;">
                    <table class="table table-bordered table-hover mb-0" style="font-size: 0.875rem; margin-bottom: 0; width: 100%; min-width: 500px;">
                        <thead style="background: linear-gradient(135deg, #059669 0%, #047857 100%); color: white;">
                            <tr>
                                <th style="padding: 12px; border: 1px solid #065f46; font-weight: 600; text-align: left; width: 40%;">Information</th>
                                <th style="padding: 12px; border: 1px solid #065f46; font-weight: 600; text-align: left; width: 60%;">Details</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: 600;">
                                    <i class="fas fa-info-circle me-2" style="color: #059669;"></i>${statusLabel}
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6;">
                                    ${getStatusBadge(order.status || order.status_display)}
                                </td>
                            </tr>
                            ${order.order_stage ? `
                            <tr>
                                <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: 600;">
                                    <i class="fas fa-layer-group me-2" style="color: #059669;"></i>Order Stage
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6;">
                                    ${order.order_stage}
                                </td>
                            </tr>
                            ` : ''}
                            <tr>
                                <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: 600;">
                                    <i class="fas fa-calendar me-2" style="color: #059669;"></i>${dateLabel}
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6;">
                                    ${order.order_datetime || order.order_date || 'N/A'}
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: 600;">
                                    <i class="fas fa-boxes me-2" style="color: #059669;"></i>${totalItemsLabel}
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6;">
                                    ${order.total_items || 0} ${unitsLabel}
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: 600;">
                                    <i class="fas fa-money-bill-wave me-2" style="color: #059669;"></i>${totalAmountLabel}
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6;">
                                    <strong style="color: #059669;">${(order.total_amount || 0).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})} MMK</strong>
                                </td>
                            </tr>
                            ${order.area ? `
                            <tr>
                                <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: 600;">
                                    <i class="fas fa-map-marker-alt me-2" style="color: #059669;"></i>Area
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6;">
                                    ${order.area}
                                </td>
                            </tr>
                            ` : ''}
                            ${order.customer_name ? `
                            <tr>
                                <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: 600;">
                                    <i class="fas fa-user me-2" style="color: #059669;"></i>${customerLabel}
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6;">
                                    ${order.customer_name}
                                </td>
                            </tr>
                            ` : ''}
                        </tbody>
                    </table>
                </div>
            `;

            infoTableContainer.innerHTML = infoTableHTML;
            messageBubbleForTable.appendChild(infoTableContainer);
            
            // Create items table container (THIRD TABLE - product items)
            const tableContainer = document.createElement('div');
            tableContainer.className = 'order-items-table mt-3 mb-3';
            tableContainer.style.cssText = 'width: 100%; overflow-x: auto;';
            
            // Build items table
            let tableHTML = `
                <div style="overflow-x: auto; width: 100%; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    <table class="table table-bordered table-hover mb-0" style="font-size: 0.875rem; margin-bottom: 0; width: 100%; min-width: 500px;">
                        <thead style="background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%); color: white;">
                            <tr>
                                <th style="padding: 12px; border: 1px solid #1e40af; font-weight: 600; text-align: left;">${productNameLabel}</th>
                                <th style="padding: 12px; border: 1px solid #1e40af; font-weight: 600; text-align: center;">${quantityLabel}</th>
                                <th style="padding: 12px; border: 1px solid #1e40af; font-weight: 600; text-align: center;">${focLabel}</th>
                                <th style="padding: 12px; border: 1px solid #1e40af; font-weight: 600; text-align: right;">${unitPriceLabel}</th>
                                <th style="padding: 12px; border: 1px solid #1e40af; font-weight: 600; text-align: right;">${totalPriceLabel}</th>
                            </tr>
                        </thead>
                        <tbody>
            `;
            
            if (order.items && order.items.length > 0) {
                order.items.forEach((item, index) => {
                    const rowColor = index % 2 === 0 ? '#f8f9fa' : '#ffffff';
                    const focDisplay = (item.free_quantity || 0) > 0 
                        ? `<span style="color: #10b981; font-weight: 600;">+${item.free_quantity}</span>` 
                        : '<span style="color: #6b7280;">-</span>';
                    
                    tableHTML += `
                        <tr style="background-color: ${rowColor};">
                            <td style="padding: 12px; border: 1px solid #dee2e6;">
                                <strong>${item.product_name || 'Unknown Product'}</strong>
                            </td>
                            <td style="padding: 12px; border: 1px solid #dee2e6; text-align: center;">
                                ${item.quantity || 0} ${unitsLabel}
                            </td>
                            <td style="padding: 12px; border: 1px solid #dee2e6; text-align: center;">
                                ${focDisplay}
                            </td>
                            <td style="padding: 12px; border: 1px solid #dee2e6; text-align: right;">
                                ${(item.unit_price || 0).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})} MMK
                            </td>
                            <td style="padding: 12px; border: 1px solid #dee2e6; text-align: right; font-weight: 600;">
                                ${(item.total_price || 0).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})} MMK
                            </td>
                        </tr>
                    `;
                });
            } else {
                tableHTML += `
                    <tr>
                        <td colspan="5" style="padding: 20px; text-align: center; color: #6b7280;">
                            No items found in this order.
                        </td>
                    </tr>
                `;
            }
            
            // Add total rows (Tax and Grand Total)
            const subtotal = order.subtotal || 0;
            const taxAmount = order.tax_amount || 0;
            const grandTotal = order.total_amount || 0;
            const taxRate = order.tax_rate || 0.05;
            const taxPercent = (taxRate * 100).toFixed(0);
            const taxLabel = `${t_func('labels.tax') || 'Tax'} (${taxPercent}%)`;
            
            tableHTML += `
                        </tbody>
                        <tfoot style="background-color: #f1f5f9; border-top: 2px solid #2563eb;">`;
            
            // Add Tax row if tax amount exists
            if (taxAmount > 0 && subtotal > 0) {
                tableHTML += `
                            <tr>
                                <td colspan="4" style="padding: 10px; border: 1px solid #dee2e6; text-align: right; font-weight: 600; font-size: 0.95rem;">
                                    <strong>${taxLabel}:</strong>
                                </td>
                                <td style="padding: 10px; border: 1px solid #dee2e6; text-align: right; font-weight: 600; font-size: 0.95rem;">
                                    ${taxAmount.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})} MMK
                                </td>
                            </tr>`;
            }
            
            // Add Grand Total row
            tableHTML += `
                            <tr>
                                <td colspan="4" style="padding: 12px; border: 1px solid #dee2e6; text-align: right; font-weight: 700; font-size: 1rem;">
                                    <strong>${t_func('labels.grandTotal')}:</strong>
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6; text-align: right; font-weight: 700; font-size: 1rem; color: #2563eb;">
                                    <strong>${grandTotal.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})} MMK</strong>
                                </td>
                            </tr>
                        </tfoot>
                    </table>
                </div>
            `;
            
            tableContainer.innerHTML = tableHTML;
            messageBubbleForTable.appendChild(tableContainer);
        }
        
        // Add action buttons based on order status
        const actionButtons = [];
        if (order.status === 'pending' || order.status === 'draft') {
            actionButtons.push({
                         text: t_func('buttons.cancelOrder'),
                action: 'cancel_order',
                style: 'danger',
                order_id: order.order_id
            });
        }
        actionButtons.push(
                     { text: t_func('buttons.print'), action: 'print_order', order_id: order.order_id, onclick: `printOrder('${order.order_id}')` },
                     { text: t_func('buttons.viewAllOrders'), action: 'track_order' },
                     { text: t_func('buttons.backToHome'), action: 'home' }
        );
        showActionButtons(actionButtons);
        
        // Scroll to bottom
        messagesDiv.scrollTo({
            top: messagesDiv.scrollHeight,
            behavior: 'smooth'
        });
    } catch (error) {
        console.error('displayMROrderDetails error:', error);
        addMessage('Error displaying order details. Please try again.', 'bot', 'error');
    }
}

// Display distributor order details with confirm/reject buttons and edit options
function displayDistributorOrderDetails(order) {
    try {
        const messagesDiv = document.getElementById('chatMessages');
        if (!messagesDiv) {
            console.error('displayDistributorOrderDetails: Chat messages container not found');
            return;
        }
        
        // Helper function to get status badge HTML
        function getStatusBadge(status) {
            const statusLower = (status || '').toLowerCase();
            let badgeClass = 'pending';
            let badgeText = status ? status.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase()) : 'Unknown';
            
            if (statusLower.includes('confirm')) badgeClass = 'confirmed';
            else if (statusLower.includes('reject')) badgeClass = 'rejected';
            else if (statusLower.includes('cancel')) badgeClass = 'cancelled';
            else if (statusLower.includes('draft')) badgeClass = 'draft';
            else if (statusLower.includes('dispatch')) badgeClass = 'dispatched';
            else if (statusLower.includes('deliver')) badgeClass = 'delivered';
            
            return `<span class="order-status-badge ${badgeClass}">${badgeText}</span>`;
        }
        
        // Helper function to format dates safely
        const formatOrFallback = (value) => {
            if (!value) return 'Not available';
            try {
                if (typeof value === 'string' && value.includes('T')) {
                    // ISO format
                    const date = new Date(value);
                    if (!isNaN(date.getTime())) {
                        return formatDate(value);
                    }
                }
                return formatDate(value);
            } catch (e) {
                return value;
            }
        };
        
        // Get translations
        const t_func = (typeof t !== 'undefined') ? t : (key) => key;
        const orderDetailsLabel = t_func('labels.orderDetails');
        const statusLabel = t_func('labels.status');
        const dateLabel = t_func('labels.date');
        const totalItemsLabel = t_func('labels.totalItems');
        const totalAmountLabel = t_func('labels.totalAmount');
        const customerLabel = t_func('labels.customer');
        const unitsLabel = t_func('labels.units');
        const productNameLabel = t_func('labels.productName');
        const quantityLabel = t_func('labels.quantity');
        const focLabel = t_func('labels.foc');
        const unitPriceLabel = t_func('labels.unitPrice');
        const totalPriceLabel = t_func('labels.totalPrice');
        
        // Get timeline data
        const placedAt = order.placed_at || order.order_datetime || order.created_at || order.order_date;
        const confirmedAt = order.distributor_confirmed_at;
        const deliveredAt = order.delivered_at;
        const lastUpdatedAt = order.last_updated_at;
        
        // Check if order is cancelled
        const orderStatus = (order.status || order.status_display || '').toLowerCase();
        const isCancelled = orderStatus.includes('cancel');
        
        // Build initial message
        let message = `**📦 ${orderDetailsLabel} - ${order.order_id || 'Unknown'}**\n\n`;
        
        // Add pending order notice if applicable
        if (order.is_fulfilled_pending_order && order.pending_source_orders && order.pending_source_orders.length > 0) {
            message += `⚠️ **This order was created by fulfilling a previous pending order.**\n\n`;
            order.pending_source_orders.forEach(p => {
                message += `• Original Order ID: **${p.original_order_id || 'N/A'}** (placed on ${p.original_order_date ? formatOrFallback(p.original_order_date) : 'N/A'})\n`;
                message += `  - Product: ${p.product_name} (${p.product_code})\n`;
                message += `  - Requested Quantity: ${p.requested_quantity} units\n`;
            });
            message += `\n`;
        }
        
        // Add message first
        addMessage(message, 'bot');
        
        // Find the last bot message to add tables
        const botMessages = messagesDiv.querySelectorAll('.message.bot');
        const lastBotMessage = botMessages[botMessages.length - 1];
        
        if (!lastBotMessage) {
            console.error('displayDistributorOrderDetails: Could not find last bot message');
            return;
        }
        
        // Add copy button to the order title
        const messageBubble = lastBotMessage.querySelector('.message-bubble .bg-light');
        if (messageBubble) {
            const titleElement = messageBubble.querySelector('strong');
            if (titleElement && order.order_id) {
                const copyBtn = document.createElement('button');
                copyBtn.className = 'copy-btn';
                copyBtn.innerHTML = '<i class="fas fa-copy"></i>';
                copyBtn.title = 'Copy Order ID';
                copyBtn.onclick = function() { copyToClipboard(order.order_id, this); };
                copyBtn.style.cssText = 'margin-left: 8px; display: inline-flex; align-items: center; gap: 4px; padding: 4px 8px; background: rgba(37, 99, 235, 0.1); border: 1px solid rgba(37, 99, 235, 0.3); border-radius: 6px; color: #2563eb; font-size: 0.75rem; cursor: pointer; transition: all 0.2s;';
                titleElement.parentNode.insertBefore(copyBtn, titleElement.nextSibling);
            }
        }
        
        // Find message bubble for table
        let messageBubbleForTable = lastBotMessage.querySelector('.message-bubble .bg-light');
        if (!messageBubbleForTable) {
            messageBubbleForTable = lastBotMessage.querySelector('.message-bubble');
        }
        if (!messageBubbleForTable) {
            messageBubbleForTable = lastBotMessage.querySelector('.bg-light');
        }
        if (!messageBubbleForTable) {
            messageBubbleForTable = lastBotMessage;
        }
        
        if (messageBubbleForTable) {
            // Add data attribute for print functionality
            messageBubbleForTable.setAttribute('data-order-id', order.order_id || '');
            
            // Create timeline and status table container (FIRST TABLE - at the top)
            const timelineTableContainer = document.createElement('div');
            timelineTableContainer.className = 'order-timeline-table mt-3 mb-3';
            timelineTableContainer.style.cssText = 'width: 100%; overflow-x: auto;';

            // Build timeline and status table
            let timelineTableHTML = `
                <div style="overflow-x: auto; width: 100%; max-width: 100%; box-sizing: border-box; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 15px;">
                    <table class="table table-bordered table-hover mb-0" style="font-size: 0.875rem; margin-bottom: 0; width: 100%; min-width: 700px; table-layout: auto;">
                        <thead style="background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%); color: white;">
                            <tr>
                                <th style="padding: 12px; border: 1px solid #1e40af; font-weight: 600; text-align: left; min-width: 180px;">Event</th>
                                <th style="padding: 12px; border: 1px solid #1e40af; font-weight: 600; text-align: left; min-width: 250px;">Date & Time</th>
                                <th style="padding: 12px; border: 1px solid #1e40af; font-weight: 600; text-align: center; min-width: 120px; white-space: nowrap;">Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr style="background-color: #f8f9fa;">
                                <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: 600; white-space: nowrap;">
                                    <i class="fas fa-shopping-cart me-2" style="color: #2563eb;"></i>Order Placed
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6;">
                                    ${placedAt ? formatOrFallback(placedAt) : 'Not available'}
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6; text-align: center; white-space: nowrap;">
                                    <span style="color: #10b981; font-weight: 600;">✓ Completed</span>
                                </td>
                            </tr>
                            ${!isCancelled ? `
                            <tr style="background-color: ${confirmedAt ? '#f0fdf4' : '#fff7ed'};">
                                <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: 600; white-space: nowrap;">
                                    <i class="fas fa-check-circle me-2" style="color: ${confirmedAt ? '#10b981' : '#f59e0b'};"></i>Dealer Confirmed
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6;">
                                    ${confirmedAt ? formatOrFallback(confirmedAt) : 'Not yet confirmed by dealer'}
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6; text-align: center; white-space: nowrap;">
                                    ${confirmedAt ? '<span style="color: #10b981; font-weight: 600;">✓ Completed</span>' : '<span style="color: #f59e0b; font-weight: 600;">⏳ Pending</span>'}
                                </td>
                            </tr>
                            <tr style="background-color: ${deliveredAt ? '#f0fdf4' : '#fff7ed'};">
                                <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: 600; white-space: nowrap;">
                                    <i class="fas fa-truck me-2" style="color: ${deliveredAt ? '#10b981' : '#f59e0b'};"></i>Delivered to Customer
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6;">
                                    ${deliveredAt ? formatOrFallback(deliveredAt) : 'Not yet delivered'}
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6; text-align: center; white-space: nowrap;">
                                    ${deliveredAt ? '<span style="color: #10b981; font-weight: 600;">✓ Completed</span>' : '<span style="color: #f59e0b; font-weight: 600;">⏳ Pending</span>'}
                                </td>
                            </tr>
                            ` : ''}
                            ${lastUpdatedAt ? `
                            <tr style="background-color: #f8f9fa;">
                                <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: 600; white-space: nowrap;">
                                    <i class="fas fa-clock me-2" style="color: #6b7280;"></i>Last Updated
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6;">
                                    ${formatOrFallback(lastUpdatedAt)}
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6; text-align: center; white-space: nowrap;">
                                    <span style="color: #6b7280;">-</span>
                                </td>
                            </tr>
                            ` : ''}
                        </tbody>
                    </table>
                </div>
            `;

            timelineTableContainer.innerHTML = timelineTableHTML;
            messageBubbleForTable.appendChild(timelineTableContainer);

            // Create order information table (SECOND TABLE)
            const infoTableContainer = document.createElement('div');
            infoTableContainer.className = 'order-info-table mt-3 mb-3';
            infoTableContainer.style.cssText = 'width: 100%; overflow-x: auto;';

            let infoTableHTML = `
                <div style="overflow-x: auto; width: 100%; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 15px;">
                    <table class="table table-bordered table-hover mb-0" style="font-size: 0.875rem; margin-bottom: 0; width: 100%; min-width: 500px;">
                        <thead style="background: linear-gradient(135deg, #059669 0%, #047857 100%); color: white;">
                            <tr>
                                <th style="padding: 12px; border: 1px solid #065f46; font-weight: 600; text-align: left; width: 40%;">Information</th>
                                <th style="padding: 12px; border: 1px solid #065f46; font-weight: 600; text-align: left; width: 60%;">Details</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: 600;">
                                    <i class="fas fa-info-circle me-2" style="color: #059669;"></i>${statusLabel}
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6;">
                                    ${getStatusBadge(order.status || order.status_display)}
                                </td>
                            </tr>
                            ${order.order_stage ? `
                            <tr>
                                <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: 600;">
                                    <i class="fas fa-layer-group me-2" style="color: #059669;"></i>Order Stage
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6;">
                                    ${order.order_stage}
                                </td>
                            </tr>
                            ` : ''}
                            <tr>
                                <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: 600;">
                                    <i class="fas fa-calendar me-2" style="color: #059669;"></i>${dateLabel}
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6;">
                                    ${order.order_datetime || order.order_date || 'N/A'}
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: 600;">
                                    <i class="fas fa-user-md me-2" style="color: #059669;"></i>MR Name
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6;">
                                    ${order.mr_name || 'N/A'}
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: 600;">
                                    <i class="fas fa-envelope me-2" style="color: #059669;"></i>MR Contact
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6;">
                                    ${order.mr_email || 'N/A'}
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: 600;">
                                    <i class="fas fa-phone me-2" style="color: #059669;"></i>MR Phone
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6;">
                                    ${order.mr_phone || 'N/A'}
                                </td>
                            </tr>
                            ${order.area ? `
                            <tr>
                                <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: 600;">
                                    <i class="fas fa-map-marker-alt me-2" style="color: #059669;"></i>Area
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6;">
                                    ${order.area}
                                </td>
                            </tr>
                            ` : ''}
                            ${order.customer_name ? `
                            <tr>
                                <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: 600;">
                                    <i class="fas fa-user me-2" style="color: #059669;"></i>${customerLabel}
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6;">
                                    ${order.customer_name}
                                </td>
                            </tr>
                            ` : ''}
                            ${order.delivery_partner_name ? `
                            <tr>
                                <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: 600;">
                                    <i class="fas fa-truck me-2" style="color: #059669;"></i>Delivery Partner
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6;">
                                    <strong>${order.delivery_partner_name}</strong>${order.delivery_partner_unique_id ? ` (${order.delivery_partner_unique_id})` : ''}
                                    ${order.delivery_partner_email ? `<br><small style="color: #6b7280;"><i class="fas fa-envelope me-1"></i>${order.delivery_partner_email}</small>` : ''}
                                    ${order.delivery_partner_phone ? `<br><small style="color: #6b7280;"><i class="fas fa-phone me-1"></i>${order.delivery_partner_phone}</small>` : ''}
                                </td>
                            </tr>
                            ` : ''}
                            <tr>
                                <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: 600;">
                                    <i class="fas fa-boxes me-2" style="color: #059669;"></i>${totalItemsLabel}
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6;">
                                    ${order.total_items || 0} ${unitsLabel}
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: 600;">
                                    <i class="fas fa-money-bill-wave me-2" style="color: #059669;"></i>${totalAmountLabel}
                                </td>
                                <td style="padding: 12px; border: 1px solid #dee2e6;">
                                    <strong style="color: #059669;">${(order.total_amount || 0).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})} MMK</strong>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            `;

            infoTableContainer.innerHTML = infoTableHTML;
            messageBubbleForTable.appendChild(infoTableContainer);
            
            // Add items table if items exist (THIRD TABLE)
            if (order.items && order.items.length > 0) {
                const itemsTableContainer = document.createElement('div');
                itemsTableContainer.className = 'order-items-table mt-3 mb-3';
                itemsTableContainer.style.cssText = 'width: 100%; overflow-x: auto;';

                let itemsTableHTML = `
                    <div style="overflow-x: auto; width: 100%; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                        <table class="table table-bordered table-hover mb-0" style="font-size: 0.875rem; margin-bottom: 0; width: 100%; min-width: 500px;">
                            <thead style="background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%); color: white;">
                                <tr>
                                    <th style="padding: 12px; border: 1px solid #1e40af; font-weight: 600; text-align: left;">${productNameLabel}</th>
                                    <th style="padding: 12px; border: 1px solid #1e40af; font-weight: 600; text-align: center;">${quantityLabel}</th>
                                    <th style="padding: 12px; border: 1px solid #1e40af; font-weight: 600; text-align: center;">${focLabel}</th>
                                    <th style="padding: 12px; border: 1px solid #1e40af; font-weight: 600; text-align: right;">${unitPriceLabel}</th>
                                    <th style="padding: 12px; border: 1px solid #1e40af; font-weight: 600; text-align: right;">${totalPriceLabel}</th>
                                </tr>
                            </thead>
                            <tbody>
                `;

                order.items.forEach((item, index) => {
                    const rowColor = index % 2 === 0 ? '#f8f9fa' : '#ffffff';
                    const focDisplay = (item.free_quantity || 0) > 0 
                        ? `<span style="color: #10b981; font-weight: 600;">+${item.free_quantity}</span>` 
                        : '<span style="color: #6b7280;">-</span>';
                    
                    itemsTableHTML += `
                        <tr style="background-color: ${rowColor};">
                            <td style="padding: 12px; border: 1px solid #dee2e6;">
                                <strong>${item.product_name || 'Unknown Product'}</strong>
                            </td>
                            <td style="padding: 12px; border: 1px solid #dee2e6; text-align: center;">
                                ${item.quantity || 0} ${unitsLabel}
                            </td>
                            <td style="padding: 12px; border: 1px solid #dee2e6; text-align: center;">
                                ${focDisplay}
                            </td>
                            <td style="padding: 12px; border: 1px solid #dee2e6; text-align: right;">
                                ${(item.unit_price || 0).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})} MMK
                            </td>
                            <td style="padding: 12px; border: 1px solid #dee2e6; text-align: right; font-weight: 600;">
                                ${(item.total_price || 0).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})} MMK
                            </td>
                        </tr>
                    `;
                });
                
                // Add total rows (Tax and Grand Total)
                const subtotal = order.subtotal || 0;
                const taxAmount = order.tax_amount || 0;
                const grandTotal = order.total_amount || 0;
                const taxRate = order.tax_rate || 0.05;
                const taxPercent = (taxRate * 100).toFixed(0);
                const taxLabel = `${t_func('labels.tax') || 'Tax'} (${taxPercent}%)`;
                
                itemsTableHTML += `
                            </tbody>
                            <tfoot style="background-color: #f1f5f9; border-top: 2px solid #2563eb;">`;
                
                // Add Tax row if tax amount exists
                if (taxAmount > 0 && subtotal > 0) {
                    itemsTableHTML += `
                                <tr>
                                    <td colspan="4" style="padding: 10px; border: 1px solid #dee2e6; text-align: right; font-weight: 600; font-size: 0.95rem;">
                                        <strong>${taxLabel}:</strong>
                                    </td>
                                    <td style="padding: 10px; border: 1px solid #dee2e6; text-align: right; font-weight: 600; font-size: 0.95rem;">
                                        ${taxAmount.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})} MMK
                                    </td>
                                </tr>`;
                }
                
                // Add Grand Total row
                itemsTableHTML += `
                                <tr>
                                    <td colspan="4" style="padding: 12px; border: 1px solid #dee2e6; text-align: right; font-weight: 700; font-size: 1rem;">
                                        <strong>${t_func('labels.grandTotal')}:</strong>
                                    </td>
                                    <td style="padding: 12px; border: 1px solid #dee2e6; text-align: right; font-weight: 700; font-size: 1rem; color: #2563eb;">
                                        <strong>${grandTotal.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})} MMK</strong>
                                    </td>
                                </tr>
                            </tfoot>
                        </table>
                    </div>
                `;

                itemsTableContainer.innerHTML = itemsTableHTML;
                messageBubbleForTable.appendChild(itemsTableContainer);
            }
        }
        
        // Now add the editable form if order can be confirmed
        if (messageBubbleForTable && order.can_confirm) {
            // Create editable form for order items
            const editFormContainer = document.createElement('div');
            editFormContainer.className = 'order-edit-form mt-3 mb-3';
            editFormContainer.style.cssText = 'width: 100%; animation: slideInFromBottom 0.3s ease-out;';
            
            // Get translations for form
            const t_func = (typeof t !== 'undefined') ? t : (key) => key;
            const editOrderItemsLabel = t_func('labels.editOrderItems');
            const quantityLabel = t_func('labels.quantity');
            const lotNumberLabel = t_func('labels.lotNumber');
            const expiryDateLabel = t_func('labels.expiryDate');
            const reasonLabel = t_func('labels.reason');
            const confirmOrderText = t_func('buttons.confirmOrder');
            const rejectOrderText = t_func('buttons.rejectOrder');
            
            let formHTML = `
                <div class="card border-0 shadow-sm" style="background: rgba(255, 255, 255, 0.98); border-radius: 12px; padding: 20px;">
                    <h6 class="mb-3" style="color: #2563eb; font-weight: 600;">
                        <i class="fas fa-edit me-2"></i>${editOrderItemsLabel}
                    </h6>
                    <p class="text-muted mb-3" style="font-size: 0.875rem;">
                        <i class="fas fa-info-circle me-1"></i>
                        ${t_func('labels.adjustQuantitiesInfo')}
                    </p>
                    <form id="orderEditForm_${order.order_id}">
            `;
            
            // Add delivery partner selection
            formHTML += `
                        <div class="mb-3" style="background: #eff6ff; padding: 15px; border-radius: 8px; border-left: 4px solid #3b82f6;">
                            <label for="delivery_partner_${order.order_id}" class="form-label" style="font-weight: 600; color: #1e40af;">
                                <i class="fas fa-truck me-2"></i>Assign Delivery Partner <span style="color: #dc2626;">*</span>
                            </label>
                            <select class="form-select" id="delivery_partner_${order.order_id}" name="delivery_partner_id" required
                                    style="border-radius: 8px; border: 2px solid #bfdbfe; padding: 10px;">
                                <option value="">-- Select Delivery Partner --</option>
                            </select>
                            <small class="text-muted" style="font-size: 0.75rem;">
                                <i class="fas fa-info-circle me-1"></i>Select a delivery partner to assign this order for delivery
                            </small>
                        </div>
            `;
            
            // Add editable fields for each item
            order.items.forEach((item, index) => {
                const itemId = item.id || item.item_id || index; // Use item.id if available, fallback to index
                const originalQty = item.quantity || 0;  // Paid quantity
                const focQty = item.free_quantity || 0;  // FOC quantity
                
                // Get lot number from database if available
                const lotNumber = item.lot_number || '';
                
                // Get expiry date from database if available, otherwise use today
                const expiryDate = item.expiry_date || new Date().toISOString().split('T')[0];
                
                // Format quantity label correctly: show paid + FOC separately
                let quantityLabelText = `${quantityLabel}`;
                if (focQty > 0) {
                    quantityLabelText += ` (Ordered: ${originalQty} + ${focQty} FOC)`;
                } else {
                    quantityLabelText += ` (Ordered: ${originalQty})`;
                }
                
                formHTML += `
                    <div class="order-item-edit mb-4 p-3" style="background: #f8f9fa; border-radius: 8px; border-left: 4px solid #2563eb;">
                        <h6 style="color: #1e40af; margin-bottom: 15px; font-weight: 600;">
                            <i class="fas fa-pills me-2"></i>${item.product_name}
                        </h6>
                        <div class="d-flex flex-column gap-3">
                            <div>
                                <label class="form-label" style="font-weight: 500; font-size: 0.875rem;">
                                    <i class="fas fa-box me-1"></i>${quantityLabelText}
                                </label>
                                <input type="number" 
                                    class="form-control form-control-sm" 
                                    id="qty_${itemId}" 
                                    name="quantity_${itemId}"
                                    value="${originalQty}"
                                    min="0"
                                    style="border-radius: 6px; border: 1.5px solid #e5e7eb;"
                                    placeholder="${t_func('labels.enterQuantity')}">
                                <small class="text-muted" style="font-size: 0.75rem;">
                                    ${t_func('labels.adjustQuantityInfo')}
                                </small>
                            </div>
                            <div>
                                <label class="form-label" style="font-weight: 500; font-size: 0.875rem;">
                                    <i class="fas fa-barcode me-1"></i>${lotNumberLabel} (Optional)
                                </label>
                                <input type="text" 
                                    class="form-control form-control-sm" 
                                    id="lot_${itemId}" 
                                    name="lot_number_${itemId}"
                                    value="${lotNumber}"
                                    style="border-radius: 6px; border: 1.5px solid #e5e7eb;"
                                    placeholder="${t_func('labels.enterLotNumber')}">
                                <small class="text-muted" style="font-size: 0.75rem;">
                                    ${t_func('labels.lotNumberInfo')}${lotNumber ? ' ' + t_func('labels.fromDatabase') : ''}
                                </small>
                            </div>
                            <div>
                                <label class="form-label" style="font-weight: 500; font-size: 0.875rem;">
                                    <i class="fas fa-calendar-alt me-1"></i>${expiryDateLabel}
                                </label>
                                <input type="date" 
                                    class="form-control form-control-sm" 
                                    id="expiry_${itemId}" 
                                    name="expiry_date_${itemId}"
                                    value="${expiryDate}"
                                    style="border-radius: 6px; border: 1.5px solid #e5e7eb;"
                                    min="${new Date().toISOString().split('T')[0]}">
                                <small class="text-muted" style="font-size: 0.75rem;">
                                    ${t_func('labels.expiryDateInfo')}${item.expiry_date ? ' ' + t_func('labels.fromDatabase') : ''}
                                </small>
                            </div>
                            <div>
                                <label class="form-label" style="font-weight: 500; font-size: 0.875rem;">
                                    <i class="fas fa-comment-alt me-1"></i>${reasonLabel} (Optional)
                                </label>
                                <input type="text" 
                                    class="form-control form-control-sm" 
                                    id="reason_${itemId}" 
                                    name="reason_${itemId}"
                                    style="border-radius: 6px; border: 1.5px solid #e5e7eb;"
                                    placeholder="${t_func('labels.reasonForAdjustment')}">
                                <small class="text-muted" style="font-size: 0.75rem;">
                                    ${t_func('labels.reasonInfo')}
                                </small>
                            </div>
                        </div>
                        <input type="hidden" name="item_id_${itemId}" value="${itemId}">
                    </div>
                `;
            });
            
            formHTML += `
                    </form>
                    <div class="d-flex gap-2 mt-3">
                        <button type="button" 
                            class="btn btn-success flex-grow-1" 
                            onclick="confirmOrderWithEdits('${order.order_id}')"
                            style="border-radius: 8px; padding: 10px; font-weight: 600;">
                            <i class="fas fa-check-circle me-2"></i>${confirmOrderText}
                        </button>
                        <button type="button" 
                            class="btn btn-outline-danger" 
                            onclick="rejectOrderAction('${order.order_id}')"
                            style="border-radius: 8px; padding: 10px; font-weight: 600;">
                            <i class="fas fa-times-circle me-2"></i>${rejectOrderText}
                        </button>
                    </div>
                </div>
            `;
            
            editFormContainer.innerHTML = formHTML;
            messageBubbleForTable.appendChild(editFormContainer);
            
            // Load delivery partners for this area after form is added to DOM
            // Use setTimeout to ensure DOM element exists
            setTimeout(() => {
                loadDeliveryPartners(order.order_id);
            }, 100);
        }
        
        // Add action buttons
        if (order.can_confirm) {
            // Buttons are in the form, but add backup buttons
            const actionButtons = [
                {
                    text: t_func('buttons.viewAllOrders'),
                    action: 'track_order'
                }
            ];
            showActionButtons(actionButtons);
        } else {
            const actionButtons = [
                {
                    text: t_func('buttons.viewAllOrders'),
                    action: 'track_order'
                },
                {
                    text: t_func('buttons.backToHome'),
                    action: 'home'
                }
            ];
            showActionButtons(actionButtons);
        }
        
        // Scroll to bottom
        messagesDiv.scrollTo({
            top: messagesDiv.scrollHeight,
            behavior: 'smooth'
        });
    } catch (error) {
        console.error('displayDistributorOrderDetails error:', error);
        addMessage('Error displaying order details. Please try again.', 'bot', 'error');
    }
}

// Confirm order by distributor with edits
async function confirmOrderWithEdits(orderId) {
    try {
        // Collect item edits from the form
        const form = document.getElementById(`orderEditForm_${orderId}`);
        if (!form) {
            // Fallback to simple confirmation if form not found
            return confirmOrderAction(orderId);
        }
        
        // Use shared function to collect edits consistently
        const itemEdits = collectItemEditsFromForm(form);
        
        if (!confirm(`Are you sure you want to confirm order ${orderId}${Object.keys(itemEdits).length > 0 ? ' with the specified adjustments' : ''}?`)) {
            return;
        }
        
        // Disable form during submission
        const submitBtn = form.closest('.card').querySelector('button[onclick*="confirmOrderWithEdits"]');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Confirming...';
        }
        
        // Get delivery partner selection
        const deliveryPartnerSelect = document.getElementById(`delivery_partner_${orderId}`);
        const deliveryPartnerId = deliveryPartnerSelect ? deliveryPartnerSelect.value : null;
        
        if (!deliveryPartnerId) {
            addMessage('❌ Please select a delivery partner before confirming the order.', 'bot', 'error');
            if (submitBtn) {
                submitBtn.disabled = false;
                const t_func = (typeof t !== 'undefined') ? t : (key) => key;
                submitBtn.innerHTML = `<i class="fas fa-check-circle me-2"></i>${t_func('buttons.confirmOrder')}`;
            }
            return;
        }
        
        const response = await fetch('/enhanced-chat/confirm_order_action', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                order_id: orderId,
                item_edits: itemEdits,
                delivery_partner_id: deliveryPartnerId
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            let successMessage = `✅ **Order Confirmed Successfully!**\n\n${data.message}\n\nThe stock has been moved from blocked to out_for_delivery, and the delivery partner has been notified via email.`;
            
            // Show notifications if any
            if (data.notifications && data.notifications.length > 0) {
                successMessage += `\n\n**📋 Notifications:**\n`;
                data.notifications.forEach(notif => {
                    successMessage += `• ${notif}\n`;
                });
            }
            
            addMessage(successMessage, 'bot');
            
            // Remove the edit form
            const editForm = form.closest('.order-edit-form');
            if (editForm) {
                editForm.style.opacity = '0';
                editForm.style.transition = 'opacity 0.3s ease-out';
                setTimeout(() => {
                    editForm.remove();
                }, 300);
            }
            
            const t_func = (typeof t !== 'undefined') ? t : (key) => key;
            showActionButtons([
                { text: t_func('buttons.viewAllOrders'), action: 'track_order' },
                { text: t_func('buttons.backToHome'), action: 'home' }
            ]);
        } else {
            addMessage(`❌ Error: ${data.message}`, 'bot', 'error');
            if (submitBtn) {
                submitBtn.disabled = false;
                const t_func = (typeof t !== 'undefined') ? t : (key) => key;
                submitBtn.innerHTML = `<i class="fas fa-check-circle me-2"></i>${t_func('buttons.confirmOrder')}`;
            }
        }
    } catch (error) {
        console.error('Error confirming order:', error);
        addMessage(`❌ Error confirming order. Please try again.`, 'bot', 'error');
    }
}

// Confirm order by distributor (simple version without edits)
async function confirmOrderAction(orderId) {
    if (!confirm(`Are you sure you want to confirm order ${orderId}?`)) {
        return;
    }
    
    try {
        // Get delivery partner selection first (must be selected before confirming)
        const deliveryPartnerSelect = document.getElementById(`delivery_partner_${orderId}`);
        const deliveryPartnerId = deliveryPartnerSelect ? deliveryPartnerSelect.value : null;
        
        if (!deliveryPartnerId) {
            addMessage('❌ Please select a delivery partner before confirming the order.', 'bot', 'error');
            return;
        }
        
        const response = await fetch('/enhanced-chat/confirm_order_action', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                order_id: orderId,
                delivery_partner_id: deliveryPartnerId
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            let successMessage = `✅ **Order Confirmed Successfully!**\n\n${data.message}\n\nThe stock has been moved from blocked to out_for_delivery, and the delivery partner has been notified via email.`;
            
            // Show notifications if any
            if (data.notifications && data.notifications.length > 0) {
                successMessage += `\n\n**📋 Notifications:**\n`;
                data.notifications.forEach(notif => {
                    successMessage += `• ${notif}\n`;
                });
            }
            
            addMessage(successMessage, 'bot');
            const t_func = (typeof t !== 'undefined') ? t : (key) => key;
            showActionButtons([
                { text: t_func('buttons.viewAllOrders'), action: 'track_order' },
                { text: t_func('buttons.backToHome'), action: 'home' }
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
    const reason = prompt('Please provide a reason for rejecting this order (optional):');
    
    try {
        const response = await fetch('/enhanced-chat/reject_order_action', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                order_id: orderId,
                rejection_reason: reason || null
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            addMessage(`✅ **Order Rejected Successfully!**\n\n${data.message}\n\nThe MR has been notified via email.`, 'bot');
            const t_func = (typeof t !== 'undefined') ? t : (key) => key;
            showActionButtons([
                { text: t_func('buttons.viewAllOrders'), action: 'track_order' },
                { text: t_func('buttons.backToHome'), action: 'home' }
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
window.confirmOrderWithEdits = confirmOrderWithEdits;
window.rejectOrderAction = rejectOrderAction;

// Reject order by distributor
async function cancelOrderAction(orderId) {
    try {
        const response = await fetch('/enhanced-chat/cancel_order_action', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ order_id: orderId })
        });
        
        const data = await response.json();
        
        if (data.success) {
            addMessage(data.message || `Order ${orderId} has been cancelled successfully.`, 'bot');
        } else {
            addMessage(data.message || data.error || 'Failed to cancel order.', 'bot', 'error');
        }
        
        // Show action buttons if provided
        if (data.action_buttons && data.action_buttons.length > 0) {
            showActionButtons(data.action_buttons);
        }
        
    } catch (error) {
        console.error('Error cancelling order:', error);
        addMessage('❌ Sorry, there was an error cancelling the order. Please try again.', 'bot', 'error');
    }
}

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
            const t_func = (typeof t !== 'undefined') ? t : (key) => key;
            showActionButtons([
                { text: t_func('buttons.viewAllOrders'), action: 'track_order' },
                { text: t_func('buttons.backToHome'), action: 'home' }
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
        <div class="message-bubble bot" style="width: 75% !important; max-width: 75% !important;">
            <div class="bg-light rounded-3 px-4 py-3 shadow-sm" style="border: 2px solid #3b82f6; width: 100%; max-width: 100%;">
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
        <div class="message-bubble bot" style="width: 75% !important; max-width: 75% !important;">
            <div class="bg-light rounded-3 px-4 py-3 shadow-sm" style="border: 2px solid #3b82f6; width: 100%; max-width: 100%;">
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

// Check FOC notification when quantity is entered
function checkFOCNotification(inputElement) {
    const quantity = parseInt(inputElement.value) || 0;
    const productCode = inputElement.getAttribute('data-product-code');
    const notificationDiv = document.getElementById(`foc-notification-${productCode}`);
    
    if (!notificationDiv || quantity === 0) {
        if (notificationDiv) notificationDiv.style.display = 'none';
        return;
    }
    
    // Get FOC schemes from data attribute
    const focSchemesJson = inputElement.getAttribute('data-foc-schemes');
    let focSchemes = [];
    try {
        focSchemes = JSON.parse(focSchemesJson || '[]');
    } catch (e) {
        console.warn('Error parsing FOC schemes:', e);
    }
    
    // First, find the best/highest scheme that quantity qualifies for
    let bestActiveScheme = null;
    let bestThreshold = 0;
    
    // Also track closest upcoming scheme (next tier above current quantity)
    let closestScheme = null;
    let minDistance = Infinity;
    let nextTierScheme = null; // The next higher tier scheme
    
    // Sort schemes by buy quantity (ascending) to check from lowest to highest
    const sortedSchemes = focSchemes
        .map(scheme => {
            if (scheme) {
                const buyQty = parseInt(scheme.buy_quantity || scheme.buy || 0);
                const freeQty = parseInt(scheme.free_quantity || scheme.free || 0);
                return { buyQty, freeQty, scheme };
            }
            return null;
        })
        .filter(s => s && s.buyQty > 0)
        .sort((a, b) => a.buyQty - b.buyQty); // Sort ascending
    
    for (const { buyQty, freeQty } of sortedSchemes) {
        // If quantity qualifies for this scheme, check if it's better than current best
        if (quantity >= buyQty && buyQty > bestThreshold) {
            bestThreshold = buyQty;
            bestActiveScheme = { buyQty, freeQty };
        }
        
        // Check if this is the next tier above current quantity
        const distance = buyQty - quantity;
        if (distance > 0) {
            // If this is closer than previous closest, or if we haven't found next tier yet
            if (distance < minDistance) {
                minDistance = distance;
                closestScheme = { buyQty, freeQty, distance };
            }
            // Track the next tier (first scheme above current quantity)
            if (!nextTierScheme && distance > 0) {
                nextTierScheme = { buyQty, freeQty, distance };
            }
        }
    }
    
    // Show the best active scheme if quantity qualifies for any
    if (bestActiveScheme) {
        notificationDiv.innerHTML = `<i class="fas fa-gift me-1"></i>FOC Active: Buy ${bestActiveScheme.buyQty} Get ${bestActiveScheme.freeQty} Free!`;
        notificationDiv.style.display = 'block';
        notificationDiv.style.color = '#059669';
    }
    // Otherwise, show notification if close to an upcoming scheme (within 5 units) or show next tier
    else if (closestScheme) {
        if (closestScheme.distance <= 5) {
            // Close to a scheme (within 5 units)
            notificationDiv.innerHTML = `<i class="fas fa-info-circle me-1"></i>Add ${closestScheme.distance} more to get FOC: Buy ${closestScheme.buyQty} Get ${closestScheme.freeQty} Free!`;
            notificationDiv.style.display = 'block';
            notificationDiv.style.color = '#f59e0b';
        } else if (nextTierScheme) {
            // Show next tier even if further away (but limit to reasonable distance)
            if (nextTierScheme.distance <= 20) {
                notificationDiv.innerHTML = `<i class="fas fa-info-circle me-1"></i>Add ${nextTierScheme.distance} more for better FOC: Buy ${nextTierScheme.buyQty} Get ${nextTierScheme.freeQty} Free!`;
                notificationDiv.style.display = 'block';
                notificationDiv.style.color = '#3b82f6';
            } else {
                notificationDiv.style.display = 'none';
            }
        } else {
            notificationDiv.style.display = 'none';
        }
    } else {
        notificationDiv.style.display = 'none';
    }
}

window.checkFOCNotification = checkFOCNotification;

// Product Search Interface Functions
function showProductSearchInterface(products) {
    const messagesDiv = document.getElementById('chatMessages');
    
    if (!messagesDiv) {
        console.error('showProductSearchInterface: Chat messages container not found');
        return;
    }
    
    // Find the last bot message
    const botMessages = messagesDiv.querySelectorAll('.message.bot');
    let lastBotMessage = null;
    
    if (botMessages.length > 0) {
        lastBotMessage = botMessages[botMessages.length - 1];
    }
    
    if (!lastBotMessage) {
        console.error('showProductSearchInterface: No bot message found');
        return;
    }
    
    // Find the inner message bubble div
    let messageBubble = lastBotMessage.querySelector('.message-bubble .bg-light');
    if (!messageBubble) {
        messageBubble = lastBotMessage.querySelector('.message-bubble .d-flex .bg-light');
    }
    if (!messageBubble) {
        messageBubble = lastBotMessage.querySelector('.bg-light');
    }
    
    if (!messageBubble) {
        const bubbleDiv = lastBotMessage.querySelector('.message-bubble');
        if (bubbleDiv) {
            let wrapper = bubbleDiv.querySelector('.d-flex');
            if (!wrapper) {
                wrapper = document.createElement('div');
                wrapper.className = 'd-flex justify-content-start align-items-center';
                wrapper.style.cssText = 'gap: 8px; width: 100%;';
                bubbleDiv.appendChild(wrapper);
            }
            let contentDiv = wrapper.querySelector('.bg-light');
            if (!contentDiv) {
                contentDiv = document.createElement('div');
                contentDiv.className = 'bg-light border rounded-3 px-3 py-2';
                contentDiv.style.cssText = 'max-width: 100%; font-size: 0.875rem; width: 100%;';
                wrapper.appendChild(contentDiv);
            }
            messageBubble = contentDiv;
        }
    }
    
    if (!messageBubble) {
        console.error('showProductSearchInterface: Could not find message bubble element');
        return;
    }
    
    const searchContainer = document.createElement('div');
    searchContainer.className = 'product-search-container mt-3';
    searchContainer.style.cssText = 'animation: slideInFromBottom 0.3s ease-out; width: 100%; max-width: 100%;';
    
    const searchCard = document.createElement('div');
    searchCard.className = 'card border-0 shadow-sm';
    searchCard.style.cssText = `
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(20px);
        border-radius: 16px;
        padding: 20px;
        width: 100%;
        box-sizing: border-box;
    `;
    
    // Store original products for filtering
    searchContainer._originalProducts = products;
    
    // Create search input and product list
    const searchLabel = (typeof t !== 'undefined') ? t('labels.searchProducts') : 'Search Products:';
    const availableLabel = (typeof t !== 'undefined') ? t('labels.availableProducts') : 'Available Products:';
    const placeholderText = (typeof t !== 'undefined') ? t('labels.typeToSearch') : 'Type product name to search...';
    const searchTitle = (typeof t !== 'undefined') ? t('messages.productInformation') : 'Product Information Search';
    
    searchCard.innerHTML = `
        <h6 class="mb-3" style="color: #2563eb; font-weight: 600;">
            <i class="fas fa-search me-2"></i>${searchTitle}
        </h6>
        <div class="mb-3">
            <label for="productSearchInput" class="form-label" style="font-weight: 500;">
                <i class="fas fa-search me-2"></i>${searchLabel}
            </label>
            <input type="text" 
                   class="form-control form-control-sm" 
                   id="productSearchInput" 
                   placeholder="${placeholderText}"
                   style="border-radius: 8px; border: 1.5px solid #e5e7eb; padding: 10px 12px; font-size: 0.875rem;"
                   oninput="filterProductList(this.value)">
        </div>
        <div class="mb-3">
            <label class="form-label" style="font-weight: 500;">
                <i class="fas fa-list me-2"></i>${availableLabel}
            </label>
            <div id="productListContainer" style="max-height: 300px; overflow-y: auto; border: 1px solid #e5e7eb; border-radius: 8px; padding: 10px;">
                ${renderProductList(products)}
            </div>
        </div>
    `;
    
    searchContainer.appendChild(searchCard);
    messageBubble.appendChild(searchContainer);
    
    // Scroll to bottom
    messagesDiv.scrollTo({
        top: messagesDiv.scrollHeight,
        behavior: 'smooth'
    });
}

function renderProductList(products) {
    if (!products || products.length === 0) {
        return '<p class="text-muted text-center mb-0">No products available</p>';
    }
    
    return products.map((product, index) => {
        const productName = product.name || 'Unknown Product';
        const productDesc = product.description ? (product.description.substring(0, 100) + '...') : '';
        return `
            <div class="product-item mb-2 p-2 border rounded" 
                 style="cursor: pointer; transition: all 0.2s; background: #f9fafb;"
                 onmouseover="this.style.background='#f3f4f6'; this.style.borderColor='#2563eb';"
                 onmouseout="this.style.background='#f9fafb'; this.style.borderColor='#e5e7eb';"
                 onclick="selectProductForDetails('${productName.replace(/'/g, "\\'")}', '${(product.id || productName).replace(/'/g, "\\'")}')">
                <div class="d-flex justify-content-between align-items-start">
                    <div style="flex: 1;">
                        <strong style="color: #2563eb; font-size: 0.9rem;">${productName}</strong>
                        ${productDesc ? `<p class="text-muted mb-0 mt-1" style="font-size: 0.8rem;">${productDesc}</p>` : ''}
                    </div>
                    <i class="fas fa-chevron-right text-primary mt-1"></i>
                </div>
            </div>
        `;
    }).join('');
}

function filterProductList(searchQuery) {
    const searchContainer = document.querySelector('.product-search-container');
    if (!searchContainer || !searchContainer._originalProducts) return;
    
    const query = searchQuery.toLowerCase().trim();
    const filteredProducts = query 
        ? searchContainer._originalProducts.filter(p => 
            (p.name && p.name.toLowerCase().includes(query)) ||
            (p.description && p.description.toLowerCase().includes(query))
          )
        : searchContainer._originalProducts;
    
    const container = document.getElementById('productListContainer');
    if (container) {
        container.innerHTML = renderProductList(filteredProducts);
    }
}

async function selectProductForDetails(productName, productId) {
    try {
        // Hide/remove the product search interface
        const searchContainer = document.querySelector('.product-search-container');
        if (searchContainer) {
            searchContainer.style.transition = 'opacity 0.3s ease-out';
            searchContainer.style.opacity = '0';
            setTimeout(() => {
                searchContainer.remove();
            }, 300);
        }
        
        // Show loading indicator
        const messagesDiv = document.getElementById('chatMessages');
        const loadingText = (typeof t !== 'undefined') ? t('messages.loadingProductInfo') : 'Loading product information...';
        const loadingMsg = addMessage(loadingText, 'bot');
        
        // Call backend to get product details
        const response = await fetch('/enhanced-chat/get_product_details', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                product_name: productName,
                product_id: productId
            })
        });
        
        // Remove loading message
        if (loadingMsg) {
            loadingMsg.remove();
        }
        
        if (!response.ok) {
            // Try to parse error message
            let errorMsg = 'Failed to load product details';
            try {
                const errorData = await response.json();
                errorMsg = errorData.error || errorMsg;
            } catch (e) {
                errorMsg = `Server error: ${response.status} ${response.statusText}`;
            }
            addMessage(`Error: ${errorMsg}`, 'bot', 'error');
            // Show action buttons even on error
            setTimeout(() => {
                showActionButtons([
                    {'text': (typeof t !== 'undefined') ? t('buttons.placeOrder') : 'Place Order', 'action': 'place_order'},
                    {'text': (typeof t !== 'undefined') ? t('buttons.viewOrder') : 'View Open Order', 'action': 'open_order'},
                    {'text': (typeof t !== 'undefined') ? t('buttons.productInfo') : 'Product Info', 'action': 'product_info'},
                    {'text': (typeof t !== 'undefined') ? t('buttons.companyInfo') : 'Company Info', 'action': 'company_info'}
                ]);
            }, 500);
            return;
        }
        
        const data = await response.json();
        
        if (data.product) {
            displayProductDetails(data.product);
        } else {
            addMessage('Error: Product details not found in response', 'bot', 'error');
            // Show action buttons even on error
            setTimeout(() => {
                showActionButtons([
                    {'text': (typeof t !== 'undefined') ? t('buttons.placeOrder') : 'Place Order', 'action': 'place_order'},
                    {'text': (typeof t !== 'undefined') ? t('buttons.viewOrder') : 'View Open Order', 'action': 'open_order'},
                    {'text': (typeof t !== 'undefined') ? t('buttons.productInfo') : 'Product Info', 'action': 'product_info'},
                    {'text': (typeof t !== 'undefined') ? t('buttons.companyInfo') : 'Company Info', 'action': 'company_info'}
                ]);
            }, 500);
        }
    } catch (error) {
        console.error('Error fetching product details:', error);
        // Remove loading message if still present
        const messagesDiv = document.getElementById('chatMessages');
        const loadingMessages = messagesDiv.querySelectorAll('.message.bot');
        if (loadingMessages.length > 0) {
            const lastMsg = loadingMessages[loadingMessages.length - 1];
            if (lastMsg.textContent.includes('Loading product information')) {
                lastMsg.remove();
            }
        }
        addMessage('Sorry, I encountered an error loading product details. Please try again.', 'bot', 'error');
        // Show action buttons even on error
        setTimeout(() => {
            showActionButtons([
                {'text': 'Place Order', 'action': 'place_order'},
                {'text': 'View Open Order', 'action': 'open_order'},
                {'text': 'Product Info', 'action': 'product_info'},
                {'text': 'Company Info', 'action': 'company_info'}
            ]);
        }, 500);
    }
}

function displayProductDetails(product) {
    const messagesDiv = document.getElementById('chatMessages');
    
    // Create a new message for product details
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message bot mb-3';
    
    const bubbleDiv = document.createElement('div');
    bubbleDiv.className = 'message-bubble bot';
    
    const wrapperDiv = document.createElement('div');
    wrapperDiv.className = 'd-flex justify-content-start align-items-center';
    wrapperDiv.style.cssText = 'gap: 8px; width: 100%;';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'bg-light border rounded-3 px-4 py-3';
    contentDiv.style.cssText = 'max-width: 100%; font-size: 0.875rem; width: 100%;';
    
    // Get translations
    const t_func = (typeof t !== 'undefined') ? t : (key) => key;
    const productName = product.name || t_func('messages.productInfo');
    const packSizeLabel = t_func('messages.packSize');
    const genericNameLabel = t_func('messages.genericName');
    const therapeuticClassLabel = t_func('messages.therapeuticClass');
    const keyUsesLabel = t_func('messages.keyUses');
    const mechanismLabel = t_func('messages.mechanismOfAction');
    const dosageLabel = t_func('messages.dosage');
    const safetyLabel = t_func('messages.safetyProfile');
    const descriptionLabel = t_func('messages.description');
    const productInfoLabel = t_func('messages.productInfo');
    
    // Build structured product information
    let productHTML = `
        <div class="product-details" style="max-width: 100%;">
            <h5 class="mb-3" style="color: #2563eb; font-weight: 600; border-bottom: 2px solid #2563eb; padding-bottom: 10px;">
                <i class="fas fa-pills me-2"></i>${productName}
            </h5>
    `;
    
    // Pack Size
    if (product.pack_size) {
        productHTML += `
            <div class="mb-3">
                <strong style="color: #1f2937;"><i class="fas fa-box me-2"></i>${packSizeLabel}:</strong>
                <p class="mb-0 mt-1" style="color: #4b5563;">${product.pack_size}</p>
            </div>
        `;
    }
    
    // Generic Name / Composition
    if (product.generic_name) {
        productHTML += `
            <div class="mb-3">
                <strong style="color: #1f2937;"><i class="fas fa-flask me-2"></i>${genericNameLabel}:</strong>
                <p class="mb-0 mt-1" style="color: #4b5563;">${product.generic_name}</p>
            </div>
        `;
    }
    
    // Therapeutic Class
    if (product.therapeutic_class) {
        productHTML += `
            <div class="mb-3">
                <strong style="color: #1f2937;"><i class="fas fa-layer-group me-2"></i>${therapeuticClassLabel}:</strong>
                <p class="mb-0 mt-1" style="color: #4b5563;">${product.therapeutic_class}</p>
            </div>
        `;
    }
    
    // Key Uses
    if (product.key_uses) {
        productHTML += `
            <div class="mb-3">
                <strong style="color: #1f2937;"><i class="fas fa-check-circle me-2"></i>${keyUsesLabel}:</strong>
                <div class="mt-1" style="color: #4b5563;">${formatProductText(product.key_uses)}</div>
            </div>
        `;
    }
    
    // Mechanism of Action
    if (product.mechanism_of_action) {
        productHTML += `
            <div class="mb-3">
                <strong style="color: #1f2937;"><i class="fas fa-cogs me-2"></i>${mechanismLabel}:</strong>
                <p class="mb-0 mt-1" style="color: #4b5563;">${formatProductText(product.mechanism_of_action)}</p>
            </div>
        `;
    }
    
    // Dosage & Administration
    if (product.dosage) {
        productHTML += `
            <div class="mb-3">
                <strong style="color: #1f2937;"><i class="fas fa-prescription-bottle-alt me-2"></i>${dosageLabel}:</strong>
                <div class="mt-1" style="color: #4b5563;">${formatProductText(product.dosage)}</div>
            </div>
        `;
    }
    
    // Safety Profile & Side Effects
    if (product.safety_profile) {
        productHTML += `
            <div class="mb-3">
                <strong style="color: #1f2937;"><i class="fas fa-shield-alt me-2"></i>${safetyLabel}:</strong>
                <div class="mt-1" style="color: #4b5563;">${formatProductText(product.safety_profile)}</div>
            </div>
        `;
    }
    
    // Description (fallback)
    if (product.description && !product.generic_name && !product.key_uses) {
        productHTML += `
            <div class="mb-3">
                <strong style="color: #1f2937;"><i class="fas fa-info-circle me-2"></i>${descriptionLabel}:</strong>
                <p class="mb-0 mt-1" style="color: #4b5563;">${formatProductText(product.description)}</p>
            </div>
        `;
    }
    
    // Full Content (if available and other fields are empty)
    if (product.full_content && !product.generic_name && !product.key_uses && !product.description) {
        productHTML += `
            <div class="mb-3">
                <strong style="color: #1f2937;"><i class="fas fa-file-alt me-2"></i>${productInfoLabel}:</strong>
                <div class="mt-1" style="color: #4b5563; white-space: pre-wrap;">${formatProductText(product.full_content)}</div>
            </div>
        `;
    }
    
    productHTML += `</div>`;
    
    contentDiv.innerHTML = productHTML;
    
    const avatarDiv = document.createElement('div');
    avatarDiv.className = 'message-avatar bot-avatar';
    avatarDiv.innerHTML = '<img src="/static/Images/Q_logo_quantum_blue-removebg-preview.png" alt="Quantum Blue Logo" style="width: 100%; height: 100%; object-fit: contain; border-radius: 50%;">';
    
    wrapperDiv.appendChild(avatarDiv);
    wrapperDiv.appendChild(contentDiv);
    bubbleDiv.appendChild(wrapperDiv);
    messageDiv.appendChild(bubbleDiv);
    
    messagesDiv.appendChild(messageDiv);
    
    // Scroll to bottom
    messagesDiv.scrollTo({
        top: messagesDiv.scrollHeight,
        behavior: 'smooth'
    });
    
    // Show action buttons after displaying product details
    setTimeout(() => {
        showActionButtons([
            {'text': (typeof t !== 'undefined') ? t('buttons.placeOrder') : 'Place Order', 'action': 'place_order'},
            {'text': (typeof t !== 'undefined') ? t('buttons.viewOrder') : 'View Open Order', 'action': 'open_order'},
            {'text': (typeof t !== 'undefined') ? t('buttons.productInfo') : 'Product Info', 'action': 'product_info'},
            {'text': (typeof t !== 'undefined') ? t('buttons.companyInfo') : 'Company Info', 'action': 'company_info'}
        ]);
    }, 500);
}

function formatProductText(text) {
    if (!text) return '';
    
    // Replace newlines with <br> and format bullet points
    let formatted = text
        .replace(/\n/g, '<br>')
        .replace(/\•/g, '•')
        .replace(/^\s*[-*]\s*/gm, '• ');
    
    // Wrap in paragraphs if it contains multiple lines
    if (formatted.includes('<br>')) {
        const lines = formatted.split('<br>');
        return lines.map(line => {
            line = line.trim();
            if (line.startsWith('•') || line.startsWith('-')) {
                return `<div style="margin-left: 20px; margin-bottom: 5px;">${line}</div>`;
            }
            return line ? `<p class="mb-2">${line}</p>` : '';
        }).join('');
    }
    
    return `<p class="mb-0">${formatted}</p>`;
}

// ============= UTILITY FUNCTIONS =============

// Copy to Clipboard
function copyToClipboard(text, buttonElement) {
    if (!text) {
        showToast('Nothing to copy', 'error');
        return;
    }
    
    // Try modern clipboard API first
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(() => {
            if (buttonElement) {
                const originalHTML = buttonElement.innerHTML;
                buttonElement.innerHTML = '<i class="fas fa-check"></i>';
                buttonElement.classList.add('copied');
                setTimeout(() => {
                    buttonElement.innerHTML = originalHTML;
                    buttonElement.classList.remove('copied');
                }, 2000);
            }
            showToast('Copied to clipboard!', 'success');
        }).catch(err => {
            console.error('Clipboard API failed:', err);
            // Fallback to older method
            fallbackCopyToClipboard(text, buttonElement);
        });
    } else {
        // Fallback for older browsers
        fallbackCopyToClipboard(text, buttonElement);
    }
}

// Fallback copy method for older browsers
function fallbackCopyToClipboard(text, buttonElement) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.left = '-999999px';
    textArea.style.top = '-999999px';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    
    try {
        const successful = document.execCommand('copy');
        if (successful) {
            if (buttonElement) {
                const originalHTML = buttonElement.innerHTML;
                buttonElement.innerHTML = '<i class="fas fa-check"></i>';
                buttonElement.classList.add('copied');
                setTimeout(() => {
                    buttonElement.innerHTML = originalHTML;
                    buttonElement.classList.remove('copied');
                }, 2000);
            }
            showToast('Copied to clipboard!', 'success');
        } else {
            throw new Error('Copy command failed');
        }
    } catch (err) {
        console.error('Fallback copy failed:', err);
        showToast('Failed to copy. Please copy manually: ' + text, 'error');
    } finally {
        document.body.removeChild(textArea);
    }
}

// Show Toast Notification
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast-notification toast-${type}`;
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#2563eb'};
        color: white;
        padding: 12px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        z-index: 10000;
        animation: slideInRight 0.3s ease-out;
    `;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideOutRight 0.3s ease-out';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Loading State Management
function showLoading(element, text = 'Loading...') {
    if (!element) return null;
    
    // Remove any existing loading overlay first
    const existing = element.querySelector('.loading-overlay');
    if (existing) existing.remove();
    
    const overlay = document.createElement('div');
    overlay.className = 'loading-overlay';
    overlay.style.cssText = `
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(255, 255, 255, 0.95);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 1000;
        border-radius: 8px;
    `;
    overlay.innerHTML = `
        <div style="display: flex; align-items: center; gap: 8px;">
            <div class="loading-spinner"></div>
            <span class="loading-text" style="color: #2563eb; font-weight: 500;">${text}</span>
        </div>
    `;
    
    // Ensure parent has relative positioning
    const currentPosition = window.getComputedStyle(element).position;
    if (currentPosition === 'static') {
        element.style.position = 'relative';
    }
    
    element.appendChild(overlay);
    return overlay;
}

function hideLoading(overlay) {
    if (overlay && overlay.parentNode) {
        overlay.remove();
    }
}

// Recent Searches Management
let recentSearches = JSON.parse(localStorage.getItem('recentSearches') || '[]');
const MAX_RECENT_SEARCHES = 10;

function addToRecentSearches(searchTerm) {
    if (!searchTerm || searchTerm.trim().length < 2) return;
    
    const term = searchTerm.trim().toLowerCase();
    recentSearches = recentSearches.filter(s => s !== term);
    recentSearches.unshift(term);
    recentSearches = recentSearches.slice(0, MAX_RECENT_SEARCHES);
    localStorage.setItem('recentSearches', JSON.stringify(recentSearches));
}

let recentSearchesDropdownCloseHandler = null;

function showRecentSearches(inputElement) {
    if (recentSearches.length === 0) return;
    
    let existing = document.getElementById('recentSearchesDropdown');
    if (existing) {
        existing.remove();
        if (recentSearchesDropdownCloseHandler) {
            document.removeEventListener('click', recentSearchesDropdownCloseHandler);
            recentSearchesDropdownCloseHandler = null;
        }
    }
    
    // Limit to only 3 most recent searches
    const displaySearches = recentSearches.slice(0, 3);
    
    const dropdown = document.createElement('div');
    dropdown.id = 'recentSearchesDropdown';
    dropdown.className = 'recent-searches';
    const inputRect = inputElement.getBoundingClientRect();
    dropdown.style.cssText = `
        position: fixed;
        top: ${inputRect.top - 4}px;
        left: ${inputRect.left}px;
        width: ${inputRect.width}px;
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        box-shadow: 0 -8px 16px rgba(0, 0, 0, 0.12);
        z-index: 1000;
        transform: translateY(-100%);
        overflow: hidden;
    `;
    
    dropdown.innerHTML = `
        <div class="recent-searches-header">
            <span class="recent-searches-title">
                <i class="fas fa-clock me-2"></i>Recent Searches
            </span>
            <button onclick="closeRecentSearches()" class="recent-searches-close-btn" title="Close">
                <i class="fas fa-times"></i>
            </button>
        </div>
        <div class="recent-searches-list">
            ${displaySearches.map(term => `
                <div class="recent-search-item" onclick="selectRecentSearch('${term.replace(/'/g, "\\'")}')">
                    <div class="recent-search-content">
                        <i class="fas fa-history recent-search-icon"></i>
                        <span class="recent-search-text">${term}</span>
                    </div>
                    <button class="recent-search-remove-btn" onclick="event.stopPropagation(); removeRecentSearch('${term.replace(/'/g, "\\'")}')" title="Remove">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            `).join('')}
        </div>
    `;
    
    document.body.appendChild(dropdown);
    
    // Close handler
    recentSearchesDropdownCloseHandler = function(e) {
        if (!dropdown.contains(e.target) && e.target !== inputElement && !inputElement.contains(e.target)) {
            closeRecentSearches();
        }
    };
    
    setTimeout(() => {
        document.addEventListener('click', recentSearchesDropdownCloseHandler);
    }, 100);
}

function closeRecentSearches() {
    const dropdown = document.getElementById('recentSearchesDropdown');
    if (dropdown) {
        dropdown.remove();
    }
    if (recentSearchesDropdownCloseHandler) {
        document.removeEventListener('click', recentSearchesDropdownCloseHandler);
        recentSearchesDropdownCloseHandler = null;
    }
}

function selectRecentSearch(term) {
    const input = document.getElementById('messageInput');
    if (input) {
        input.value = term;
        input.focus();
        closeRecentSearches();
        sendMessage();
    }
}

function removeRecentSearch(term) {
    recentSearches = recentSearches.filter(s => s !== term.toLowerCase());
    localStorage.setItem('recentSearches', JSON.stringify(recentSearches));
    const input = document.getElementById('messageInput');
    if (input && document.activeElement === input && input.value.trim().length === 0) {
        showRecentSearches(input);
    } else {
        closeRecentSearches();
    }
}

// Favorites Management
let favorites = {
    products: JSON.parse(localStorage.getItem('favoriteProducts') || '[]'),
    customers: JSON.parse(localStorage.getItem('favoriteCustomers') || '[]')
};

function toggleFavorite(type, id, name) {
    const list = favorites[type] || [];
    const index = list.findIndex(item => item.id === id);
    
    if (index > -1) {
        list.splice(index, 1);
        if (typeof showToast === 'function') {
            showToast(`${name} removed from favorites`, 'info');
        }
    } else {
        list.push({ id, name, addedAt: new Date().toISOString() });
        if (typeof showToast === 'function') {
            showToast(`${name} added to favorites`, 'success');
        }
    }
    
    favorites[type] = list;
    localStorage.setItem(`favorite${type.charAt(0).toUpperCase() + type.slice(1)}`, JSON.stringify(list));
    
    // Update all favorite buttons for this item across the page
    const favoriteButtons = document.querySelectorAll(`.favorite-btn[onclick*="'${id}'"]`);
    favoriteButtons.forEach(btn => {
        if (index === -1) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
    
    // If it's a customer favorite, refresh the customer table filter
    if (type === 'customers' && typeof filterCustomerTable === 'function') {
        // Small delay to ensure localStorage is updated
        setTimeout(() => {
            filterCustomerTable();
        }, 100);
    }
    
    return index === -1;
}

function isFavorite(type, id) {
    return favorites[type]?.some(item => item.id === id) || false;
}

// Quick Stats
let quickStats = {
    pendingOrders: 0,
    totalOrders: 0,
    cartItems: 0
};

function updateQuickStats() {
    if (!currentUser) return;
    
    // Fetch stats based on user role
    fetch('/enhanced-chat/api/quick-stats')
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                quickStats = data.stats;
                renderQuickStats();
            }
        })
        .catch(err => console.error('Error fetching stats:', err));
}

function renderQuickStats() {
    let statsContainer = document.getElementById('quickStats');
    if (!statsContainer) {
        statsContainer = document.createElement('div');
        statsContainer.id = 'quickStats';
        statsContainer.className = 'quick-stats';
        const header = document.querySelector('.card-header');
        if (header) {
            header.appendChild(statsContainer);
        }
    }
    
    const role = currentUser?.role || '';
    if (role === 'mr') {
        statsContainer.innerHTML = `
            <div class="stat-item">
                <span class="stat-value">${quickStats.pendingOrders || 0}</span>
                <span class="stat-label">Pending</span>
            </div>
            <div class="stat-item">
                <span class="stat-value">${quickStats.totalOrders || 0}</span>
                <span class="stat-label">Total</span>
            </div>
            <div class="stat-item">
                <span class="stat-value">${cartItems.length}</span>
                <span class="stat-label">Cart</span>
            </div>
        `;
    } else if (role === 'distributor') {
        statsContainer.innerHTML = `
            <div class="stat-item">
                <span class="stat-value">${quickStats.pendingOrders || 0}</span>
                <span class="stat-label">Pending</span>
            </div>
            <div class="stat-item">
                <span class="stat-value">${quickStats.totalOrders || 0}</span>
                <span class="stat-label">Total</span>
            </div>
        `;
    }
}

// Keyboard Navigation
function setupKeyboardNavigation() {
    document.addEventListener('keydown', function(e) {
        // Tab navigation for forms
        if (e.key === 'Tab') {
            const focusableElements = document.querySelectorAll(
                'input:not([disabled]), select:not([disabled]), textarea:not([disabled]), button:not([disabled]), [tabindex]:not([tabindex="-1"])'
            );
            const currentIndex = Array.from(focusableElements).indexOf(document.activeElement);
            
            if (e.shiftKey && currentIndex === 0) {
                e.preventDefault();
                focusableElements[focusableElements.length - 1].focus();
            } else if (!e.shiftKey && currentIndex === focusableElements.length - 1) {
                e.preventDefault();
                focusableElements[0].focus();
            }
        }
        
        // Escape to close modals/dropdowns
        if (e.key === 'Escape') {
            document.querySelectorAll('.recent-searches, .customer-dropdown').forEach(el => el.remove());
        }
    });
}

// Print Functionality
function printOrder(orderId) {
    try {
        // Find the order element
        const orderElement = document.querySelector(`[data-order-id="${orderId}"]`);
        
        if (!orderElement) {
            showToast('Order details not found', 'error');
            return;
        }
        
        // Clone the element to avoid modifying the original
        const clone = orderElement.cloneNode(true);
        
        // Remove action buttons and other non-printable elements
        clone.querySelectorAll('.action-buttons-container, .copy-btn, .no-print').forEach(el => el.remove());
        
        // Get order details from the DOM
        const orderTitle = clone.querySelector('strong')?.textContent || `Order ${orderId}`;
        const orderInfo = Array.from(clone.querySelectorAll('li, p')).map(el => el.textContent).join('\n');
        const orderTable = clone.querySelector('.order-items-table')?.outerHTML || '';
        
        // Create print window
        const printWindow = window.open('', '_blank');
        
        printWindow.document.write(`
            <!DOCTYPE html>
            <html>
                <head>
                    <title>Order ${orderId}</title>
                    <style>
                        @media print {
                            @page { margin: 1cm; }
                            body { margin: 0; }
                        }
                        body { 
                            font-family: Arial, sans-serif; 
                            padding: 20px; 
                            color: #333;
                        }
                        .order-header { 
                            border-bottom: 3px solid #2563eb; 
                            padding-bottom: 15px; 
                            margin-bottom: 20px; 
                        }
                        .order-header h1 {
                            color: #2563eb;
                            margin: 0 0 10px 0;
                            font-size: 24px;
                        }
                        .order-info {
                            margin: 15px 0;
                            line-height: 1.8;
                        }
                        .order-info strong {
                            color: #1e40af;
                        }
                        table { 
                            width: 100%; 
                            border-collapse: collapse; 
                            margin: 20px 0; 
                            font-size: 12px;
                        }
                        th, td { 
                            border: 1px solid #ddd; 
                            padding: 10px; 
                            text-align: left; 
                        }
                        th { 
                            background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
                            color: white; 
                            font-weight: 600;
                        }
                        tr:nth-child(even) {
                            background-color: #f8f9fa;
                        }
                        .order-total {
                            font-weight: 700;
                            font-size: 16px;
                            color: #2563eb;
                            margin-top: 20px;
                            padding-top: 15px;
                            border-top: 2px solid #2563eb;
                        }
                        .print-footer {
                            margin-top: 30px;
                            padding-top: 15px;
                            border-top: 1px solid #ddd;
                            text-align: center;
                            color: #666;
                            font-size: 11px;
                        }
                    </style>
                </head>
                <body>
                    <div class="order-header">
                        <h1>${orderTitle}</h1>
                        <p style="color: #666; margin: 0;">Order ID: ${orderId}</p>
                    </div>
                    <div class="order-info">
                        ${orderInfo.replace(/\*\*/g, '').replace(/\n/g, '<br>')}
                    </div>
                    ${orderTable}
                    <div class="print-footer">
                        <p>Generated by HV (Powered by Quantum Blue AI)</p>
                        <p>Printed on: ${new Date().toLocaleString()}</p>
                    </div>
                </body>
            </html>
        `);
        printWindow.document.close();
        
        // Wait for content to load, then print
        setTimeout(() => {
            printWindow.focus();
            printWindow.print();
        }, 250);
        
    } catch (error) {
        console.error('Print error:', error);
        showToast('Error printing order', 'error');
    }
}

// Make functions globally available
window.showProductSearchInterface = showProductSearchInterface;
window.filterProductList = filterProductList;
window.selectProductForDetails = selectProductForDetails;
window.displayProductDetails = displayProductDetails;
window.copyToClipboard = copyToClipboard;
window.selectRecentSearch = selectRecentSearch;
window.removeRecentSearch = removeRecentSearch;
window.closeRecentSearches = closeRecentSearches;
window.toggleFavorite = toggleFavorite;
window.isFavorite = isFavorite;
window.filterCustomerTable = filterCustomerTable;
window.printOrder = printOrder;

// ============= BULK ACTIONS & EXPORT =============
// Bulk order functionality has been removed

async function handleOrderSelectionFromList(orderId) {
    if (!orderId) return;
    
    // Normal flow: display in chatbot
    const form = document.getElementById('orderSelectionForm');
    if (form) {
        const select = document.getElementById('orderSelect');
        if (select) {
            select.value = orderId;
        }
        handleOrderSelection({ preventDefault: () => {}, target: form });
    }
}

// Order edits map removed (bulk functionality removed)

// Shared function to collect item edits from a form (used by both single and bulk order flows)
function collectItemEditsFromForm(form) {
    if (!form) {
        return {};
    }
    
    const itemEdits = {};
    const itemIds = [];
    
    // Get all item IDs from hidden inputs
    form.querySelectorAll('input[type="hidden"][name^="item_id_"]').forEach(input => {
        const itemId = parseInt(input.value);
        if (!isNaN(itemId)) {
            itemIds.push(itemId);
        }
    });
    
    // Collect edits for each item - ALWAYS include quantity if field exists
    itemIds.forEach(itemId => {
        const quantity = form.querySelector(`#qty_${itemId}`);
        const lotNumber = form.querySelector(`#lot_${itemId}`);
        const expiryDate = form.querySelector(`#expiry_${itemId}`);
        const reason = form.querySelector(`#reason_${itemId}`);
        
        const edits = {};
        let hasEdits = false;
        
        // Quantity: ALWAYS include if field exists (backend needs it to dispatch stock)
        // CRITICAL: We must always send quantity, even if 0, so backend knows what to dispatch
        if (quantity && quantity.value !== null && quantity.value !== undefined && quantity.value !== '') {
            const qtyValue = parseInt(quantity.value);
            if (!isNaN(qtyValue)) {
                // Always include quantity (even if 0) - backend will validate and use requested_qty if needed
                edits.quantity = qtyValue;
                hasEdits = true;
            }
        } else if (quantity) {
            // Field exists but is empty - this shouldn't happen, but if it does, don't include
            // Backend will use requested_qty from database
        }
        
        // Lot number: include if value is provided and not empty
        if (lotNumber && lotNumber.value && lotNumber.value.trim()) {
            edits.lot_number = lotNumber.value.trim();
            hasEdits = true;
        }
        
        // Expiry date: include if value is provided
        if (expiryDate && expiryDate.value) {
            edits.expiry_date = expiryDate.value;
            hasEdits = true;
        }
        
        // Reason: include if value is provided and not empty
        if (reason && reason.value && reason.value.trim()) {
            edits.reason = reason.value.trim();
            hasEdits = true;
        }
        
        // Always include item if quantity is present (even if no other edits)
        // This ensures backend receives the quantity to set adjusted_quantity
        if (hasEdits || (quantity && !isNaN(parseInt(quantity.value)) && parseInt(quantity.value) >= 0)) {
            itemEdits[itemId] = edits;
        }
    });
    
    return itemEdits;
}

// All bulk order functions and modal functions removed

// ============= ORDER TEMPLATES =============

let orderTemplates = JSON.parse(localStorage.getItem('orderTemplates') || '[]');

function saveOrderTemplate(templateName, customerId, items, customerName = '') {
    if (!templateName || !items || items.length === 0) {
        showToast('Invalid template data', 'error');
        return false;
    }
    
    // Get customer name from items or parameter
    const finalCustomerName = customerName || items[0]?.customer_name || '';
    
    const template = {
        id: Date.now().toString(),
        name: templateName,
        customer_id: customerId,
        customer_name: finalCustomerName,
        items: items.map(item => ({
            product_id: item.product_id,
            product_name: item.product_name,
            product_code: item.product_code,
            quantity: item.quantity
        })),
        created_at: new Date().toISOString(),
        last_used: new Date().toISOString()
    };
    
    orderTemplates.push(template);
    localStorage.setItem('orderTemplates', JSON.stringify(orderTemplates));
    showToast(`Template "${templateName}" saved successfully!`, 'success');
    return true;
}

async function loadOrderTemplate(templateId) {
    // Prevent multiple simultaneous loads
    if (window.isLoadingTemplate) {
        return;
    }
    window.isLoadingTemplate = true;
    
    try {
        // Reload templates from localStorage
        orderTemplates = JSON.parse(localStorage.getItem('orderTemplates') || '[]');
        
        const template = orderTemplates.find(t => t.id === templateId);
        if (!template) {
            showToast('Template not found', 'error');
            return;
        }
        
        // Show loading message only once
        addMessage(`Loading template "${template.name}"...`, 'bot');
        
        // Update last used
        template.last_used = new Date().toISOString();
        localStorage.setItem('orderTemplates', JSON.stringify(orderTemplates));
        
        // Add items to cart sequentially with a small delay to prevent duplicates
        let successCount = 0;
        let errorCount = 0;
        
        const errorDetails = [];
        
        for (let i = 0; i < template.items.length; i++) {
            const item = template.items[i];
            try {
                // Add small delay between requests to prevent race conditions
                if (i > 0) {
                    await new Promise(resolve => setTimeout(resolve, 100));
                }
                
                // Validate item data
                if (!item.product_code) {
                    errorCount++;
                    errorDetails.push(`${item.product_name || 'Unknown'}: Missing product code`);
                    console.error('Template item missing product_code:', item);
                    continue;
                }
                
                if (!item.quantity || item.quantity <= 0) {
                    errorCount++;
                    errorDetails.push(`${item.product_name || item.product_code}: Invalid quantity (${item.quantity})`);
                    console.error('Template item has invalid quantity:', item);
                    continue;
                }
                
                const response = await fetch('/enhanced-chat/cart/add', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        product_code: item.product_code,
                        quantity: item.quantity
                    })
                });
                
                let data;
                try {
                    if (!response.ok) {
                        // Try to get error message from response
                        let errorText = `HTTP ${response.status}`;
                        try {
                            const errorData = await response.json();
                            errorText = errorData.error || errorData.message || errorText;
                        } catch {
                            const text = await response.text();
                            errorText = text || errorText;
                        }
                        errorCount++;
                        errorDetails.push(`${item.product_name || item.product_code}: ${errorText}`);
                        console.error(`Failed to add item (HTTP ${response.status}):`, item.product_name, errorText);
                        continue;
                    }
                    
                    // Response is OK, parse JSON
                    data = await response.json();
                    if (data.success) {
                        successCount++;
                    } else {
                        errorCount++;
                        const errorMsg = data.error || data.message || 'Unknown error';
                        errorDetails.push(`${item.product_name || item.product_code}: ${errorMsg}`);
                        console.error('Failed to add item:', item.product_name, errorMsg);
                    }
                } catch (error) {
                    errorCount++;
                    const errorMsg = error.message || 'Network error';
                    errorDetails.push(`${item.product_name || item.product_code}: ${errorMsg}`);
                    console.error('Error processing response:', error);
                }
            } catch (error) {
                errorCount++;
                const errorMsg = error.message || 'Network error';
                errorDetails.push(`${item.product_name || item.product_code}: ${errorMsg}`);
                console.error('Error adding item from template:', error);
            }
        }
        
        // Show result message only once
        if (successCount > 0) {
            let successMessage = `✅ Template "${template.name}" loaded successfully! ${successCount} item(s) added to cart.`;
            if (errorCount > 0) {
                successMessage += `\n\n⚠️ ${errorCount} item(s) failed to load:\n${errorDetails.slice(0, 5).map(e => `• ${e}`).join('\n')}`;
                if (errorDetails.length > 5) {
                    successMessage += `\n... and ${errorDetails.length - 5} more errors.`;
                }
            }
            addMessage(successMessage, 'bot');
            
            // Hide action buttons after loading template
            const actionButtons = document.querySelectorAll('.action-buttons-container');
            actionButtons.forEach(container => {
                container.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
                container.style.opacity = '0';
                container.style.transform = 'translateY(-10px)';
                setTimeout(() => {
                    container.remove();
                }, 300);
            });
            
            // Show cart only once, with a small delay to ensure all items are added
            setTimeout(async () => {
                await viewCart();
            }, 500);
        } else {
            let errorMessage = `❌ Failed to load template "${template.name}".\n\n`;
            if (errorDetails.length > 0) {
                errorMessage += `**Errors encountered:**\n${errorDetails.map(e => `• ${e}`).join('\n')}\n\n`;
            }
            errorMessage += `**Possible reasons:**\n• Products may no longer be available\n• Product codes may have changed\n• Stock may be insufficient\n\nPlease check the template and try again, or create a new template with current products.`;
            addMessage(errorMessage, 'bot', 'error');
            
            // No action buttons on failure - user can use default buttons or try again
        }
    } finally {
        window.isLoadingTemplate = false;
    }
}

function deleteOrderTemplate(templateId) {
    orderTemplates = orderTemplates.filter(t => t.id !== templateId);
    localStorage.setItem('orderTemplates', JSON.stringify(orderTemplates));
    showToast('Template deleted', 'success');
    // Refresh template list if showing
    if (orderTemplates.length > 0) {
        showOrderTemplates();
    } else {
        addMessage('All templates have been deleted.', 'bot');
    }
}

function showDeleteTemplateInterface() {
    if (orderTemplates.length === 0) {
        addMessage('No templates to delete.', 'bot');
        return;
    }
    
    let message = `**🗑️ Delete Template**\n\nSelect a template to delete:\n\n`;
    orderTemplates.forEach((template, index) => {
        message += `${index + 1}. **${template.name}** (${template.items.length} items)\n`;
    });
    
    addMessage(message, 'bot');
    
    // Add delete buttons for each template
    const deleteButtons = orderTemplates.map(template => ({
        text: `🗑️ Delete "${template.name}"`,
        action: 'delete_template_item',
        template_id: template.id,
        onclick: `if(confirm('Are you sure you want to delete template "${template.name}"?')) { deleteOrderTemplate('${template.id}'); }`
    }));
    
    deleteButtons.push({ text: 'Cancel', action: 'cancel' });
    showActionButtons(deleteButtons);
}

function showOrderTemplates() {
    // Reload templates from localStorage to get latest
    orderTemplates = JSON.parse(localStorage.getItem('orderTemplates') || '[]');
    
    if (orderTemplates.length === 0) {
        addMessage('No saved order templates. You can save your current cart as a template after adding items.', 'bot');
        return;
    }
    
    // Create a formatted message with template list
    let message = `**📋 Saved Order Templates (${orderTemplates.length})**\n\n`;
    message += `Select a template from the dropdown below to view its details and load it into your cart.`;
    
    addMessage(message, 'bot');
    
    // Find the last bot message to add the selection form
    const messagesDiv = document.getElementById('chatMessages');
    const botMessages = messagesDiv.querySelectorAll('.message.bot');
    const lastBotMessage = botMessages[botMessages.length - 1];
    
    if (lastBotMessage) {
        const messageBubble = lastBotMessage.querySelector('.message-bubble .bg-light');
        if (messageBubble) {
            // Create template selection form
            const formHTML = `
                <div class="template-selection-container mt-3 p-3" style="background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%); border-radius: 12px; border: 2px solid #3b82f6;">
                    <div class="mb-3">
                        <label for="templateSelect" class="form-label" style="font-weight: 600; color: #1e40af; margin-bottom: 8px;">
                            <i class="fas fa-file-alt me-2"></i>Select Template:
                        </label>
                        <select id="templateSelect" class="form-select" style="border-radius: 8px; padding: 10px; font-size: 0.9rem; border: 2px solid #3b82f6;">
                            <option value="">-- Choose a template --</option>
                            ${orderTemplates.map(template => `
                                <option value="${template.id}" 
                                        data-name="${template.name.replace(/"/g, '&quot;')}"
                                        data-customer="${(template.customer_name || 'N/A').replace(/"/g, '&quot;')}"
                                        data-items='${JSON.stringify(template.items).replace(/'/g, "&#39;")}'
                                        data-last-used="${template.last_used}">
                                    ${template.name} - ${template.customer_name || 'N/A'} (${template.items.length} items)
                                </option>
                            `).join('')}
                        </select>
                    </div>
                    <div class="d-flex gap-2 flex-wrap">
                        <button type="button" class="btn btn-primary" onclick="handleTemplateSelection()" style="border-radius: 8px; padding: 8px 16px;">
                            <i class="fas fa-eye me-2"></i>View Details
                        </button>
                        <button type="button" class="btn btn-success" onclick="loadSelectedTemplate()" style="border-radius: 8px; padding: 8px 16px;">
                            <i class="fas fa-download me-2"></i>Load Template
                        </button>
                        <button type="button" class="btn btn-danger" onclick="deleteSelectedTemplate()" style="border-radius: 8px; padding: 8px 16px;">
                            <i class="fas fa-trash me-2"></i>Delete Template
                        </button>
                        <button type="button" class="btn btn-secondary" onclick="closeTemplateSelection()" style="border-radius: 8px; padding: 8px 16px;">
                            <i class="fas fa-times me-2"></i>Cancel
                        </button>
                    </div>
                </div>
            `;
            
            const formContainer = document.createElement('div');
            formContainer.innerHTML = formHTML;
            messageBubble.appendChild(formContainer);
            
            // Add event listener to dropdown for automatic popup on selection
            setTimeout(() => {
                const templateSelect = document.getElementById('templateSelect');
                if (templateSelect) {
                    templateSelect.addEventListener('change', function() {
                        if (this.value) {
                            // Automatically show popup when template is selected
                            handleTemplateSelection();
                        }
                    });
                }
            }, 100);
        }
    }
}

function handleTemplateSelection() {
    const templateSelect = document.getElementById('templateSelect');
    if (!templateSelect || !templateSelect.value) {
        showToast('Please select a template first', 'warning');
        return;
    }
    
    const selectedOption = templateSelect.options[templateSelect.selectedIndex];
    const templateId = selectedOption.value;
    const templateName = selectedOption.getAttribute('data-name');
    const customerName = selectedOption.getAttribute('data-customer');
    const itemsJson = selectedOption.getAttribute('data-items');
    const lastUsed = selectedOption.getAttribute('data-last-used');
    
    if (!itemsJson) {
        showToast('Template data not found', 'error');
        return;
    }
    
    try {
        const items = JSON.parse(itemsJson.replace(/&#39;/g, "'"));
        showTemplateDetailsModal(templateId, templateName, customerName, items, lastUsed);
    } catch (error) {
        console.error('Error parsing template items:', error);
        showToast('Error loading template details', 'error');
    }
}

function showTemplateDetailsModal(templateId, templateName, customerName, items, lastUsed) {
    // Create modal HTML
    const modalHTML = `
        <div class="modal fade" id="templateDetailsModal" tabindex="-1" aria-labelledby="templateDetailsModalLabel" aria-hidden="true">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header" style="background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); color: white;">
                        <h5 class="modal-title" id="templateDetailsModalLabel">
                            <i class="fas fa-file-alt me-2"></i>Template Details: ${templateName}
                        </h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <div class="mb-3">
                            <strong>Customer:</strong> ${customerName || 'N/A'}<br>
                            <strong>Last Used:</strong> ${new Date(lastUsed).toLocaleDateString()}<br>
                            <strong>Total Items:</strong> ${items.length} products
                        </div>
                        <div class="table-responsive">
                            <table class="table table-bordered table-hover">
                                <thead style="background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);">
                                    <tr>
                                        <th style="padding: 10px; border: 1px solid #dee2e6; font-weight: 600;">Product Name</th>
                                        <th style="padding: 10px; border: 1px solid #dee2e6; font-weight: 600; text-align: center;">Quantity</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${items.map(item => `
                                        <tr>
                                            <td style="padding: 10px; border: 1px solid #dee2e6;">${item.product_name || item.product_code || 'Unknown'}</td>
                                            <td style="padding: 10px; border: 1px solid #dee2e6; text-align: center; font-weight: 600;">${item.quantity}</td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                        <button type="button" class="btn btn-success" onclick="loadOrderTemplate('${templateId}'); bootstrap.Modal.getInstance(document.getElementById('templateDetailsModal')).hide();">
                            <i class="fas fa-download me-2"></i>Load Template
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Remove existing modal if any
    const existingModal = document.getElementById('templateDetailsModal');
    if (existingModal) {
        existingModal.remove();
    }
    
    // Add modal to body
    const modalContainer = document.createElement('div');
    modalContainer.innerHTML = modalHTML;
    document.body.appendChild(modalContainer);
    
    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('templateDetailsModal'));
    modal.show();
    
    // Clean up when modal is hidden
    document.getElementById('templateDetailsModal').addEventListener('hidden.bs.modal', function() {
        this.remove();
    });
}

function loadSelectedTemplate() {
    const templateSelect = document.getElementById('templateSelect');
    if (!templateSelect || !templateSelect.value) {
        showToast('Please select a template first', 'warning');
        return;
    }
    
    const templateId = templateSelect.value;
    loadOrderTemplate(templateId);
    
    // Close template selection
    closeTemplateSelection();
}

function deleteSelectedTemplate() {
    const templateSelect = document.getElementById('templateSelect');
    if (!templateSelect || !templateSelect.value) {
        showToast('Please select a template first', 'warning');
        return;
    }
    
    const selectedOption = templateSelect.options[templateSelect.selectedIndex];
    const templateName = selectedOption.getAttribute('data-name');
    
    if (confirm(`Are you sure you want to delete the template "${templateName}"?`)) {
        const templateId = templateSelect.value;
        deleteOrderTemplate(templateId);
        
        // Refresh template selection
        setTimeout(() => {
            closeTemplateSelection();
            showOrderTemplates();
        }, 500);
    }
}

function closeTemplateSelection() {
    const templateContainer = document.querySelector('.template-selection-container');
    if (templateContainer) {
        templateContainer.style.transition = 'opacity 0.3s ease';
        templateContainer.style.opacity = '0';
        setTimeout(() => {
            templateContainer.remove();
        }, 300);
    }
    
    // Show default action buttons
    setTimeout(() => {
        showActionButtons([
            {'text': 'Place Order', 'action': 'place_order'},
            {'text': 'View Open Order', 'action': 'open_order'},
            {'text': 'Company Info', 'action': 'company_info'},
            {'text': 'Product Info', 'action': 'product_info'}
        ]);
    }, 350);
}

// Save current cart as template
async function saveCartAsTemplate() {
    try {
        // Get current cart
        const response = await fetch('/enhanced-chat/cart');
        const data = await response.json();
        
        if (!data.cart_items || data.cart_items.length === 0) {
            showToast('Cart is empty. Add items to cart before saving as template.', 'error');
            return;
        }
        
        // Get customer info - try multiple sources
        let customerId = data.customer_id || null;
        let customerName = data.customer_name || '';
        
        // If not in cart response, try to get from the order message or session
        if (!customerName) {
            // Look for customer name in recent bot messages
            const messagesDiv = document.getElementById('chatMessages');
            if (messagesDiv) {
                const botMessages = messagesDiv.querySelectorAll('.message.bot');
                for (let i = botMessages.length - 1; i >= 0; i--) {
                    const messageText = botMessages[i].textContent || '';
                    const match = messageText.match(/Ordering for:\s*([^(]+)\s*\(/);
                    if (match && match[1]) {
                        customerName = match[1].trim();
                        break;
                    }
                }
            }
        }
        
        // Prompt for template name
        const templateName = prompt('Enter a name for this template:');
        if (!templateName || !templateName.trim()) {
            return;
        }
        
        // Prepare items for template (without customer_name in each item)
        const items = data.cart_items.map(item => ({
            product_id: item.product_id,
            product_name: item.product_name,
            product_code: item.product_code,
            quantity: item.paid_quantity || item.quantity || item.total_quantity || 0
        }));
        
        // Save template with customer name as separate parameter
        if (saveOrderTemplate(templateName.trim(), customerId, items, customerName)) {
            // Close cart modal
            const cartModal = bootstrap.Modal.getInstance(document.getElementById('cartModal'));
            if (cartModal) {
                cartModal.hide();
            }
        }
    } catch (error) {
        console.error('Error saving cart as template:', error);
        showToast('Error saving template', 'error');
    }
}

// Load delivery partners for dealer to select
async function loadDeliveryPartners(orderId) {
    try {
        console.log(`🔍 Loading delivery partners for order ${orderId}...`);
        const response = await fetch('/enhanced-chat/api/delivery-partners', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            console.error(`❌ API error: ${response.status} ${response.statusText}`);
            const errorText = await response.text();
            console.error('Error response:', errorText);
            throw new Error(`API error: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('📦 Delivery partners API response:', data);
        
        if (data.success && data.delivery_partners) {
            const select = document.getElementById(`delivery_partner_${orderId}`);
            if (select) {
                // Clear existing options except the first one
                select.innerHTML = '<option value="">-- Select Delivery Partner --</option>';
                
                if (data.delivery_partners.length > 0) {
                    // Add delivery partners
                    data.delivery_partners.forEach(partner => {
                        const option = document.createElement('option');
                        option.value = partner.id;
                        option.textContent = `${partner.name} (${partner.unique_id})`;
                        select.appendChild(option);
                    });
                    console.log(`✅ Loaded ${data.delivery_partners.length} delivery partner(s) for area: ${data.area || 'unknown'}`);
                } else {
                    // No delivery partners found
                    const noPartnersOption = document.createElement('option');
                    noPartnersOption.value = '';
                    noPartnersOption.textContent = '⚠️ No delivery partners available for this area';
                    noPartnersOption.disabled = true;
                    select.appendChild(noPartnersOption);
                    console.warn(`⚠️ No delivery partners found for area: ${data.area || 'unknown'}`);
                }
            } else {
                console.error(`❌ Delivery partner select element not found: delivery_partner_${orderId}`);
            }
        } else {
            console.error('❌ Failed to load delivery partners:', data.error);
            const select = document.getElementById(`delivery_partner_${orderId}`);
            if (select) {
                const errorOption = document.createElement('option');
                errorOption.value = '';
                errorOption.textContent = `⚠️ ${data.error || 'No delivery partners found'}`;
                errorOption.disabled = true;
                select.appendChild(errorOption);
            }
        }
    } catch (error) {
        console.error('Error loading delivery partners:', error);
        const select = document.getElementById(`delivery_partner_${orderId}`);
        if (select) {
            const errorOption = document.createElement('option');
            errorOption.value = '';
            errorOption.textContent = '⚠️ Error loading delivery partners';
            errorOption.disabled = true;
            select.appendChild(errorOption);
        }
    }
}

// Delivery Partner Dashboard Functions
async function showDeliveryPartnerDashboard() {
    try {
        const response = await fetch('/enhanced-chat/api/delivery-partner/orders', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            if (data.orders.length === 0) {
                addMessage('📦 **No Orders Assigned**\n\nYou currently have no orders assigned for delivery.', 'bot');
                const t_func = (typeof t !== 'undefined') ? t : (key) => key;
                showActionButtons([
                    { text: '🔄 Refresh Orders', action: 'delivery_dashboard' },
                    { text: t_func('buttons.backToHome'), action: 'home' }
                ]);
            } else {
                // Store orders data globally for filtering
                window.deliveryPartnerOrders = data.orders;
                
                // Show initial message
                addMessage(`📦 **Track Delivery Orders**\n\nYou have **${data.orders.length}** order(s) assigned for delivery. Please select an order to view details.`, 'bot');
                
                // Add order selection form with filters
                addDeliveryPartnerOrderSelectionForm(data.orders);
                
                const t_func = (typeof t !== 'undefined') ? t : (key) => key;
                showActionButtons([
                    { text: '🔄 Refresh Orders', action: 'delivery_dashboard' },
                    { text: t_func('buttons.backToHome'), action: 'home' }
                ]);
            }
        } else {
            addMessage(`❌ Error: ${data.error}`, 'bot', 'error');
        }
    } catch (error) {
        console.error('Error loading delivery partner dashboard:', error);
        addMessage('❌ Error loading orders. Please try again.', 'bot', 'error');
    }
}

// Add order selection form for delivery partners
function addDeliveryPartnerOrderSelectionForm(orders) {
    const messagesDiv = document.getElementById('chatMessages');
    if (!messagesDiv) {
        console.error('Chat messages container not found');
        return;
    }
    
    // Get last bot message
    const botMessages = messagesDiv.querySelectorAll('.message.bot');
    const lastBotMessage = botMessages[botMessages.length - 1];
    
    if (!lastBotMessage) {
        console.error('Last bot message not found');
        return;
    }
    
    // Create form container
    const formContainer = document.createElement('div');
    formContainer.className = 'delivery-partner-order-selection-container';
    formContainer.style.cssText = 'width: 100%; margin-top: 15px; animation: slideInFromBottom 0.3s ease-out;';
    
    // Get unique dates and statuses for filters
    const uniqueDates = [...new Set(orders.map(o => new Date(o.order_date).toISOString().split('T')[0]))].sort().reverse();
    const uniqueStatuses = [...new Set(orders.map(o => o.status))].sort();
    
    // Build HTML for filters and order selection
    let formHTML = `
        <div class="card border-0 shadow-sm" style="background: rgba(255, 255, 255, 0.98); border-radius: 12px; padding: 20px;">
            <h6 class="mb-3" style="color: #2563eb; font-weight: 600;">
                <i class="fas fa-filter me-2"></i>Filters & Order Selection
            </h6>
            
            <!-- Filters - Stacked Vertically -->
            <div class="mb-3">
                <label for="dp_statusFilter" class="form-label" style="font-weight: 600; color: #1e40af; font-size: 0.875rem; margin-bottom: 8px;">
                    <i class="fas fa-tag me-1"></i>Filter by Status
                </label>
                <select class="form-select" id="dp_statusFilter" onchange="filterDeliveryPartnerOrders()"
                        style="border-radius: 8px; border: 2px solid #e5e7eb; padding: 10px;">
                    <option value="">All Statuses</option>
                    ${uniqueStatuses.map(status => `
                        <option value="${status}">${(status || 'confirmed').replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}</option>
                    `).join('')}
                </select>
            </div>
            
            <div class="mb-3">
                <label for="dp_dateFilter" class="form-label" style="font-weight: 600; color: #1e40af; font-size: 0.875rem; margin-bottom: 8px;">
                    <i class="fas fa-calendar me-1"></i>Filter by Date
                </label>
                <select class="form-select" id="dp_dateFilter" onchange="filterDeliveryPartnerOrders()"
                        style="border-radius: 8px; border: 2px solid #e5e7eb; padding: 10px;">
                    <option value="">All Dates</option>
                    ${uniqueDates.map(date => `
                        <option value="${date}">${new Date(date).toLocaleDateString()}</option>
                    `).join('')}
                </select>
            </div>
            
            <div class="mb-3">
                <label for="dp_orderSelect" class="form-label" style="font-weight: 600; color: #1e40af; font-size: 0.875rem; margin-bottom: 8px;">
                    <i class="fas fa-list me-1"></i>Select Order <span style="color: #dc2626;">*</span>
                </label>
                <select class="form-select form-select-lg" id="dp_orderSelect" onchange="loadDeliveryPartnerOrderDetails()" required
                        style="border-radius: 10px; border: 2px solid #3b82f6; padding: 12px; font-size: 0.95rem;">
                    <option value="">-- Select an Order --</option>
                    ${orders.map(order => {
                        const statusBadge = order.status === 'confirmed' ? '🟡' : order.status === 'in_transit' ? '🟠' : '🔵';
                        const dateStr = new Date(order.order_date).toLocaleDateString();
                        return `<option value="${order.order_id}" data-order-index="${orders.indexOf(order)}">
                            ${order.order_id} ${statusBadge} - ${dateStr} - ${(order.total_amount || 0).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})} MMK
                        </option>`;
                    }).join('')}
                </select>
            </div>
            
            <!-- Order Details Container (shown after selection) -->
            <div id="dp_orderDetailsContainer" style="display: none; margin-top: 20px; padding: 15px; background: #f9fafb; border-radius: 8px;">
                <!-- Order details will be loaded here -->
            </div>
        </div>
    `;
    
    formContainer.innerHTML = formHTML;
    
    // Find message bubble and append form
    let messageBubble = lastBotMessage.querySelector('.message-bubble .bg-light');
    if (!messageBubble) {
        messageBubble = lastBotMessage.querySelector('.message-bubble');
    }
    if (!messageBubble) {
        messageBubble = lastBotMessage;
    }
    
    messageBubble.appendChild(formContainer);
    
    // Store orders data in form container for filtering
    formContainer._originalOrders = orders;
    formContainer._filteredOrders = orders;
    
    // Scroll to bottom
    messagesDiv.scrollTo({
        top: messagesDiv.scrollHeight,
        behavior: 'smooth'
    });
}

// Filter delivery partner orders
function filterDeliveryPartnerOrders() {
    const formContainer = document.querySelector('.delivery-partner-order-selection-container');
    if (!formContainer || !formContainer._originalOrders) {
        return;
    }
    
    const statusFilter = document.getElementById('dp_statusFilter')?.value || '';
    const dateFilter = document.getElementById('dp_dateFilter')?.value || '';
    const orderSelect = document.getElementById('dp_orderSelect');
    
    if (!orderSelect) return;
    
    let filteredOrders = formContainer._originalOrders;
    
    // Apply status filter
    if (statusFilter) {
        filteredOrders = filteredOrders.filter(order => order.status === statusFilter);
    }
    
    // Apply date filter
    if (dateFilter) {
        filteredOrders = filteredOrders.filter(order => {
            const orderDate = new Date(order.order_date).toISOString().split('T')[0];
            return orderDate === dateFilter;
        });
    }
    
    // Update dropdown options
    const selectedValue = orderSelect.value;
    orderSelect.innerHTML = '<option value="">-- Select an Order --</option>';
    
    filteredOrders.forEach(order => {
        const statusBadge = order.status === 'confirmed' ? '🟡' : order.status === 'in_transit' ? '🟠' : '🔵';
        const dateStr = new Date(order.order_date).toLocaleDateString();
        const option = document.createElement('option');
        option.value = order.order_id;
        option.setAttribute('data-order-index', formContainer._originalOrders.indexOf(order).toString());
        option.textContent = `${order.order_id} ${statusBadge} - ${dateStr} - ${(order.total_amount || 0).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})} MMK`;
        orderSelect.appendChild(option);
    });
    
    // Restore selection if still available
    if (selectedValue) {
        const option = Array.from(orderSelect.options).find(opt => opt.value === selectedValue);
        if (option) {
            orderSelect.value = selectedValue;
            loadDeliveryPartnerOrderDetails();
        } else {
            // Clear order details if selected order is filtered out
            const detailsContainer = document.getElementById('dp_orderDetailsContainer');
            if (detailsContainer) {
                detailsContainer.style.display = 'none';
                detailsContainer.innerHTML = '';
            }
        }
    }
    
    // Store filtered orders
    formContainer._filteredOrders = filteredOrders;
}

// Load order details when order is selected
function loadDeliveryPartnerOrderDetails() {
    const orderSelect = document.getElementById('dp_orderSelect');
    const detailsContainer = document.getElementById('dp_orderDetailsContainer');
    
    if (!orderSelect || !detailsContainer) {
        return;
    }
    
    const selectedOrderId = orderSelect.value;
    
    if (!selectedOrderId) {
        detailsContainer.style.display = 'none';
        detailsContainer.innerHTML = '';
        return;
    }
    
    // Get order data
    const formContainer = document.querySelector('.delivery-partner-order-selection-container');
    if (!formContainer || !formContainer._originalOrders) {
        return;
    }
    
    const order = formContainer._originalOrders.find(o => o.order_id === selectedOrderId);
    
    if (!order) {
        detailsContainer.innerHTML = '<p class="text-danger">Order not found.</p>';
        detailsContainer.style.display = 'block';
        return;
    }
    
    // Build order details HTML
    const statusBadge = order.status === 'confirmed' ? '🟡' : order.status === 'in_transit' ? '🟠' : '🔵';
    const dateStr = new Date(order.order_date).toLocaleDateString();
    
    let detailsHTML = `
        <div class="delivery-order-details">
            <h6 class="mb-3" style="color: #059669; font-weight: 600; border-bottom: 2px solid #059669; padding-bottom: 10px;">
                <i class="fas fa-box-open me-2"></i>Order Details
            </h6>
            
            <!-- Order Information - First -->
            <div class="mb-3">
                <div class="info-box" style="background: #eff6ff; padding: 15px; border-radius: 8px; border-left: 4px solid #3b82f6;">
                    <p class="mb-2"><strong><i class="fas fa-hashtag me-1"></i>Order ID:</strong> ${order.order_id} ${statusBadge}</p>
                    <p class="mb-2"><strong><i class="fas fa-calendar me-1"></i>Date:</strong> ${dateStr}</p>
                    <p class="mb-2"><strong><i class="fas fa-tag me-1"></i>Status:</strong> ${order.status_display || order.status}</p>
                    <p class="mb-0"><strong><i class="fas fa-money-bill-wave me-1"></i>Total Amount:</strong> ${(order.total_amount || 0).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})} MMK</p>
                </div>
            </div>
            
            <!-- Customer Details - Second -->
            <div class="mb-3">
                <h6 style="color: #10b981; font-weight: 600; margin-bottom: 10px;">
                    <i class="fas fa-user me-2"></i>Customer Details
                </h6>
                <div class="info-box" style="background: #f0fdf4; padding: 15px; border-radius: 8px; border-left: 4px solid #10b981;">
                    <p class="mb-2"><strong><i class="fas fa-user-circle me-1"></i>Customer Name:</strong> ${order.customer.name || 'N/A'}</p>
                    <p class="mb-2"><strong><i class="fas fa-phone me-1"></i>Phone:</strong> ${order.customer.phone || 'N/A'}</p>
                    <p class="mb-0"><strong><i class="fas fa-map-marker-alt me-1"></i>Address:</strong> ${order.customer.address || 'Address not provided'}</p>
                </div>
            </div>
            
            <!-- Items to Deliver - Third -->
            <div class="mb-3">
                <h6 style="color: #1e40af; font-weight: 600; margin-bottom: 10px;">
                    <i class="fas fa-list-ul me-2"></i>Items to Deliver
                </h6>
                <div class="table-responsive">
                    <table class="table table-bordered" style="font-size: 0.9rem;">
                        <thead style="background: #3b82f6; color: white;">
                            <tr>
                                <th>Product</th>
                                <th style="text-align: center;">Quantity</th>
                                <th style="text-align: center;">FOC</th>
                                <th style="text-align: right;">Unit Price</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${order.items.map(item => {
                                const paidQty = item.quantity || 0;
                                const freeQty = item.free_quantity || 0;
                                const totalQty = paidQty + freeQty;
                                return `
                                    <tr>
                                        <td>${item.product_name} (${item.product_code})</td>
                                        <td style="text-align: center;">${paidQty}</td>
                                        <td style="text-align: center; color: #10b981;">${freeQty > 0 ? `+${freeQty}` : '-'}</td>
                                        <td style="text-align: right;">${(item.unit_price || 0).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})} MMK</td>
                                    </tr>
                                `;
                            }).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
            
            <!-- Mark as Delivered Button - Styled like action buttons -->
            <div class="mt-4" style="display: flex; justify-content: center; gap: 10px;">
                <button class="btn btn-success action-btn" onclick="markOrderDelivered('${order.order_id}')" 
                        style="background: linear-gradient(135deg, rgba(16, 185, 129, 0.95) 0%, rgba(5, 150, 105, 0.95) 100%);
                               color: white;
                               border: none;
                               padding: 12px 24px;
                               font-size: 0.9rem;
                               font-weight: 600;
                               border-radius: 10px;
                               box-shadow: 0 4px 12px rgba(16, 185, 129, 0.25), 0 2px 4px rgba(16, 185, 129, 0.15);
                               transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                               min-width: 180px;
                               display: flex;
                               align-items: center;
                               justify-content: center;
                               gap: 8px;
                               cursor: pointer;"
                        onmouseover="this.style.transform='translateY(-3px) scale(1.02)'; this.style.boxShadow='0 6px 20px rgba(16, 185, 129, 0.4)';"
                        onmouseout="this.style.transform='translateY(0) scale(1)'; this.style.boxShadow='0 4px 12px rgba(16, 185, 129, 0.25), 0 2px 4px rgba(16, 185, 129, 0.15)';">
                    <i class="fas fa-check-circle"></i>
                    <span>Mark as Delivered</span>
                </button>
            </div>
        </div>
    `;
    
    detailsContainer.innerHTML = detailsHTML;
    detailsContainer.style.display = 'block';
    
    // Scroll to details
    detailsContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

async function markOrderDelivered(orderId) {
    if (!confirm(`Are you sure you want to mark order ${orderId} as delivered?`)) {
        return;
    }
    
    try {
        // Hide/remove the selection form immediately
        const formContainer = document.querySelector('.delivery-partner-order-selection-container');
        if (formContainer) {
            formContainer.style.transition = 'opacity 0.3s ease-out';
            formContainer.style.opacity = '0';
            setTimeout(() => {
                formContainer.remove();
            }, 300);
        }
        
        // Hide order details container
        const detailsContainer = document.getElementById('dp_orderDetailsContainer');
        if (detailsContainer) {
            detailsContainer.style.display = 'none';
        }
        
        const response = await fetch('/enhanced-chat/api/delivery-partner/mark-delivered', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ order_id: orderId })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Show success message
            addMessage(`✅ **Order Delivered Successfully!**\n\n${data.message}\n\nThe stock has been moved from out_for_delivery to sold, and notifications have been sent to the MR and dealer.`, 'bot');
            
            // Check if there are more orders assigned to this DP
            setTimeout(async () => {
                try {
                    const checkResponse = await fetch('/enhanced-chat/api/delivery-partner/orders', {
                        method: 'GET',
                        headers: {
                            'Content-Type': 'application/json'
                        }
                    });
                    
                    const checkData = await checkResponse.json();
                    
                    if (checkData.success) {
                        if (checkData.orders.length > 0) {
                            // There are more orders - show action buttons (Track Orders and Help)
                            const t_func = (typeof t !== 'undefined') ? t : (key) => key;
                            showActionButtons([
                                { text: 'Track Orders', action: 'delivery_dashboard' },
                                { text: 'Help', action: 'help' }
                            ]);
                        } else {
                            // No more orders - just show success message
                            addMessage('📦 You have no more orders assigned for delivery.', 'bot');
                            // No action buttons needed - just the success message
                        }
                    }
                } catch (error) {
                    console.error('Error checking remaining orders:', error);
                    // On error, still show action buttons
                    showActionButtons([
                        { text: 'Track Orders', action: 'delivery_dashboard' },
                        { text: 'Help', action: 'help' }
                    ]);
                }
            }, 500);
        } else {
            addMessage(`❌ Error: ${data.message}`, 'bot', 'error');
            // On error, restore the form
            if (formContainer && !formContainer.parentElement) {
                const messagesDiv = document.getElementById('chatMessages');
                const botMessages = messagesDiv.querySelectorAll('.message.bot');
                const lastBotMessage = botMessages[botMessages.length - 1];
                if (lastBotMessage) {
                    let messageBubble = lastBotMessage.querySelector('.message-bubble .bg-light');
                    if (!messageBubble) {
                        messageBubble = lastBotMessage.querySelector('.message-bubble');
                    }
                    if (!messageBubble) {
                        messageBubble = lastBotMessage;
                    }
                    messageBubble.appendChild(formContainer);
                }
            }
        }
    } catch (error) {
        console.error('Error marking order as delivered:', error);
        addMessage('❌ Error marking order as delivered. Please try again.', 'bot', 'error');
    }
}

// Make functions globally available
window.loadDeliveryPartners = loadDeliveryPartners;
window.showDeliveryPartnerDashboard = showDeliveryPartnerDashboard;
window.markOrderDelivered = markOrderDelivered;
window.filterDeliveryPartnerOrders = filterDeliveryPartnerOrders;
window.loadDeliveryPartnerOrderDetails = loadDeliveryPartnerOrderDetails;

// Make template functions globally available
window.saveOrderTemplate = saveOrderTemplate;
window.loadOrderTemplate = loadOrderTemplate;
window.deleteOrderTemplate = deleteOrderTemplate;
window.showOrderTemplates = showOrderTemplates;
window.handleTemplateSelection = handleTemplateSelection;
window.showTemplateDetailsModal = showTemplateDetailsModal;
window.loadSelectedTemplate = loadSelectedTemplate;
window.deleteSelectedTemplate = deleteSelectedTemplate;
window.closeTemplateSelection = closeTemplateSelection;
window.saveCartAsTemplate = saveCartAsTemplate;

// ============= ADVANCED SEARCH =============

function performAdvancedSearch(query, filters = {}) {
    // Enhanced search with multiple criteria
    const searchParams = {
        query: query,
        filters: filters,
        date_range: filters.date_range || null,
        status: filters.status || null,
        customer: filters.customer || null,
        product: filters.product || null
    };
    
    // Send to backend for advanced search
    fetch('/enhanced-chat/advanced_search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(searchParams)
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            if (data.orders && data.orders.length > 0) {
                addMessage(`Found ${data.orders.length} order(s) matching your search.`, 'bot');
                showOrdersTable(data.orders);
            } else if (data.products && data.products.length > 0) {
                addMessage(`Found ${data.products.length} product(s) matching your search.`, 'bot');
                showProductTable(data.products);
            } else {
                addMessage('No results found for your search.', 'bot');
            }
        } else {
            addMessage(data.error || 'Search failed', 'bot', 'error');
        }
    })
    .catch(error => {
        console.error('Advanced search error:', error);
        addMessage('Error performing search', 'bot', 'error');
    });
}

window.performAdvancedSearch = performAdvancedSearch;
window.sendMessage = sendMessage;
