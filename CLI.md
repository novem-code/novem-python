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


## Checking a share or a tag
A `-s`/`-t` that names a target but gives neither `-C` nor `-D` asks whether
that target is already there. Nothing is printed and the exit code is the
answer: `0` when every named share/tag is present, `1` otherwise (with the
misses on stderr), so it drops straight into a shell conditional.
```bash
  # is this plot public?
  novem -p plot_name -s public && echo "yes"

  # every tag must be present for the check to pass
  novem -p plot_name -t fav,+demo || echo "not fully tagged"

  # works for the coding resources too
  novem -s my-space -s +acme~crew
```


## Coding resources: spaces, repos, computers, images
`-c` selects a computer and nothing else. The config file it used to name now
requires `--config` (an alias for `--config-path`) — `-c` was the one flag
whose two meanings could legitimately appear in the same command, and guessing
wrong there picks the wrong credentials.

The other three do double duty:

| flag | selects   | everyday meaning                 |
|------|-----------|----------------------------------|
| `-s` | spaces    | share group (`-s public -C`)     |
| `-r` | repos     | read path to stdout (`-r url`)   |
| `-i` | images    | `--input` upload dir (with `-R`) |

The rule: when nothing else claims the invocation (no `-p`/`-g`/`-m`/`-d`/`-j`/
`-c` selector and no standalone command like `--init` or `--get`), the *first*
occurrence of one of these flags selects the resource — every later occurrence
keeps its everyday meaning. Long forms `--space`, `--repo`, `--computer` and
`--image` always work.

```bash
  # list your spaces / repos / computers / images
  novem -s
  novem -r
  novem -c
  novem -i

  # read the clone url of a repo (first -r selects, second -r reads)
  novem -r repo_name -r url

  # create a space and share it with the public — each -C covers one
  # action, so this creates the space AND adds the share in one line
  novem -s space_name -C -s public -C

  # several writes in one line
  novem -c box_name -C -w config/cpu 4 -w config/memory 4Gi -w status online

  # upload a file into a space, read it back, delete it
  novem -s space_name -w content/data.csv @data.csv
  novem -s space_name -r content/data.csv
  novem -s space_name -e content/notes.md      # edit in $EDITOR

  # create a computer, size it, boot it, watch it
  novem -c box_name -C --image @novem/base -w config/cpu 4 -w config/memory 4Gi
  novem -c box_name -w status online
  novem -c box_name -r status
  novem -c box_name -r log

  # run a command on it, or attach a shell
  novem -c box_name -R -- ls -la /var/log
  novem -c box_name -A

  # inspect an image built from one of your repos
  novem -i image_name -r status
  novem -i image_name -r labels
```

Images are derived from their source repo (one appears whenever a repo has
been built) and cannot be created or deleted directly — everything else
(shares, tags, `-w name`, `-r ...`) works like the other resources.

### Running commands and attaching a shell
`-R` runs a workload and `-A` attaches an interactive shell. Everything after a
standalone `--` is the invocation to run, passed through verbatim:

```bash
  # one-off command; arguments survive without shell re-parsing, and the
  # exit code is the command's own
  novem -c box_name -R -- python3 -c 'print(1+1)'

  # stdin is piped through
  cat data.csv | novem -c box_name -R -- wc -l

  # follow a log — a long-running command, not a separate feature
  novem -c box_name -R -- tail -f /var/log/app.log

  # interactive shell
  novem -c box_name -A
```

Both need the computer to be running, and both wait while it finishes booting
rather than failing immediately. A command killed by a signal reports
`128 + signal`, the way a shell does.

`--image` follows the same first-selector rule as the short flags: on its own
it selects an image, and once a resource is selected it sets that resource's
image.

```bash
  novem --image                       # list your images
  novem --image image_name -r status  # inspect one
  novem -c box_name --image @novem/base   # set the computer's image
  novem -c box_name --image               # read it back
```

Because plot/grid/mail/doc/job selectors always win, existing invocations are
unchanged: `novem -p plot_name -s public -C` still shares a plot, and
`novem -j job_name -R -i data/` still uploads a directory to a job run.

With `-O org -G group`, a *bare* code selector lists what is shared with that
group (a valued one keeps its everyday meaning, so `-i ./data` is still an
input directory there):

```bash
  novem -O org_name -G group_name -s    # spaces shared with the group
  novem -O org_name -G group_name -r    # repos shared with the group
  novem -O org_name -G group_name -c    # computers shared with the group
  novem -O org_name -G group_name -i    # images shared with the group
```

A valued flag in group context is reserved for future per-resource deep
dives (`-O org -G group -r repo_name -r url`) and currently does nothing.


## Invitations
`novem --invites` is your inbox. It lists everything pending: inbound group
and organisation invitations, inbound connection requests, your own personal
invites still awaiting an answer, and your active invite URLs.

```bash
  # list every pending invitation
  novem --invites

  # accept / reject — one endpoint answers them all, connection
  # requests (a bare @username) included
  novem --invites +org_name~group_name --accept
  novem --invites @username --accept
  novem --invites @username --reject

  # invite a user to a group (requires -G, and -O for org groups)
  novem -O org_name -G group_name --invite username
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
