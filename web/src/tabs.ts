/** The sections, declared once.
 *
 * Both the landing's cinematic pills and the tab bar on every other page read
 * from this list, so changing or adding a tab is a single edit here.
 *
 * Order matters: this array is rendered left to right, and
 * "Future optimizations" is required to stay last. Add new tabs before it.
 */
export interface Tab {
  id: string
  label: string
  path: string
}

export const TABS: Tab[] = [
  { id: 'upload', label: 'Upload', path: '/upload' },
  { id: 'live', label: 'Live progress', path: '/live' },
  { id: 'process', label: 'Process', path: '/process' },
  { id: 'accuracy', label: 'Accuracy', path: '/dashboard' },
  { id: 'heatmaps', label: 'Heat maps', path: '/heatmaps' },
  // Hidden from the nav for now while the content is still being reviewed. The
  // page and its /future route are unchanged and still reachable by URL —
  // uncomment to restore the button (must stay rightmost).
  // { id: 'future', label: 'Future optimizations', path: '/future' },
]
