<script module lang="ts">
  import { defineMeta } from '@storybook/addon-svelte-csf';
  import { Alert, Badge, Disclosure, PageColumns, Panel } from '@service-unavailable/ui';
  import { t } from './copy.svelte';

  const { Story } = defineMeta({ title: 'Layout/Surfaces and statuses' });
</script>

<Story name="Page columns and panels">
  <PageColumns columns={3}>
    <Panel>
      {#snippet header()}<h2>{t('Requests')}</h2>{/snippet}
      <strong>2,450</strong>
    </Panel>
    <Panel>
      {#snippet header()}<h2>{t('Active users')}</h2>{/snippet}
      <strong>18,260</strong>
    </Panel>
    <Panel inset>
      {#snippet header()}<h2>{t('Queue occupancy')}</h2>{/snippet}
      <strong>12%</strong>
    </Panel>
  </PageColumns>
</Story>

<Story name="Badges and alerts">
  <div class="statuses">
    <div class="row">
      <Badge>{t('Draft')}</Badge>
      <Badge tone="success">{t('Healthy')}</Badge>
      <Badge tone="info">{t('Monitored')}</Badge>
      <Badge tone="warning">{t('Saturated')}</Badge>
      <Badge tone="danger">{t('Offline')}</Badge>
    </div>
    <Alert tone="warning" title={t('Capacity warning')}>{t('Incoming traffic is approaching the provisioned limit.')}</Alert>
    <Alert tone="danger" title={t('Deployment failed')}>{t('Check the server configuration and retry.')}</Alert>
  </div>
</Story>

<Story name="Disclosure">
  <Disclosure label={t('Monitoring coverage')}>
    {t('Measurements are available for monitored servers.')}
  </Disclosure>
</Story>

<style>
  h2 { margin: 0; font: 600 1rem/1.35 var(--sui-heading); }
  strong { color: var(--sui-primary); font: var(--sui-title); }
  .statuses { display: grid; gap: var(--sui-space-4); max-inline-size: 42rem; }
  .row { display: flex; flex-wrap: wrap; gap: var(--sui-space-2); }
</style>
