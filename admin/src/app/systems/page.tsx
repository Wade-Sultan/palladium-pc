export const dynamic = 'force-dynamic';

import { db } from '@/lib/prisma';
import { SystemTable } from './client';

export default async function SystemsPage() {
  const [data, families] = await Promise.all([
    db.system.findMany({
      include: {
        pcPart: { include: { listings: { include: { amazonListing: true } } } },
        family: true,
      },
      orderBy: { pcPart: { name: 'asc' } },
    }),
    db.systemFamily.findMany({ orderBy: { name: 'asc' }, select: { id: true, name: true } }),
  ]);
  return <SystemTable data={data} families={families} />;
}
