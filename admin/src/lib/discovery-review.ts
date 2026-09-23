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

const buildcoresDirectories: Record<string, string> = {
  cpu: 'CPU', gpu_variant: 'GPU', gpu_chipset: 'GPU', motherboard: 'Motherboard',
  ram_kit: 'RAM', storage_drive: 'Storage', psu: 'PSU', case: 'PCCase',
  cpu_cooler: 'CPUCooler', fan: 'CaseFan',
};

/** Imported catalog evidence is distinct from a manufacturer's announcement.
 * Only the importer-owned, pinned provenance contract qualifies for this path.
 * Generic discovery records must still satisfy the official-confirmation gate.
 */
export function buildcoresSource(item: { category: string; fieldProvenance: unknown }) {
  const provenance = asRecord(item.fieldProvenance);
  const source = asRecord(provenance._buildcores);
  const directory = buildcoresDirectories[item.category];
  if (!directory || source.repository !== 'https://github.com/buildcores/buildcores-open-db'
    || source.converter !== 'buildcores-v1'
    || source.license !== 'https://opendatacommons.org/licenses/by/1-0/'
    || typeof source.revision !== 'string' || !/^[a-f0-9]{40}$/.test(source.revision)) return null;
  const ids = item.category === 'gpu_chipset' ? source.board_ids : [source.opendb_id];
  if (!Array.isArray(ids) || ids.length === 0 || !ids.every((id) =>
    typeof id === 'string' && /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(id))) return null;
  const url = asRecord(provenance.name).source_url;
  const prefix = `${source.repository}/blob/${source.revision}/open-db/${directory}/`;
  if (typeof url !== 'string' || !ids.some((id) => url === `${prefix}${id}.json`)) return null;
  const review = asRecord(source.review);
  const reasons = Array.isArray(review.reasons)
    ? review.reasons.filter((r): r is string => typeof r === 'string') : [];
  return { revision: source.revision, url, license: source.license, reasons };
}

export function requireConfirmation(item: {
  category: string; reviewStatus: string; extractedFields: unknown; fieldProvenance: unknown;
}, approvedName?: string) {
  if (item.reviewStatus !== 'pending') throw new Error('Item was already reviewed');
  if (item.category === 'ai_model') return;
  const fields = asRecord(item.extractedFields);
  if (buildcoresSource(item)) {
    // A chipset candidate's name is synthesized by the importer ("GeForce RTX
    // 4070 12GB GDDR6X"), not a product name, so the reviewer may rename it to
    // the catalog's convention ("RTX 4070").
    if (item.category !== 'gpu_chipset' && approvedName
      && referenceKey(approvedName) !== referenceKey(String(fields.name ?? ''))) {
      throw new Error('The approved model must match the imported BuildCores product.');
    }
    return;
  }
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
