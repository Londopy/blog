#!/usr/bin/env python3
"""Check the built JSON API before it deploys.

    python scripts/check_api.py public

Walks every path in public/api/openapi.json (each post, tag and badge for the
templated ones), checks the file exists, and validates every JSON response
against the schema the OpenAPI document declares for it. Then cross-checks:
the API lists exactly the posts that were built as pages (so a scheduled post
can't leak early and a published one can't go missing), post HTML has no
relative URLs, and the feed, search index, posts.txt, latest.json and stats
agree with posts.json. Standard library only; exits 1 on any failure.
"""
import glob
import json
import os
import re
import sys
from urllib.parse import urlparse

DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")
JSON_TYPES = ("application/json", "application/feed+json")
TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


def validate(inst, schema, spec, where, errors):
    """The JSON Schema subset the OpenAPI document uses."""
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        return validate(inst, spec["components"]["schemas"][name], spec, where, errors)
    for sub in schema.get("allOf", []):
        validate(inst, sub, spec, where, errors)
    if "oneOf" in schema:
        hits = sum(1 for sub in schema["oneOf"] if not validate(inst, sub, spec, where, []))
        if hits != 1:
            errors.append(f"{where}: matches {hits} of oneOf")
    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(TYPES[t](inst) for t in types):
            errors.append(f"{where}: expected {schema['type']}, got {type(inst).__name__}")
            return errors
    if "const" in schema and inst != schema["const"]:
        errors.append(f"{where}: expected {schema['const']!r}, got {inst!r}")
    if "enum" in schema and inst not in schema["enum"]:
        errors.append(f"{where}: {inst!r} not in {schema['enum']}")
    if isinstance(inst, dict):
        for key in schema.get("required", []):
            if key not in inst:
                errors.append(f"{where}: missing {key}")
        props, extra = schema.get("properties", {}), schema.get("additionalProperties")
        for key, value in inst.items():
            if key in props:
                validate(value, props[key], spec, f"{where}.{key}", errors)
            elif isinstance(extra, dict):
                validate(value, extra, spec, f"{where}.{key}", errors)
    if isinstance(inst, list) and "items" in schema:
        for i, value in enumerate(inst):
            validate(value, schema["items"], spec, f"{where}[{i}]", errors)
    if TYPES["number"](inst):
        if "minimum" in schema and inst < schema["minimum"]:
            errors.append(f"{where}: {inst} < {schema['minimum']}")
        if "maximum" in schema and inst > schema["maximum"]:
            errors.append(f"{where}: {inst} > {schema['maximum']}")
    if isinstance(inst, str):
        if "pattern" in schema and not re.search(schema["pattern"], inst):
            errors.append(f"{where}: {inst!r} doesn't match {schema['pattern']}")
        if schema.get("format") == "date-time" and not DATETIME.match(inst):
            errors.append(f"{where}: not a date-time: {inst!r}")
        if schema.get("format") == "uri" and not re.match(r"^https?://", inst):
            errors.append(f"{where}: not an absolute URL: {inst!r}")
    return errors


def main(public):
    errors = []
    load = lambda rel: json.load(open(os.path.join(public, rel.lstrip("/")), encoding="utf-8"))
    spec = load("api/openapi.json")
    index = load("api/v1/index.json")
    version = index["meta"]["version"]
    base = urlparse(index["meta"]["self"]).path.removesuffix("/api/v1/index.json")

    if spec["info"]["version"] != version:
        errors.append(f"openapi.json is version {spec['info']['version']}, the index says {version}")
    listed = {e["path"].removeprefix(base) for e in index["data"]["endpoints"]}
    for p in sorted(listed ^ set(spec["paths"])):
        errors.append(f"{p}: in {'the index' if p in listed else 'openapi.json'} but not the other")

    posts = load("api/v1/posts.json")["data"]
    fill = {
        "slug": [p["slug"] for p in posts],
        "tag": [t["slug"] for t in load("api/v1/tags.json")["data"]],
    }
    checked = 0
    for path, item in spec["paths"].items():
        op = item["get"]
        params = re.findall(r"\{(\w+)\}", path)
        values = [None]
        if params:
            name = params[0]
            enum = next((p["schema"].get("enum") for p in op.get("parameters", []) if p["name"] == name), None)
            values = enum or fill[name]
        media, body = next(iter(op["responses"]["200"]["content"].items()))
        for value in values:
            rel = path.replace(f"{{{params[0]}}}", value) if params else path
            file = os.path.join(public, rel.lstrip("/"))
            if not os.path.isfile(file):
                errors.append(f"{rel}: missing")
                continue
            checked += 1
            if media not in JSON_TYPES:
                continue
            doc = load(rel)
            errors += validate(doc, body["schema"], spec, rel, [])
            if "meta" in doc and doc["meta"].get("self", "").removesuffix(rel) == doc["meta"].get("self"):
                errors.append(f"{rel}: meta.self is {doc['meta'].get('self')}")

    # the API lists exactly the posts that were built as pages
    built = {os.path.basename(os.path.dirname(f)) for f in glob.glob(os.path.join(public, "posts", "*", "index.html"))}
    if built != set(fill["slug"]):
        errors.append(f"posts.json has {sorted(fill['slug'])}, the site built {sorted(built)}")

    urls = [p["url"] for p in posts]
    for slug in fill["slug"]:
        html = load(f"api/v1/posts/{slug}.json")["data"]["content_html"]
        for rel in re.findall(r'(?:src|href)="(?!https?://|#|mailto:)[^"]*"', html):
            errors.append(f"posts/{slug}.json: relative URL left in content_html: {rel}")
    latest = load("api/v1/latest.json")["data"]
    if (latest or {}).get("slug") != (posts[0]["slug"] if posts else None):
        errors.append("latest.json isn't the first post in posts.json")
    feed = load("api/v1/feed.json")["items"]
    if [i["url"] for i in feed] != urls[: len(feed)] or (posts and not feed):
        errors.append("feed.json items don't follow posts.json")
    search = {i["url"] for i in load("api/v1/search.json")["data"]}
    errors += [f"search.json is missing {u}" for u in urls if u not in search]
    text = open(os.path.join(public, "api/v1/posts.txt"), encoding="utf-8").read()
    errors += [f"posts.txt is missing {u}" for u in urls if u not in text]
    if load("api/v1/stats.json")["data"]["posts"] != len(posts):
        errors.append("stats.json counts a different number of posts")

    for e in errors:
        print("FAIL", e)
    print(f"API check: {checked} files against {len(spec['paths'])} paths, "
          f"{len(posts)} posts, {len(fill['tag'])} tags: {'OK' if not errors else f'{len(errors)} problem(s)'}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "public"))
