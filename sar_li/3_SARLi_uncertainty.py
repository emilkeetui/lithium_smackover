'''
Script to calculate uncertainty using the output of predicted lithium concentrations across the model domain based on
all models with a root-mean-square-error (RMSE) within one standard error of the model with the lowest RMSE model,
also known as "one-se models"

Author: Katherine J. Knierim
Date:   October 13, 2023
'''

import os,sys
import time
import glob
import numpy as np
import pandas as pd
import rasterio


def CalcUnc():

    ### read uncertainty rasters
    # get list of tifs
    tifs = glob.glob(os.path.join(ws, 'output', 'uncertainty','*.tif'))
    print('{} uncertainty tifs'.format(len(tifs)))

    # create empty dictionary
    ras_dict = {}

    # loop over tifs, read, and save to dataframe
    for t in tifs:
        tname = os.path.splitext(os.path.basename(t))[0]
        tname = tname.split('_')[2]
        with rasterio.open(t, 'r') as r:
            r_vals = r.read(1)
            ras_dict['m{}'.format(tname)] = r_vals.flatten()
    df = pd.DataFrame.from_dict(ras_dict)

    # replace missing flag (-99) with NAN for calculations
    df = df.replace(-99, np.nan)

    ### summarize uncertainty rasters
    # calc stats across rows so each cell represents a statistic of predictions at that cell
    df['min'] = df.apply(lambda x: x.min(), axis=1)
    df['p5'] = df.apply(lambda x: np.percentile(x, 5), axis=1)
    df['p25'] = df.apply(lambda x: np.percentile(x, 25), axis=1)
    df['p50'] = df.apply(lambda x: np.percentile(x, 50), axis=1)
    df['p75'] = df.apply(lambda x: np.percentile(x, 75), axis=1)
    df['p95'] = df.apply(lambda x: np.percentile(x, 95), axis=1)
    df['max'] = df.apply(lambda x: x.max(), axis=1)
    df['rngp'] = df['p95'] - df['p5']

    ### calculate qualitative uncertainty
    thresh = 100
    # set low estimate event flag
    df['lowE'] = np.nan
    df.loc[df['p5'] <= thresh, 'lowE'] = 0
    df.loc[df['p5'] > thresh, 'lowE'] = 1

    # set median event flag
    df['medE'] = np.nan
    df.loc[df['p50'] <= thresh, 'medE'] = 0
    df.loc[df['p50'] > thresh, 'medE'] = 1

    # set high estimate event flag
    df['highE'] = np.nan
    df.loc[df['p95'] <= thresh, 'highE'] = 0
    df.loc[df['p95'] > thresh, 'highE'] = 1

    # establish qual unc groups
    df['qualunc'] = -99 # set missing flag
    df.loc[(df['lowE'] == 0) & (df['medE'] == 0) & (df['highE'] == 0), 'qualunc'] = 0 # very likely below threshold
    df.loc[(df['lowE'] == 0) & (df['medE'] == 0) & (df['highE'] == 1), 'qualunc'] = 1 # likely below threshold
    df.loc[(df['lowE'] == 0) & (df['medE'] == 1) & (df['highE'] == 1), 'qualunc'] = 2 # likely above threshold
    df.loc[(df['lowE'] == 1) & (df['medE'] == 1) & (df['highE'] == 1), 'qualunc'] = 3 # very likely above threshold

    # replace missing (NAN) with missing data flag (-99)
    df = df.replace(np.nan, -99)

    ### write out rasters
    # get raster metadata info to create new raster
    with rasterio.open(tifs[1], 'r') as r:
        meta = r.meta.copy()
        meta.update(compress='lzw')

    dt = time.strftime('%Y_%m%d', time.localtime())

    # write summaries to new raster
    df_cols = ['p5', 'p95', 'p50', 'rngp', 'qualunc']
    for x in df_cols:
        newras = os.path.join('output','smackover_Li_uncertainty_{}_{}.tif'.format(x, dt))
        with rasterio.open(newras, 'w+', **meta) as out:
            df[x] = np.round(df[x],0)
            vals = df[x].to_numpy()
            r_vals = np.reshape(vals, (32, 90))
            out.write(r_vals, 1)








if __name__ == '__main__':
    ws = os.getcwd()
    print('current workspace:', ws)

    CalcUnc()