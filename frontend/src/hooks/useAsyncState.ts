import { useState, useCallback } from "react";

export interface AsyncState<T> {
  data: T;
  loading: boolean;
  error: string;
}

export interface UseAsyncStateReturn<T> {
  data: T;
  loading: boolean;
  error: string;
  setData: (data: T | ((prev: T) => T)) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string) => void;
  reset: () => void;
}

export function useAsyncState<T>(initialData: T): UseAsyncStateReturn<T> {
  const [data, setData] = useState<T>(initialData);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const reset = useCallback(() => {
    setData(initialData);
    setLoading(false);
    setError("");
  }, [initialData]);

  return {
    data,
    loading,
    error,
    setData,
    setLoading,
    setError,
    reset,
  };
}
