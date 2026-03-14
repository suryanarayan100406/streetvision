import axios from 'axios';
import Constants from 'expo-constants';

function resolveApiBaseUrl() {
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

const api = axios.create({
  baseURL: resolveApiBaseUrl(),
  timeout: 15000,
});

export default api;
