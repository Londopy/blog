---
title: "Things GitHub Actions Can Do That Aren't CI"
date: 2026-09-24T12:00:00-07:00
draft: true
description: "GitHub Actions is a free, event-driven computer attached to every repo. Running tests is just the start."
tags: ["github", "github-actions", "automation"]
author: "Londopy"
ShowToc: true
cover:
  image: "cover.png"
  alt: "A terminal printing a scheduled GitHub Actions workflow, above the post title"
  relative: true
---

Most people meet GitHub Actions as "the thing that runs tests on pull requests." But under the hood it's much more general: a computer that wakes up when something happens, runs whatever you tell it, and goes back to sleep. For public repos, it's free.

Here are things you can do with it that have nothing to do with CI.

## How it works in 30 seconds

A workflow is a YAML file in `.github/workflows/`. It has:

- **triggers** (`on:`): a push, a new issue, a schedule, a button click
- **jobs** that run on a fresh virtual machine
- **steps**, each either a shell command or a reusable action

That's it. Anything you can script, you can trigger.

## 1. Host a website

This blog is built by Actions. Every push to `main` builds the site with Hugo and publishes it to GitHub Pages. No server, no bill.

```yaml
on:
  push:
    branches: [main]
```

The official `actions/upload-pages-artifact` and `actions/deploy-pages` actions do the publishing.

## 2. Run things on a schedule

Actions supports cron:

```yaml
on:
  schedule:
    - cron: "0 14 * * 1"   # every Monday at 14:00 UTC
  workflow_dispatch:        # plus a manual "Run" button
```

Uses: nightly data scrapes, weekly reports, checking whether a website is up, rebuilding a site so "posted 3 days ago" stays accurate.

**Know this:**
- Times are in **UTC**.
- Scheduled runs can start late when GitHub is busy, sometimes by many minutes. Don't use it for anything that must happen at an exact second.
- In public repos, scheduled workflows are **automatically disabled after 60 days without repository activity**. GitHub emails you first.

## 3. Keep a file updated automatically

A workflow can edit files and commit them back. For example, a profile README that always lists your latest blog posts:

```yaml
permissions:
  contents: write

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: ./scripts/update-readme.sh
      - run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add README.md
          git diff --cached --quiet || git commit -m "Update latest posts"
          git push
```

The `git diff --cached --quiet ||` part only commits if something actually changed, so you don't get empty commits.

## 4. Manage issues and pull requests

- **Auto-label** PRs by which files they touch (`actions/labeler`).
- **Welcome first-time contributors** with a friendly comment.
- **Close stale issues** after a period of inactivity (`actions/stale`). Use gently; closing people's issues automatically can feel rude.
- **Enforce PR title formats** for changelogs.

Triggers like `issues`, `issue_comment`, and `pull_request` make this easy.

## 5. Build a ChatOps bot

A workflow can react to comments. Someone types `/deploy staging` on a PR, and a workflow checks their permissions and runs the deploy. Check the comment author's permission level before doing anything, or anyone on the internet can trigger it.

## 6. Watch other things on the internet

A scheduled job can:

- check whether your site returns 200 and open an issue if not
- check whether a dependency released a new version
- watch a page for changes and notify you

GitHub isn't built for real-time monitoring, but for "check once an hour and tell me," it's plenty.

## 7. Trigger workflows from outside GitHub

With `repository_dispatch`, anything that can make an HTTP request can start a workflow: a script on your server, a webhook from another service, a phone shortcut.

```yaml
on:
  repository_dispatch:
    types: [rebuild-site]
```

## 8. Generate release artifacts

Build binaries for Windows, macOS, and Linux in parallel with a matrix, then attach them to a GitHub Release automatically when you push a version tag.

```yaml
on:
  push:
    tags: ["v*"]
```

## Things you should know

**Least privilege.** Set `permissions:` explicitly in every workflow. Give each workflow only what it needs.

**Secrets and forks.** Workflows triggered by pull requests from forks don't get your secrets, on purpose. Be very careful with the `pull_request_target` trigger: it runs with your secrets and write permissions, and if it checks out and runs the fork's code, a stranger's PR can steal your secrets.

**Pin actions.** A third-party action is someone else's code running with your permissions. Pin it to a full commit hash rather than a tag if you don't fully trust the author:

```yaml
- uses: some-author/some-action@8f4b7f84864484a7bf31766abe9204da3cbe65b3
```

**Free isn't unlimited.** Public repos get free minutes on standard runners. Private repos get a monthly allowance, then usage is billed. Check the current limits before you build something heavy.

## Closing thought

Think of every repo as coming with a small, free, scriptable computer that listens for events. CI is one thing you can do with it. Your imagination and the terms of service are the rest.
