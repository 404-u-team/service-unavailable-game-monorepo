import { ApiError } from './api';
import russian from './ru.json';

export type Language = 'en' | 'ru';
let language = $state<Language>('en');
const dictionary: Record<string, string> = russian;

export function locale() { return language; }

export function setLanguage(value: Language) {
  language = value;
  if (typeof window !== 'undefined') {
    localStorage.setItem('workbench-language', value);
    document.documentElement.lang = value;
  }
}

export function t(message: string, args: readonly unknown[] = []) {
  const translated = language === 'ru' ? dictionary[message] ?? message : message;
  return args.length ? translated.replace(/\{(\d+)\}/g, (match, index) => String(args[Number(index)] ?? match)) : translated;
}

export function count(n: number, one: string, other: string, ru: [string, string, string]) {
  const plural = new Intl.PluralRules(language).select(n);
  const word = language === 'ru' ? ru[plural === 'one' ? 0 : plural === 'few' ? 1 : 2] : plural === 'one' ? one : other;
  return `${new Intl.NumberFormat(language).format(n)} ${word}`;
}

const matches: [RegExp, string][] = [
  [/^Deployed (\d+) infrastructure changes$/, 'Deployed infrastructure changes: {0}'],
  [/^(.+) cannot connect to (.+)\.$/, '{0} cannot connect to {1}.'],
  [/^(.+) has an unknown setting: (.+)\.$/, '{0} has an unknown setting: {1}.'],
  [/^(.+): invalid value for (.+)\.$/, '{0}: invalid value for {1}.'],
  [/^(.+) can replicate from one primary database\.$/, '{0} can replicate from one primary database.'],
  [/^Remove (.+) and add a new component to change its type\.$/, 'Remove {0} and add a new component to change its type.'],
  [/^(.+) is disconnected and will still incur operating costs\.$/, '{0} is disconnected and will still incur operating costs.'],
  [/^(.+) has no route for writes\.$/, '{0} has no route for writes.'],
  [/^(.+) has no write path\. Route traffic to an API with a direct connection to a primary database\.$/, '{0} has no write path. Route traffic to an API with a direct connection to a primary database.'],
  [/^(.+) cannot serve cache misses without a data connection\.$/, '{0} cannot serve cache misses without a data connection.'],
  [/^(.+) needs a connection to a primary database\.$/, '{0} needs a connection to a primary database.'],
  [/^(.+) has multiple primary links\. Only the first by component ID serves its dataset\.$/, '{0} has multiple primary links. Only the first by component ID serves its dataset.'],
  [/^(.+) has no worker\. Its backlog will build up\.$/, '{0} has no worker. Its backlog will build up.'],
  [/^(.+) campaign started$/, '{0} campaign started'],
  [/^(.+) campaign completed$/, '{0} campaign completed'],
  [/^(.+) released$/, '{0} released'],
  [/^(.+) disabled$/, '{0} disabled'],
  [/^(.+) enabled$/, '{0} enabled'],
  [/^Connect the required infrastructure: (.+)\.$/, 'Connect the required infrastructure: {0}.'],
  [/^This action costs (.+)\. Available balance is (.+)\.$/, 'This action costs {0}. Available balance is {1}.'],
  [/^(.+) has no monitoring links\.$/, '{0} has no monitoring links.'],
  [/^(.+) has more monitoring links than available slots\.$/, '{0} has more monitoring links than available slots.'],
  [/^(.+) campaign has ended$/, '{0} campaign completed'],
];

export function message(message: string): string {
  if (language === 'en') return message;
  for (const [pattern, key] of matches) {
    const result = pattern.exec(message);
    if (result) return t(key, result.slice(1).map((value) => t(value)));
  }
  return t(message);
}

const errorKeys: Record<string, string> = {
  incompatible_connection: '{0} cannot connect to {1}.',
  invalid_setting: '{0}: invalid value for {1}.',
  duplicate_connection: 'A connection already exists between these components.',
  connection_cycle: 'Connections cannot form a cycle.',
  multiple_primaries: '{0} can replicate from one primary database.',
  feature_infrastructure_missing: 'Production infrastructure does not meet the release requirements.',
  feature_not_ready: 'This feature is not ready for that action.',
  missing_write_path: 'Connect traffic to an API server, then connect that API directly to a primary database to handle writes.',
  invalid_values: 'Some submitted values are invalid.',
  save_not_found: 'Save not found.',
  save_file_json: 'The selected file is not a valid JSON save.',
  save_file_invalid: 'This save file is incomplete or contains invalid game data.',
  save_file_version: 'This save file version is unsupported.',
  save_file_too_large: 'The save file is larger than 8 MB.',
  request_id_conflict: 'This request ID was already used for a different action.',
  revision_conflict: 'The architecture changed in another session. Reload the latest draft and retry.',
  upstream_unavailable: 'The game server is unavailable. Try again shortly.',
  incompatible_catalog: 'The game server returned an incompatible catalog. Check the API address and rebuild the API container, then retry.'
};

export function apiMessage(error: unknown): string {
  if (error instanceof ApiError && error.code && errorKeys[error.code]) {
    return t(errorKeys[error.code], error.values.map((value) => t(value)));
  }
  return message(error instanceof Error ? error.message : 'The request could not be completed.');
}
