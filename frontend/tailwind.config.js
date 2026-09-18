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
        // Status tones. These eight pairs were written inline, as
        // style="background:#fffbeb;color:#b45309", 169 distinct hex literals
        // across the components and the commonest repeated 261 times. Same
        // meaning, slightly different colour, everywhere. Named once here.
        tone: {
          good: "#047857", goodbg: "#ecfdf5", goodline: "#a7f3d0",
          warn: "#b45309", warnbg: "#fffbeb", warnline: "#fde68a",
          bad: "#b91c1c", badbg: "#fef2f2", badline: "#fecaca",
          info: "#0369a1", infobg: "#eff6ff", infoline: "#bfdbfe",
          calm: "#6d28d9", calmbg: "#f5f3ff", calmline: "#ddd6fe",
          mute: "#57534e", mutebg: "#fafaf9", muteline: "#e7e5e4",
        },
        // semantic
        sale: "#c4301c",
        success: { DEFAULT: "#1f9d55", dark: "#047857" },
        info: "#0369a1",
        violet: "#7c3aed",
      },
      // Six steps instead of fourteen. The old scale ran 9, 9.5, 10, 10.5, 11,
      // 11.5, 12, 12.5, 13, 14… — differences nobody can see, so they carried no
      // hierarchy, only noise. And its centre of gravity was 10–11px, which is
      // small for people reading figures all day. The floor is 11px now.
      fontSize: {
        micro: ["11px", { lineHeight: "1.45" }],   // labels, table headers, hints
        small: ["12px", { lineHeight: "1.5" }],    // secondary text
        base2: ["13px", { lineHeight: "1.55" }],   // body, table cells, inputs
        lead: ["14px", { lineHeight: "1.5" }],     // emphasis, card titles
        title: ["16px", { lineHeight: "1.4" }],    // section titles
        display: ["22px", { lineHeight: "1.25" }], // figures that carry the page
      },
      borderRadius: { card: "15px", chip: "9px", badge: "6px" },
      boxShadow: {
        card: "0 1px 2px rgba(28,25,23,.04)",
        cardHover: "0 4px 10px rgba(28,25,23,.05),0 18px 40px -16px rgba(28,25,23,.20)",
        // Filled buttons used to carry a coloured halo — an 8px teal or
        // terracotta bloom under every one of them, 62 buttons across the app.
        // Stacked in a toolbar it reads as vibration, not depth. A filled
        // button is already the loudest thing on the row; the glow was volume
        // on top of volume. What is left is a hairline of real shadow: enough
        // to seat the button on the surface, not enough to notice.
        prim: "0 1px 1px rgba(28,25,23,.07)",
        brand: "0 1px 1px rgba(28,25,23,.07)",
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
