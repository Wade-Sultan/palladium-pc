/** The storage vocabulary the backend reads: StorageInterface in
 * backend/app/models/pcparts.py, the discovery validator's storage_type set,
 * and the "2.5"/"3.5" bay matching in recommender/validation.py. Free-text
 * entry once produced `sata`, `sata_ssd` and `2_5_inch`, which hid every
 * SATA drive from the recommender, so forms pick from these lists and the
 * server actions refuse anything else. */
export const STORAGE_TYPES = [
  { value: 'nvme', label: 'NVMe SSD' },
  { value: 'ssd', label: 'SSD (not NVMe)' },
  { value: 'hdd', label: 'Hard drive' },
] as const;

export const STORAGE_INTERFACES = [
  { value: 'pcie_gen3', label: 'PCIe Gen 3' },
  { value: 'pcie_gen4', label: 'PCIe Gen 4' },
  { value: 'pcie_gen5', label: 'PCIe Gen 5' },
  { value: 'sata3', label: 'SATA III' },
] as const;

export const STORAGE_FORM_FACTORS = [
  { value: 'm2_2280', label: 'M.2 2280' },
  { value: 'm2_2230', label: 'M.2 2230' },
  { value: 'm2_2242', label: 'M.2 2242' },
  { value: 'm2_2260', label: 'M.2 2260' },
  { value: 'm2_22110', label: 'M.2 22110' },
  { value: '2.5', label: '2.5-inch' },
  { value: '3.5', label: '3.5-inch' },
] as const;

const allowed = (options: readonly { value: string }[]) => new Set(options.map((o) => o.value));
const types = allowed(STORAGE_TYPES);
const interfaces = allowed(STORAGE_INTERFACES);
const formFactors = allowed(STORAGE_FORM_FACTORS);

/** Server-side guard for any action that writes a storage group. */
export function storageVocabError(d: { storageType: string; formFactor: string; interface: string }): string | null {
  if (!types.has(d.storageType)) return `Unknown storage type "${d.storageType}"`;
  if (!interfaces.has(d.interface)) return `Unknown storage interface "${d.interface}"`;
  if (!formFactors.has(d.formFactor)) return `Unknown storage form factor "${d.formFactor}"`;
  // Same pairings the backend's discovery validator rejects.
  if (d.storageType === 'nvme' && d.interface === 'sata3') return 'NVMe drives are not SATA';
  if (d.storageType === 'hdd' && d.interface.startsWith('pcie')) return 'Hard drives are not PCIe';
  return null;
}
