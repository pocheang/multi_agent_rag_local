import { useState, useCallback } from "react";

export interface AsyncActionOptions<T> {
  onSuccess?: (result: T) => void;
  onError?: (error: unknown) => void | Promise<void>;
  onFinally?: () => void;
}

export function useAsyncAction<T = void>() {
  const [loading, setLoading] = useState(false);

  const execute = useCallback(
    async (
      action: () => Promise<T>,
      options?: AsyncActionOptions<T>
    ): Promise<T | undefined> => {
      setLoading(true);
      try {
        const result = await action();
        options?.onSuccess?.(result);
        return result;
      } catch (error) {
        await options?.onError?.(error);
        throw error;
      } finally {
        setLoading(false);
        options?.onFinally?.();
      }
    },
    []
  );

  return { loading, execute };
}
