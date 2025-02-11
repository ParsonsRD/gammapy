# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""Sampler parameter classes."""

import numpy as np
import ultranest
from .covariance import Covariance
from .utils import _parse_datasets

__all__ = ["Sampler", "SamplerLikelihood"]  # , "SamplerResult"


class Sampler:
    """Sampler class.

    The sampler class provides a uniform interface to multiple sampler backends.
    Currently available: "UltraNest", ("zeusmc", "emcee"  in #TODO).

    Parameters
    ----------
    backend : {"ultranest"}
        Global backend used for sampler. Default is "ultranest".
        UltraNest: Most options can be found in the UltraNest doc
        https://johannesbuchner.github.io/UltraNest/ultranest.html#ultranest.integrator.ReactiveNestedSampler

    #TODO : describe all parameters
    """

    def __init__(self, backend="ultranest", sampler_opts=None):
        self._sampler = None
        self.backend = backend
        self.sampler_opts = sampler_opts

        if self.backend == "ultranest":
            default_opts = {
                "live_points": 200,
                "frac_remain": 0.5,
                "log_dir": None,
                "resume": "subfolder",
                "step_sampler": False,
                "nsteps": 20,
            }

        self.sampler_opts = default_opts
        if sampler_opts is not None:
            self.sampler_opts.update(sampler_opts)

    @staticmethod
    def _update_models(models, results):
        posterior = results["posterior"]
        samples = results["samples"]
        for i, par in enumerate(models.parameters.free_parameters):
            par.value = posterior["mean"][i]  # Todo : add option for median, maxLogL
            par.error = posterior["stdev"][i]

        covariance = Covariance.from_factor_matrix(models.parameters, np.cov(samples.T))
        models.covariance = covariance
        return models

    def sampler_ultranest(self, parameters, like):
        """
        Defines the Ultranest sampler and options
        Returns the result dictionary that contains the samples and other information.
        """

        def _prior_inverse_cdf(values):
            if None in parameters:
                raise ValueError(
                    "Some parameters have no prior set. You need priors on all parameters."
                )
            return [par.prior._inverse_cdf(val) for par, val in zip(parameters, values)]

        # create ultranest object
        self._sampler = ultranest.ReactiveNestedSampler(
            parameters.names,
            like.fcn,
            transform=_prior_inverse_cdf,
            log_dir=self.sampler_opts["log_dir"],
            resume=self.sampler_opts["resume"],
        )

        if self.sampler_opts["step_sampler"]:
            self._sampler.stepsampler = ultranest.stepsampler.SliceSampler(
                nsteps=self.sampler_opts["step_sampler"],
                generate_direction=ultranest.stepsampler.generate_mixture_random_direction,
                adaptive_nsteps=False,
            )

        result = self._sampler.run(
            min_num_live_points=self.sampler_opts["live_points"],
            frac_remain=self.sampler_opts["frac_remain"],
        )

        return result

    def run(self, datasets):
        datasets, parameters = _parse_datasets(datasets=datasets)
        parameters = parameters.free_parameters

        if self.backend == "ultranest":
            # create log likelihood function
            like = SamplerLikelihood(
                function=datasets._stat_sum_likelihood, parameters=parameters
            )
            result = self.sampler_ultranest(parameters, like)

            self._update_models(datasets.models, result)
            print(self._sampler.print_results())

            result = SamplerResult.from_ultranest(result)
            result.models = datasets.models.copy()
            return result
        else:
            raise ValueError(f"sampler {self.backend} is not supported.")


class SamplerResult:
    """SamplerResult class.
    This is a placeholder to store the results from the sampler

    TODO:
    - Support parameter posteriors: directly on Parameter
        - e.g. adding a errn and errp entry
        - or creating a posterior entry on Parameter
    - Or support with a specific entry on the SamplerResult

    Parameters
    ----------
    nfev : int
        number of likelihood calls/evaluations
    success : bool
        Did the sampler succeed in finding a good fit? Definition of convergence depends on the sampler backend.
    models : `~gammapy.modeling.models`
        the models used by the sampler
    samples : `~numpy.ndarray`, optional
        array of (weighted) samples
    sampler_results : dict, optional
        output of sampler.
    """

    def __init__(
        self, nfev=0, success=False, models=None, samples=None, sampler_results=None
    ):
        self.nfev = nfev
        self.success = success
        self.models = models
        self.samples = samples
        self.sampler_results = sampler_results

    @classmethod
    def from_ultranest(cls, ultranest_result):
        kwargs = {}
        kwargs["nfev"] = ultranest_result["ncall"]
        kwargs["success"] = ultranest_result["insertion_order_MWW_test"]["converged"]
        kwargs["samples"] = ultranest_result["samples"]
        kwargs["sampler_results"] = ultranest_result
        return cls(**kwargs)


class SamplerLikelihood:
    """Wrapper of the likelihood function used by the sampler.
    This is needed to modify parameters and likelihood by *-0.5
    #TODO: can this be done in a simpler manner without a class
    Parameters
    ----------
    parameters : `~gammapy.modeling.Parameters`
        Parameters with starting values.
    function : callable
        Likelihood function.
    """

    def __init__(self, function, parameters):
        self.function = function
        self.parameters = parameters

    def fcn(self, value):
        self.parameters.value = value
        total_stat = -0.5 * self.function()
        return total_stat
