import { QuartzComponent, QuartzComponentConstructor } from "./types"
// @ts-ignore  bundled as client-side script
import script from "./scripts/radialWheel.inline"

const style = `
.radial-wheel { margin: 1.5rem auto; }

/* ---- circular layout (wide screens) ---- */
.rw-stage {
  position: relative;
  width: 100%;
  max-width: 620px;
  margin: 0 auto;
}
.rw-stage::before { content: ""; display: block; padding-bottom: 100%; } /* square */
.rw-ring {
  position: absolute; inset: 0;
  border-radius: 50%;
  border: 1px dashed var(--lightgray);
  background:
    radial-gradient(circle at center, var(--highlight) 0%, transparent 62%);
}
.rw-center {
  position: absolute; left: 50%; top: 50%;
  transform: translate(-50%, -50%);
  width: 30%; height: 30%;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  text-align: center;
  border-radius: 50%;
  background: var(--light);
  border: 1px solid var(--lightgray);
  box-shadow: 0 4px 18px rgba(120,90,60,0.12);
}
.rw-center-title { font-family: var(--headerFont); font-size: clamp(0.95rem, 2.4vw, 1.35rem); color: var(--dark); line-height: 1.05; }
.rw-center-sub { font-size: 0.72rem; color: var(--secondary); margin-top: 0.15rem; font-weight: 600; }

.rw-spoke {
  position: absolute;
  width: 27%;
  left: 50%; top: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  text-decoration: none !important;
  color: var(--dark);
  transition: transform 0.18s ease;
}
.rw-tile {
  display: block;
  border-radius: 50%;
  overflow: hidden;
  aspect-ratio: 1 / 1;
  background: var(--light);
  border: 2px solid var(--lightgray);
  box-shadow: 0 3px 12px rgba(120,90,60,0.10);
  transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
}
.rw-tile img { width: 100%; height: 100%; object-fit: cover; display: block; }
.rw-label { display: block; margin-top: 0.3rem; font-size: 0.78rem; line-height: 1.15; font-weight: 600; color: var(--darkgray); }
.rw-sub { display: block; font-size: 0.66rem; color: var(--secondary); }
.rw-spoke:hover, .rw-spoke:focus-visible { z-index: 5; outline: none; }
.rw-spoke:hover .rw-tile, .rw-spoke:focus-visible .rw-tile {
  border-color: var(--secondary);
  box-shadow: 0 8px 22px rgba(120,90,60,0.22);
  transform: scale(1.08);
}
.rw-spoke:focus-visible .rw-tile { outline: 3px solid var(--secondary); outline-offset: 2px; }

/* ---- grid fallback (narrow screens) ---- */
.radial-wheel.rw-grid .rw-stage { display: none; }
.rw-fallback { display: none; }
.radial-wheel.rw-grid .rw-fallback {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(118px, 1fr));
  gap: 1rem;
}
.rw-fallback .rw-spoke {
  position: static; transform: none; width: auto;
  display: flex; flex-direction: column; align-items: center;
}
.rw-fallback .rw-tile { width: 88px; height: 88px; }
.rw-fallback .rw-spoke:hover .rw-tile { transform: scale(1.05); }
`

export default (() => {
  const RadialWheel: QuartzComponent = () => null
  RadialWheel.afterDOMLoaded = script
  RadialWheel.css = style
  return RadialWheel
}) satisfies QuartzComponentConstructor
