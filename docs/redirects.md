# Redirects and URL Aliases

This site uses [`jekyll-redirect-from`](https://github.com/jekyll/jekyll-redirect-from), which is included in the GitHub Pages gem and enabled in `_config.yml`.

## Policy

- Do not rename public URLs unless there is a clear user-facing reason.
- When a public page is renamed, keep the old URL working with `redirect_from`.
- Add redirects in the same PR that introduces the new public URL.
- Keep old URLs stable until redirect support is enabled and verified locally.
- Do not add redirects preemptively for pages that have not moved.

## Generated Public Pages

`talks.md`, `blog.md`, and `code.md` are generated from structured data:

- `data/talks.yml`
- `data/writing.yml`
- `data/projects.yml`

For those pages, add aliases to the data file's `front_matter` block, not to the generated Markdown file. Example:

```yaml
front_matter:
  layout: page
  title: Projects
  redirect_from:
    - /code.html
    - /code/
```

Then run:

```bash
python3 -m automation.cli courses render
python3 -m automation.cli courses validate
RBENV_VERSION=3.3.0 bundle exec jekyll build
```

## Hand-Authored Pages

For a hand-authored page, add `redirect_from` directly to the page front matter:

```yaml
---
layout: page
title: Projects
redirect_from:
  - /code.html
---
```

Prefer `.html` aliases for existing top-level pages because the current public URLs use that form in navigation. Add slash-form aliases only if that slash URL was also public or externally shared.

## Generated Teaching Pages

`teaching/*.md` pages are generated from `data/teaching/courses.yml`. For a renamed course slug, add aliases to the course entry:

```yaml
courses:
  - slug: deep-learning
    title: Deep Learning @ TAU
    redirect_from:
      - /teaching/deep-learning-legacy
      - /teaching/deep-learning-legacy.html
```

Do not add aliases that point at an existing public page. Validation rejects duplicate aliases and aliases that collide with live generated URLs.
