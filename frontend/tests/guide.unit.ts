import { expect, test } from 'bun:test';
import { articles, categories, componentArticles, fieldArticle, resourceArticle } from '../src/lib/guide';
import russian from '../src/lib/ru.json';

const dictionary: Record<string, string> = russian;

test('guide navigation and article content resolve in both languages', () => {
  for (const label of Object.values(categories)) expect(dictionary[label]).toBeTruthy();
  for (const [id, article] of Object.entries(articles)) {
    expect(dictionary[article.title], id).toBeTruthy();
    expect(new Set(article.sections.map((section) => section.id)).size).toBe(article.sections.length);
    for (const section of article.sections) {
      for (const text of [section.title, ...(section.body ?? []), section.diagram].filter(Boolean)) {
        expect(dictionary[text!], text).toBeTruthy();
      }
    }
    for (const related of article.related) expect(articles[related], related).toBeDefined();
  }
});

test('component, setting and diagnostic links point to existing sections', () => {
  for (const [kind, article] of Object.entries(componentArticles)) {
    expect(kind).toBe(article.kind ?? '');
    expect(article.sections.map((section) => section.id)).toContain('example');
  }
  const targets = [
    ...['cpu', 'disk', 'memory', 'storage', 'search_index', 'connections'].map((field) => fieldArticle('database', field)),
    ...['CPU', 'Disk I/O', 'RAM', 'Storage', 'Connections', 'Legacy write throttle', 'Replication'].map(resourceArticle)
  ];
  for (const [article, section] of targets) {
    expect(articles[article].sections.some((item) => item.id === section)).toBe(true);
  }
});
