<script module lang="ts">
  import { defineMeta } from '@storybook/addon-svelte-csf';
  import { Accordion, Dropdown, NavTabs, Tabs } from '@service-unavailable/ui';
  import { t } from './copy.svelte';

  const { Story } = defineMeta({ title: 'Navigation/Navigation' });
</script>

<script lang="ts">
  let selected = $state('overview');
  let action = $state('');
</script>

<Story name="Tabs">
  <Tabs label={t('Service settings')} bind:value={selected} items={[
    { value: 'overview', label: t('Overview') },
    { value: 'telemetry', label: t('Telemetry') },
    { value: 'finance', label: t('Finance'), disabled: true }
  ]}>
    {#snippet children(item)}
      {item.value === 'overview' ? t('Service capacity and demand.') : t('Recent measurements from monitored servers.')}
    {/snippet}
  </Tabs>
</Story>

<Story name="Route navigation">
  <NavTabs label={t('Workbench sections')} items={[
    { href: '#overview', label: t('Overview'), current: true },
    { href: '#architecture', label: t('Architecture') },
    { href: '#finance', label: t('Finance') }
  ]} />
</Story>

<Story name="Accordion">
  <div class="list">
    <Accordion initialOpen="capacity" items={[
      { id: 'capacity', title: t('Capacity and demand') },
      { id: 'monitoring', title: t('Monitoring coverage') }
    ]}>
      {#snippet children(item)}
        {item.id === 'capacity' ? t('Compare incoming requests with provisioned capacity.') : t('Measurements are available for monitored servers.')}
      {/snippet}
    </Accordion>
  </div>
</Story>

<Story name="Action dropdown">
  <div class="list">
    <div>
      <Dropdown label={t('Server actions')} items={[
        { id: 'compare', label: t('Compare'), onSelect: () => action = 'Comparison opened.' },
        { id: 'restart', label: t('Restart'), disabled: true, onSelect: () => {} },
        { id: 'remove', label: t('Remove server'), tone: 'danger', onSelect: () => action = 'Removal requested.' }
      ]} />
    </div>
    <output>{action ? t(action) : ''}</output>
  </div>
</Story>

<style>
  .list { display: grid; gap: var(--sui-space-4); max-inline-size: 32rem; }
</style>
