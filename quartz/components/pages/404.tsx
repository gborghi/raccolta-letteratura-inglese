import { i18n } from "../../i18n"
import { QuartzComponent, QuartzComponentConstructor, QuartzComponentProps } from "../types"

// Client-side redirects for retired URLs. In v5 this built-in NotFound component
// IS the served 404.html (it overrides any content/404.md), so the redirect logic
// must live here, not in a generated markdown page. Two families:
//   1. SPA per-atom restructure: /testi/<a>/<sub>/<work>/<chapter>/<part…> ->
//      /testi/<a>/<sub>/<work>#<chapter>--<part> (deterministic, no lookup).
//   2. Dickinson cluster-SPA restructure: retired per-poem reading + works pages
//      (no trailing segment, so #1's regex skips them) -> new cluster fragment via
//      the static quartz/static/dickinson_redirects.json map, fetched only on a 404.
const REDIRECT_SCRIPT = `(function(){
  var p=decodeURIComponent(location.pathname).replace(/\\/index\\.html$/,"").replace(/\\/$/,"");
  var m=p.match(/^(.*)\\/testi\\/([^/]+)\\/(atomized|plays|long)\\/([^/]+)\\/(.+)$/i);
  if(m){location.replace(m[1]+"/testi/"+m[2]+"/"+m[3]+"/"+m[4]+"#"+m[5].replace(/\\//g,"--"));return;}
  var d=p.match(/^(.*)\\/((?:testi\\/dickinson\\/atomized|works)\\/.+)$/i);
  if(d){fetch(d[1]+"/static/dickinson_redirects.json").then(function(r){return r.ok?r.json():null;}).then(function(map){if(map&&map[d[2]])location.replace(d[1]+"/"+map[d[2]]);}).catch(function(){});}
})();`

const NotFound: QuartzComponent = ({ cfg }: QuartzComponentProps) => {
  // If baseUrl contains a pathname after the domain, use this as the home link
  const url = new URL(`https://${cfg.baseUrl ?? "example.com"}`)
  const baseDir = url.pathname

  return (
    <article class="popover-hint">
      <h1>404</h1>
      <p>{i18n(cfg.locale).pages.error.notFound}</p>
      <a href={baseDir}>{i18n(cfg.locale).pages.error.home}</a>
      <script dangerouslySetInnerHTML={{ __html: REDIRECT_SCRIPT }} />
    </article>
  )
}

export default (() => NotFound) satisfies QuartzComponentConstructor
