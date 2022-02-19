import logging
import os
from numbers import Number
from typing import Callable, Tuple, Any, Dict

import matplotlib
import matplotlib.pyplot as plt
import numpy
import numpy as np
from matplotlib import animation

from phi import math
from phi.geom import Sphere, BaseBox
from phi.math import Tensor, batch, channel
from phi.vis._plot_util import smooth_uniform_curve
from phi.vis._vis_base import display_name, PlottingLibrary
from phi.field import Grid, StaggeredGrid, PointCloud, Scene, unstack, SampledField
from phi.field._scene import _str


class MatplotlibPlots(PlottingLibrary):

    def create_figure(self,
                      size: tuple,
                      rows: int,
                      cols: int,
                      subplots: Dict[Tuple[int, int], int],
                      titles: Tensor) -> Tuple[Any, Dict[Tuple[int, int], Any]]:
        figure, axes = plt.subplots(rows, cols, figsize=size)
        axes = np.reshape(axes, (rows, cols))
        axes_by_pos = {}
        for row in range(rows):
            for col in range(cols):
                axes[row, col].set_title(titles.rows[row].cols[col].native())
                if (row, col) not in subplots:
                    axes[row, col].remove()
                else:
                    if subplots[(row, col)] == 3:
                        axes[row, col].remove()
                        axes[row, col] = figure.add_subplot(rows, cols, cols*row + col + 1, projection='3d')
                    axes_by_pos[(row, col)] = axes[row, col]
        return figure, axes_by_pos

    def plot(self,
             data: SampledField,
             figure,
             subplot,
             min_val: float = None,
             max_val: float = None,
             show_color_bar: bool = True,
             **plt_args):
        _plot(subplot, data, show_color_bar=show_color_bar, vmin=min_val, vmax=max_val, **plt_args)
        plt.tight_layout()
        return figure

    def show(self, figure=None):
        if figure is not None:
            figure.show()
        else:
            plt.show()


MATPLOTLIB = MatplotlibPlots()


def plot(field: SampledField or Tensor or tuple or list,
         title=False,
         size=(12, 5),
         show_color_bar=True,
         same_scale=True,
         existing_figure: plt.Figure or None = None,
         **plt_args):
    """
    Creates a Matplotlib figure to display a single field or batch of fields.

    Use [`matplotlib.pyplot.show()`](https://matplotlib.org/3.1.1/api/_as_gen/matplotlib.pyplot.show.html) or
    [`matplotlib.pyplot.savefig()`](https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.savefig.html) to view the figure.

    Args:
        field: `SampledField`, may contain batch dimensions which will create sub-figures.
        title: Figure/sub-figure title. If `str` or `tuple`/`list` of `str`. `True` to generate a title automatically.
        show_color_bar: Whether to show a colorbar for heatmap plots.
        size: Figure (width, height) in inches.
        same_scale: Whether to use the same value scale for all subplots.
        existing_figure: Existing Matplotlib figure to add this plot to. Figure will not be cleared before plotting.
        **plt_args: Additional plotting arguments passed to Matplotlib.

    Returns:
        [Matplotlib figure](https://matplotlib.org/stable/api/figure_api.html#matplotlib.figure.Figure).
    """
    fig, fields = _subplots(field, size, existing_figure=existing_figure)
    if title:
        for b in range(len(fig.axes)):
            if isinstance(title, str):
                sub_title = title
            elif title is True:
                sub_title = f"{b} of {field.shape.batch}"
            elif isinstance(title, (tuple, list)):
                sub_title = title[b]
            else:
                sub_title = None
            if sub_title is not None:
                fig.axes[b].set_title(sub_title)
    if same_scale and any(isinstance(f, Grid) for f in fields):
        min_val = min([float(f.values.min) for f in fields if isinstance(f, Grid)])
        max_val = min([float(f.values.max) for f in fields if isinstance(f, Grid)])
    else:
        min_val, max_val = None, None
    for axis, field in zip(fig.axes, fields):
        _plot(axis, field, show_color_bar=show_color_bar, vmin=min_val, vmax=max_val, **plt_args)
    plt.tight_layout()
    return fig


def animate(fields: SampledField,
            dim='frames',
            repeat=True,
            interval=200,
            title=False,
            size=(8, 6),
            show_color_bar=False,
            same_scale=True,
            **plt_args) -> animation.Animation:
    """
    Creates a Matplotlib animation from `fields`.
    `fields` may be a sequence of frames or a single `SampledField` instances with a `frames` dimension.

    Args:
        fields: `SampledField` with `frames` dimension or `tuple` or `list` of `SampledField`.
        dim: Time dimension to animate (default=`'frames'`).
        repeat: Whether the video should loop.
        interval: Frame time in milliseconds.
        title: Figure/sub-figure title. If `str` or `tuple`/`list` of `str`. `True` to generate a title automatically.
        size: Figure size
        show_color_bar: Whether to show a color bar
        same_scale: Whether to use the same scale, both temporally and for all sub-figures.
        **plt_args: Further plotting arguments, see `plot()`.

    Returns:
        Matplotlib `Animation`
    """
    assert isinstance(fields, SampledField)
    assert dim in fields.shape, f"Animation dimension {dim} not present in data."
    fields = list(fields.unstack(dim))
    fig, _ = _subplots(fields[0], size, None)

    def func(frame: int):
        field = fields[frame]
        for axis in fig.axes:
            axis.clear()
        plot(field, existing_figure=fig, title=title, show_color_bar=show_color_bar, same_scale=same_scale, **plt_args)

    ani = animation.FuncAnimation(fig, func, init_func=lambda: fig.axes, repeat=repeat, frames=len(fields), interval=interval)
    plt.close(fig)
    return ani


def _plot(axis, field, show_color_bar, vmin, vmax, **plt_args):
    if isinstance(field, Grid) and channel(field).volume == 1 and field.spatial_rank == 2:
        left, bottom = field.bounds.lower.vector.unstack_spatial('x,y')
        right, top = field.bounds.upper.vector.unstack_spatial('x,y')
        extent = (float(left), float(right), float(bottom), float(top))
        im = axis.imshow(field.values.numpy('y,x'), origin='lower', extent=extent, vmin=vmin, vmax=vmax, **plt_args)
        if show_color_bar:
            plt.colorbar(im, ax=axis)
    elif isinstance(field, Grid) and field.spatial_rank == 2:  # vector field
        if isinstance(field, StaggeredGrid):
            field = field.at_centers()
        x, y = [d.numpy('x,y') for d in field.points.vector.unstack_spatial('x,y')]
        u, v = [d.numpy('x,y') for d in field.values.vector.unstack_spatial('x,y')]
        color = axis.xaxis.label.get_color()
        axis.quiver(x, y, u, v, color=color, units='xy', scale=1)
        axis.set_aspect('equal', adjustable='box')
    elif isinstance(field, Grid) and channel(field).volume > 1 and field.spatial_rank == 3:
        x, y, z = [d.numpy('x,y,z') for d in field.points.vector.unstack_spatial('x,y,z')]
        u, v, w = [d.numpy('x,y,z') for d in field.values.vector.unstack_spatial('x,y,z')]
        axis.quiver(x, y, z, u, v, w)
        axis.set_xlabel('x')
        axis.set_ylabel('y')
        axis.set_zlabel('z')
    elif isinstance(field, Grid) and channel(field).volume == 1 and field.spatial_rank == 3:
        x, y, z = [d.numpy('x,y,z') for d in field.points.vector.unstack_spatial('x,y,z')]
        values = field.values.numpy('x,y,z')
        cmap = plt.get_cmap('viridis')
        norm = matplotlib.colors.Normalize(vmin=np.min(values), vmax=np.max(values))
        colors = cmap(norm(values))
        axis.voxels(values, facecolors=colors, edgecolor='k')
    elif isinstance(field, PointCloud):
        points = field.points
        x, y = [d.numpy() for d in points.vector.unstack_spatial('x,y')]
        color = [str(d) for d in field.color.points.unstack(len(x))]
        if field.bounds:
            lower_x, lower_y = [float(d) for d in field.bounds.lower.vector.unstack_spatial('x,y')]
            upper_x, upper_y = [float(d) for d in field.bounds.upper.vector.unstack_spatial('x,y')]
        else:
            lower_x, lower_y = [np.min(x), np.min(y)]
            upper_x, upper_y = [np.max(x), np.max(y)]
        if isinstance(field.elements, Sphere):
            shape = 'o'
            size = float(field.elements.bounding_radius()) / 2
        elif isinstance(field.elements, BaseBox):
            shape = 's'
            size = float(field.elements.bounding_half_extent())
        else:
            shape = 'X'
            size = float(field.elements.bounding_radius())
        axis.set_xlim((lower_x, upper_x))
        axis.set_ylim((lower_y, upper_y))
        M = axis.transData.get_matrix()
        x_scale, y_scale = M[0, 0], M[1, 1]
        axis.scatter(x, y, marker=shape, color=color, s=(size * 2 * x_scale) ** 2)
        axis.set_aspect('equal', adjustable='box')
    else:
        raise NotImplementedError(f"No figure recipe for {field}")


def _subplots(field: SampledField or tuple or list,
              size: tuple,
              existing_figure: plt.Figure or None):

    def recursive_unstack(field, flat: list):
        if isinstance(field, SampledField) and field.shape.batch_rank == 0:
            flat.append(field)
        elif isinstance(field, SampledField):
            fields = unstack(field, field.shape.batch[0])
            for f in fields:
                recursive_unstack(f, flat)
        else:
            assert isinstance(field, (tuple, list))
            for f in field:
                recursive_unstack(f, flat)
        return flat

    fields = recursive_unstack(field, [])
    if existing_figure is not None:
        assert len(existing_figure.axes) == len(fields)
        return existing_figure, fields
    else:
        fig, _ = plt.subplots(1, len(fields), figsize=size)
        return fig, fields


def plot_scalars(scene: str or tuple or list or Scene or math.Tensor,
                 names: str or tuple or list or math.Tensor = None,
                 reduce: str or tuple or list or math.Shape = 'names',
                 down='',
                 smooth=1,
                 smooth_alpha=0.2,
                 smooth_linewidth=2.,
                 size=(8, 6),
                 transform: Callable = None,
                 tight_layout=True,
                 grid: str or dict = 'y',
                 log_scale='',
                 legend='upper right',
                 x='steps',
                 xlim=None,
                 ylim=None,
                 titles=True,
                 labels: math.Tensor = None,
                 xlabel: str = None,
                 ylabel: str = None,
                 colors: math.Tensor = 'default'):
    """

    Args:
        scene: `str` or `Tensor`. Scene paths containing the data to plot.
        names: Data files to plot for each scene. The file must be located inside the scene directory and have the name `log_<name>.txt`.
        reduce: Tensor dimensions along which all curves are plotted in the same diagram.
        down: Tensor dimensions along which diagrams are ordered top-to-bottom instead of left-to-right.
        smooth: `int` or `Tensor`. Number of data points to average, -1 for all.
        smooth_alpha: Opacity of the non-smoothed curves under the smoothed curves.
        smooth_linewidth: Line width of the smoothed curves.
        size: Figure size in inches.
        transform: Function `T(x,y) -> (x,y)` transforming the curves.
        tight_layout:
        grid:
        log_scale:
        legend:
        x:
        xlim:
        ylim:
        titles:
        labels:
        xlabel:
        ylabel:
        colors: Line colors as `str`, `int` or `Tensor`. Integers are interpreted as indices of the default color list.

    Returns:
        MatPlotLib [figure](https://matplotlib.org/stable/api/figure_api.html#matplotlib.figure.Figure)
    """
    scene = Scene.at(scene)
    additional_reduce = ()
    if names is None:
        first_path = next(iter(math.flatten(scene.paths)))
        names = [_str(n) for n in os.listdir(first_path)]
        names = [n[4:-4] for n in names if n.endswith('.txt') and n.startswith('log_')]
        names = math.wrap(names, batch('names'))
        additional_reduce = ['names']
    elif isinstance(names, str):
        names = math.wrap(names)
    elif isinstance(names, (tuple, list)):
        names = math.wrap(names, batch('names'))
    else:
        assert isinstance(names, math.Tensor), f"Invalid argument 'names': {type(names)}"
    if not isinstance(colors, math.Tensor):
        colors = math.wrap(colors)
    if xlabel is None:
        xlabel = 'Iterations' if x == 'steps' else 'Time (s)'

    shape = (scene.shape & names.shape)
    batches = shape.without(reduce).without(additional_reduce)

    cycle = list(plt.rcParams['axes.prop_cycle'].by_key()['color'])
    fig, axes = plt.subplots(batches.only(down).volume, batches.without(down).volume, figsize=size)
    axes = axes if isinstance(axes, numpy.ndarray) else [axes]

    for b, axis in zip(batches.meshgrid(), axes):
        assert isinstance(axis, plt.Axes)
        names_equal = names[b].rank == 0
        paths_equal = scene.paths[b].rank == 0
        if titles is not None and titles is not False:
            if isinstance(titles, str):
                axis.set_title(titles)
            elif names_equal:
                axis.set_title(display_name(str(names[b])))
            elif paths_equal:
                axis.set_title(os.path.basename(str(scene.paths[b])))
        if labels is not None:
            curve_labels = labels
        elif names_equal:
            curve_labels = math.map(os.path.basename, scene.paths[b])
        elif paths_equal:
            curve_labels = names[b]
        else:
            curve_labels = math.map(lambda p, n: f"{os.path.basename(p)} - {n}", scene.paths[b], names[b])

        def single_plot(name, path, label, i, color, smooth):
            logging.debug(f"Reading {os.path.join(path, f'log_{name}.txt')}")
            curve = numpy.loadtxt(os.path.join(path, f"log_{name}.txt"))
            if curve.ndim == 2:
                x_values, values, *_ = curve.T
            else:
                values = curve
                x_values = np.arange(len(values))
            if x == 'steps':
                pass
            else:
                assert x == 'time', f"x must be 'steps' or 'time' but got {x}"
                logging.debug(f"Reading {os.path.join(path, 'log_step_time.txt')}")
                _, x_values, *_ = numpy.loadtxt(os.path.join(path, "log_step_time.txt")).T
                values = values[:len(x_values)]
                x_values = np.cumsum(x_values[:len(values)])
            if transform:
                x_values, values = transform(np.stack([x_values, values]))
            if color == 'default':
                color = cycle[i]
            try:
                color = int(color)
            except ValueError:
                pass
            if isinstance(color, Number):
                color = cycle[int(color)]
            logging.debug(f"Plotting curve {label}")
            axis.plot(x_values, values, color=color, alpha=smooth_alpha, linewidth=1)
            axis.plot(*smooth_uniform_curve(x_values, values, n=smooth), color=color, linewidth=smooth_linewidth, label=label)
            if grid:
                if isinstance(grid, dict):
                    axis.grid(**grid)
                else:
                    grid_axis = 'both' if 'x' in grid and 'y' in grid else grid
                    axis.grid(which='both', axis=grid_axis, linestyle='--', linewidth=size[1] * 0.3)
            if 'x' in log_scale:
                axis.set_xscale('log')
            if 'y' in log_scale:
                axis.set_yscale('log')
            if xlim:
                axis.set_xlim(xlim)
            if ylim:
                axis.set_ylim(ylim)
            if xlabel:
                axis.set_xlabel(xlabel)
            if ylabel:
                axis.set_ylabel(ylabel)
            return name

        math.map(single_plot, names[b], scene.paths[b], curve_labels, math.range_tensor(shape.after_gather(b)), colors, smooth)
        if legend:
            axis.legend(loc=legend)
    # Final touches
    if tight_layout:
        plt.tight_layout()
    return fig


def savefig(filename: str, transparent=True):
    plt.savefig(filename, transparent=transparent)
