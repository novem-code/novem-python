
# novem - data visualisation for coders

A wrapper library for the novem.no data visualisation platform. Create charts,
documents e-mails and dashboards through one simple api.

**NB:** novem is currently in closed alpha, if you want to try it out please
reach out to hello@novem.no


## Exampels

Create a linechart from a dataframe using pandas data reader

```python
from pandas_datareader import data
from novem import Plot

line = Plot("aapl_price_hist", type="line", name="Apple price history")

# Only get the adjusted close.
aapl = data.DataReader("AAPL",
                       start="2015-1-1",
                       end="2021-12-31",
                       data_source="yahoo")["Adj Close"]

# send data to the plot
aapl.pipe(line)

# url to view plot
print(line.url)
```


## Getting started
To get started with novem you'll have to register an account, currently this
can be done by reaching out to the novem developers on hello@novem.no.

Once you have a username and password you can setup your environment using:
```bash
  python -m novem --init
```

In additon to invoking the novem module as shown above, the novem package also
includes an extensive command-line interface (cli). Check out CLI.md in this
repostiory or [novem.no](https://novem.no) for more details.



## Creating a plot
Novem represents plots as a Plot class that can be imported from the main novem
package `from novem import Plot`.

The plot class takes a single mandatory positional argument, the name of the
plot.
 * If the plot name is new, the instantiation of the class will create the plot.
 * If the plot name already exist, then the new object will operate on the
   existing plot.

In addition to the name, there are two broad categories of options for a
plot, data and config:
 * The **data** contains the actual information to visualise (usually in the form
   of numeric csv)
 * **Config**, which contains information about the visual such as:
   * Type (bar, line, donut, map etc)
   * Titles/captions/names/colors/legends/axis etc


There are two ways to interact with the plots, one can either supply all
the neccessary options as named arguments when creating the plot, or use the
property accessors to modfity them one by one (this is more helpful when working
with the plot in an interactive way). Below is an example of the two
approaches.

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

In addition to setting individual properties, the plot object is also callable.
This means that the resulting plot can be used as a function, either by being
provided data as an argument, or used as part of a pipe chain.

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
details
