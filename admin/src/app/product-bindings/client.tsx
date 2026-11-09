'use client';

import { useMemo, useState, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import type { ColumnDef } from '@tanstack/react-table';
import { Check, ExternalLink, Link2, Undo2, X } from 'lucide-react';
import { DataTable } from '@/components/data-table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { googleShoppingUrl, type CandidateEvidence } from '@/lib/product-bindings';
import { formatDate, formatUsd } from '@/lib/utils';
import { bindManually, confirmCandidate, rejectCandidate, retireBinding } from './actions';

export interface CandidateRow extends CandidateEvidence {
  bindingId: string;
  googleProductId: string;
  googleTitle: string | null;
  createdAt: string;
}

export interface PartGroup {
  partId: string;
  partName: string;
  partType: string;
  msrpCents: number | null;
  modelNumber: string | null;
  query: string | null;
  whyNotAuto: string[];
  candidates: CandidateRow[];
}

export interface BoundRow {
  bindingId: string;
  partId: string;
  partName: string;
  partType: string;
  googleProductId: string;
  googleTitle: string | null;
  status: string;
  confirmedBy: string | null;
  since: string;
  lastSuccessAt: string | null;
}

export interface UnboundRow {
  partId: string;
  partName: string;
  partType: string;
  tracksGroup: string | null;
  lastSearchedAt: string | null;
  lastSearchError: string | null;
}

const GROUP_LABELS: Record<string, string> = {
  gpu_chipset: 'GPU chipset',
  psu_group: 'PSU group',
  ram_group: 'RAM group',
  storage_group: 'storage group',
};

/** Runs a server action, shows its error inline, refreshes on success. */
function useAction() {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const run = (action: () => Promise<{ error?: string }>) =>
    startTransition(async () => {
      setError(null);
      const result = await action();
      if (result.error) setError(result.error);
      else router.refresh();
    });
  return { pending, error, run };
}

function ProductLink({ id }: { id: string }) {
  return (
    <a
      href={googleShoppingUrl(id)}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center gap-1 font-mono text-xs text-muted-foreground hover:underline"
    >
      {id}
      <ExternalLink className="h-3 w-3" />
    </a>
  );
}

function CandidateLine({ c, msrpCents }: { c: CandidateRow; msrpCents: number | null }) {
  const { pending, error, run } = useAction();
  return (
    <div className="flex flex-col gap-2 border-t py-3 first:border-t-0 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0 space-y-1">
        <div className="font-medium">{c.googleTitle ?? '(no title)'}</div>
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <ProductLink id={c.googleProductId} />
          {c.source && <span>{c.source}</span>}
          {c.priceCents !== null && (
            <span>
              {formatUsd(c.priceCents)}
              {msrpCents !== null && c.priceRatio !== null && ` (${Math.round(c.priceRatio * 100)}% of MSRP)`}
            </span>
          )}
          {c.coverage !== null && <span>name coverage {c.coverage}</span>}
          {c.multipleSources ? (
            <Badge variant="secondary">multiple sellers</Badge>
          ) : (
            <Badge variant="outline">single listing</Badge>
          )}
          {c.modelNumberInTitle && <Badge variant="secondary">model number in title</Badge>}
        </div>
        {error && <div className="text-xs text-destructive">{error}</div>}
      </div>
      <div className="flex shrink-0 gap-2">
        <Button size="sm" disabled={pending} onClick={() => run(() => confirmCandidate(c.bindingId))}>
          <Check className="mr-1 h-4 w-4" />
          This is it
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={pending}
          onClick={() => run(() => rejectCandidate(c.bindingId))}
        >
          <X className="mr-1 h-4 w-4" />
          Not it
        </Button>
      </div>
    </div>
  );
}

function ManualBind({ partId, compact }: { partId: string; compact?: boolean }) {
  const { pending, error, run } = useAction();
  const [value, setValue] = useState('');
  return (
    <div className="space-y-1">
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          run(() => bindManually(partId, value));
        }}
      >
        <Input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={compact ? 'Shopping URL or product id' : 'None of these? Paste the Google Shopping URL or product id'}
          className="h-8 text-xs"
        />
        <Button size="sm" variant="outline" disabled={pending || !value.trim()} type="submit">
          <Link2 className="mr-1 h-4 w-4" />
          Bind
        </Button>
      </form>
      {error && <div className="text-xs text-destructive">{error}</div>}
    </div>
  );
}

function RetireButton({ bindingId }: { bindingId: string }) {
  const { pending, error, run } = useAction();
  return (
    <div className="flex flex-col items-end gap-1">
      <Button variant="ghost" size="sm" disabled={pending} onClick={() => run(() => retireBinding(bindingId))}>
        <Undo2 className="mr-1 h-4 w-4" />
        Retire
      </Button>
      {error && <span className="text-xs text-destructive">{error}</span>}
    </div>
  );
}

export function ProductBindingsView({
  groups,
  bound,
  unbound,
}: {
  groups: PartGroup[];
  bound: BoundRow[];
  unbound: UnboundRow[];
}) {
  const unboundColumns = useMemo<ColumnDef<UnboundRow>[]>(
    () => [
      {
        accessorKey: 'partName',
        id: 'name',
        header: 'Part',
        cell: ({ row }) => (
          <div className="flex flex-col">
            <span className="font-medium">{row.original.partName}</span>
            <span className="text-xs text-muted-foreground">
              {row.original.partType}
              {row.original.tracksGroup && ` · prices its ${GROUP_LABELS[row.original.tracksGroup] ?? row.original.tracksGroup}`}
            </span>
          </div>
        ),
      },
      {
        accessorKey: 'lastSearchedAt',
        header: 'Last searched',
        cell: ({ row }) =>
          row.original.lastSearchedAt ? (
            <div className="flex flex-col text-xs">
              <span>{formatDate(row.original.lastSearchedAt)}</span>
              <span className="text-muted-foreground">
                {row.original.lastSearchError ? `failed: ${row.original.lastSearchError}` : 'nothing matched'}
              </span>
            </div>
          ) : (
            <span className="text-xs text-muted-foreground">not yet</span>
          ),
      },
      {
        id: 'bind',
        header: 'Bind by hand',
        cell: ({ row }) => <ManualBind partId={row.original.partId} compact />,
      },
    ],
    [],
  );

  const boundColumns = useMemo<ColumnDef<BoundRow>[]>(
    () => [
      {
        accessorKey: 'partName',
        id: 'name',
        header: 'Part',
        cell: ({ row }) => (
          <div className="flex flex-col">
            <span className="font-medium">{row.original.partName}</span>
            <span className="max-w-md truncate text-xs text-muted-foreground" title={row.original.googleTitle ?? ''}>
              {row.original.googleTitle}
            </span>
          </div>
        ),
      },
      {
        accessorKey: 'googleProductId',
        header: 'Product',
        cell: ({ row }) => <ProductLink id={row.original.googleProductId} />,
      },
      {
        accessorKey: 'status',
        header: 'Status',
        cell: ({ row }) => (
          <div className="flex gap-1">
            <Badge variant={row.original.status === 'stale' ? 'destructive' : 'secondary'}>{row.original.status}</Badge>
            {row.original.confirmedBy && <Badge variant="outline">{row.original.confirmedBy}</Badge>}
          </div>
        ),
      },
      {
        accessorKey: 'since',
        header: 'Since',
        cell: ({ row }) => formatDate(row.original.since),
      },
      {
        id: 'actions',
        cell: ({ row }) => <RetireButton bindingId={row.original.bindingId} />,
      },
    ],
    [],
  );

  const autoCount = bound.filter((b) => b.confirmedBy === 'auto').length;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">Product bindings</h1>
        <p className="text-sm text-muted-foreground">
          Which Google Shopping product each tracked part is. Prices are fetched only for confirmed bindings.
          Discovery confirms clear matches itself and leaves the rest here.
        </p>
      </div>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">
          Needs review <span className="text-muted-foreground">({groups.length})</span>
        </h2>
        {groups.length === 0 ? (
          <p className="text-sm text-muted-foreground">No candidates waiting.</p>
        ) : (
          groups.map((g) => (
            <Card key={g.partId}>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">
                  {g.partName}{' '}
                  <span className="text-sm font-normal text-muted-foreground">
                    {g.partType}
                    {g.msrpCents !== null && ` · MSRP ${formatUsd(g.msrpCents)}`}
                    {g.modelNumber && ` · ${g.modelNumber}`}
                  </span>
                </CardTitle>
                {g.whyNotAuto.length > 0 && (
                  <p className="text-xs text-muted-foreground">Not confirmed automatically: {g.whyNotAuto.join('; ')}</p>
                )}
                {g.query && <p className="text-xs text-muted-foreground">Searched for &ldquo;{g.query}&rdquo;</p>}
              </CardHeader>
              <CardContent className="space-y-3">
                <div>
                  {g.candidates.map((c) => (
                    <CandidateLine key={c.bindingId} c={c} msrpCents={g.msrpCents} />
                  ))}
                </div>
                <ManualBind partId={g.partId} />
              </CardContent>
            </Card>
          ))
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">
          No binding <span className="text-muted-foreground">({unbound.length})</span>
        </h2>
        <p className="text-sm text-muted-foreground">
          Tracked parts discovery has not searched yet, or searched and found nothing it could trust. They are not
          priced until bound.
        </p>
        <DataTable columns={unboundColumns} data={unbound} filterPlaceholder="Filter by part name..." />
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">
          Bound <span className="text-muted-foreground">({bound.length}, {autoCount} automatic)</span>
        </h2>
        <DataTable columns={boundColumns} data={bound} filterPlaceholder="Filter by part name..." />
      </section>
    </div>
  );
}
