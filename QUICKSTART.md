"""
Frise - Smart Food Shelf-Life Tracker

Quick Start Guide
"""

# =====================================================
# FRISE QUICK START GUIDE
# =====================================================

# 1. BACKEND SETUP
# =====================================================
cd backend
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Make sure Tesseract OCR is installed on the system and on PATH

# Run the server (http://localhost:8000)
python main.py

# The API documentation will be available at:
# http://localhost:8000/docs (Swagger UI)
# http://localhost:8000/redoc (ReDoc)


# 2. FRONTEND SETUP (in a new terminal)
# =====================================================
cd frontend
npm install
npm run dev

# The frontend will be available at:
# http://localhost:3000 (or http://localhost:5173 for Vite)


# 3. ACCESS THE APPLICATION
# =====================================================
# Open browser and navigate to:
# http://localhost:3000


# 4. FEATURES TO TEST
# =====================================================

# Dashboard
# - View total items, fresh items, expiring soon, and expired items
# - See real-time statistics and alerts

# Inventory Management
# - Click "+" button to add a new food item
# - Fill in item details (name, category, expiry date, etc.)
# - Upload food images
# - Edit items by clicking the edit button
# - Delete items by clicking the delete button

# Filtering & Search
# - Search by food name or barcode
# - Filter by category
# - Filter by status (Fresh, Expiring Soon, Expired)
# - Sort by expiry date, name, or category

# Notifications
# - View expiry alerts and warnings
# - Mark notifications as read
# - Delete old notifications

# Analytics
# - View category distribution charts
# - Monitor Fresh vs Expired ratio
# - Track monthly food waste trends


# 5. TROUBLESHOOTING
# =====================================================

# Backend issues:
# - Make sure Python 3.9+ is installed
# - Verify virtual environment is activated
# - Check that port 8000 is not in use
# - Clear Python cache: find . -type d -name __pycache__ -exec rm -r {} +

# Frontend issues:
# - Make sure Node.js 16+ is installed
# - Delete node_modules and reinstall: rm -rf node_modules && npm install
# - Clear npm cache: npm cache clean --force
# - Check that port 3000/5173 is not in use

# Database issues:
# - The database is automatically initialized on first run
# - To reset: delete frise.db file and restart backend
# - Database file location: backend/frise.db


# 6. DEVELOPMENT COMMANDS
# =====================================================

# Backend
python main.py                    # Start development server
pytest                            # Run tests
black . --line-length=100         # Format code
flake8 .                          # Lint code

# Frontend
npm run dev                       # Start dev server
npm run build                     # Build for production
npm run preview                   # Preview production build


# 7. PRODUCTION DEPLOYMENT
# =====================================================

# Backend with Gunicorn
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 main:app

# Frontend build
npm run build
# Deploy the 'dist' folder to your hosting service


# 8. API ENDPOINTS
# =====================================================

# Food Items
POST   /api/food-items              # Create new item
GET    /api/food-items              # List items (with filters)
GET    /api/food-items/{id}         # Get specific item
PUT    /api/food-items/{id}         # Update item
DELETE /api/food-items/{id}         # Delete item
POST   /api/food-items/{id}/upload-image  # Upload image
POST   /api/ocr/expiry-date               # OCR expiry date from label image

# Search & Filter
GET    /api/search?query=<text>    # Search items

# Dashboard
GET    /api/dashboard/stats        # Get statistics
GET    /api/dashboard/categories   # Get category stats

# Notifications
GET    /api/notifications          # List notifications
PUT    /api/notifications/{id}/read # Mark as read
DELETE /api/notifications/{id}     # Delete notification

# Health
GET    /health                     # Health check


# 9. DATABASE SCHEMA
# =====================================================

FoodItem:
- id (Integer, Primary Key)
- item_name (String)
- category (String)
- barcode (String, Optional)
- image_path (String, Optional)
- expiry_date (DateTime)
- created_at (DateTime)
- status (Enum: fresh, expiring_soon, expired)
- quantity (Integer)
- description (String)
- unit (String)

Notification:
- id (Integer, Primary Key)
- item_id (Integer)
- message (String)
- notification_type (Enum: expiring_soon, expired, info)
- created_at (DateTime)
- is_read (Boolean)
- triggered_at (DateTime)

ActivityLog:
- id (Integer, Primary Key)
- action (String)
- item_id (Integer)
- details (String)
- created_at (DateTime)


# 10. ENVIRONMENT VARIABLES
# =====================================================

# Backend (.env)
DATABASE_URL=sqlite:///./frise.db
DEBUG=False
API_TITLE=Frise API
API_VERSION=1.0.0

# Frontend (.env)
REACT_APP_API_URL=http://localhost:8000
