import React, { useRef, useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, useLocation, Link } from 'react-router-dom';
import { ToastContainer, toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import { FiHome, FiBox, FiBell, FiBarChart2, FiVolume2, FiGrid } from 'react-icons/fi';

import Dashboard from './components/Dashboard';
import Inventory from './components/Inventory';
import Analytics from './components/Analytics';
import NotificationCenter from './components/NotificationCenter';
import FoodModal from './components/FoodModal';
import AuthScreen from './components/AuthScreen';

import { authAPI, foodItemsAPI, dashboardAPI, notificationsAPI } from './services/api';

import './App.css';

const getItemsExpiringWithinOneDay = (items) => {
  const now = new Date();
  const oneDayFromNow = new Date(now.getTime() + 24 * 60 * 60 * 1000);

  return items.filter(item => {
    const expiryDate = new Date(item.expiry_date);
    return expiryDate > now && expiryDate <= oneDayFromNow;
  });
};

const EXPIRY_REMINDER_INTERVAL_MS = 60 * 60 * 1000;

const isNotificationForItemExpiringWithinOneDay = (notification, items) => {
  if (notification.notification_type !== 'expiring_soon') return false;

  const item = items.find(foodItem => foodItem.id === notification.item_id);
  if (!item) return false;

  const now = new Date();
  const expiryDate = new Date(item.expiry_date);
  const oneDayFromNow = new Date(now.getTime() + 24 * 60 * 60 * 1000);

  return expiryDate > now && expiryDate <= oneDayFromNow;
};

const toDateTimeLocal = (date) => {
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
};

const parseVoiceDate = (command) => {
  const now = new Date();
  const lower = command.toLowerCase();

  if (lower.includes('tomorrow')) {
    const date = new Date(now);
    date.setDate(date.getDate() + 1);
    date.setHours(20, 0, 0, 0);
    return date;
  }

  if (lower.includes('today')) {
    const date = new Date(now);
    date.setHours(20, 0, 0, 0);
    return date;
  }

  const isoMatch = lower.match(/(\d{4}-\d{1,2}-\d{1,2})/);
  if (isoMatch) {
    const parsed = new Date(`${isoMatch[1]}T20:00`);
    if (!Number.isNaN(parsed.getTime())) return parsed;
  }

  const namedDate = lower.match(/(?:on|date|expire on|expires on)\s+([a-z]+\s+\d{1,2}(?:\s+\d{4})?)/);
  if (namedDate) {
    const parsed = new Date(`${namedDate[1]} ${namedDate[1].match(/\d{4}/) ? '' : now.getFullYear()} 20:00`);
    if (!Number.isNaN(parsed.getTime())) return parsed;
  }

  return null;
};

const parseNumberAfter = (command, label, fallback = 1) => {
  const match = command.match(new RegExp(`${label}\\s+(\\d+)`, 'i'));
  return match ? Number(match[1]) : fallback;
};

const parsePhraseAfter = (command, labels) => {
  const labelGroup = labels.join('|');
  const match = command.match(new RegExp(`(?:${labelGroup})\\s+(.+?)(?:\\s+(?:quantity|space|shelf|location|expire|expires|on|update|delete|remove)\\b|$)`, 'i'));
  return match?.[1]?.trim() || '';
};

const parseVoiceCommand = (command) => {
  const lower = command.toLowerCase().trim();

  if (lower.startsWith('add ')) {
    const name = lower
      .replace(/^add\s+/, '')
      .split(/\s+(?:that|which|will|expires|expire|on|quantity|space|shelf|location)\b/)[0]
      .trim();
    const expiryDate = parseVoiceDate(lower);

    if (!name || !expiryDate) {
      return { error: 'Try: add milk that will expire tomorrow quantity 2 shelf top shelf' };
    }

    return {
      action: 'add',
      item: {
        item_name: name,
        category: 'Other',
        barcode: null,
        expiry_date: toDateTimeLocal(expiryDate),
        quantity: parseNumberAfter(lower, 'quantity', 1),
        unit: 'pcs',
        description: null,
        shelf_location: parsePhraseAfter(lower, ['shelf', 'location']) || null,
        space_units: parseNumberAfter(lower, 'space', 1)
      }
    };
  }

  if (lower.startsWith('delete ') || lower.startsWith('remove ')) {
    return {
      action: 'delete',
      name: lower.replace(/^(delete|remove)\s+/, '').trim()
    };
  }

  if (lower.startsWith('update ')) {
    const name = lower
      .replace(/^update\s+/, '')
      .split(/\s+(?:quantity|space|shelf|location|expire|expires|on)\b/)[0]
      .trim();
    const updates = {};
    const expiryDate = parseVoiceDate(lower);

    if (expiryDate) updates.expiry_date = toDateTimeLocal(expiryDate);
    if (lower.includes('quantity')) updates.quantity = parseNumberAfter(lower, 'quantity', 1);
    if (lower.includes('space')) updates.space_units = parseNumberAfter(lower, 'space', 1);

    const shelf = parsePhraseAfter(lower, ['shelf', 'location']);
    if (shelf) updates.shelf_location = shelf;

    if (!name || Object.keys(updates).length === 0) {
      return { error: 'Try: update milk quantity 2 shelf door rack' };
    }

    return { action: 'update', name, updates };
  }

  return { error: 'Say add, update, or delete followed by the item name.' };
};

function SidebarContent({ stats }) {
  const location = useLocation();

  const isActive = (path) => location.pathname === path ? 'active' : '';

  const navItems = [
    { path: '/', label: 'Dashboard', icon: FiHome },
    { path: '/inventory', label: 'Inventory', icon: FiBox },
    { path: '/notifications', label: 'Notifications', icon: FiBell },
    { path: '/analytics', label: 'Analytics', icon: FiBarChart2 },
  ];

  return (
    <div className="sidebar">
      <div className="sidebar-content">
        <nav className="sidebar-nav">
          {navItems.map(item => {
            const Icon = item.icon;
            const hasNotifications = item.path === '/notifications' && stats?.unread_notifications > 0;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`sidebar-link ${isActive(item.path)}`}
              >
                <Icon size={20} />
                <span>{item.label}</span>
                {hasNotifications && (
                  <div className="sidebar-badge">{stats.unread_notifications}</div>
                )}
              </Link>
            );
          })}
        </nav>
      </div>
    </div>
  );
}

function AppContent({ 
  items, 
  stats, 
  notifications, 
  categoryStats,
  patternInsights,
  isModalOpen,
  setIsModalOpen,
  editingItem,
  setEditingItem,
  onSaveItem,
  onDeleteItem,
  onMarkConsumed,
  onMarkWasted,
  onImageUpload,
  onMarkRead,
  onDeleteNotification
}) {
  const categories = [
    'Fruits', 'Vegetables', 'Dairy', 'Meat', 'Grains', 'Snacks',
    'Beverages', 'Frozen', 'Pantry', 'Other'
  ];

  return (
    <div className="main-content">
      <SidebarContent stats={stats} />

      <div className="content-wrapper">
        <div className="page-content">
          <Routes>
            <Route
              path="/"
              element={<Dashboard stats={stats} items={items} patternInsights={patternInsights} />}
            />
            <Route
              path="/inventory"
              element={
                <div>
                  <Inventory
                    items={items}
                    categories={categories}
                    onEdit={(item) => {
                      setEditingItem(item);
                      setIsModalOpen(true);
                    }}
                    onDelete={onDeleteItem}
                    onMarkConsumed={onMarkConsumed}
                    onMarkWasted={onMarkWasted}
                    onImageUpload={onImageUpload}
                  />
                  <button
                    className="fab-button"
                    onClick={() => {
                      setEditingItem(null);
                      setIsModalOpen(true);
                    }}
                    title="Add new item"
                  >
                    +
                  </button>
                </div>
              }
            />
            <Route
              path="/notifications"
              element={
                <NotificationCenter
                  notifications={notifications}
                  onMarkRead={onMarkRead}
                  onDelete={onDeleteNotification}
                />
              }
            />
            <Route
              path="/analytics"
              element={
                <Analytics
                  items={items}
                  categoryStats={categoryStats}
                />
              }
            />
          </Routes>
        </div>
      </div>

      <FoodModal
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false);
          setEditingItem(null);
        }}
        onSubmit={onSaveItem}
        initialData={editingItem}
      />

      <ToastContainer
        position="bottom-right"
        autoClose={3000}
        hideProgressBar={false}
        newestOnTop={false}
        closeOnClick
        rtl={false}
        pauseOnFocusLoss
        draggable
        pauseOnHover
      />
    </div>
  );
}

function App() {
  const [user, setUser] = useState(null);
  const [items, setItems] = useState([]);
  const [stats, setStats] = useState(null);
  const [notifications, setNotifications] = useState([]);
  const [categoryStats, setCategoryStats] = useState([]);
  const [patternInsights, setPatternInsights] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState(null);
  const [loading, setLoading] = useState(true);
  const [alertsEnabled, setAlertsEnabled] = useState(false);
  const alertsEnabledRef = useRef(false);
  const knownNotificationIds = useRef(new Set());
  const hasLoadedNotifications = useRef(false);
  const audioContextRef = useRef(null);
  const lastReminderAt = useRef(new Map());

  useEffect(() => {
    const token = localStorage.getItem('frise_token');
    if (!token) {
      setLoading(false);
      return undefined;
    }
    authAPI.me()
      .then(response => setUser(response.data))
      .catch(() => localStorage.removeItem('frise_token'))
      .finally(() => setLoading(false));
    return undefined;
  }, []);

  useEffect(() => {
    if (!user) return undefined;
    loadData();
    const interval = setInterval(loadData, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, [user]);

  const handleLogout = () => {
    localStorage.removeItem('frise_token');
    setUser(null);
    setItems([]);
    setStats(null);
  };

  const handleCapacityChange = async () => {
    const value = Number(window.prompt('How many space units can your fridge hold?', user.fridge_capacity));
    if (!Number.isInteger(value) || value < 1 || value > 1000) return;
    try {
      const response = await authAPI.updateFridge(value);
      setUser(response.data);
      loadData();
      toast.success('Fridge capacity updated');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not update fridge capacity');
    }
  };

  const playAlertSound = async ({ force = false } = {}) => {
    if (!force && !alertsEnabledRef.current) return false;

    try {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (!AudioContext) return false;

      const audioContext = audioContextRef.current || new AudioContext();
      audioContextRef.current = audioContext;

      if (audioContext.state === 'suspended') {
        await audioContext.resume();
      }

      if (audioContext.state !== 'running') return false;

      const startTime = audioContext.currentTime + 0.02;
      const beepTimes = [0, 0.22, 0.44];

      beepTimes.forEach((offset) => {
        const oscillator = audioContext.createOscillator();
        const gain = audioContext.createGain();
        const start = startTime + offset;
        const end = start + 0.14;

        oscillator.type = 'square';
        oscillator.frequency.setValueAtTime(980, start);
        oscillator.frequency.setValueAtTime(720, start + 0.07);

        gain.gain.setValueAtTime(0.0001, start);
        gain.gain.exponentialRampToValueAtTime(0.55, start + 0.015);
        gain.gain.exponentialRampToValueAtTime(0.0001, end);

        oscillator.connect(gain);
        gain.connect(audioContext.destination);
        oscillator.start(start);
        oscillator.stop(end + 0.02);
      });

      return true;
    } catch (error) {
      console.error('Failed to play Web Audio alert sound:', error);
    }

    try {
      const sampleRate = 44100;
      const duration = 0.75;
      const sampleCount = Math.floor(sampleRate * duration);
      const buffer = new ArrayBuffer(44 + sampleCount * 2);
      const view = new DataView(buffer);

      const writeString = (offset, value) => {
        for (let index = 0; index < value.length; index += 1) {
          view.setUint8(offset + index, value.charCodeAt(index));
        }
      };

      writeString(0, 'RIFF');
      view.setUint32(4, 36 + sampleCount * 2, true);
      writeString(8, 'WAVE');
      writeString(12, 'fmt ');
      view.setUint32(16, 16, true);
      view.setUint16(20, 1, true);
      view.setUint16(22, 1, true);
      view.setUint32(24, sampleRate, true);
      view.setUint32(28, sampleRate * 2, true);
      view.setUint16(32, 2, true);
      view.setUint16(34, 16, true);
      writeString(36, 'data');
      view.setUint32(40, sampleCount * 2, true);

      for (let index = 0; index < sampleCount; index += 1) {
        const time = index / sampleRate;
        const pulse =
          (time < 0.16) ||
          (time > 0.24 && time < 0.4) ||
          (time > 0.48 && time < 0.64);
        const frequency = time < 0.4 ? 980 : 720;
        const value = pulse
          ? Math.sin(2 * Math.PI * frequency * time) * 0.95
          : 0;

        view.setInt16(44 + index * 2, value * 32767, true);
      }

      const audioUrl = URL.createObjectURL(new Blob([view], { type: 'audio/wav' }));
      const audio = new Audio(audioUrl);
      audio.volume = 1;
      await audio.play();
      audio.addEventListener('ended', () => URL.revokeObjectURL(audioUrl), { once: true });
      return true;
    } catch (fallbackError) {
      console.error('Failed to play fallback alert sound:', fallbackError);
      return false;
    }
  };

  const showSystemNotification = (notification) => {
    if (
      !alertsEnabledRef.current ||
      !('Notification' in window) ||
      Notification.permission !== 'granted'
    ) {
      return;
    }

    const title = notification.notification_type === 'expired'
      ? 'Food expired'
      : 'Food expiring soon';

    const browserNotification = new Notification(title, {
      body: notification.message,
      tag: `frise-${notification.id}`,
      requireInteraction: notification.notification_type === 'expired'
    });

    browserNotification.onclick = () => {
      window.focus();
      browserNotification.close();
    };
  };

  const showExpiryReminder = (notification, toastIdPrefix = 'notification') => {
    toast.warning(notification.message, {
      toastId: `${toastIdPrefix}-${notification.id}`,
      autoClose: 8000
    });
    showSystemNotification(notification);
    playAlertSound();
    lastReminderAt.current.set(notification.id, Date.now());
  };

  const remindUnreadExpiringNotifications = (
    nextNotifications,
    nextItems,
    { forceDue = false } = {}
  ) => {
    const unreadExpiringSoon = nextNotifications.filter(notification =>
      !notification.is_read &&
      isNotificationForItemExpiringWithinOneDay(notification, nextItems)
    );

    const unreadIds = new Set(unreadExpiringSoon.map(notification => notification.id));
    Array.from(lastReminderAt.current.keys()).forEach((notificationId) => {
      if (!unreadIds.has(notificationId)) {
        lastReminderAt.current.delete(notificationId);
      }
    });

    unreadExpiringSoon.forEach((notification) => {
      const previousReminderAt = lastReminderAt.current.get(notification.id) || 0;
      const isDue = Date.now() - previousReminderAt >= EXPIRY_REMINDER_INTERVAL_MS;

      if (forceDue || isDue) {
        showExpiryReminder(notification, 'expiry-reminder');
      }
    });
  };

  const handleIncomingNotifications = (nextNotifications, nextItems) => {
    const unreadNotifications = nextNotifications.filter(notif => !notif.is_read);

    if (!hasLoadedNotifications.current) {
      unreadNotifications.forEach(notif => knownNotificationIds.current.add(notif.id));
      hasLoadedNotifications.current = true;
      remindUnreadExpiringNotifications(nextNotifications, nextItems);
      return;
    }

    const newUnreadNotifications = unreadNotifications.filter(
      notif => !knownNotificationIds.current.has(notif.id)
    );

    unreadNotifications.forEach(notif => knownNotificationIds.current.add(notif.id));

    newUnreadNotifications.forEach((notification) => {
      toast.warning(notification.message, {
        toastId: `notification-${notification.id}`,
        autoClose: notification.notification_type === 'expired' ? 8000 : 5000
      });
      showSystemNotification(notification);
      if (isNotificationForItemExpiringWithinOneDay(notification, nextItems)) {
        playAlertSound();
        lastReminderAt.current.set(notification.id, Date.now());
      }
    });

    remindUnreadExpiringNotifications(nextNotifications, nextItems);
  };

  const enableAlerts = async () => {
    try {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (AudioContext && !audioContextRef.current) {
        audioContextRef.current = new AudioContext();
      }

      if (audioContextRef.current?.state === 'suspended') {
        await audioContextRef.current.resume();
      }

      alertsEnabledRef.current = true;
      setAlertsEnabled(true);

      if ('Notification' in window && Notification.permission === 'default') {
        await Notification.requestPermission();
      }

      toast.success('Expiry pop-ups enabled. The buzzer will remind hourly for unread items expiring within 24 hours.');

      const latestUnread = notifications
        .filter(notif => !notif.is_read)
        .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))[0];

      if (latestUnread) {
        toast.warning(latestUnread.message, {
          toastId: `notification-current-${latestUnread.id}`,
          autoClose: latestUnread.notification_type === 'expired' ? 8000 : 5000
        });
        showSystemNotification(latestUnread);
      }

      remindUnreadExpiringNotifications(notifications, items, { forceDue: true });

    } catch (error) {
      console.error('Failed to enable alerts:', error);
      toast.error('Could not enable alerts in this browser');
    }
  };

  const loadData = async () => {
    try {
      const [itemsRes, statsRes, notifRes, categoryRes, patternsRes] = await Promise.all([
        foodItemsAPI.list(),
        dashboardAPI.getStats(),
        notificationsAPI.list(),
        dashboardAPI.getCategoryStats(),
        dashboardAPI.getConsumptionPatterns()
      ]);

      setItems(itemsRes.data);
      setStats(statsRes.data);
      setNotifications(notifRes.data);
      setCategoryStats(categoryRes.data);
      setPatternInsights(patternsRes.data);
      handleIncomingNotifications(notifRes.data, itemsRes.data);
      setLoading(false);
    } catch (error) {
      console.error('Failed to load data:', error);
      setLoading(false);
    }
  };

  // Create or update item
  const handleSaveItem = async (formData) => {
    try {
      if (editingItem?.id) {
        await foodItemsAPI.update(editingItem.id, formData);
      } else {
        await foodItemsAPI.create(formData);
      }
      setIsModalOpen(false);
      setEditingItem(null);
      loadData();
    } catch (error) {
      console.error('Failed to save item:', error);
      toast.error(error.response?.data?.detail || 'Failed to save item');
    }
  };

  // Delete item
  const handleDeleteItem = async (itemId) => {
    if (window.confirm('Are you sure you want to delete this item?')) {
      try {
        await foodItemsAPI.delete(itemId);
        loadData();
      } catch (error) {
        console.error('Failed to delete item:', error);
      }
    }
  };

  const handleMarkConsumed = async (itemId) => {
    try {
      await foodItemsAPI.consume(itemId);
      toast.success('Marked as used. Frise learned from it.');
      loadData();
    } catch (error) {
      console.error('Failed to mark item as used:', error);
      toast.error('Could not mark item as used');
    }
  };

  const handleMarkWasted = async (itemId) => {
    try {
      await foodItemsAPI.waste(itemId);
      toast.success('Marked as wasted. Frise will adjust suggestions.');
      loadData();
    } catch (error) {
      console.error('Failed to mark item as wasted:', error);
      toast.error('Could not mark item as wasted');
    }
  };

  // Upload image
  const handleImageUpload = async (itemId, file) => {
    try {
      await foodItemsAPI.uploadImage(itemId, file);
      loadData();
    } catch (error) {
      console.error('Failed to upload image:', error);
      throw error;
    }
  };

  // Mark notification as read
  const handleMarkRead = async (notifId) => {
    try {
      await notificationsAPI.markRead(notifId);
      loadData();
    } catch (error) {
      console.error('Failed to mark notification:', error);
    }
  };

  // Delete notification
  const handleDeleteNotification = async (notifId) => {
    try {
      await notificationsAPI.delete(notifId);
      loadData();
    } catch (error) {
      console.error('Failed to delete notification:', error);
    }
  };

  if (!user) {
    return <AuthScreen onAuthenticated={setUser} />;
  }

  return (
    <Router>
      <div className="App">
        <nav className="navbar">
          <div className="navbar-container">
            <Link to="/" className="navbar-brand">
              <span className="brand-icon">
                <FiGrid size={18} />
              </span>
              <span className="brand-name">Frise</span>
            </Link>
            <button
              className={`alert-toggle ${alertsEnabled ? 'enabled' : ''}`}
              onClick={enableAlerts}
              title="Enable expiry pop-ups and hourly expiry reminder buzzer"
              type="button"
            >
              {alertsEnabled ? <FiBell size={18} /> : <FiVolume2 size={18} />}
              <span>{alertsEnabled ? 'Alerts On' : 'Enable Alerts'}</span>
            </button>
            <button type="button" className="account-control" onClick={handleCapacityChange} title="Change fridge capacity">
              Fridge: {user.fridge_capacity} units
            </button>
            <button type="button" className="account-control" onClick={handleLogout}>
              Sign out
            </button>
          </div>
        </nav>
        {!alertsEnabled && (
          <div className="alert-setup-bar">
            <FiVolume2 size={20} />
            <span>Enable expiry pop-ups and hourly expiry reminder buzzer</span>
            <button type="button" onClick={enableAlerts}>
              Enable Alerts
            </button>
          </div>
        )}

        {loading ? (
          <div className="loading-screen">
            <div className="spinner"></div>
            <p>Loading Frise...</p>
          </div>
        ) : (
          <AppContent
            items={items}
            stats={stats}
            notifications={notifications}
            categoryStats={categoryStats}
            patternInsights={patternInsights}
            isModalOpen={isModalOpen}
            setIsModalOpen={setIsModalOpen}
            editingItem={editingItem}
            setEditingItem={setEditingItem}
            onSaveItem={handleSaveItem}
            onDeleteItem={handleDeleteItem}
            onMarkConsumed={handleMarkConsumed}
            onMarkWasted={handleMarkWasted}
            onImageUpload={handleImageUpload}
            onMarkRead={handleMarkRead}
            onDeleteNotification={handleDeleteNotification}
          />
        )}
      </div>
    </Router>
  );
}

export default App;
