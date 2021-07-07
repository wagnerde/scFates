import numpy as np
import matplotlib.pyplot as plt
from anndata import AnnData
from typing import Optional, Union
from scanpy.plotting._utils import savefig_or_show


def linearity_deviation(
    adata: AnnData,
    start_milestone,
    end_milestone,
    ntop_genes: int = 30,
    show: Optional[bool] = None,
    save: Union[str, bool, None] = None,
):

    """\
    Plot the results generated by `tl.linearity_deviation`.

    Parameters
    ----------
    adata
        Annotated data matrix.
    start_milestone
        tip defining the starting point of analysed segment.
    end_milestone
        tip defining the end point of analysed segment.
    ntop_genes
        number of top genes to show.
    show
        show the plot.
    save
        save the plot.

    Returns
    -------
    If `show==False` a matrix of :class:`~matplotlib.axes.Axes`

    """

    name = start_milestone + "->" + end_milestone

    topgenes = adata.var[name + "_rss"].sort_values(ascending=False)[:ntop_genes]
    ymin = np.min(topgenes)
    ymax = np.max(topgenes)
    ymax += 0.3 * (ymax - ymin)

    fig, ax = plt.subplots()
    ax.set_ylim(ymin, ymax)
    ax.set_xlim(-0.9, len(topgenes) - 0.1)
    for ig, gene_name in enumerate(topgenes.index):
        ax.text(
            ig,
            topgenes[gene_name],
            gene_name,
            rotation="vertical",
            verticalalignment="bottom",
            horizontalalignment="center",
        )

    ax.set_xlabel("ranking")
    ax.set_ylabel("deviance from linearity")

    savefig_or_show("linearity_transition", show=show, save=save)

    if show == False:
        return ax
