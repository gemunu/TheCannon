""" Code for LAMOST data munging """

from __future__ import (absolute_import, division, print_function,)
import numpy as np
import scipy.optimize as opt
from scipy import interpolate 
import os
import sys
import matplotlib.pyplot as plt
import glob

# python 3 special
PY3 = sys.version_info[0] > 2
if not PY3:
    range = xrange

try:
    from astropy.io import fits as pyfits
except ImportError:
    import pyfits

def get_pixmask(file_in, wl, middle, flux, ivar):
    """ Return a mask array of bad pixels for one object's spectrum

    Bad pixels are defined as follows: fluxes or ivars are not finite, or 
    ivars are negative

    Major sky lines. 4046, 4358, 5460, 5577, 6300, 6363, 6863

    Where the red and blue wings join together: 5800-6000

    Read bad pix mask: file_in[0].data[3] is the andmask 

    Parameters
    ----------
    fluxes: ndarray
        flux array

    flux_errs: ndarray
        measurement uncertainties on fluxes

    Returns
    -------
    mask: ndarray, dtype=bool
        array giving bad pixels as True values
    """
    npix = len(wl)
    
    bad_flux = (~np.isfinite(flux)) # count: 0
    bad_err = (~np.isfinite(ivar)) | (ivar <= 0)
    # ivar == 0 for approximately 3-5% of pixels
    bad_pix_a = bad_err | bad_flux
    
    # LAMOST people: wings join together, 5800-6000 Angstroms
    wings = np.logical_and(wl > 5800, wl < 6000)
    # this is another 3-4% of the spectrum
    andmask = (file_in[0].data[3] >0)
    # ^ problematic...this is over a third of the spectrum!
    bad_pix_b = wings | andmask
    # bad_pix_b = wings

    spread = 3 # due to redshift
    skylines = np.array([4046, 4358, 5460, 5577, 6300, 6363, 6863])
    bad_pix_c = np.zeros(npix, dtype=bool)
    for skyline in skylines:
        badmin = skyline-spread
        badmax = skyline+spread
        bad_pix_temp = np.logical_and(wl > badmin, wl < badmax)
        bad_pix_c[bad_pix_temp] = True
    # 34 pixels

    bad_pix_ab = bad_pix_a | bad_pix_b
    bad_pix = bad_pix_ab | bad_pix_c

    return bad_pix_a


def load_spectra(data_dir, filenames, input_grid=None):
    """
    Extracts spectra (wavelengths, fluxes, fluxerrs) from apogee fits files

    Parameters
    ----------
    data_dir: string
        directory where the files are located

    filenames: np ndarray
        files from which to extract spectra

    input_grid: np ndarray
        grid onto which to interpolate

    Returns
    -------
    IDs: list of length nstars
        stellar IDs
    
    wl: numpy ndarray of length npixels
        rest-frame wavelength vector

    fluxes: numpy ndarray of shape (nstars, npixels)
        training set or test set pixel intensities

    ivars: numpy ndarray of shape (nstars, npixels)
        inverse variances, parallel to fluxes
        
    SNRs: numpy ndarray of length nstars
    """
    print("Loading spectra from directory %s" %data_dir)
    files = np.array(filenames)
    nstars = len(files)
    npix = np.zeros(nstars) # count num of good (ivar>0) pix in each object

    if input_grid is None:
        # use first file as template
        file_in = pyfits.open("%s/%s" %(data_dir, files[0])) 
        grid = np.array(file_in[0].data[2])
        middle = np.logical_and(grid_all > 3905, grid_all < 9000)
        grid = grid_all[middle]
        file_in.close()

    else:
        grid = input_grid

    # grid is the template onto which everything is interpolated
    npixels = len(grid)
    SNRs = np.zeros(nstars, dtype=float)
    fluxes = np.zeros((nstars, npixels), dtype=float)
    ivars = np.zeros(fluxes.shape, dtype=float)

    for jj, fits_file in enumerate(files):
        file_in = pyfits.open("%s/%s" %(data_dir, fits_file))
        wl = np.array(file_in[0].data[2])
        flux = np.array(file_in[0].data[0])
        ivar = np.array((file_in[0].data[1]))
        npix[jj] = sum(ivar>0)
        # SNR should be calculated ignoring bad pixels
        SNR[jj] = np.median(flux[ivar>0]*ivar[ivar>0]**0.5)
        # correct for radial velocity of star
        redshift = file_in[0].header['Z']
        wl_shifted = wl - redshift * wl
        # resample
        flux_rs = (interpolate.interp1d(wl_shifted, flux))(grid)
        ivar_rs = (interpolate.interp1d(wl_shifted, ivar))(grid)
        ivar_rs[ivar_rs < 0] = 0. # in interpolating you can end up with neg
        fluxes[jj,:] = flux_rs
        ivars[jj,:] = ivar_rs

    print("Spectra loaded")
    return files, grid, fluxes, ivars, npix


def load_labels(lamost_ids, filename='lamost_labels_all_dates.csv'):
    """ Extracts training labels from file.

    Assumes that first row is # then label names, first col is # then 
    filenames, remaining values are floats and user wants all the labels.
    """
    direc = "home/annaho/TheCannon/examples/lamost_dr2"
    label_file = '%s/%s' %(direc, filename)
    print("Loading reference labels from file %s" %label_file)
    searchIn = np.loadtxt(
        label_file, usecols=(0,), delimiter=',', dtype=str)
    all_tr_label_val = np.loadtxt(
        label_file, usecols=(1,2,3), delimiter=',', dtype=str)
    searchIn = np.array([a.split('/')[-1] for a in searchIn])
    inds = np.array([np.where(searchIn==a)[0][0] for a in lamost_ids])
    return tr_labels[inds]


def is_badstar(star_id):
    ids = np.loadtxt(
        "apogee_dr12_labels.csv", usecols=(0,), delimiter=',', dtype=str)
    bad = np.loadtxt(
        "apogee_dr12_labels.csv", usecols=(6,), delimiter=',', dtype=str)
    return bad[ids==star_id]


def get_starmask(ids, labels, aspcapflag, paramflag):
    """ Identifies which APOGEE objects have unreliable physical parameters,
    as laid out in Holzman et al 2015 and on the APOGEE DR12 website

    Parameters
    ----------
    data: np array
        all APOGEE DR12 IDs and labels

    Returns
    -------
    bad: np array
        mask where 1 corresponds to a star with unreliable parameters
    """
    # teff outside range (4000,6000) K and logg < 0
    teff = labels[0,:]
    bad_teff = np.logical_or(teff < 4000, teff > 6000)
    logg = labels[1,:]
    bad_logg = logg < 0
    cuts = bad_teff | bad_logg

    # STAR_WARN flag set (TEFF, LOGG, CHI2, COLORTE, ROTATION, SN)
    # M_H_WARN, ALPHAFE_WARN not included in the above, so do them separately
    star_warn = np.bitwise_and(aspcapflag, 2**7) != 0
    star_bad = np.bitwise_and(aspcapflag, 2**23) != 0
    mh_warn = np.bitwise_and(aspcapflag, 2**3) != 0
    alpha_warn = np.bitwise_and(aspcapflag, 2**4) != 0
    aspcapflag_bad = star_warn | star_bad | mh_warn | alpha_warn

    # separate element flags
    teff_flag = paramflag[:,0] != 0
    logg_flag = paramflag[:,1] != 0
    mh_flag = paramflag[:,3] != 0
    alpha_flag = paramflag[:,4] != 0
    paramflag_bad = teff_flag | logg_flag | mh_flag | alpha_flag

    return cuts | aspcapflag_bad | paramflag_bad 


def make_kepler_label_file():
    """ using the values made by The Cannon """
    lamost_key = np.loadtxt('lamost_sorted_by_ra.txt',dtype=str)
    apogee_key = np.loadtxt('apogee_sorted_by_ra.txt', dtype=str)
    apogee_key_short = np.array(
            [(item.split('v603-')[-1]).split('.fits')[0]
            for item in apogee_key])
    nstars = len(lamost_key)

    direc = "/home/annaho/TheCannon/examples/example_apokasc/test_is_lamost_apogee_overlap"
    kepler_ids = np.load("%s/test_ids.npz" %direc)['arr_0']
    kepler_ids = np.array([a.split('/')[-1] for a in kepler_ids])
    kepler_labels = np.load("%s/test_labels.npz" %direc)['arr_0']
    inds = np.array(
            [np.where(apogee_key==a)[0][0] for a in kepler_ids])
    teff = kepler_labels[:,0][inds]
    logg = kepler_labels[:,1][inds]
    feh = kepler_labels[:,2][inds]
    alpha = kepler_labels[:,3][inds]

    outputf = open("apogee_cannon_labels.csv", "w")
    header = "#lamost_id,apogee_id,teff,logg,feh,alpha,snr,vscatter,starflag\n"
    outputf.write(header)
    for i in range(nstars):
        line = lamost_key[i]+','+apogee_key[i]+','+\
               str(teff[i])+','+str(logg[i])+','+str(feh[i])+','+\
               str(alpha[i])+',0'+',0'+',0'+'\n'
        outputf.write(line)
 

def make_apogee_label_file():
    #lamost_key = np.loadtxt('lamost_sorted_by_ra.txt',dtype=str)
    #apogee_key = np.loadtxt('apogee_sorted_by_ra.txt', dtype=str)
    #apogee_key_short = np.array(
    #        [(item.split('v603-')[-1]).split('.fits')[0] 
    #        for item in apogee_key])
    #nstars = len(lamost_key)
    hdulist = pyfits.open("example_DR12/allStar-v603.fits")
    datain = hdulist[1].data
    apstarid= datain['APSTAR_ID']
    aspcapflag = datain['ASPCAPFLAG']
    paramflag =datain['PARAMFLAG']
    apogee_id = np.array(
            [element.split('.')[-1] for element in apstarid])
    # these are the calibrated parameters
    t = np.array(datain['TEFF'], dtype=float)
    g = np.array(datain['LOGG'], dtype=float)
    # according to Holtzman et al 2015, the most reliable values
    m = np.array(datain['PARAM_M_H'], dtype=float)
    f = np.array(datain['FE_H'], dtype=float)
    a = np.array(datain['PARAM_ALPHA_M'], dtype=float)
    mg = np.array(datain['MG_H'], dtype=float)
    mg_flag = np.array(datain['MG_H_FLAG'], dtype=float)
    ca = np.array(datain['CA_H'], dtype=float)
    ca_flag = np.array(datain['CA_H_FLAG'], dtype=float)
    vscat = np.array(datain['VSCATTER'])
    SNR = np.array(datain['SNR'])
    labels = np.vstack((t, g, m, a))

    # 1 if object would be an unsuitable training object
    mask = get_starmask(apogee_id, labels, aspcapflag, paramflag)

    # we only want the objects that are in apogee_key
    inds = np.array(
            [np.where(apogee_id==ID)[0][0] 
                for ID in apogee_key_short]) 
    teff = t[inds]
    logg = g[inds]
    mh = m[inds]
    alpha = a[inds]
    snr = SNR[inds]
    vscatter = vscat[inds]
    starflags = mask[inds]

    outputf = open("apogee_dr12_labels.csv", "w")
    header = "#lamost_id,apogee_id,teff,logg,mh,alpha,snr,vscatter,starflag\n"
    outputf.write(header)
    for i in range(nstars):
        line = lamost_key[i]+','+apogee_key[i]+','+\
               str(teff[i])+','+str(logg[i])+','+str(mh[i])+','+\
               str(alpha[i])+','+str(snr[i])+','+str(vscatter[i])+','+\
               str(starflags[i])+'\n'
        outputf.write(line)
    outputf.close()


def make_tr_file_list(frac_cut=0.94, snr_cut=100):
    """ make a list of training objects, given cuts

    Parameters
    ----------
    frac_cut: float
        the fraction of pix in the spectrum that must be good

    snr_cut: float
        the snr that the spec

    Returns
    -------
    tr_files: np array
        list of file names of training objects
    """
    allfiles = np.loadtxt(
            "apogee_dr12_labels.csv", delimiter=',', usecols=(0,), 
            dtype=str)
    allfiles_apogee= np.loadtxt(
            "apogee_dr12_labels.csv", delimiter=',', usecols=(1,), 
            dtype=str)
    starflags = np.loadtxt(
            "apogee_dr12_labels.csv", delimiter=',', usecols=(8,), dtype=str)
    #nstars = len(allfiles)
    #dir_dat = "example_LAMOST/Data_All"
    #ID, wl, flux, ivar = load_spectra(dir_dat, allfiles)
    #npix = np.float(flux.shape[1])
    #ngoodpix = np.array([np.count_nonzero(ivar[jj,:]) for jj in range(nstars)])
    #good_frac = ngoodpix/npix
    #SNR_raw = flux * ivar**0.5
    #bad = SNR_raw == 0
    #SNR_raw = np.ma.array(SNR_raw, mask=bad)
    #SNR = np.ma.median(SNR_raw, axis=1).filled()
    #good_cut = np.logical_and(good_frac > frac_cut, SNR>snr_cut)
    #starflags = starflags[np.argsort(allfiles)]
    #good = np.logical_and(good_cut, starflags=="False")
    good = starflags == "False"
    #tr_files = ID[good] #945 spectra 
    tr_files = allfiles[good]
    tr_files_apogee = allfiles_apogee[good]
    outputf = open("PAPER_training_step/tr_files.txt", "w")
    for tr_file in tr_files:
        outputf.write(tr_file + '\n')
    outputf.close()
    outputf = open("PAPER_training_step/tr_files_apogee.txt", "w")
    for tr_file in tr_files_apogee:
        outputf.write(tr_file + '\n')
    outputf.close()
    return tr_files


if __name__ == '__main__':
    make_apogee_label_file()
