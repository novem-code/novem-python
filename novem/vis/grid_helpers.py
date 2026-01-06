from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Union

if TYPE_CHECKING:
    from novem.vis.grid import Grid
    from novem.vis.plot import Plot


class GridMap:
    """
    Helper class to map grid cell identifiers to novem visualizations.

    GridMap converts a dictionary of cell keys to Plot/Grid objects into
    the plain text format expected by the novem API:

        a => /u/:username/p/:plot_id
        b => /u/:username/g/:grid_id

    Example usage:
        grd.mapping = GridMap({
            'a': Plot("my_plot"),
            'b': Grid("my_grid"),
        })
    """

    def __init__(self, mapping: Dict[str, Union["Plot", "Grid"]]) -> None:
        """
        Initialize GridMap with a dictionary mapping cell keys to visualizations.

        :param mapping: Dictionary mapping cell identifiers (strings) to
                        Plot or Grid objects.
        """
        self._mapping = mapping

    def __str__(self) -> str:
        """
        Convert the mapping to the novem API format.

        Returns a newline-separated string of mappings in the format:
            key => /u/:username/:type/:id
        """
        lines = []
        for key, vis in self._mapping.items():
            # Get the shortname which contains the path info
            # shortname format is like: /u/username/p/plot_id or /p/plot_id
            shortname = vis.shortname.strip()
            lines.append(f"{key} => {shortname}")

        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"GridMap({self._mapping!r})"

    def get(self, key: str) -> Union["Plot", "Grid", None]:
        """
        Get a visualization by its cell key.

        :param key: The cell identifier
        :return: The Plot or Grid object, or None if not found
        """
        return self._mapping.get(key)

    def keys(self) -> Any:
        """Return the cell keys."""
        return self._mapping.keys()

    def values(self) -> Any:
        """Return the visualization objects."""
        return self._mapping.values()

    def items(self) -> Any:
        """Return key-visualization pairs."""
        return self._mapping.items()
