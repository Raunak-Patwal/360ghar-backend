/**
 * Theme utilities for ChatGPT widgets.
 */

import { useTheme } from './bridge';

/**
 * CSS variables for theming.
 */
export const themeColors = {
  light: {
    background: '#ffffff',
    backgroundSecondary: '#f7f7f8',
    text: '#1a1a1a',
    textSecondary: '#666666',
    border: '#e5e5e5',
    primary: '#0066cc',
    primaryHover: '#0052a3',
    success: '#16a34a',
    error: '#dc2626',
    warning: '#f59e0b',
  },
  dark: {
    background: '#1e1e1e',
    backgroundSecondary: '#2d2d2d',
    text: '#ffffff',
    textSecondary: '#a0a0a0',
    border: '#3d3d3d',
    primary: '#3b82f6',
    primaryHover: '#60a5fa',
    success: '#22c55e',
    error: '#ef4444',
    warning: '#fbbf24',
  },
} as const;

/**
 * Hook to get theme-aware colors.
 */
export function useThemeColors() {
  const theme = useTheme();
  return themeColors[theme];
}

/**
 * Get CSS styles for the current theme.
 */
export function getThemeStyles(theme: 'light' | 'dark'): React.CSSProperties {
  const colors = themeColors[theme];
  return {
    backgroundColor: colors.background,
    color: colors.text,
  };
}
