# Open-source self-hosted comments

A [table](https://lisakov.com/projects/open-source-comments/) of open-source
self-hosted *(mostly)* commenting servers.

The data are stored in `data.yaml`. `yaml_2_js.py` converts `YAML` to
`js`-arrays in `data.js` so it can be loaded to
[datatables.js](https://github.com/DataTables/DataTables).

`get_gh_data.py`:
  - creates `apigh/<YYYY-MM-DD>/` directory if does not exist;
  - downloads (using system `wget`);
    `https://api.github.com/repos/:user/:repo` and 
    `https://api.github.com/repos/:user/:repo/commits/master` inside the
    created dir;
  - reads these files and updates `data.yaml` for the following:
    - github stars,
    - creation date,
    - last commit date,
    - license.

# TODO

- Foremost: check/add the information to make the table useful. I'd appreciate
  adding a missing demo. Sometimes it's not easy to find. For example,
  [Juvia](https://github.com/phusion/juvia) is rated over 1000 stars on github,
  but I spent an hour to find couple currently working instances. I even found
  a recent (2018) [post](https://blog.backslasher.net/disqus.html) about
  switching from Juvia to Disqus!

- Simplify and improve the python code.

- Check grammar in this README.

# Contribution

Contributions are welcome. Fork the repo and send PR. Want to add something
but don't feel like sending PR? Let me know by submitting an issue or leave a
[comment](https://lisakov.com/projects/open-source-comments/#isso-thread)[^1] at
the website. It currently uses [isso](https://github.com/posativ/isso).
