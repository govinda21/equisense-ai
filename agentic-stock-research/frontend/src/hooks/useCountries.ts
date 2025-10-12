import { useState, useEffect, useRef } from 'react';

export function useCountries() {
  const [countries, setCountries] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const fetchedRef = useRef(false);

  useEffect(() => {
    // Prevent double execution in React StrictMode
    if (fetchedRef.current) {
      return;
    }

    let isMounted = true;
    fetchedRef.current = true;

    const fetchCountries = async () => {
      try {
        setLoading(true);
        const base = (import.meta as any).env.VITE_API_BASE_URL || 'http://localhost:8000';
        const response = await fetch(`${base}/countries`);

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();

        if (isMounted) {
          setCountries(data.countries || []);
          setError(null);
        }
      } catch (err) {
        console.error('Failed to fetch countries:', err);
        
        if (isMounted) {
          // Fallback to default countries
          setCountries(['India', 'United States', 'United Kingdom', 'Canada']);
          setError(err instanceof Error ? err.message : 'Failed to fetch countries');
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    fetchCountries();

    return () => {
      isMounted = false;
    };
  }, []);

  return { countries, loading, error };
}
