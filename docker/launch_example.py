# -*- coding: utf-8 -*-

from tvb.basic.profile import TvbProfile
TvbProfile.set_profile(TvbProfile.LIBRARY_PROFILE)

import matplotlib as mpl
mpl.use('Agg')

import os
import numpy as np
from tvb_nest.config import Config
from tvb_nest.examples.example import main_example
from tvb_nest.nest_models.builders.models.red_ww_exc_io_inh_i import RedWWExcIOInhIBuilder
from tvb_nest.interfaces.builders.models.red_ww_exc_io_inh_i \
    import RedWWexcIOinhIBuilder as InterfaceRedWWexcIOinhIBuilder
from tvb_multiscale.plot.plotter import Plotter
from tvb.simulator.models.reduced_wong_wang_exc_io_inh_i import ReducedWongWangExcIOInhI
from tvb.datatypes.connectivity import Connectivity


config = Config(output_base="outputs/")
config.figures.SAVE_FLAG = False
config.figures.SHOW_FLAG = False
config.figures.MATPLOTLIB_BACKEND = "Agg"
plotter = Plotter(config)

# Select the regions for the fine scale modeling with NEST spiking networks
nest_nodes_ids = []  # the indices of fine scale regions modeled with NEST
# In this example, we model parahippocampal cortices (left and right) with NEST
connectivity = Connectivity.from_file(config.DEFAULT_CONNECTIVITY_ZIP)
for id in range(connectivity.region_labels.shape[0]):
    if connectivity.region_labels[id].find("hippo") > 0:
        nest_nodes_ids.append(id)

results, simulator = \
    main_example(ReducedWongWangExcIOInhI, RedWWExcIOInhIBuilder, InterfaceRedWWexcIOinhIBuilder,
                 nest_nodes_ids, nest_populations_order=100, connectivity=connectivity,
                 simulation_length=100.0, exclusive_nodes=True, config=config)

np.save(os.path.join(config.out.FOLDER_RES, "connectivity_weights.npy"), simulator.connectivity.weights)
np.save(os.path.join(config.out.FOLDER_RES, "connectivity_lengths.npy"), simulator.connectivity.tract_lengths)
np.save(os.path.join(config.out.FOLDER_RES, "results.npy"), results[0][1])


# # -------------------------------------------6. Plot results--------------------------------------------------------
# from tvb_nest.examples.plot_results import plot_results
# plot_results(results, simulator, tvb_nest_model,
#              tvb_state_variable_type_label="Synaptic Gating Variable",
#              tvb_state_variables_labels=["S_e", "S_i"],
#              plotter=plotter)