<script lang="ts">
  import { LocalizedNumberInput } from '@service-unavailable/ui';
  import type { ComponentProps } from 'svelte';
  import { locale, t } from '../i18n.svelte';
  import { parseNumber } from './numeric';

  let { value = $bindable(), ...props }:
    Omit<ComponentProps<typeof LocalizedNumberInput>, 'locale' | 'parse' | 'invalidMessage' | 'stepLabels'> = $props();
</script>

<LocalizedNumberInput {...props} bind:value locale={locale()} parse={(text) => parseNumber(text, locale())}
  invalidMessage={t('Enter a number between {0} and {1}.', [props.min ?? -Infinity, props.max ?? Infinity])}
  stepLabels={{ decrease: t('Decrease {0}', [props.label]), increase: t('Increase {0}', [props.label]) }} />
