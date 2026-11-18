import * as path from "node:path";

export interface MementoAdapter {
  get<T>(key: string, defaultValue: T): T;
  update(key: string, value: unknown): Thenable<void> | Promise<void>;
}

const APPROVED_WORKSPACES_KEY = "projectT.approvedWorkspaces";

function normalizeRoot(dirPath: string): string {
  return path.resolve(dirPath);
}

/**
 * Maintains explicit user-approved workspace folder paths before querying /context/select.
 */
export class WorkspaceAllowlistStore {
  constructor(private readonly memento: MementoAdapter) {}

  listApproved(): string[] {
    const raw = this.memento.get<string[]>(APPROVED_WORKSPACES_KEY, []);
    return Array.from(new Set(raw.map(normalizeRoot)));
  }

  isApproved(workspaceRoot: string): boolean {
    const candidate = normalizeRoot(workspaceRoot);
    return this.listApproved().some((approved) => {
      const rel = path.relative(approved, candidate);
      return rel === "" || (!rel.startsWith("..") && !path.isAbsolute(rel));
    });
  }

  async approve(workspaceRoot: string): Promise<string[]> {
    const normalized = normalizeRoot(workspaceRoot);
    const next = Array.from(new Set([...this.listApproved(), normalized]));
    await this.memento.update(APPROVED_WORKSPACES_KEY, next);
    return next;
  }

  async revoke(workspaceRoot: string): Promise<string[]> {
    const normalized = normalizeRoot(workspaceRoot);
    const next = this.listApproved().filter((p) => p !== normalized);
    await this.memento.update(APPROVED_WORKSPACES_KEY, next);
    return next;
  }
}
