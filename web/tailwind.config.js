/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        navy:    "#1B2A5C",
        saffron: "#F28C28",
        light:   "#F4F6FB",
        ink:     "#1F2937",
      },
      fontFamily: {
        sans: ["Inter", "Noto Sans Devanagari", "sans-serif"],
      },
    },
  },
  plugins: [],
};
