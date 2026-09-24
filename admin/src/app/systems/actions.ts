'use server';

import { revalidatePath } from 'next/cache';
import { db } from '@/lib/prisma';
import { usdToCents } from '@/lib/utils';

export interface SystemFormData {
  name: string;
  manufacturer: string;
  modelNumber: string;
  yearReleased: number | null;
  isActive: boolean;
  msrpUsd: number | null;
  systemFamilyId: string;
  chip: string;
  cpuCores: number | null;
  gpuCores: number | null;
  unifiedMemoryGb: number | null;
  gpuAddressableMemoryGb: number | null;
  memoryBandwidthGbps: number | null;
  storageGb: number | null;
  tdpWatts: number | null;
}

// Street price is the pricing ETL's to write (part_type "system" is in its
// batch); only the list price is entered here. A system with neither is kept
// in the catalog but never offered, because the offer cannot be priced.
function partData(d: SystemFormData) {
  return {
    name: d.name,
    manufacturer: d.manufacturer || null,
    modelNumber: d.modelNumber || null,
    yearReleased: d.yearReleased,
    isActive: d.isActive,
    msrpCents: usdToCents(d.msrpUsd),
  };
}

function specData(d: SystemFormData) {
  return {
    systemFamilyId: d.systemFamilyId,
    chip: d.chip,
    cpuCores: d.cpuCores,
    gpuCores: d.gpuCores,
    unifiedMemoryGb: d.unifiedMemoryGb ?? 0,
    gpuAddressableMemoryGb: d.gpuAddressableMemoryGb ?? 0,
    memoryBandwidthGbps: d.memoryBandwidthGbps ?? 0,
    storageGb: d.storageGb,
    tdpWatts: d.tdpWatts,
  };
}

export async function createSystem(data: SystemFormData) {
  await db.pcPart.create({
    data: { ...partData(data), partType: 'system', system: { create: specData(data) } },
  });
  revalidatePath('/systems');
}

export async function updateSystem(id: string, data: SystemFormData) {
  await db.$transaction([
    db.pcPart.update({ where: { id }, data: partData(data) }),
    db.system.update({ where: { id }, data: specData(data) }),
  ]);
  revalidatePath('/systems');
}

export async function deleteSystem(id: string) {
  await db.pcPart.delete({ where: { id } });
  revalidatePath('/systems');
}
