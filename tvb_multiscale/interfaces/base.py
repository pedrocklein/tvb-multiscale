# -*- coding: utf-8 -*-
from xarray import DataArray
import pandas as pd
from tvb_multiscale.config import CONFIGURED
from tvb_multiscale.spiking_models.devices import InputDeviceDict, OutputDeviceDict, OutputSpikeDeviceDict
from tvb_scripts.utils.log_error_utils import initialize_logger
from tvb_scripts.utils.data_structures_utils import is_integer
from tvb_scripts.time_series.model import TimeSeries, TimeSeriesRegion


LOG = initialize_logger(__name__)


PARAMETERS = ["current", "potential"]


class TVBSpikeNetInterface(object):

    # This is the actual interface class between TVB and a SpikingNetwork

    _available_input_devices = InputDeviceDict.keys()
    _current_input_devices = []
    _spike_rate_input_devices = []
    _available_output_devices = OutputDeviceDict.keys()
    _spike_rate_output_devices = OutputSpikeDeviceDict.keys()
    _multimeter_output_devices = ["multimeter"]
    _voltmeter_output_devices = ["voltmeter"]

    tvb_model = None
    dt = 0.1

    tvb_nodes_ids = []
    spiking_nodes_ids = []

    spiking_network = None

    tvb_to_spikeNet_interfaces = None
    tvb_to_spikeNet_params = []
    spikeNet_to_tvb_interfaces = None
    spikeNet_to_tvb_params_interfaces_ids = None
    spikeNet_to_tvb_sv_interfaces_ids = None
    spikeNet_to_tvb_params = []

    def __init__(self, config=CONFIGURED):
        self.config = config
        LOG.info("%s created!" % self.__class__)

    @property
    def spiking_nodes(self):
        return self.spiking_network.region_nodes

    @property
    def spikeNet_min_delay(self):
        return self.spiking_network.min_delay

    @property
    def number_of_spiking_nodes(self):
        return len(self.spiking_nodes_ids)

    @property
    def number_of_tvb_nodes(self):
        return len(self.tvb_nodes_ids)

    @property
    def number_of_nodes(self):
        return self.number_of_spiking_nodes + self.number_of_tvb_nodes

    @property
    def number_of_tvb_state_variables(self):
        return len(self.tvb_model.state_variables)

    def configure(self, tvb_model):
        # Organize the different kinds of interfaces and set the TVB region model of the TVB Simulator
        self.spikeNet_to_tvb_params = []
        self.spikeNet_to_tvb_params_interfaces_ids = []
        self.spikeNet_to_tvb_sv_interfaces_ids = []
        for interface_id, interface in enumerate(self.spikeNet_to_tvb_interfaces):
            if is_integer(interface.tvb_sv_id) and interface.tvb_sv_id >= 0:
                self.spikeNet_to_tvb_sv_interfaces_ids.append(interface_id)
            else:
                self.spikeNet_to_tvb_params_interfaces_ids.append(interface_id)
            # Even if the target in TVB is a state variable,
            # we are going to create a TVB parameter with the same name
            self.spikeNet_to_tvb_params.append(interface.name)
        self.tvb_model = tvb_model

    def tvb_state_to_spikeNet(self, state, coupling, stimulus, model):
        # Apply TVB -> Spiking Network input at time t before integrating time step t -> t+dt
        for interface in self.tvb_to_spikeNet_interfaces:
            if interface.model in self._available_input_devices:
                values = state[interface.tvb_sv_id].squeeze()  # if we need the state variable
                if interface.model in self._current_input_devices:
                    transform_fun = self.transforms["tvb_to_current"]
                    # We assume that current is a mean field quantity
                    # applied equally and in parallel
                    # to all target neurons of the spiking populations
                    # This is why no scaling has been applied
                    # for the synaptic weight from the dc_generator device, representing a TVB node,
                    # to the target spiking node
                    # For this output TVB state variable:
                    # ...transmit it to the corresponding devices of the spiking network,
                    # ...which represent each TVB node
                elif interface.model in self._spike_rate_input_devices:
                    # Rate is already a meanfield quantity.
                    # All neurons of the target spiking populations
                    # will receive the same spike rate.
                    # No further scaling is required with the population size (number of neurons)
                    # For this output TVB state variable:
                    # ...convert to spiking rate for every TVB node..
                    # For this output TVB state variable:
                    # ...convert to spiking rate for every TVB node...
                    transform_fun = self.transforms["tvb_to_spike_rate"]
            elif interface.model in PARAMETERS:
                values = coupling[interface.tvb_coupling_id].squeeze()
                if interface.model == "current":
                    transform_fun = self.transforms["tvb_to_current"]
                    # We assume that current is a mean field quantity
                    # applied equally and in parallel
                    # to all target neurons of the spiking populations
                    # Instantaneous transmission. TVB history is used to buffer delayed communication.
                elif interface.model == "potential":
                    transform_fun = self.transforms["tvb_to_potential"]
                    # We assume that potential is a mean field quantity
                    # applied equally and in parallel
                    # to all target neurons of the spiking populations
                    # Instantaneous transmission. TVB history is used to buffer delayed communication.
            else:
                raise ValueError("Interface model %s is not supported yet!" % interface.model)
            # General form: interface_scale_weight * transformation_of(TVB_state_values)
            values = interface.scale * \
                     transform_fun(values, interface.nodes_ids)
            interface.set(values)

    def spikeNet_state_to_tvb_parameter(self, model):
        # Apply Spiking Network -> TVB parameter input at time t before integrating time step t -> t+dt
        for interface_id in self.spikeNet_to_tvb_params_interfaces_ids:
            # ...update them:
            interface = self.spikeNet_to_tvb_interfaces[interface_id]
            # Update TVB parameter
            param_values = getattr(model, interface.name)
            if interface.model in self._spike_rate_output_devices:
                transform_fun = self.transforms["spikes_to_tvb"]
                values = interface.population_mean_spikes_number
                interface.reset  # We need to erase the spikes we have already read and communicated to TVB
            elif interface.model == self._multimeter_output_devices:
                transform_fun = self.transforms["spikes_sv_to_tvb"]
                values = interface.current_population_mean_values
            elif interface.model == self._voltmeter_output_devices:
                transform_fun = self.transforms["potential_to_tvb"]
                values = interface.current_population_mean_values
            # TODO: add any other possible Spiking Network output devices to TVB parameters interfaces here!
            else:
                raise ValueError("Interface model %s is not supported yet!" % interface.model)
            # General form: interface_scale_weight * transformation_of(SpikeNet_state_values)
            param_values[interface.nodes_ids] = \
                interface.scale * transform_fun(values, interface.nodes_ids)
            setattr(model, "__" + interface.name, param_values)
        return model

    def spikeNet_state_to_tvb_state(self, state):
        # Apply Spiking Network -> TVB state input at time t+dt after integrating time step t -> t+dt
        for interface_id in self.spikeNet_to_tvb_sv_interfaces_ids:
            interface = self.spikeNet_to_tvb_interfaces[interface_id]
            # Update TVB state
            if interface.model in self._spike_rate_output_devices:
                # The number of spikes has to be converted to a spike rate via division:
                #  by the total number of neurons to convert it to a mean field quantity,
                #  and by the time step dt, which is already included in the spikes_to_tvb scaling.
                # Instantaneous transmission. TVB history is used to buffer delayed communication.
                transform_fun = self.transforms["spikes_to_tvb"]
                values = interface.population_mean_spikes_number
                interface.reset
            elif interface.model == self._multimeter_output_devices:
                # Instantaneous transmission. TVB history is used to buffer delayed communication.
                transform_fun = self.transforms["spikes_sv_to_tvb"]
                values = interface.current_population_mean_values
            elif interface.model == self._voltmeter_output_devices:
                # Instantaneous transmission. TVB history is used to buffer delayed communication.
                transform_fun = self.transforms["potential_to_tvb"]
                values = interface.current_population_mean_values
            # TODO: add any other possible Spiking Network output devices to TVB parameters interfaces here!
            else:
                raise ValueError("Interface model %s is not supported yet!" % interface.model)
            # General form: interface_scale_weight * transformation_of(SpikeNet_state_values)
            state[interface.tvb_sv_id, interface.nodes_ids, 0] = \
                interface.scale * transform_fun(values,  interface.nodes_ids)
        return state

    def get_mean_data_from_multimeter_to_TVBTimeSeries(self, **kwargs):
        # This method interrogates the Spiking Network's output_devices (if any) for measured quantities
        mean_data = self.spiking_network.get_mean_data_from_multimeter(**kwargs)
        if mean_data is None:
            return None
        connectivity = kwargs.pop("connectivity", None)
        if connectivity is None:
            time_series = TimeSeries()
        else:
            time_series = TimeSeriesRegion(connectivity=connectivity)
        if isinstance(mean_data, DataArray):
            return time_series.from_xarray_DataArray(mean_data)
        else:  # Assuming a pd.Series or a dict of xarrays.DataArray
            output_xarrays = []
            pop_names = []
            for d_name, d in mean_data.iteritems():
                output_xarrays.append(time_series.from_xarray_DataArray(d))
                pop_names.append(d_name)
            if isinstance(mean_data, pd.Series):
                name = mean_data.name
            else:
                name = kwargs.get("name", "Mean data from multimeter")
            return pd.Series(output_xarrays, index=pd.Index(pop_names, name="Population"), name=name)

    def get_mean_spikes_rates_to_TVBTimeSeries(self, **kwargs):
        # This method interrogates the Spiking Network's spikes' output_devices (if any) for spike rates
        rates, spike_detectors = self.spiking_network.compute_mean_spikes_rates(**kwargs)
        if rates is None:
            return None, None
        connectivity = kwargs.pop("connectivity", None)
        if connectivity is None:
            time_series = TimeSeries()
        else:
            time_series = TimeSeriesRegion(connectivity=connectivity)
        if isinstance(rates, DataArray):
            return time_series.from_xarray_DataArray(rates), spike_detectors
        else:
            # Assuming a pd.Series or a dict of xarrays.DataArray
            output_xarrays = []
            pop_names = []
            for d_name, d in rates.iteritems():
                output_xarrays.append(time_series.from_xarray_DataArray(d))
                pop_names.append(d_name)
            if isinstance(rates, pd.Series):
                name = rates.name
            else:
                name = kwargs.get("name", "Mean rates from spike detectors")
            return pd.Series(output_xarrays, index=pd.Index(pop_names, name="Population"), name=name), \
                   spike_detectors
