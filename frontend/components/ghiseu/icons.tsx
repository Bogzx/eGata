import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function svg(size: number, children: React.ReactNode, props: Omit<IconProps, "size">) {
  const { width = size, height = size, ...rest } = props;
  return (
    <svg
      width={width}
      height={height}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      {children}
    </svg>
  );
}

export const MicIcon = ({ size = 20, ...p }: IconProps) =>
  svg(size, <>
    <rect x="9" y="3" width="6" height="12" rx="3" />
    <path d="M5 11a7 7 0 0014 0M12 18v3" />
  </>, p);

export const MicOffIcon = ({ size = 20, ...p }: IconProps) =>
  svg(size, <>
    <line x1="3" y1="3" x2="21" y2="21" />
    <path d="M9 9v3a3 3 0 005.12 2.12M15 9.34V6a3 3 0 00-5.94-.6" />
    <path d="M19 10v2a7 7 0 01-.11 1.23M5 10v2a7 7 0 0012 5" />
    <line x1="12" y1="19" x2="12" y2="22" />
  </>, p);

export const RefreshIcon = ({ size = 18, ...p }: IconProps) =>
  svg(size, <>
    <path d="M3 12a9 9 0 0 1 15.5-6.3L21 8" />
    <path d="M21 3v5h-5" />
    <path d="M21 12a9 9 0 0 1-15.5 6.3L3 16" />
    <path d="M3 21v-5h5" />
  </>, p);

export const StopIcon = ({ size = 20, ...p }: IconProps) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="currentColor"
    aria-hidden="true"
    focusable="false"
    {...p}
  >
    <rect x="7" y="5" width="3.5" height="14" rx="1" />
    <rect x="13.5" y="5" width="3.5" height="14" rx="1" />
  </svg>
);

export const CheckIcon = ({ size = 24, ...p }: IconProps) =>
  svg(size, <path d="M5 12l5 5L20 7" />, { ...p, strokeWidth: 2.4 });

export const EditIcon = ({ size = 22, ...p }: IconProps) =>
  svg(size, <>
    <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
    <path d="M18.5 2.5a2.12 2.12 0 113 3L12 15l-4 1 1-4 9.5-9.5z" />
  </>, p);

export const MailIcon = ({ size = 24, ...p }: IconProps) =>
  svg(size, <>
    <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
    <polyline points="22,6 12,13 2,6" />
  </>, p);

export const CityIcon = ({ size = 24, ...p }: IconProps) =>
  svg(size, <>
    <path d="M3 21h18" />
    <path d="M5 21V8l5-4 5 4v13" />
    <path d="M15 21v-7h4v7" />
    <path d="M9 14h2" />
    <path d="M9 18h2" />
  </>, p);

export const AlertIcon = ({ size = 40, ...p }: IconProps) =>
  svg(size, <>
    <circle cx="12" cy="12" r="10" />
    <line x1="12" y1="8" x2="12" y2="12" />
    <line x1="12" y1="16" x2="12.01" y2="16" />
  </>, p);

export const MicSlashIcon = ({ size = 40, ...p }: IconProps) =>
  svg(size, <>
    <line x1="3" y1="3" x2="21" y2="21" />
    <path d="M9 9v3a3 3 0 005.12 2.12M15 9.34V6a3 3 0 00-5.94-.6" />
    <path d="M19 10v2a7 7 0 01-.11 1.23M5 10v2a7 7 0 0012 5" />
    <line x1="12" y1="19" x2="12" y2="22" />
  </>, p);

export const LogoIcon = ({ size = 20, ...p }: IconProps) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="#EEEEEE"
    strokeWidth={2.4}
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
    focusable="false"
    {...p}
  >
    <path d="M3 11l9-7 9 7" />
    <path d="M5 10v9h14v-9" />
    <path d="M10 19v-5h4v5" />
  </svg>
);
