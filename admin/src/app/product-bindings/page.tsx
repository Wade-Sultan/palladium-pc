export const dynamic = 'force-dynamic';

import { db } from '@/lib/prisma';
import { readEvidence } from '@/lib/product-bindings';
import { ProductBindingsView, type BoundRow, type PartGroup, type UnboundRow } from './client';

// Which Google Shopping product each tracked SKU is, for product-bound pricing.
//
// The backend's discovery job (app/jobs/product_bindings.py) searches once per
// SKU and confirms only clear matches; everything it is unsure of lands here as
// candidates. Parts it found nothing for are listed too, with a box to paste a
// Shopping URL: the first real search (Ryzen 7 9800X3D) returned 40 results
// and not one was the CPU, so that box is a normal path, not an edge case.
export default async function ProductBindingsPage() {
  const partSelect = {
    id: true,
    name: true,
    manufacturer: true,
    partType: true,
    msrpCents: true,
    modelNumber: true,
    isActive: true,
  } as const;

  const [candidates, bound, tracking] = await Promise.all([
    db.googleProductBinding.findMany({
      where: { status: 'candidate' },
      orderBy: [{ createdAt: 'asc' }],
      include: { part: { select: partSelect } },
    }),
    db.googleProductBinding.findMany({
      where: { status: { in: ['confirmed', 'stale'] } },
      orderBy: [{ statusChangedAt: 'desc' }],
      take: 500,
      include: { part: { select: partSelect } },
    }),
    db.priceTrackingState.findMany({
      where: { trackedPartId: { not: null } },
      include: { trackedPart: { select: partSelect } },
    }),
  ]);

  const groups = new Map<string, PartGroup>();
  for (const c of candidates) {
    const evidence = readEvidence(c.matchEvidence);
    let group = groups.get(c.partId);
    if (!group) {
      group = {
        partId: c.partId,
        partName: [c.part.manufacturer, c.part.name].filter(Boolean).join(' '),
        partType: c.part.partType,
        msrpCents: c.part.msrpCents,
        modelNumber: c.part.modelNumber,
        query: evidence.query,
        whyNotAuto: evidence.whyNotAuto,
        candidates: [],
      };
      groups.set(c.partId, group);
    }
    group.candidates.push({
      bindingId: c.id,
      googleProductId: c.googleProductId,
      googleTitle: c.googleTitle,
      createdAt: c.createdAt.toISOString(),
      ...evidence,
    });
  }

  const boundRows: BoundRow[] = bound.map((b) => ({
    bindingId: b.id,
    partId: b.partId,
    partName: [b.part.manufacturer, b.part.name].filter(Boolean).join(' '),
    partType: b.part.partType,
    googleProductId: b.googleProductId,
    googleTitle: b.googleTitle,
    status: b.status,
    confirmedBy: b.confirmedBy,
    since: b.statusChangedAt.toISOString(),
    lastSuccessAt: b.lastSuccessAt?.toISOString() ?? null,
  }));

  // Tracked SKUs with nothing confirmed, pending or stale: the ones only a
  // human (or the next discovery run) can bind.
  const covered = new Set([...candidates, ...bound].map((b) => b.partId));
  const unboundTracking = tracking.filter(
    (t) => t.trackedPart && t.trackedPart.isActive && !covered.has(t.trackedPart.id),
  );
  const unboundIds = [...new Set(unboundTracking.map((t) => t.trackedPart!.id))];
  const searches = unboundIds.length
    ? await db.priceFetch.findMany({
        where: { purpose: 'discovery', partId: { in: unboundIds } },
        orderBy: { fetchedAt: 'desc' },
        select: { partId: true, fetchedAt: true, errorDetail: true },
      })
    : [];
  const lastSearch = new Map<string, { fetchedAt: Date; errorDetail: string | null }>();
  for (const s of searches) {
    if (s.partId && !lastSearch.has(s.partId)) lastSearch.set(s.partId, s);
  }

  const seen = new Set<string>();
  const unbound: UnboundRow[] = [];
  for (const t of unboundTracking) {
    const p = t.trackedPart!;
    if (seen.has(p.id)) continue;
    seen.add(p.id);
    const s = lastSearch.get(p.id);
    unbound.push({
      partId: p.id,
      partName: [p.manufacturer, p.name].filter(Boolean).join(' '),
      partType: p.partType,
      tracksGroup: t.targetKind === 'pc_part' ? null : t.targetKind,
      lastSearchedAt: s?.fetchedAt.toISOString() ?? null,
      lastSearchError: s?.errorDetail ?? null,
    });
  }
  unbound.sort((a, b) => a.partType.localeCompare(b.partType) || a.partName.localeCompare(b.partName));

  return (
    <ProductBindingsView groups={[...groups.values()]} bound={boundRows} unbound={unbound} />
  );
}
