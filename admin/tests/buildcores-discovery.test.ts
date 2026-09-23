import assert from 'node:assert/strict';
import test from 'node:test';
import { buildcoresSource, requireConfirmation } from '../src/lib/discovery-review';
import { discoveryFilters, discoveryWhere } from '../src/lib/discovery-query';

const revision = 'a'.repeat(40);
const id = '00000000-0000-4000-8000-000000000001';
function imported(category = 'cpu', directory = 'CPU') {
  return {
    category, reviewStatus: 'pending', extractedFields: { name: 'Example 120' },
    fieldProvenance: {
      _buildcores: {
        repository: 'https://github.com/buildcores/buildcores-open-db',
        revision, opendb_id: id, board_ids: [id], converter: 'buildcores-v1',
        license: 'https://opendatacommons.org/licenses/by/1-0/',
      },
      name: { source_url: `https://github.com/buildcores/buildcores-open-db/blob/${revision}/open-db/${directory}/${id}.json` },
    },
  };
}

for (const [category, directory] of Object.entries({ cpu: 'CPU', gpu_variant: 'GPU', gpu_chipset: 'GPU', motherboard: 'Motherboard', ram_kit: 'RAM', storage_drive: 'Storage', psu: 'PSU', case: 'PCCase', cpu_cooler: 'CPUCooler', fan: 'CaseFan' })) {
  test(`pinned ${category} import can enter the approval pipeline without web-discovery confirmation`, () => {
    const item = imported(category, directory);
    assert.ok(buildcoresSource(item));
    assert.doesNotThrow(() => requireConfirmation(item, 'Example 120'));
  });
}

test('import approval does not allow a different product or a previously reviewed item', () => {
  const item = imported();
  assert.throws(() => requireConfirmation(item, 'Example 130'), /must match/);
  item.reviewStatus = 'rejected';
  assert.throws(() => requireConfirmation(item), /already reviewed/);
});

test('a marker alone, a moving branch, wrong category, or unrelated URL cannot bypass confirmation', () => {
  const item = imported();
  item.fieldProvenance._buildcores.revision = 'main';
  assert.throws(() => requireConfirmation(item), /Official confirmation/);
  item.fieldProvenance._buildcores.revision = revision;
  item.fieldProvenance.name.source_url = 'https://example.com/spec';
  assert.throws(() => requireConfirmation(item), /Official confirmation/);
  assert.throws(() => requireConfirmation(imported('motherboard', 'CPU')), /Official confirmation/);
  assert.throws(() => requireConfirmation({ ...imported(), fieldProvenance: { _buildcores: { converter: 'buildcores-v1' } } }), /Official confirmation/);
});

test('web-discovery confirmation remains required and still accepts verified evidence', () => {
  const base = { ...imported(), fieldProvenance: {} };
  assert.throws(() => requireConfirmation(base), /Official confirmation/);
  assert.doesNotThrow(() => requireConfirmation({
    ...base, extractedFields: { name: 'Example 120', confirmation_status: 'released' },
    fieldProvenance: { confirmation_status: { verified: true, source_url: 'https://manufacturer.example/spec', snippet: 'Released product' } },
  }));
});

test('queue filters are bounded, preserve normalized punctuation, and apply in the database', () => {
  const filters = discoveryFilters({ q: 'DDR5-6000 (2x16)', source: 'buildcores', category: 'ram_kit', validation: 'failed', page: '2' });
  const where = discoveryWhere(filters);
  assert.equal(filters.page, 2);
  assert.deepEqual(where, {
    reviewStatus: 'pending', category: 'ram_kit', validationStatus: 'failed',
    run: { is: { pipelineVersion: { startsWith: 'buildcores-v1:' } } },
    OR: [{ nameNormalized: { contains: 'ddr56000(2x16)', mode: 'insensitive' } }, { modelNumber: { contains: 'DDR5-6000 (2x16)', mode: 'insensitive' } }],
  });
  assert.equal(discoveryFilters({ page: '-1', category: 'invalid' }).page, 1);
  assert.equal(discoveryFilters({ page: 'Infinity' }).page, 1);
  assert.equal(discoveryFilters({ category: 'invalid' }).category, '');
  assert.equal(discoveryFilters({ q: 'x'.repeat(1000) }).q.length, 200);
});

test('a synthesized GPU chipset candidate may be renamed to the catalog convention', () => {
  const chipset = imported('gpu_chipset', 'GPU');
  chipset.extractedFields.name = 'GeForce RTX 4070 12GB GDDR6X';
  assert.doesNotThrow(() => requireConfirmation(chipset, 'RTX 4070'));
  assert.throws(() => requireConfirmation(imported('gpu_variant', 'GPU'), 'Something else'), /must match/);
});

test('importer review reasons reach the reviewer', () => {
  const item = imported();
  (item.fieldProvenance._buildcores as Record<string, unknown>).review = { reasons: ['no existing RAM group matches'] };
  assert.deepEqual(buildcoresSource(item)?.reasons, ['no existing RAM group matches']);
  assert.deepEqual(buildcoresSource(imported())?.reasons, []);
});
