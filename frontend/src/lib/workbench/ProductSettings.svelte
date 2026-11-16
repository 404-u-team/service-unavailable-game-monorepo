<script lang="ts">
  import { Button, Form, FormField, PageColumns, Switch } from '@service-unavailable/ui';
  import Select from '../controls/Select.svelte';
  import NumberInput from '../controls/NumberInput.svelte';
  import { message, t } from '../i18n.svelte';
  import { num, pct, preciseMoney } from '../format';
  import type { Catalog, Game, ProductSettings } from '../types';

  let { game, catalog, busy, error, save }: {
    game: Game; catalog: Catalog; busy: boolean; error: string;
    save: (product: ProductSettings) => Promise<Game | null>;
  } = $props();

  let edits = $state<Partial<ProductSettings>>({});
  const product = $derived({ ...game.product, ...edits });
  const ads = $derived(game.features.find((item) => item.id === 'advertising'));
  const premium = $derived(game.features.find((item) => item.id === 'premium'));
  const estimate = $derived(game.advertising_estimates[product.ad_intensity]);
  const premiumQuotaMode = $derived(product.premium_media_quota_gb === null ? 'standard'
    : product.premium_media_quota_gb === 'unlimited' ? 'unlimited' : 'custom');
  const quotaMin = $derived(catalog.media_quota_min_gb);
  const quotaMax = $derived(catalog.media_quota_max_gb);
  const valid = $derived(Object.values(product).every((value) => typeof value !== 'number' || Number.isFinite(value)));

  function setPremiumQuota(mode: string) {
    if (mode === 'custom') {
      edits.premium_media_quota_gb = Math.min(quotaMax, Math.max(1, product.media_quota_gb ?? 0));
    } else {
      edits.premium_media_quota_gb = mode === 'unlimited' ? 'unlimited' : null;
    }
  }

  async function submit() {
    if (valid && await save(product)) edits = {};
  }
</script>

<Form class="stack" onsubmit={(event) => { event.preventDefault(); void submit(); }}>
  <PageColumns columns={3} minWidth="17rem">
    {#if ads?.state === 'released'}
      <fieldset class="stack">
        <legend>{t('Advertising')}</legend>
        <div class="field"><span>{t('Ad intensity')}</span>
          <Select label={t('Ad intensity')} value={product.ad_intensity} onchange={(value) => edits.ad_intensity = value as ProductSettings['ad_intensity']}
            options={[{ value: 'low', label: t('Low') }, { value: 'moderate', label: t('Moderate') }, { value: 'high', label: t('High') }]} />
        </div>
        {#if estimate}
          <p class="muted">{t('Estimated at current audience and availability with ads enabled.')}</p>
          <dl class="estimate">
            <div><dt>{t('Revenue / day')}</dt><dd>{preciseMoney(estimate.revenue)}</dd></div>
            <div><dt>{t('Impressions / day')}</dt><dd>{num(Math.round(estimate.impressions))}</dd></div>
            <div><dt>{t('Satisfaction impact')}</dt><dd>{t('{0} pp', [num(estimate.satisfaction_impact * 100)])}</dd></div>
            <div><dt>{t('Additional daily churn')}</dt><dd>+{t('{0} pp', [num(estimate.churn_impact * 100)])}</dd></div>
          </dl>
        {/if}
      </fieldset>
    {/if}
    {#if premium?.state === 'released'}
      <fieldset class="stack">
        <legend>{t('Premium subscriptions')}</legend>
        <div class="field"><span>{t('Price per game month (USD)')}</span>
          <NumberInput label={t('Price per game month (USD)')} required min={catalog.premium_price_min} max={catalog.premium_price_max} step={.01} precision={2}
            value={product.premium_price} onchange={(value) => edits.premium_price = value ?? NaN} unit="USD" />
        </div>
        <p class="muted">{t('Higher prices reduce adoption. Price changes apply to new subscriptions and renewals.')}</p>
        <Switch label={t('Offer faster synchronization')} checked={product.premium_fast_sync} onchange={({ currentTarget }) => edits.premium_fast_sync = currentTarget.checked} />
        <Switch label={t('Offer higher-quality media')} checked={product.premium_high_quality_media}
          onchange={({ currentTarget }) => edits.premium_high_quality_media = currentTarget.checked} />
        <FormField label={t('Premium cloud media storage')}>
          {#snippet children(field)}
            <Select {...field} label={t('Premium cloud media storage')} value={premiumQuotaMode} onchange={setPremiumQuota}
              options={[
                { value: 'standard', label: t('Standard plan limit') },
                { value: 'custom', label: t('Custom limit') },
                { value: 'unlimited', label: t('Unlimited') }
              ]} />
          {/snippet}
        </FormField>
        {#if typeof product.premium_media_quota_gb === 'number'}
          <FormField label={t('Cloud media limit per subscriber')} hint={t('Subscribers always get at least the standard plan allowance.')}>
            {#snippet children(field)}
              <NumberInput {...field} label={t('Cloud media limit per subscriber')} required
                min={quotaMin} max={quotaMax} step={quotaMin} precision={2} unit={t('GB')}
                value={product.premium_media_quota_gb as number} onchange={(value) => edits.premium_media_quota_gb = value ?? NaN} />
            {/snippet}
          </FormField>
        {/if}
        <p class="muted">{t('Faster synchronization increases requests. Higher-quality media uses more bandwidth and storage when the standard plan uses lower quality.')}</p>
        <p class="muted">{t('Premium is ad-free. Benefit changes apply to new subscriptions and renewals. Paid terms keep their benefits until they expire.')}</p>
        <p class="muted">{t('Reliability and latency affect renewals.')}</p>
        <dl class="estimate">
          <div><dt>{t('Paying subscribers')}</dt><dd>{num(game.economy.subscribers)}</dd></div>
          <div><dt>{t('Premium satisfaction')}</dt><dd>{pct(game.economy.premium_satisfaction, 1)}</dd></div>
        </dl>
      </fieldset>
    {/if}
    <fieldset class="stack">
      <legend>{t('Service behavior')}</legend>
      <div class="field"><span>{t('Synchronization frequency')}</span>
          <Select label={t('Synchronization frequency')} value={product.sync_frequency} onchange={(value) => edits.sync_frequency = value as ProductSettings['sync_frequency']}
            options={[{ value: 'relaxed', label: t('Relaxed') }, { value: 'standard', label: t('Standard') }, { value: 'frequent', label: t('Frequent') }]} />
        </div>
      <p class="muted">{t('Frequent sync improves responsiveness and generates more requests.')}</p>
      <div class="field"><span>{t('Media quality')}</span>
          <Select label={t('Media quality')} value={product.media_quality} onchange={(value) => edits.media_quality = value as ProductSettings['media_quality']}
            options={[{ value: 'compressed', label: t('Compressed') }, { value: 'standard', label: t('Standard') }, { value: 'high', label: t('High') }]} />
        </div>
      <p class="muted">{t('Compression reduces network and storage use for future uploads and requires more CPU. Higher quality improves satisfaction.')}</p>
      <Switch label={t('Limit cloud media storage')} checked={product.media_quota_gb !== null}
        onchange={({ currentTarget }) => edits.media_quota_gb = currentTarget.checked ? 0.1 : null} />
      {#if product.media_quota_gb !== null}
        <FormField label={t('Cloud media limit per user')}>
          {#snippet children(field)}
            <NumberInput {...field} label={t('Cloud media limit per user')} required
              min={quotaMin} max={quotaMax} step={quotaMin} precision={2} unit={t('GB')}
              value={product.media_quota_gb ?? undefined} onchange={(value) => edits.media_quota_gb = value ?? NaN} />
          {/snippet}
        </FormField>
      {/if}
      <p class="muted">{t('The limit covers images, voice messages and files. It restricts new uploads and keeps existing media.')}</p>
    </fieldset>
    {#if game.product.north_america}
    <fieldset class="stack">
      <legend>{t('Markets')}</legend>
      <p>{t('Europe is the starting market.')}</p>
      <Switch label={t('Acquire users in North America')} checked={product.north_america} onchange={({ currentTarget }) => edits.north_america = currentTarget.checked} />
      <p class="muted">{t('Campaigns and organic growth can reach this market. Existing users keep access if you stop acquisition.')}</p>
    </fieldset>
    {/if}
  </PageColumns>
  {#if error}<p class="notice error" role="alert">{message(error)}</p>{/if}
  <div><Button variant="primary" type="submit" disabled={busy || !valid || !Object.keys(edits).length}>{t('Save product settings')}</Button></div>
</Form>

<style>
  fieldset { background: var(--sui-surface); border: 1px solid var(--border); border-radius: 8px; padding: 12px; min-width: 0; align-content: start; }
  legend { padding-inline: 6px; font-weight: 600; }
  .estimate { margin: 0; font-size: 13px; }
  .estimate div { display: flex; justify-content: space-between; gap: 6px; padding-block: 5px; border-bottom: 1px solid var(--border); }
  .estimate dd { margin: 0; font-family: var(--mono); white-space: nowrap; }
</style>
