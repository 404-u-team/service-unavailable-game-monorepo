<script lang="ts">
  import { Badge, Button, Checkbox } from '@service-unavailable/ui';
  import Modal from '../Modal.svelte';
  import Select from '../controls/Select.svelte';
  import { num } from '../format';
  import { t } from '../i18n.svelte';
  import type { Component, Game, Topology } from '../types';

  let { router, topology, game, editable, busy, close, openDraft, move }: {
    router: Component; topology: Topology; game: Game; editable: boolean; busy: boolean; close: () => void;
    openDraft: () => Promise<Game | null>; move: (keys: number[], owner: string) => Promise<boolean>;
  } = $props();

  const owners = $derived((editable ? game.draft_shard_keys : game.shard_keys)?.[router.id] ?? []);
  const primaries = $derived(topology.nodes.filter((node) => node.kind === 'database' &&
    topology.edges.some((edge) => edge.source === router.id && edge.target === node.id)));
  let source = $state('');
  let destination = $state('');
  let selected = $state<number[]>([]);
  const effectiveSource = $derived(primaries.some((node) => node.id === source) ? source : primaries[0]?.id ?? '');
  const keys = $derived(owners.flatMap((owner, key) => owner === effectiveSource ? [key] : []));

  async function transfer() {
    if (await move(selected.filter((key) => keys.includes(key)), destination)) {
      selected = [];
      destination = '';
    }
  }
</script>

<Modal title={t('Shard key ownership')} side="end" close={close}>
  <div class="stack">
    {#each primaries as node (node.id)}
      {@const writes = game.snapshot.components[node.id]?.database}
      <div class="row spread wrap">
        <strong>{t(node.name)}</strong>
        <Badge>{t('{0} shard keys', [owners.filter((owner) => owner === node.id).length])}</Badge>
      </div>
      {#if writes}
        <small>{t('Live writes · {0} demand / {1} capacity', [num(writes.write_demand), num(writes.write_capacity ?? 0)])}</small>
      {/if}
    {/each}
    {#if !primaries.length}<p>{t('Connect primaries to see their shard keys.')}</p>{/if}
    {#if primaries.length}
      <Select label={t('Source shard')} value={effectiveSource}
        onchange={(value) => { source = value; selected = []; destination = ''; }}
        options={primaries.map((node) => ({ value: node.id, label: t(node.name) }))} />
      {#if editable}
        <fieldset class="key-grid">
          <legend>{t('Select keys to move')}</legend>
          {#each keys as key}
            <Checkbox label={key === 0 ? t('0 · Hot key') : String(key)} checked={selected.includes(key)}
              onchange={({ currentTarget }) => selected = currentTarget.checked ? [...selected, key] : selected.filter((item) => item !== key)} />
          {/each}
        </fieldset>
        <Select label={t('Destination shard')} value={destination} onchange={(value) => destination = value}
          options={primaries.filter((node) => node.id !== effectiveSource).map((node) => ({ value: node.id, label: t(node.name) }))} />
        <Button variant="primary" disabled={busy || !destination || !selected.some((key) => keys.includes(key))} onclick={transfer}>{t('Move shard keys')}</Button>
        <small class="muted">{t('Key moves take effect after you deploy the draft and migrate data.')}</small>
      {:else}
        <p class="keys">{keys.map((key) => key === 0 ? t('0 · Hot key') : key).join(', ')}</p>
        <Button disabled={busy} onclick={openDraft}>{t('Edit in draft')}</Button>
      {/if}
    {/if}
  </div>
</Modal>

<style>
  .key-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(83px, 1fr)); gap: 6px 10px; border: 0; padding: 0; margin: 0; }
  .key-grid legend { margin-bottom: 8px; }
  .keys { overflow-wrap: anywhere; }
</style>
