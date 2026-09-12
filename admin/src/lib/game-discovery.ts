import type { Prisma } from '@prisma/client';
import { gameDiscoverySchema, referenceKey, requireConfirmation } from './discovery-review';
import { slugify } from './utils';

/** Caller owns the transaction: requirements and review status commit together. */
export async function approveDiscoveredGame(tx: Prisma.TransactionClient, itemId: string) {
  const item = await tx.discoveredItem.findUniqueOrThrow({ where: { id: itemId } });
  requireConfirmation(item);
  if (item.category !== 'game' || item.validationStatus !== 'passed') {
    throw new Error('Game requirements must pass discovery validation before approval.');
  }
  // Read the staged, sourced payload on the server. The browser supplies
  // only an item ID, never new requirements or dependency IDs.
  const fields = gameDiscoverySchema.parse(item.extractedFields);
  const [cpus, chipsets] = await Promise.all([
    tx.pcPart.findMany({ where: { partType: 'cpu' }, select: { id: true, name: true } }),
    tx.gpuChipset.findMany({ select: { id: true, name: true } }),
  ]);
  const requirements = [];
  for (const req of fields.requirements) {
    const category = req.role === 'cpu' ? 'cpu' : 'gpu_chipset';
    const dependency = fields.hardware_dependencies.find((d) =>
      d.category === category && referenceKey(d.name) === referenceKey(req.published_name));
    if (!dependency) throw new Error(`Missing discovery dependency for ${req.published_name}. Run discovery again.`);
    const catalog = req.role === 'cpu' ? cpus : chipsets;
    let resolved = catalog.filter((p) => referenceKey(p.name) === referenceKey(req.published_name));
    if (resolved.length !== 1 && dependency.discovered_item_id) {
      const staged = await tx.discoveredItem.findUnique({ where: { id: dependency.discovered_item_id } });
      const createdId = req.role === 'cpu' ? staged?.createdPartId : staged?.createdChipsetId;
      if (staged?.category === category && staged.reviewStatus === 'approved' && createdId) {
        // Approval may normalize the official retail name. The dependency
        // carries the exact item that was discovered for this requirement.
        resolved = catalog.filter((p) => p.id === createdId);
      }
    }
    if (resolved.length !== 1) {
      throw new Error(`Review and approve ${req.published_name} first, then approve this game.`);
    }
    requirements.push({
      tier: req.tier,
      role: req.role,
      publishedName: req.published_name,
      minRamGb: req.min_ram_gb,
      partId: req.role === 'cpu' ? resolved[0].id : null,
      gpuChipsetId: req.role === 'gpu' ? resolved[0].id : null,
    });
  }
  const game = await tx.game.create({
    data: {
      title: fields.name,
      slug: slugify(fields.name),
      aliases: [],
      genre: fields.genre ?? null,
      storeUrl: fields.store_url,
      hardRequirements: fields.hard_requirements ?? [],
      minStorageGb: fields.min_storage_gb ?? null,
      requirementsNotes: fields.requirements_notes ?? null,
      minimumParts: { create: requirements },
    },
  });
  const { count } = await tx.discoveredItem.updateMany({
    where: { id: itemId, reviewStatus: 'pending' },
    data: { reviewStatus: 'approved', reviewedAt: new Date(), createdGameId: game.id },
  });
  if (count !== 1) throw new Error('Item was already reviewed');
  return game.id;
}
