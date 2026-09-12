import { z } from 'zod';

export function referenceKey(name: string): string {
  return name.toLowerCase()
    .replace(/\b(?:amd|intel|nvidia|geforce|radeon|processor|desktop|graphics|card)\b/g, '')
    .replace(/[^a-z0-9]/g, '');
}

export function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown> : {};
}

export function requireConfirmation(item: {
  category: string; reviewStatus: string; extractedFields: unknown; fieldProvenance: unknown;
}, approvedName?: string) {
  if (item.reviewStatus !== 'pending') throw new Error('Item was already reviewed');
  if (item.category === 'ai_model') return;
  const fields = asRecord(item.extractedFields);
  const proof = asRecord(asRecord(item.fieldProvenance).confirmation_status);
  if (!['released', 'officially_announced'].includes(String(fields.confirmation_status))
    || proof.verified !== true
    || typeof proof.source_url !== 'string' || !proof.source_url.startsWith('https://')
    || typeof proof.snippet !== 'string' || !proof.snippet.trim()) {
    throw new Error('Official confirmation is missing. Run discovery again before approving this item.');
  }
  if (approvedName && referenceKey(approvedName) !== referenceKey(String(fields.name ?? ''))) {
    throw new Error('The approved model must match the officially confirmed product. Discover the other model separately.');
  }
}

export const gameDiscoverySchema = z.object({
  name: z.string().min(1).max(255),
  genre: z.string().optional(),
  store_url: z.string().url(),
  hard_requirements: z.array(z.string()).optional(),
  min_storage_gb: z.number().int().positive().optional(),
  requirements_notes: z.string().optional(),
  requirements: z.array(z.object({
    tier: z.enum(['minimum', 'recommended', 'ultra']),
    role: z.enum(['cpu', 'gpu']),
    published_name: z.string().min(2).max(255),
    snippet: z.string().min(2),
    min_ram_gb: z.number().int().positive().nullable(),
  })).min(1).max(16),
  hardware_dependencies: z.array(z.object({
    name: z.string(),
    category: z.enum(['cpu', 'gpu_chipset']),
    catalog_id: z.string().uuid().nullable(),
    discovered_item_id: z.string().uuid().nullable().optional(),
  })).max(16),
});
