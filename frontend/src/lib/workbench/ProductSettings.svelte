<script lang="ts">
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

  async function submit() {
    if (await save(product)) edits = {};
  }
</script>

<form class="panel pad stack" onsubmit={(event) => { event.preventDefault(); void submit(); }}>
  <h2>{t('Product settings')}</h2>
  <div class="settings-grid">
    {#if ads?.state === 'released'}
      <fieldset class="stack">
        <legend>{t('Advertising')}</legend>
        <label class="field"><span>{t('Ad intensity')}</span>
          <select value={product.ad_intensity} onchange={(event) => edits.ad_intensity = event.currentTarget.value as ProductSettings['ad_intensity']}>
            <option value="low">{t('Low')}</option>
            <option value="moderate">{t('Moderate')}</option>
            <option value="high">{t('High')}</option>
          </select>
        </label>
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
        <label class="field"><span>{t('Price per game month (USD)')}</span>
          <input type="number" required min={catalog.premium_price_min} max={catalog.premium_price_max} step="0.01"
            value={product.premium_price} oninput={(event) => edits.premium_price = event.currentTarget.valueAsNumber} />
        </label>
        <p class="muted">{t('Higher prices reduce adoption. Price changes apply to new subscriptions and renewals.')}</p>
        <label class="row"><input type="checkbox" role="switch" checked={product.premium_fast_sync} onchange={(event) => edits.premium_fast_sync = event.currentTarget.checked} /> {t('Offer faster synchronization')}</label>
        <p class="muted">{t('Premium is ad-free. Faster synchronization adds load and makes the plan more attractive. Existing terms retain their benefits.')}</p>
        <p class="muted">{t('Reliability and latency affect renewals.')}</p>
        <dl class="estimate">
          <div><dt>{t('Paying subscribers')}</dt><dd>{num(game.economy.subscribers)}</dd></div>
          <div><dt>{t('Premium satisfaction')}</dt><dd>{pct(game.economy.premium_satisfaction, 1)}</dd></div>
        </dl>
      </fieldset>
    {/if}
    <fieldset class="stack">
      <legend>{t('Service behavior')}</legend>
      <label class="field"><span>{t('Synchronization frequency')}</span>
        <select value={product.sync_frequency} onchange={(event) => edits.sync_frequency = event.currentTarget.value as ProductSettings['sync_frequency']}>
          <option value="relaxed">{t('Relaxed')}</option>
          <option value="standard">{t('Standard')}</option>
          <option value="frequent">{t('Frequent')}</option>
        </select>
      </label>
      <p class="muted">{t('Frequent sync improves responsiveness and generates more requests.')}</p>
      <label class="field"><span>{t('Media quality')}</span>
        <select value={product.media_quality} onchange={(event) => edits.media_quality = event.currentTarget.value as ProductSettings['media_quality']}>
          <option value="compressed">{t('Compressed')}</option>
          <option value="standard">{t('Standard')}</option>
          <option value="high">{t('High')}</option>
        </select>
      </label>
      <p class="muted">{t('Compression reduces network and storage use for future uploads and requires more CPU. Higher quality improves satisfaction.')}</p>
    </fieldset>
    {#if game.product.north_america}
    <fieldset class="stack">
      <legend>{t('Markets')}</legend>
      <p>{t('Europe is the starting market.')}</p>
      <label class="row"><input type="checkbox" role="switch" checked={product.north_america} onchange={(event) => edits.north_america = event.currentTarget.checked} /> {t('Acquire users in North America')}</label>
      <p class="muted">{t('Campaigns and organic growth can reach this market. Existing users keep access if you stop acquisition.')}</p>
    </fieldset>
    {/if}
  </div>
  {#if error}<p class="notice error" role="alert">{message(error)}</p>{/if}
  <div><button class="btn primary" type="submit" disabled={busy || !Object.keys(edits).length}>{t('Save product settings')}</button></div>
</form>

<style>
  .settings-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(235px, 100%), 1fr)); gap: 12px; }
  fieldset { border: 1px solid var(--border); border-radius: 8px; padding: 12px; min-width: 0; align-content: start; }
  legend { padding-inline: 6px; font-weight: 600; }
  .estimate { margin: 0; font-size: 13px; }
  .estimate div { display: flex; justify-content: space-between; gap: 6px; padding-block: 5px; border-bottom: 1px solid var(--border); }
  .estimate dd { margin: 0; font-family: var(--mono); white-space: nowrap; }
</style>
