# The novem command-line interface (CLI)
The novem cli provides a simple and easy way to interact with the novem service
from the command line. Below is a set of examples followed by some details.

For a shorthand overview you can always use the `-h` or `--help` commands, and
see [novem.io](https://novem.io) for the full documentation.

The resource you operate on is selected by a flag: `-p` plot, `-g` grid,
`-m` mail, `-d` doc, `-j` job. Most examples below use `-p`, but the same
options apply to the other resource types.


## Authentication
```bash
  # interactively set up a profile (username/password or token) in the config file
  novem --init

  # authenticate with an existing token instead
  novem --init token

  # one-off: pick a non-default profile, or pass a token directly
  novem --profile work -p my_chart
  novem --token <token> -p my_chart

  # the NOVEM_TOKEN / NOVEM_API_ROOT environment variables are also honoured
```


## Creating and writing visualisations
```bash
  # create a new line chart with no data (--type sets the chart type)
  novem -p test_chart --type line

  # write data to the chart, three different ways
  novem -p test_chart -w data @data.csv         # write a file to the /data endpoint
  cat data.csv | novem -p test_chart -w data     # send stdin to the /data endpoint
  cat data.csv | novem -p test_chart             # send stdin to the default (/data) endpoint

  # write description / caption from a markdown file via stdin
  cat desc.md    | novem -p test_chart -w description
  cat caption.md | novem -p test_chart -w config/caption

  # create a grid, a mail and a doc
  cat layout.txt | novem -g  dashboard
  cat body.md    | novem -m  welcome --subject "Hello" --to a@b.com
  cat report.md  | novem -d  q1_report
```


## Reading, listing and deleting
```bash
  # read a value (e.g. the public url) and open it in the browser
  novem -p plot_name -r url | xdg-open   # use `open` on macOS

  # create a chart and print its url in one go
  cat data.csv | novem -p plot_name --type line -r url

  # list all plots (use -l for ids only)
  novem -p
  novem -p -l

  # delete a plot
  novem -p old_plot_name -D
```


## Sharing
Add a share with `-C`, remove it with `-D`, and list current shares with a
bare `-s`.
```bash
  # list current shares
  novem -p plot_name -s

  # make a plot public / remove the public share
  novem -p plot_name -s public -C
  novem -p plot_name -s public -D

  # share / unshare with a user group
  novem -p plot_name -s @username~groupname -C
  novem -p plot_name -s @username~groupname -D

  # share / unshare with an org group
  novem -p plot_name -s +orgname~groupname -C
  novem -p plot_name -s +orgname~groupname -D
```


## Tagging
Tags work like shares: `-C` to add, `-D` to remove, bare `-t` to list. Multiple
tags can be comma-separated.
```bash
  # list current tags
  novem -p plot_name -t

  # add / remove tags
  novem -p plot_name -t fav -C
  novem -p plot_name -t fav,+demo -C
  novem -p plot_name -t fav -D
```


## Raw API access
```bash
  # read / write arbitrary api paths
  novem --get vis/plots/plot_name/url
  novem --post vis/plots/plot_name/data @data.csv
  novem --put  vis/plots/plot_name/config/type line
  novem --delete vis/plots/plot_name
```


## Inspecting structure
```bash
  # print the api tree for a visualisation
  novem -p plot_name --tree
```
