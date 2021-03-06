# -*- coding: utf-8 -*-
from tvb_nest.interfaces.tvb_to_nest_devices_interfaces import INPUT_INTERFACES_DICT
from tvb_nest.nest_models.builders.nest_factory import create_device, connect_device
from tvb_multiscale.interfaces.builders.tvb_to_spikeNet_device_interface_builder import \
    TVBtoSpikeNetDeviceInterfaceBuilder
from tvb_multiscale.spiking_models.builders.factory import build_and_connect_devices


class TVBtoNESTDeviceInterfaceBuilder(TVBtoSpikeNetDeviceInterfaceBuilder):
    _available_input_device_interfaces = INPUT_INTERFACES_DICT

    @property
    def nest_instance(self):
        return self.spiking_network.nest_instance

    def build_and_connect_devices(self, devices, nodes, *args, **kwargs):
        return build_and_connect_devices(devices, create_device, connect_device,
                                         nodes, self.config, nest_instance=self.nest_instance)
