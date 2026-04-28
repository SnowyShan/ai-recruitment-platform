/**
 * Logo component — use this everywhere instead of old Sparkles + text pattern.
 *
 * Props:
 *   variant: 'horizontal' (default) | 'icon-only'
 *   theme:   'purple' (default) | 'white' | 'gradient'
 *   size:    'sm' | 'md' (default) | 'lg'
 */
export default function Logo({ variant = 'horizontal', theme = 'purple', size = 'md' }) {
  const heights = { sm: 'h-7', md: 'h-9', lg: 'h-12' };
  const iconSizes = { sm: 'h-6 w-6', md: 'h-8 w-8', lg: 'h-11 w-11' };

  if (variant === 'icon-only') {
    const iconSrc =
      theme === 'white' ? '/logos/svg/icon-mark-white.svg'
      : theme === 'gradient' ? '/logos/svg/icon-gradient.svg'
      : '/logos/svg/icon-purple-on-white.svg';
    return <img src={iconSrc} alt="TalentBridge" className={iconSizes[size]} />;
  }

  // horizontal lockup
  const lockupSrc =
    theme === 'white' ? '/logos/svg/lockup-horizontal-white-on-purple.svg'
    : theme === 'gradient' ? '/logos/svg/lockup-horizontal-gradient.svg'
    : '/logos/svg/lockup-horizontal-purple.svg';

  return <img src={lockupSrc} alt="TalentBridge AI" className={`${heights[size]} w-auto`} />;
}