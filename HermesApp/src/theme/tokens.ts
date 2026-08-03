/**
 * Hermes design tokens.
 *
 * The look is deliberately quiet: warm off-whites, near-blacks, a refined
 * bronze accent, hairline separators and generous whitespace. Every screen
 * should feel airy — few borders, soft radii, restrained color.
 */

export interface Palette {
  bg: string;
  surface: string;
  /** Slightly raised surface (cards on top of surface). */
  surfaceAlt: string;
  text: string;
  subtle: string;
  accent: string;
  /** Text drawn on top of the accent color. */
  onAccent: string;
  hairline: string;
  danger: string;
  success: string;
  /** Tint used behind the user's chat bubbles. */
  bubbleUser: string;
}

export const lightPalette: Palette = {
  bg: '#FAFAF8',
  surface: '#FFFFFF',
  surfaceAlt: '#F4F3F0',
  text: '#111214',
  subtle: '#6B6E76',
  accent: '#B08D57',
  onAccent: '#FFFFFF',
  hairline: '#E7E5E0',
  danger: '#C0392B',
  success: '#2E7D5B',
  bubbleUser: '#F1EADF',
};

export const darkPalette: Palette = {
  bg: '#0C0C0E',
  surface: '#16161A',
  surfaceAlt: '#1D1D22',
  text: '#F4F4F2',
  subtle: '#9A9DA6',
  accent: '#C9A265',
  onAccent: '#141414',
  hairline: '#26262B',
  danger: '#E06C5B',
  success: '#5BB08C',
  bubbleUser: '#242028',
};

/** 4pt spacing grid. */
export const space = (n: number): number => n * 4;

export const radius = {
  sm: 10,
  md: 14,
  lg: 20,
} as const;

export const type = {
  /**
   * Titles aspire to New York (Apple's serif). "NewYork" resolves on iOS
   * builds where the font is registered; elsewhere RN silently falls back
   * to the system font, which is an acceptable degradation.
   */
  titleFamily: 'NewYork',
  title: 28,
  heading: 20,
  body: 16,
  small: 13,
  micro: 11,
} as const;

export const shadow = {
  soft: {
    shadowColor: '#000',
    shadowOpacity: 0.06,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
    elevation: 2,
  },
} as const;

export interface Theme {
  colors: Palette;
  dark: boolean;
}
