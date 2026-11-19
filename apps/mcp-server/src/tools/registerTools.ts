import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import type { CallToolResult } from "@modelcontextprotocol/sdk/types.js";
import { redactSecrets } from "@project-t/shared-utils";
import type { McpRuntimeClient } from "../runtimeClient.js";
import {
  MAX_CONTEXT_TOTAL_BYTES,
  MAX_LOG_BYTES,
  MAX_PROMPT_BYTES,
  MAX_TOKEN_TEXT_BYTES,
  assertUtf8ByteLimit,
  validateWorkspaceAndPinnedPaths
} from "./limits.js";
import {
  AnalyzeContextInputSchema,
  CompressTerminalOutputInputSchema,
  DeduplicateContextInputSchema,
  EstimateTokensInputSchema,
  GetOptimizationReportInputSchema,
  OptimizePromptInputSchema,
  SelectRelevantFilesInputSchema
} from "./schemas.js";

export interface RegisterToolsOptions {
  /**
   * Optional MCP-level workspace root allowlist enforced in addition to
   * Local Runtime's server-side allowlist.
   */
  approvedWorkspaces?: readonly string[];
}

function okResult(payload: Record<string, unknown>, summaryText: string): CallToolResult {
  return {
    content: [
      {
        type: "text",
        text: `${summaryText}\n\n${JSON.stringify(payload, null, 2)}`
      }
    ],
    structuredContent: payload
  };
}

function errorResult(toolName: string, err: unknown): CallToolResult {
  const rawMessage = err instanceof Error ? err.message : String(err);
  return {
    isError: true,
    content: [
      {
        type: "text",
        text: redactSecrets(`Tool '${toolName}' failed: ${rawMessage}`)
      }
    ]
  };
}

export function registerProjectTTools(
  server: McpServer,
  client: McpRuntimeClient,
  options: RegisterToolsOptions = {}
): void {
  // 1. optimize_prompt
  server.registerTool(
    "optimize_prompt",
    {
      title: "Optimize Prompt",
      description:
        "[local-only by default; cloud only if AI semantic compression is explicitly enabled in Local Runtime] " +
        "Optimize prompt or context text with deterministic rules, protected-span locking, quality validation, and recoverable original content. Max input: 512 KB.",
      inputSchema: OptimizePromptInputSchema,
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false
      }
    },
    async (args) => {
      try {
        assertUtf8ByteLimit(args.content, MAX_PROMPT_BYTES, "content");
        const { wire } = await client.optimize({
          content: args.content,
          content_type: args.content_type,
          mode: args.mode,
          provider: args.provider,
          model: args.model,
          integration: "mcp",
          optimization: {
            deduplicate: true,
            semantic_compression: false,
            context_filtering: true,
            preserve_identifiers: args.preserve_identifiers
          }
        });
        return okResult(
          wire as unknown as Record<string, unknown>,
          `Optimized prompt (${wire.tokens.original} -> ${wire.tokens.optimized} tokens, saved ${wire.tokens.saved} [${wire.tokens.reduction_percentage}%], accuracy=${wire.tokens.accuracy}).`
        );
      } catch (err) {
        return errorResult("optimize_prompt", err);
      }
    }
  );

  // 2. analyze_context
  server.registerTool(
    "analyze_context",
    {
      title: "Analyze Context",
      description:
        "[local-only] Classify content type, extract explicit constraints, list locked protected spans, and count/estimate tokens without modifying text. Max input: 512 KB.",
      inputSchema: AnalyzeContextInputSchema,
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false
      }
    },
    async (args) => {
      try {
        assertUtf8ByteLimit(args.content, MAX_PROMPT_BYTES, "content");
        const analysis = await client.analyze({
          content: args.content,
          content_type: args.content_type,
          provider: args.provider,
          model: args.model
        });
        return okResult(
          analysis as unknown as Record<string, unknown>,
          `Classified as '${analysis.classification.mapped_content_type}' (${analysis.token_estimate.count} tokens [${analysis.token_estimate.accuracy}], ${analysis.protected_spans.length} protected spans).`
        );
      } catch (err) {
        return errorResult("analyze_context", err);
      }
    }
  );

  // 3. compress_terminal_output
  server.registerTool(
    "compress_terminal_output",
    {
      title: "Compress Terminal Output",
      description:
        "[local-only; never executes shell commands] Compress passed terminal or test-runner output while preserving command, exit code, errors, stack trace frames, file/line references, failure warnings, and test summaries. Max input: 1 MB.",
      inputSchema: CompressTerminalOutputInputSchema,
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false
      }
    },
    async (args) => {
      try {
        assertUtf8ByteLimit(args.output, MAX_LOG_BYTES, "output");
        const { wire } = await client.compressLogs({
          output: args.output,
          command: args.command,
          exit_code: args.exit_code,
          context_lines: args.context_lines,
          provider: args.provider,
          model: args.model
        });
        return okResult(
          wire as unknown as Record<string, unknown>,
          `Terminal log compressed (${wire.tokens.original} -> ${wire.tokens.optimized} tokens, saved ${wire.tokens.saved}, accuracy=${wire.tokens.accuracy}).`
        );
      } catch (err) {
        return errorResult("compress_terminal_output", err);
      }
    }
  );

  // 4. select_relevant_files
  server.registerTool(
    "select_relevant_files",
    {
      title: "Select Relevant Files",
      description:
        "[local-only; workspace-scoped] Rank task-relevant files inside an explicitly approved workspace_root using BM25/SQLite FTS5 lexical and structural signals. Max files returned: 100.",
      inputSchema: SelectRelevantFilesInputSchema,
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false
      }
    },
    async (args) => {
      try {
        assertUtf8ByteLimit(args.task_description, 32 * 1024, "task_description");
        const { normalizedRoot, normalizedPinned } = validateWorkspaceAndPinnedPaths(
          args.workspace_root,
          args.pinned_files,
          options.approvedWorkspaces
        );
        const selected = await client.selectContext({
          task_description: args.task_description,
          workspace_root: normalizedRoot,
          pinned_files: normalizedPinned,
          max_files: args.max_files,
          max_tokens: args.max_tokens,
          provider: args.provider,
          model: args.model
        });
        return okResult(
          selected as unknown as Record<string, unknown>,
          `Selected ${selected.selected_files.length} relevant files (${selected.total_tokens} tokens, accuracy=${selected.accuracy}).`
        );
      } catch (err) {
        return errorResult("select_relevant_files", err);
      }
    }
  );

  // 5. deduplicate_context
  server.registerTool(
    "deduplicate_context",
    {
      title: "Deduplicate Context",
      description:
        "[local-only] Deduplicate and compress repeated context snippets while preserving pinned items and project scope. Max: 100 items / 1 MB total.",
      inputSchema: DeduplicateContextInputSchema,
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false
      }
    },
    async (args) => {
      try {
        const totalBytes = args.items.reduce(
          (sum, item) => sum + Buffer.byteLength(item.content, "utf-8"),
          0
        );
        if (totalBytes > MAX_CONTEXT_TOTAL_BYTES) {
          throw new Error(
            `Combined context items size (${totalBytes} bytes) exceeds ${MAX_CONTEXT_TOTAL_BYTES} byte limit.`
          );
        }
        const { wire } = await client.compressContext({
          items: args.items,
          project_id: args.project_id,
          mode: args.mode,
          provider: args.provider,
          model: args.model
        });
        return okResult(
          wire as unknown as Record<string, unknown>,
          `Context deduplicated (${wire.tokens.original} -> ${wire.tokens.optimized} tokens, saved ${wire.tokens.saved}, accuracy=${wire.tokens.accuracy}).`
        );
      } catch (err) {
        return errorResult("deduplicate_context", err);
      }
    }
  );

  // 6. estimate_tokens
  server.registerTool(
    "estimate_tokens",
    {
      title: "Estimate Tokens",
      description:
        "[local-only by default; optional remote provider count only if allow_remote_count=true] Count or estimate tokens for text with explicit 'exact' vs 'estimated' accuracy label. Max input: 1 MB.",
      inputSchema: EstimateTokensInputSchema,
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false
      }
    },
    async (args) => {
      try {
        assertUtf8ByteLimit(args.text, MAX_TOKEN_TEXT_BYTES, "text");
        const countResult = await client.countTokens({
          text: args.text,
          provider: args.provider,
          model: args.model,
          allow_remote_count: args.allow_remote_count
        });
        return okResult(
          countResult as unknown as Record<string, unknown>,
          `Token count: ${countResult.count} (accuracy=${countResult.accuracy}, ${countResult.provider}:${countResult.model}).`
        );
      } catch (err) {
        return errorResult("estimate_tokens", err);
      }
    }
  );

  // 7. get_optimization_report
  server.registerTool(
    "get_optimization_report",
    {
      title: "Get Optimization Report",
      description:
        "[local-only; metadata-only] Retrieve aggregated token savings, fallback rates, and accuracy breakdown from Local Runtime SQLite without exposing raw prompts or source code.",
      inputSchema: GetOptimizationReportInputSchema,
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false
      }
    },
    async (args) => {
      try {
        const report = await client.metrics(args.integration, args.window_days);
        return okResult(
          report as unknown as Record<string, unknown>,
          `Metrics (${args.window_days}d): ${report.total_runs} runs, ${report.total_tokens_saved} tokens saved, ${report.fallback_count} fallbacks.`
        );
      } catch (err) {
        return errorResult("get_optimization_report", err);
      }
    }
  );
}
