export interface SecretStorageAdapter {
  get(key: string): Thenable<string | undefined> | Promise<string | undefined>;
  store(key: string, value: string): Thenable<void> | Promise<void>;
  delete(key: string): Thenable<void> | Promise<void>;
}

const TOKEN_SECRET_KEY = "projectT.localRuntimeBearerToken";

/**
 * Persists the per-installation Local Runtime bearer token strictly in SecretStorage.
 * Never reads or writes tokens in workspace settings.json.
 */
export class RuntimeTokenStore {
  constructor(private readonly secrets: SecretStorageAdapter) {}

  async getToken(): Promise<string | undefined> {
    const value = await this.secrets.get(TOKEN_SECRET_KEY);
    const trimmed = value?.trim();
    return trimmed ? trimmed : undefined;
  }

  async setToken(token: string): Promise<void> {
    const trimmed = token.trim();
    if (!trimmed) {
      throw new Error("Bearer token cannot be empty.");
    }
    await this.secrets.store(TOKEN_SECRET_KEY, trimmed);
  }

  async clearToken(): Promise<void> {
    await this.secrets.delete(TOKEN_SECRET_KEY);
  }
}
