/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    './index.html',
    './src/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Consolas', 'Monaco', 'monospace'],
      },
      colors: {
        finance: {
          green: '#16a34a',
          gold: '#ca8a04',
        },
        enterprise: {
          primary: '#0ea5e9',
          secondary: '#8b5cf6',
          success: '#10b981',
          warning: '#f59e0b',
          danger: '#ef4444',
        },
      },
      fontWeight: {
        display: '900',
        heading: '700',
        subheading: '600',
        body: '500',
        caption: '400',
      },
    },
  },
  plugins: [],
}
