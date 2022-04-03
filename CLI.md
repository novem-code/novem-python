# The novem command-line interface (CLI)
The novem cli provides a simple and easy way to interact with the novem service
from the command line. Below is a set of examples followed by some details.

For a shorthand overview you can always use the `-h` or `--help` commands

## Examples
```bash
  # create a new line chart with no data
  novem -p test_chart -t line

  # write data to the line chart, three different ways
  novem -p test_chart -w data @data.csv                   # explicitly specify file and endpoint
  cat data.csv | novem -p test_chart -w data              # send stdin to endpoint
  cat data.csv | novem -p test_chart                      # send stdin to default endpoint (/data)

  # write description from markdown file
  cat desc.md | novem -p test_plot -w description         # send content from stdin to /description

  # write caption from file
  cat caption.md | novem -p test_plot -w config/caption   # send content from stdin to /config/caption

  # create a plot and open the url with chrome on linux (use open for mac)
  cat data.csv | novem -p plot_name -t line -r url | xdg-rpen

  # Create a new view and have the browser show it, then create a new line chart and display it in
  # the view
  novem -v default_view -r url | xdg-rpen                                     # create the view
  cat data.csv | novem -p plot_name -t line -r url | novem -v default_view    # create chart and show

  # list all plots with a detailed view
  novem -p -l

  # delete a plot
  novem -p old_plot_name -D

  # make a plot public
  novem -p plot_name -s public

  # make a plot private
  novem -p plot_name -s public -D

  # share a plot with a usergroup
  novem -p plot_name -s @username~groupname

  # unshare a plot with a usergroup
  novem -p plot_name -s @username~groupname -D

  # share a plot with a org-group
  novem -p plot_name -s +orgname~groupname

  # unshare a plot with a org-group
  novem -p plot_name -s +orgname~groupname -D
```
