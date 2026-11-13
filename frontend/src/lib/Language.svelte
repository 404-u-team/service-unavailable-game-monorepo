<script lang="ts">
  import { onMount } from 'svelte';
  import { locale, setLanguage, t } from './i18n.svelte';
  let ready = $state(false);
  onMount(() => { ready = true; });
</script>

<label class="field">
  <span>{t('Interface language')}</span>
  <select disabled={!ready} value={locale()} onchange={(event) => setLanguage(event.currentTarget.value === 'ru' ? 'ru' : 'en')}>
    <option value="en" lang="en">English</option>
    <option value="ru" lang="ru">Русский</option>
  </select>
</label>
