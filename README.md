# Londopy blog

Notes on security, systems, radio, and building things.
Live at **https://londopy.github.io/blog/**.

Built with [Hugo](https://gohugo.io/) (extended) and the
[PaperMod](https://github.com/adityatelange/hugo-PaperMod) theme, deployed to
GitHub Pages by GitHub Actions. This repo is a project site, so it is served
under `/blog/`. The root of `londopy.github.io` is the project index from
[Londopy/londopy.github.io](https://github.com/Londopy/londopy.github.io).

## Local setup

```sh
git clone --recurse-submodules https://github.com/Londopy/blog.git
cd blog
hugo server -D -F
```

Then open http://localhost:1313/blog/. `-D` shows drafts and `-F` shows posts
dated in the future. You need Hugo extended 0.166.0, the version pinned in the
deploy workflow. If you cloned without `--recurse-submodules`, run
`git submodule update --init`.

## Writing a post

1. `hugo new posts/<slug>/index.md`. The slug is the folder name, lowercase
   with hyphens. New posts start as `draft: true`.
2. Fill in `description` (required: it becomes the search and social preview)
   and `tags`.
3. Make the cover: `python scripts/make_cover.py content/posts/<slug>`. Add
   `--file NAME --snippet` to show the post's first code block instead of the
   description. Needs Pillow.
4. Strip metadata from every image in the bundle, since photos can carry GPS
   and device info:
   `exiftool -all= -overwrite_original content/posts/<slug>/*.png`
   (and `*.jpg`).
5. Preview with `hugo server -D -F` on desktop and phone.
6. To publish, set `date` to the actual publish time, set `draft: false`, then
   commit and push. Hugo skips posts dated in the future, and nothing rebuilds
   on its own when that date arrives.

Images live next to the post in its page bundle. Keep `cover.relative: true`
in the front matter: PaperMod builds `og:image` from it, and without it the
social preview points at `/blog/cover.png` and 404s.

Chroma has no lexer for `.gitattributes`, so fences tagged `gitattributes` are
highlighted by `layouts/_markup/render-codeblock-gitattributes.html`.

## Deploying

Every push to `main` builds the site and deploys it to Pages
(`.github/workflows/deploy.yml`). The Pages source is set to "GitHub Actions"
in the repo settings. Drafts never build in production.

Versions are pinned: Hugo in the workflow (`hugo-version`) and the theme by its
submodule commit. To upgrade either, bump it, check `hugo server` locally, and
push. For the theme:

```sh
git submodule update --remote themes/PaperMod
```

The build prints two deprecation warnings (`.Language.LanguageCode` and
`.Language.LanguageDirection`). They come from the theme's templates and will
go away when PaperMod catches up with Hugo.

## Cross-posting

The blog is the canonical home of every post. Copies on dev.to, Hashnode, or
Medium must set their canonical URL to the post here. dev.to can import
straight from the feed, which carries full post content:
https://londopy.github.io/blog/index.xml

## License

- Writing (the posts in `content/`): [CC BY 4.0](LICENSE-CONTENT)
- Code (the site source and the code snippets in posts): [MIT](LICENSE)

The theme in `themes/PaperMod` has its own MIT license.
