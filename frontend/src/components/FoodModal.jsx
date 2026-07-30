import React, { useEffect, useRef, useState } from 'react';
import { BrowserMultiFormatReader } from '@zxing/browser';
import { FiCamera, FiLoader, FiSearch, FiX } from 'react-icons/fi';
import { foodItemsAPI } from '../services/api';
import '../styles/FoodModal.css';

const emptyFormData = {
  item_name: '',
  category: 'Fruits',
  barcode: '',
  expiry_date: '',
  quantity: 1,
  description: '',
  unit: 'pcs',
  shelf_location: 'Top Shelf',
  space_units: 1
};

const shelfCapacityUnits = {
  'Top Shelf': 8,
  'Middle Shelf': 8,
  'Bottom Shelf': 8,
  'Door Rack': 5,
  'Crisper Drawer': 5,
  Freezer: 4,
  'Chiller Tray': 2,
};

const monthLookup = {
  jan: 0,
  january: 0,
  feb: 1,
  february: 1,
  mar: 2,
  march: 2,
  apr: 3,
  april: 3,
  may: 4,
  jun: 5,
  june: 5,
  jul: 6,
  july: 6,
  aug: 7,
  august: 7,
  sep: 8,
  sept: 8,
  september: 8,
  oct: 9,
  october: 9,
  nov: 10,
  november: 10,
  dec: 11,
  december: 11,
};

const toDateTimeLocalValue = (date) => {
  const normalized = new Date(date);
  normalized.setHours(20, 0, 0, 0);
  const offset = normalized.getTimezoneOffset() * 60000;
  return new Date(normalized.getTime() - offset).toISOString().slice(0, 16);
};

const normalizeYear = (yearText) => {
  const year = Number(yearText);
  if (yearText.length === 2) return year + 2000;
  return year;
};

const isValidDateParts = (day, monthIndex, year) => {
  if (year < 2020 || year > 2100 || monthIndex < 0 || monthIndex > 11) return false;
  const date = new Date(year, monthIndex, day);
  return (
    date.getFullYear() === year &&
    date.getMonth() === monthIndex &&
    date.getDate() === day
  );
};

const parseExpiryDateFromText = (text) => {
  const candidates = [];
  const addCandidate = (day, monthIndex, year) => {
    if (!isValidDateParts(day, monthIndex, year)) return;
    const date = new Date(year, monthIndex, day, 20, 0, 0, 0);
    candidates.push(date);
  };

  const numericPattern = /\b(\d{1,4})[./\-\s](\d{1,2})[./\-\s](\d{2,4})\b/g;
  let match = numericPattern.exec(text);
  while (match) {
    const first = Number(match[1]);
    const second = Number(match[2]);
    const third = normalizeYear(match[3]);

    if (match[1].length === 4) {
      addCandidate(Number(match[3]), second - 1, first);
    } else {
      addCandidate(first, second - 1, third);
      if (first <= 12 && second <= 12) {
        addCandidate(second, first - 1, third);
      }
    }
    match = numericPattern.exec(text);
  }

  const monthPattern = /\b(\d{1,2})\s*(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s*(\d{2,4})?\b/gi;
  match = monthPattern.exec(text);
  while (match) {
    addCandidate(
      Number(match[1]),
      monthLookup[match[2].toLowerCase()],
      match[3] ? normalizeYear(match[3]) : new Date().getFullYear()
    );
    match = monthPattern.exec(text);
  }

  const reverseMonthPattern = /\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s*(\d{1,2})(?:,)?\s*(\d{2,4})?\b/gi;
  match = reverseMonthPattern.exec(text);
  while (match) {
    addCandidate(
      Number(match[2]),
      monthLookup[match[1].toLowerCase()],
      match[3] ? normalizeYear(match[3]) : new Date().getFullYear()
    );
    match = reverseMonthPattern.exec(text);
  }

  const now = new Date();
  const futureCandidates = candidates
    .filter(date => date >= now)
    .sort((a, b) => a - b);

  return futureCandidates[0] || candidates.sort((a, b) => b - a)[0] || null;
};

const FoodModal = ({ isOpen, onClose, onSubmit, initialData }) => {
  const [formData, setFormData] = useState(emptyFormData);
  const [errors, setErrors] = useState({});
  const [barcodeStatus, setBarcodeStatus] = useState('');
  const [expiryScanStatus, setExpiryScanStatus] = useState('');
  const [ocrScanStatus, setOcrScanStatus] = useState('');
  const [isLookingUpBarcode, setIsLookingUpBarcode] = useState(false);
  const [isScanningBarcode, setIsScanningBarcode] = useState(false);
  const [isOcrScanning, setIsOcrScanning] = useState(false);
  const [ocrScanMode, setOcrScanMode] = useState(null);
  const formDataRef = useRef(emptyFormData);
  const videoRef = useRef(null);
  const ocrVideoRef = useRef(null);
  const barcodeReaderRef = useRef(null);
  const barcodeControlsRef = useRef(null);
  const barcodeStreamRef = useRef(null);
  const scanLockedRef = useRef(false);
  const barcodeLookupTimerRef = useRef(null);
  const ocrStreamRef = useRef(null);
  const ocrAutoCaptureRef = useRef(null);
  const ocrScanAttemptsRef = useRef(0);
  const ocrActiveRef = useRef(false);
  const ocrScanModeRef = useRef(null);

  const categories = [
    'Fruits', 'Vegetables', 'Dairy', 'Meat', 'Grains', 'Snacks', 
    'Beverages', 'Frozen', 'Pantry', 'Other'
  ];

  const units = ['pcs', 'kg', 'lb', 'liter', 'ml', 'dozen', 'box'];
  const shelfLocations = [
    'Top Shelf',
    'Middle Shelf',
    'Bottom Shelf',
    'Door Rack',
    'Crisper Drawer',
    'Freezer',
    'Chiller Tray'
  ];
  const selectedShelfCapacity = shelfCapacityUnits[formData.shelf_location] || 1;

  useEffect(() => {
    if (!isOpen) return;

    const nextFormData = initialData ? {
      ...initialData,
      barcode: initialData.barcode || '',
      description: initialData.description || '',
      expiry_date: initialData.expiry_date?.slice(0, 16) || '',
      unit: initialData.unit || 'pcs',
      shelf_location: initialData.shelf_location || 'Top Shelf',
      space_units: initialData.space_units || 1
    } : { ...emptyFormData };

    setFormData(nextFormData);
    formDataRef.current = nextFormData;
    setErrors({});
    setBarcodeStatus('');
    setExpiryScanStatus('');
  }, [initialData, isOpen]);

  useEffect(() => () => {
    if (barcodeControlsRef.current) {
      barcodeControlsRef.current.stop();
      barcodeControlsRef.current = null;
    }
    if (barcodeStreamRef.current) {
      barcodeStreamRef.current.getTracks().forEach(track => track.stop());
      barcodeStreamRef.current = null;
    }
    if (ocrStreamRef.current) {
      ocrStreamRef.current.getTracks().forEach(track => track.stop());
      ocrStreamRef.current = null;
    }
    if (ocrAutoCaptureRef.current) {
      window.clearTimeout(ocrAutoCaptureRef.current);
      ocrAutoCaptureRef.current = null;
    }
    if (barcodeLookupTimerRef.current) {
      window.clearTimeout(barcodeLookupTimerRef.current);
      barcodeLookupTimerRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (isOpen) return;

    if (barcodeControlsRef.current) {
      barcodeControlsRef.current.stop();
      barcodeControlsRef.current = null;
    }
    if (barcodeStreamRef.current) {
      barcodeStreamRef.current.getTracks().forEach(track => track.stop());
      barcodeStreamRef.current = null;
    }
    if (ocrStreamRef.current) {
      ocrStreamRef.current.getTracks().forEach(track => track.stop());
      ocrStreamRef.current = null;
    }
    if (ocrAutoCaptureRef.current) {
      window.clearTimeout(ocrAutoCaptureRef.current);
      ocrAutoCaptureRef.current = null;
    }
    if (barcodeLookupTimerRef.current) {
      window.clearTimeout(barcodeLookupTimerRef.current);
      barcodeLookupTimerRef.current = null;
    }

    scanLockedRef.current = false;
    ocrActiveRef.current = false;
    ocrScanModeRef.current = null;
    setIsScanningBarcode(false);
    setIsOcrScanning(false);
    setOcrScanMode(null);
  }, [isOpen]);

  const clearBarcodeLookupTimer = () => {
    if (barcodeLookupTimerRef.current) {
      window.clearTimeout(barcodeLookupTimerRef.current);
      barcodeLookupTimerRef.current = null;
    }
  };

  const scheduleBarcodeLookup = (barcode) => {
    clearBarcodeLookupTimer();
    if (!/^[A-Za-z0-9._-]{4,64}$/.test(barcode)) {
      return;
    }
    barcodeLookupTimerRef.current = window.setTimeout(() => {
      handleBarcodeLookup(barcode);
    }, 700);
  };

  const stopOcrStream = (preserveStatus = false) => {
    if (ocrStreamRef.current) {
      ocrStreamRef.current.getTracks().forEach(track => track.stop());
      ocrStreamRef.current = null;
    }
    if (ocrAutoCaptureRef.current) {
      window.clearTimeout(ocrAutoCaptureRef.current);
      ocrAutoCaptureRef.current = null;
    }
    if (ocrVideoRef.current) {
      ocrVideoRef.current.pause();
      ocrVideoRef.current.srcObject = null;
    }
    ocrActiveRef.current = false;
    ocrScanModeRef.current = null;
    setIsOcrScanning(false);
    setOcrScanMode(null);
    if (!preserveStatus) {
      setOcrScanStatus('');
      setExpiryScanStatus('');
    }
  };

  const setModeStatus = (message) => {
    setOcrScanStatus(message);
    setExpiryScanStatus(message);
  };

  const scheduleOcrAttempt = (delay = 1800) => {
    if (ocrAutoCaptureRef.current) {
      window.clearTimeout(ocrAutoCaptureRef.current);
      ocrAutoCaptureRef.current = null;
    }

    ocrAutoCaptureRef.current = window.setTimeout(async () => {
      if (!ocrActiveRef.current || ocrScanModeRef.current !== 'expiry') return;
      ocrScanAttemptsRef.current += 1;
      const success = await captureOcrFrame();
      if (!success && ocrActiveRef.current && ocrScanAttemptsRef.current < 3) {
        setModeStatus(`Retrying expiry scan (${ocrScanAttemptsRef.current + 1}/3)...`);
        scheduleOcrAttempt(1800);
      }
    }, delay);
  };

  const startOcrScan = async () => {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setModeStatus('Camera not available in this browser');
      return;
    }

    stopBarcodeScan();
    stopOcrStream();

    setModeStatus('Starting camera...');
    setOcrScanMode('expiry');
    ocrScanModeRef.current = 'expiry';
    setIsOcrScanning(true);
    ocrActiveRef.current = true;
    ocrScanAttemptsRef.current = 0;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
      ocrStreamRef.current = stream;
      if (ocrVideoRef.current) {
        ocrVideoRef.current.srcObject = stream;
        await ocrVideoRef.current.play();
      }

      setModeStatus('Camera ready. Hold the expiry label steady; scanning automatically...');
      scheduleOcrAttempt(1800);
    } catch (error) {
      console.error('OCR camera error', error);
      setModeStatus('Unable to access camera. Allow permission and try again.');
      setIsOcrScanning(false);
      setOcrScanMode(null);
      ocrScanModeRef.current = null;
      ocrActiveRef.current = false;
    }
  };

  const captureOcrFrame = async () => {
    if (!ocrVideoRef.current || !ocrVideoRef.current.videoWidth) {
      setModeStatus('Camera not ready');
      return;
    }

    if (ocrAutoCaptureRef.current) {
      window.clearTimeout(ocrAutoCaptureRef.current);
      ocrAutoCaptureRef.current = null;
    }

    setModeStatus('Capturing image...');

    const canvas = document.createElement('canvas');
    canvas.width = ocrVideoRef.current.videoWidth;
    canvas.height = ocrVideoRef.current.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(ocrVideoRef.current, 0, 0, canvas.width, canvas.height);

    try {
      const imageBlob = await new Promise((resolve, reject) => {
        canvas.toBlob((blob) => {
          if (!blob) {
            reject(new Error('Could not create image snapshot'));
            return;
          }
          resolve(blob);
        }, 'image/jpeg', 0.95);
      });

      const snapshotFile = new File([imageBlob], 'expiry-label.jpg', {
        type: 'image/jpeg'
      });
      const response = await foodItemsAPI.scanExpiryDate(snapshotFile);
      const data = response?.data || {};
      const parsedDate = data.expiry_date ? new Date(data.expiry_date) : null;

      if (!parsedDate || Number.isNaN(parsedDate.getTime())) {
        setModeStatus('Could not read expiry date. Try a clearer view of the date label.');
        return false;
      }

      setFormData(prev => ({
        ...prev,
        expiry_date: toDateTimeLocalValue(parsedDate)
      }));
      setModeStatus(`Expiry date filled: ${parsedDate.toLocaleDateString()}`);
      stopOcrStream(true);
      return true;
    } catch (error) {
      console.error('OCR capture error', error);
      const message = error.response?.data?.detail || 'OCR scan failed. Try again with a clearer label.';
      setModeStatus(message);
      stopOcrStream(true);
      return false;
    }
  };

  const normalizeBarcode = (value) => value.replace(/\s/g, '').trim();


  const handleChange = (e) => {
    const { name, value } = e.target;
    const normalizedValue = name === 'barcode' ? normalizeBarcode(value) : value;
    const nextValue = {
      ...formDataRef.current,
      [name]: normalizedValue
    };
    formDataRef.current = nextValue;
    setFormData(nextValue);

    if (errors[name]) {
      setErrors(prev => ({
        ...prev,
        [name]: ''
      }));
    }

    if (name === 'barcode') {
      if (/^[A-Za-z0-9._-]{4,64}$/.test(normalizedValue)) {
        scheduleBarcodeLookup(normalizedValue);
      } else {
        clearBarcodeLookupTimer();
      }
    }
  };

  const handleBarcodeKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      const nextBarcode = normalizeBarcode(formDataRef.current.barcode || '');
      const nextValue = {
        ...formDataRef.current,
        barcode: nextBarcode
      };
      formDataRef.current = nextValue;
      setFormData(nextValue);
      clearBarcodeLookupTimer();
      handleBarcodeLookup(nextBarcode);
    }
  };

  const applyProductDetails = (details) => {
    const nextItemName = details?.item_name?.trim() || '';
    const nextCategory = details?.category?.trim() || 'Other';
    const nextDescription = details?.description?.trim() || '';

    const nextValue = {
      ...formDataRef.current,
      barcode: details?.barcode || formDataRef.current.barcode,
      item_name: nextItemName || formDataRef.current.item_name,
      category: nextCategory || formDataRef.current.category,
      description: nextDescription || formDataRef.current.description,
    };
    formDataRef.current = nextValue;
    setFormData(nextValue);
  };

  const handleBarcodeLookup = async (barcode = formDataRef.current.barcode) => {
    const normalizedBarcode = normalizeBarcode(String(barcode || formDataRef.current.barcode || ''));
    if (!normalizedBarcode) {
      console.log('Barcode lookup skipped: no barcode value');
      setErrors(prev => ({ ...prev, barcode: 'Enter or scan a barcode first' }));
      return;
    }

    clearBarcodeLookupTimer();
    setIsLookingUpBarcode(true);
    setBarcodeStatus('Looking up product...');
    try {
      console.log('Barcode lookup request', normalizedBarcode);
      const response = await foodItemsAPI.lookupBarcode(normalizedBarcode);
      const data = response?.data || {};
      console.log('Barcode lookup response', data);

      const nextValue = {
        ...formDataRef.current,
        barcode: normalizedBarcode
      };
      formDataRef.current = nextValue;
      setFormData(nextValue);
      if (!data.found) {
        setBarcodeStatus('No product details found for this barcode');
        return;
      }

      applyProductDetails(data);
      setBarcodeStatus(`Filled details from ${data.source || 'barcode lookup'}`);
    } catch (error) {
      console.error('Barcode lookup failed', error);
      setBarcodeStatus(error.response?.data?.detail || 'Barcode lookup failed');
    } finally {
      setIsLookingUpBarcode(false);
    }
  };

  const stopBarcodeScan = () => {
    if (barcodeControlsRef.current) {
      barcodeControlsRef.current.stop();
      barcodeControlsRef.current = null;
    }
    if (barcodeStreamRef.current) {
      barcodeStreamRef.current.getTracks().forEach(track => track.stop());
      barcodeStreamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.pause();
      videoRef.current.srcObject = null;
    }
    scanLockedRef.current = false;
    setIsScanningBarcode(false);
  };

  const waitForVideoReady = async (targetRef) => {
    for (let i = 0; i < 20; i += 1) {
      if (targetRef.current) {
        return targetRef.current;
      }
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
    return targetRef.current;
  };

  const startBarcodeScan = async () => {
    if (isScanningBarcode) {
      stopBarcodeScan();
      return;
    }

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setBarcodeStatus('Camera not available in this browser');
      return;
    }

    stopOcrStream();
    setBarcodeStatus('Requesting camera access...');
    setIsScanningBarcode(true);
    scanLockedRef.current = false;

    try {
      if (!barcodeReaderRef.current) {
        barcodeReaderRef.current = new BrowserMultiFormatReader();
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: 'environment',
          width: { ideal: 1280 },
          height: { ideal: 720 }
        }
      });

      barcodeStreamRef.current = stream;
      const videoElement = await waitForVideoReady(videoRef);
      if (!videoElement) {
        throw new Error('Camera preview is not available yet');
      }

      videoElement.srcObject = stream;
      videoElement.setAttribute('playsinline', 'true');
      videoElement.muted = true;
      await videoElement.play();

      setBarcodeStatus('Camera active. Hold barcode in front of the camera.');

      barcodeControlsRef.current = await barcodeReaderRef.current.decodeFromStream(
        stream,
        videoElement,
        (result, error) => {
          if (error) {
            console.debug('Barcode scan callback error', error);
            return;
          }
          if (!result || scanLockedRef.current) return;

          scanLockedRef.current = true;
          const scannedBarcode = normalizeBarcode(result.getText());
          setFormData(prev => ({ ...prev, barcode: scannedBarcode }));
          setBarcodeStatus('Barcode scanned. Fetching product details...');
          stopBarcodeScan();
          void handleBarcodeLookup(scannedBarcode);
        }
      );
    } catch (error) {
      console.error('Barcode scan error', error);
      const message = error.name === 'NotAllowedError'
        ? 'Camera permission denied. Allow camera access and retry.'
        : error.name === 'NotFoundError'
          ? 'No camera found. Use a device with a camera.'
          : 'Camera scan failed. Check camera permission or enter barcode manually.';
      setBarcodeStatus(message);
      stopBarcodeScan();
    }
  };

  const validateForm = () => {
    const newErrors = {};

    if (!formData.item_name.trim()) {
      newErrors.item_name = 'Item name is required';
    }
    if (!formData.expiry_date) {
      newErrors.expiry_date = 'Expiry date is required';
    }
    if (formData.quantity < 1) {
      newErrors.quantity = 'Quantity must be at least 1';
    }
    if (formData.space_units < 1) {
      newErrors.space_units = 'Space must be at least 1';
    }
    if (formData.barcode && !/^[A-Za-z0-9._-]{4,64}$/.test(formData.barcode)) {
      newErrors.barcode = 'Enter a valid barcode without spaces';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (validateForm()) {
      const payload = {
        ...formData,
        barcode: formData.barcode?.trim() || null,
        description: formData.description?.trim() || null,
        shelf_location: formData.shelf_location?.trim() || null,
        quantity: Number(formData.quantity),
        space_units: Number(formData.space_units)
      };

      onSubmit(payload);
    }
  };

  if (!isOpen) return null;

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  return (
    <div className="modal-overlay" onClick={handleOverlayClick}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{initialData?.id ? 'Edit Food Item' : 'Add New Food Item'}</h2>
          <button className="close-btn" onClick={onClose}>
            <FiX size={24} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          <div className="form-section">
            <div className="section-header">
              <h3>Item details</h3>
              <p>Start with the item name and category.</p>
            </div>

            <div className="form-group">
              <label>Item Name *</label>
              <input
                type="text"
                name="item_name"
                value={formData.item_name}
                onChange={handleChange}
                placeholder="e.g., Fresh Milk"
                className={errors.item_name ? 'input-error' : ''}
              />
              {errors.item_name && <span className="error-text">{errors.item_name}</span>}
            </div>

            <div className="form-group">
              <label>Category *</label>
              <select
                name="category"
                value={formData.category}
                onChange={handleChange}
              >
                {categories.map(cat => (
                  <option key={cat} value={cat}>{cat}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="form-section">
            <div className="section-header">
              <h3>Scan & identify</h3>
              <p>Use barcode lookup or the packed-item camera for faster entry.</p>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Barcode scan</label>
                <div className="input-with-actions">
                  <input
                    type="text"
                    name="barcode"
                    value={formData.barcode}
                    onChange={handleChange}
                    onKeyDown={handleBarcodeKeyDown}
                    placeholder="Enter barcode or scan below"
                    inputMode="numeric"
                    autoComplete="off"
                    className={errors.barcode ? 'input-error' : ''}
                  />
                  <button
                    type="button"
                    className="icon-action"
                    onClick={() => handleBarcodeLookup()}
                    disabled={isLookingUpBarcode}
                    title="Look up barcode"
                  >
                    {isLookingUpBarcode ? <FiLoader size={16} /> : <FiSearch size={16} />}
                  </button>
                </div>
                <button
                  type="button"
                  className="btn btn-secondary barcode-scan-btn"
                  onClick={startBarcodeScan}
                  disabled={isScanningBarcode}
                  title={isScanningBarcode ? 'Stop scanning' : 'Scan barcode'}
                >
                  {isScanningBarcode ? 'Stop barcode scan' : 'Scan barcode'}
                </button>
                <span className="helper-text">Enter or scan the barcode to fetch product details.</span>
                {errors.barcode && <span className="error-text">{errors.barcode}</span>}
                {barcodeStatus && <span className="helper-text">{barcodeStatus}</span>}
              </div>

              <div className="form-group">
                <label>Packed item OCR camera</label>
                <button
                  type="button"
                  className="scan-action-card"
                  onClick={startOcrScan}
                  disabled={isOcrScanning}
                  title="Scan packed item expiry"
                >
                  <span className="scan-action-icon">
                    {isOcrScanning ? <FiLoader size={18} /> : <FiCamera size={18} />}
                  </span>
                  <span className="scan-action-content">
                    <span className="scan-action-title">Scan packed item expiry</span>
                    <span className="scan-action-copy">Use the camera to read the expiry label automatically.</span>
                  </span>
                </button>
                <span className="helper-text">This helps fill the expiry date from the package label.</span>
                {expiryScanStatus && <span className="helper-text">{expiryScanStatus}</span>}
              </div>
            </div>

            {(isScanningBarcode || isOcrScanning) && (
              <div className="scanner-panel">
                {isScanningBarcode && (
                  <>
                    <video ref={videoRef} className="scanner-video" muted playsInline />
                    <button type="button" className="btn btn-secondary" onClick={stopBarcodeScan}>
                      Stop Barcode Scanner
                    </button>
                  </>
                )}
                {isOcrScanning && (
                  <>
                    <video ref={ocrVideoRef} className="scanner-video" muted playsInline />
                    <div className="scanner-actions">
                      <button type="button" className="btn btn-primary" onClick={captureOcrFrame}>
                        Capture
                      </button>
                      <button type="button" className="btn btn-secondary" onClick={stopOcrStream}>
                        Stop Scan
                      </button>
                    </div>
                    <span className="helper-text">{ocrScanStatus}</span>
                  </>
                )}
              </div>
            )}
          </div>

          <div className="form-section">
            <div className="section-header">
              <h3>Storage & quantity</h3>
              <p>Set the storage location and amount for the item.</p>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Shelf Location</label>
                <select
                  name="shelf_location"
                  value={formData.shelf_location}
                  onChange={handleChange}
                >
                  {shelfLocations.map(location => (
                    <option key={location} value={location}>{location}</option>
                  ))}
                </select>
                <span className="helper-text">
                  Capacity: {selectedShelfCapacity} unit{selectedShelfCapacity !== 1 ? 's' : ''}
                </span>
              </div>

              <div className="form-group">
                <label>Fridge Space Used *</label>
                <input
                  type="number"
                  name="space_units"
                  value={formData.space_units}
                  onChange={handleChange}
                  min="1"
                  max={selectedShelfCapacity}
                  className={errors.space_units ? 'input-error' : ''}
                />
                {errors.space_units && <span className="error-text">{errors.space_units}</span>}
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Expiry Date *</label>
                <input
                  type="datetime-local"
                  name="expiry_date"
                  value={formData.expiry_date}
                  onChange={handleChange}
                  className={errors.expiry_date ? 'input-error' : ''}
                />
                {errors.expiry_date && <span className="error-text">{errors.expiry_date}</span>}
              </div>

              <div className="form-group">
                <label>Quantity *</label>
                <div className="quantity-input">
                  <input
                    type="number"
                    name="quantity"
                    value={formData.quantity}
                    onChange={handleChange}
                    min="1"
                    className={errors.quantity ? 'input-error' : ''}
                  />
                  <select
                    name="unit"
                    value={formData.unit}
                    onChange={handleChange}
                  >
                    {units.map(unit => (
                      <option key={unit} value={unit}>{unit}</option>
                    ))}
                  </select>
                </div>
                {errors.quantity && <span className="error-text">{errors.quantity}</span>}
              </div>
            </div>
          </div>

          <div className="form-group">
            <label>Description</label>
            <textarea
              name="description"
              value={formData.description}
              onChange={handleChange}
              placeholder="Add notes about this item..."
              rows="3"
            />
          </div>

          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary">
              {initialData?.id ? 'Update Item' : 'Add Item'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default FoodModal;
