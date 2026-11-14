<script lang="ts">
  import Select from './controls/Select.svelte';
  import { onMount } from 'svelte';
  import { locale, setLanguage, t } from './i18n.svelte';
  let ready = $state(false);
  onMount(() => { ready = true; });
</script>

<div class="field">
  <span>{t('Interface language')}</span>
  <Select disabled={!ready} value={locale()} label={t('Interface language')} onchange={(value) => setLanguage(value === 'ru' ? 'ru' : 'en')}
    options={[{ value: 'en', label: 'English' }, { value: 'ru', label: 'Русский' }]} />
</div>
