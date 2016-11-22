# Licensed under a 3-clause BSD style license - see LICENSE.rst
from __future__ import absolute_import, division, print_function, unicode_literals
import astropy.units as u
import numpy as np
from ...utils.testing import requires_dependency
from ...irf import EnergyDispersion, EffectiveAreaTable
from .. import SpectrumExtraction, SpectrumSimulation
from ..models import PowerLaw


@requires_dependency('scipy')
class TestSpectrumSimulation:
    def setup(self):
        e_true = SpectrumExtraction.DEFAULT_TRUE_ENERGY
        e_reco = SpectrumExtraction.DEFAULT_RECO_ENERGY

        edisp = EnergyDispersion.from_gauss(
            e_true=e_true, e_reco=e_reco, sigma=0.2,
        )

        aeff = EffectiveAreaTable.from_parametrization(energy=e_true)

        self.source_model = PowerLaw(
            index=2.3 * u.Unit(''),
            amplitude=2.5 * 1e-12 * u.Unit('cm-2 s-1 TeV-1'),
            reference=1 * u.TeV
        )
        self.background_model = PowerLaw(
            index=3 * u.Unit(''),
            amplitude=3 * 1e-12 * u.Unit('cm-2 s-1 TeV-1'),
            reference=1 * u.TeV
        )
        self.alpha = 1. / 3

        # Minimal setup
        self.sim = SpectrumSimulation(aeff=aeff,
                                      edisp=edisp,
                                      source_model=self.source_model,
                                      livetime=4 * u.h)

    def test_without_background(self):
        self.sim.simulate_obs(seed=23)
        assert self.sim.obs.on_vector.total_counts == 156

    def test_with_background(self):
        self.sim.background_model = self.background_model
        self.sim.alpha = self.alpha
        self.sim.simulate_obs(seed=23)
        assert self.sim.obs.on_vector.total_counts == 525
        assert self.sim.obs.off_vector.total_counts == 1096

    def test_observations_list(self):
        seeds = np.arange(5)
        self.sim.run(seed=seeds)
        assert (self.sim.result.obs_id == seeds).all()
        assert self.sim.result[0].on_vector.total_counts == 169
        assert self.sim.result[1].on_vector.total_counts == 159
        assert self.sim.result[2].on_vector.total_counts == 151
        assert self.sim.result[3].on_vector.total_counts == 163
        assert self.sim.result[4].on_vector.total_counts == 185
