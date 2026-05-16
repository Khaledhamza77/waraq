# Waraq — Landing Page Design Enhancement Prompt
# Feed this directly to Claude Code

---

Enhance the visual design of the existing landing page at `/`. Do NOT change any copy, structure, routing, or functionality. Only update CSS, styling, and visual presentation. Here is exactly what to change for each element:

---

## 1. Global / Base

- Background: true black `#000000` — not navy, not `#0b0c14`. Pure black.
- Set a single fixed ambient halo layer behind everything (z-index: 0, pointer-events: none):
  - One large radial gradient ellipse: violet `rgba(124, 58, 237, 0.32)` → transparent, positioned top-right, ~70vw wide, blurred 70px
  - A second overlapping radial: magenta `rgba(192, 38, 211, 0.22)` → transparent, slightly lower-right, blurred 90px
  - Both animate with a very slow drift (translate ±4–6%, scale ±4%, 13–18s ease-in-out infinite alternate). This is Finaira's signature moving aurora — it should be barely perceptible, like light breathing.
- All other elements sit at z-index 1+
- Font stack: `'Inter', sans-serif` for all UI. Import from Google Fonts.
- Base text color: `#F0F2FF`
- Direction: `rtl` on `<html>` or the root wrapper

---

## 2. Navbar

- Height: 64px
- Background: `rgba(0, 0, 0, 0.75)` + `backdrop-filter: blur(18px)`
- Border-bottom: `1px solid rgba(255, 255, 255, 0.06)`
- Position: `sticky top-0`, `z-index: 100`
- App name `ورق · waraq`:
  - Font: Inter 600, 20px
  - Color: `#F0F2FF`
  - A small geometric logo mark to the right of the text (since RTL): a simple square rotated 45° (diamond shape), 10×10px, filled with a violet→blue gradient `linear-gradient(135deg, #7C3AED, #2563EB)`
- "ادخل التطبيق" button (go to app):
  - Style: outlined pill — `border-radius: 999px`, `border: 1px solid #C9A84C`, transparent background, color `#C9A84C`
  - Font: Inter 500, 13px
  - Padding: 9px 22px
  - Hover: `background: rgba(201, 168, 76, 0.10)`, subtle gold glow `box-shadow: 0 0 14px rgba(201,168,76,0.2)`
  - Transition: 0.2s ease

---

## 3. Hero Section

- Min-height: 100vh, centered flex column, padding top 64px (navbar offset)
- NO extra background — let the halo show through
- Arabic headline (main title):
  - Font: Inter 700 (or 800 if available), 56–64px, line-height 1.25
  - The word/phrase "المحاسبة المصرية" (or whichever word has the gold accent): color `#C9A84C`, keep the rest `#F0F2FF`
  - Text-align: right (RTL)
  - Max-width: 720px
- Subtitle paragraph:
  - Font: Inter 300, 18px, line-height 1.8
  - Color: `#8A8FAD`
  - Max-width: 560px
- Short horizontal rule accent below the headline (before subtitle):
  - `width: 52px; height: 2px; background: #C9A84C; border: none; margin: 20px 0; margin-right: 0;`
- Primary CTA button "ادخل التطبيق" (in hero):
  - Filled gold pill: `background: #C9A84C`, `color: #000`, `border-radius: 999px`
  - Font: Inter 600, 14px, letter-spacing 0.04em
  - Padding: 14px 32px
  - Hover: `background: #D4B460`, `box-shadow: 0 0 24px rgba(201,168,76,0.35)`
  - Has a small arrow icon (→ or lucide `ArrowLeft` since RTL) inline after text
  - Active: `scale(0.97)`, transition 100ms

---

## 4. Feature Cards Section

- Section padding: 80px 0
- Section label above cards (small, uppercase, muted):
  - "ما الذي يقدمه ورق؟" or similar
  - Font: Inter 500, 11px, letter-spacing 0.12em, color `#4A4F6E`, text-align center
- Cards layout: CSS Grid, 3 columns on desktop, 1 on mobile, gap 20px
- Max-width of grid: 1080px, centered

### Each Card:
- Background: `#0F1020` (very dark, slightly blue-tinted — distinguished from true black bg)
- Border: `1px solid #1C1E35`
- Border-radius: `20px`
- Padding: `32px 28px`
- Position: relative, overflow: hidden
- Subtle corner glow (::before pseudo): radial gradient from card's accent color at 10% opacity, top-right corner, 100px radius, blurred — unique per card:
  - Card 1 (document): violet glow `rgba(124, 58, 237, 0.12)`
  - Card 2 (legal expert): gold glow `rgba(201, 168, 76, 0.12)`
  - Card 3 (citations/verify): cyan glow `rgba(6, 182, 212, 0.10)`
- Hover state: `border-color: #2A2D50`, `transform: translateY(-4px)`, transition 0.25s ease
- Icon container:
  - 44×44px rounded square (`border-radius: 12px`)
  - Card 1: background `rgba(124, 58, 237, 0.15)`, icon color `#8B5CF6`
  - Card 2: background `rgba(201, 168, 76, 0.12)`, icon color `#C9A84C`
  - Card 3: background `rgba(6, 182, 212, 0.12)`, icon color `#22D3EE`
  - Icon: Lucide outline, 22px, strokeWidth 1.5
- Arabic card title:
  - Font: Inter 600, 18px, color `#F0F2FF`, margin-top 16px
- English subtitle:
  - Font: Inter 400, 12px, color `#4A4F6E`, letter-spacing 0.06em, text-transform uppercase, margin-top 4px
- Description text:
  - Font: Inter 400, 14px, color `#7A7F9D`, line-height 1.8, margin-top 12px
- Small bottom link/tag — optional, each card:
  - Font: 11px, card's accent color, with a small → icon
  - Text like "اكتشف أكثر" — purely decorative for now (no routing needed)

---

## 5. Footer

- Background: `rgba(0, 0, 0, 0.6)`
- Border-top: `1px solid #1C1E35`
- Padding: 28px 40px
- Flex row, space-between
- Left side (in RTL = end side): copyright text, Inter 400, 12px, color `#3A3F5C`
- Right side (in RTL = start side): brand mark `ورق · waraq`, Inter 500, 13px, color `#3A3F5C`
- No heavy content — keep it minimal

---

## 6. Spacing & Layout Globals

- Max content width: `1200px`, `margin: 0 auto`, `padding: 0 40px`
- Section vertical rhythm: hero 100vh, cards section ~300px, footer ~80px
- Smooth scroll: `html { scroll-behavior: smooth; }`
- No horizontal overflow

---

## 7. Micro-interactions & Motion

- Halo: drifts slowly, continuous, barely noticeable — don't make it distracting
- Cards: `translateY(-4px)` on hover, `transition: transform 0.25s ease, border-color 0.25s ease`
- Navbar CTA + Hero CTA buttons: `transition: all 0.2s ease`, scale on active
- Page load: no heavy animations — keep it instant and clean
- Scrollbar: custom dark thin scrollbar if possible:
  ```css
  ::-webkit-scrollbar { width: 4px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: #2A2D50; border-radius: 2px; }
  ```

---

## 8. What NOT to change

- All Arabic copy and English subtitles — keep exactly as written
- All routing (`/` and `/app`)
- The 3-card structure and their content
- Any Chainlit or backend integration at `/app`
- Component hierarchy / file structure — just update styles

---

## Summary of color tokens to use throughout:

```
--bg:             #000000
--surface:        #0F1020
--border:         #1C1E35
--border-hover:   #2A2D50
--text-primary:   #F0F2FF
--text-secondary: #8A8FAD
--text-muted:     #4A4F6E
--gold:           #C9A84C
--gold-hover:     #D4B460
--violet:         #7C3AED
--cyan:           #22D3EE
--halo-violet:    rgba(124, 58, 237, 0.32)
--halo-magenta:   rgba(192, 38, 211, 0.22)
```
