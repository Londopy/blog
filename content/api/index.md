---
title: "API"
description: "Every post on this blog as JSON: the full text, tags, the archive, the numbers, a JSON Feed and badges. Read-only, no key, open to any website."
hidemeta: true
hiddenInRss: true
ShowToc: true
ShowPostNavLinks: false
---

Everything on this blog is also available as JSON, for your own reader, a widget, or a script. It's a set of static files rebuilt with the blog on every push and every day, so there's no key and no sign-up, and any website can fetch it (CORS is open). GitHub Pages may cache a file for up to ten minutes.

Only published posts appear. A scheduled post joins the API with the build that publishes it.

## Quick start

```sh
# every post, newest first
curl -s https://londopy.github.io/blog/api/v1/posts.json

# one post in full
curl -s https://londopy.github.io/blog/api/v1/posts/gitattributes.json

# the list, readable in a terminal
curl -s https://londopy.github.io/blog/api/v1/posts.txt
```

From a web page:

```js
const res = await fetch("https://londopy.github.io/blog/api/v1/latest.json");
const { data: post } = await res.json();
console.log(post.title, post.url);
```

With [jq](https://jqlang.org/):

```sh
curl -s https://londopy.github.io/blog/api/v1/posts.json |
  jq -r '.data[] | "\(.published[:10])  \(.title)"'
```

## Endpoints

{{< api-endpoints >}}

The same list is available as JSON at [/blog/api/v1/index.json](https://londopy.github.io/blog/api/v1/index.json). The whole API is described in OpenAPI 3.1 at [/blog/api/openapi.json](https://londopy.github.io/blog/api/openapi.json), which you can load into Swagger UI, Postman, or a client generator.

## The envelope

Every response wraps its payload the same way as my [portfolio's API](https://londopy.github.io/api/):

```json
{
  "meta": {
    "api": "londopy-blog",
    "version": "1.0.0",
    "generated": "2026-09-25T20:39:31Z",
    "self": "https://londopy.github.io/blog/api/v1/posts.json",
    "docs": "https://londopy.github.io/blog/api/"
  },
  "data": []
}
```

The standard formats skip the envelope, so their usual tools work on them: the JSON Feed, the shields.io badges, RSS, and `posts.txt`.

## A post

The lists (`posts.json`, `tags/{tag}.json`) carry a summary of each post:

| Field | What it is |
|---|---|
| `slug`, `title`, `description` | The post's slug, title, and my one-paragraph description |
| `summary` | The opening of the post, as plain text |
| `url` | The post on this blog, which is always the original |
| `api_url` | The post in full, as JSON |
| `published`, `updated` | ISO 8601 dates; `updated` comes from git |
| `tags` | Each tag's `name`, `slug`, `url` and `api_url` |
| `reading_time_minutes`, `word_count` | How long it is |
| `cover` | The cover image's `url`, `width`, `height` and `alt` |

`posts/{slug}.json` and `latest.json` add the rest:

| Field | What it is |
|---|---|
| `content_html` | The rendered post, with every link and image URL made absolute |
| `content_text` | The same post as plain text |
| `headings` | Each heading's `level`, `id`, `title`, and a `url` straight to it |
| `code` | How many code blocks, and in which languages |
| `links` | Every link in the post, split into `internal` and `external` |
| `images` | Each image's `url`, `width` and `height`, and whether it's the cover |
| `older`, `newer` | The posts on either side, or `null` |
| `license` | `CC-BY-4.0` for the writing, `MIT` for the code |
| `source` | The Markdown on GitHub, the raw file, and its history |

## Feeds and badges

The [JSON Feed](https://www.jsonfeed.org/) at `/blog/api/v1/feed.json` and the RSS feed at `/blog/index.xml` both carry full posts, so either works in a feed reader.

The badges plug into [shields.io](https://shields.io/badges/endpoint-badge), for a README or anywhere else:

```md
![blog posts](https://img.shields.io/endpoint?url=https://londopy.github.io/blog/api/v1/badges/posts.json)
```

The metrics are `posts`, `words`, `latest` (the newest post's title) and `updated` (its date).

## Versioning

This is version 1. Within `v1`, changes only add things: new fields, new endpoints. Anything that would break a client gets a new `/api/v2/`, and `v1` stays up alongside it.

Before every deploy, [`scripts/check_api.py`](https://github.com/Londopy/blog/blob/main/scripts/check_api.py) validates every response against the OpenAPI description, so what the docs promise is what you get.

## Using the writing

The posts are licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/): quote them, translate them, or republish them, as long as you credit Londopy and link to the original post. Code in the posts is [MIT](https://github.com/Londopy/blog/blob/main/LICENSE). The whole site's source is on [GitHub](https://github.com/Londopy/blog).

My [portfolio's API](https://londopy.github.io/api/) covers everything else on londopy.github.io: the projects, pull requests, and more.
