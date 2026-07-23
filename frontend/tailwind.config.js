/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        navy: {
          DEFAULT: '#0B2545',
          light: '#13345E',
          dark: '#071730',
        },
        teal: {
          DEFAULT: '#0F6E6E',
          light: '#158C8C',
          dark: '#0A4F4F',
        },
        mint: {
          DEFAULT: '#8FE3C6',
          light: '#B4EEDA',
          dark: '#5FCBA4',
        },
        amber: {
          DEFAULT: '#E8A33D',
        },
        coral: {
          DEFAULT: '#E15554',
        },
        slate: {
          bg: '#F5F8F8',
          text: '#1B2430',
          muted: '#5B6675',
        },
      },
      fontFamily: {
        display: ['"Space Grotesk"', 'sans-serif'],
        body: ['"Inter"', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'monospace'],
      },
    },
  },
  plugins: [],
}
