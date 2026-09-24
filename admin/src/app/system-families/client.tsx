'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import type { ColumnDef } from '@tanstack/react-table';
import type { SystemFamily } from '@prisma/client';
import { Pencil, Trash2 } from 'lucide-react';
import { DataTable } from '@/components/data-table';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Form, FormControl, FormDescription, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import { SYSTEM_WORKLOADS } from '@/lib/system-workloads';
import {
  createSystemFamily, updateSystemFamily, deleteSystemFamily, type SystemFamilyFormData,
} from './actions';

type FamilyRow = SystemFamily & { _count: { variants: number } };

const schema = z.object({
  name: z.string().min(1, 'Name is required'),
  platform: z.string().min(1, 'Platform is required'),
  gpuBackend: z.string().min(1, 'GPU backend is required'),
  os: z.string().min(1, 'OS is required'),
  suitedFor: z.array(z.string()),
  summary: z.string(),
  strengthsInput: z.string(),
  limitationsInput: z.string(),
});

function FamilyForm({ item, onSuccess }: { item: FamilyRow | null; onSuccess: () => void }) {
  const form = useForm<SystemFamilyFormData>({
    resolver: zodResolver(schema),
    defaultValues: item ? {
      name: item.name,
      platform: item.platform,
      gpuBackend: item.gpuBackend,
      os: item.os,
      suitedFor: item.suitedFor,
      summary: item.summary ?? '',
      strengthsInput: item.strengths.join('\n'),
      limitationsInput: item.limitations.join('\n'),
    } : {
      name: '', platform: '', gpuBackend: '', os: '', suitedFor: [],
      summary: '', strengthsInput: '', limitationsInput: '',
    },
  });
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(data: SystemFamilyFormData) {
    setError(null);
    try {
      if (item) { await updateSystemFamily(item.id, data); } else { await createSystemFamily(data); }
      onSuccess();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'An error occurred');
    }
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          {([
            ['name', 'Name * (e.g. DGX Spark (GB10))', 'Shown to users; a trailing parenthetical is dropped on buttons.'],
            ['platform', 'Platform * (grouping label, e.g. nvidia_gb10)', 'Never branched on by code.'],
            ['gpuBackend', 'GPU backend * (cuda / metal / rocm)', 'Matched against the backends an AI workload is published for.'],
            ['os', 'OS * (e.g. macOS, Windows 11 or Linux)', 'Offers put families running the OS a user names first.'],
          ] as [keyof SystemFamilyFormData, string, string][]).map(([name, label, hint]) => (
            <FormField key={name} control={form.control} name={name}
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{label}</FormLabel>
                  <FormControl><Input {...field} value={field.value as string} /></FormControl>
                  <FormDescription>{hint}</FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
          ))}
        </div>
        <FormField control={form.control} name="suitedFor"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Offered for</FormLabel>
              <FormDescription>
                The chat only offers this family for the workloads ticked here. Revisit as software support changes.
              </FormDescription>
              <div className="grid grid-cols-2 gap-2">
                {SYSTEM_WORKLOADS.map((w) => (
                  <label key={w.value} className="flex items-center gap-2 text-sm">
                    <Checkbox
                      checked={field.value.includes(w.value)}
                      onCheckedChange={(checked) =>
                        field.onChange(
                          checked ? [...field.value, w.value] : field.value.filter((v) => v !== w.value),
                        )
                      }
                    />
                    {w.label}
                  </label>
                ))}
              </div>
            </FormItem>
          )}
        />
        <FormField control={form.control} name="summary"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Summary (offer card subtitle)</FormLabel>
              <FormControl><Textarea rows={2} {...field} /></FormControl>
            </FormItem>
          )}
        />
        <div className="grid grid-cols-2 gap-4">
          {([
            ['strengthsInput', 'Strengths (one per line)'],
            ['limitationsInput', 'Limitations (one per line)'],
          ] as [keyof SystemFamilyFormData, string][]).map(([name, label]) => (
            <FormField key={name} control={form.control} name={name}
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{label}</FormLabel>
                  <FormControl><Textarea rows={5} {...field} value={field.value as string} /></FormControl>
                  <FormDescription>
                    Shown on the offer card verbatim, and the only tradeoffs the pitch may mention.
                  </FormDescription>
                </FormItem>
              )}
            />
          ))}
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <div className="flex justify-end pt-2">
          <Button type="submit" disabled={form.formState.isSubmitting}>
            {form.formState.isSubmitting ? 'Saving...' : item ? 'Update family' : 'Create family'}
          </Button>
        </div>
      </form>
    </Form>
  );
}

export function SystemFamilyTable({ data }: { data: FamilyRow[] }) {
  const router = useRouter();
  const [selected, setSelected] = useState<FamilyRow | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const handleSuccess = () => { setDialogOpen(false); router.refresh(); };
  const handleDelete = async (id: string) => { await deleteSystemFamily(id); setDeleteId(null); router.refresh(); };

  const columns: ColumnDef<FamilyRow>[] = [
    { accessorKey: 'name', header: 'Name', enableSorting: true },
    { accessorKey: 'gpuBackend', header: 'Backend', enableSorting: true },
    { accessorKey: 'os', header: 'OS' },
    { id: 'suitedFor', accessorFn: (r) => r.suitedFor.join(', '), header: 'Offered for' },
    { id: 'variants', accessorFn: (r) => r._count.variants, header: 'Systems', enableSorting: true },
    {
      id: 'actions', header: '',
      cell: ({ row }) => (
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="sm" onClick={() => { setSelected(row.original); setDialogOpen(true); }}>
            <Pencil className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost" size="sm" className="text-destructive hover:text-destructive"
            disabled={row.original._count.variants > 0}
            title={row.original._count.variants > 0 ? 'Delete its systems first' : undefined}
            onClick={() => setDeleteId(row.original.id)}
          >
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
          <h1 className="text-2xl font-bold">System Families</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Complete machines grouped by platform. What each family is offered for lives here, not in code.
          </p>
        </div>
        <Button onClick={() => { setSelected(null); setDialogOpen(true); }}>New family</Button>
      </div>
      <DataTable columns={columns} data={data} filterPlaceholder="Filter families..." />
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle>{selected ? 'Edit family' : 'New family'}</DialogTitle></DialogHeader>
          <FamilyForm item={selected} onSuccess={handleSuccess} />
        </DialogContent>
      </Dialog>
      <AlertDialog open={!!deleteId} onOpenChange={(open) => !open && setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete family?</AlertDialogTitle>
            <AlertDialogDescription>Its eBay group listings are deleted with it. This cannot be undone.</AlertDialogDescription>
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
