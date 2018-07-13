# Open-source self-hosted comments

A table of open-source self-hosted commenting servers
(https://lisakov.com/projects/open-source-comments/)
to make the choice easier.

The data are stored in `data.yaml`. `yml2js.py` converts `YAML` to
`js`-arrays in `data.js` so it can be loaded to
[datatables.js](https://github.com/DataTables/DataTables).

# TODO

- Foremost: check/add the information to make the table useful. I'd appreciate
  adding a missing demo. Sometimes it's not easy to find. For example,
  [Juvia](https://github.com/phusion/juvia) is rated over 1000 stars on github,
  but I spent an hour to find couple currently working instances. I even found
  a recent (2018) [post](https://blog.backslasher.net/disqus.html) about
  switching from Juvia to Disqus!

- Script to parse amount of github stars and write to `data.yaml`. See
  [github-stars](https://github.com/stretchr/github-stars).

- Simplify and improve python code.

# Contribution

Any contribution on adding commenting system other information are welcome.
Please fork the repository and push changes to the `data.yaml` file. Want
another column? Let me know by submitting an issue.
