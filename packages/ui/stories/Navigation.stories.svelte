<script module lang="ts">
  import { defineMeta } from '@storybook/addon-svelte-csf';
  import { Accordion, ActionRow, Badge, Dropdown, NavTabs, Pagination, Tabs } from '@service-unavailable/ui';
  import { t } from './copy.svelte';

  const { Story } = defineMeta({ title: 'Navigation/Navigation' });
</script>

<script lang="ts">
  let selected = $state('overview');
  let action = $state('');
  let page = $state(1);
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

<Story name="Pagination">
  <Pagination {page} pages={5} label={t('Pagination')} previousLabel={t('Previous page')}
    nextLabel={t('Next page')} pageLabel={(page, pages) => t('Page {0} of {1}', [page, pages])}
    onchange={(next) => page = next} />
</Story>

<Story name="Action row">
  <div class="list">
    <ActionRow title={t('Monitoring coverage')} description={t('Measurements are available for monitored servers.')} href="#coverage">
      {#snippet status()}<Badge tone="success">{t('Monitored')}</Badge>{/snippet}
    </ActionRow>
    <ActionRow title={t('Server settings')} onclick={() => action = 'Settings saved'} />
    <output>{t(action)}</output>
  </div>
</Story>

<Story name="Route navigation">
  <NavTabs label={t('Workbench sections')} items={[
    { href: '#overview', label: t('Overview'), current: true },
    { href: '#architecture', label: t('Architecture') },
    { href: '#finance', label: t('Finance') }
  ]} />
</Story>

<Story name="Navigation rail">
  <div class="rail">
    <NavTabs variant="rail" label={t('Workbench sections')} items={[
      { href: '#monitor', label: t('Monitor'), current: true },
      { href: '#saves', label: t('Saved games') }
    ]} />
  </div>
</Story>

<Story name="Accordion">
  <div class="list">
    <Accordion initialOpen="capacity" items={[
      { id: 'capacity', title: t('Capacity and demand') },
      { id: 'monitoring', title: t('Monitoring coverage') }
    ]}>
      {#snippet summary(item)}
        {#if item.id === 'monitoring'}<Badge tone="success">{t('Monitored')}</Badge>{/if}
      {/snippet}
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
  .rail { inline-size: 6.25rem; padding-inline: var(--sui-space-1); }
</style>
