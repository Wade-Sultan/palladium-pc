import type { Prisma } from '@prisma/client';

export const DISCOVERY_PAGE_SIZE = 50;
const categories = new Set(['game', 'cpu', 'gpu_chipset', 'gpu_variant', 'motherboard', 'cpu_cooler', 'ram_kit', 'storage_drive', 'psu', 'case', 'fan', 'ai_model']);
export type DiscoveryFilters = { q: string; source: string; category: string; validation: string; page: number };
export type SearchParams = Record<string, string | string[] | undefined>;

export function discoveryFilters(params: SearchParams): DiscoveryFilters {
  const value = (key: string) => typeof params[key] === 'string' ? params[key] as string : '';
  const page = Number(value('page'));
  return {
    q: value('q').trim().slice(0, 200),
    source: ['buildcores', 'discovery'].includes(value('source')) ? value('source') : '',
    category: categories.has(value('category')) ? value('category') : '',
    validation: ['passed', 'failed'].includes(value('validation')) ? value('validation') : '',
    page: Number.isSafeInteger(page) && page > 0 ? Math.min(page, 100000) : 1,
  };
}

export function discoveryWhere(filters: DiscoveryFilters): Prisma.DiscoveredItemWhereInput {
  const where: Prisma.DiscoveredItemWhereInput = { reviewStatus: 'pending' };
  if (filters.category) where.category = filters.category;
  if (filters.validation) where.validationStatus = filters.validation;
  if (filters.source) {
    const imported = { pipelineVersion: { startsWith: 'buildcores-v1:' } };
    where.run = filters.source === 'buildcores' ? { is: imported } : { isNot: imported };
  }
  if (filters.q) where.OR = [
    { nameNormalized: { contains: filters.q.toLowerCase().replace(/^socket\s*/, '').replace(/[\s-]+/g, ''), mode: 'insensitive' } },
    { modelNumber: { contains: filters.q, mode: 'insensitive' } },
  ];
  return where;
}
