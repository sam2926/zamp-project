/** Inline icons. Status is never carried by colour alone, so several of these
 *  travel with a status chip as its second channel. */

type Props = { size?: number }

const base = (size: number) => ({
  width: size,
  height: size,
  viewBox: '0 0 16 16',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.6,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  'aria-hidden': true,
})

export const CheckIcon = ({ size = 14 }: Props) => (
  <svg {...base(size)}>
    <path d="M3 8.5l3.2 3.2L13 5" />
  </svg>
)

export const AlertIcon = ({ size = 14 }: Props) => (
  <svg {...base(size)}>
    <path d="M8 2.8L14.4 13.6H1.6z" />
    <path d="M8 6.6v3" />
    <path d="M8 11.6h.01" />
  </svg>
)

export const WrenchIcon = ({ size = 14 }: Props) => (
  <svg {...base(size)}>
    <path d="M10.4 2.2a3.6 3.6 0 00-4.6 4.4L2.3 10a1.4 1.4 0 002 2l3.4-3.5a3.6 3.6 0 004.4-4.6L10.2 6 9 4.8z" />
  </svg>
)

export const MissingIcon = ({ size = 14 }: Props) => (
  <svg {...base(size)}>
    <circle cx="8" cy="8" r="6" />
    <path d="M5.6 5.6l4.8 4.8" />
  </svg>
)

export const UploadIcon = ({ size = 16 }: Props) => (
  <svg {...base(size)}>
    <path d="M8 11V3" />
    <path d="M4.8 6.2L8 3l3.2 3.2" />
    <path d="M2.6 11.4v1.2a1.4 1.4 0 001.4 1.4h8a1.4 1.4 0 001.4-1.4v-1.2" />
  </svg>
)

export const InboxIcon = ({ size = 16 }: Props) => (
  <svg {...base(size)}>
    <path d="M2 9.5h3l1 2h4l1-2h3" />
    <path d="M3.4 3h9.2l1.4 6.5v3a1 1 0 01-1 1H3a1 1 0 01-1-1v-3z" />
  </svg>
)

export const PlugIcon = ({ size = 16 }: Props) => (
  <svg {...base(size)}>
    <path d="M6 2v3M10 2v3" />
    <path d="M4.4 5h7.2v3.2A3.6 3.6 0 018 11.8a3.6 3.6 0 01-3.6-3.6z" />
    <path d="M8 11.8V14" />
  </svg>
)

export const FileIcon = ({ size = 16 }: Props) => (
  <svg {...base(size)}>
    <path d="M9.2 1.8H4.4a1 1 0 00-1 1v10.4a1 1 0 001 1h7.2a1 1 0 001-1V5.2z" />
    <path d="M9.2 1.8v3.4h3.4" />
  </svg>
)
