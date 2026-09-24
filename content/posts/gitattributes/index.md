---
title: "The Best Git Feature You've Never Used"
date: 2026-09-24T12:00:00-07:00
draft: true
description: "Every repo has a .gitignore. Almost nobody has a .gitattributes. Here's everything it can do: line endings, smarter diffs, merge strategies, filters, release archives, and GitHub extras."
tags: ["git", "github", "gitattributes", "tooling", "devops"]
author: "Londopy"
ShowToc: true
cover:
  image: "cover.png"
  alt: "A terminal printing a .gitattributes file, above the post title"
  relative: true
---

Every repo has a `.gitignore`. Almost nobody has a `.gitattributes`. That's a shame, because this one small file controls how Git sees, diffs, merges, normalizes, and exports your files. Once you know what it can do, you'll want one in every project.

## What it is

`.gitattributes` is a plain text file that assigns *attributes* to paths. Each line is a pattern followed by one or more attributes:

```gitattributes
*.sh    text eol=lf
*.png   binary
docs/** linguist-documentation
```

The patterns work much like `.gitignore`, with two catches. Negation (`!pattern`) isn't allowed. And a directory pattern like `vendor/` does not apply to the files inside it, so you need `vendor/**`.

Each attribute can be in one of four states:

- **Set:** `text`
- **Unset:** `-text`
- **Set to a value:** `eol=lf`
- **Unspecified:** `!text`, which resets it to as if you never mentioned it

## Where it lives

Git reads attributes from several places, from highest priority to lowest:

1. `.git/info/attributes`: local to your clone and never committed. Good for personal rules.
2. `.gitattributes` files in the repo. A file in a subdirectory overrides one in a parent directory.
3. Your global file (set with `core.attributesFile`, usually `~/.config/git/attributes`).
4. The system-wide file.

When a file behaves strangely, ask Git what it thinks:

```sh
git check-attr -a path/to/file
```

## 1. End the line-ending wars

This is the reason most people should add a `.gitattributes` today. Windows uses CRLF, everything else uses LF, and without rules you end up with diffs where every line "changed."

```gitattributes
* text=auto
*.sh  text eol=lf
*.bat text eol=crlf
*.ps1 text eol=crlf
```

`text=auto` lets Git detect text files and store them with LF in the repo. The `eol=` rules pin specific file types, which matters for shell scripts that break with CRLF and batch files that expect it.

**Know this:** adding these rules doesn't fix files that are already committed. Run this once and commit the result:

```sh
git add --renormalize .
```

To see the current line-ending state of every file:

```sh
git ls-files --eol
```

## 2. Mark binaries as binary

```gitattributes
*.png  binary
*.jpg  binary
*.zip  binary
```

`binary` is a built-in *macro* that expands to `-text -diff -merge`. Git won't try to convert line endings, show a text diff, or attempt a text merge. That last one saves you from corrupted files after a merge that "succeeded."

## 3. Hunk headers that actually help

When you run `git diff`, each hunk starts with a line like `@@ -12,7 +12,8 @@`, followed by some context Git guessed at. Often that guess is useless. Tell Git the language and it names the enclosing function or class instead:

```gitattributes
*.py   diff=python
*.rs   diff=rust
*.go   diff=golang
*.java diff=java
*.md   diff=markdown
*.tex  diff=tex
```

These drivers are built in. There's nothing to install. The Markdown one shows the nearest heading, which is great for docs.

## 4. Diff files that aren't text

With a `textconv` driver, Git runs a command that turns a binary file into text, then diffs that text.

```gitattributes
*.png  diff=exif
*.pdf  diff=pdf
*.docx diff=docx
```

```sh
git config --global diff.exif.textconv exiftool
git config --global diff.docx.textconv "pandoc --from=docx --to=plain"
```

Git appends the file path to the command, and the command must print text to stdout. `exiftool` and `pandoc` already do that. `pdftotext` doesn't; by default it writes a `.txt` file next to the input. Wrap it in a tiny script:

```sh
#!/bin/sh
# save as ~/bin/pdf2txt and chmod +x it
pdftotext -layout "$1" -
```

```sh
git config --global diff.pdf.textconv pdf2txt
```

Now `git diff` on an image shows which metadata changed, and `git log -p` on a Word doc or PDF shows actual prose changes. Add `git config --global diff.pdf.cachetextconv true` so Git doesn't reconvert unchanged files every time.

## 5. Silence noise you don't care about

```gitattributes
package-lock.json -diff
Cargo.lock        -diff
*.min.js          -diff
```

The files are still tracked and versioned normally. `git diff` just prints "Binary files differ" instead of four thousand lines of dependency churn.

## 6. Merge strategies per file

```gitattributes
CHANGELOG.md  merge=union
```

`union` keeps the lines from both sides instead of creating a conflict. It's perfect for append-only files like changelogs or lists of contributors. It's dangerous for anything where order or structure matters, like code or JSON.

You can also keep your own version of a file on merge:

```gitattributes
config/local.yml merge=ours
```

```sh
git config merge.ours.driver true
```

**Know this:** a merge driver only runs when *both* branches changed the file. If only the other branch touched it, Git takes their version cleanly and your driver never runs. Plenty of people have been surprised by this.

## 7. Clean and smudge filters

This is the most powerful feature in the file. A filter has two halves:

- **clean** runs when a file is staged, transforming the working copy into what gets stored.
- **smudge** runs on checkout, transforming the stored version back into your working copy.

```gitattributes
*.ipynb filter=nbstrip
```

```sh
git config filter.nbstrip.clean "jupyter nbconvert --clear-output --to notebook --stdout --stdin"
git config filter.nbstrip.smudge cat
git config filter.nbstrip.required true
```

Now notebook outputs never get committed, but you keep them locally.

Real-world tools built on filters:

- **Git LFS** stores large files elsewhere and commits small pointers: `*.psd filter=lfs diff=lfs merge=lfs -text`
- **git-crypt** transparently encrypts files in the repo and decrypts them on checkout
- **nbstripout** does the notebook trick above

**Know this:** filter *definitions* live in Git config, not in the repo. `.gitattributes` only says "use the filter named X." Every person who clones the repo has to set up the filter themselves. This is on purpose: if a repo could define commands that run automatically on checkout, cloning a stranger's repo would be a security risk. Document your filters in the README.

## 8. Shape your release archives

`git archive` builds a tarball or zip of your repo. Attributes control what goes in it:

```gitattributes
tests/         export-ignore
.github/       export-ignore
.gitattributes export-ignore
VERSION        export-subst
```

`export-ignore` leaves files out of release archives. GitHub's "Download ZIP" and release source tarballs respect this too.

`export-subst` expands placeholders at archive time. Put this in `VERSION`:

```text
$Format:%H$ $Format:%cd$
```

The archive will contain the real commit hash and date.

## 9. The GitHub extras

GitHub reads a set of `linguist-*` attributes that change how your repo is displayed:

```gitattributes
vendor/**      linguist-vendored
dist/**        linguist-generated
docs/**        linguist-documentation
*.nx           linguist-language=Rust
scripts/*.txt  linguist-detectable
```

- `linguist-vendored` and `linguist-documentation` exclude files from the language bar.
- `linguist-generated` also **collapses those files in pull request diffs**. For generated code, lockfiles, or build output, this makes reviews much faster.
- `linguist-language` fixes misdetection, or lets a custom language borrow another's highlighting.
- `linguist-detectable` forces a language to count toward the stats when it normally wouldn't.

## 10. Lesser-known attributes

**`whitespace`** sets per-file rules for what `git diff --check` flags:

```gitattributes
*.md whitespace=-trailing-space
*.py whitespace=trailing-space,tab-in-indent
```

Markdown uses two trailing spaces as a line break, so you don't want those flagged there.

**`working-tree-encoding`** stores UTF-16 files as UTF-8 in the repo so they diff properly, then converts them back on checkout:

```gitattributes
*.ps1 working-tree-encoding=UTF-16LE eol=crlf
```

**`-delta`** skips delta compression for huge binaries that don't compress well anyway, which speeds up packing:

```gitattributes
*.mp4 -delta
```

**`ident`** expands `$Id$` in a file to `$Id: <blob hash>$` on checkout. It's old-school, but handy for embedding a file's exact version.

**`lockable`** works with Git LFS file locking. Files are checked out read-only until you lock them, which prevents two people from editing the same unmergeable file:

```gitattributes
*.psd lockable
```

## 11. Macros

In the top-level `.gitattributes` only, you can define your own bundles of attributes:

```gitattributes
[attr]lockfile -diff merge=ours linguist-generated

package-lock.json lockfile
yarn.lock         lockfile
Cargo.lock        lockfile
```

One name, one place to change it later.

## A sane starter file

If you take one thing from this post, drop this into your next project:

```gitattributes
# Normalize line endings
* text=auto

# Scripts that care about endings
*.sh  text eol=lf
*.bat text eol=crlf
*.ps1 text eol=crlf

# Better diff hunk headers
*.py diff=python
*.md diff=markdown
*.rs diff=rust

# Binaries
*.png binary
*.jpg binary
*.gif binary
*.ico binary
*.zip binary
*.pdf binary

# Quiet noisy files
*.lock            -diff
package-lock.json -diff

# Keep release archives clean
.github/        export-ignore
.gitattributes  export-ignore
```

## Closing thought

`.gitignore` tells Git what to leave out. `.gitattributes` tells Git how to understand everything you keep. It's a few lines of text that fix line-ending chaos, make diffs readable, prevent merge disasters, and shape what your users download. Most repos never touch it. Now yours can.
