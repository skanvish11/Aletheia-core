const paths = {
  search: 'M20.5 20.5 16 16 M18 10.5a7.5 7.5 0 1 1-15 0 7.5 7.5 0 0 1 15 0',
  external: 'M14 4h6v6m0-6-10 10 M10 5H6a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-4',
  enter: 'M19 5v8a2 2 0 0 1-2 2H5m5-5-5 5 5 5',
  back: 'M19 12H5m6-6-6 6 6 6',
  chevron: 'm7 10 5 5 5-5',
  planet: 'M19 12a7 7 0 1 1-14 0 7 7 0 0 1 14 0 M5.2 11C.8 14.3.7 17.4 4 17.6c3.8.3 12.2-3.1 16-7.1 3.1-3.2 1.6-4.9-2.2-4',
  wave: 'M2 12h3l2.4-6 3.7 12 3.4-15 2.8 11 1.5-2H22',
  heart: 'M12 20 4.2 12.5C-1 6.8 6.5.8 12 7c5.5-6.2 13-.2 7.8 5.5Z',
  globe: 'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0 M3 12h18 M12 3c-5.5 5.5-5.5 12.5 0 18 5.5-5.5 5.5-12.5 0-18Z',
  info: 'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0 M12 11v5m0-9v.5',
  fingerprint: 'M3.5 12a8.5 8.5 0 0 1 17 0c0 2.5-.2 4.1-.6 5.7 M4.2 17c.9-1.3 1.6-3 1.6-5a6.2 6.2 0 0 1 12.4 0c0 3.9-.7 6.7-1.9 8.9 M6.1 20.1c1.7-2.3 2.6-5 2.6-8.1a3.3 3.3 0 1 1 6.6 0c0 4-.8 7.3-2.3 10 M9.4 21.9c1.7-3.2 2.6-6.3 2.6-10',
}
export type IconName = keyof typeof paths
export function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.55" strokeLinecap="round" strokeLinejoin="round"><path d={paths[name]} /></svg>
}
