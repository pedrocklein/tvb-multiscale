# -*- coding: utf-8 -*-

from tvb.basic.profile import TvbProfile
TvbProfile.set_profile(TvbProfile.LIBRARY_PROFILE)

import matplotlib as mpl
mpl.use('Agg')

import numpy as np
from tvb_nest.config import Config
from tvb_nest.examples.example import main_example
from tvb_nest.nest_models.builders.models.red_ww_exc_io_inh_i import RedWWExcIOInhIBuilder
from tvb_nest.interfaces.builders.models.red_ww_exc_io_inh_i import \
    RedWWexcIOinhIBuilder as InterfaceRedWWexcIOinhIBuilder
from tvb.datatypes.connectivity import Connectivity
from tvb.simulator.models.reduced_wong_wang_exc_io_inh_i import ReducedWongWangExcIOInhI


def prepare_launch_default_simulation():
    config = Config(output_base="outputs/")
    config.figures.SAVE_FLAG = False
    config.figures.SHOW_FLAG = False
    config.figures.MATPLOTLIB_BACKEND = "Agg"

    connectivity = Connectivity.from_file(config.DEFAULT_CONNECTIVITY_ZIP)

    # Select the regions for the fine scale modeling with NEST spiking networks
    nest_nodes_ids = []  # the indices of fine scale regions modeled with NEST
    # In this example, we model parahippocampal cortices (left and right) with NEST
    for id in range(connectivity.region_labels.shape[0]):
        if connectivity.region_labels[id].find("hippo") > 0:
            nest_nodes_ids.append(id)

    results, simulator = \
        main_example(ReducedWongWangExcIOInhI, RedWWExcIOInhIBuilder, InterfaceRedWWexcIOinhIBuilder,
                     nest_nodes_ids, nest_populations_order=100, connectivity=connectivity,
                     simulation_length=100.0, exclusive_nodes=True, config=config)

    return simulator.connectivity.weights, simulator.connectivity.tract_lengths, results[0][1]


def test_connectivity_weights_shape():
    (weights, tract_lengths, results) = prepare_launch_default_simulation()
    assert weights.shape == (68, 68)


def test_connectivity_tract_lengths_shape():
    (weights, tract_lengths, results) = prepare_launch_default_simulation()
    assert tract_lengths.shape == (68, 68)


def test_results_shape():
    (weights, tract_lengths, results) = prepare_launch_default_simulation()
    assert not np.isinf(results.ravel()).all()
    assert not np.isnan(results.ravel()).all()
    assert results.shape == (1000, 4, 68, 1)
