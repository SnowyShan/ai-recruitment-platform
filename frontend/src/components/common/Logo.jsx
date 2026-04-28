/**
 * Logo component — single source of truth for TalentBridge branding.
 *
 * Props:
 *   variant: 'horizontal' (default) | 'stacked' | 'icon-only'
 *   theme:   'purple' (default) | 'white' | 'gradient'
 *   size:    'sm' | 'md' (default) | 'lg' | 'xl' | '2xl'
 */
export default function Logo({ variant = 'horizontal', theme = 'purple', size = 'md' }) {
  const heights = {
    sm: 'h-7',    // 28px — sidebar, compact headers
    md: 'h-10',   // 40px — mobile headers, standard
    lg: 'h-14',   // 56px — prominent horizontal use
    xl: 'h-20',   // 80px — large horizontal on light bg
    '2xl': 'h-28', // 112px — hero/login panel stacked
  };
  const iconSizes = {
    sm: 'h-6 w-6',
    md: 'h-8 w-8',
    lg: 'h-12 w-12',
    xl: 'h-16 w-16',
    '2xl': 'h-24 w-24',
  };

  if (variant === 'icon-only') {
    const src =
      theme === 'white'    ? '/logos/svg/icon-mark-white.svg'
      : theme === 'gradient' ? '/logos/svg/icon-gradient.svg'
      : '/logos/svg/icon-purple-on-white.svg';
    return <img src={src} alt="TalentBridge" className={iconSizes[size]} />;
  }

  if (variant === 'stacked') {
    const src =
      theme === 'white'    ? '/logos/svg/lockup-stacked-gradient.svg'
      : theme === 'gradient' ? '/logos/svg/lockup-stacked-gradient.svg'
      : '/logos/svg/lockup-stacked-purple.svg';
    // Stacked logos are taller than wide — use width instead of height
    const widths = { sm: 'w-24', md: 'w-32', lg: 'w-40', xl: 'w-52', '2xl': 'w-64' };
    return <img src={src} alt="TalentBridge AI" className={`${widths[size]} h-auto`} />;
  }

  // horizontal lockup (default)
  const src =
    theme === 'white'    ? '/logos/svg/lockup-horizontal-white-on-purple.svg'
    : theme === 'gradient' ? '/logos/svg/lockup-horizontal-gradient.svg'
    : '/logos/svg/lockup-horizontal-purple.svg';

  return <img src={src} alt="TalentBridge AI" className={`${heights[size]} w-auto`} />;
}