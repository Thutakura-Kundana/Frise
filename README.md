# Frise - Smart Food Shelf-Life Tracker

A production-ready full-stack web application for intelligent food inventory management, real-time expiry tracking, and automated waste reduction.

## Features

### 🍎 Core Features
- **Inventory Management**: Add, edit, delete, and manage food items with detailed information
- **Expiry Tracking**: Automatic status calculation (Fresh, Expiring Soon, Expired)
- **Smart Notifications**: Real-time alerts for expiring foods and expired items
- **Food Images**: Upload and display food item images
- **Barcode Scanning**: Support for barcode input and management
- **Package Label OCR**: Extract expiry dates from label photos with OpenCV + Tesseract
- **Advanced Search**: Search items by name or barcode
- **Filtering & Sorting**: Filter by category and status, sort by expiry date

### 📊 Analytics & Dashboard
- **Dashboard Analytics**: Real-time statistics on inventory status
- **Category Distribution**: Visual breakdown of food items by category
- **Status Overview**: Charts showing fresh vs expiring vs expired items
- **Waste Trends**: Monthly food waste tracking and forecasting
- **Detailed Reports**: Comprehensive inventory reports

### 🔔 Notification System
- **Real-time Alerts**: Instant notifications for expiry events
- **Notification Center**: Dedicated page for managing notifications
- **Status Badges**: Visual indicators (Green/Orange/Red) for item status
- **Unread Tracking**: Keep track of unread notifications

### 💾 Data Management
- **Persistent Storage**: SQLite database with SQLAlchemy ORM
- **API-driven**: RESTful API for all operations
- **Data Validation**: Pydantic validation for request/response

## Technology Stack

### Backend
- **Framework**: FastAPI
- **Database**: SQLite (Development)
- **ORM**: SQLAlchemy
- **Validation**: Pydantic
- **Server**: Uvicorn
- **OCR**: OpenCV + Tesseract

### Frontend
- **Framework**: React 18+
- **Styling**: CSS3 with modern design patterns
- **HTTP Client**: Axios
- **Routing**: React Router
- **Charts**: Recharts
- **Icons**: React Icons
- **Notifications**: React Toastify

## Project Structure

```
frise/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── models.py            # SQLAlchemy models
│   ├── schemas.py           # Pydantic schemas
│   ├── database.py          # Database configuration
│   ├── requirements.txt     # Python dependencies
│   └── uploads/             # Image storage
│
├── frontend/
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── pages/           # Page components
│   │   ├── services/        # API service layer
│   │   ├── styles/          # CSS files
│   │   ├── App.jsx          # Main App component
│   │   ├── index.jsx        # React entry point
│   │   └── assets/          # Static assets
│   ├── package.json         # NPM dependencies
│   ├── vite.config.js       # Vite configuration
│   └── index.html           # HTML entry point
│
└── .github/
    └── copilot-instructions.md
```

## Installation & Setup

### Prerequisites
- Python 3.9+
- Node.js 16+ and npm
- Git
- Tesseract OCR installed on your machine and available on `PATH`

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a virtual environment:
```bash
python -m venv venv

# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the server:
```bash
python main.py
```

The backend will be available at `http://localhost:8000`

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm start
```

The frontend will be available at `http://localhost:3000`

## API Endpoints

### Food Items
- `POST /api/food-items` - Create a new food item
- `GET /api/food-items` - List all food items (with filters)
- `GET /api/food-items/{id}` - Get a specific item
- `PUT /api/food-items/{id}` - Update a food item
- `DELETE /api/food-items/{id}` - Delete a food item
- `POST /api/food-items/{id}/upload-image` - Upload item image
- `POST /api/ocr/expiry-date` - Scan a package label image and extract an expiry date

### Search & Filter
- `GET /api/search?query=` - Search by name or barcode

### Dashboard
- `GET /api/dashboard/stats` - Get dashboard statistics
- `GET /api/dashboard/categories` - Get category statistics

### Notifications
- `GET /api/notifications` - List all notifications
- `PUT /api/notifications/{id}/read` - Mark as read
- `DELETE /api/notifications/{id}` - Delete notification

## Database Schema

### FoodItem
```
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
```

### Notification
```
- id (Integer, Primary Key)
- item_id (Integer, Foreign Key)
- message (String)
- notification_type (Enum: expiring_soon, expired, info)
- created_at (DateTime)
- is_read (Boolean)
- triggered_at (DateTime)
```

### ActivityLog
```
- id (Integer, Primary Key)
- action (String)
- item_id (Integer)
- details (String)
- created_at (DateTime)
```

## Status Calculation Logic

- **Fresh**: More than 48 hours remaining
- **Expiring Soon**: Less than 48 hours remaining
- **Expired**: Expiry date-time has passed

## Features Demo

### Add Food Item
1. Click the "+" button on the Inventory page
2. Fill in item details (name, category, expiry date, etc.)
3. Click "Add Item"
4. Upload image if desired

### View Inventory
1. Navigate to Inventory page
2. Use filters to find specific items
3. Sort by expiry date or category
4. View real-time countdown of expiring items

### Monitor Notifications
1. Navigate to Notifications page
2. View all expiry alerts and warnings
3. Mark notifications as read
4. Delete old notifications

### Analyze Trends
1. Navigate to Analytics page
2. View distribution charts by category
3. Monitor Fresh vs Expired ratio
4. Track monthly waste trends

## Deployment

### Backend Deployment (Production)
```bash
# Install gunicorn
pip install gunicorn

# Run with gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 main:app
```

### Frontend Deployment (Production)
```bash
# Build production bundle
npm run build

# Deploy the dist folder to your hosting service
```

## Future Enhancements

- [ ] User authentication and authorization
- [ ] Dark mode support
- [ ] Email reminders
- [ ] Export to CSV/PDF
- [ ] Mobile app
- [ ] WebSocket real-time updates
- [ ] Recipe suggestions based on expiring items
- [ ] Multi-user support
- [ ] Cloud synchronization

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues.

## License

This project is open source and available under the MIT License.

## Support

For support, please open an issue on the GitHub repository or contact the development team.

---

Made with ❤️ for reducing food waste and promoting sustainability.
