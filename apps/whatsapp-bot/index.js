/**
 * WhatsApp QR bot — serves /health, /qr, POST /reconnect for API bridge.
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
const AUTH_FOLDER = process.env.AUTH_FOLDER || './auth';

const app = express();
app.use(express.json());
let sock = null;
let qrValue = null;
let lastDisconnectReason = null;
let connected = false;
let connecting = false;

function clearAuthFolder() {
  try {
    if (fs.existsSync(AUTH_FOLDER)) {
      for (const f of fs.readdirSync(AUTH_FOLDER)) {
        fs.unlinkSync(path.join(AUTH_FOLDER, f));
      }
    }
  } catch (e) {
    logger.warn('clearAuthFolder: %s', e.message);
  }
}

async function connect() {
  if (connecting) return;
  connecting = true;
  qrValue = null;
  lastDisconnectReason = null;
  connected = false;
  if (sock) {
    try { sock.end(undefined); } catch (_) {}
    sock = null;
  }
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_FOLDER);
  sock = makeWASocket({
    auth: state,
    printQRInTerminal: false,
    logger: pino({ level: 'silent' }),
  });

  sock.ev.on('connection.update', (up) => {
    if (up.qr) {
      qrValue = up.qr;
      qrcode.generate(up.qr, { small: true });
    } else {
      qrValue = null;
    }
    if (up.connection === 'close') {
      lastDisconnectReason = up.lastDisconnectReason;
      connected = false;
    } else if (up.connection === 'open') {
      connected = true;
    }
    connecting = false;
  });

  sock.ev.on('creds.update', saveCreds);
  connecting = false;
}

app.get('/health', (req, res) => {
  res.json({
    connected: !!sock && connected,
    status: connected ? 'open' : (lastDisconnectReason || 'disconnected'),
    lastDisconnectReason: lastDisconnectReason || null,
    server_time: new Date().toISOString(),
  });
});

app.get('/qr', (req, res) => {
  const now = new Date();
  const expiresIn = qrValue ? 60 : 0; // QR expires in ~60s
  res.json({
    qr: qrValue || null,
    expires_in: expiresIn,
    server_time: now.toISOString(),
  });
});

app.post('/reconnect', async (req, res) => {
  try {
    if (sock) {
      try { sock.end(undefined); } catch (_) {}
      sock = null;
    }
    clearAuthFolder();
    connected = false;
    qrValue = null;
    await connect();
    res.json({ ok: true, message: 'Reconnecting; new QR will appear shortly.' });
  } catch (e) {
    logger.error('reconnect: %s', e.message);
    res.status(500).json({ ok: false, error: e.message });
  }
});

async function main() {
  await connect();
  app.listen(PORT, () => logger.info(`WhatsApp bot listening on :${PORT}`));
}
main().catch((e) => {
  logger.error(e);
  process.exit(1);
});
