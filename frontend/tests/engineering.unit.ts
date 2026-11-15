import { expect, test } from 'bun:test';
import { engineeringArticles } from '../src/lib/engineering-guide';
import { engineeringLessons } from '../src/lib/workbench/engineering-lesson';
import { fieldArticle } from '../src/lib/guide';
import russian from '../src/lib/ru.json';

const dictionary: Record<string, string> = russian;
test('all engineering settings and lessons resolve bilingual help', () => {
  expect(Object.keys(engineeringArticles)).toHaveLength(12);
  for (const field of ['role', 'domain', 'partition', 'query_plan', 'autoscale', 'min_instances', 'max_instances', 'target_utilization', 'instances']) {
    const [article, section] = fieldArticle('api', field);
    expect(engineeringArticles[article].sections.some((s) => s.id === section)).toBe(true);
  }
  expect(engineeringLessons).toHaveLength(6);
  for (const lesson of engineeringLessons) {
    expect(dictionary[lesson.title]).toMatch(/[а-яё]/iu);
    expect(dictionary[lesson.text]).toMatch(/[а-яё]/iu);
  }
  for (const article of Object.values(engineeringArticles)) {
    expect(dictionary[article.title]).toMatch(/[а-яё]/iu);
    for (const section of article.sections) for (const text of section.body ?? []) {
      expect(dictionary[text]).toMatch(/[а-яё]/iu);
    }
  }
});
