'use server';

import { revalidatePath } from 'next/cache';
import { db } from '@/lib/prisma';

const PART_PAGES = new Set([
  '/cpus', '/gpus', '/motherboards', '/cpu-coolers', '/ram', '/storage', '/psus', '/cases', '/fans',
]);

/** The list-page Active checkbox. Only is_active changes; the recommender
 * skips inactive parts, so this is how an imported part goes live. */
export async function setPartActive(
  id: string,
  isActive: boolean,
  page: string,
): Promise<{ error?: string }> {
  if (!PART_PAGES.has(page)) return { error: 'Unknown part page' };
  const { count } = await db.pcPart.updateMany({ where: { id }, data: { isActive } });
  if (count === 0) return { error: 'Part no longer exists' };
  revalidatePath(page);
  return {};
}
