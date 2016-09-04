# -*- coding: utf-8 -*-
"""

Author
------
Bo Zhang

Email
-----
bozhang@nao.cas.cn

Created on
----------
- Sat Sep 03 12:00:00 2016

Modifications
-------------
- Sat Sep 03 12:00:00 2016

Aims
----
- Keenan class

"""

from __future__ import print_function

import os
import numpy as np
from joblib import load, dump, Parallel, delayed
from .standardization import standardize, standardize_ivar
from .train import train_multi_pixels


class Keenan(object):
    """ This defines Keenan class """
    # training data
    wave = None
    tr_flux = None
    tr_ivar = None
    tr_labels = None

    # training data scalers
    tr_flux_scaler = None
    tr_ivar_scaler = None
    tr_labels_scaler = None

    # dimentions of data
    n_obs = 0
    n_pix = 0
    n_dim = 0

    # SVR result list
    svrs = []
    scores = []
    trained = False

    def __init__(self, wave, tr_flux, tr_ivar, tr_labels, scale=True):
        """ initialize the Keenan instance with tr_flux, tr_ivar, tr_labels

        Parameters
        ----------
        wave: 1D ndarray
            spectral wavelength
        tr_flux: ndarray with a shape of (n_obs x n_pix)
            training flux (RV-corrected, normalized)
        tr_ivar: ndarray with a shape of (n_obs x n_pix)
            training ivar
        tr_labels: ndarray with a shape of (n_obs x n_dim)
            training labels

        Returns
        -------
        Keenan instance

        """

        # input data assertions
        try:
            # assert input data are 2-d np.ndarray
            assert isinstance(wave, np.ndarray) and wave.ndim == 1
            assert isinstance(tr_flux, np.ndarray) and tr_flux.ndim == 2
            assert isinstance(tr_ivar, np.ndarray) and tr_ivar.ndim == 2
            assert isinstance(tr_labels, np.ndarray) and tr_labels.ndim == 2

            # assert input data shape consistency
            assert tr_flux.shape == tr_ivar.shape
            assert tr_flux.shape[0] == tr_labels.shape[0]

        except:
            raise (ValueError(
                "@Keenan: input data error, go back and check your data!"))

        if scale:
            # if scale: do standardization

            # assign attributes
            self.tr_flux = tr_flux
            self.tr_ivar = tr_ivar
            self.tr_labels = tr_labels

            # standardization
            self.tr_flux_scaler, self.tr_flux_scaled = \
                standardize(tr_flux)
            self.tr_ivar_scaler, self.tr_ivar_scaled = \
                standardize_ivar(tr_ivar, self.tr_flux_scaler)
            self.tr_labels_scaler, self.tr_labels_scaled = \
                standardize(tr_labels)

            # update dimensions
            self.__update_dims__()

        else:
            # if not scale, assume the input data is already scaled

            # assign attributes
            self.tr_flux_scaled = tr_flux
            self.tr_ivar_scaled = tr_ivar
            self.tr_labels_scaled = tr_labels

            # update dimensions
            self.__update_dims__()

    def __update_dims__(self, verbose=True):
        """ update data dimensions """
        # record old data dimensions
        n_obs_old, n_pix_old, n_dim_old = self.n_obs, self.n_pix, self.n_dim
        # assign new data dimensions
        self.n_obs, self.n_pix = self.tr_flux_scaled.shape
        self.n_dim = self.tr_labels_scaled.shape[1]
        # verbose
        if verbose:
            print("")
            print("@Keenan: updating data dimensions!")
            print("----------------------------------")
            print("n_obs: %s --> %s" % (n_obs_old, self.n_obs))
            print("n_pix: %s --> %s" % (n_pix_old, self.n_pix))
            print("n_dim: %s --> %s" % (n_dim_old, self.n_dim))
            print("----------------------------------")

    def __repr__(self):
        repr_strs = [
            "Keenan:",
            "tr_flux............: ( %s x %s )" % (self.n_obs, self.n_pix),
            "tr_ivar............: ( %s x %s )" % (self.n_obs, self.n_pix),
            "tr_labels..........: ( %s x %s )" % (self.n_obs, self.n_dim),

            "tr_flux_scaler.....: ( %s x %s )" % (self.n_obs, self.n_pix),
            "tr_ivar_scaler.....: ( %s x %s )" % (self.n_obs, self.n_pix),
            "tr_labels_scaler...: ( %s x %s )" % (self.n_obs, self.n_dim),

            "svrs...............: list[%s]" % len(self.svrs),
            "trained............: %s" % self.trained,
        ]
        return '\n'.join(repr_strs)

    def save_dump(self, filepath, overwrite=False, *args, **kwargs):
        """ save Keenan object to dump file using joblib

        Parameters
        ----------
        filepath: string
            file path
        overwrite: bool
            If True, overwrite the file directly.

        *args, **kwargs:
            extra parameters are passed to joblib.dump()

        """
        # check file existence
        if os.path.exists(filepath) and not overwrite:
            raise (IOError("@Keenan: file exists! [%s]" % filepath))
        else:
            # the joblib.dump() will overwrite file in default
            dump(self, filepath, *args, **kwargs)
            return

    @classmethod
    def load_dump(cls, filepath):
        """ load Keenan instance from dump file

        Parameters
        ----------
        filepath: string
            the dump file path

        Returns
        -------
        Keenan instance / arbitrary python object

        Example
        -------
        >>> k = Keenan.load_dump('./keenan.dump')

        """
        # check file existence
        try:
            assert os.path.exists(filepath)
        except:
            raise (IOError("@Keenan: file does not exist! [%s]" % filepath))

        return load(filepath)

    def save_dump_svrs(self, filepath, overwrite=False, *args, **kwargs):
        """ [NOT RECOMMENDED] save only (wave, svrs) to dump file

        Parameters
        ----------
        filepath: string
            file path
        overwrite: bool
            If True, overwrite the file directly.

        *args, **kwargs:
            extra parameters are passed to joblib.dump()

        Example
        -------
        >>> k.save_dump_svrs('./keenan_svrs.dump')

        """
        # check file existence
        if os.path.exists(filepath) and not overwrite:
            raise (IOError("@Keenan: file exists! [%s]" % filepath))
        else:
            # the joblib.dump() will overwrite file in default
            dump((self.wave, self.svrs), filepath, *args, **kwargs)
            return

    @classmethod
    def load_dump_svrs(cls, filepath):
        """ [NOT RECOMMENDED] initialize Keenan instance with only *svrs* data

        Parameters
        ----------
        filepath: string
            the dump file path

        Returns
        -------
        A Keenan instance
        flux, ivar and labels will be automatically filled with np.zeros

        Example
        -------
        >>> k = Keenan.load_dump_svrs('./keenan_svrs.dump')
        >>> print(k)

        """
        wave, svrs = load(filepath)
        n_pix = len(wave)
        k = Keenan(wave,
                   np.zeros((10, n_pix)),
                   np.zeros((10, n_pix)),
                   np.zeros((10, n_pix)),
                   scale=False)
        k.svrs = svrs
        k.trained = True
        return k

    def train_pixels(self, cv=10, n_jobs=10, method='simple', *args, **kwargs):
        """ train pixels usig SVR

        Parameters
        ----------
        n_jobs: int
            number of jobs that will be launched simultaneously
        cv: int
            if cv>1, cv-fold Cross-Validation will be performed
        *args, **kwargs:
            will be passed to the svr.fit() method

        Returns
        -------
        self.svrs: list
            a list of SVR results
        self.trained: bool
            will be set True

        """
        # training
        results = train_multi_pixels(self.tr_labels_scaled,
                                     [y for y in self.tr_flux_scaled.T],
                                     [None for y in self.tr_flux_scaled.T],
                                     cv,
                                     method=method,
                                     n_jobs=n_jobs,
                                     verbose=10,
                                     **kwargs)

        # clear & store new results
        self.svrs = []
        self.scores = []
        for svr, score in results:
            self.svrs.append(svr)
            self.scores.append(score)

        self.trained = True
        return


def _test_repr():
    wave = np.arange(5000, 6000)
    tr_flux = np.random.randn(10, 1000)
    tr_ivar = np.random.randn(10, 1000)
    tr_labels = np.random.randn(10, 3)
    k = Keenan(wave, tr_flux, tr_ivar, tr_labels)
    print(k)


if __name__ == '__main__':
    _test_repr()