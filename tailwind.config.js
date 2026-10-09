/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        appBg: '#ECE2D9',
        maroon: '#662023',
        deep: '#421517',
        deeper: '#3B1117',
        card: '#F9F2EB',
        warmwhite: '#FFF9F3',
        border: '#DCCBBE',
        text: '#33221F',
        muted: '#76645B',
        gold: '#C99A53',
        success: '#3F8061',
        warning: '#B87928',
        danger: '#B33838',
      },
      fontFamily: {
        sans: [
          'Inter',
          'ui-sans-serif',
          'system-ui',
          '-apple-system',
          'Segoe UI',
          'Roboto',
          'Helvetica Neue',
          'Arial',
          'sans-serif',
        ],
        serif: ['Georgia', 'Cambria', 'Times New Roman', 'serif'],
      },
      boxShadow: {
        panel: '0 5px 18px rgba(59,17,23,0.08)',
        soft: '0 2px 8px rgba(59,17,23,0.06)',
      },
    },
  },
  plugins: [],
}
