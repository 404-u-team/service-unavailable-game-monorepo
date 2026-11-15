import type { HTMLInputAttributes } from 'svelte/elements';
import type { Snippet } from 'svelte';

export type Tone = 'neutral' | 'success' | 'warning' | 'danger' | 'info';

export type FieldControl = {
  id: string;
  'aria-describedby'?: string;
  'aria-invalid'?: boolean;
};

export type NumberStepLabels = { decrease: string; increase: string };

export type SelectOption = { value: string; label: string; disabled?: boolean };
export type MenuAction = { id: string; label: string; disabled?: boolean; tone?: 'danger'; onSelect: () => void };
export type TabItem = SelectOption;
export type NavItem = { href: string; label: string; current?: boolean };
export type AccordionItem = { id: string; title: string };

export type CheckProps = Omit<HTMLInputAttributes, 'type' | 'checked' | 'children' | 'role' | 'indeterminate'> & {
  label: string;
  description?: string;
  checked?: boolean;
};

export type OverlayProps = {
  open?: boolean;
  title: string;
  description?: string;
  closeLabel: string;
  dismissible?: boolean;
  returnFocus?: HTMLElement;
  children: Snippet;
  footer?: Snippet;
};
