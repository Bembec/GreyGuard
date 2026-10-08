import { useQuery } from "@tanstack/react-query"

import { fetchSetupStatus } from "../api/client"

/**
 * Whether this deployment has zero administrator accounts yet (a fresh install that
 * needs the one-time setup wizard). Public, pre-authentication endpoint - safe to call
 * before any session exists.
 */
export function useSetupStatus() {
  return useQuery({
    queryKey: ["setup-status"],
    queryFn: fetchSetupStatus,
    staleTime: Infinity,
    retry: false,
  })
}
