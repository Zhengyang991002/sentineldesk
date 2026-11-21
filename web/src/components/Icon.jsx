// Stroke icons drawn on a 24x24 grid. Add new ones to ICONS and reference them by name.
const ICONS = {
  collapse: ['M11 17l-5-5 5-5', 'M18 17l-5-5 5-5'],
  expand: ['M13 17l5-5-5-5', 'M6 17l5-5-5-5'],
  home: ['M3 11l9-8 9 8', 'M5 10v10h14V10'],
  checks: ['M2 12.5l5 5L17 7', 'M13 16.5l1.5 1.5L22 10'],
  ticket: ['M3 9V6h18v3a3 3 0 0 0 0 6v3H3v-3a3 3 0 0 0 0-6z', 'M14 6v12'],
  db: ['M4 5c0-1.1 3.6-2 8-2s8 .9 8 2-3.6 2-8 2-8-.9-8-2z', 'M4 5v14c0 1.1 3.6 2 8 2s8-.9 8-2V5', 'M4 12c0 1.1 3.6 2 8 2s8-.9 8-2'],
  user: ['M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z', 'M4 21c0-4 3.6-6 8-6s8 2 8 6'],
  clients: ['M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z', 'M2 20c0-3.5 3-5.5 7-5.5s7 2 7 5.5', 'M16 4.5a3.5 3.5 0 0 1 0 6.5', 'M18 15c2.3.6 4 2.2 4 5'],
  selector: ['M8 9l4-4 4 4', 'M8 15l4 4 4-4'],
  chevronDown: ['M6 9l6 6 6-6'],
  close: ['M6 6l12 12M18 6L6 18'],
  newChat: ['M12 20h9', 'M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z'],
  send: ['M5 12h14M13 6l6 6-6 6'],
  copy: ['M9 9h11v11H9z', 'M5 15V5a1 1 0 0 1 1-1h10'],
  check: ['M4 12.5l5 5L20 6.5'],
  refresh: ['M21 12a9 9 0 1 1-3-6.7', 'M21 4v5h-5'],
  search: ['M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16z', 'M21 21l-4.3-4.3'],
  plus: ['M12 5v14', 'M5 12h14'],
}

export default function Icon({ name, size = 20, strokeWidth = 2 }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {ICONS[name].map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  )
}
