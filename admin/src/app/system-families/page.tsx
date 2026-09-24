export const dynamic = 'force-dynamic';

import { db } from '@/lib/prisma';
import { SystemFamilyTable } from './client';

export default async function SystemFamiliesPage() {
  const data = await db.systemFamily.findMany({
    orderBy: { name: 'asc' },
    include: { _count: { select: { variants: true } } },
  });
  return <SystemFamilyTable data={data} />;
}
