/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          950: '#020617', // Deep Navy (audio waveform, dark terminal surfaces)
          900: '#0F172A', // Primary Navy (sidebar background, authority headers)
          850: '#131D36',
          800: '#1E293B',
          700: '#334155',
        },
        teal: {
          DEFAULT: '#0D9488', // Primary Teal
          hover: '#0B7A70',
          50: '#F0FDFA',
          100: '#CCFBF1',
          200: '#99F6E4',
          500: '#14B8A6',
          600: '#0D9488',
          700: '#0F766E',
          800: '#115E59',
          900: '#134E4A',
        },
        brand: {
          blue: '#2563EB', // Secondary Blue
          blueHover: '#1D4ED8',
          teal: '#0D9488', // Primary Teal
          tealHover: '#0B7A70',
          lightBlue: '#38BDF8',
          navy: '#0F172A',
          deepNavy: '#020617',
        },
        clinical: {
          bg: '#F8FAFC',
          card: '#FFFFFF',
          border: '#E2E8F0',
          borderSubtle: '#F1F5F9',
          subtle: '#F1F5F9',
          muted: '#64748B',
          draftBg: '#FEF3C7',
          draftBorder: '#FDE68A',
          draftText: '#92400E',
          reviewedBg: '#DCFCE7',
          reviewedBorder: '#86EFAC',
          reviewedText: '#166534',
          sourceDictatedBg: '#EFF6FF',
          sourceDictatedBorder: '#BFDBFE',
          sourceDictatedText: '#1E40AF',
          sourcePresetBg: '#F0FDF4',
          sourcePresetBorder: '#BBF7D0',
          sourcePresetText: '#166534',
          sourceOcrBg: '#ECFEFF',
          sourceOcrBorder: '#A5F3FC',
          sourceOcrText: '#0E7490',
          sourceManualBg: '#FAF5FF',
          sourceManualBorder: '#E9D5FF',
          sourceManualText: '#6B21A8',
        }
      },
      boxShadow: {
        'xs': '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
        'clinical': '0 1px 3px 0 rgba(15, 23, 42, 0.08), 0 1px 2px -1px rgba(15, 23, 42, 0.04)',
        'modal': '0 20px 25px -5px rgba(15, 23, 42, 0.15), 0 8px 10px -6px rgba(15, 23, 42, 0.1)',
      }
    },
  },
  plugins: [],
}
