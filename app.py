# ============================================
# ORDERFLOW - WORKING VERSION (NO ERRORS)
# ============================================
# Save as: app.py
# Run: python -m streamlit run app.py

import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import urllib.parse

# Page config
st.set_page_config(
    page_title="OrderFlow",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .stButton button {
        width: 100%;
        border-radius: 10px;
        height: 50px;
        font-size: 16px;
        font-weight: 600;
    }
    
    .welcome-banner {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 30px;
        border-radius: 15px;
        color: white;
        margin-bottom: 20px;
    }
    
    .status-draft {
        background-color: #ffc107;
        color: black;
        padding: 5px 15px;
        border-radius: 20px;
        font-weight: bold;
    }
    
    .status-approved {
        background-color: #28a745;
        color: white;
        padding: 5px 15px;
        border-radius: 20px;
        font-weight: bold;
    }
    
    .whatsapp-message {
        background-color: #dcf8c6;
        padding: 15px;
        border-radius: 10px;
        font-family: monospace;
        white-space: pre-wrap;
        border: 1px solid #25D366;
    }
</style>
""", unsafe_allow_html=True)

# ============================================
# FIREBASE SETUP
# ============================================

@st.cache_resource
def init_firebase():
    try:
        firebase_admin.get_app()
    except ValueError:
        cred = credentials.Certificate('firebase-key.json')
        firebase_admin.initialize_app(cred)
    return firestore.client()

db = init_firebase()

# ============================================
# CATEGORIZATION ENGINE
# ============================================

KEYWORDS_DATABASE = {
    "Dairy & Milk Products": ["milk", "butter", "cheese", "paneer", "curd", "ghee", "cream", "dahi", "malai"],
    "Meat, Poultry & Seafood": ["chicken", "mutton", "fish", "eggs", "prawns", "meat", "keema"],
    "Vegetables": ["onion", "tomato", "potato", "carrot", "beans", "cabbage", "spinach", "palak", "gobi"],
    "Fruits": ["apple", "banana", "mango", "orange", "grapes", "papaya"],
    "Rice, Grains & Pulses": ["rice", "wheat", "atta", "dal", "pasta", "noodles", "maida", "rava"],
    "Spices & Masala": ["salt", "pepper", "turmeric", "chilli", "masala", "jeera", "haldi"],
    "Cooking Oil & Ghee": ["oil", "ghee", "butter", "refined", "mustard oil"],
    "Bakery & Bread": ["bread", "bun", "cake", "biscuit", "pav", "rusk"],
    "Beverages & Drinks": ["tea", "coffee", "juice", "water", "cold drink", "chai"],
    "Cleaning & Kitchen Supplies": ["tissue", "napkin", "detergent", "soap", "foil", "cleaner"]
}

def categorize_item(item_name):
    if not item_name:
        return "Uncategorized"
    
    item_lower = item_name.lower().strip()
    
    for category, keywords in KEYWORDS_DATABASE.items():
        if item_lower in keywords:
            return category
    
    for category, keywords in KEYWORDS_DATABASE.items():
        for keyword in keywords:
            if keyword in item_lower:
                return category
    
    return "Uncategorized"

# ============================================
# VENDOR MANAGER
# ============================================

class VendorManager:
    def __init__(self):
        self.vendors_ref = db.collection('vendors')
    
    def add_vendor(self, category, vendor_name, phone, vendor_type="WhatsApp"):
        vendor_data = {
            "category": category,
            "vendor_name": vendor_name,
            "phone": phone,
            "vendor_type": vendor_type,
            "created_at": firestore.SERVER_TIMESTAMP
        }
        self.vendors_ref.add(vendor_data)
        return True
    
    def get_all_vendors(self):
        docs = self.vendors_ref.stream()
        vendors = []
        for doc in docs:
            vendor = doc.to_dict()
            vendor['id'] = doc.id
            vendors.append(vendor)
        return vendors
    
    def get_vendor_by_category(self, category):
        docs = self.vendors_ref.where('category', '==', category).limit(1).stream()
        for doc in docs:
            vendor = doc.to_dict()
            vendor['id'] = doc.id
            return vendor
        return None
    
    def delete_vendor(self, vendor_id):
        self.vendors_ref.document(vendor_id).delete()
        return True

vendor_manager = VendorManager()

# ============================================
# DRAFT MANAGER
# ============================================

class DraftManager:
    def __init__(self):
        self.draft_ref = db.collection('drafts').document('current-draft')
        self.orders_ref = db.collection('orders')
    
    def add_item(self, item_name, quantity, added_by):
        category = categorize_item(item_name)
        
        item = {
            "name": item_name.strip(),
            "quantity": quantity.strip(),
            "category": category,
            "added_by": added_by,
            "added_at": datetime.now().isoformat()
        }
        
        draft_doc = self.draft_ref.get()
        
        if draft_doc.exists:
            current_items = draft_doc.to_dict().get('items', [])
            current_items.append(item)
            self.draft_ref.update({
                'items': current_items,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
        else:
            self.draft_ref.set({
                'items': [item],
                'status': 'Draft',
                'created_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
        
        return category
    
    def get_draft(self):
        draft_doc = self.draft_ref.get()
        if not draft_doc.exists:
            return {"items": [], "status": "Draft"}
        return draft_doc.to_dict()
    
    def approve_draft(self, approved_by):
        draft = self.get_draft()
        if len(draft.get('items', [])) == 0:
            return False, "Cannot approve empty draft"
        
        self.draft_ref.update({
            'status': 'Approved',
            'approved_by': approved_by,
            'approved_at': firestore.SERVER_TIMESTAMP
        })
        return True, "Draft approved successfully"
    
    def mark_as_sent(self, sent_by):
        draft = self.get_draft()
        order_data = draft.copy()
        order_data['sent_by'] = sent_by
        order_data['sent_at'] = firestore.SERVER_TIMESTAMP
        order_data['status'] = 'Sent'
        
        self.orders_ref.add(order_data)
        
        self.draft_ref.set({
            'items': [],
            'status': 'Draft',
            'created_at': firestore.SERVER_TIMESTAMP
        })
        return True
    
    def remove_item(self, index):
        draft = self.get_draft()
        items = draft.get('items', [])
        
        if 0 <= index < len(items):
            removed = items.pop(index)
            self.draft_ref.update({
                'items': items,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            return removed
        return None
    
    def clear_draft(self):
        self.draft_ref.set({
            'items': [],
            'status': 'Draft',
            'created_at': firestore.SERVER_TIMESTAMP
        })
    
    def get_order_history(self, limit=10):
        docs = self.orders_ref.order_by('sent_at', direction=firestore.Query.DESCENDING).limit(limit).stream()
        orders = []
        for doc in docs:
            order = doc.to_dict()
            order['id'] = doc.id
            orders.append(order)
        return orders

draft_manager = DraftManager()

# ============================================
# MESSAGE GENERATOR
# ============================================

def generate_whatsapp_message(vendor_name, items):
    message = f"Hi {vendor_name},\n\n"
    message += "Order for tomorrow:\n\n"
    
    for item in items:
        message += f"• {item['name']}"
        if item['quantity']:
            message += f" - {item['quantity']}"
        message += "\n"
    
    message += "\nThanks!"
    return message

def create_whatsapp_url(phone, message):
    clean_phone = ''.join(filter(str.isdigit, phone))
    
    if not clean_phone.startswith('91') and len(clean_phone) == 10:
        clean_phone = '91' + clean_phone
    
    encoded_message = urllib.parse.quote(message)
    url = f"https://wa.me/{clean_phone}?text={encoded_message}"
    return url

# ============================================
# SESSION STATE
# ============================================

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_name = ""
    st.session_state.user_role = ""

# ============================================
# LOGIN SCREEN
# ============================================

def login_screen():
    st.markdown("""
    <div class='welcome-banner'>
        <h1 style='color: white; margin: 0;'>🛒 OrderFlow</h1>
        <p style='color: white; margin: 0;'>Smart Inventory Management</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.subheader("Welcome! Please Login")
    
    with st.form("login_form"):
        name = st.text_input("Your Name", placeholder="Enter your name")
        role = st.selectbox("Your Role", ["Staff", "Owner"])
        
        submitted = st.form_submit_button("Login", use_container_width=True, type="primary")
        
        if submitted:
            if name and name.strip():
                st.session_state.logged_in = True
                st.session_state.user_name = name.strip()
                st.session_state.user_role = role
                st.success(f"✅ Welcome, {name}!")
                st.rerun()
            else:
                st.error("❌ Please enter your name")

# ============================================
# HOME SCREEN
# ============================================

def home_screen():
    draft = draft_manager.get_draft()
    status = draft.get('status', 'Draft')
    
    st.markdown(f"""
    <div class='welcome-banner'>
        <h2 style='color: white; margin: 0;'>Welcome back, {st.session_state.user_name}!</h2>
        <p style='color: white; margin: 0;'>Role: {st.session_state.user_role}</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("Current Draft Status")
    with col2:
        if status == "Draft":
            st.markdown('<span class="status-draft">📝 Draft</span>', unsafe_allow_html=True)
        elif status == "Approved":
            st.markdown('<span class="status-approved">✅ Approved</span>', unsafe_allow_html=True)
    
    items = draft.get('items', [])
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("📦 Total Items", len(items))
    
    with col2:
        categories = len(set(item['category'] for item in items if item['category'] != 'Uncategorized'))
        st.metric("📂 Categories", categories)
    
    with col3:
        vendors = len(vendor_manager.get_all_vendors())
        st.metric("👥 Vendors", vendors)
    
    st.markdown("---")
    
    st.subheader("Quick Actions")
    
    if st.session_state.user_role == "Staff":
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("➕ Add Items", use_container_width=True, type="primary"):
                st.session_state.current_page = "add_items"
                st.rerun()
        
        with col2:
            if st.button("📋 View Draft", use_container_width=True):
                st.session_state.current_page = "view_draft"
                st.rerun()
    
    else:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("➕ Add Items", use_container_width=True):
                st.session_state.current_page = "add_items"
                st.rerun()
        
        with col2:
            if st.button("📋 View Draft", use_container_width=True):
                st.session_state.current_page = "view_draft"
                st.rerun()
        
        with col3:
            if len(items) > 0 and status == "Draft":
                if st.button("✅ Review", use_container_width=True, type="primary"):
                    st.session_state.current_page = "review"
                    st.rerun()
            elif status == "Approved":
                if st.button("📤 Send Orders", use_container_width=True, type="primary"):
                    st.session_state.current_page = "send_orders"
                    st.rerun()
        
        with col4:
            if st.button("👥 Vendors", use_container_width=True):
                st.session_state.current_page = "vendors"
                st.rerun()
    
    st.markdown("---")
    
    if len(items) > 0:
        st.subheader("Current Draft Preview")
        recent = items[-5:]
        recent.reverse()
        
        for item in recent:
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                st.write(f"**{item['name']}**")
            with col2:
                st.write(f"{item['quantity']}")
            with col3:
                st.caption(item['category'][:12])
        
        if len(items) > 5:
            st.caption(f"...and {len(items) - 5} more items")
    else:
        st.info("📋 No items in draft. Click 'Add Items' to get started!")

# ============================================
# ADD ITEMS SCREEN
# ============================================

def add_items_screen():
    st.title("➕ Add New Item")
    
    draft = draft_manager.get_draft()
    status = draft.get('status', 'Draft')
    
    if status != "Draft":
        st.warning(f"⚠️ Draft is currently **{status}**. Cannot add items.")
        if st.button("← Back to Home"):
            st.session_state.current_page = "home"
            st.rerun()
        return
    
    with st.form("add_item_form", clear_on_submit=True):
        item_name = st.text_input("Item Name *", placeholder="e.g., Milk, Chicken, Onions")
        
        col1, col2 = st.columns(2)
        
        with col1:
            quantity = st.text_input("Quantity", placeholder="e.g., 10L, 5kg")
        
        with col2:
            added_by = st.text_input("Added By", value=st.session_state.user_name)
        
        col1, col2 = st.columns(2)
        
        with col1:
            submitted = st.form_submit_button("➕ Add Item", type="primary", use_container_width=True)
        
        with col2:
            cancel = st.form_submit_button("Cancel", use_container_width=True)
        
        if submitted:
            if not item_name or not item_name.strip():
                st.error("❌ Please enter item name")
            else:
                category = draft_manager.add_item(item_name, quantity, added_by)
                
                if category == "Uncategorized":
                    st.warning(f"⚠️ {item_name} added but needs categorization")
                else:
                    st.success(f"✅ {item_name} added to {category}")
                
                st.balloons()
        
        if cancel:
            st.session_state.current_page = "home"
            st.rerun()

# ============================================
# VIEW DRAFT SCREEN
# ============================================

def view_draft_screen():
    st.title("📋 Current Draft")
    
    draft = draft_manager.get_draft()
    items = draft.get('items', [])
    status = draft.get('status', 'Draft')
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader(f"Status: {status}")
    with col2:
        if status == "Draft":
            st.markdown('<span class="status-draft">📝 Draft</span>', unsafe_allow_html=True)
        elif status == "Approved":
            st.markdown('<span class="status-approved">✅ Approved</span>', unsafe_allow_html=True)
    
    if len(items) == 0:
        st.info("📋 Draft is empty.")
        if st.button("➕ Add Items", type="primary"):
            st.session_state.current_page = "add_items"
            st.rerun()
        return
    
    by_category = {}
    for item in items:
        cat = item['category']
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(item)
    
    for category, cat_items in by_category.items():
        icon = "⚠️" if category == "Uncategorized" else "✅"
        
        with st.expander(f"{icon} {category} ({len(cat_items)} items)", expanded=True):
            for item in cat_items:
                idx = items.index(item)
                
                col1, col2, col3 = st.columns([4, 2, 1])
                
                with col1:
                    st.markdown(f"**{item['name']}**")
                    st.caption(f"Added by {item['added_by']}")
                
                with col2:
                    st.write(f"{item['quantity']}")
                
                with col3:
                    if status == "Draft":
                        if st.button("🗑️", key=f"del_{idx}"):
                            draft_manager.remove_item(idx)
                            st.rerun()
                
                st.markdown("---")
    
    st.markdown("---")
    
    if status == "Draft":
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("➕ Add More Items", use_container_width=True):
                st.session_state.current_page = "add_items"
                st.rerun()
        
        with col2:
            if st.button("🗑️ Clear All", use_container_width=True, type="secondary"):
                draft_manager.clear_draft()
                st.success("Draft cleared!")
                st.rerun()

# ============================================
# REVIEW SCREEN
# ============================================

def review_screen():
    st.title("✅ Review & Approve Draft")
    
    if st.session_state.user_role != "Owner":
        st.error("❌ Only owners can approve drafts")
        if st.button("← Back"):
            st.session_state.current_page = "home"
            st.rerun()
        return
    
    draft = draft_manager.get_draft()
    items = draft.get('items', [])
    status = draft.get('status', 'Draft')
    
    if len(items) == 0:
        st.warning("⚠️ Cannot approve empty draft")
        if st.button("← Back"):
            st.session_state.current_page = "home"
            st.rerun()
        return
    
    if status != "Draft":
        st.info(f"ℹ️ This draft is already **{status}**")
        if st.button("← Back"):
            st.session_state.current_page = "home"
            st.rerun()
        return
    
    st.subheader("Draft Summary")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Items", len(items))
    with col2:
        categories = len(set(item['category'] for item in items))
        st.metric("Categories", categories)
    with col3:
        uncategorized = sum(1 for item in items if item['category'] == 'Uncategorized')
        st.metric("Uncategorized", uncategorized)
    
    st.markdown("---")
    
    by_category = {}
    for item in items:
        cat = item['category']
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(item)
    
    st.subheader("Items by Category")
    
    for category, cat_items in by_category.items():
        icon = "⚠️" if category == "Uncategorized" else "✅"
        
        with st.expander(f"{icon} {category} ({len(cat_items)} items)", expanded=True):
            for item in cat_items:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**{item['name']}** - {item['quantity']}")
                with col2:
                    st.caption(f"by {item['added_by']}")
    
    st.markdown("---")
    
    if uncategorized > 0:
        st.warning(f"⚠️ {uncategorized} items are uncategorized.")
    
    st.subheader("Actions")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("✅ Approve Draft", type="primary", use_container_width=True):
            success, message = draft_manager.approve_draft(st.session_state.user_name)
            if success:
                st.success(message)
                st.balloons()
                st.session_state.current_page = "home"
                st.rerun()
    
    with col2:
        if st.button("← Cancel", use_container_width=True):
            st.session_state.current_page = "home"
            st.rerun()

# ============================================
# VENDORS SCREEN
# ============================================

def vendors_screen():
    st.title("👥 Vendor Management")
    
    if st.session_state.user_role != "Owner":
        st.error("❌ Only owners can manage vendors")
        if st.button("← Back"):
            st.session_state.current_page = "home"
            st.rerun()
        return
    
    vendors = vendor_manager.get_all_vendors()
    
    st.subheader("Add New Vendor")
    
    with st.form("add_vendor_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            categories = list(KEYWORDS_DATABASE.keys())
            category = st.selectbox("Category", categories)
        
        with col2:
            vendor_name = st.text_input("Vendor Name", placeholder="e.g., Ramesh Milk Supplier")
        
        phone = st.text_input("Phone Number", placeholder="e.g., 9876543210")
        
        submitted = st.form_submit_button("Add Vendor", use_container_width=True, type="primary")
        
        if submitted:
            if vendor_name and phone:
                vendor_manager.add_vendor(category, vendor_name, phone)
                st.success(f"✅ Vendor added for {category}")
                st.rerun()
            else:
                st.error("❌ Please fill all fields")
    
    st.markdown("---")
    
    st.subheader("Current Vendors")
    
    if len(vendors) == 0:
        st.info("No vendors added yet")
    else:
        for vendor in vendors:
            with st.expander(f"📞 {vendor['vendor_name']} - {vendor['category']}", expanded=False):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.write(f"**Category:** {vendor['category']}")
                    st.write(f"**Phone:** {vendor['phone']}")
                    st.write(f"**Type:** {vendor.get('vendor_type', 'WhatsApp')}")
                
                with col2:
                    if st.button("🗑️ Delete", key=f"del_vendor_{vendor['id']}"):
                        vendor_manager.delete_vendor(vendor['id'])
                        st.success("Vendor deleted")
                        st.rerun()

# ============================================
# SEND ORDERS SCREEN
# ============================================

def send_orders_screen():
    st.title("📤 Send Orders to Vendors")
    
    if st.session_state.user_role != "Owner":
        st.error("❌ Only owners can send orders")
        if st.button("← Back"):
            st.session_state.current_page = "home"
            st.rerun()
        return
    
    draft = draft_manager.get_draft()
    items = draft.get('items', [])
    status = draft.get('status', 'Draft')
    
    if status != "Approved":
        st.warning(f"⚠️ Draft must be approved first. Current status: {status}")
        if st.button("← Back"):
            st.session_state.current_page = "home"
            st.rerun()
        return
    
    by_category = {}
    for item in items:
        cat = item['category']
        if cat != 'Uncategorized':
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(item)
    
    if len(by_category) == 0:
        st.warning("No categorized items to send")
        if st.button("← Back"):
            st.session_state.current_page = "home"
            st.rerun()
        return
    
    st.info(f"📦 {len(by_category)} categories ready to send")
    
    st.markdown("---")
    
    for category, cat_items in by_category.items():
        st.subheader(f"{category} ({len(cat_items)} items)")
        
        vendor = vendor_manager.get_vendor_by_category(category)
        
        if not vendor:
            st.warning(f"⚠️ No vendor mapped for {category}")
            st.caption("Go to 'Vendors' to add one")
            st.markdown("---")
            continue
        
        message = generate_whatsapp_message(vendor['vendor_name'], cat_items)
        
        st.markdown("**Message Preview:**")
        st.markdown(f'<div class="whatsapp-message">{message}</div>', unsafe_allow_html=True)
        
        whatsapp_url = create_whatsapp_url(vendor['phone'], message)
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.write(f"**Sending to:** {vendor['vendor_name']} ({vendor['phone']})")
        
        with col2:
            st.link_button("📱 Send via WhatsApp", whatsapp_url, use_container_width=True)
        
        st.markdown("---")
    
    st.subheader("After Sending All Messages")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("✅ Mark All as Sent", type="primary", use_container_width=True):
            draft_manager.mark_as_sent(st.session_state.user_name)
            st.success("✅ Orders sent and archived!")
            st.balloons()
            st.session_state.current_page = "home"
            st.rerun()
    
    with col2:
        if st.button("← Back", use_container_width=True):
            st.session_state.current_page = "home"
            st.rerun()

# ============================================
# ORDER HISTORY SCREEN
# ============================================

def history_screen():
    st.title("📜 Order History")
    
    orders = draft_manager.get_order_history(limit=10)
    
    if len(orders) == 0:
        st.info("No orders sent yet")
        if st.button("← Back"):
            st.session_state.current_page = "home"
            st.rerun()
        return
    
    st.write(f"Showing last {len(orders)} orders")
    
    for order in orders:
        with st.expander(f"📦 Order - {order.get('sent_at', 'Unknown date')}", expanded=False):
            items = order.get('items', [])
            
            st.write(f"**Total Items:** {len(items)}")
            st.write(f"**Sent by:** {order.get('sent_by', 'Unknown')}")
            st.write(f"**Approved by:** {order.get('approved_by', 'Unknown')}")
            
            st.markdown("---")
            
            by_category = {}
            for item in items:
                cat = item['category']
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(item)
            
            for category, cat_items in by_category.items():
                st.write(f"**{category}:**")
                for item in cat_items:
                    st.write(f"  • {item['name']} - {item['quantity']}")

# ============================================
# MAIN APP
# ============================================

def main():
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "home"
    
    # Check if logged in
    if not st.session_state.logged_in:
        login_screen()
        return
    
    # Sidebar
    with st.sidebar:
        st.title("🛒 OrderFlow")
        
        st.markdown("---")
        
        if st.button("🏠 Home", use_container_width=True):
            st.session_state.current_page = "home"
            st.rerun()
        
        if st.button("➕ Add Items", use_container_width=True):
            st.session_state.current_page = "add_items"
            st.rerun()
        
        if st.button("📋 View Draft", use_container_width=True):
            st.session_state.current_page = "view_draft"
            st.rerun()
        
        # Owner-only buttons
        if st.session_state.user_role == "Owner":
            st.markdown("---")
            st.caption("Owner Menu")
            
            draft = draft_manager.get_draft()
            status = draft.get('status', 'Draft')
            items = draft.get('items', [])
            
            if len(items) > 0 and status == "Draft":
                if st.button("✅ Review", use_container_width=True):
                    st.session_state.current_page = "review"
                    st.rerun()
            
            if status == "Approved":
                if st.button("📤 Send Orders", use_container_width=True, type="primary"):
                    st.session_state.current_page = "send_orders"
                    st.rerun()
            
            if st.button("👥 Vendors", use_container_width=True):
                st.session_state.current_page = "vendors"
                st.rerun()
            
            if st.button("📜 History", use_container_width=True):
                st.session_state.current_page = "history"
                st.rerun()
        
        st.markdown("---")
        
        st.caption(f"**{st.session_state.user_name}**")
        st.caption(f"Role: {st.session_state.user_role}")
        
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.current_page = "home"
            st.rerun()
    
    # Route to screens
    if st.session_state.current_page == "home":
        home_screen()
    elif st.session_state.current_page == "add_items":
        add_items_screen()
    elif st.session_state.current_page == "view_draft":
        view_draft_screen()
    elif st.session_state.current_page == "review":
        review_screen()
    elif st.session_state.current_page == "vendors":
        vendors_screen()
    elif st.session_state.current_page == "send_orders":
        send_orders_screen()
    elif st.session_state.current_page == "history":
        history_screen()

if __name__ == "__main__":
    main()