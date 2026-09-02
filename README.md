# Open-source self-hosted comments

Comparison table for open-source self-hosted commenting servers
([lisakov.com/projects/open-source-comments/](https://lisakov.com/projects/open-source-comments/)).
Inspired by [staticsitegenerators.net](http://staticsitegenerators.net). 

## Workflow

- The data are stored in `data.yaml`. This file is edited manually.

- `get_data.py` reads the GitHub and GitLab repositories from `data.yaml`,
  fetches the current repository metadata and latest commit through their APIs, then
  updates `data.yaml` for the following:
    - displayed stars from the repository with the higher star count,
    - combined star growth over the last 30 days,
    - latest commit date,
    - creation date,
    - license.

- Historical repository-derived data are stored in `apigh/history.json`. It keeps
  only value changes for the fields used by the page (`stars`, `stars_total`,
  `stars_github`, `stars_gitlab`, `open_issues`, `created`, `license`,
  `last_commit`) instead of storing raw API
  responses for every repository every day.

- `yaml_2_js.py` converts `data.yaml` to `data.js` (it defines three variables
  — `osc_data`, `cols` and `col_keys`).

- `history_2_js.py` reduces `apigh/history.json` to `star-history.js`, the star
  series the interactive chart reads: only the `stars` field, without the
  samples `plot-stars.py` also rejects, downsampled to the points that are
  visible at chart resolution.

- `index.html` is the page structure; `index.md` holds all of its prose.
  `md_to_html.py` renders each `<!--osc:NAME-->` section of `index.md` into the
  matching slot in `index.html`, and computes the system and attribute counts
  from the data. The table, the column popover, the project record and the
  chart are drawn by `js/osc.js` (with `js/osc-lib.js`) from `data.js` and
  `star-history.js` — plain scripts, no framework and no build step.

- `plot-stars.py` reads `apigh/history.json`, plots stars vs. time for selected
  projects, and writes `stars-v-date.svg`. The page shows the interactive chart
  instead and falls back to this SVG inside `<noscript>`.

- The webpage is updated daily via `cron`. `updater.sh` runs `get_data.py`,
  `md_to_html.py`, `yaml_2_js.py`, `plot-stars.py`, and `history_2_js.py`, then
  deploys the updated files and pushes the repository. Repository redirects are
  followed automatically and their canonical URLs are saved back to
  `data.yaml`.

- The chain from `cron` to the webroot is: the crontab entry names
  `~/.local/bin/open-source-comments-update`, which is `cron_wrapper.sh`
  installed under that name; it sets `OSC_SCRIPT_DIR`
  (`~/.local/share/open-source-comments`) and hands over to the `updater.sh`
  installed there; that operates on the checkout in `~/open-source-comments`
  and deploys to `/var/www/lisakov.com/projects/open-source-comments`.

- The scripts are executed from `OSC_SCRIPT_DIR` rather than from the checkout
  so that the `git pull` at the start of a run cannot replace code while it is
  executing. `updater.sh` reinstalls the pulled Python there on every run, so a
  new build step takes effect immediately. It cannot do that for itself — bash
  is already reading the installed copy — so if `updater.sh` changed it stops
  and asks for `./install_scripts.sh` to be run once.

- `install_scripts.sh` installs every tracked script into `OSC_SCRIPT_DIR` and
  the wrapper into `OSC_BIN_DIR` (`~/.local/bin`). It is idempotent and reports
  what it changed. Run it after changing `updater.sh`, `cron_wrapper.sh` or
  itself; the Python looks after itself.

- Any non-routine event for an individual repository — including an API retry,
  redirect, invalid response, suspicious identity change, or persistent request
  failure — sends an email immediately. Affected repositories retain their last
  trusted values and get an asterisk next to the star count; its tooltip contains
  the warning date and details. Other repositories continue to update and the
  page is still published. A daily star decrease is treated as non-routine only
  when it reaches 20 stars; smaller decreases do not produce an asterisk. The
  marker is removed after the next completely clean update for that repository.

- `updater.sh` exits on a failed step and writes the failure to stderr and the
  system log. It also sends a direct email to `lisakov57@gmail.com`; set
  `OSC_ALERT_EMAIL` in the cron environment to override that address.
  Cron's standard `MAILTO` remains supported as an alternative. Concurrent runs
  are rejected, generated files are backed up during the transaction, all
  outputs are validated before commit/push, and deployment starts only after a
  successful push. A global failure rolls generated files back and prevents
  deployment.

- Generated YAML history, JavaScript, HTML, and SVG files use atomic replacement
  so an interrupted write does not leave a truncated production artifact.

- If the server's system DNS is unavailable, the updater starts a loopback-only
  CONNECT proxy that resolves hosts through a fallback DNS server. Git and API
  HTTPS traffic keep normal TLS hostname verification. The first activation
  during a continuous DNS outage sends an email; later runs only log it. The
  notification is armed again after system DNS recovers.

## Dependencies

Install Python dependencies with:

```bash
python3 -m pip install -r requirements.txt
```

## How to view the page locally

Clone the repo and open `index.html` in your browser — the page has no build
step and no module imports, so it works straight from the filesystem. Some
browsers refuse to load fonts over `file://`; the page then falls back to a
system sans and is otherwise unchanged.

The page loads nothing from a third party. Everything but the comment thread is
served from this directory; the thread comes from `comments.lisakov.com`, the
site's own Isso instance.

`css/fonts/archivo.woff2` is Archivo subset to the characters the page and
`data.yaml` actually render, with the variable weight axis clamped to the
400-800 the design uses — 18 kB rather than the 35 kB of the stock Latin subset.
`css/fonts/archivo-subset.txt` lists exactly what it covers, and
`validate_outputs.py` reports any character in `data.js` that falls outside it
(a fallback glyph, not a failure). Text outside that set — Cyrillic in comments,
for instance — renders in the reader's system sans, as it did before. To widen
the subset, request a new file from Google Fonts with the extra characters in
the `text=` parameter and update the `.txt` alongside it.

To preview it at the URL it has in production, run the lisakov.com Hexo site
with `hexo s`. The middleware that does it is `tools/hexo-osc-preview.js` in
this repository; the Hexo site keeps a short `scripts/osc-preview.js` that
requires it and passes in `serve-static`, so the behaviour is versioned here
rather than in that site, which is not a git repo. Point it at a different
checkout with `OSC_DIR=/path/to/open-source-comments hexo s`.

A Hexo `scripts/` file is dev-server tooling: it never becomes part of the
generated site, so `hexo generate` / `hexo deploy` has nothing to publish for
it. Pulling this repository is what updates the preview.

That script also proxies the Isso API, so the real comment thread loads in the
local preview — Isso answers CORS only for the lisakov.com origin, and the
proxy makes the call same-origin instead. It is read-only: posting, editing and
voting are refused locally so a preview cannot write to the live comment
database. Turn the proxy off with `OSC_ISSO_PROXY=off`.

To change the prose, edit `index.md` and run `python3 md_to_html.py`. Sections
in `index.md` are delimited by `<!--osc:NAME-->` markers and land in the
matching `<!--osc:NAME-->…<!--/osc:NAME-->` slot in `index.html`, which the
script overwrites.

After modifying `data.yaml`, run `python3 yaml_2_js.py` to update `data.js`,
and `python3 history_2_js.py` to update `star-history.js`.

Run reliability tests with:

```bash
python3 -m unittest -v test_get_data.py test_reliability.py
```

## TODO

- Check and add the information to make the table useful.
  I would appreciate adding a missing demo.

- Where do I find a number of opened and closed issues? For example,
  https://api.github.com/users/posativ/isso has `open_issues_count` and
  `open_issues`, both equal to 131, whereas there are 110 issues and 21 PR.

- ~~`apigh/<date>` folders store a lot of information which is never used.
  Need to extract only needed info from the files and remove the rest.~~
  
- ~~Plot stars vs. time for several top commenting systems. Update the plot daily
  automatically.~~

- Get rid of yaml, convert data.yaml to data.json

## Contribution

Contributions are welcome.
Fork the repo and send PR,
submit an issue,
or leave a
[comment](https://lisakov.com/projects/open-source-comments/#isso-thread)
at the website.
