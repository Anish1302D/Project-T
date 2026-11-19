import * as path from "node:path";

/**
 * Per-tool input bounds aligned with docs/api/mcp-tools-specification.md.
 */
export const MAX_PROMPT_BYTES = 512 * 1024; // 512 KB
export const MAX_LOG_BYTES = 1024 * 1024; // 1 MB
export const MAX_TOKEN_TEXT_BYTES = 1024 * 1024; // 1 MB
export const MAX_CONTEXT_ITEMS = 100;
export const MAX_CONTEXT_TOTAL_BYTES = 1024 * 1024; // 1 MB
export const MAX_SELECTED_FILES = 100;

export class InputLimitError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "InputLimitError";
  }
}

export class WorkspaceScopeError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "WorkspaceScopeError";
  }
}

export function assertUtf8ByteLimit(value: string, maxBytes: number, fieldName: string): void {
  const bytes = Buffer.byteLength(value, "utf-8");
  if (bytes > maxBytes) {
    throw new InputLimitError(
      `Input '${fieldName}' (${bytes} bytes) exceeds maximum allowed limit of ${maxBytes} bytes.`
    );
  }
}

export function assertNoNullBytes(value: string, fieldName: string): void {
  if (value.includes("\0")) {
    throw new WorkspaceScopeError(`Invalid null byte in '${fieldName}'.`);
  }
}

export function validateWorkspaceAndPinnedPaths(
  workspaceRoot: string,
  pinnedFiles: readonly string[],
  approvedWorkspaces?: readonly string[]
): { normalizedRoot: string; normalizedPinned: string[] } {
  assertNoNullBytes(workspaceRoot, "workspace_root");
  const normalizedRoot = path.resolve(workspaceRoot);

  if (approvedWorkspaces !== undefined) {
    if (approvedWorkspaces.length === 0) {
      throw new WorkspaceScopeError("No approved workspaces are configured on MCP server.");
    }
    const isAllowed = approvedWorkspaces.some((approved) => {
      const approvedResolved = path.resolve(approved);
      const rel = path.relative(approvedResolved, normalizedRoot);
      return rel === "" || (!rel.startsWith("..") && !path.isAbsolute(rel));
    });
    if (!isAllowed) {
      throw new WorkspaceScopeError(
        "Requested workspace_root is outside the approved workspace allowlist."
      );
    }
  }

  const normalizedPinned: string[] = [];
  for (const rawPinned of pinnedFiles) {
    assertNoNullBytes(rawPinned, "pinned_files");
    if (path.isAbsolute(rawPinned)) {
      throw new WorkspaceScopeError(
        "pinned_files entries must be relative paths inside workspace_root."
      );
    }
    const resolvedPinned = path.resolve(normalizedRoot, rawPinned);
    const rel = path.relative(normalizedRoot, resolvedPinned);
    if (rel === "" || rel.startsWith("..") || path.isAbsolute(rel)) {
      throw new WorkspaceScopeError(
        `Path traversal rejected in pinned_files: '${rawPinned}' escapes workspace_root.`
      );
    }
    normalizedPinned.push(rel.split(path.sep).join("/"));
  }

  return { normalizedRoot, normalizedPinned };
}
