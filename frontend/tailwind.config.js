/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{html,ts}'],
  theme: {
    extend: {
      fontFamily: { sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'] },
      colors: {
        navy: { 950: '#0a1627', 900: '#102039', 800: '#183151', 700: '#24486e' },
        brand: { 50: '#f1f7fc', 100: '#e1eef8', 500: '#518ac1', 600: '#3975ae', 700: '#2d6092' },
        accent: { 400: '#43c6b0', 500: '#25aa96' }
      },
      boxShadow: { panel: '0 12px 32px rgba(25, 51, 84, .06)' }
    }
  },
  plugins: []
};
