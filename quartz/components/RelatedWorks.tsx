import { QuartzComponent, QuartzComponentConstructor } from "./types"
// @ts-ignore  bundled as client-side script
import script from "./scripts/relatedWorks.inline"

const style = `
.related-works {
  margin: 2.2rem 0 0.5rem;
  padding-top: 1.2rem;
  border-top: 1px solid var(--lightgray);
}
.related-works h2 { margin: 0 0 0.7rem; font-size: 1.15rem; }
.related-works ul { list-style: none; margin: 0; padding: 0; display: grid;
  grid-template-columns: repeat(auto-fill, minmax(15rem, 1fr)); gap: 0.35rem 1rem; }
.related-works li { padding: 0.15rem 0; line-height: 1.3; }
.related-works a { font-weight: 600; }
.related-works .rw-author { color: var(--gray); font-size: 0.85rem; }
`

export default (() => {
  const RelatedWorks: QuartzComponent = () => null
  RelatedWorks.afterDOMLoaded = script
  RelatedWorks.css = style
  return RelatedWorks
}) satisfies QuartzComponentConstructor
