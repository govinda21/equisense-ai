/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    './index.html',
    './src/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        finance: {
          green: '#16a34a',
          gold: '#ca8a04',
        },
      },
    },
  },
  plugins: [],
}
