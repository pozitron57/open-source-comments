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
    - combined star growth in the latest N days,
    - latest commit date,
    - creation date,
    - license.

- Historical repository-derived data are stored in `apigh/history.json`. It keeps
  only value changes for the fields used by the page (`stars`, `stars_total`,
  `stars_github`, `stars_gitlab`, `open_issues`, `created`, `license`,
  `last_commit`) instead of storing raw API
  responses for every repository every day.

- `yaml_2_js.py` converts `data.yaml` to `data.js` (it defines two variables
  — `osc_data` and `cols`).

- `index.html` reads `data.js` and parses it to the html table using
  [datatables.js](https://github.com/DataTables/DataTables).

- `plot-stars.py` reads `apigh/history.json`, plots stars vs. time for selected
  projects, and writes `stars-v-date.svg`.

- The webpage is updated daily via `cron`. `updater.sh` runs `get_data.py`,
  `md_to_html.py`, `yaml_2_js.py`, and `plot-stars.py`, then deploys the
  updated files and pushes the repository.

## Dependencies

Install Python dependencies with:

```bash
python3 -m pip install -r requirements.txt
```

## How to view the page locally

Clone the repo and open `index.html` in your browser. 
To change it, edit `index.md` and run `python3 md_to_html.py`. 
It will overwrite existing `index.html`.

After modifying `data.yaml`, run `python3 yaml_2_js.py`.
It will update the `data.js` file.

## TODO

- Check and add the information to make the table useful.
  I would appreciate adding a missing demo.

- Improve the python code.

- `get_data.py`: retry transient repository API errors.

- Show column descriptions on mouse over.

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
