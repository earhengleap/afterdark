/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        dark: {
          DEFAULT: '#111111',
          card: '#1a1a1a',
          elevated: '#222222',
          border: '#2a2a2a',
          bg: '#0d0d0d',
        },
        accent: {
          DEFAULT: '#ffffff',
          hover: '#e5e5e5',
          glow: 'rgba(255,255,255,0.15)',
          muted: 'rgba(255,255,255,0.08)',
        },
        text: {
          primary: '#ffffff',
          secondary: '#aaaaaa',
          muted: '#555555',
        },
        success: '#22c55e',
        error:   '#ef4444',
        warning: '#f59e0b',
        info:    '#3b82f6',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      fontSize: {
        '2xs': ['0.625rem', { lineHeight: '0.875rem' }],
      },
      animation: {
        'fadeIn':        'fadeIn 0.25s ease-out forwards',
        'slideUp':       'slideUp 0.3s ease-out forwards',
        'shimmer':       'shimmer 1.2s infinite linear',
        'slide-in-right':'slideInRight 0.3s ease-out forwards',
        'slide-out-right':'slideOutRight 0.25s ease-in forwards',
        'typing':        'typing 1.2s ease-in-out infinite',
        'spin-slow':     'spin 3s linear infinite',
      },
      keyframes: {
        fadeIn:       { '0%': { opacity:'0' }, '100%': { opacity:'1' } },
        slideUp:      { '0%': { opacity:'0', transform:'translateY(16px)' }, '100%': { opacity:'1', transform:'translateY(0)' } },
        shimmer:      { '0%': { backgroundPosition:'200% 0' }, '100%': { backgroundPosition:'-200% 0' } },
        slideInRight: { '0%': { opacity:'0', transform:'translateX(100%)' }, '100%': { opacity:'1', transform:'translateX(0)' } },
        slideOutRight:{ '0%': { opacity:'1', transform:'translateX(0)' }, '100%': { opacity:'0', transform:'translateX(100%)' } },
        typing:       { '0%,60%,100%': { transform:'translateY(0)', opacity:'0.4' }, '30%': { transform:'translateY(-6px)', opacity:'1' } },
      },
      boxShadow: {
        'glow-sm':   '0 0 10px rgba(255,144,0,0.20)',
        'glow':      '0 0 20px rgba(255,144,0,0.30)',
        'glow-lg':   '0 0 40px rgba(255,144,0,0.40)',
        'card':      '0 2px 12px rgba(0,0,0,0.5)',
        'card-hover':'0 4px 24px rgba(0,0,0,0.7)',
      },
      borderRadius: {
        'xl': '0.75rem',
        '2xl': '1rem',
      },
      transitionTimingFunction: {
        'spring': 'cubic-bezier(0.16, 1, 0.3, 1)',
      },
      screens: {
        'xs': '375px',
        '3xl': '1920px',
      },
    },
  },
  plugins: [],
}
