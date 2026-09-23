# Frise - Smart Food Shelf-Life Tracker

A full-stack web application for intelligent food inventory management, expiry tracking, and food waste reduction.

## Features

### 🍎 Core Features

- **Inventory Management**: Add, edit, delete, and manage food items with detailed information
- **Expiry Tracking**: Automatic status calculation (Fresh, Expiring Soon, Expired)
- **Smart Notifications**: Alerts for expiring foods and expired items
- **Food Images**: Upload and display food item images
- **Barcode Scanning**: Support for barcode scanning and product lookup
- **Package Label OCR**: Extract expiry dates from label photos using OpenCV + Tesseract
- **Advanced Search**: Search items by name or barcode
- **Filtering & Sorting**: Filter by category and status, and sort by expiry date

### 📊 Analytics & Dashboard

- **Dashboard Analytics**: Statistics on inventory status
- **Category Distribution**: Visual breakdown of food items by category
- **Status Overview**: Charts showing Fresh vs Expiring Soon vs Expired items
- **Waste Trends**: Track food waste over time
- **Detailed Reports**: Inventory and consumption information

### 🔔 Notification System

- **Expiry Alerts**: Notifications for upcoming and expired food items
- **Notification Center**: Dedicated page for managing notifications
- **Status Badges**: Visual indicators for food status
- **Unread Tracking**: Keep track of unread notifications

### 💾 Data Management

- **Persistent Storage**: SQLite database with SQLAlchemy ORM
- **API-driven**: RESTful API for application operations
- **Data Validation**: Pydantic validation for request and response data

## Technology Stack

### Backend

- **Framework**: FastAPI
- **Database**: SQLite
- **ORM**: SQLAlchemy
- **Validation**: Pydantic
- **Server**: Uvicorn
- **OCR**: OpenCV + Tesseract

### Frontend

- **Framework**: React 18+
- **Styling**: CSS3
- **HTTP Client**: Axios
- **Routing**: React Router
- **Charts**: Recharts
- **Icons**: React Icons
- **Notifications**: React Toastify
- **Barcode Scanning**: ZXing

## Project Structure

```text
frise/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── models.py            # SQLAlchemy models
│   ├── schemas.py           # Pydantic schemas
│   ├── database.py          # Database configuration
│   ├── requirements.txt     # Python dependencies
│   └── uploads/             # Uploaded images
│
├── frontend/
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── services/        # API service layer
│   │   ├── styles/          # CSS files
│   │   ├── assets/          # Static assets
│   │   ├── App.jsx          # Main App component
│   │   └── main.jsx         # React entry point
│   ├── package.json         # NPM dependencies
│   ├── package-lock.json    # Dependency lock file
│   ├── vite.config.js       # Vite configuration
│   └── index.html           # HTML entry point
│
├── .github/
│   └── copilot-instructions.md
│
├── .gitignore
├── README.md
├── QUICKSTART.md
├── PROJECT_STRUCTURE.md
├── setup.bat
├── setup.sh
└── start.bat
```

## Installation & Setup

### Prerequisites

- Python 3.9+
- Node.js 18+ and npm
- Git
- Tesseract OCR installed on your machine and available on PATH

### Backend Setup

1. Navigate to the backend directory:

```bash
cd backend
```

2. Create a virtual environment:

```bash
python -m venv venv
```

On Windows:

```bash
venv\Scripts\activate
```

On macOS/Linux:

```bash
source venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Run the backend server:

```bash
python main.py
```

The backend will be available at:

```text
http://localhost:8000
```

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
npm run dev
```

The frontend will be available at the URL shown by Vite in the terminal, typically:

```text
http://localhost:5173
```

## Quick Start

On Windows, the project also includes:

```text
start.bat
```

which can be used to start the backend and frontend development servers.

## API Endpoints

### Food Items

- `POST /api/food-items` - Create a new food item
- `GET /api/food-items` - List all food items with filters
- `GET /api/food-items/{id}` - Get a specific food item
- `PUT /api/food-items/{id}` - Update a food item
- `DELETE /api/food-items/{id}` - Delete a food item
- `POST /api/food-items/{id}/upload-image` - Upload an item image

### Barcode & OCR

- `GET /api/barcode/{barcode}` - Look up product information using a barcode
- `POST /api/ocr/barcode` - Detect a barcode from an uploaded image
- `POST /api/ocr/expiry-date` - Extract an expiry date from a package-label image

### Search & Filter

- `GET /api/search?query=` - Search food items by name or barcode

### Dashboard

- `GET /api/dashboard/stats` - Get dashboard statistics
- `GET /api/dashboard/categories` - Get category statistics
- `GET /api/dashboard/consumption-patterns` - Get consumption patterns

### Notifications

- `GET /api/notifications` - List notifications
- `PUT /api/notifications/{id}/read` - Mark a notification as read
- `DELETE /api/notifications/{id}` - Delete a notification

## Database Schema

### FoodItem

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

### Notification

- id (Integer, Primary Key)
- item_id (Integer, Foreign Key)
- message (String)
- notification_type (Enum: expiring_soon, expired, info)
- created_at (DateTime)
- is_read (Boolean)
- triggered_at (DateTime)

### ActivityLog

- id (Integer, Primary Key)
- action (String)
- item_id (Integer)
- details (String)
- created_at (DateTime)

## Status Calculation Logic

- **Fresh**: More than 48 hours remaining
- **Expiring Soon**: Less than 48 hours remaining
- **Expired**: Expiry date and time has passed

## Features Demo

### Add Food Item

1. Click the + button on the Inventory page
2. Enter the food item details
3. Enter or scan the barcode if available
4. Enter or scan the expiry date
5. Upload an image if desired
6. Click Add Item

### View Inventory

1. Navigate to the Inventory page
2. Use filters to find specific items
3. Sort items by expiry date or category
4. View the expiry status of each food item

### Barcode & OCR

1. Open the Add Food Item modal
2. Use the barcode scanner to scan a product
3. Product information can be retrieved using the barcode
4. Capture a package-label image
5. Use OCR to detect the expiry date
6. Review the detected information before saving

### Monitor Notifications

1. Navigate to the Notifications page
2. View expiry alerts and warnings
3. Mark notifications as read
4. Delete old notifications

### Analyze Trends

1. Navigate to the Analytics page
2. View distribution charts by category
3. Monitor Fresh, Expiring Soon, and Expired items
4. Track food consumption and waste patterns

## Deployment

### Backend Deployment

For production deployment, the FastAPI application can be served using a production ASGI server.

Example:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Frontend Deployment

Build the production frontend bundle:

```bash
npm run build
```

The generated `dist` folder can then be deployed to a suitable hosting service.

## Future Enhancements

- [ ] Dark mode support
- [ ] Email reminders
- [ ] Export to CSV/PDF
- [ ] Mobile application
- [ ] Recipe suggestions based on expiring items
- [ ] Multi-user support
- [ ] Cloud synchronization
- [ ] Advanced real-time updates

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues.

## Support

For support, please open an issue on the GitHub repository.

---

Made with ❤️ for reducing food waste and promoting sustainability.
