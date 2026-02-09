/**
 * WhatsApp QR bot — serves /health, /status, /qr, POST /reconnect for API bridge.
 * Persists QR state to /data/wa-auth/last_qr.json for reliability across restarts.
 * AUTH_FOLDER, PORT from env.
 */
const express = require('express');
const fs = require('fs');
const path = require('path');
const { default: makeWASocket, useMultiFileAuthState } = require('@whiskeysockets/baileys');
const pino = require('pino');
const qrcode = require('qrcode-terminal');

const logger = pino({ level: process.env.LOG_LEVEL || 'info' });
const PORT = parseInt(process.env.PORT || '3100', 10);
// Ensure AUTH_FOLDER is EXACTLY /data/wa-auth (required by docker volume mount)
const AUTH_FOLDER = process.env.AUTH_FOLDER || '/data/wa-auth';
const QR_EXPIRY_SECONDS = 120; // QR expires in 120 seconds

// Helper for writing QR state file (matches exact format requested)
const QR_FILE = path.join(AUTH_FOLDER, 'last_qr.json');
const nowTs = () => Math.floor(Date.now() / 1000);

function writeLastQr(payload) {
  try {
    fs.mkdirSync(AUTH_FOLDER, { recursive: true });
    fs.writeFileSync(QR_FILE, JSON.stringify(payload, null, 2), 'utf-8');
  } catch (e) {
    logger.warn('writeLastQr: %s', e.message);
  }
}

const app = express();
app.use(express.json());
let sock = null;
let qrValue = null;
let qrTimestamp = null;
let lastDisconnectReason = null;
let connected = false;
let connecting = false;
let phoneNumber = null;
let connectionState = 'disconnected'; // disconnected, connecting, qr_ready, connected

/**
 * Load persisted QR state from file.
 */
function loadQrState() {
  try {
    if (fs.existsSync(QR_FILE)) {
      const content = fs.readFileSync(QR_FILE, 'utf-8');
      const state = JSON.parse(content);
      const now = Math.floor(Date.now() / 1000);
      
      // Check if QR is still valid (not expired)
      if (state.status === 'qr_ready' && state.qr && state.expires_at) {
        if (now < state.expires_at) {
          qrValue = state.qr;
          qrTimestamp = state.updated_at * 1000; // Convert to ms
          connectionState = 'qr_ready';
          logger.info({ event: 'QR_LOADED_FROM_DISK' }, 'Loaded QR from disk (expires in %ds)', state.expires_at - now);
          return;
        } else {
          logger.info({ event: 'QR_EXPIRED' }, 'QR from disk expired, clearing');
        }
      } else if (state.status === 'connected') {
        connectionState = 'disconnected'; // Will reconnect on startup
        logger.info({ event: 'STATE_LOADED' }, 'Previous state: connected, will reconnect');
        return;
      }
    }
  } catch (e) {
    logger.warn({ event: 'QR_STATE_LOAD_ERROR' }, 'Failed to load QR state: %s', e.message);
  }
  // Default: no valid QR
  qrValue = null;
  qrTimestamp = null;
}

/**
 * Persist QR state to file.
 */
function saveQrState(status, qr = null, reason = null) {
  try {
    const now = Math.floor(Date.now() / 1000);
    const state = {
      qr: qr,
      status: status,
      expires_at: status === 'qr_ready' && qr ? now + QR_EXPIRY_SECONDS : null,
      updated_at: now,
      lastDisconnectReason: reason || null,
    };
    
    // Ensure directory exists
    if (!fs.existsSync(AUTH_FOLDER)) {
      fs.mkdirSync(AUTH_FOLDER, { recursive: true });
    }
    
    fs.writeFileSync(QR_FILE, JSON.stringify(state, null, 2), 'utf-8');
    logger.debug({ event: 'QR_STATE_SAVED', status }, 'Saved QR state: %s', status);
  } catch (e) {
    logger.warn({ event: 'QR_STATE_SAVE_ERROR' }, 'Failed to save QR state: %s', e.message);
  }
}

function clearAuthFolder() {
  try {
    if (fs.existsSync(AUTH_FOLDER)) {
      for (const f of fs.readdirSync(AUTH_FOLDER)) {
        const p = path.join(AUTH_FOLDER, f);
        // Don't delete last_qr.json, only auth files
        if (f === path.basename(QR_FILE)) {
          continue;
        }
        const stat = fs.statSync(p);
        if (stat.isDirectory()) {
          fs.rmSync(p, { recursive: true });
        } else {
          fs.unlinkSync(p);
        }
      }
    }
  } catch (e) {
    logger.warn({ event: 'CLEAR_AUTH_ERROR' }, 'clearAuthFolder: %s', e.message);
  }
}

async function connect() {
  if (connecting) {
    logger.warn({ event: 'CONNECT_ALREADY_IN_PROGRESS' }, 'connect() called while already connecting, skipping');
    return;
  }
  connecting = true;
  qrValue = null;
  lastDisconnectReason = null;
  connected = false;
  
  try {
    if (sock) {
      try { 
        sock.end(undefined); 
        logger.info({ event: 'SOCKET_CLOSED' }, 'Closed existing socket');
      } catch (e) {
        logger.warn({ event: 'SOCKET_CLOSE_ERROR' }, 'Error closing socket: %s', e.message);
      }
      sock = null;
    }
    
    logger.info({ AUTH_FOLDER }, 'WA_CONNECT_START');
    
    // Use AUTH_FOLDER (defaults to /data/wa-auth, set via env in docker-compose)
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_FOLDER);
    logger.info('WA_AUTH_STATE_READY');
    
    sock = makeWASocket({
      auth: state,
      printQRInTerminal: false,
      logger: pino({ level: 'info' }), // Changed from 'silent' to 'info' for visibility
    });
    
    logger.info('Starting Baileys socket...');

    sock.ev.on('connection.update', (up) => {
      // QR event
      if (up.qr) {
        qrValue = up.qr;
        logger.info('QR_READY');
        writeLastQr({ qr: up.qr, status: 'qr_ready', expires_at: nowTs() + 60, updated_at: nowTs() });
        qrcode.generate(up.qr, { small: true });
      }
      
      // Connection state changes
      if (up.connection === 'open') {
        connected = true;
        qrValue = null;
        logger.info('CONNECTED');
        writeLastQr({ qr: null, status: 'connected', expires_at: 0, updated_at: nowTs() });
        phoneNumber = up.me?.id?.split(':')[0] || null;
      } else if (up.connection === 'close') {
        lastDisconnectReason = up.lastDisconnectReason || null;
        connected = false;
        logger.info({ reason: lastDisconnectReason }, 'DISCONNECTED');
        writeLastQr({ qr: null, status: 'disconnected', lastDisconnectReason, expires_at: 0, updated_at: nowTs() });
        phoneNumber = null;
      }
      
      if (up.isNewLogin) {
        logger.info({ event: 'NEW_LOGIN' }, 'New login detected');
      }
      
      // Ensure connecting flag is reset at end of handler
      connecting = false;
    });

    sock.ev.on('creds.update', saveCreds);
    
    logger.info({ event: 'SOCKET_CREATED' }, 'Baileys socket created, waiting for connection events...');
  } catch (e) {
    connecting = false;
    logger.error('connect fatal: %s', e?.stack || e?.message || String(e));
    throw e; // keep behavior unless it causes crash loops; if it does, remove throw and just return
  }
}

app.get('/health', (req, res) => {
  res.json({ status: 'ok' });
});

app.get('/debug/auth', (req, res) => {
  // READ ONLY endpoint to confirm file creation
  const result = {
    AUTH_FOLDER: AUTH_FOLDER,
    exists: false,
    files: [],
    last_qr_json: null,
    error: null,
  };
  
  try {
    result.exists = fs.existsSync(AUTH_FOLDER);
    
    if (result.exists) {
      try {
        result.files = fs.readdirSync(AUTH_FOLDER);
      } catch (e) {
        result.error = `readdirSync failed: ${e.message}`;
      }
      
      // Try to read last_qr.json if it exists
      const qrFilePath = path.join(AUTH_FOLDER, 'last_qr.json');
      if (fs.existsSync(qrFilePath)) {
        try {
          const content = fs.readFileSync(qrFilePath, 'utf-8');
          // Cap output length to 2KB
          result.last_qr_json = content.length > 2048 ? content.substring(0, 2048) + '... (truncated)' : content;
        } catch (e) {
          result.error = `readFileSync failed: ${e.message}`;
        }
      }
    }
  } catch (e) {
    result.error = `General error: ${e.message}`;
  }
  
  res.json(result);
});

app.get('/status', (req, res) => {
  res.json({
    connected,
    status: connected ? 'connected' : (qrValue ? 'qr_ready' : (connecting ? 'not_ready' : 'disconnected')),
    lastDisconnectReason: lastDisconnectReason || null,
    server_time: new Date().toISOString(),
  });
});

app.get('/qr', (req, res) => {
  const now = Date.now();
  let expiresIn = 0;
  
  if (connected) {
    res.json({
      status: 'connected',
      qr: null,
      expires_in: 0,
      server_time: new Date().toISOString(),
    });
    return;
  }
  
  if (qrValue && qrTimestamp) {
    const elapsed = Math.floor((now - qrTimestamp) / 1000);
    expiresIn = Math.max(0, QR_EXPIRY_SECONDS - elapsed);
    
    if (expiresIn <= 0) {
      // QR expired
      qrValue = null;
      qrTimestamp = null;
      connectionState = 'not_ready';
      saveQrState('not_ready', null);
    }
  }
  
  res.json({
    status: qrValue ? 'qr_ready' : 'not_ready',
    qr: qrValue || null,
    expires_in: expiresIn,
    server_time: new Date().toISOString(),
  });
});

app.post('/reconnect', async (req, res) => {
  // Return immediately - reconnect is non-blocking
  res.json({ ok: true, message: 'Reconnect triggered. Poll /qr for QR code.' });
  
  // Perform reconnect asynchronously (fire-and-forget)
  (async () => {
    try {
      console.log('RECONNECT_REQUESTED');
      logger.info({ event: 'RECONNECT_REQUESTED' }, 'Reconnect requested');
      
      // Prevent double reconnection
      if (connecting) {
        logger.warn({ event: 'RECONNECT_ALREADY_IN_PROGRESS' }, 'Reconnect already in progress, skipping');
        return;
      }
      
      // If currently connected, logout first
      if (connected && sock) {
        console.log('LOGOUT_START');
        logger.info({ event: 'LOGOUT_START' }, 'Currently connected, logging out first...');
        try {
          await sock.logout();
          console.log('LOGOUT_SUCCESS');
          logger.info({ event: 'LOGOUT_SUCCESS' }, 'Logout successful');
        } catch (e) {
          console.log('LOGOUT_ERROR', e.message);
          logger.warn({ event: 'LOGOUT_ERROR' }, 'Logout error (continuing): %s', e.message);
          // Force close socket
          try {
            sock.end(undefined);
          } catch (_) {}
        }
        sock = null;
        connected = false;
        connectionState = 'disconnected';
        // Brief wait for logout to complete
        await new Promise((r) => setTimeout(r, 500));
      }
      
      // Clear auth state if not connected
      if (!connected) {
        console.log('AUTH_CLEARED');
        clearAuthFolder();
        writeLastQr({ qr: null, status: 'disconnected', expires_at: 0, updated_at: nowTs() });
      }
      
      // Reset state
      qrValue = null;
      qrTimestamp = null;
      phoneNumber = null;
      connectionState = 'disconnected';
      
      // Start connection (non-blocking)
      console.log('RECONNECT_CONNECT_START');
      await connect();
      
      // Note: QR will be available via polling /qr endpoint
      console.log('RECONNECT_IN_PROGRESS');
      logger.info({ event: 'RECONNECT_IN_PROGRESS' }, 'Reconnect initiated, QR will appear shortly');
    } catch (e) {
      console.error('RECONNECT_ERROR', e.message);
      logger.error({ event: 'RECONNECT_ERROR' }, 'reconnect: %s', e.message);
      logger.error(e.stack);
    }
  })();
});

app.post('/reset-session', async (req, res) => {
  try {
    logger.info({ event: 'RESET_SESSION_REQUESTED' }, 'Reset session requested');
    if (sock) {
      try { sock.end(undefined); } catch (_) {}
      sock = null;
    }
    connected = false;
    qrValue = null;
    qrTimestamp = null;
    phoneNumber = null;
    connectionState = 'disconnected';
    clearAuthFolder();
    // Also delete QR state file
    try {
      if (fs.existsSync(QR_FILE)) {
        fs.unlinkSync(QR_FILE);
      }
    } catch (_) {}
    logger.info({ event: 'SESSION_RESET' }, 'Auth folder cleared, exiting process to trigger restart');
    res.json({ ok: true, message: 'Session reset. Process will exit for restart.' });
    setTimeout(() => process.exit(0), 1000);
  } catch (e) {
    logger.error({ event: 'RESET_SESSION_ERROR' }, 'reset-session: %s', e.message);
    res.status(500).json({ ok: false, error: e.message });
  }
});

// Global error handlers (do NOT crash-loop silently)
process.on('unhandledRejection', (err) => {
  console.error('unhandledRejection', err);
  logger.error({ event: 'UNHANDLED_REJECTION' }, err);
});

process.on('uncaughtException', (err) => {
  console.error('uncaughtException', err);
  logger.error({ event: 'UNCAUGHT_EXCEPTION' }, err);
  // Don't exit immediately - let the process manager handle it
});

async function main() {
  // Load persisted QR state on startup
  loadQrState();
  
  // Connect (will use persisted auth state if available)
  await connect();
  
  // Listen on 0.0.0.0 to accept connections from Docker network
  app.listen(PORT, '0.0.0.0', () => {
    console.log('HTTP_SERVER_STARTED', PORT);
    logger.info({ event: 'SERVER_STARTED', port: PORT }, 'WhatsApp bot listening on 0.0.0.0:%d', PORT);
  });
}

main().catch((e) => {
  console.error('STARTUP_ERROR', e);
  logger.error({ event: 'STARTUP_ERROR' }, e);
  process.exit(1);
});
