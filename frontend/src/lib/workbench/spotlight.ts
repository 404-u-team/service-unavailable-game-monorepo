type Box = Pick<DOMRect, 'left' | 'right' | 'top' | 'bottom'>;
const inset = 10;

export function viewport(): Box {
  const view = window.visualViewport;
  const left = view?.offsetLeft ?? 0;
  const top = view?.offsetTop ?? 0;
  return { left, top, right: left + (view?.width ?? document.documentElement.clientWidth),
    bottom: top + (view?.height ?? document.documentElement.clientHeight) };
}

export function intersection(a: Box, b: Box): Box {
  return { left: Math.max(a.left, b.left), top: Math.max(a.top, b.top),
    right: Math.min(a.right, b.right), bottom: Math.min(a.bottom, b.bottom) };
}

function scrollBox(element: HTMLElement): Box {
  const rect = element.getBoundingClientRect();
  const left = rect.left + element.clientLeft;
  const top = rect.top + element.clientTop;
  return { left, top, right: left + element.clientWidth, bottom: top + element.clientHeight };
}

export function openDialog() {
  return [...document.querySelectorAll<HTMLDialogElement>('dialog[open]')].at(-1);
}

export function findTarget(key: string | undefined, dialog?: HTMLDialogElement) {
  if (!key) return;
  const root = dialog ?? document;
  return [...root.querySelectorAll<HTMLElement>(`[data-tutorial="${key}"]`)]
    .find((node) => node.getClientRects().length && getComputedStyle(node).visibility === 'visible' && !node.closest('[inert]'));
}

function obstructions(node: HTMLElement, area: Box, scope?: HTMLElement): Box {
  let { top, bottom } = area;
  const root = scope ?? document;
  for (const item of root.querySelectorAll<HTMLElement>('[data-tutorial-obstruction]')) {
    if (item.contains(node) || (scope ? item.closest('dialog, [data-tutorial-scroll]') !== scope
      : item.closest('dialog, [data-tutorial-scroll]'))) continue;
    const box = item.getBoundingClientRect();
    if (!box.width || !box.height || box.left >= area.right || box.right <= area.left) continue;
    if (item.dataset.tutorialObstruction === 'top' && box.top <= area.top + 2 && box.bottom > top) top = box.bottom;
    if (item.dataset.tutorialObstruction === 'bottom' && box.bottom >= area.bottom - 2 && box.top < bottom) bottom = box.top;
  }
  return { ...area, top, bottom };
}

function ancestors(node: HTMLElement, dialog?: HTMLDialogElement) {
  if (node === dialog) return [];
  const result: { element: HTMLElement; clipX: boolean; clipY: boolean; scrollX: boolean; scrollY: boolean }[] = [];
  for (let parent = node.parentElement; parent && parent !== document.body; parent = parent.parentElement) {
    const { overflowX, overflowY } = getComputedStyle(parent);
    const clipX = /auto|scroll|hidden|clip/.test(overflowX);
    const clipY = /auto|scroll|hidden|clip/.test(overflowY);
    if (clipX || clipY) result.push({ element: parent, clipX, clipY,
      scrollX: /auto|scroll/.test(overflowX) && parent.scrollWidth > parent.clientWidth,
      scrollY: /auto|scroll/.test(overflowY) && parent.scrollHeight > parent.clientHeight });
    if (parent === dialog) break;
  }
  return result;
}

function scrollOffset(start: number, end: number, min: number, max: number) {
  if (start >= min && end <= max) return 0;
  if (end - start >= max - min) return start - min;
  return (start + end - min - max) / 2;
}

export function revealTarget(node: HTMLElement, dialog?: HTMLDialogElement) {
  const view = viewport();
  for (const { element, scrollX, scrollY } of ancestors(node, dialog)) {
    if ((!scrollX && !scrollY) || element === document.scrollingElement) continue;
    const area = obstructions(node, scrollBox(element), element);
    const rect = node.getBoundingClientRect();
    const left = scrollX ? scrollOffset(rect.left, rect.right, area.left + inset, area.right - inset) : 0;
    const top = scrollY ? scrollOffset(rect.top, rect.bottom, area.top + inset, area.bottom - inset) : 0;
    if (left || top) element.scrollBy({ left, top, behavior: 'instant' });
  }
  if (dialog || node.closest('[data-tutorial-obstruction]')) return;
  const safe = obstructions(node, view);
  const rect = node.getBoundingClientRect();
  const left = scrollOffset(rect.left, rect.right, safe.left + inset, safe.right - inset);
  const top = scrollOffset(rect.top, rect.bottom, safe.top + inset, safe.bottom - inset);
  if (left || top) window.scrollBy({ left, top, behavior: 'instant' });
}

export function spotlightBounds(rect: Box, clip: Box, padding = 5): Box | undefined {
  const clipped = intersection(clip, rect);
  if (clipped.right <= clipped.left || clipped.bottom <= clipped.top) return;
  return intersection(clip, {
    left: clipped.left - padding, right: clipped.right + padding,
    top: clipped.top - padding, bottom: clipped.bottom + padding
  });
}

export function visibleTarget(node: HTMLElement, dialog?: HTMLDialogElement): Box | undefined {
  let box = dialog ? viewport() : obstructions(node, viewport());
  for (const { element, clipX, clipY } of ancestors(node, dialog)) {
    if (element === document.scrollingElement) continue;
    const area = obstructions(node, scrollBox(element), element);
    box = intersection(box, {
      left: clipX ? area.left : box.left, right: clipX ? area.right : box.right,
      top: clipY ? area.top : box.top, bottom: clipY ? area.bottom : box.bottom
    });
  }
  const rect = node.getBoundingClientRect();
  const clipped = intersection(box, rect);
  const width = clipped.right - clipped.left;
  const height = clipped.bottom - clipped.top;
  if (width < Math.min(24, rect.width * .65) || height < Math.min(24, rect.height * .65) || width <= 0 || height <= 0) return;
  const hit = document.elementFromPoint(clipped.left + width / 2, clipped.top + height / 2);
  if (!node.contains(hit) && !hit?.closest('[data-spotlight-ui]')) return;
  return spotlightBounds(rect, box);
}

export function placeTooltip(view: Box, hole: Box | undefined, width: number, height: number, keepClear?: Box) {
  const safe = { left: view.left + inset, top: view.top + inset, right: view.right - inset, bottom: view.bottom - inset };
  if (keepClear) safe.bottom = Math.min(safe.bottom, keepClear.top - inset);
  const clamp = (value: number, min: number, max: number) => Math.min(Math.max(min, max), Math.max(min, value));
  const alignX = (value: number) => clamp(value, safe.left, safe.right - width);
  const alignY = (value: number) => clamp(value, safe.top, safe.bottom - height);
  const bottom = { x: alignX(safe.right - width), y: alignY(safe.bottom - height), maxHeight: safe.bottom - safe.top };
  if (!hole) return bottom;

  const gap = 10;
  const x = alignX((hole.left + hole.right - width) / 2);
  const y = alignY(hole.top);
  const above = hole.top - safe.top - gap;
  const below = safe.bottom - hole.bottom - gap;
  if (height <= below) return { ...bottom, x, y: hole.bottom + gap };
  if (height <= above) return { ...bottom, x, y: hole.top - gap - height };
  if (hole.right + gap + width <= safe.right) return { ...bottom, x: hole.right + gap, y };
  if (hole.left - gap - width >= safe.left) return { ...bottom, x: hole.left - gap - width, y };
  if (Math.max(above, below) > 0) {
    return below >= above
      ? { x, y: hole.bottom + gap, maxHeight: below }
      : { x, y: Math.max(safe.top, hole.top - gap - height), maxHeight: above };
  }
  return bottom;
}
