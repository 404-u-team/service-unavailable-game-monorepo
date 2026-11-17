<script lang="ts">
  import { untrack } from 'svelte';
  import { Alert, Button, Meter, NumberInput } from '@service-unavailable/ui';
  import Modal from '../Modal.svelte';
  import Select from '../controls/Select.svelte';
  import { api } from '../api';
  import { migrationProgress } from './details';
  import { num, preciseMoney } from '../format';
  import { apiMessage, message, t } from '../i18n.svelte';
  import type { Catalog, Component, Game, MigrationPace, MigrationResource, MigrationUpgrade } from '../types';

  let { game, catalog, act, busy, close, initialNode }: {
    game: Game; catalog: Catalog; busy: boolean; initialNode: string; close: () => void;
    act: (path: string, body: object, method?: string) => Promise<Game | null>;
  } = $props();

  const pending = $derived(game.migration);
  const total = $derived(Object.values(pending?.media_sources ?? {}).reduce((sum, gb) => sum + gb, 0));
  const copied = $derived(pending?.media_copied ?? 0);
  const progress = $derived(pending ? migrationProgress(pending) : null);
  const paceLabels = { gentle: 'Gentle', normal: 'Normal', fast: 'Fast' } as const;
  const resources = {
    database: ['storage', 'cpu', 'memory'],
    object_storage: ['storage', 'network']
  } as const satisfies Partial<Record<Component['kind'], readonly MigrationResource[]>>;

  let side = $state<MigrationUpgrade['side']>('production');
  let nodeId = $state(untrack(() => initialNode));
  let field = $state<MigrationResource>('storage');
  let value = $state<number>();
  const nodes = $derived((side === 'production' ? game.production : pending?.topology)?.nodes.filter((node) => node.kind in resources) ?? []);
  const node = $derived(nodes.find((item) => item.id === nodeId));
  const fields = $derived(node?.kind === 'database' || node?.kind === 'object_storage' ? resources[node.kind] : []);
  const definition = $derived(node && catalog.components[node.kind].fields[field]);
  let quote = $state<{ signature: string; cost: number }>();
  let quoting = $state(false);
  let quoteError = $state('');
  const request = $derived(node && value != null ? { revision: game.revision, side, node_id: node.id, field, value } : null);
  const signature = $derived(JSON.stringify(request));
  const current = $derived(definition ? Number(node?.config[field] ?? definition.default) : 0);

  function pace(next: MigrationPace) {
    return act('/migration/pace', { revision: game.revision, pace: next });
  }

  async function upgrade() {
    if (!request) return;
    if (quote?.signature !== signature) {
      const key = signature;
      quoting = true;
      quoteError = '';
      try {
        const { cost } = await api<{ cost: number }>(`/${game.id}/migration/upgrade/quote`, 'POST', request);
        quote = { signature: key, cost };
      } catch (error) {
        quoteError = apiMessage(error);
      } finally {
        quoting = false;
      }
      return;
    }
    if (await act('/migration/upgrade', request)) value = undefined;
  }
</script>

{#if pending}
  <Modal title={t('Architecture migration')} side="end" close={close}>
    <div class="stack">
      {#if progress !== null}
        <Meter label={t('Migration progress')} value={progress} valueText={`${progress}%`} />
      {/if}
      <p>
        {#if pending.blocked}{t('Migration needs attention')}
        {:else if pending.pace === 'paused'}{t('Migration paused')}
        {:else}{t('About {0} ticks remaining', [Math.max(1, pending.ready_at - game.tick)])}{/if}
      </p>
      {#if pending.blocked}
        <Alert tone="warning" title={t('Copying is blocked')}>
          {pending.blocked_reason ? message(pending.blocked_reason) : t('Check space and availability on the source and destination, then resume if the migration is paused.')}
        </Alert>
      {/if}
      {#if Object.keys(pending.database_sources ?? {}).length}
        <h3>{t('Database transfer')}</h3>
        <ul>{#each Object.entries(pending.database_sources ?? {}) as [source, gb]}
          <li>{t(game.production.nodes.find((item) => item.id === source)?.name ?? source)} · {num(gb)} {t('GB')}</li>
        {/each}</ul>
      {/if}
      {#if total}
        <h3>{t('Attachment transfer')}</h3>
        <p>{t('{0} of {1} GB transferred', [num(copied), num(total)])}</p>
        <ul>
          {#each Object.entries(pending.media_sources ?? {}) as [source, gb]}
            <li>{t(game.production.nodes.find((item) => item.id === source)?.name ?? source)} → {t(pending.topology.nodes.find((item) => item.id === pending?.media_target)?.name ?? 'Object Storage')} · {num(gb)} {t('GB')}</li>
          {/each}
        </ul>
        <p class="muted">{t('New uploads use Object Storage. Existing attachments move in batches.')}</p>
      {:else}
        <p class="muted">{t('Production serves traffic while data is copied.')}</p>
      {/if}
      {#if game.speed === 0}
        <Button disabled={busy} onclick={() => act('/clock', { speed: 1 }, 'PUT')}>{t('Run game clock')}</Button>
      {/if}
      <div class="stack">
        <h3>{t('Migration speed')}</h3>
        <div class="row wrap">
          {#each Object.entries(paceLabels) as [setting, label]}
            <Button disabled={busy} aria-pressed={(pending.pace ?? 'normal') === setting}
              onclick={() => pace(setting as MigrationPace)}>{t(label)}</Button>
          {/each}
          <Button disabled={busy || pending.pace === 'paused'} onclick={() => pace('paused')}>{t('Pause migration')}</Button>
        </div>
        <small class="muted">{t('Gentle uses 5% of database capacity, Normal 10%, Fast 20%. Choose a speed to resume.')}</small>
      </div>
      <div class="stack">
        <h3>{t('Upgrade capacity')}</h3>
        <Select label={t('Migration side')} value={side} onchange={(next) => { side = next as MigrationUpgrade['side']; nodeId = ''; value = undefined; }}
          options={[{ value: 'production', label: t('Production') }, { value: 'destination', label: t('After migration') }]} />
        <Select label={t('Component')} value={nodeId} onchange={(next) => { nodeId = next; field = 'storage'; value = undefined; }}
          options={nodes.map((item) => ({ value: item.id, label: side === 'production' && !pending?.topology.nodes.some((candidate) => candidate.id === item.id)
            ? t('{0} · Removed after migration', [t(item.name)]) : t(item.name) }))} />
        {#if node && definition}
          <Select label={t('Resource')} value={field} onchange={(next) => { field = next as MigrationResource; value = undefined; }}
            options={fields.map((key) => ({ value: key, label: t(catalog.components[node.kind].fields[key].label) }))} />
          <p>{t('Current capacity · {0}', [num(current)])}</p>
          <NumberInput aria-label={t('New capacity')} bind:value min={current + (definition.step ?? 1)}
            max={definition.max ?? undefined} step={definition.step ?? 1}
            disabled={current >= (definition.max ?? 0)}
            stepLabels={{ decrease: t('Decrease'), increase: t('Increase') }} />
          {#if quoteError}<Alert tone="danger">{message(quoteError)}</Alert>{/if}
          <Button variant="primary" disabled={busy || quoting || value == null || value <= current || value > (definition.max ?? 0)
            || (quote?.signature === signature && quote.cost > game.balance)}
            onclick={upgrade}>{quote?.signature === signature
              ? t('Buy upgrade for {0}', [preciseMoney(quote.cost)]) : t('Check upgrade cost')}</Button>
        {/if}
      </div>
    </div>
  </Modal>
{/if}
