import { createContext, useContext, type ReactNode } from 'react';
import { ApiClient } from './apiClient';

const ApiContext = createContext<ApiClient | null>(null);

interface ApiProviderProps {
  client: ApiClient;
  children: ReactNode;
}

/** Provides the single centralized ApiClient to the component tree. */
export function ApiProvider({ client, children }: ApiProviderProps) {
  return <ApiContext.Provider value={client}>{children}</ApiContext.Provider>;
}

export function useApiClient(): ApiClient {
  const client = useContext(ApiContext);
  if (!client) {
    throw new Error('useApiClient must be used within an ApiProvider.');
  }
  return client;
}