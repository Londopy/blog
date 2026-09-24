---
title: "git bisect run: Let Git Find the Bug for You"
date: 2026-10-08T09:00:00-07:00
draft: false
description: "Something broke, and you don't know which of the last 400 commits did it. Git can binary-search your history and find the exact commit, automatically."
tags: ["git", "debugging", "tooling"]
author: "Londopy"
ShowToc: true
cover:
  image: "cover.png"
  alt: "A terminal running git bisect run to find the first bad commit, above the post title"
  relative: true
---

It worked last month. It doesn't work now. There are 400 commits in between.

You could read them all. Or you could let Git find the guilty one in about nine steps.

## The idea: binary search through history

`git bisect` takes two points: a commit where things were **good** and one where they're **bad**. It checks out the commit halfway between and asks you which it is. Then it throws away the half that can't contain the bug and repeats.

Each step halves the search. 400 commits takes at most 9 steps. 10,000 commits takes at most 14.

## Manual bisect

```sh
git bisect start
git bisect bad                 # the current commit is broken
git bisect good v2.3.0         # this tag was fine
```

Git checks out a commit in the middle and tells you roughly how many steps are left. Test it, then tell Git:

```sh
git bisect good    # this one works
# or
git bisect bad     # this one is broken
```

Repeat until Git prints:

```text
a1b2c3d is the first bad commit
```

When you're done, go back to where you started:

```sh
git bisect reset
```

You can also give both endpoints up front:

```sh
git bisect start HEAD v2.3.0
```

## The real magic: `git bisect run`

If you can write a script that tells good from bad, Git will do the whole search without you:

```sh
git bisect start HEAD v2.3.0
git bisect run ./check.sh
```

Git checks out each candidate commit, runs your script, and reads its **exit code**:

| Exit code      | Meaning                                       |
|----------------|-----------------------------------------------|
| 0              | good                                          |
| 1 to 127 (not 125) | bad                                       |
| 125            | skip: this commit can't be tested             |
| 128 or higher  | abort the whole bisect                        |

Your test suite is often the script already:

```sh
git bisect run pytest tests/test_login.py
git bisect run cargo test parse_header
git bisect run npm test
```

## Writing a good check script

The script should test *only* the bug you're hunting. A full test suite may fail for unrelated reasons partway through history.

```sh
#!/bin/sh
# check.sh: exit 0 if the bug is absent, 1 if present, 125 if we can't tell

# If it doesn't build, we can't test this commit. Skip it.
make >/dev/null 2>&1 || exit 125

# The actual check
./app --version | grep -q "expected output" && exit 0 || exit 1
```

A few tips:

- **Use 125 for "can't test."** Commits that don't compile, or that predate the feature entirely, should be skipped, not marked bad. Otherwise Git blames the wrong commit.
- **Keep the script outside the repo,** or untracked. Bisect checks out old commits, and an old commit might not have your script, or might have an older version of it.
- **Make it fast.** It runs once per step.
- **Make it deterministic.** A flaky test sends the search in the wrong direction and gives a confident, wrong answer.

## Useful extras

**Skip a commit by hand:**

```sh
git bisect skip
```

**See or replay the session.** If you mark a commit wrong, save the log, edit out the mistake, and replay it:

```sh
git bisect log > bisect.log
# edit bisect.log
git bisect reset
git bisect replay bisect.log
```

**Visualize what's left:**

```sh
git bisect visualize --oneline
```

**Hunt for things that aren't bugs.** "Good" and "bad" are just labels. You can rename them:

```sh
git bisect start --term-old=fast --term-new=slow
git bisect fast v2.3.0
git bisect slow HEAD
```

Now you can find the commit where something got slow, or the commit where a feature first appeared.

**Ignore merged-in side branches.** On a repo with many merges, `--first-parent` only follows the main line of history:

```sh
git bisect start --first-parent
```

## Things you should know

- **Bisect needs a clean working tree.** Commit or stash your changes first.
- **It finds the first bad commit, not the cause.** Sometimes the "first bad commit" just exposed a bug that was already there. Read the diff before blaming anyone.
- **Small commits make bisect better.** If the guilty commit changed 3,000 lines, knowing which commit it was doesn't help much. Another reason to commit in small, focused steps.

## Closing thought

The next time you catch yourself scrolling through `git log` trying to guess when something broke, stop. Write a ten-line script, run `git bisect run`, and go get a coffee.
