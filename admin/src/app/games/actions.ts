'use server';

import { revalidatePath } from 'next/cache';
import { db } from '@/lib/prisma';
import { splitCommaList, slugify } from '@/lib/utils';

export interface GameMinimumPartFormData {
  tier: string; // minimum | recommended | ultra
  role: string; // cpu | gpu
  partId: string | null;
  gpuChipsetId: string | null;
  publishedName: string;
  minRamGb: number | null;
}

export interface GamePerformanceProfileFormData {
  gameVersion: string;
  resolution: '1080p' | '1440p' | '4k';
  targetFps: number;
  qualityPreset: 'low' | 'medium' | 'high' | 'ultra';
  rayTracingMode: 'off' | 'low' | 'medium' | 'high' | 'ultra' | 'path_tracing';
  upscalingMode: 'native' | 'quality' | 'balanced' | 'performance';
  frameGeneration: boolean;
  minGpuRasterScore: number | null;
  minGpuRtScore: number | null;
  minGpuModernScore: number | null;
  minCpuSingleScore: number | null;
  minCpuMultiScore: number | null;
  minVramGb: number | null;
  minRamGb: number | null;
  requiredFeaturesInput: string;
  confidence: number;
  sampleCount: number;
  derivationMethod: string;
  sourceUrlsInput: string;
  notes: string;
  isActive: boolean;
}

export interface GameFormData {
  title: string;
  slug: string;
  genre: string;
  storeUrl: string;
  imageUrl: string;
  hardRequirementsInput: string;
  minStorageGb: number | null;
  requirementsNotes: string;
  minimumParts: GameMinimumPartFormData[];
  performanceProfiles: GamePerformanceProfileFormData[];
}

function toData(d: GameFormData) {
  return {
    title: d.title,
    slug: d.slug ? slugify(d.slug) : slugify(d.title),
    genre: d.genre || null,
    storeUrl: d.storeUrl || null,
    imageUrl: d.imageUrl || null,
    hardRequirements: splitCommaList(d.hardRequirementsInput),
    minStorageGb: d.minStorageGb,
    requirementsNotes: d.requirementsNotes || null,
  };
}

// Every GameMinimumPart column is represented in the form, so children are
// simply replaced wholesale on save.
function toMinimumParts(rows: GameMinimumPartFormData[]) {
  return rows.map((r) => ({
    tier: r.tier,
    role: r.role,
    partId: r.partId,
    gpuChipsetId: r.gpuChipsetId,
    publishedName: r.publishedName || null,
    minRamGb: r.minRamGb,
  }));
}

function toPerformanceProfiles(rows: GamePerformanceProfileFormData[]) {
  return rows.map((r) => ({
    gameVersion: r.gameVersion || null,
    resolution: r.resolution,
    targetFps: r.targetFps,
    qualityPreset: r.qualityPreset,
    rayTracingMode: r.rayTracingMode,
    upscalingMode: r.upscalingMode,
    frameGeneration: r.frameGeneration,
    minGpuRasterScore: r.minGpuRasterScore,
    minGpuRtScore: r.minGpuRtScore,
    minGpuModernScore: r.minGpuModernScore,
    minCpuSingleScore: r.minCpuSingleScore,
    minCpuMultiScore: r.minCpuMultiScore,
    minVramGb: r.minVramGb,
    minRamGb: r.minRamGb,
    requiredFeatures: splitCommaList(r.requiredFeaturesInput),
    confidence: r.confidence,
    sampleCount: r.sampleCount,
    derivationMethod: r.derivationMethod,
    sourceUrls: splitCommaList(r.sourceUrlsInput),
    notes: r.notes || null,
    isActive: r.isActive,
  }));
}

export async function createGame(data: GameFormData) {
  await db.game.create({
    data: {
      ...toData(data),
      minimumParts: { create: toMinimumParts(data.minimumParts) },
      performanceProfiles: { create: toPerformanceProfiles(data.performanceProfiles) },
    },
  });
  revalidatePath('/games');
}

export async function updateGame(id: string, data: GameFormData) {
  await db.game.update({
    where: { id },
    data: {
      ...toData(data),
      minimumParts: { deleteMany: {}, create: toMinimumParts(data.minimumParts) },
      performanceProfiles: {
        deleteMany: {},
        create: toPerformanceProfiles(data.performanceProfiles),
      },
    },
  });
  revalidatePath('/games');
}

export async function deleteGame(id: string) {
  await db.game.delete({ where: { id } });
  revalidatePath('/games');
}
