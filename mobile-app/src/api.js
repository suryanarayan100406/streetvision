import axios from 'axios';
import Constants from 'expo-constants';

function trimSlash(value) {
  return String(value || '').replace(/\/$/, '');
}

function uniq(items) {
  return [...new Set(items.filter(Boolean))];
}

function resolveApiBaseUrl() {
  const fullBaseUrl =
    process.env.EXPO_PUBLIC_API_BASE_URL
    || Constants.expoConfig?.extra?.apiBaseUrl
    || Constants.manifest2?.extra?.apiBaseUrl;
  if (fullBaseUrl) {
    return String(fullBaseUrl).replace(/\/$/, '');
  }

  const configuredHost =
    process.env.EXPO_PUBLIC_API_HOST
    || Constants.expoConfig?.extra?.apiHost
    || Constants.manifest2?.extra?.apiHost;
  const configuredPort =
    process.env.EXPO_PUBLIC_API_PORT
    || Constants.expoConfig?.extra?.apiPort
    || Constants.manifest2?.extra?.apiPort
    || '8000';

  const hostUri =
    Constants.expoConfig?.hostUri
    || Constants.manifest2?.extra?.expoClient?.hostUri
    || Constants.manifest?.debuggerHost
    || null;

  const inferredHost = hostUri ? hostUri.split(':')[0] : null;
  const apiHost = configuredHost || inferredHost || 'localhost';

  return `http://${apiHost}:${configuredPort}/api`;
}

function buildApiCandidates() {
  const configuredBase =
    process.env.EXPO_PUBLIC_API_BASE_URL
    || Constants.expoConfig?.extra?.apiBaseUrl
    || Constants.manifest2?.extra?.apiBaseUrl
    || null;

  const configuredHost =
    process.env.EXPO_PUBLIC_API_HOST
    || Constants.expoConfig?.extra?.apiHost
    || Constants.manifest2?.extra?.apiHost
    || null;
  const configuredPort =
    process.env.EXPO_PUBLIC_API_PORT
    || Constants.expoConfig?.extra?.apiPort
    || Constants.manifest2?.extra?.apiPort
    || '8000';

  const hostUri =
    Constants.expoConfig?.hostUri
    || Constants.manifest2?.extra?.expoClient?.hostUri
    || Constants.manifest?.debuggerHost
    || null;

  const inferredHost = hostUri ? hostUri.split(':')[0] : null;

  const candidates = [
    configuredBase ? trimSlash(configuredBase) : null,
    configuredHost ? `http://${configuredHost}:${configuredPort}/api` : null,
    inferredHost ? `http://${inferredHost}:${configuredPort}/api` : null,
    'http://10.0.2.2:8000/api',
    'http://127.0.0.1:8000/api',
    'http://localhost:8000/api',
    resolveApiBaseUrl(),
  ];

  return uniq(candidates.map(trimSlash));
}

async function probeHealth(baseUrl, timeoutMs = 2500) {
  const root = baseUrl.replace(/\/api$/, '');
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${root}/health`, { signal: controller.signal });
    return res.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

let activeBaseUrl = trimSlash(resolveApiBaseUrl());
let resolvingBaseUrlPromise = null;

async function ensureReachableBaseUrl() {
  if (resolvingBaseUrlPromise) {
    return resolvingBaseUrlPromise;
  }

  resolvingBaseUrlPromise = (async () => {
    const candidates = buildApiCandidates();
    for (const baseUrl of candidates) {
      const ok = await probeHealth(baseUrl);
      if (ok) {
        activeBaseUrl = baseUrl;
        return activeBaseUrl;
      }
    }
    activeBaseUrl = candidates[0] || activeBaseUrl;
    return activeBaseUrl;
  })();

  try {
    const resolved = await resolvingBaseUrlPromise;
    return resolved;
  } finally {
    resolvingBaseUrlPromise = null;
  }
}

const api = axios.create({
  baseURL: activeBaseUrl,
  timeout: 9000,
});

api.interceptors.request.use(async (config) => {
  const reachableBase = await ensureReachableBaseUrl();
  config.baseURL = reachableBase;
  return config;
});

export function getApiBaseUrl() {
  return activeBaseUrl;
}

export default api;
