# Open-source self-hosted comments

Comparison table for open-source self-hosted commenting servers
([lisakov.com/projects/open-source-comments/](https://lisakov.com/projects/open-source-comments/)).
Inspired by [staticsitegenerators.net](http://staticsitegenerators.net). 

## Workflow

- The data are stored in `data.yaml`. This file is edited manually.

- `get_gh_data.py`:
  - creates `apigh/<YYYY-MM-DD>/` directory if does not exist;
  - downloads (using system `curl`)
    `https://api.github.com/repos/:user/:repo` and 
    `https://api.github.com/repos/:user/:repo/commits/master` to the created
    directory;
  - reads these files and updates `data.yaml` for the following:
    - Github stars,
    - Github stars in the latest N days,
    - latest commit date,
    - creation date,
    - license.

- `yaml_2_js.py` converts `data.yaml` to `data.js` (it defines two variables
  — `osc_data` and `cols`).

- `index.html` reads `data.js` and parses it to the html table using
  [datatables.js](https://github.com/DataTables/DataTables).

- The webpage is updated daily at 17:00 UTC via `cron`. `updater.sh`
  runs `get_gh_data.py`, then `yaml_2_js.py`, then deploys the updated files,
  then updates the repo.

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

- `get_gh_data.py`: retry to get the api data if response contains
  `"message": "Server Error"`.

- Show column descriptions on mouse over.

- Where do I find a number of opened and closed issues? For example,
  https://api.github.com/users/posativ/isso has `open_issues_count` and
  `open_issues`, both equal to 131, whereas there are 110 issues and 21 PR.

- ~~`apigh/<date>` folders store a lot of information which is never used.
  Need to extract only needed info from the files and remove the rest.~~
  
- ~~Plot stars vs. time for ~10 top commenting systems. Update the plot daily
  automatically.~~

- Get rid of yaml, convert data.yaml to data.json

## Contribution

Contributions are welcome.
Fork the repo and send PR,
submit an issue,
or leave a
[comment](https://lisakov.com/projects/open-source-comments/#isso-thread)
at the website.
