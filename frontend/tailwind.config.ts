import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#f5f7ff",
          100: "#e9edff",
          200: "#d5dcff",
          300: "#bcc8ff",
          400: "#97a8ff",
          500: "#6b86ff",
          600: "#4f67ff",
          700: "#3d52d9",
          800: "#2f3cae",
          900: "#252c86",
        },
      },
    },
  },
  plugins: [],
} satisfies Config;

