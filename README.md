# Londopy blog

Notes on security, systems, radio, and building things, plus whatever else
I'm chewing on. Live at **https://londopy.github.io/blog/**.

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
3. Make the cover: `python scripts/make_cover.py content/posts/<slug>`. To put
   terminal lines on the card instead of the description, add them to
   `scripts/covers.json` under the slug first (`$ ` lines are commands, the
   rest is output, five lines at most). Needs Pillow.
4. Strip metadata from every image in the bundle, since photos can carry GPS
   and device info:
   `exiftool -all= -overwrite_original content/posts/<slug>/*.png`
   (and `*.jpg`).
5. Preview with `hugo server -D -F` on desktop and phone.
6. To publish, set `draft: false`, then commit and push. The `date` decides
   when the post appears: a date that has passed goes live with the push, and
   a future date goes live with the first daily rebuild on or after it (see
   Deploying). That's how to schedule a post. Either way, subscribers get an
   email once it's live (see Emails for new posts).

Images live next to the post in its page bundle. Keep `cover.relative: true`
in the front matter: PaperMod builds `og:image` from it, and without it the
social preview points at `/blog/cover.png` and 404s.

Chroma has no lexer for `.gitattributes`, so fences tagged `gitattributes` are
highlighted by `layouts/_markup/render-codeblock-gitattributes.html`.

## Assets

Every image the site serves comes from a script, so the whole set can be
rebuilt after a design change:

- `python scripts/make_icons.py` writes the favicons (`.ico`, 16 and 32 px
  PNGs, and `favicon.svg`, which is also the header logo), the Safari
  pinned-tab mask, the Apple touch icon, and the Android icons that
  `static/site.webmanifest` lists. They reproduce the `>_` mark from
  londopy.github.io, traced from JetBrains Mono Bold.
- `python scripts/make_cover.py --all` writes every post's `cover.png` (using
  the lines in `scripts/covers.json`) and `static/og-image.png`, the social
  card for pages without a cover. `--site` or a single post directory
  rebuilds just that one.

Both scripts need Pillow, and `make_icons.py` also needs fontTools
(`pip install pillow fonttools`) and the JetBrains Mono font.

## Deploying

Every push to `main` builds the site and deploys it to Pages
(`.github/workflows/deploy.yml`). The Pages source is set to "GitHub Actions"
in the repo settings. Drafts never build in production.

The same workflow also rebuilds the site every day at 17:30 UTC (10:30 PDT,
09:30 PST). Hugo leaves out posts dated in the future, so that daily run is
what publishes a scheduled post: one dated 09:00 Pacific goes up the same
morning. GitHub pauses scheduled workflows in public repos after 60 days
without repository activity; if that happens, re-enable it from the Actions
tab. To see what a given day's build will contain, run
`hugo --clock 2026-10-01T17:30:00Z` locally.

Versions are pinned: Hugo in the workflow (`hugo-version`) and the theme by its
submodule commit. To upgrade either, bump it, check `hugo server` locally, and
push. For the theme:

```sh
git submodule update --remote themes/PaperMod
```

The build prints two deprecation warnings (`.Language.LanguageCode` and
`.Language.LanguageDirection`). They come from the theme's templates and will
go away when PaperMod catches up with Hugo.

## Emails for new posts

Readers can get each new post by email. The deploy sends the emails itself,
through [Buttondown](https://buttondown.com)'s API (free for up to 100
subscribers), so publishing a post is all it takes:

- The build job's "Find posts to email" step (`scripts/notify.py plan`)
  compares the posts in the new build with the ones the live site lists at
  `/api/v1/posts.json`. The posts only the new build has are the ones this
  deploy publishes, whether they were pushed or were scheduled and let
  through by the daily rebuild.
- After the deploy, the `notify` job (`scripts/notify.py send`) emails each
  of them. The subject is the title, and the body is the cover, the
  description, and a link. It first asks Buttondown whether that post was
  already emailed, because Pages can serve the old posts.json for ten minutes
  after a deploy.
- Nothing about emails can stop a deploy. If the notifier's tests fail, the
  live site can't be read, or more than three posts turn up at once, nobody
  is emailed and the run shows a warning.

The `BUTTONDOWN_API_KEY` repository secret holds the API key, and
`params.newsletter.buttondown` in `hugo.toml` names the Buttondown account
that the sign-up forms post to (`londopy`). While it's empty, the form on
`/subscribe/` and the box after each post stay hidden.

If an email didn't go out, run the workflow by hand (Actions, then "Deploy
Hugo site to Pages", then "Run workflow") with the post's slug. Tick "only
make a draft" to preview the email in Buttondown instead. From a terminal:

```sh
gh workflow run deploy.yml -f email_post=<slug> -f email_draft=true
```

Changing a post's slug makes it look new, so it gets emailed again.

`python scripts/test_notify.py` runs the notifier's tests offline, against a
stand-in for Buttondown. The deploy runs them too, before it looks for posts
to email.

## API

Every post is also served as JSON under `/blog/api/v1/`, documented at
https://londopy.github.io/blog/api/ and described in OpenAPI 3.1 at
`/blog/api/openapi.json`. It's static: Hugo writes it on every build, from the
same published pages as the site, so drafts and scheduled posts never show up
early. The pieces:

- `data/api.yaml`: the catalog of endpoints. It feeds `/api/v1/index.json`,
  the table on the docs page and the deploy check.
- `layouts/home.api.json` and `layouts/_partials/api/`: the templates that
  write every endpoint.
- `assets/api/openapi.yaml`: the OpenAPI description, published as JSON.
- `content/api/index.md`: the docs page.
- `scripts/check_api.py`: run by the deploy after every build. It validates
  each response against the OpenAPI schemas and checks the API lists exactly
  the posts that were built. Run it locally with
  `hugo -d public && python scripts/check_api.py public`.

To add an endpoint: add it to `data/api.yaml`, write it in
`layouts/home.api.json`, and describe it in `assets/api/openapi.yaml`. The
check fails the deploy if the catalog and the OpenAPI paths disagree. Within
`v1`, only add fields and endpoints; anything that would break a client goes
in a new `/api/v2/`.

## Cross-posting

The blog is the canonical home of every post. Copies on dev.to, Hashnode, or
Medium must set their canonical URL to the post here. dev.to can import
straight from the feed, which carries full post content:
https://londopy.github.io/blog/index.xml

## License

- Writing (the posts in `content/`): [CC BY 4.0](LICENSE-CONTENT)
- Code (the site source and the code snippets in posts): [MIT](LICENSE)

The theme in `themes/PaperMod` has its own MIT license.
