'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import type { ColumnDef } from '@tanstack/react-table';
import type { System, PcPart, Listing, AmazonListing } from '@prisma/client';
import { Pencil, Trash2 } from 'lucide-react';
import { DataTable } from '@/components/data-table';
import { Button } from '@/components/ui/button';
import { ActiveToggle } from '@/components/active-toggle';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ListingsDialog } from '@/components/listings-dialog';
import { centsToUsd, formatUsd } from '@/lib/utils';
import { createSystem, updateSystem, deleteSystem, type SystemFormData } from './actions';

type SystemWithPart = System & {
  pcPart: PcPart & { listings: (Listing & { amazonListing: AmazonListing | null })[] };
  family: { id: string; name: string };
};
type FamilyOption = { id: string; name: string };

// Nullable to match the form's empty state, then required: these three are
// what the offer rules compare, and a zero would read as "holds nothing".
const requiredCount = z.coerce
  .number()
  .int()
  .nullable()
  .refine((v) => v != null && v > 0, 'Required');

const schema = z.object({
  name: z.string().min(1, 'Name is required'),
  manufacturer: z.string(),
  modelNumber: z.string(),
  yearReleased: z.coerce.number().int().nullable(),
  isActive: z.boolean(),
  msrpUsd: z.coerce.number().nullable(),
  systemFamilyId: z.string().min(1, 'Family is required'),
  chip: z.string().min(1, 'Chip is required'),
  cpuCores: z.coerce.number().int().nullable(),
  gpuCores: z.coerce.number().int().nullable(),
  unifiedMemoryGb: requiredCount,
  gpuAddressableMemoryGb: requiredCount,
  memoryBandwidthGbps: requiredCount,
  storageGb: z.coerce.number().int().nullable(),
  tdpWatts: z.coerce.number().int().nullable(),
});

function SystemForm({ item, families, onSuccess }: { item: SystemWithPart | null; families: FamilyOption[]; onSuccess: () => void }) {
  const form = useForm<SystemFormData>({
    resolver: zodResolver(schema),
    defaultValues: item ? {
      name: item.pcPart.name,
      manufacturer: item.pcPart.manufacturer ?? '',
      modelNumber: item.pcPart.modelNumber ?? '',
      yearReleased: item.pcPart.yearReleased,
      isActive: item.pcPart.isActive,
      msrpUsd: centsToUsd(item.pcPart.msrpCents),
      systemFamilyId: item.systemFamilyId,
      chip: item.chip,
      cpuCores: item.cpuCores,
      gpuCores: item.gpuCores,
      unifiedMemoryGb: item.unifiedMemoryGb,
      gpuAddressableMemoryGb: item.gpuAddressableMemoryGb,
      memoryBandwidthGbps: item.memoryBandwidthGbps,
      storageGb: item.storageGb,
      tdpWatts: item.tdpWatts,
    } : {
      name: '', manufacturer: '', modelNumber: '', yearReleased: null, isActive: true,
      msrpUsd: null, systemFamilyId: '', chip: '', cpuCores: null, gpuCores: null,
      unifiedMemoryGb: null, gpuAddressableMemoryGb: null, memoryBandwidthGbps: null,
      storageGb: null, tdpWatts: null,
    },
  });

  const [error, setError] = useState<string | null>(null);

  const numField = (field: { value: number | null; onChange: (v: number | null) => void }) => ({
    ...field,
    type: 'number' as const,
    value: field.value ?? '',
    onChange: (e: React.ChangeEvent<HTMLInputElement>) =>
      field.onChange(e.target.value === '' ? null : Number(e.target.value)),
  });

  async function onSubmit(data: SystemFormData) {
    setError(null);
    try {
      if (item) { await updateSystem(item.id, data); } else { await createSystem(data); }
      onSuccess();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'An error occurred');
    }
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField control={form.control} name="systemFamilyId"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Family * (backend, OS, what it is offered for)</FormLabel>
              <Select value={field.value} onValueChange={field.onChange}>
                <FormControl><SelectTrigger><SelectValue placeholder="Select a family" /></SelectTrigger></FormControl>
                <SelectContent>
                  {families.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
                </SelectContent>
              </Select>
              <FormMessage />
            </FormItem>
          )}
        />
        <div className="grid grid-cols-2 gap-4">
          {([
            ['name', 'Product Name * (include memory and storage)'], ['manufacturer', 'Manufacturer'],
            ['modelNumber', 'Model Number'], ['chip', 'Chip * (e.g. M5 Max 18C/40G)'],
          ] as [keyof SystemFormData, string][]).map(([name, label]) => (
            <FormField key={name} control={form.control} name={name}
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{label}</FormLabel>
                  <FormControl><Input {...field} value={field.value as string ?? ''} /></FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          ))}
          {([
            ['msrpUsd', 'List price (USD)'], ['yearReleased', 'Year'],
            ['unifiedMemoryGb', 'Unified memory (GB) *'],
            ['gpuAddressableMemoryGb', 'GPU-addressable memory (GB) * (what a model can use, not the headline)'],
            ['memoryBandwidthGbps', 'Memory bandwidth (GB/s) *'], ['storageGb', 'Storage (GB)'],
            ['cpuCores', 'CPU cores'], ['gpuCores', 'GPU cores'], ['tdpWatts', 'Power (W)'],
          ] as [keyof SystemFormData, string][]).map(([name, label]) => (
            <FormField key={name} control={form.control} name={name}
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{label}</FormLabel>
                  <FormControl>
                    <Input {...numField(field as { value: number | null; onChange: (v: number | null) => void })} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          ))}
        </div>
        <FormField control={form.control} name="isActive"
          render={({ field }) => (
            <FormItem className="flex items-center gap-2 space-y-0">
              <FormControl><Checkbox checked={field.value} onCheckedChange={field.onChange} /></FormControl>
              <FormLabel>Active</FormLabel>
            </FormItem>
          )}
        />
        {error && <p className="text-sm text-destructive">{error}</p>}
        <div className="flex justify-end pt-2">
          <Button type="submit" disabled={form.formState.isSubmitting}>
            {form.formState.isSubmitting ? 'Saving...' : item ? 'Update system' : 'Create system'}
          </Button>
        </div>
      </form>
    </Form>
  );
}

export function SystemTable({ data, families }: { data: SystemWithPart[]; families: FamilyOption[] }) {
  const router = useRouter();
  const [selected, setSelected] = useState<SystemWithPart | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const handleSuccess = () => { setDialogOpen(false); router.refresh(); };
  const handleDelete = async (id: string) => { await deleteSystem(id); setDeleteId(null); router.refresh(); };

  const columns: ColumnDef<SystemWithPart>[] = [
    { id: 'name', accessorFn: (r) => r.pcPart.name, header: 'Name', enableSorting: true },
    { id: 'family', accessorFn: (r) => r.family.name, header: 'Family', enableSorting: true },
    { accessorKey: 'gpuAddressableMemoryGb', header: 'GPU memory (GB)', enableSorting: true },
    { accessorKey: 'memoryBandwidthGbps', header: 'GB/s', enableSorting: true },
    {
      id: 'price', header: 'Price', enableSorting: true,
      accessorFn: (r) => r.pcPart.streetPriceCents ?? r.pcPart.msrpCents ?? -1,
      cell: ({ row }) => {
        const p = row.original.pcPart;
        if (p.streetPriceCents == null && p.msrpCents == null) {
          return <span className="text-destructive" title="Unpriced systems are never offered">none</span>;
        }
        return p.streetPriceCents != null ? formatUsd(p.streetPriceCents) : `${formatUsd(p.msrpCents)} (list)`;
      },
    },
    {
      id: 'listings', header: 'Listings',
      cell: ({ row }) => (
        <ListingsDialog
          partId={row.original.pcPart.id}
          partName={row.original.pcPart.name}
          group={{ kind: 'systemFamily', id: row.original.family.id, name: row.original.family.name }}
          listings={row.original.pcPart.listings}
        />
      ),
    },
    {
      id: 'isActive', accessorFn: (r) => r.pcPart.isActive, header: 'Active',
      cell: ({ row }) => <ActiveToggle partId={row.original.pcPart.id} active={row.original.pcPart.isActive} page="/systems" />,
    },
    {
      id: 'actions', header: '',
      cell: ({ row }) => (
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="sm" onClick={() => { setSelected(row.original); setDialogOpen(true); }}>
            <Pencil className="h-3.5 w-3.5" />
          </Button>
          <Button variant="ghost" size="sm" className="text-destructive hover:text-destructive" onClick={() => setDeleteId(row.original.id)}>
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Complete Systems</h1>
          <p className="text-muted-foreground text-sm mt-1">{data.length} systems, offered in chat instead of a custom build when they fit</p>
        </div>
        <Button onClick={() => { setSelected(null); setDialogOpen(true); }} disabled={families.length === 0}>New system</Button>
      </div>
      {families.length === 0 && (
        <p className="text-sm text-muted-foreground">Create a System Family first: every system belongs to one.</p>
      )}
      <DataTable columns={columns} data={data} filterPlaceholder="Filter systems..." />
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-3xl">
          <DialogHeader><DialogTitle>{selected ? 'Edit system' : 'New system'}</DialogTitle></DialogHeader>
          <SystemForm item={selected} families={families} onSuccess={handleSuccess} />
        </DialogContent>
      </Dialog>
      <AlertDialog open={!!deleteId} onOpenChange={(open) => !open && setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete system?</AlertDialogTitle>
            <AlertDialogDescription>This action cannot be undone.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => deleteId && handleDelete(deleteId)}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
