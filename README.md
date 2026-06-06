
# novem - data visualisation for coders

A wrapper library for the novem.io data visualisation platform. Create charts,
documents, e-mails and dashboards through one simple API.

**NB:** novem is currently in closed alpha, if you want to try it out please
reach out to hello@novem.io


## Examples

Create a linechart from a pandas dataframe (assumes a configured profile —
see "Getting started" below).

```python
import numpy as np
import pandas as pd
from novem import Plot

# a sample price-like series; swap in your own dataframe. Name the index and
# series so the CSV has a proper "Date,Price" header.
dates = pd.date_range("2015-01-01", "2021-12-31", freq="B", name="Date")
prices = pd.Series(
    100 + np.random.randn(len(dates)).cumsum(), index=dates, name="Price"
)

line = Plot("price_hist", type="line", name="Sample price history")

# send data to the plot
prices.pipe(line)

# url to view the plot
print(line.url)
```


## Getting started
To get started with novem you will have to register an account. Please
[reach out](mailto:hello@novem.io) to us!

Once you have a username and password you can setup your environment using:
```bash
  python -m novem --init
```

In addition to invoking the novem module as shown above, the novem package also
includes an extensive command-line interface (cli). Check out CLI.md in this
repository or [novem.io](https://novem.io) for more details.


## Configuration and authentication
Every novem object needs a token and an API root to talk to the platform.
These are resolved, in order of precedence, from:

 1. explicit keyword arguments on the object (or a `Session`, see below)
 2. values set programmatically via `novem.config`
 3. the `NOVEM_TOKEN` / `NOVEM_API_ROOT` environment variables
 4. the config file written by `python -m novem --init`

The simplest setup is the config file (`--init` above). To configure novem
programmatically instead — handy in notebooks, scripts or CI — set a token on
the global `novem.config` object once, and objects created afterwards pick it
up automatically:

```python
import novem

novem.config.set_token("your-token")

plot = novem.Plot("my-plot")
```

`novem.config` also exposes `set_api_root(...)` (to point at a non-default API)
and `use_profile(...)` (to select a profile from the config file).

Alternatively, pass the token straight to the object. An explicit argument
always wins over whatever is on `novem.config`:

```python
plot = novem.Plot("my-plot", token="your-token")
```

### Multiple accounts / profiles
A `Session` captures connection settings (token, api_root or a config-file
profile) and constructs objects bound to them, without touching the global
defaults — useful when working against several accounts at once:

```python
import novem

work = novem.Session(profile="work")
personal = novem.Session(profile="personal")

# copy a plot's data from one account to the other
personal.Plot("earnings").data = work.Plot("earnings").data
```



## Creating a plot
Novem represents plots as a `Plot` class that can be imported from the main
novem package `from novem import Plot`.

The `Plot` class takes a single mandatory positional argument, the name of the
plot.
 * If the plot name is new, the instantiation of the class will create the plot.
 * If the plot name already exist, then the new object will operate on the
   existing plot.

In addition to the name, there are two broad categories of options for a
plot: data and config.
 * The **data** contains the actual information to visualise (usually in the form
   of numeric csv)
 * **Config**, which contains information about the visual such as:
   * Type (bar, line, donut, map etc)
   * Titles/captions/names/colors/legends/axis etc


There are two ways to interact with the plots, one can either supply all
the necessary options as named arguments when creating the plot, or use the
property accessors to modify them one by one (this is more helpful when working
with the plot interactively). Below is an example of both approaches.

```python
from novem import Plot

# everything in the constructor
barchart = Plot(<name>, \
  type="bar", \
  title="barchart title", \
  caption = "caption"
)

# property approach
barchart = Plot("plot_name")
barchart.type = "bar"
barchart.title = "barchart title"
barchart.caption = "caption"
```

In addition to setting individual properties, the `Plot` object is also
callable.  This means that the resulting plot can be used as a function, either
by being provided data as an argument, or used as part of a pipe chain.

```python
from novem import Plot
import pandas as pd
import numpy as np

# construct some random sample data
df = pd.DataFrame(np.random.randn(100, 4), columns=list("ABCD")).cumsum()

line = Plot("new_line", type="line")

# alternative one, setting data explicitly to a csv string
line.data = df.to_csv()

# or let the plot invoke the to_csv
line.data = df

# alternative two, calling Plot with a csv string
line(df.to_csv())

# alternative three calling the Plot with an object that has a to_csv function
line(df)

# or
df.pipe(line)

```


**NB:** All novem plot operations are live.
This means that as soon as you write to or modify any aspects of the plot
object, those changes are reflected on the novem server and anyone watching
the plot in real time.



## Contribution and development
The novem python library and platform is under active development, contributions
or issues are most welcome.

For guidelines on how to contribute, please check out the CONTRIBUTING.md file
in this repository.


## LICENSE
This python library is licensed under the MIT license, see the LICENSE file for
details.
