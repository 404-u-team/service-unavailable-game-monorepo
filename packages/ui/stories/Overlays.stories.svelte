<script module lang="ts">
  import { defineMeta } from '@storybook/addon-svelte-csf';
  import { Button, FormField, Modal, Slideover, Switch, TextInput, Toaster, Tooltip, createToasts } from '@service-unavailable/ui';
  import { t } from './copy.svelte';

  const { Story } = defineMeta({ title: 'Overlays/Feedback and overlays' });
</script>

<script lang="ts">
  const toasts = createToasts();
  let modalOpen = $state(false);
  let slideoverOpen = $state(false);
</script>

<Story name="Modal">
  <Button onclick={() => modalOpen = true}>{t('Open deployment review')}</Button>
  <Modal bind:open={modalOpen} title={t('Review deployment')} description={t('Apply the current draft to production?')} closeLabel={t('Close dialog')} dismissible={false}>
    <p>{t('The service will briefly migrate to the new architecture.')}</p>
    {#snippet footer()}
      <div class="row">
        <Button onclick={() => modalOpen = false}>{t('Cancel')}</Button>
        <Button variant="primary" onclick={() => modalOpen = false}>{t('Deploy')}</Button>
      </div>
    {/snippet}
  </Modal>
</Story>

<Story name="Slideover">
  <Button onclick={() => slideoverOpen = true}>{t('Open server settings')}</Button>
  <Slideover bind:open={slideoverOpen} title={t('Server settings')} description={t('Edit the selected API server.')} closeLabel={t('Close dialog')} resizeLabel={t('Resize side panel')}>
    <div class="fields">
      <FormField label={t('Service name')}>
        {#snippet children(control)}<TextInput {...control} value="api-eu-01" />{/snippet}
      </FormField>
      <Switch checked label={t('Enable monitoring')} />
    </div>
    {#snippet footer()}<Button block variant="primary" onclick={() => slideoverOpen = false}>{t('Save settings')}</Button>{/snippet}
  </Slideover>
</Story>

<Story name="Tooltip">
  <div class="help">
    {t('Capacity target')}
    <Tooltip label={t('About capacity targets')} side="bottom" text={t('Capacity is the number of requests that the current topology can serve per second.')} />
  </div>
</Story>

<Story name="Toasts">
  <div class="row">
    <Button variant="primary" onclick={() => toasts.add({
      title: t('Settings saved'), description: t('The workbench now uses your updated settings.'), tone: 'success'
    })}>{t('Show success')}</Button>
    <Button onclick={() => toasts.add({
      title: t('Deployment failed'), description: t('Check the server configuration and retry.'), tone: 'danger', announce: 'assertive'
    })}>{t('Show error')}</Button>
  </div>
  <Toaster {toasts} label={t('Notifications')} dismissLabel={(title) => t('Dismiss {0}', [title])} />
</Story>

<Story name="Top-right notifications">
  <Button onclick={() => toasts.add({
    title: t('Settings saved'), tone: 'success', duration: 0,
    action: { label: t('Example link'), href: '#settings' }
  })}>{t('Show success')}</Button>
  <Toaster {toasts} placement="top-end" label={t('Notifications')} dismissLabel={(title) => t('Dismiss {0}', [title])} />
</Story>

<style>
  .row { display: flex; flex-wrap: wrap; gap: var(--sui-space-2); }
  .fields { display: grid; gap: var(--sui-space-4); }
  .help { display: flex; align-items: center; gap: var(--sui-space-1); }
  p { margin: 0; }
</style>
