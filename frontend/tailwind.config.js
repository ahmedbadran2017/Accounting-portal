/** @type {import('tailwindcss').Config} */
// JoyAgent Books design tokens (see design_handoff_joyagent_books/README.md).
export default {
  content: ["./index.html", "./src/**/*.{vue,js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Inter"', "system-ui", "-apple-system", "sans-serif"],
        arabic: ['"Alexandria"', "system-ui", "-apple-system", "sans-serif"],
      },
      colors: {
        // Atlas palette — deep teal primary (trust / numbers), terracotta brand.
        accent: { DEFAULT: "#0f766e", dark: "#0b5c4f", soft: "#e7f4f1" },
        brand: { DEFAULT: "#c2562f", dark: "#9a3d1e", soft: "#fbf2ee" },
        ink: { DEFAULT: "#1c1917", 2: "#57534e", 3: "#78716c", muted: "#a8a29e" },
        // app surfaces / borders
        app: { bg: "#f3f1ef", warm: "#faf6f4", warm2: "#fafaf9" },
        line: { DEFAULT: "#f0efed", 2: "#e7e5e4", hair: "#f4f2f0" },
        // semantic
        sale: "#c4301c",
        success: { DEFAULT: "#1f9d55", dark: "#047857" },
        info: "#0369a1",
        violet: "#7c3aed",
      },
      borderRadius: { card: "15px", chip: "9px", badge: "6px" },
      boxShadow: {
        card: "0 1px 2px rgba(28,25,23,.04)",
        cardHover: "0 4px 10px rgba(28,25,23,.05),0 18px 40px -16px rgba(28,25,23,.20)",
        prim: "0 2px 8px rgba(15,118,110,.26),0 1px 2px rgba(15,118,110,.18)",
        brand: "0 2px 8px rgba(194,86,47,.28),0 1px 2px rgba(194,86,47,.18)",
        modal: "0 24px 64px -16px rgba(28,25,23,.4)",
      },
      keyframes: {
        barGrow: { "0%": { transform: "scaleY(0)" }, "100%": { transform: "scaleY(1)" } },
        fadeIn: { "0%": { opacity: "0" }, "100%": { opacity: "1" } },
        modalIn: {
          "0%": { opacity: "0", transform: "translateY(8px) scale(.98)" },
          "100%": { opacity: "1", transform: "translateY(0) scale(1)" },
        },
      },
      animation: {
        barGrow: "barGrow .7s cubic-bezier(.3,1,.3,1) both",
        fadeIn: "fadeIn .25s ease both",
        modalIn: "modalIn .18s cubic-bezier(.34,1.56,.64,1) both",
      },
    },
  },
  plugins: [],
};
