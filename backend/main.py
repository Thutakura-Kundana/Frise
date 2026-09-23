"""FastAPI main application for Frise."""
import os
import re
import json
import math
import hashlib
import secrets
import base64
import hmac
from datetime import datetime
from typing import Dict, List, Optional
from contextlib import asynccontextmanager

import aiohttp
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.models import (
    ActivityLog,
    FoodItem,
    Notification,
    NotificationTypeEnum,
    StatusEnum,
    User,
)
from backend import schemas
from backend.database import get_db, init_db

FRIDGE_CAPACITY_UNITS = 40
JWT_SECRET = os.getenv("FRISE_JWT_SECRET", "change-this-frise-secret")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60 * 24 * 7
EXPIRY_ALERT_WINDOW_HOURS = 24
SHELF_CAPACITY_UNITS = {
    "Top Shelf": 8,
    "Middle Shelf": 8,
    "Bottom Shelf": 8,
    "Door Rack": 5,
    "Crisper Drawer": 5,
    "Freezer": 4,
    "Chiller Tray": 2,
}


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    init_db()
    print("Database initialized")
    yield
    # Shutdown
    print("Application shutting down")


# Create FastAPI app
app = FastAPI(
    title="Frise API",
    description="Smart Food Shelf-Life Tracker",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration - Add BEFORE any middleware or routes
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://localhost",
        "*"  # Allow all origins for development
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    max_age=3600,
)

# Create uploads directory if it doesn't exist
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """Hash a password with a salted, slow standard-library KDF."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 210000)
    return f"pbkdf2_sha256$210000${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    """Verify a password hash without exposing timing differences."""
    try:
        algorithm, rounds, salt_hex, digest_hex = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(rounds)
        )
        return secrets.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: int) -> str:
    """Create a short-lived signed bearer token."""
    from datetime import timedelta
    expires = int((datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES)).timestamp())
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=")
    body = base64.urlsafe_b64encode(
        json.dumps({"sub": str(user_id), "exp": expires}, separators=(",", ":")).encode()
    ).rstrip(b"=")
    unsigned = header + b"." + body
    signature = hmac.new(JWT_SECRET.encode(), unsigned, hashlib.sha256).digest()
    return (unsigned + b"." + base64.urlsafe_b64encode(signature).rstrip(b"=")).decode()


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated user from the bearer token."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        header, body, encoded_signature = credentials.credentials.split(".")
        unsigned = f"{header}.{body}".encode()
        expected = hmac.new(JWT_SECRET.encode(), unsigned, hashlib.sha256).digest()
        actual = base64.urlsafe_b64decode(encoded_signature + "===")
        if not hmac.compare_digest(actual, expected):
            raise ValueError("invalid signature")
        payload = json.loads(base64.urlsafe_b64decode(body + "===").decode())
        if int(payload["exp"]) < int(datetime.utcnow().timestamp()):
            raise ValueError("expired token")
        user_id = int(payload["sub"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User no longer exists")
    return user


def user_item_query(db: Session, user: User):
    """Return the authenticated user's items, including pre-auth legacy rows."""
    return db.query(FoodItem).filter(
        (FoodItem.user_id == user.id) | (FoodItem.user_id.is_(None))
    )


def claim_legacy_data(db: Session, user: User) -> None:
    """Give the first account ownership of data from older Frise versions."""
    if db.query(User).count() != 1:
        return
    db.query(FoodItem).filter(FoodItem.user_id.is_(None)).update(
        {FoodItem.user_id: user.id}, synchronize_session=False
    )
    db.query(Notification).filter(Notification.user_id.is_(None)).update(
        {Notification.user_id: user.id}, synchronize_session=False
    )
    db.query(ActivityLog).filter(ActivityLog.user_id.is_(None)).update(
        {ActivityLog.user_id: user.id}, synchronize_session=False
    )


# ==================== Utility Functions ====================

def calculate_status(expiry_date: datetime) -> StatusEnum:
    """Calculate food item status based on expiry date."""
    now = datetime.now()
    time_diff = expiry_date - now

    if time_diff.total_seconds() < 0:
        return StatusEnum.EXPIRED
    elif time_diff.total_seconds() <= EXPIRY_ALERT_WINDOW_HOURS * 3600:
        return StatusEnum.EXPIRING_SOON
    else:
        return StatusEnum.FRESH


def format_remaining_time(expiry_date: datetime) -> str:
    """Format remaining time until expiry."""
    now = datetime.now()
    diff = expiry_date - now

    if diff.total_seconds() < 0:
        return "Expired"

    days = diff.days
    hours = diff.seconds // 3600
    minutes = (diff.seconds % 3600) // 60

    if days > 0:
        return f"{days} Day{'s' if days != 1 else ''}"
    elif hours > 0:
        return f"{hours} Hour{'s' if hours != 1 else ''}"
    else:
        return f"{minutes} Minute{'s' if minutes != 1 else ''}"


def build_notification_message(item: FoodItem, status: StatusEnum) -> str:
    """Build a user-facing notification message for an item status."""
    if status == StatusEnum.EXPIRED:
        return f"{item.item_name} has expired."

    remaining_time = format_remaining_time(item.expiry_date)
    return f"{item.item_name} is expiring soon. {remaining_time} remaining."


def ensure_status_notification(
    db: Session,
    item: FoodItem,
    status: StatusEnum
) -> None:
    """Create a status notification if one does not already exist."""
    if status not in (StatusEnum.EXPIRING_SOON, StatusEnum.EXPIRED):
        return

    notification_type = NotificationTypeEnum(status.value)
    existing = db.query(Notification).filter(
        Notification.item_id == item.id,
        Notification.notification_type == notification_type
    ).first()

    if existing:
        return

    db.add(Notification(
        item_id=item.id,
        user_id=item.user_id,
        message=build_notification_message(item, status),
        notification_type=notification_type,
        triggered_at=datetime.now()
    ))


def prune_non_expiring_notifications(db: Session, user: Optional[User] = None) -> bool:
    """Remove expiry alerts whose item's current status no longer matches."""
    item_query = user_item_query(db, user) if user else db.query(FoodItem)
    notification_query = db.query(Notification)
    if user:
        notification_query = notification_query.filter(Notification.user_id == user.id)
    active_status_by_item_id = {item.id: item.status for item in item_query.all()}
    notification_statuses = {
        NotificationTypeEnum.EXPIRING_SOON: StatusEnum.EXPIRING_SOON,
        NotificationTypeEnum.EXPIRED: StatusEnum.EXPIRED,
    }
    notifications = notification_query.filter(
        Notification.notification_type.in_(notification_statuses.keys())
    ).all()

    stale_notifications = [
        notification
        for notification in notifications
        if active_status_by_item_id.get(notification.item_id)
        != notification_statuses[notification.notification_type]
    ]
    for notification in stale_notifications:
        db.delete(notification)

    return bool(stale_notifications)


def sync_item_statuses_and_notifications(db: Session, user: User) -> None:
    """Refresh item statuses and generate expiry notifications."""
    changed = False
    items = user_item_query(db, user).all()

    for item in items:
        status = calculate_status(item.expiry_date)
        if item.status != status:
            item.status = status
            db.add(item)
            changed = True

        if status in (StatusEnum.EXPIRING_SOON, StatusEnum.EXPIRED):
            before_new = len(db.new)
            ensure_status_notification(db, item, status)
            changed = changed or len(db.new) > before_new

    changed = prune_non_expiring_notifications(db, user) or changed

    if changed:
        db.commit()


def first_text_value(*values: Optional[str]) -> Optional[str]:
    """Return the first non-empty text value."""
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _load_ocr_dependencies():
    """Load OCR libraries lazily so the app can still boot without them."""
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
        import pytesseract  # type: ignore
    except ImportError as exc:  # pragma: no cover - dependency availability
        raise HTTPException(
            status_code=503,
            detail=(
                "OCR dependencies are not installed. Install "
                "opencv-python-headless and pytesseract, and make sure the "
                "Tesseract binary is available on the server."
            )
        ) from exc

    return cv2, np, pytesseract


def preprocess_ocr_image(image_bytes: bytes):
    """Create OCR-friendly image variants from an uploaded label photo."""
    cv2, np, _ = _load_ocr_dependencies()

    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=400, detail="Could not read the image")

    height, width = image.shape[:2]
    if width and width < 1200:
        scale = 1200 / width
        image = cv2.resize(
            image,
            None,
            fx=scale,
            fy=scale,
            interpolation=cv2.INTER_CUBIC
        )

    grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    grayscale = cv2.bilateralFilter(grayscale, 9, 75, 75)
    grayscale = cv2.convertScaleAbs(grayscale, alpha=1.5, beta=0)

    threshold = cv2.adaptiveThreshold(
        grayscale,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11
    )
    inverted_threshold = cv2.bitwise_not(threshold)
    sharpened = cv2.GaussianBlur(grayscale, (0, 0), 3)
    sharpened = cv2.addWeighted(grayscale, 1.6, sharpened, -0.6, 0)

    return [grayscale, threshold, inverted_threshold, sharpened]


def _clean_ocr_text(text: str) -> str:
    """Normalize OCR text for date extraction."""
    return re.sub(r"[ \t]+", " ", (text or "").replace("\r", "\n")).strip()


def _safe_normalize_year(year_text: str) -> int:
    """Convert two-digit years into four digits."""
    year = int(year_text)
    if len(year_text) == 2:
        year += 2000
    return year


def _is_valid_date(day: int, month_index: int, year: int) -> bool:
    """Check whether a date component set is valid."""
    try:
        datetime(year, month_index + 1, day)
    except ValueError:
        return False
    return 2020 <= year <= 2100


def _score_context(context: str) -> int:
    """Score label text around a date candidate."""
    lower = context.lower()
    score = 0

    for keyword in [
        "best before",
        "bestby",
        "best-by",
        "use by",
        "use-by",
        "expiry",
        "exp",
        "expires",
        "expire",
        "sell by",
        "sell-by",
        "bb",
        "bb/",
        "bb:",
    ]:
        if keyword in lower:
            score += 5

    for keyword in [
        "mfg",
        "manufactured",
        "production",
        "packed",
        "batch",
        "lot",
    ]:
        if keyword in lower:
            score -= 3

    return score


def extract_expiry_candidates(text: str) -> List[Dict]:
    """Extract likely expiry dates from OCR text."""
    cleaned_text = _clean_ocr_text(text)
    candidates = []
    current_year = datetime.now().year
    now = datetime.now()

    def add_candidate(match_text: str, candidate_date: datetime, context: str):
        score = _score_context(context)
        if candidate_date >= now:
            score += 2
        else:
            score -= 1

        if candidate_date.year >= current_year:
            score += 1

        candidates.append({
            "text": match_text,
            "date": candidate_date,
            "score": score,
            "context": context.strip(),
        })

    iso_pattern = re.compile(r"\b(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})\b")
    numeric_pattern = re.compile(r"\b(\d{1,2})[./\-\s](\d{1,2})[./\-\s](\d{2,4})\b")
    month_lookup = {
        "jan": 0,
        "january": 0,
        "feb": 1,
        "february": 1,
        "mar": 2,
        "march": 2,
        "apr": 3,
        "april": 3,
        "may": 4,
        "jun": 5,
        "june": 5,
        "jul": 6,
        "july": 6,
        "aug": 7,
        "august": 7,
        "sep": 8,
        "sept": 8,
        "september": 8,
        "oct": 9,
        "october": 9,
        "nov": 10,
        "november": 10,
        "dec": 11,
        "december": 11,
    }
    month_pattern = re.compile(
        r"\b(\d{1,2})\s*"
        r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|"
        r"jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|"
        r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
        r"(?:\s+(\d{2,4}))?\b",
        re.IGNORECASE
    )
    reverse_month_pattern = re.compile(
        r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|"
        r"jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|"
        r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+"
        r"(\d{1,2})(?:,?\s+(\d{2,4}))?\b",
        re.IGNORECASE
    )

    for match in iso_pattern.finditer(cleaned_text):
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))
        if _is_valid_date(day, month - 1, year):
            context = cleaned_text[max(0, match.start() - 30): match.end() + 30]
            add_candidate(match.group(0), datetime(year, month, day), context)

    for match in numeric_pattern.finditer(cleaned_text):
        first = int(match.group(1))
        second = int(match.group(2))
        year = _safe_normalize_year(match.group(3))
        context = cleaned_text[max(0, match.start() - 30): match.end() + 30]

        if len(match.group(1)) == 4 and _is_valid_date(int(match.group(3)), second - 1, first):
            add_candidate(match.group(0), datetime(first, second, int(match.group(3))), context)
            continue

        if _is_valid_date(first, second - 1, year):
            add_candidate(match.group(0), datetime(year, second, first), context)

        if first <= 12 and second <= 12 and _is_valid_date(second, first - 1, year):
            add_candidate(match.group(0), datetime(year, first, second), context)

    for match in month_pattern.finditer(cleaned_text):
        day = int(match.group(1))
        month_name = match.group(2).lower()
        year = _safe_normalize_year(match.group(3)) if match.group(3) else current_year
        month = month_lookup.get(month_name[:3])
        if month is None or not _is_valid_date(day, month, year):
            continue
        context = cleaned_text[max(0, match.start() - 30): match.end() + 30]
        add_candidate(match.group(0), datetime(year, month + 1, day), context)

    for match in reverse_month_pattern.finditer(cleaned_text):
        month_name = match.group(1).lower()
        day = int(match.group(2))
        year = _safe_normalize_year(match.group(3)) if match.group(3) else current_year
        month = month_lookup.get(month_name[:3])
        if month is None or not _is_valid_date(day, month, year):
            continue
        context = cleaned_text[max(0, match.start() - 30): match.end() + 30]
        add_candidate(match.group(0), datetime(year, month + 1, day), context)

    candidates.sort(
        key=lambda item: (
            item["score"],
            1 if item["date"] >= now else 0,
            item["date"],
        ),
        reverse=True,
    )
    return candidates


def extract_expiry_date_from_text(text: str) -> Optional[datetime]:
    """Pick the most likely expiry date from OCR text."""
    candidates = extract_expiry_candidates(text)
    if not candidates:
        return None

    positive_context = [candidate for candidate in candidates if candidate["score"] >= 5]
    pool = positive_context or candidates
    future_candidates = [candidate for candidate in pool if candidate["date"] >= datetime.now()]
    selected = future_candidates[0] if future_candidates else pool[0]
    return selected["date"]


def ocr_label_image(image_bytes: bytes) -> Dict:
    """Run OpenCV preprocessing and Tesseract OCR on a package label image."""
    _, _, pytesseract = _load_ocr_dependencies()
    image_variants = preprocess_ocr_image(image_bytes)
    best_text = ""
    best_candidates = []

    for variant in image_variants:
        for psm in (6, 11, 12):
            config = f"--oem 3 --psm {psm}"
            text = pytesseract.image_to_string(variant, config=config)
            cleaned_text = _clean_ocr_text(text)
            if len(cleaned_text) > len(best_text):
                best_text = cleaned_text

            candidate_date = extract_expiry_date_from_text(cleaned_text)
            if candidate_date:
                best_candidates = extract_expiry_candidates(cleaned_text)
                break
        if best_candidates:
            break

    selected_date = extract_expiry_date_from_text(best_text)
    if not selected_date and best_candidates:
        selected_date = best_candidates[0]["date"]

    return {
        "found": selected_date is not None,
        "expiry_date": selected_date.isoformat() if selected_date else None,
        "raw_text": best_text,
        "candidates": [
            {
                "text": candidate["text"],
                "expiry_date": candidate["date"].isoformat(),
                "score": candidate["score"],
                "context": candidate["context"],
            }
            for candidate in best_candidates[:5]
        ],
    }


def _is_valid_gtin(barcode: str) -> bool:
    """Validate the check digit used by EAN, UPC, and other GTIN codes."""
    if not re.fullmatch(r"\d{8}|\d{12,14}", barcode):
        return False

    payload = barcode[:-1]
    weighted_sum = sum(
        int(digit) * (3 if index % 2 == 0 else 1)
        for index, digit in enumerate(reversed(payload))
    )
    return (weighted_sum + int(barcode[-1])) % 10 == 0


def extract_barcode_from_ocr(image_bytes: bytes) -> Dict:
    """Read and validate a printed barcode number when visual decoding fails."""
    _, _, pytesseract = _load_ocr_dependencies()
    image_variants = preprocess_ocr_image(image_bytes)
    candidates = []

    for variant in image_variants:
        for psm in (6, 7, 11, 12):
            text = pytesseract.image_to_string(
                variant,
                config=f"--oem 3 --psm {psm} -c tessedit_char_whitelist=0123456789",
            )
            for match in re.finditer(r"(?:\d[\s-]*){8,14}", text):
                candidate = re.sub(r"\D", "", match.group(0))
                if candidate not in candidates:
                    candidates.append(candidate)

    valid_barcode = next((code for code in candidates if _is_valid_gtin(code)), None)
    return {
        "found": valid_barcode is not None,
        "barcode": valid_barcode,
        "candidates": candidates[:10],
    }


def map_product_category(product: Dict) -> str:
    """Map product metadata into the app's category list."""
    category_text = " ".join([
        str(product.get("categories") or ""),
        str(product.get("categories_tags") or ""),
        str(product.get("pnns_groups_1") or ""),
        str(product.get("pnns_groups_2") or ""),
    ]).lower()

    category_keywords = [
        ("Dairy", ["dairy", "milk", "cheese", "yogurt", "butter"]),
        ("Meat", ["meat", "fish", "poultry", "seafood", "ham", "sausage"]),
        ("Fruits", ["fruit", "fruits"]),
        ("Vegetables", ["vegetable", "vegetables"]),
        ("Beverages", ["beverage", "drink", "juice", "soda"]),
        ("Snacks", ["snack", "chips", "biscuits", "cookies", "sweet"]),
        ("Frozen", ["frozen"]),
        ("Grains", ["cereal", "grain", "rice", "pasta", "bread"]),
        ("Pantry", ["sauce", "condiment", "oil", "spice", "canned"]),
    ]

    for category, keywords in category_keywords:
        if any(keyword in category_text for keyword in keywords):
            return category

    return "Other"


def build_product_payload(barcode: str, product: Dict) -> Dict:
    """Shape Open Food Facts data for the item form."""
    item_name = first_text_value(
        product.get("product_name"),
        product.get("product_name_en"),
        product.get("generic_name"),
        product.get("generic_name_en"),
        product.get("abbreviated_product_name"),
    )
    quantity_text = first_text_value(product.get("quantity"))

    return {
        "barcode": barcode,
        "found": bool(item_name),
        "item_name": item_name,
        "category": map_product_category(product),
        "description": first_text_value(
            product.get("brands"),
            product.get("categories")
        ),
        "quantity_text": quantity_text,
        "image_url": first_text_value(
            product.get("image_front_url"),
            product.get("image_url")
        ),
        "source": "Open Food Facts",
    }


def get_used_space(db: Session, user: User, exclude_item_id: Optional[int] = None) -> int:
    """Calculate fridge space used by stored items."""
    query = user_item_query(db, user)
    if exclude_item_id is not None:
        query = query.filter(FoodItem.id != exclude_item_id)

    return sum((item.space_units or 1) for item in query.all())


def get_shelf_used_space(
    db: Session,
    user: User,
    shelf_location: Optional[str],
    exclude_item_id: Optional[int] = None
) -> int:
    """Calculate fridge space used on a specific shelf."""
    if not shelf_location:
        return 0

    query = user_item_query(db, user).filter(FoodItem.shelf_location == shelf_location)
    if exclude_item_id is not None:
        query = query.filter(FoodItem.id != exclude_item_id)

    return sum((item.space_units or 1) for item in query.all())


def ensure_fridge_space(
    db: Session,
    user: User,
    requested_space: Optional[int],
    shelf_location: Optional[str] = None,
    exclude_item_id: Optional[int] = None
) -> None:
    """Reject create/update requests that exceed fridge or shelf capacity."""
    space_units = requested_space or 1
    used_space = get_used_space(db, user, exclude_item_id=exclude_item_id)
    empty_space = user.fridge_capacity - used_space

    if space_units > empty_space:
        unit_label = "unit" if empty_space == 1 else "units"
        raise HTTPException(
            status_code=400,
            detail=(
                f"Not enough fridge space. {empty_space} space "
                f"{unit_label} available."
            )
        )

    if shelf_location in SHELF_CAPACITY_UNITS:
        shelf_capacity = SHELF_CAPACITY_UNITS[shelf_location]
        shelf_used = get_shelf_used_space(
            db,
            user,
            shelf_location,
            exclude_item_id=exclude_item_id
        )
        shelf_empty = shelf_capacity - shelf_used

        if space_units > shelf_empty:
            unit_label = "unit" if shelf_empty == 1 else "units"
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Not enough space on {shelf_location}. "
                    f"{shelf_empty} space {unit_label} available."
                )
            )


def build_upload_filename(
    item_id: int,
    original_filename: Optional[str]
) -> str:
    """Create a safe, stable filename for an uploaded item image."""
    basename = os.path.basename(original_filename or "image")
    stem, extension = os.path.splitext(basename)
    safe_stem = (
        re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._") or "image"
    )
    safe_extension = re.sub(r"[^A-Za-z0-9.]+", "", extension.lower())
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    return f"{item_id}_{timestamp}_{safe_stem[:80]}{safe_extension}"


def get_item_lifecycle_days(item: FoodItem) -> int:
    """Return how many days an item has been tracked."""
    created_at = item.created_at or datetime.now()
    if getattr(created_at, "tzinfo", None) is not None:
        created_at = created_at.replace(tzinfo=None)

    seconds = max((datetime.now() - created_at).total_seconds(), 0)
    return max(1, math.ceil(seconds / 86400))


def log_item_outcome(db: Session, item: FoodItem, outcome: str) -> None:
    """Persist a consumption/waste event for pattern learning."""
    details = {
        "item_name": item.item_name,
        "category": item.category,
        "quantity": item.quantity or 1,
        "unit": item.unit or "unit",
        "days_in_fridge": get_item_lifecycle_days(item),
        "outcome": outcome.lower(),
    }

    db.add(ActivityLog(
        user_id=item.user_id,
        action=outcome.upper(),
        item_id=item.id,
        details=json.dumps(details)
    ))


def delete_item_records(db: Session, item: FoodItem) -> None:
    """Remove an item and its active notifications."""
    db.query(Notification).filter(Notification.item_id == item.id).delete()
    db.delete(item)


def parse_outcome_details(log: ActivityLog) -> Optional[Dict]:
    """Read structured learning details from an activity log row."""
    if log.action not in ("CONSUMED", "WASTED") or not log.details:
        return None

    try:
        details = json.loads(log.details)
    except json.JSONDecodeError:
        return None

    if not details.get("item_name"):
        return None

    return details


def build_pattern_insights(db: Session, user: User) -> Dict:
    """Build learned consumption and waste suggestions."""
    logs = db.query(ActivityLog).filter(
        ActivityLog.user_id == user.id,
        ActivityLog.action.in_(["CONSUMED", "WASTED"])
    ).order_by(desc(ActivityLog.created_at)).all()

    grouped = {}
    for log in logs:
        details = parse_outcome_details(log)
        if not details:
            continue

        key = details["item_name"].strip().lower()
        group = grouped.setdefault(key, {
            "item_name": details["item_name"].strip(),
            "category": details.get("category") or "Other",
            "consumed_days": [],
            "wasted_count": 0,
            "total_count": 0,
            "last_seen": log.created_at,
        })

        group["total_count"] += 1
        if details.get("outcome") == "wasted":
            group["wasted_count"] += 1
        else:
            group["consumed_days"].append(details.get("days_in_fridge") or 1)

    insights = []
    for group in grouped.values():
        average_days = None
        if group["consumed_days"]:
            average_days = round(sum(group["consumed_days"]) / len(group["consumed_days"]))

        messages = []
        if average_days:
            messages.append(
                f"You usually finish {group['item_name']} in {average_days} day"
                f"{'s' if average_days != 1 else ''}."
            )

        if group["wasted_count"] > 0:
            messages.append(f"You usually waste {group['item_name']}.")

        if group["wasted_count"] > 0:
            recommendation = f"Buy smaller quantity of {group['item_name']} next time."
        elif average_days:
            recommendation = (
                f"Plan {group['item_name']} for about {average_days} day"
                f"{'s' if average_days != 1 else ''} after buying."
            )
        else:
            recommendation = f"Keep tracking {group['item_name']} to improve suggestions."

        insights.append({
            "item_name": group["item_name"],
            "category": group["category"],
            "average_consumption_days": average_days,
            "wasted_count": group["wasted_count"],
            "total_events": group["total_count"],
            "messages": messages,
            "recommendation": recommendation,
            "confidence": min(group["total_count"], 4),
        })

    insights.sort(key=lambda insight: (insight["wasted_count"], insight["total_events"]), reverse=True)

    return {
        "total_events": sum(group["total_count"] for group in grouped.values()),
        "insights": insights[:6],
    }


# ==================== Food Items Endpoints ====================

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Frise API - Smart Food Shelf-Life Tracker",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.post("/api/auth/register", response_model=schemas.AuthResponse)
async def register_user(payload: schemas.AuthRegister, db: Session = Depends(get_db)):
    """Create an account with an individual fridge capacity."""
    email = payload.email.strip().lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        fridge_capacity=payload.fridge_capacity,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    claim_legacy_data(db, user)
    db.commit()
    return schemas.AuthResponse(
        access_token=create_access_token(user.id), token_type="bearer", user=user
    )


@app.post("/api/auth/login", response_model=schemas.AuthResponse)
async def login_user(payload: schemas.AuthLogin, db: Session = Depends(get_db)):
    """Authenticate an existing account."""
    user = db.query(User).filter(User.email == payload.email.strip().lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return schemas.AuthResponse(
        access_token=create_access_token(user.id), token_type="bearer", user=user
    )


@app.get("/api/auth/me", response_model=schemas.UserResponse)
async def get_profile(user: User = Depends(get_current_user)):
    """Return the current user's profile."""
    return user


@app.put("/api/settings/fridge", response_model=schemas.UserResponse)
async def update_fridge_settings(
    settings: schemas.FridgeSettings,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update the current user's fridge capacity."""
    used_space = get_used_space(db, user)
    if settings.fridge_capacity < used_space:
        raise HTTPException(
            status_code=400,
            detail=f"Capacity cannot be lower than current usage of {used_space} units",
        )
    user.fridge_capacity = settings.fridge_capacity
    db.commit()
    db.refresh(user)
    return user


@app.post("/api/food-items", response_model=schemas.FoodItemResponse)
async def create_food_item(
    item: schemas.FoodItemCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a new food item."""
    # Check for duplicate barcode
    if item.barcode:
        existing = user_item_query(db, user).filter(
            FoodItem.barcode == item.barcode
        ).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Barcode already exists"
            )

    # Calculate initial status
    status = calculate_status(item.expiry_date)
    ensure_fridge_space(db, user, item.space_units, item.shelf_location)

    # Create food item
    db_item = FoodItem(
        user_id=user.id,
        item_name=item.item_name,
        category=item.category,
        barcode=item.barcode,
        expiry_date=item.expiry_date,
        quantity=item.quantity,
        description=item.description,
        unit=item.unit,
        shelf_location=item.shelf_location,
        storage_state=item.storage_state,
        space_units=item.space_units,
        status=status
    )

    db.add(db_item)
    db.commit()
    db.refresh(db_item)

    ensure_status_notification(db, db_item, status)

    # Log activity
    log = ActivityLog(
        user_id=user.id,
        action="CREATE",
        item_id=db_item.id,
        details=f"Created food item: {item.item_name}"
    )
    db.add(log)
    db.commit()

    return db_item


@app.get("/api/food-items", response_model=List[schemas.FoodItemResponse])
async def list_food_items(
    category: Optional[str] = None,
    status: Optional[str] = None,
    sort_by: Optional[str] = "expiry_date",
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all food items with filtering and sorting."""
    sync_item_statuses_and_notifications(db, user)

    query = user_item_query(db, user)

    if category:
        query = query.filter(FoodItem.category == category)

    if status:
        try:
            status_enum = StatusEnum(status)
            query = query.filter(FoodItem.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status")

    # Sorting
    if sort_by == "expiry_date":
        query = query.order_by(FoodItem.expiry_date)
    elif sort_by == "name":
        query = query.order_by(FoodItem.item_name)
    elif sort_by == "category":
        query = query.order_by(FoodItem.category)
    elif sort_by == "created_at":
        query = query.order_by(desc(FoodItem.created_at))

    items = query.offset(skip).limit(limit).all()
    return items


@app.get("/api/food-items/{item_id}", response_model=schemas.FoodItemResponse)
async def get_food_item(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Get a specific food item."""
    sync_item_statuses_and_notifications(db, user)

    item = user_item_query(db, user).filter(
        FoodItem.id == item_id
    ).first()

    if not item:
        raise HTTPException(status_code=404, detail="Food item not found")

    return item


@app.put("/api/food-items/{item_id}", response_model=schemas.FoodItemResponse)
async def update_food_item(
    item_id: int,
    item_update: schemas.FoodItemUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update a food item."""
    db_item = user_item_query(db, user).filter(
        FoodItem.id == item_id
    ).first()

    if not db_item:
        raise HTTPException(status_code=404, detail="Food item not found")

    # Check for duplicate barcode
    if item_update.barcode and item_update.barcode != db_item.barcode:
        existing = user_item_query(db, user).filter(
            FoodItem.barcode == item_update.barcode
        ).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Barcode already exists"
            )

    # Update fields
    update_data = item_update.model_dump(exclude_unset=True)
    requested_space = update_data.get("space_units", db_item.space_units or 1)
    requested_shelf = update_data.get("shelf_location", db_item.shelf_location)
    ensure_fridge_space(
        db,
        user,
        requested_space,
        requested_shelf,
        exclude_item_id=item_id
    )

    for field, value in update_data.items():
        setattr(db_item, field, value)

    # Recalculate status if expiry_date changed
    if item_update.expiry_date:
        db_item.status = calculate_status(item_update.expiry_date)

    db.add(db_item)
    db.commit()
    db.refresh(db_item)

    ensure_status_notification(db, db_item, db_item.status)
    prune_non_expiring_notifications(db, user)

    # Log activity
    log = ActivityLog(
        user_id=user.id,
        action="UPDATE",
        item_id=db_item.id,
        details=f"Updated food item: {db_item.item_name}"
    )
    db.add(log)
    db.commit()

    return db_item


@app.delete("/api/food-items/{item_id}")
async def delete_food_item(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Delete a food item."""
    db_item = user_item_query(db, user).filter(
        FoodItem.id == item_id
    ).first()

    if not db_item:
        raise HTTPException(status_code=404, detail="Food item not found")

    item_name = db_item.item_name

    delete_item_records(db, db_item)
    db.commit()

    # Log activity
    log = ActivityLog(
        user_id=user.id,
        action="DELETE",
        item_id=item_id,
        details=f"Deleted food item: {item_name}"
    )
    db.add(log)
    db.commit()

    return {"message": "Food item deleted successfully"}


@app.post("/api/food-items/{item_id}/consume")
async def mark_food_item_consumed(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Mark an item as used so Frise can learn consumption patterns."""
    db_item = user_item_query(db, user).filter(FoodItem.id == item_id).first()

    if not db_item:
        raise HTTPException(status_code=404, detail="Food item not found")

    log_item_outcome(db, db_item, "CONSUMED")
    delete_item_records(db, db_item)
    db.commit()

    return {"message": "Item marked as used"}


@app.post("/api/food-items/{item_id}/waste")
async def mark_food_item_wasted(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Mark an item as wasted so Frise can learn waste patterns."""
    db_item = user_item_query(db, user).filter(FoodItem.id == item_id).first()

    if not db_item:
        raise HTTPException(status_code=404, detail="Food item not found")

    log_item_outcome(db, db_item, "WASTED")
    delete_item_records(db, db_item)
    db.commit()

    return {"message": "Item marked as wasted"}


# ==================== Image Upload Endpoint ====================

@app.post("/api/food-items/{item_id}/upload-image")
async def upload_image(
    item_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Upload an image for a food item."""
    db_item = user_item_query(db, user).filter(
        FoodItem.id == item_id
    ).first()

    if not db_item:
        raise HTTPException(status_code=404, detail="Food item not found")

    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid file type")

    # Save file
    filename = build_upload_filename(item_id, file.filename)
    file_path = os.path.join("uploads", filename)

    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())

    # Update item
    db_item.image_path = f"/uploads/{filename}"
    db.add(db_item)
    db.commit()

    return {
        "message": "Image uploaded successfully",
        "path": db_item.image_path
    }


@app.post("/api/ocr/expiry-date")
async def extract_expiry_date(
    file: UploadFile = File(...),
):
    """Extract an expiry date from a package label image."""
    allowed_types = [
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/jpg",
    ]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid file type")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty image upload")

    result = ocr_label_image(image_bytes)
    return result


@app.post("/api/ocr/barcode")
async def extract_barcode_number(
    file: UploadFile = File(...),
):
    """Read the digits printed below a barcode as a fallback scanner."""
    allowed_types = [
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/jpg",
    ]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid file type")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty image upload")

    return extract_barcode_from_ocr(image_bytes)


# ==================== Search Endpoint ====================

@app.get("/api/search")
async def search_items(
    query: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Search food items by name or barcode."""
    if len(query) < 2:
        raise HTTPException(status_code=400, detail="Query too short")

    items = user_item_query(db, user).filter(
        (FoodItem.item_name.ilike(f"%{query}%")) |
        (FoodItem.barcode == query)
    ).limit(10).all()

    return items


@app.get("/api/barcode/{barcode}")
async def lookup_barcode(barcode: str):
    """Look up a barcode and return product details for form autofill."""
    normalized_barcode = re.sub(r"\D+", "", barcode or "")
    if len(normalized_barcode) < 4:
        raise HTTPException(status_code=400, detail="Enter a valid barcode")

    url = (
        "https://world.openfoodfacts.org/api/v2/product/"
        f"{normalized_barcode}.json"
    )
    fields = ",".join([
        "code",
        "product_name",
        "product_name_en",
        "generic_name",
        "generic_name_en",
        "abbreviated_product_name",
        "brands",
        "categories",
        "categories_tags",
        "pnns_groups_1",
        "pnns_groups_2",
        "quantity",
        "image_front_url",
        "image_url",
    ])

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                params={"fields": fields},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status >= 500:
                    raise HTTPException(
                        status_code=502,
                        detail="Barcode lookup service is unavailable"
                    )
                data = await response.json()
    except aiohttp.ClientError as exc:
        raise HTTPException(
            status_code=502,
            detail="Could not reach barcode lookup service"
        ) from exc

    if data.get("status") != 1 or not data.get("product"):
        return {
            "barcode": normalized_barcode,
            "found": False,
            "source": "Open Food Facts",
        }

    return build_product_payload(normalized_barcode, data["product"])


# ==================== Dashboard Endpoints ====================

@app.get("/api/dashboard/stats", response_model=schemas.DashboardStats)
async def get_dashboard_stats(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get dashboard statistics."""
    sync_item_statuses_and_notifications(db, user)

    item_query = user_item_query(db, user)
    total_items = item_query.count()
    fresh_items = item_query.filter(
        FoodItem.status == StatusEnum.FRESH
    ).count()
    expiring_soon_items = item_query.filter(
        FoodItem.status == StatusEnum.EXPIRING_SOON
    ).count()
    expired_items = item_query.filter(
        FoodItem.status == StatusEnum.EXPIRED
    ).count()

    expiry_notification_types = [
        NotificationTypeEnum.EXPIRING_SOON,
        NotificationTypeEnum.EXPIRED,
    ]
    notification_query = db.query(Notification).filter(Notification.user_id == user.id)
    total_notifications = notification_query.filter(
        Notification.notification_type.in_(expiry_notification_types)
    ).count()
    unread_notifications = notification_query.filter(
        Notification.notification_type.in_(expiry_notification_types),
        Notification.is_read.is_(False)
    ).count()
    used_space = get_used_space(db, user)

    return schemas.DashboardStats(
        total_items=total_items,
        fresh_items=fresh_items,
        expiring_soon_items=expiring_soon_items,
        expired_items=expired_items,
        total_notifications=total_notifications,
        unread_notifications=unread_notifications,
        fridge_capacity=user.fridge_capacity,
        used_space=used_space,
        empty_space=max(user.fridge_capacity - used_space, 0)
    )


@app.get(
    "/api/dashboard/categories",
    response_model=List[schemas.CategoryStats]
)
async def get_category_stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Get statistics by category."""
    sync_item_statuses_and_notifications(db, user)

    item_query = user_item_query(db, user)
    categories = item_query.with_entities(FoodItem.category).distinct().all()

    stats = []
    for (category,) in categories:
        total = item_query.filter(
            FoodItem.category == category
        ).count()
        fresh = item_query.filter(
            FoodItem.category == category,
            FoodItem.status == StatusEnum.FRESH
        ).count()
        expiring_soon = item_query.filter(
            FoodItem.category == category,
            FoodItem.status == StatusEnum.EXPIRING_SOON
        ).count()
        expired = item_query.filter(
            FoodItem.category == category,
            FoodItem.status == StatusEnum.EXPIRED
        ).count()

        stats.append(schemas.CategoryStats(
            category=category,
            count=total,
            fresh=fresh,
            expiring_soon=expiring_soon,
            expired=expired
        ))

    return stats


@app.get("/api/dashboard/consumption-patterns")
async def get_consumption_patterns(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Get learned food consumption and waste patterns."""
    return build_pattern_insights(db, user)


# ==================== Notification Endpoints ====================

@app.get(
    "/api/notifications",
    response_model=List[schemas.NotificationResponse]
)
async def get_notifications(
    skip: int = 0,
    limit: int = 50,
    unread_only: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get notifications."""
    sync_item_statuses_and_notifications(db, user)

    query = db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.notification_type.in_([
            NotificationTypeEnum.EXPIRING_SOON,
            NotificationTypeEnum.EXPIRED,
        ])
    )

    if unread_only:
        query = query.filter(Notification.is_read.is_(False))

    notifications = query.order_by(
        desc(Notification.created_at)
    ).offset(skip).limit(limit).all()

    return notifications


@app.put("/api/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Mark notification as read."""
    notification = db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.id == notification_id
    ).first()

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.is_read = True
    db.add(notification)
    db.commit()

    return {"message": "Notification marked as read"}


@app.delete("/api/notifications/{notification_id}")
async def delete_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete a notification."""
    notification = db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.id == notification_id
    ).first()

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    db.delete(notification)
    db.commit()

    return {"message": "Notification deleted"}


# ==================== Health Check ====================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
