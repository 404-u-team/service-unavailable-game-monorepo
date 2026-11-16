<script module lang="ts">
  import { defineMeta } from '@storybook/addon-svelte-csf';
  import { CircleHelp } from '@lucide/svelte';
  import { Button, Checkbox, FilePicker, Form, FormField, LocalizedNumberInput, NumberInput, SearchSelect, Select, Slider, Switch, Textarea, TextInput } from '@service-unavailable/ui';
  import { locale, stepLabels, t } from './copy.svelte';
  import { parseNumber } from '../../../frontend/src/lib/controls/numeric';

  const { Story } = defineMeta({ title: 'Inputs/Controls' });
</script>

<script lang="ts">
  let capacity = $state(240);
  let amount = $state<number | undefined>(1500.25);
  let markets = $state(['europe']);
  let selected = $state('');
  let regionSaved = $state(false);
  let traffic = $state(45);
  let email = $state('');
  let saved = $state('');
  let fileName = $state('');
  let mixed = $state(true);
</script>

<Story name="File picker">
  <div class="fields">
    <div class="row">
      <FilePicker label={t('Import layout preset')} accept=".json,application/json" onchange={(file) => fileName = file.name}>
        {t('Import layout preset')}
      </FilePicker>
      <FilePicker label={t('Import layout into current game')} disabled onchange={() => {}}>
        {t('Import layout into current game')}
      </FilePicker>
    </div>
    <output>{fileName}</output>
  </div>
</Story>

<Story name="Localized number">
  <div class="fields">
    <LocalizedNumberInput label={t('Campaign budget')} bind:value={amount} locale={locale()} min={10} max={100000} step={50} precision={2} unit="USD"
      parse={(text) => parseNumber(text, locale())} stepLabels={stepLabels(t('Campaign budget'))}
      invalidMessage={t('Enter an amount between {0} and {1}.', [10, 100000])} required />
  </div>
</Story>

<Story name="Searchable selection">
  <div class="fields">
    <SearchSelect label={t('Target markets')} {t} multiple searchable selected={markets} choose={(values) => markets = values}
      options={[
        { value: 'europe', label: t('Europe') },
        { value: 'asia', label: t('Asia') },
        { value: 'oceania', label: t('Oceania'), disabled: true, reason: t('Launch the market to target it.') }
      ]} />
  </div>
</Story>

<Story name="Buttons">
  <div class="row">
    <Button variant="primary">{t('Save settings')}</Button>
    <Button>{t('Compare')}</Button>
    <Button variant="ghost">{t('Cancel')}</Button>
    <Button variant="danger">{t('Remove server')}</Button>
    <Button disabled>{t('Unavailable')}</Button>
    <Button iconOnly aria-label={t('Help')}><CircleHelp size={18} aria-hidden="true" /></Button>
  </div>
</Story>

<Story name="Text and textarea">
  <div class="fields">
    <FormField label={t('Service name')} hint={t('Shown in the workbench.')}>
      {#snippet children(control)}<TextInput {...control} name="service" placeholder="Messenger" />{/snippet}
    </FormField>
    <FormField label={t('Email')} error={t('Enter a valid email address.')}>
      {#snippet children(control)}<TextInput {...control} name="email" type="email" value="ops@" required />{/snippet}
    </FormField>
    <FormField label={t('Deployment notes')}>
      {#snippet children(control)}<Textarea {...control} name="notes" placeholder={t('Describe the changes for your team.')} />{/snippet}
    </FormField>
  </div>
</Story>

<Story name="Number input">
  <div class="fields">
    <FormField label={t('Server capacity')} hint={t('Use the arrow keys to change the value.')}>
      {#snippet children(control)}
        <NumberInput {...control} bind:value={capacity} min={20} max={1200} step={10} stepLabels={stepLabels(t('Server capacity'))} unit={t('req/s')} />
      {/snippet}
    </FormField>
    <FormField label={t('Premium price')}>
      {#snippet children(control)}
        <NumberInput {...control} value={4.99} min={0} step={0.01} stepLabels={stepLabels(t('Premium price'))} unit="USD" />
      {/snippet}
    </FormField>
  </div>
</Story>

<Story name="Slider with manual input">
  <div class="fields">
    <FormField label={t('Traffic allocation')} hint={t('Allocate up to 100% of incoming requests.')}>
      {#snippet children(control)}
        <Slider {...control} name="traffic" bind:value={traffic} min={0} max={100} step={5} manualLabel={t('Exact traffic allocation')} manualStepLabels={stepLabels(t('Traffic allocation'))} unit="%" />
      {/snippet}
    </FormField>
    <FormField label={t('Capacity target')}>
      {#snippet children(control)}<Slider {...control} value={70} min={0} max={100} />{/snippet}
    </FormField>
  </div>
</Story>

<Story name="Select">
  <div class="fields">
    <Form ondata={() => regionSaved = true}>
      <FormField label={t('Region')}>
        {#snippet children(control)}
          <Select {...control} name="region" required placeholder={t('Choose a region')}
            bind:value={selected} onValueChange={() => regionSaved = false} options={[
              { value: 'eu', label: t('Europe') },
              { value: 'na', label: t('North America') },
              { value: 'apac', label: t('Asia Pacific'), disabled: true }
            ]} />
        {/snippet}
      </FormField>
      <div><Button type="submit" variant="primary">{t('Save settings')}</Button></div>
    </Form>
    <output>{regionSaved ? t('Settings saved') : ''}</output>
  </div>
</Story>

<Story name="Checkbox and switch">
  <div class="fields">
    <Checkbox label={t('Select all regions')} bind:indeterminate={mixed} />
    <Checkbox label={t('Include capacity estimates')} checked />
    <Checkbox label={t('Include migration history')} disabled />
    <Switch label={t('Enable monitoring')} description={t('Collect service history for this region.')} checked />
    <Switch label={t('Enable replication')} />
  </div>
</Story>

<Story name="Form submission">
  <div class="fields">
    <Form aria-label={t('Service settings')} ondata={(data) => saved = String(data.get('email'))}>
      <FormField label={t('Email')} hint={t('We use this address for service alerts.')}>
        {#snippet children(control)}
          <TextInput {...control} type="email" name="email" bind:value={email} autocomplete="email" required />
        {/snippet}
      </FormField>
      <Checkbox label={t('Send weekly reports')} name="reports" />
      <div><Button variant="primary" type="submit">{t('Save settings')}</Button></div>
    </Form>
    <output>{saved ? t('Settings saved for {0}.', [saved]) : ''}</output>
  </div>
</Story>

<style>
  .fields { display: grid; gap: var(--sui-space-4); max-inline-size: 29rem; }
  .row { display: flex; flex-wrap: wrap; gap: var(--sui-space-2); }
  output { color: var(--sui-primary); }
</style>
