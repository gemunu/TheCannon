import matplotlib.pyplot as plt
from math import log10, floor
from matplotlib import rc
import matplotlib.gridspec as gridspec
from matplotlib.colors import LogNorm
plt.rc('text', usetex=True)
plt.rc('font', family='serif')
import numpy as np

def round_sig(x, sig=2):
    if x < 0:
        return -round(-x, sig-int(floor(log10(-x)))-1)
    return round(x, sig-int(floor(log10(x)))-1)


#label_names_all = ['T_{eff}', '\log g', '[M/H]', '[\\alpha/Fe]', 'Al', 'Ca',
#               'C', 'Fe', 'K', 'Mg', 'Mn','Na', 'Ni','N', 'O', 'Si', 'S',
#               'Ti', 'V']
label_names_all = ['T_{eff}', '\log g', 'Al/Fe', 'Ca/Fe',
               'C/Fe', 'Fe/H', 'K/Fe', 'Mg/Fe', 'Mn/Fe','Na/Fe', 'Ni/Fe','N/Fe', 'O/Fe', 
               'Si/Fe', 'S/Fe', 'Ti/Fe', 'V/Fe']

units_all = ['K']
for label in label_names_all[1:]:
    units_all.append('dex')

start = 8
end = 17
names = label_names_all[start:end]
units = units_all[start:end]

all_cannon = np.load("run_14_all_abundances_fe/all_cannon_labels.npz")['arr_0']
all_ids = np.load("run_14_all_abundances_fe/test_id.npz")['arr_0']
all_apogee = np.load("run_14_all_abundances_fe/test_label.npz")['arr_0']

good = np.min(all_cannon, axis=1) > -500
all_cannon = all_cannon[good]
good_id = all_ids[good]
all_apogee = all_apogee[good]

snr = np.load("run_14_all_abundances_fe/test_snr.npz")['arr_0'][good]

IDs_lamost = np.loadtxt(
        "../examples/test_training_overlap/lamost_sorted_by_ra_with_dr2_params.txt",
        usecols=(0,), dtype=(str))
labels_all_lamost = np.loadtxt(
        "../examples/test_training_overlap/lamost_sorted_by_ra_with_dr2_params.txt",
        usecols=(3,4,5), dtype=(float))
inds = np.array([np.where(IDs_lamost==a)[0][0] for a in good_id])
lamost = labels_all_lamost[inds,:]

apogee = all_apogee[:,start:end]
cannon = all_cannon[:,start:end]

fig = plt.figure(figsize=(10,12))
gs = gridspec.GridSpec(5,2, wspace=0.3, hspace=0.3)

#lows = [3800, 0, -1.7,-0.08, -1.0, -1.5, -0.8, -1.3, -1.5, -1.0,
#        -1.0, -1.5, -1.5, -1.2, -0.7, -0.7, -0.7, -1.1, -2.4]
lows = [3800, 0, -0.4, -0.5, -0.2, -0.3, -1.0, -0.4, -0.2, -0.3, 
        -0.3, -0.15, -0.1, -0.0, -0.0, -0.2, -0.4]
lows = lows[start:end]
#highs = [5500, 5.1, 0.55, 0.41, 0.47, 0.86, 0.64, 0.56, 0.45, 0.44,
#        0.56, 0.58, 0.70, 0.44, 0.52, 0.64, 0.6, 0.62, 0.8]
highs = [5500, 5.1, 0.3, 0.6, 0.5, 0.3, 0.45, 0.2, 0.3, 0.3, 
        0.30, 0.1, 0.4, 0.5, 0.5, 0.2, 0.4]
highs = highs[start:end]

obj = []

for i in range(0, len(names)):
    name = names[i]
    unit = units[i]
    #low = mins[i]
    #high = maxs[i]
    
    choose = snr > 80 
    diff_cannon = cannon[:,i][choose]-apogee[:,i][choose]
    scatter = round_sig(np.std(diff_cannon),3)
    y_cannon = cannon[:,i][choose]
    y_apogee = apogee[:,i][choose]

    ax = plt.subplot(gs[i])
    #low = np.min([np.min(y_apogee), np.min(y_cannon)])
    #high = np.max([np.max(y_apogee), np.max(y_cannon)])
    low = lows[i]
    high = highs[i]
    print(low, high)
    ax.hist2d(y_apogee, y_cannon, norm=LogNorm(), range=[[low,high],[low,high]], bins=60, 
            cmap="gray_r")
    ax.plot([low,high], [low,high], c='k',label="x=y")
    ax.tick_params(axis='x', labelsize=14)
    ax.tick_params(axis='y', labelsize=14)
    if i > 7:
        ax.set_xlabel("APOGEE Value", fontsize=16)
    ax.set_ylabel(r"$%s \mathrm{(%s)}$" %(name,unit), fontsize=16)
    text = "Scatter: %s" %scatter
    ax.text(0.05, 0.90, text, horizontalalignment='left', verticalalignment='top',
            transform=ax.transAxes)


#plt.show()
plt.savefig("xval_6panel_8_17_nomalpha_snr80.png")
