# Open-source self-hosted comments

Comparison table for open-source self-hosted commenting servers 
([lisakov.com/projects/open-source-comments/](https://lisakov.com/projects/open-source-comments/)).
Inspired by [staticsitegenerators.net](http://staticsitegenerators.net). 

# Workflow

- The data are stored in `data.yaml`.

- `get_gh_data.py`:
  - creates `apigh/<YYYY-MM-DD>/` directory if does not exist;
  - downloads (using system `curl`);
    `https://api.github.com/repos/:user/:repo` and 
    `https://api.github.com/repos/:user/:repo/commits/master` to the created directory;
  - reads these files and updates `data.yaml` for the following:
    - github stars,
    - last commit date,
    - creation date,
    - license.

- `yaml_2_js.py` converts `data.yaml` to `data.js` (it defines two variables). 

- `index.html` reads it using
  [datatables.js](https://github.com/DataTables/DataTables).

- The webpage is updated daily at 17:00 UTC using `cron`. `updater.sh` collects
  the information via Github API, run `get_gh_data.py`, then `yaml_2_js.py`,
  then deploys the updated files, then updates the repo.


# TODO

- Check and add the information to make the table useful. I'd appreciate adding
  a missing demo. Sometimes it's not easy to find. For example,
  [Juvia](https://github.com/phusion/juvia) is rated over 1000 stars on github,
  but I spent an hour to find a couple of currently working instances. I even
  found a recent (2018) [post](https://blog.backslasher.net/disqus.html) about
  switching from Juvia to Disqus!

- Improve the python code.

- Add badges to show the change in stars during last 30 days or so. Just like
  at https://www.staticgen.com/. I'am going to add a few lines to
  `get_gh_data.py` to compare current value with the previous one, time
  difference specified. Is it a proper way of doing it? 

- Where do I find a number of opened and closed issues? For example,
  https://api.github.com/users/posativ/isso has `open_issues_count` and
  `open_issues`, both equal to 131, whereas there are 110 issues and 21 PR.

- `apigh/<date>` folders store a lot of information which is never used.
  Need to write a python script to extract only needed info from the files
  and delete the rest.

# Contribution

Contributions are welcome. Fork the repo and send PR. Want to add something
but don't feel like sending PR? Let me know by submitting an issue or leave a
[comment](https://lisakov.com/projects/open-source-comments/#isso-thread) at
the website. It currently uses [isso](https://github.com/posativ/isso).
