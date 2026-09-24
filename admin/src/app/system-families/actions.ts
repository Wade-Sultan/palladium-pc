'use server';

import { revalidatePath } from 'next/cache';
import { db } from '@/lib/prisma';

export interface SystemFamilyFormData {
  name: string;
  platform: string;
  gpuBackend: string;
  os: string;
  suitedFor: string[];
  summary: string;
  strengthsInput: string;
  limitationsInput: string;
}

/** One item per line: these are sentences, and sentences contain commas. */
function splitLines(value: string): string[] {
  return value.split('\n').map((s) => s.trim()).filter(Boolean);
}

function toData(d: SystemFamilyFormData) {
  return {
    name: d.name,
    platform: d.platform,
    gpuBackend: d.gpuBackend,
    os: d.os,
    suitedFor: d.suitedFor,
    summary: d.summary || null,
    strengths: splitLines(d.strengthsInput),
    limitations: splitLines(d.limitationsInput),
  };
}

export async function createSystemFamily(data: SystemFamilyFormData) {
  await db.systemFamily.create({ data: toData(data) });
  revalidatePath('/system-families');
}

export async function updateSystemFamily(id: string, data: SystemFamilyFormData) {
  await db.systemFamily.update({ where: { id }, data: toData(data) });
  revalidatePath('/system-families');
}

export async function deleteSystemFamily(id: string) {
  await db.systemFamily.delete({ where: { id } });
  revalidatePath('/system-families');
}
