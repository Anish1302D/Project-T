import {
  CONTENT_TYPES,
  INTEGRATION_SOURCES,
  OPTIMIZATION_MODES
} from "@project-t/contracts";
import { z } from "zod";
import { MAX_CONTEXT_ITEMS, MAX_SELECTED_FILES } from "./limits.js";

const OptimizationModeSchema = z.enum(OPTIMIZATION_MODES);
const ContentTypeSchema = z.enum(CONTENT_TYPES);
const IntegrationSourceSchema = z.enum(INTEGRATION_SOURCES);

export const OptimizePromptInputSchema = z
  .object({
    content: z.string().min(1, "content must be non-empty"),
    content_type: ContentTypeSchema.optional(),
    mode: OptimizationModeSchema.default("balanced"),
    provider: z.string().min(1).default("local"),
    model: z.string().min(1).default("generic"),
    preserve_identifiers: z.boolean().default(true)
  })
  .strict();

export const AnalyzeContextInputSchema = z
  .object({
    content: z.string().min(1, "content must be non-empty"),
    content_type: ContentTypeSchema.optional(),
    provider: z.string().min(1).default("local"),
    model: z.string().min(1).default("generic")
  })
  .strict();

export const CompressTerminalOutputInputSchema = z
  .object({
    output: z.string().min(1, "output must be non-empty"),
    command: z.string().optional(),
    exit_code: z.number().int().optional(),
    context_lines: z.number().int().min(0).max(50).default(5),
    provider: z.string().min(1).default("local"),
    model: z.string().min(1).default("generic")
  })
  .strict();

export const SelectRelevantFilesInputSchema = z
  .object({
    task_description: z.string().min(1, "task_description must be non-empty"),
    workspace_root: z.string().min(1, "workspace_root is required"),
    pinned_files: z.array(z.string().min(1)).max(MAX_SELECTED_FILES).default([]),
    max_files: z.number().int().min(1).max(MAX_SELECTED_FILES).default(15),
    max_tokens: z.number().int().min(100).max(1_000_000).default(8000),
    provider: z.string().min(1).default("local"),
    model: z.string().min(1).default("generic")
  })
  .strict();

export const DeduplicateContextItemSchema = z
  .object({
    id: z.string().min(1),
    content: z.string(),
    content_type: ContentTypeSchema.optional(),
    pinned: z.boolean().default(false)
  })
  .strict();

export const DeduplicateContextInputSchema = z
  .object({
    items: z
      .array(DeduplicateContextItemSchema)
      .min(1, "items must contain at least 1 entry")
      .max(MAX_CONTEXT_ITEMS, `Maximum ${MAX_CONTEXT_ITEMS} items permitted`),
    project_id: z.string().min(1).optional(),
    mode: OptimizationModeSchema.default("safe"),
    provider: z.string().min(1).default("local"),
    model: z.string().min(1).default("generic")
  })
  .strict();

export const EstimateTokensInputSchema = z
  .object({
    text: z.string(),
    provider: z.string().min(1).default("local"),
    model: z.string().min(1).default("generic"),
    allow_remote_count: z.boolean().default(false)
  })
  .strict();

export const GetOptimizationReportInputSchema = z
  .object({
    integration: IntegrationSourceSchema.optional(),
    window_days: z.number().int().min(1).max(365).default(30)
  })
  .strict();
