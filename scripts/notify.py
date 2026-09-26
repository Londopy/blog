#!/usr/bin/env python3
"""Email subscribers when a post goes live.

    python scripts/notify.py plan public    # build job, before the deploy
    python scripts/notify.py send           # notify job, after the deploy

`plan` compares the posts in this build (public/api/v1/posts.json) with the
posts the live site serves right now (LIVE_POSTS, the URL of its posts.json).
The posts only this build has are the ones this deploy publishes, whether they
were pushed or were scheduled and let through by the daily rebuild. It writes
them to the step output `new_posts` as JSON. EMAIL_POST=<slug> picks one post
from the build instead, to redo an email that failed. Whenever it can't be
sure (the live site unreachable, more than MAX_NEW new posts at once), the
answer is no posts, with a warning on the run: a missed email can be sent by
hand, but a wrong one can't be unsent.

`send` emails each post in NEW_POSTS through Buttondown's API, using the
BUTTONDOWN_API_KEY secret. The subject is the title, and the body is the cover,
the description, and a link to the post. Before sending, it asks Buttondown
whether an email for that post already went out: GitHub Pages can serve the
old posts.json for up to ten minutes after a deploy, so a second deploy soon
after the first could see the same post as new. With EMAIL_DRAFT=true it makes
drafts to preview in Buttondown instead. Without an API key it does nothing.

Standard library only.
"""
import html
import http.client
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = os.environ.get("BUTTONDOWN_API_URL", "https://api.buttondown.com/v1")
# Pinned: from this version on, an email is a draft unless the request says
# otherwise, and the first send needs the confirmation header in email().
API_VERSION = "2026-04-01"
# One post a week is the plan. More than this at once is a mistake (a renamed
# API path, slugs changed in bulk), not a busy week.
MAX_NEW = 3
# Emails in these states never reached anyone. Every other state means sent,
# sending, or scheduled to send.
NOT_SENT = {"draft", "deleted", "errored"}
RETRY_DELAY = 5  # seconds, times the attempt number
AGENT = "londopy-blog-notify (+https://github.com/Londopy/blog)"


def note(kind, message):
    """Print a message, as an annotation on the run (notice, warning or error) in Actions."""
    if os.environ.get("GITHUB_ACTIONS"):
        escaped = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::{kind}::{escaped}")
    else:
        print(f"{kind}: {message}")


def append(env, text):
    """Append to the file an Actions variable names (GITHUB_OUTPUT, GITHUB_STEP_SUMMARY)."""
    path = os.environ.get(env)
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text + "\n")


def request(method, url, body=None, headers=None):
    """Return (status, parsed JSON or None, response headers). Network failures raise OSError."""
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("User-Agent", AGENT)
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    for name, value in (headers or {}).items():
        req.add_header(name, value)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            status, raw, got = r.status, r.read(), r.headers
    except urllib.error.HTTPError as e:
        status, raw, got = e.code, e.read(), e.headers
    except http.client.HTTPException as e:  # a connection cut off mid-response
        raise OSError(f"{type(e).__name__}: {e}") from e
    try:
        doc = json.loads(raw.decode("utf-8")) if raw else None
    except ValueError:
        doc = None
    return status, doc, got


def live_slugs(url):
    """The slugs the live site lists, or None if it has no posts API yet (a 404)."""
    problem = None
    for attempt in range(1, 4):
        try:
            status, doc, _ = request("GET", url)
        except OSError as e:
            problem = e
        else:
            if status == 404:
                return None
            if status == 200 and isinstance(doc, dict) and isinstance(doc.get("data"), list):
                return {p["slug"] for p in doc["data"]}
            problem = f"HTTP {status}"
        if attempt < 3:
            time.sleep(RETRY_DELAY * attempt)
    raise RuntimeError(f"couldn't read {url} ({problem})")


def brief(post):
    """The fields of a post that send() uses, so the step output stays small."""
    keep = ("slug", "title", "url", "description", "published", "reading_time_minutes", "cover")
    return {key: post.get(key) for key in keep}


def plan(site):
    with open(os.path.join(site, "api", "v1", "posts.json"), encoding="utf-8") as f:
        built = json.load(f)["data"]
    wanted = os.environ.get("EMAIL_POST", "").strip()
    new = []
    if wanted:
        new = [p for p in built if p["slug"] == wanted]
        if not new:
            note("error", f"Not emailing: no published post has the slug {wanted!r}.")
            append("GITHUB_OUTPUT", "new_posts=[]")
            return 1
    elif not os.environ.get("LIVE_POSTS"):
        note("error", "Set LIVE_POSTS to the live site's posts.json URL.")
        return 2
    else:
        try:
            live = live_slugs(os.environ["LIVE_POSTS"])
        except RuntimeError as e:
            note("warning", f"Not emailing anyone this time: {e}.")
            live = None
        else:
            if live is None:
                note("notice", "The live site has no posts API to compare with yet, so no emails.")
        if live is not None:
            new = [p for p in built if p["slug"] not in live]
        if len(new) > MAX_NEW:
            note("warning", f"{len(new)} posts are new at once, more than the {MAX_NEW} this sends "
                 "on its own, so no emails. To email one, run the deploy by hand with its slug.")
            new = []
    new.sort(key=lambda p: p["published"])
    append("GITHUB_OUTPUT", "new_posts=" + json.dumps([brief(p) for p in new], separators=(",", ":")))
    if new:
        for p in new:
            print(f"To email: {p['title']} ({p['url']})")
        append("GITHUB_STEP_SUMMARY", "### Posts to email\n\n"
               + "\n".join(f"- [{p['title']}]({p['url']})" for p in new))
    else:
        print("No new posts to email.")
    return 0


def body(post):
    """The email: the cover (linking to the post), the description, and the link."""
    url = html.escape(post["url"])
    parts = ["<!-- buttondown-editor-mode: fancy -->"]
    cover = post.get("cover")
    if cover:
        parts.append(f'<p><a href="{url}"><img src="{html.escape(cover["url"])}" '
                     f'alt="{html.escape(cover.get("alt") or "")}" width="600" '
                     f'style="max-width:100%;height:auto;border-radius:8px"></a></p>')
    parts.append(f"<p>{html.escape(post['description'])}</p>")
    link = f'<strong><a href="{url}">Read it on the blog →</a></strong>'
    minutes = post.get("reading_time_minutes")
    parts.append(f"<p>{link} · {minutes} min read</p>" if minutes else f"<p>{link}</p>")
    return "\n".join(parts)


def wait(retry_after, default):
    """Seconds to wait before a retry: Retry-After if it's a number of seconds (capped at a minute)."""
    try:
        return min(max(float(retry_after), 0), 60)
    except (TypeError, ValueError):
        return default


def already_sent(post, auth):
    """How Buttondown lists an email it already sent for this post, or None."""
    url = f"{API}/emails?" + urllib.parse.urlencode({"subject": post["title"]})
    while url:
        status, doc, _ = request("GET", url, headers=auth)
        if status != 200 or not isinstance(doc, dict):
            raise RuntimeError(f"listing emails: HTTP {status}")
        for e in doc.get("results", []):
            if e.get("status") in NOT_SENT:
                continue
            if e.get("canonical_url") == post["url"] or (e.get("metadata") or {}).get("slug") == post["slug"]:
                return f"email {e.get('id')}, {e.get('status')}"
        url = doc.get("next")
    return None


def email(post, key, draft):
    """Send (or draft) one post's email. Returns what happened; raises on failure."""
    title = post["title"]
    auth = {"Authorization": f"Token {key}", "X-API-Version": API_VERSION}
    if not draft:
        prior = already_sent(post, auth)
        if prior:
            return f"Skipped {title!r}: Buttondown already sent it ({prior})."
    payload = {
        "subject": f"[Preview] {title}" if draft else title,
        "body": body(post),
        "description": post["description"],
        "canonical_url": post["url"],
        "status": "draft" if draft else "about_to_send",
        # The blog is the archive, so the email stays off Buttondown's web archive.
        "archival_mode": "disabled",
        "metadata": {"slug": post["slug"], "source": "londopy-blog"},
    }
    if post.get("cover"):
        payload["image"] = post["cover"]["url"]
    headers = dict(auth)
    if not draft:
        # Buttondown's check that a request really means to email everyone.
        headers["X-Buttondown-Live-Dangerously"] = "true"
    problem = None
    for attempt in range(1, 4):
        try:
            status, doc, got = request("POST", f"{API}/emails", payload, headers)
        except OSError as e:
            status, doc, got, problem = None, None, {}, e
        if status == 201:
            verb = "Drafted" if draft else "Sent"
            return f"{verb} {title!r} (email {doc.get('id')}, {doc.get('status')})."
        code = doc.get("code") if isinstance(doc, dict) else None
        if status == 400 and code == "email_duplicate":
            return f"Skipped {title!r}: Buttondown already has this email."
        if status is not None and status != 429 and status < 500:
            detail = doc.get("detail") if isinstance(doc, dict) else None
            raise RuntimeError(f"HTTP {status} {code or ''} {detail or ''}".strip())
        problem = problem if status is None else f"HTTP {status}"
        if attempt < 3:
            time.sleep(wait(got.get("Retry-After"), RETRY_DELAY * attempt))
        # A timeout or server error can hide a send that worked. Check before trying again.
        if status != 429 and not draft and already_sent(post, auth):
            return f"Sent {title!r} (confirmed after {problem})."
    raise RuntimeError(f"gave up after 3 tries ({problem})")


def send():
    posts = json.loads(os.environ.get("NEW_POSTS") or "[]")
    if not posts:
        print("No new posts to email.")
        return 0
    key = os.environ.get("BUTTONDOWN_API_KEY", "").strip()
    if not key:
        note("notice", "No BUTTONDOWN_API_KEY secret, so no emails for: "
             + ", ".join(p["title"] for p in posts))
        return 0
    draft = os.environ.get("EMAIL_DRAFT", "").strip().lower() == "true"
    failed = 0
    for post in posts:
        try:
            result = email(post, key, draft)
        except (OSError, RuntimeError) as e:
            note("error", f"Couldn't email {post['title']!r}: {e}")
            failed += 1
            continue
        print(result)
        append("GITHUB_STEP_SUMMARY", f"- {result}")
    return 1 if failed else 0


def main(argv):
    if argv[:1] == ["plan"]:
        return plan(argv[1] if len(argv) > 1 else "public")
    if argv[:1] == ["send"]:
        return send()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
