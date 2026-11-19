import { useCallback, useEffect, useState } from "react";
import type { AnalyticsFilters, AnalyticsOverview } from "@project-t/shared-ui";
import {
  OFFLINE_DEMO_OVERVIEW,
  fetchAnalyticsOverview,
  loginCloudAccount
} from "../services/cloudApi";

const INITIAL_FILTERS: AnalyticsFilters = {
  granularity: "daily",
  start_date: "",
  end_date: "",
  provider: "",
  integration: "",
  mode: "",
  accuracy: "",
  device_id: ""
};

function readInitialConfig(): { apiUrl: string; token: string } {
  if (typeof window === "undefined") {
    return { apiUrl: "", token: "" };
  }
  const params = new URLSearchParams(window.location.search);
  const apiFromQuery = params.get("api");
  const tokenFromQuery = params.get("token");
  if (apiFromQuery !== null) {
    window.localStorage.setItem("project_t_cloud_api", apiFromQuery);
  }
  if (tokenFromQuery !== null) {
    window.localStorage.setItem("project_t_cloud_token", tokenFromQuery);
  }
  return {
    apiUrl: apiFromQuery ?? window.localStorage.getItem("project_t_cloud_api") ?? "",
    token: tokenFromQuery ?? window.localStorage.getItem("project_t_cloud_token") ?? ""
  };
}

export function useAnalytics(initialOverview?: AnalyticsOverview) {
  const initial = readInitialConfig();
  const [apiBaseUrl, setApiBaseUrl] = useState<string>(initial.apiUrl);
  const [authToken, setAuthToken] = useState<string>(initial.token);
  const [filters, setFilters] = useState<AnalyticsFilters>(INITIAL_FILTERS);
  const [overview, setOverview] = useState<AnalyticsOverview>(
    initialOverview ?? OFFLINE_DEMO_OVERVIEW
  );
  const [dataSource, setDataSource] = useState<"live" | "offline-demo">(
    initial.token ? "live" : "offline-demo"
  );
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const loadOverview = useCallback(
    async (nextBaseUrl: string, nextToken: string, nextFilters: AnalyticsFilters) => {
      if (!nextToken.trim()) {
        setDataSource("offline-demo");
        setOverview(initialOverview ?? OFFLINE_DEMO_OVERVIEW);
        setError(null);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const data = await fetchAnalyticsOverview(nextBaseUrl, nextToken, nextFilters);
        setOverview(data);
        setDataSource("live");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load cloud analytics.");
      } finally {
        setLoading(false);
      }
    },
    [initialOverview]
  );

  useEffect(() => {
    if (authToken.trim()) {
      void loadOverview(apiBaseUrl, authToken, filters);
    }
  }, [apiBaseUrl, authToken, filters, loadOverview]);

  const signIn = useCallback(
    async (baseUrl: string, email: string, password: string) => {
      setLoading(true);
      setError(null);
      try {
        const session = await loginCloudAccount(baseUrl, email, password);
        if (typeof window !== "undefined") {
          window.localStorage.setItem("project_t_cloud_api", baseUrl);
          window.localStorage.setItem("project_t_cloud_token", session.access_token);
        }
        setApiBaseUrl(baseUrl);
        setAuthToken(session.access_token);
        const data = await fetchAnalyticsOverview(baseUrl, session.access_token, filters);
        setOverview(data);
        setDataSource("live");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Sign-in failed.");
      } finally {
        setLoading(false);
      }
    },
    [filters]
  );

  const disconnect = useCallback(() => {
    if (typeof window !== "undefined") {
      window.localStorage.removeItem("project_t_cloud_token");
    }
    setAuthToken("");
    setDataSource("offline-demo");
    setOverview(initialOverview ?? OFFLINE_DEMO_OVERVIEW);
    setError(null);
  }, [initialOverview]);

  const resetFilters = useCallback(() => {
    setFilters(INITIAL_FILTERS);
  }, []);

  return {
    apiBaseUrl,
    setApiBaseUrl,
    authToken,
    filters,
    setFilters,
    resetFilters,
    overview,
    dataSource,
    loading,
    error,
    signIn,
    disconnect,
    refresh: () => void loadOverview(apiBaseUrl, authToken, filters)
  };
}
