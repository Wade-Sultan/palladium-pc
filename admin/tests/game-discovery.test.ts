import assert from 'node:assert/strict';
import test from 'node:test';
import type { Prisma } from '@prisma/client';
import { approveDiscoveredGame } from '../src/lib/game-discovery';
import { requireConfirmation, referenceKey } from '../src/lib/discovery-review';

// Synthetic names and fixtures: these tests do not call the backend or DB.
const cpuId = '00000000-0000-4000-8000-000000000001';
const gpuId = '00000000-0000-4000-8000-000000000002';
const dependencyId = '00000000-0000-4000-8000-000000000003';

function fixture() {
  const item = {
    id: 'game-discovery', category: 'game', reviewStatus: 'pending', validationStatus: 'passed',
    extractedFields: {
      name: 'Example Quest', confirmation_status: 'officially_announced',
      store_url: 'https://store.steampowered.com/app/1234/Example_Quest/',
      requirements: [
        { tier: 'minimum', role: 'cpu', published_name: 'Intel Core i5-8400', snippet: 'Minimum CPU: Intel Core i5-8400', min_ram_gb: 8 },
        { tier: 'recommended', role: 'gpu', published_name: 'NVIDIA GeForce GTX 1060', snippet: 'Recommended GPU: NVIDIA GeForce GTX 1060', min_ram_gb: 16 },
      ],
      hardware_dependencies: [
        { name: 'Intel Core i5-8400', category: 'cpu', catalog_id: cpuId },
        { name: 'NVIDIA GeForce GTX 1060', category: 'gpu_chipset', catalog_id: null, discovered_item_id: dependencyId },
      ],
    },
    fieldProvenance: { confirmation_status: { verified: true, source_url: 'https://store.steampowered.com/app/1234/', snippet: 'Example Quest is officially announced.' } },
  };
  const created: Record<string, unknown>[] = [];
  const updates: Record<string, unknown>[] = [];
  const tx = {
    discoveredItem: {
      findUniqueOrThrow: async () => item,
      findUnique: async () => ({ category: 'gpu_chipset', reviewStatus: 'pending', createdChipsetId: null }),
      updateMany: async (data: Record<string, unknown>) => { updates.push(data); return { count: 1 }; },
    },
    // Inactive CPUs intentionally remain usable as requirement references.
    pcPart: { findMany: async () => [{ id: cpuId, name: 'Intel Core i5-8400', isActive: false }] },
    gpuChipset: { findMany: async () => [{ id: gpuId, name: 'GeForce GTX 1060' }] },
    game: { create: async ({ data }: { data: Record<string, unknown> }) => { created.push(data); return { id: 'new-game' }; } },
  };
  return { item, tx, created, updates, client: tx as unknown as Prisma.TransactionClient };
}

test('approval links inactive CPU and chipset without creating purchasable hardware', async () => {
  const f = fixture();
  assert.equal(await approveDiscoveredGame(f.client, f.item.id), 'new-game');
  const children = (f.created[0].minimumParts as { create: Record<string, unknown>[] }).create;
  assert.equal(children[0].partId, cpuId);
  assert.equal(children[0].gpuChipsetId, null);
  assert.equal(children[1].gpuChipsetId, gpuId);
  assert.equal(children[1].partId, null);
  assert.deepEqual(children.map((r) => r.tier), ['minimum', 'recommended']);
  assert.equal(f.updates.length, 1);
});

test('pending dependency blocks approval before any catalog write', async () => {
  const f = fixture();
  f.tx.gpuChipset.findMany = async () => [];
  await assert.rejects(approveDiscoveredGame(f.client, f.item.id), /Review and approve/);
  assert.equal(f.created.length, 0);
  assert.equal(f.updates.length, 0);
});

test('neighboring GPU model cannot satisfy a game dependency', async () => {
  const f = fixture();
  f.tx.gpuChipset.findMany = async () => [{ id: gpuId, name: 'GeForce GTX 1060 Ti' }];
  await assert.rejects(approveDiscoveredGame(f.client, f.item.id), /Review and approve/);
  assert.equal(f.created.length, 0);
});

test('a failed game extraction cannot be approved', async () => {
  const f = fixture();
  f.item.validationStatus = 'failed';
  await assert.rejects(approveDiscoveredGame(f.client, f.item.id), /pass discovery validation/);
  assert.equal(f.created.length, 0);
});

test('legacy and unconfirmed discoveries cannot be approved', () => {
  const f = fixture();
  f.item.extractedFields.confirmation_status = 'unconfirmed';
  assert.throws(() => requireConfirmation(f.item), /Official confirmation/);
  f.item.extractedFields.confirmation_status = 'released';
  f.item.fieldProvenance.confirmation_status.verified = false;
  assert.throws(() => requireConfirmation(f.item), /Official confirmation/);
});

test('approval cannot rename confirmed hardware to a rumored next model', () => {
  const f = fixture();
  f.item.category = 'cpu';
  f.item.extractedFields.name = 'Intel Core i5-8400';
  assert.throws(() => requireConfirmation(f.item, 'Intel Core i5-9400'), /confirmed product/);
  assert.doesNotThrow(() => requireConfirmation(f.item, 'Core i5 8400 Processor'));
  assert.notEqual(referenceKey('RTX 5070'), referenceKey('RTX 5070 Ti'));
});

test('published alternatives remain separate requirement rows', async () => {
  const f = fixture();
  f.item.extractedFields.requirements.push({ tier: 'recommended', role: 'cpu', published_name: 'Intel Core i5-8400', snippet: 'Recommended CPU: Intel Core i5-8400', min_ram_gb: 16 });
  await approveDiscoveredGame(f.client, f.item.id);
  const children = (f.created[0].minimumParts as { create: unknown[] }).create;
  assert.equal(children.length, 3);
});
