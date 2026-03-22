export function getTelegramWebApp() {
  return window.Telegram?.WebApp || null;
}

export function isTelegramMiniAppContext() {
  return Boolean(getTelegramWebApp()?.initData);
}

export function getInitData({ persist = true } = {}) {
  const tg = getTelegramWebApp();
  const fromTelegram = tg?.initData?.trim();

  if (fromTelegram) {
    if (persist) {
      localStorage.setItem('pending_tma_init_data', fromTelegram);
    }
    return fromTelegram;
  }

  const fromStorage = localStorage.getItem('pending_tma_init_data')?.trim();
  return fromStorage || null;
}

export function buildAuthHeaders(extraHeaders = {}, { requireInitData = false } = {}) {
  const initData = getInitData();
  if (requireInitData && !initData) {
    throw new Error('Telegram initData не найден');
  }

  return {
    ...extraHeaders,
    ...(initData ? { Authorization: `tma ${initData}` } : {}),
    'ngrok-skip-browser-warning': 'true',
  };
}

function normalizeBotUsername(value) {
  if (!value) return null;
  let normalized = String(value).trim();
  if (!normalized) return null;
  if (normalized.startsWith('@')) {
    normalized = normalized.slice(1);
  }
  return normalized || null;
}

function normalizeMiniAppShortName(value) {
  if (!value) return null;
  let normalized = String(value).trim();
  if (!normalized) return null;
  normalized = normalized.replace(/^\/+|\/+$/g, '');
  return normalized || null;
}

export function getTelegramBotUsername() {
  if (typeof window === 'undefined') return null;

  const query = new URLSearchParams(window.location.search);
  const fromQuery = normalizeBotUsername(query.get('bot'));
  if (fromQuery) {
    localStorage.setItem('telegram_bot_username', fromQuery);
    return fromQuery;
  }

  const fromEnv = normalizeBotUsername(import.meta.env.VITE_TELEGRAM_BOT_USERNAME);
  if (fromEnv) {
    localStorage.setItem('telegram_bot_username', fromEnv);
    return fromEnv;
  }

  return normalizeBotUsername(localStorage.getItem('telegram_bot_username'));
}

export function getTelegramMiniAppShortName() {
  if (typeof window === 'undefined') return null;

  const query = new URLSearchParams(window.location.search);
  const fromQuery = normalizeMiniAppShortName(query.get('app') || query.get('appname'));
  if (fromQuery) {
    localStorage.setItem('telegram_mini_app_short_name', fromQuery);
    return fromQuery;
  }

  const fromEnv = normalizeMiniAppShortName(import.meta.env.VITE_TELEGRAM_MINI_APP_SHORT_NAME);
  if (fromEnv) {
    localStorage.setItem('telegram_mini_app_short_name', fromEnv);
    return fromEnv;
  }

  return normalizeMiniAppShortName(localStorage.getItem('telegram_mini_app_short_name'));
}

export function getTelegramBotLink(startApp = 'home') {
  const botUsername = getTelegramBotUsername();
  if (!botUsername) return null;
  const shortName = getTelegramMiniAppShortName();
  if (shortName) {
    return `https://t.me/${botUsername}/${shortName}?startapp=${encodeURIComponent(startApp)}`;
  }
  return `https://t.me/${botUsername}?startapp=${encodeURIComponent(startApp)}`;
}

export function getTelegramNativeLink(startApp = 'home') {
  const botUsername = getTelegramBotUsername();
  if (!botUsername) return null;
  const shortName = getTelegramMiniAppShortName();
  const params = new URLSearchParams({ domain: botUsername, startapp: startApp });
  if (shortName) {
    params.set('appname', shortName);
  }
  return `tg://resolve?${params.toString()}`;
}

export function getStartAppParam() {
  const tg = getTelegramWebApp();
  const fromTelegram = tg?.initDataUnsafe?.start_param?.trim();
  if (fromTelegram) return fromTelegram;

  if (typeof window !== 'undefined') {
    const query = new URLSearchParams(window.location.search);
    const fromQuery = query.get('tgWebAppStartParam')?.trim() || query.get('startapp')?.trim();
    if (fromQuery) return fromQuery;
  }

  return null;
}

export function redirectToTelegramBot(startApp = 'home') {
  const fallbackUrl = getTelegramBotLink(startApp);
  if (!fallbackUrl) return false;

  const nativeUrl = getTelegramNativeLink(startApp);
  if (!nativeUrl) {
    window.location.href = fallbackUrl;
    return true;
  }

  const fallbackTimer = setTimeout(() => {
    window.location.href = fallbackUrl;
  }, 1200);

  const cancelFallback = () => {
    clearTimeout(fallbackTimer);
    document.removeEventListener('visibilitychange', onVisibilityChange);
    window.removeEventListener('pagehide', cancelFallback);
  };

  const onVisibilityChange = () => {
    if (document.hidden) {
      cancelFallback();
    }
  };

  document.addEventListener('visibilitychange', onVisibilityChange);
  window.addEventListener('pagehide', cancelFallback);

  window.location.href = nativeUrl;
  return true;
}
