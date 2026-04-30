Shay Palachy-Affek's personal web site at [http://shaypal5.github.io/](http://shaypal5.github.io/).

The site uses the [Beautiful Jekyll](http://deanattali.com/beautiful-jekyll) theme provided by Dean Attali.

## Local Jekyll Build

Use Ruby 3.3.0 with Bundler 2.7.2, matching `.ruby-version` and
`Gemfile.lock`:

```bash
RBENV_VERSION=3.3.0 bundle install
RBENV_VERSION=3.3.0 bundle exec jekyll build
```

On macOS, plain `bundle exec jekyll build` may select system Ruby and fail if
Bundler 2.7.2 is not installed there.
