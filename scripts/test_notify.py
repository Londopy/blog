#!/usr/bin/env python3
"""Tests for notify.py, against a local stand-in for the live site and Buttondown.

    python scripts/test_notify.py

Offline and standard library only. Nothing here reaches the real API.
"""
import contextlib
import http.server
import io
import json
import os
import socket
import sys
import tempfile
import threading
import unittest
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import notify  # noqa: E402

BASE = "https://example.test/blog/posts"


def post(slug, published):
    return {
        "slug": slug, "title": f"Post {slug}", "url": f"{BASE}/{slug}/",
        "description": f"All about {slug}.", "published": published,
        "reading_time_minutes": 5, "summary": "...", "tags": [], "word_count": 900,
        "cover": {"url": f"{BASE}/{slug}/cover.png", "alt": f"{slug} cover", "width": 1200, "height": 630},
    }


A = post("a", "2026-09-24T09:00:00-07:00")
B = post("b", "2026-10-01T09:00:00-07:00")
C = post("c", "2026-10-08T09:00:00-07:00")
D = post("d", "2026-10-15T09:00:00-07:00")


class Stand(http.server.BaseHTTPRequestHandler):
    """Serves the live posts.json and Buttondown's /v1/emails from class-level state."""
    live = (200, {"data": []})
    listing = []      # emails Buttondown already has
    replies = []      # queued (status, body) answers to POST /v1/emails
    seen = []         # (method, path, headers, body) of every request

    def answer(self, status, doc):
        raw = json.dumps(doc).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        url = urlparse(self.path)
        Stand.seen.append(("GET", self.path, {k.lower(): v for k, v in self.headers.items()}, None))
        if url.path == "/live/posts.json":
            return self.answer(*Stand.live)
        if url.path == "/v1/emails":
            subject = parse_qs(url.query).get("subject", [""])[0]
            hits = [e for e in Stand.listing if subject in e["subject"]]
            return self.answer(200, {"results": hits, "next": None, "previous": None, "count": len(hits)})
        self.answer(404, {"detail": "Not found."})

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        Stand.seen.append(("POST", self.path, {k.lower(): v for k, v in self.headers.items()}, payload))
        status, doc, *went_out = Stand.replies.pop(0) if Stand.replies else (201, None)
        if went_out:  # the send worked, but the answer says otherwise
            Stand.listing.append({"id": "em_late", "subject": payload["subject"], "status": "sent",
                                  "canonical_url": payload["canonical_url"], "metadata": payload["metadata"]})
        self.answer(status, doc if doc is not None else {"id": "em_1", "status": payload["status"]})

    def log_message(self, *args):
        pass


class Case(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Stand)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.root = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        Stand.live, Stand.listing, Stand.replies, Stand.seen = (200, {"data": []}), [], [], []
        notify.API, notify.RETRY_DELAY = f"{self.root}/v1", 0
        self.tmp = tempfile.TemporaryDirectory()
        self.output = os.path.join(self.tmp.name, "output")
        self.summary = os.path.join(self.tmp.name, "summary")
        self.env = {"GITHUB_OUTPUT": self.output, "GITHUB_STEP_SUMMARY": self.summary,
                    "LIVE_POSTS": f"{self.root}/live/posts.json"}
        self.saved = {k: os.environ.pop(k, None) for k in (
            "GITHUB_ACTIONS", "GITHUB_OUTPUT", "GITHUB_STEP_SUMMARY", "LIVE_POSTS", "EMAIL_POST",
            "NEW_POSTS", "BUTTONDOWN_API_KEY", "EMAIL_DRAFT")}

    def tearDown(self):
        for k, v in self.saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
        self.tmp.cleanup()

    def run_notify(self, *argv, **env):
        os.environ.update({**self.env, **env})
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = notify.main(list(argv))
        return code, out.getvalue()

    def plan(self, built, **env):
        site = os.path.join(self.tmp.name, "public")
        os.makedirs(os.path.join(site, "api", "v1"), exist_ok=True)
        with open(os.path.join(site, "api", "v1", "posts.json"), "w", encoding="utf-8") as f:
            json.dump({"meta": {}, "data": built}, f)
        code, text = self.run_notify("plan", site, **env)
        with open(self.output, encoding="utf-8") as f:
            lines = f.read().splitlines()
        self.assertEqual(len(lines), 1, lines)
        name, value = lines[0].split("=", 1)
        self.assertEqual(name, "new_posts")
        return code, [p["slug"] for p in json.loads(value)], text

    def send(self, posts, **env):
        return self.run_notify("send", NEW_POSTS=json.dumps([notify.brief(p) for p in posts]), **env)

    def posts_sent(self):
        return [s for s in Stand.seen if s[0] == "POST"]


class Plan(Case):
    def test_the_new_post_is_the_one_only_the_build_has(self):
        Stand.live = (200, {"data": [A, B]})
        self.assertEqual(self.plan([C, B, A])[:2], (0, ["c"]))

    def test_new_posts_come_oldest_first(self):
        Stand.live = (200, {"data": [A]})
        self.assertEqual(self.plan([C, B, A])[1], ["b", "c"])

    def test_nothing_new(self):
        Stand.live = (200, {"data": [B, A]})
        code, slugs, text = self.plan([B, A])
        self.assertEqual((code, slugs), (0, []))
        self.assertIn("No new posts", text)

    def test_no_live_api_yet_means_no_emails(self):
        Stand.live = (404, {"detail": "Not found"})
        code, slugs, text = self.plan([B, A])
        self.assertEqual((code, slugs), (0, []))
        self.assertIn("notice:", text)

    def test_live_site_erroring_means_no_emails(self):
        Stand.live = (503, {})
        code, slugs, text = self.plan([B, A])
        self.assertEqual((code, slugs), (0, []))
        self.assertIn("warning:", text)
        self.assertEqual(len(Stand.seen), 3)  # tried three times

    def test_live_site_unreachable_means_no_emails(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            closed = s.getsockname()[1]
        code, slugs, text = self.plan([B, A], LIVE_POSTS=f"http://127.0.0.1:{closed}/posts.json")
        self.assertEqual((code, slugs), (0, []))
        self.assertIn("warning:", text)

    def test_too_many_at_once_means_no_emails(self):
        code, slugs, text = self.plan([D, C, B, A])
        self.assertEqual((code, slugs), (0, []))
        self.assertIn("4 posts are new at once", text)

    def test_email_post_picks_one_without_asking_the_live_site(self):
        self.env.pop("LIVE_POSTS")
        self.assertEqual(self.plan([C, B, A], EMAIL_POST="b")[:2], (0, ["b"]))
        self.assertEqual(Stand.seen, [])

    def test_email_post_with_an_unknown_slug(self):
        code, slugs, text = self.plan([B, A], EMAIL_POST="nope")
        self.assertEqual((code, slugs), (1, []))
        self.assertIn("error:", text)

    def test_annotations_in_actions(self):
        Stand.live = (404, {})
        text = self.plan([A], GITHUB_ACTIONS="true")[2]
        self.assertIn("::notice::", text)


class Send(Case):
    def test_nothing_to_send(self):
        self.assertEqual(self.run_notify("send", NEW_POSTS="")[0], 0)
        self.assertEqual(Stand.seen, [])

    def test_no_api_key_sends_nothing(self):
        code, text = self.send([C])
        self.assertEqual(code, 0)
        self.assertIn("No BUTTONDOWN_API_KEY", text)
        self.assertEqual(Stand.seen, [])

    def test_sends_the_email(self):
        code, text = self.send([C], BUTTONDOWN_API_KEY="k123")
        self.assertEqual(code, 0, text)
        (_, get_path, get_headers, _), (_, path, headers, payload) = Stand.seen
        self.assertEqual(parse_qs(urlparse(get_path).query)["subject"], ["Post c"])
        self.assertEqual(path, "/v1/emails")
        self.assertEqual(headers["authorization"], "Token k123")
        self.assertEqual(headers["x-api-version"], notify.API_VERSION)
        self.assertEqual(get_headers["authorization"], "Token k123")
        self.assertEqual(headers["x-buttondown-live-dangerously"], "true")
        self.assertEqual(payload["subject"], "Post c")
        self.assertEqual(payload["status"], "about_to_send")
        self.assertEqual(payload["canonical_url"], C["url"])
        self.assertEqual(payload["image"], C["cover"]["url"])
        self.assertEqual(payload["archival_mode"], "disabled")
        self.assertEqual(payload["metadata"]["slug"], "c")
        self.assertIn(f'href="{C["url"]}"', payload["body"])
        self.assertIn("Sent 'Post c'", text)

    def test_skips_a_post_buttondown_already_sent(self):
        Stand.listing = [{"id": "em_0", "subject": "Post c", "status": "sent", "canonical_url": C["url"]}]
        code, text = self.send([C], BUTTONDOWN_API_KEY="k")
        self.assertEqual(code, 0)
        self.assertEqual(self.posts_sent(), [])
        self.assertIn("already sent", text)

    def test_a_draft_or_failed_email_doesnt_count_as_sent(self):
        Stand.listing = [
            {"id": "em_0", "subject": "[Preview] Post c", "status": "draft", "canonical_url": C["url"]},
            {"id": "em_9", "subject": "Post c", "status": "errored", "metadata": {"slug": "c"}},
        ]
        self.assertEqual(self.send([C], BUTTONDOWN_API_KEY="k")[0], 0)
        self.assertEqual(len(self.posts_sent()), 1)

    def test_draft_mode_makes_a_preview_draft(self):
        code, text = self.send([C], BUTTONDOWN_API_KEY="k", EMAIL_DRAFT="true")
        self.assertEqual(code, 0)
        [(_, _, headers, payload)] = Stand.seen  # no duplicate check for a preview
        self.assertEqual(payload["status"], "draft")
        self.assertEqual(payload["subject"], "[Preview] Post c")
        self.assertNotIn("x-buttondown-live-dangerously", headers)
        self.assertIn("Drafted", text)

    def test_buttondown_calling_it_a_duplicate_is_a_skip(self):
        Stand.replies = [(400, {"code": "email_duplicate", "detail": "Duplicate."})]
        code, text = self.send([C], BUTTONDOWN_API_KEY="k")
        self.assertEqual(code, 0)
        self.assertIn("already has this email", text)

    def test_a_rejected_email_fails_the_job(self):
        Stand.replies = [(422, {"detail": [{"msg": "bad"}]})]
        code, text = self.send([C], BUTTONDOWN_API_KEY="k")
        self.assertEqual(code, 1)
        self.assertIn("error: Couldn't email 'Post c': HTTP 422", text)

    def test_retries_after_a_server_error(self):
        Stand.replies = [(502, {})]
        code, text = self.send([C], BUTTONDOWN_API_KEY="k")
        self.assertEqual(code, 0, text)
        self.assertEqual(len(self.posts_sent()), 2)

    def test_doesnt_resend_when_the_error_hid_a_send(self):
        Stand.replies = [(504, {}, "went out")]
        code, text = self.send([C], BUTTONDOWN_API_KEY="k")
        self.assertEqual(code, 0, text)
        self.assertEqual(len(self.posts_sent()), 1)
        self.assertIn("confirmed after HTTP 504", text)

    def test_one_failure_doesnt_stop_the_rest(self):
        Stand.replies = [(422, {"detail": "bad"}), (201, None)]
        code, text = self.send([B, C], BUTTONDOWN_API_KEY="k")
        self.assertEqual(code, 1)
        self.assertEqual([p[3]["subject"] for p in self.posts_sent()], ["Post b", "Post c"])
        self.assertIn("Sent 'Post c'", text)


class Body(unittest.TestCase):
    def test_escapes_the_text_and_links_the_post(self):
        p = dict(C, description='Tags like <b> & "quotes"', cover=dict(C["cover"], alt='a "cover"'))
        html = notify.body(notify.brief(p))
        self.assertTrue(html.startswith("<!-- buttondown-editor-mode: fancy -->"))
        self.assertIn("Tags like &lt;b&gt; &amp; &quot;quotes&quot;", html)
        self.assertIn('alt="a &quot;cover&quot;"', html)
        self.assertEqual(html.count(f'href="{C["url"]}"'), 2)
        self.assertIn("5 min read", html)

    def test_without_a_cover(self):
        html = notify.body(dict(notify.brief(C), cover=None))
        self.assertNotIn("<img", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
