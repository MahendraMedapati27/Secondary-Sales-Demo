// i18next Configuration for Multi-language Support
// Languages: English, Burmese, Hindi, Telugu

// Initialize i18next
let i18n;

function initializeI18n() {
    // Wait for i18next to be loaded
    if (typeof i18next === 'undefined') {
        console.warn('i18next not loaded, will retry');
        setTimeout(initializeI18n, 100);
        return;
    }
    
    if (!i18n) {
        i18n = i18next.createInstance();
    }
    
    i18n.init({
    resources: {
        en: {
            translation: {
                buttons: {
                    userInfo: "User Info",
                    dashboard: "Dashboard",
                    reset: "Reset",
                    cart: "Cart",
                    placeOrder: "Place Order",
                    viewOrder: "View Open Order",
                    productInfo: "Product Info",
                    companyInfo: "Company Info",
                    trackOrder: "Track Order",
                    getHelp: "Get Help",
                    addItems: "Add Items",
                    confirmOrder: "Confirm Order",
                    cancelOrder: "Cancel Order",
                    rejectOrder: "Reject Order",
                    viewAllOrders: "View All Orders",
                    print: "Print",
                    backToHome: "Back to Home",
                    cancelOrderAction: "Cancel Order",
                    trackAnotherOrder: "Track Another Order",
                    placeNewOrder: "Place New Order",
                    modifyCart: "Modify Cart",
                    addMoreItems: "Add More Items",
                    viewCart: "View Cart"
                },
                messages: {
                    welcome: "Welcome to HV (Powered by Quantum Blue AI)",
                    loading: "Loading...",
                    error: "An error occurred",
                    searchProducts: "Search Products",
                    availableProducts: "Available Products",
                    productInformation: "Product Information",
                    pleaseSearch: "Please search for a product or select from the list below:",
                    loadingProductInfo: "Loading product information...",
                    packSize: "Pack Size",
                    genericName: "Generic Name / Composition",
                    therapeuticClass: "Therapeutic Class",
                    keyUses: "Key Uses",
                    mechanismOfAction: "Mechanism of Action",
                    dosage: "Dosage & Administration",
                    safetyProfile: "Safety Profile & Common Side Effects",
                    description: "Description",
                    productInfo: "Product Information",
                    placeOrder: "I want to place an order",
                    trackOrder: "I want to track an order",
                    companyInfo: "Tell me about the company",
                    showCart: "Show me my cart",
                    addMoreItems: "I want to add more items to my order",
                    needHelp: "I need help",
                    changeCustomer: "Change customer",
                    selectCustomer: "Select Customer",
                    addNewCustomer: "Add New Customer",
                    confirmOrder: "confirm my order",
                    showStock: "Show me stock status",
                    editCart: "Edit cart",
                    placeOrderFinal: "Place order",
                    showPendingStock: "show pending stock",
                    generateReport: "generate report",
                    selectOrderFromDropdown: "Select an order from the dropdown to view details",
                    selectOrderToTrack: "Select an order to track"
                },
                labels: {
                    searchProducts: "Search Products:",
                    availableProducts: "Available Products:",
                    typeToSearch: "Type product name to search...",
                    noProducts: "No products available",
                    orderId: "Order ID",
                    status: "Status",
                    totalItems: "Total Items",
                    totalAmount: "Total Amount",
                    customer: "Customer",
                    date: "Date",
                    productName: "Product Name",
                    quantity: "Quantity",
                    foc: "FOC",
                    unitPrice: "Unit Price",
                    totalPrice: "Total Price",
                    orderItems: "Order Items",
                    units: "units",
                    orderDetails: "Order Details",
                    orderInformation: "Order Information",
                    paymentSummary: "Payment Summary",
                    subtotal: "Subtotal",
                    tax: "Tax",
                    grandTotal: "Grand Total",
                    expiryDate: "Expiry Date",
                    lotNumber: "Lot Number",
                    reason: "Reason",
                    editOrderItems: "Edit Order Items (Optional)",
                    quantityOrdered: "Quantity (Ordered:",
                    enterQuantity: "Enter quantity",
                    enterLotNumber: "Enter lot number",
                    reasonForAdjustment: "Reason for adjustment",
                    orderManagementDashboard: "Order Management Dashboard",
                    selectOrderToTrack: "Select Order to Track",
                    filterByMRName: "Filter by MR Name:",
                    filterByCustomer: "Filter by Customer:",
                    filterByDate: "Filter by Date:",
                    filterByStatus: "Filter by Status:",
                    chooseAnOrder: "Choose an order:",
                    allMRs: "-- All MRs --",
                    allCustomers: "-- All Customers --",
                    allDates: "-- All Dates --",
                    allStatuses: "-- All Statuses --",
                    selectOrder: "-- Select Order --",
                    exportExcel: "Export Excel",
                    selected: "selected",
                    confirmSelected: "Confirm Selected",
                    rejectSelected: "Reject Selected",
                    clear: "Clear",
                    viewOrderDetails: "View Order Details",
                    cancel: "Cancel",
                    user: "User",
                    area: "Area",
                    type: "Type",
                    adjustQuantitiesInfo: "You can adjust quantities, lot numbers, and expiry dates before confirming. If you reduce quantity, the remaining will be moved to pending orders. Leave unchanged to use original values.",
                    adjustQuantityInfo: "Adjust if different from ordered quantity. If reduced, remaining will be moved to pending orders.",
                    lotNumberInfo: "Optional: Lot/Batch number for this item",
                    expiryDateInfo: "Select expiry date for this item",
                    reasonInfo: "Optional: Reason for quantity/date/lot change. MR will be notified if quantity is changed and reason is provided.",
                    fromDatabase: "(from database)"
                },
                placeholders: {
                    typeMessage: "Type your message..."
                }
            }
        },
        my: { // Burmese
            translation: {
                buttons: {
                    userInfo: "အသုံးပြုသူ အချက်အလက်",
                    dashboard: "ဒက်ရှ်ဘုတ်",
                    reset: "ပြန်လည်သတ်မှတ်",
                    cart: "ခြင်းတောင်း",
                    placeOrder: "အော်ဒါတင်ရန်",
                    viewOrder: "ဖွင့်ထားသော အော်ဒါကို ကြည့်ရန်",
                    productInfo: "ထုတ်ကုန် အချက်အလက်",
                    companyInfo: "ကုမ္ပဏီ အချက်အလက်",
                    trackOrder: "အော်ဒါကို ခြေရာခံရန်",
                    getHelp: "အကူအညီရယူရန်",
                    addItems: "ပစ္စည်းများ ထည့်ရန်",
                    confirmOrder: "အော်ဒါကို အတည်ပြုရန်",
                    cancelOrder: "အော်ဒါကို ပယ်ဖျက်ရန်",
                    rejectOrder: "အော်ဒါကို ငြင်းဆိုရန်",
                    viewAllOrders: "အော်ဒါအားလုံးကို ကြည့်ရန်",
                    print: "ပုံနှိပ်ရန်",
                    backToHome: "ပင်မစာမျက်နှာသို့ ပြန်ရန်",
                    cancelOrderAction: "အော်ဒါကို ပယ်ဖျက်ရန်",
                    trackAnotherOrder: "အခြား အော်ဒါကို ခြေရာခံရန်",
                    placeNewOrder: "အော်ဒါအသစ် တင်ရန်",
                    modifyCart: "ခြင်းတောင်းကို ပြင်ဆင်ရန်",
                    addMoreItems: "ပိုမိုသော ပစ္စည်းများ ထည့်ရန်",
                    viewCart: "ခြင်းတောင်းကို ကြည့်ရန်"
                },
                messages: {
                    welcome: "HV သို့ ကြိုဆိုပါသည် (Quantum Blue AI မှ ပံ့ပိုးသည်)",
                    loading: "ဖွင့်နေသည်...",
                    error: "အမှားအယွင်း ဖြစ်ပွားခဲ့သည်",
                    searchProducts: "ထုတ်ကုန်များ ရှာဖွေရန်",
                    placeOrder: "အော်ဒါတင်လိုပါသည်",
                    trackOrder: "အော်ဒါကို ခြေရာခံလိုပါသည်",
                    companyInfo: "ကုမ္ပဏီအကြောင်း ပြောပြပါ",
                    showCart: "ကျွန်ုပ်၏ ခြင်းတောင်းကို ပြပါ",
                    addMoreItems: "ကျွန်ုပ်၏ အော်ဒါသို့ ပိုမိုသော ပစ္စည်းများ ထည့်လိုပါသည်",
                    needHelp: "ကျွန်ုပ်အား အကူအညီ လိုအပ်ပါသည်",
                    changeCustomer: "ဖောက်သည်ကို ပြောင်းလဲရန်",
                    selectCustomer: "ဖောက်သည်ကို ရွေးချယ်ရန်",
                    addNewCustomer: "ဖောက်သည်အသစ် ထည့်ရန်",
                    confirmOrder: "ကျွန်ုပ်၏ အော်ဒါကို အတည်ပြုရန်",
                    showStock: "စတော့ခ် အခြေအနေကို ပြပါ",
                    editCart: "ခြင်းတောင်းကို တည်းဖြတ်ရန်",
                    placeOrderFinal: "အော်ဒါတင်ရန်",
                    showPendingStock: "စောင့်ဆိုင်းနေသော စတော့ခ်ကို ပြပါ",
                    generateReport: "အစီရင်ခံစာ ထုတ်လုပ်ရန်",
                    selectOrderFromDropdown: "အော်ဒါတစ်ခုကို dropdown မှ ရွေးချယ်ပြီး အသေးစိတ်ကို ကြည့်ရန်",
                    selectOrderToTrack: "အော်ဒါတစ်ခုကို ခြေရာခံရန် ရွေးချယ်ပါ",
                    availableProducts: "ရရှိနိုင်သော ထုတ်ကုန်များ",
                    productInformation: "ထုတ်ကုန် အချက်အလက်",
                    pleaseSearch: "ထုတ်ကုန်တစ်ခုကို ရှာဖွေရန် သို့မဟုတ် အောက်ပါစာရင်းမှ ရွေးချယ်ရန်:",
                    loadingProductInfo: "ထုတ်ကုန် အချက်အလက်ကို ဖွင့်နေသည်...",
                    packSize: "ထုပ်ပိုးမှု အရွယ်အစား",
                    genericName: "ယေဘုယျ အမည် / ဖွဲ့စည်းပုံ",
                    therapeuticClass: "ကုထုံးဆိုင်ရာ အမျိုးအစား",
                    keyUses: "အဓိက အသုံးပြုမှုများ",
                    mechanismOfAction: "လုပ်ဆောင်ပုံ ယန္တရား",
                    dosage: "ဆေးသောက်ရမည့် ပမာဏနှင့် စီမံခန့်ခွဲမှု",
                    safetyProfile: "လုံခြုံမှု ပရိုဖိုင်နှင့် အဖြစ်များသော ဘေးထွက်ဆိုးကျိုးများ",
                    description: "ဖော်ပြချက်",
                    productInfo: "ထုတ်ကုန် အချက်အလက်"
                },
                labels: {
                    searchProducts: "ထုတ်ကုန်များ ရှာဖွေရန်:",
                    availableProducts: "ရရှိနိုင်သော ထုတ်ကုန်များ:",
                    typeToSearch: "ထုတ်ကုန် အမည်ကို ရိုက်ထည့်ရန်...",
                    noProducts: "ထုတ်ကုန်များ မရရှိနိုင်ပါ",
                    orderId: "အော်ဒါ ID",
                    status: "အခြေအနေ",
                    totalItems: "စုစုပေါင်း ပစ္စည်းများ",
                    totalAmount: "စုစုပေါင်း ငွေပမာဏ",
                    customer: "ဖောက်သည်",
                    date: "ရက်စွဲ",
                    productName: "ထုတ်ကုန် အမည်",
                    quantity: "အရေအတွက်",
                    foc: "FOC",
                    unitPrice: "ယူနစ် စျေးနှုန်း",
                    totalPrice: "စုစုပေါင်း စျေးနှုန်း",
                    orderItems: "အော်ဒါ ပစ္စည်းများ",
                    units: "ယူနစ်",
                    orderDetails: "အော်ဒါ အသေးစိတ်",
                    orderInformation: "အော်ဒါ အချက်အလက်",
                    paymentSummary: "ငွေပေးချေမှု အကျဉ်းချုပ်",
                    subtotal: "အကြား စုစုပေါင်း",
                    tax: "အခွန်",
                    grandTotal: "စုစုပေါင်း စုစုပေါင်း",
                    expiryDate: "သက်တမ်းကုန်ဆုံးရက်",
                    lotNumber: "လော့နံပါတ်",
                    reason: "အကြပြချက်",
                    editOrderItems: "အော်ဒါ ပစ္စည်းများကို တည်းဖြတ်ရန် (ရွေးချယ်ရန်)",
                    quantityOrdered: "အရေအတွက် (မှာယူထားသော:",
                    enterQuantity: "အရေအတွက်ကို ထည့်သွင်းပါ",
                    enterLotNumber: "လော့နံပါတ်ကို ထည့်သွင်းပါ",
                    reasonForAdjustment: "ပြင်ဆင်မှု၏ အကြပြချက်"
                },
                placeholders: {
                    typeMessage: "သင့်စာကို ရိုက်ထည့်ပါ..."
                }
            }
        },
        hi: { // Hindi
            translation: {
                buttons: {
                    userInfo: "उपयोगकर्ता जानकारी",
                    dashboard: "डैशबोर्ड",
                    reset: "रीसेट",
                    cart: "कार्ट",
                    placeOrder: "ऑर्डर करें",
                    viewOrder: "खुला ऑर्डर देखें",
                    productInfo: "उत्पाद जानकारी",
                    companyInfo: "कंपनी जानकारी",
                    trackOrder: "ऑर्डर ट्रैक करें",
                    getHelp: "मदद लें",
                    addItems: "आइटम जोड़ें",
                    confirmOrder: "ऑर्डर पुष्टि करें",
                    cancelOrder: "ऑर्डर रद्द करें",
                    rejectOrder: "ऑर्डर अस्वीकार करें",
                    viewAllOrders: "सभी ऑर्डर देखें",
                    print: "प्रिंट",
                    backToHome: "होम पर वापस जाएं",
                    cancelOrderAction: "ऑर्डर रद्द करें",
                    trackAnotherOrder: "दूसरा ऑर्डर ट्रैक करें",
                    placeNewOrder: "नया ऑर्डर करें",
                    modifyCart: "कार्ट संशोधित करें",
                    addMoreItems: "और आइटम जोड़ें",
                    viewCart: "कार्ट देखें"
                },
                messages: {
                    welcome: "HV में आपका स्वागत है (क्वांटम ब्लू AI द्वारा संचालित)",
                    loading: "लोड हो रहा है...",
                    error: "एक त्रुटि हुई",
                    searchProducts: "उत्पाद खोजें",
                    placeOrder: "मैं एक ऑर्डर देना चाहता हूं",
                    trackOrder: "मैं एक ऑर्डर ट्रैक करना चाहता हूं",
                    companyInfo: "मुझे कंपनी के बारे में बताएं",
                    showCart: "मुझे मेरी कार्ट दिखाएं",
                    addMoreItems: "मैं अपने ऑर्डर में और आइटम जोड़ना चाहता हूं",
                    needHelp: "मुझे मदद चाहिए",
                    changeCustomer: "ग्राहक बदलें",
                    selectCustomer: "ग्राहक चुनें",
                    addNewCustomer: "नया ग्राहक जोड़ें",
                    confirmOrder: "मेरे ऑर्डर की पुष्टि करें",
                    showStock: "मुझे स्टॉक स्थिति दिखाएं",
                    editCart: "कार्ट संपादित करें",
                    placeOrderFinal: "ऑर्डर करें",
                    showPendingStock: "लंबित स्टॉक दिखाएं",
                    generateReport: "रिपोर्ट जेनरेट करें",
                    availableProducts: "उपलब्ध उत्पाद",
                    productInformation: "उत्पाद जानकारी",
                    pleaseSearch: "कृपया उत्पाद खोजें या नीचे दी गई सूची से चुनें:",
                    loadingProductInfo: "उत्पाद जानकारी लोड हो रही है...",
                    packSize: "पैक आकार",
                    genericName: "सामान्य नाम / संरचना",
                    therapeuticClass: "चिकित्सीय वर्ग",
                    keyUses: "मुख्य उपयोग",
                    mechanismOfAction: "कार्रवाई का तंत्र",
                    dosage: "खुराक और प्रशासन",
                    safetyProfile: "सुरक्षा प्रोफ़ाइल और सामान्य दुष्प्रभाव",
                    description: "विवरण",
                    productInfo: "उत्पाद जानकारी"
                },
                labels: {
                    searchProducts: "उत्पाद खोजें:",
                    availableProducts: "उपलब्ध उत्पाद:",
                    typeToSearch: "उत्पाद नाम टाइप करें...",
                    noProducts: "कोई उत्पाद उपलब्ध नहीं",
                    orderId: "ऑर्डर ID",
                    status: "स्थिति",
                    totalItems: "कुल आइटम",
                    totalAmount: "कुल राशि",
                    customer: "ग्राहक",
                    date: "तारीख",
                    productName: "उत्पाद नाम",
                    quantity: "मात्रा",
                    foc: "FOC",
                    unitPrice: "इकाई मूल्य",
                    totalPrice: "कुल मूल्य",
                    orderItems: "ऑर्डर आइटम",
                    units: "इकाइयाँ",
                    orderDetails: "ऑर्डर विवरण",
                    orderInformation: "ऑर्डर जानकारी",
                    paymentSummary: "भुगतान सारांश",
                    subtotal: "उप-योग",
                    tax: "कर",
                    grandTotal: "कुल योग",
                    expiryDate: "समाप्ति तिथि",
                    lotNumber: "लॉट नंबर",
                    reason: "कारण",
                    editOrderItems: "ऑर्डर आइटम संपादित करें (वैकल्पिक)",
                    quantityOrdered: "मात्रा (ऑर्डर किया गया:",
                    enterQuantity: "मात्रा दर्ज करें",
                    enterLotNumber: "लॉट नंबर दर्ज करें",
                    reasonForAdjustment: "समायोजन का कारण",
                    selectOrderFromDropdown: "विवरण देखने के लिए ड्रॉपडाउन से एक ऑर्डर चुनें, या कई ऑर्डर के लिए बल्क सेलेक्ट सक्षम करें",
                    selectOrderToTrack: "ट्रैक करने के लिए एक ऑर्डर चुनें"
                },
                labels: {
                    searchProducts: "उत्पाद खोजें:",
                    availableProducts: "उपलब्ध उत्पाद:",
                    typeToSearch: "उत्पाद नाम टाइप करें...",
                    noProducts: "कोई उत्पाद उपलब्ध नहीं",
                    orderId: "ऑर्डर ID",
                    status: "स्थिति",
                    totalItems: "कुल आइटम",
                    totalAmount: "कुल राशि",
                    customer: "ग्राहक",
                    date: "तारीख",
                    productName: "उत्पाद नाम",
                    quantity: "मात्रा",
                    foc: "FOC",
                    unitPrice: "इकाई मूल्य",
                    totalPrice: "कुल मूल्य",
                    orderItems: "ऑर्डर आइटम",
                    units: "इकाइयाँ",
                    orderDetails: "ऑर्डर विवरण",
                    orderInformation: "ऑर्डर जानकारी",
                    paymentSummary: "भुगतान सारांश",
                    subtotal: "उप-योग",
                    tax: "कर",
                    grandTotal: "कुल योग",
                    expiryDate: "समाप्ति तिथि",
                    lotNumber: "लॉट नंबर",
                    reason: "कारण",
                    editOrderItems: "ऑर्डर आइटम संपादित करें (वैकल्पिक)",
                    quantityOrdered: "मात्रा (ऑर्डर किया गया:",
                    enterQuantity: "मात्रा दर्ज करें",
                    enterLotNumber: "लॉट नंबर दर्ज करें",
                    reasonForAdjustment: "समायोजन का कारण",
                    orderManagementDashboard: "ऑर्डर प्रबंधन डैशबोर्ड",
                    selectOrderToTrack: "ट्रैक करने के लिए ऑर्डर चुनें",
                    filterByMRName: "MR नाम से फ़िल्टर करें:",
                    filterByCustomer: "ग्राहक से फ़िल्टर करें:",
                    filterByDate: "तारीख से फ़िल्टर करें:",
                    filterByStatus: "स्थिति से फ़िल्टर करें:",
                    chooseAnOrder: "एक ऑर्डर चुनें:",
                    allMRs: "-- सभी MR --",
                    allCustomers: "-- सभी ग्राहक --",
                    allDates: "-- सभी तारीखें --",
                    allStatuses: "-- सभी स्थितियां --",
                    selectOrder: "-- ऑर्डर चुनें --",
                    exportExcel: "एक्सेल निर्यात करें",
                    selected: "चयनित",
                    confirmSelected: "चयनित ऑर्डर पुष्टि करें",
                    rejectSelected: "चयनित ऑर्डर अस्वीकार करें",
                    clear: "साफ़ करें",
                    viewOrderDetails: "ऑर्डर विवरण देखें",
                    cancel: "रद्द करें",
                    user: "उपयोगकर्ता",
                    area: "क्षेत्र",
                    type: "प्रकार",
                    adjustQuantitiesInfo: "पुष्टि करने से पहले आप मात्रा, लॉट नंबर और समाप्ति तिथियां समायोजित कर सकते हैं। यदि आप मात्रा कम करते हैं, तो शेष को लंबित ऑर्डर में स्थानांतरित कर दिया जाएगा। मूल मानों का उपयोग करने के लिए अपरिवर्तित छोड़ दें।",
                    adjustQuantityInfo: "यदि ऑर्डर की गई मात्रा से अलग है तो समायोजित करें। यदि कम किया जाता है, तो शेष को लंबित ऑर्डर में स्थानांतरित कर दिया जाएगा।",
                    lotNumberInfo: "वैकल्पिक: इस आइटम के लिए लॉट/बैच नंबर",
                    expiryDateInfo: "इस आइटम के लिए समाप्ति तिथि चुनें",
                    reasonInfo: "वैकल्पिक: मात्रा/तारीख/लॉट परिवर्तन का कारण। यदि मात्रा बदली जाती है और कारण प्रदान किया जाता है, तो MR को सूचित किया जाएगा।",
                    fromDatabase: "(डेटाबेस से)"
                },
                placeholders: {
                    typeMessage: "अपना संदेश टाइप करें..."
                }
            }
        },
        te: { // Telugu
            translation: {
                buttons: {
                    userInfo: "వినియోగదారు సమాచారం",
                    dashboard: "డాష్బోర్డ్",
                    reset: "రీసెట్",
                    cart: "కార్ట్",
                    placeOrder: "ఆర్డర్ చేయండి",
                    viewOrder: "తెరిచిన ఆర్డర్ చూడండి",
                    productInfo: "ఉత్పత్తి సమాచారం",
                    companyInfo: "కంపెనీ సమాచారం",
                    trackOrder: "ఆర్డర్ ట్రాక్ చేయండి",
                    getHelp: "సహాయం పొందండి",
                    addItems: "అంశాలను జోడించండి",
                    confirmOrder: "ఆర్డర్ నిర్ధారించండి",
                    cancelOrder: "ఆర్డర్ రద్దు చేయండి",
                    rejectOrder: "ఆర్డర్ తిరస్కరించండి",
                    viewAllOrders: "అన్ని ఆర్డర్లు చూడండి",
                    print: "ముద్రించండి",
                    backToHome: "హోమ్‌కు తిరిగి వెళ్లండి",
                    cancelOrderAction: "ఆర్డర్ రద్దు చేయండి",
                    trackAnotherOrder: "మరొక ఆర్డర్ ట్రాక్ చేయండి",
                    placeNewOrder: "కొత్త ఆర్డర్ చేయండి",
                    modifyCart: "కార్ట్ సవరించండి",
                    addMoreItems: "మరిన్ని అంశాలను జోడించండి",
                    viewCart: "కార్ట్ చూడండి"
                },
                messages: {
                    welcome: "HV కు స్వాగతం (క్వాంటమ్ బ్లూ AI ద్వారా నడుపబడుతుంది)",
                    loading: "లోడ్ అవుతోంది...",
                    error: "దోషం సంభవించింది",
                    searchProducts: "ఉత్పత్తులను శోధించండి",
                    placeOrder: "నేను ఆర్డర్ చేయాలనుకుంటున్నాను",
                    trackOrder: "నేను ఆర్డర్‌ను ట్రాక్ చేయాలనుకుంటున్నాను",
                    companyInfo: "కంపెనీ గురించి నాకు చెప్పండి",
                    showCart: "నా కార్ట్‌ను నాకు చూపించండి",
                    addMoreItems: "నేను నా ఆర్డర్‌కు మరిన్ని అంశాలను జోడించాలనుకుంటున్నాను",
                    needHelp: "నాకు సహాయం కావాలి",
                    changeCustomer: "కస్టమర్‌ను మార్చండి",
                    selectCustomer: "కస్టమర్‌ను ఎంచుకోండి",
                    addNewCustomer: "కొత్త కస్టమర్‌ను జోడించండి",
                    confirmOrder: "నా ఆర్డర్‌ను నిర్ధారించండి",
                    showStock: "స్టాక్ స్థితిని నాకు చూపించండి",
                    editCart: "కార్ట్‌ను సవరించండి",
                    placeOrderFinal: "ఆర్డర్ చేయండి",
                    showPendingStock: "పెండింగ్ స్టాక్‌ను చూపించండి",
                    generateReport: "రిపోర్ట్‌ను రూపొందించండి",
                    availableProducts: "అందుబాటులో ఉన్న ఉత్పత్తులు",
                    productInformation: "ఉత్పత్తి సమాచారం",
                    pleaseSearch: "దయచేసి ఉత్పత్తిని శోధించండి లేదా క్రింది జాబితా నుండి ఎంచుకోండి:",
                    loadingProductInfo: "ఉత్పత్తి సమాచారం లోడ్ అవుతోంది...",
                    packSize: "ప్యాక్ పరిమాణం",
                    genericName: "సాధారణ పేరు / కూర్పు",
                    therapeuticClass: "చికిత్సా తరగతి",
                    keyUses: "ప్రధాన ఉపయోగాలు",
                    mechanismOfAction: "చర్య యంత్రాంగం",
                    dosage: "మోతాదు మరియు నిర్వహణ",
                    safetyProfile: "భద్రతా ప్రొఫైల్ మరియు సాధారణ వైపు ప్రభావాలు",
                    description: "వివరణ",
                    productInfo: "ఉత్పత్తి సమాచారం"
                },
                labels: {
                    searchProducts: "ఉత్పత్తులను శోధించండి:",
                    availableProducts: "అందుబాటులో ఉన్న ఉత్పత్తులు:",
                    typeToSearch: "ఉత్పత్తి పేరు టైప్ చేయండి...",
                    noProducts: "ఉత్పత్తులు అందుబాటులో లేవు",
                    orderId: "ఆర్డర్ ID",
                    status: "స్థితి",
                    totalItems: "మొత్తం అంశాలు",
                    totalAmount: "మొత్తం మొత్తం",
                    customer: "కస్టమర్",
                    date: "తేదీ",
                    productName: "ఉత్పత్తి పేరు",
                    quantity: "పరిమాణం",
                    foc: "FOC",
                    unitPrice: "యూనిట్ ధర",
                    totalPrice: "మొత్తం ధర",
                    orderItems: "ఆర్డర్ అంశాలు",
                    units: "యూనిట్లు",
                    orderDetails: "ఆర్డర్ వివరాలు",
                    orderInformation: "ఆర్డర్ సమాచారం",
                    paymentSummary: "చెల్లింపు సారాంశం",
                    subtotal: "ఉప-మొత్తం",
                    tax: "పన్ను",
                    grandTotal: "మొత్తం మొత్తం",
                    expiryDate: "గడువు తేదీ",
                    lotNumber: "లాట్ నంబర్",
                    reason: "కారణం",
                    editOrderItems: "ఆర్డర్ అంశాలను సవరించండి (ఐచ్ఛికం)",
                    quantityOrdered: "పరిమాణం (ఆర్డర్ చేయబడింది:",
                    enterQuantity: "పరిమాణం నమోదు చేయండి",
                    enterLotNumber: "లాట్ నంబర్ నమోదు చేయండి",
                    reasonForAdjustment: "సర్దుబాటు కారణం",
                    selectOrderFromDropdown: "వివరాలను వీక్షించడానికి డ్రాప్‌డౌన్ నుండి ఆర్డర్‌ను ఎంచుకోండి, లేదా బహుళ ఆర్డర్‌ల కోసం బల్క్ సెలెక్ట్‌ను ప్రారంభించండి",
                    selectOrderToTrack: "ట్రాక్ చేయడానికి ఆర్డర్‌ను ఎంచుకోండి"
                },
                labels: {
                    searchProducts: "ఉత్పత్తులను శోధించండి:",
                    availableProducts: "అందుబాటులో ఉన్న ఉత్పత్తులు:",
                    typeToSearch: "ఉత్పత్తి పేరు టైప్ చేయండి...",
                    noProducts: "ఉత్పత్తులు అందుబాటులో లేవు",
                    orderId: "ఆర్డర్ ID",
                    status: "స్థితి",
                    totalItems: "మొత్తం అంశాలు",
                    totalAmount: "మొత్తం మొత్తం",
                    customer: "కస్టమర్",
                    date: "తేదీ",
                    productName: "ఉత్పత్తి పేరు",
                    quantity: "పరిమాణం",
                    foc: "FOC",
                    unitPrice: "యూనిట్ ధర",
                    totalPrice: "మొత్తం ధర",
                    orderItems: "ఆర్డర్ అంశాలు",
                    units: "యూనిట్లు",
                    orderDetails: "ఆర్డర్ వివరాలు",
                    orderInformation: "ఆర్డర్ సమాచారం",
                    paymentSummary: "చెల్లింపు సారాంశం",
                    subtotal: "ఉప-మొత్తం",
                    tax: "పన్ను",
                    grandTotal: "మొత్తం మొత్తం",
                    expiryDate: "గడువు తేదీ",
                    lotNumber: "లాట్ నంబర్",
                    reason: "కారణం",
                    editOrderItems: "ఆర్డర్ అంశాలను సవరించండి (ఐచ్ఛికం)",
                    quantityOrdered: "పరిమాణం (ఆర్డర్ చేయబడింది:",
                    enterQuantity: "పరిమాణం నమోదు చేయండి",
                    enterLotNumber: "లాట్ నంబర్ నమోదు చేయండి",
                    reasonForAdjustment: "సర్దుబాటు కారణం",
                    orderManagementDashboard: "ఆర్డర్ మేనేజ్‌మెంట్ డాష్‌బోర్డ్",
                    selectOrderToTrack: "ట్రాక్ చేయడానికి ఆర్డర్‌ను ఎంచుకోండి",
                    filterByMRName: "MR పేరు ద్వారా ఫిల్టర్ చేయండి:",
                    filterByCustomer: "కస్టమర్ ద్వారా ఫిల్టర్ చేయండి:",
                    filterByDate: "తేదీ ద్వారా ఫిల్టర్ చేయండి:",
                    filterByStatus: "స్థితి ద్వారా ఫిల్టర్ చేయండి:",
                    chooseAnOrder: "ఆర్డర్‌ను ఎంచుకోండి:",
                    allMRs: "-- అన్ని MRలు --",
                    allCustomers: "-- అన్ని కస్టమర్‌లు --",
                    allDates: "-- అన్ని తేదీలు --",
                    allStatuses: "-- అన్ని స్థితులు --",
                    selectOrder: "-- ఆర్డర్‌ను ఎంచుకోండి --",
                    exportExcel: "ఎక్సెల్‌కు ఎగుమతి చేయండి",
                    selected: "ఎంచుకున్నది",
                    confirmSelected: "ఎంచుకున్న ఆర్డర్‌లను నిర్ధారించండి",
                    rejectSelected: "ఎంచుకున్న ఆర్డర్‌లను తిరస్కరించండి",
                    clear: "క్లియర్",
                    viewOrderDetails: "ఆర్డర్ వివరాలను వీక్షించండి",
                    cancel: "రద్దు చేయండి",
                    user: "వినియోగదారు",
                    area: "ప్రాంతం",
                    type: "రకం",
                    adjustQuantitiesInfo: "నిర్ధారించే ముందు మీరు పరిమాణాలు, లాట్ నంబర్‌లు మరియు గడువు తేదీలను సర్దుబాటు చేయవచ్చు. మీరు పరిమాణాన్ని తగ్గిస్తే, మిగిలినది పెండింగ్ ఆర్డర్‌లకు తరలించబడుతుంది. అసలు విలువలను ఉపయోగించడానికి మార్పు చేయకండి.",
                    adjustQuantityInfo: "ఆర్డర్ చేసిన పరిమాణం నుండి భిన్నమైతే సర్దుబాటు చేయండి. తగ్గించినట్లయితే, మిగిలినది పెండింగ్ ఆర్డర్‌లకు తరలించబడుతుంది.",
                    lotNumberInfo: "ఐచ్ఛికం: ఈ అంశం కోసం లాట్/బ్యాచ్ నంబర్",
                    expiryDateInfo: "ఈ అంశం కోసం గడువు తేదీని ఎంచుకోండి",
                    reasonInfo: "ఐచ్ఛికం: పరిమాణం/తేదీ/లాట్ మార్పు కారణం. పరిమాణం మార్చబడి కారణం అందించబడితే, MRకి తెలియజేయబడుతుంది.",
                    fromDatabase: "(డేటాబేస్ నుండి)"
                },
                placeholders: {
                    typeMessage: "మీ సందేశాన్ని టైప్ చేయండి..."
                }
            }
        }
    },
    fallbackLng: 'en',
    lng: localStorage.getItem('preferredLanguage') || 'en',
    debug: false,
    interpolation: {
        escapeValue: false
    }
    }).then(() => {
        // Update UI after initialization
        if (typeof updateAllUITexts === 'function') {
            updateAllUITexts();
        }
        // Also trigger update after a short delay to ensure DOM is ready
        setTimeout(() => {
            if (typeof updateAllUITexts === 'function') {
                updateAllUITexts();
            }
        }, 100);
    });
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeI18n);
} else {
    // DOM already loaded
    initializeI18n();
}

// Function to change language
function changeLanguage(lang) {
    // Update voice language if voice interaction is available
    if (typeof updateVoiceLanguage === 'function') {
        updateVoiceLanguage(lang);
    }
    // Multi-language feature disabled - show coming soon popup
    // Reset selector to English
    const selector = document.getElementById('languageSelector');
    if (selector) {
        selector.value = 'en';
    }
    
    // Show coming soon message
    if (typeof showToast === 'function') {
        showToast('Multi-language feature coming soon!', 'info');
    } else {
        alert('Multi-language feature coming soon!');
    }
    // Dead code removed - multi-language feature not implemented
}

// Function to update all UI texts
function updateAllUITexts() {
    if (!i18n) {
        console.warn('i18n not initialized, skipping UI text update');
        return;
    }
    
    // Update elements with data-i18n attribute
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        const translation = i18n.t(key);
        if (translation && translation !== key) {
            // Check if element has icon as child, preserve it
            const icon = el.querySelector('i');
            if (icon) {
                // Preserve icon and update text
                const iconHTML = icon.outerHTML;
                el.innerHTML = iconHTML + ' ' + translation;
            } else {
                // Check if parent has icon as sibling (for labels with icon siblings)
                const parent = el.parentElement;
                if (parent) {
                    // Check for sibling icon (icon that's a sibling of this element)
                    const siblingIcon = Array.from(parent.children).find(child => 
                        child.tagName === 'I' && child !== el
                    );
                    if (siblingIcon) {
                        // Just update text, keep icon as sibling
                        el.textContent = translation;
                    } else {
                        // Check if parent has icon (for buttons with icon siblings)
                        const parentIcon = parent.querySelector('i');
                        if (parentIcon && parentIcon !== el) {
                            // Just update text, keep icon in parent
                            el.textContent = translation;
                        } else {
                            el.textContent = translation;
                        }
                    }
                } else {
                    el.textContent = translation;
                }
            }
        }
    });
    
    // Update placeholders
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        const key = el.getAttribute('data-i18n-placeholder');
        const translation = i18n.t(key);
        if (translation && translation !== key) {
            el.placeholder = translation;
        }
    });
    
    // Update titles
    document.querySelectorAll('[data-i18n-title]').forEach(el => {
        const key = el.getAttribute('data-i18n-title');
        const translation = i18n.t(key);
        if (translation && translation !== key) {
            el.title = translation;
        }
    });
}

// Helper function to get translation
function t(key) {
    if (!i18n) {
        return key; // Return key if i18n not initialized
    }
    return i18n.t(key);
}

// Make i18n globally available
window.i18n = i18n;
window.changeLanguage = changeLanguage;
window.updateAllUITexts = updateAllUITexts;
window.t = t;

