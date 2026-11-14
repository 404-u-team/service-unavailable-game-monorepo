export function spotlightBounds(rect: Pick<DOMRect, 'left' | 'right' | 'top' | 'bottom'>, width: number, height: number) {
  const left = Math.max(0, rect.left - 4);
  const top = Math.max(0, rect.top - 4);
  const right = Math.min(width, rect.right + 4);
  const bottom = Math.min(height, rect.bottom + 4);
  if (rect.right <= 0 || rect.left >= width || rect.bottom <= 0 || rect.top >= height || right <= left || bottom <= top) return;
  return { left, top, width: right - left, height: bottom - top };
}
