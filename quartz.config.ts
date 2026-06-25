import { QuartzConfig } from "./quartz/cfg"
import * as Plugin from "./quartz/plugins"

/**
 * Quartz 4 Configuration
 *
 * See https://quartz.jzhao.xyz/configuration for more information.
 */
const config: QuartzConfig = {
  configuration: {
    pageTitle: "English Literature — A Knowledge Graph",
    pageTitleSuffix: "",
    enableSPA: true,
    enablePopovers: true,
    analytics: null,
    locale: "en-US",
    baseUrl: "gborghi.github.io/raccolta-letteratura-inglese",
    ignorePatterns: ["private", "templates", ".obsidian", "Authors"],
    defaultDateType: "modified",
    theme: {
      fontOrigin: "googleFonts",
      cdnCaching: true,
      typography: {
        header: "Fraunces",
        body: "Source Sans 3",
        code: "IBM Plex Mono",
      },
      colors: {
        lightMode: {
          light: "#fbf6ee",
          lightgray: "#e7ddcf",
          gray: "#a99c88",
          darkgray: "#5a5145",
          dark: "#33302b",
          secondary: "#c9785b",
          tertiary: "#8a9a78",
          highlight: "rgba(201, 120, 91, 0.10)",
          textHighlight: "#e8b88c88",
        },
        darkMode: {
          light: "#23201c",
          lightgray: "#3c372f",
          gray: "#7f7565",
          darkgray: "#d9cfbf",
          dark: "#f2ebe0",
          secondary: "#d98e6f",
          tertiary: "#9cae88",
          highlight: "rgba(217, 142, 111, 0.12)",
          textHighlight: "#c9785b88",
        },
      },
    },
  },
  plugins: {
    transformers: [
      Plugin.FrontMatter(),
      Plugin.CreatedModifiedDate({
        // "git" walks the full repo history per file — with ~19k pages that is
        // both very slow and memory-hungry (OOM during parse). Filesystem mtime
        // is plenty for this content set.
        priority: ["frontmatter", "filesystem"],
      }),
      Plugin.SyntaxHighlighting({
        theme: {
          light: "github-light",
          dark: "github-dark",
        },
        keepBackground: false,
      }),
      Plugin.ObsidianFlavoredMarkdown({ enableInHtmlEmbed: false }),
      Plugin.GitHubFlavoredMarkdown(),
      Plugin.TableOfContents(),
      Plugin.CrawlLinks({ markdownLinkResolution: "shortest" }),
      Plugin.Description(),
      Plugin.Latex({ renderEngine: "katex" }),
    ],
    filters: [Plugin.RemoveDrafts()],
    emitters: [
      Plugin.AliasRedirects(),
      Plugin.ComponentResources(),
      Plugin.ContentPage(),
      Plugin.FolderPage(),
      Plugin.TagPage(),
      Plugin.ContentIndex({
        enableSiteMap: true,
        enableRSS: true,
      }),
      Plugin.Assets(),
      Plugin.Static(),
      Plugin.Favicon(),
      Plugin.NotFoundPage(),
      // CustomOgImages disabled: 3500+ notes makes per-page OG rendering far too slow.
      // Plugin.CustomOgImages(),
    ],
  },
}

export default config
