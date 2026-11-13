import { useCallback, useEffect, useState } from "react";

// Loads data now and every `intervalMs`. Returns {data, error, reload}.
export default function usePolling(loader, deps, intervalMs = 5000) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const reload = useCallback(() => loader().then((d) => { setData(d); setError(null); }, setError), deps);

  useEffect(() => {
    reload();
    const id = setInterval(reload, intervalMs);
    return () => clearInterval(id);
  }, [reload, intervalMs]);

  return { data, error, reload, setData };
}
