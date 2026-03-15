import { useState, useEffect } from 'react';

export default function useFetch(url) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const controller = new AbortController();

    setLoading(true);
    setError(null);

    fetch(url, { signal: controller.signal })
      .then(async (r) => {
        if (!r.ok) {
          let message = '';
          try {
            message = await r.text();
          } catch {
            message = '';
          }
          throw new Error(message || `Request failed: ${r.status}`);
        }
        return r.json();
      })
      .then(d => {
        setData(d);
        setLoading(false);
      })
      .catch(e => {
        if (e.name === 'AbortError') return;
        setError(e);
        setLoading(false);
      });

    return () => controller.abort();
  }, [url]);

  return { data, loading, error };
}
