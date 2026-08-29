'''
Script containing functions to estimate the mass of lithium in brines of the
Reynolds oolite unit of the Smackover Formation in southern Arkansas.
The script uses maps of predicted lithum concentrations from a random forest machine-learning model
to provide a range for the estimated lithium mass.
The user can change the values of porosity to investigate how different porosity values affect
the estimated lithium mass. The default porosity values are 10, 20, and 30%.


Author: Katherine J. Knierim
Date:   October 13, 2023
'''

import os,sys
import time
import numpy as np
import pandas as pd
import rasterio
import matplotlib.pyplot as plt


# generic function to read a raster and return numpy array and raster metadata
def ReturnArray(tif_path):
    '''
    :param tif_path: str, filepath of raster (tif) to read
    :return: tif_vals: numpy array
    :return: pm: rasterio metadata
    '''
    # read raster
    with rasterio.open(tif_path, 'r') as ds:
        tif_vals = ds.read(1)  # read all raster values
        pm = ds.profile # read raster metadata information
        pm.update(dtype=rasterio.int32, nodata=0) # update metadata information

    return tif_vals, pm


# generic function to interactively plot numpy arrays
def PlotInt(a, title='title'):
    '''
    :param a: numpy array
    :param title: string for plot title
    '''
    plt.imshow(a)
    plt.colorbar(orientation='horizontal')
    plt.title(title)
    plt.show()


# function to read and return the thickness of the Reynolds oolite unit of the Smackover Formation
def SmackoverThickness(m, plot_on):
    '''
    :param m: numpy array, array to use as mask
    :param plot_on: str, flag for whether to display interactive plots
    :return: numpy array of masked thickness values
    '''
    # read raster stack file
    evdf = pd.read_csv(os.path.join(ws, 'input', 'exvars', 'SAR_modeldomain_rasterstack.txt'))
    # read thickness (in meters) into numpy array
    smack_th = evdf['smackover_thick'].to_numpy()
    # transform to 2D array of model domain (32 rows by 90 columns)
    smack_th = np.reshape(smack_th,(32,90))
    # mask, set no data to NAN
    smack_th = np.where(m == 1, smack_th, np.nan)
    print('Smackover Thickness: ', smack_th.shape)
    print('...average: {} meters'.format(np.round(np.nanmean(smack_th), 0)))
    if plot_on == 'yes':
        PlotInt(smack_th, 'Smackover Thickness (meters)')

    return smack_th


# function to calculate the mass of lithium in the Reynolds oolite of the Smackover Formation, based on porosity (in percent)
def LithiumEstimate(porosity=[10], plot_on='yes'):
    '''
    :param porosity: list of floats, porosity value in percent (default = 10 percent)
    :param plot_on: str, flag for whether to display interactive plots, default='yes'
    :return:
    '''
    # create output folder
    if not os.path.exists('output/li_est'):
        os.mkdir('output/li_est')

    ### MASKED RASTER
    # read masking raster
    m, pm = ReturnArray(os.path.join(ws, 'grid', 'SAR_modeldomain_mask.tif'))
    if plot_on == 'yes':
        PlotInt(m, 'mask for model domain (masked = 0)')

    ### SMACKOVER THICKNESS
    # retrieve the masked Smackover Formation thickness, in meters
    smack_th = SmackoverThickness(m, plot_on)
    print('\t')

    ### BRINE PRODUCTION (2022)
    # get 2022 brine production data, in barrels
    smack_prod = ReturnArray(os.path.join(ws, 'input', 'brine', 'smackover_H2Oprod_2022.tif'))[0]

    # convert brine production to liters
    # conversions:
    # 1 barrel = 158.99 liters
    smack_prod = smack_prod * 158.99
    if plot_on == 'yes':
        PlotInt(smack_prod, 'Smackover Brine Production, 2022 (liters)')

    ### WATER RATIOS
    # read raster of water ratios based on Nehring field locations
    # assuming 90% (water ratio = 0.9) outside of oil fields
    smack_wratio = ReturnArray(os.path.join(ws, 'input', 'brine', 'smackover_H2Oratios.tif'))[0]
    if plot_on == 'yes':
        PlotInt(smack_wratio, 'Smackover Water:Oil Ratios')

    ### LITHIUM CONCENTRATION
    # create dictionary of lithium predictions (mg/L)
    liPred = {}
    liPred['low'] = os.path.join(ws, 'output', 'smackover_Li_uncertainty_p5.tif') # low estimate = 5th percentile prediction
    liPred['median'] = os.path.join(ws, 'output', 'smackover_Li_uncertainty_p50.tif')  # median estimate = 50th percentile
    liPred['high'] = os.path.join(ws, 'output', 'smackover_Li_uncertainty_p95.tif') # high estimate = 95th percentile prediction

    ### ESTIMATE MASS BASED ON POROSITY
    # loop over porosity values and estimate brine volume
    lidfs = []
    for p in porosity:
        print('BRINE VOLUME FOR {0}% POROSITY'.format(p))

        # calculate the volume of each 2-kilometer squared (4 square km) model cell, in liters
        # conversions:
        # 1 meter = 3.28 feet
        # 1 km = 1000 meters
        # 1 cubic foot = 28.3168 liters
        vol_ft3 = (smack_th * 3.28) * (2 * 1000 * 3.28) * (2 * 1000 * 3.28)
        vol_L = vol_ft3 * 28.3168

        # multiply by porosity
        vol_L = vol_L * (p / 100)

        # mask, no data = NAN
        vol_L = np.where(m == 1, vol_L, np.nan)
        vol_avg_L = np.round(np.nanmean(vol_L), 0)
        print('    ...average Smackover Pore Volume: {} liters'.format(vol_avg_L))
        vol_sum_L = np.round(np.nansum(vol_L), 0)
        print('    ...total Smackover Pore Volume: {} liters'.format(vol_sum_L))

        # multiply by water ratio
        vol_L = vol_L * smack_wratio

        # mask, no data = NAN
        vol_L = np.where(m == 1, vol_L, np.nan)
        vol_avg_L = np.round(np.nanmean(vol_L), 0)
        print('    ...average Smackover Brine Volume: {} liters'.format(vol_avg_L))
        vol_sum_L = np.round(np.nansum(vol_L), 0)
        print('    ...total Smackover Brine Volume: {} liters'.format(vol_sum_L))
        if plot_on == 'yes':
            PlotInt(vol_L, 'Volume of Brine (liters)')

        # write raster (Note: convert to Millions of Liters for raster storage, NANs = 0)
        vol_ML = np.where(m == 1, vol_L/ 1000000, 0)
        with rasterio.open(os.path.join(ws, 'output', 'li_est', 'brine_vol_ML_{}.tif'.format(p)), 'w', **pm) as dst:
            dst.write(vol_ML, 1)

        # loop over lithium predictions and estimate lithium mass
        kDict = {}
        for k, tif in liPred.items():
            print('ESTIMATING {0} LITHIUM FOR {1}% POROSITY'.format(k,p))

            # retrieve the predicted lithium concentration of the Smackover Formation brines, in mg/L
            smack_li = ReturnArray(tif)[0]
            # mask, no data = NAN
            smack_li = np.where(m == 1, smack_li, np.nan)
            li_avg_mgL = np.round(np.nanmean(smack_li),0)
            print('    ...average Smackover Lithium Concentration : {} mg/L'.format(li_avg_mgL))
            if plot_on == 'yes':
                PlotInt(smack_li, 'Lithium (mg/L)')

            # calculate the mass of lithium in each cell, in metric tons
            # conversions:
            # 1 g = 1000 mg
            # 1 kg = 1000 g
            # 1 metric ton = 1000 kg
            li_ton = np.round(vol_L * smack_li / (1000 * 1000 * 1000), 0)
            li_sum_tn = np.round(np.nansum(li_ton), 0)
            print('    ...mass of Lithium: {} metric tons'.format(li_sum_tn))
            if plot_on == 'yes':
                PlotInt(li_ton, 'Lithium (metric tons)')

            # write raster (Note: NANs = 0)
            li_ton = np.where(m == 1,  li_ton, 0)
            with rasterio.open(os.path.join(ws, 'output', 'li_est', 'li_tons_{}{}.tif'.format(k, p)), 'w',
                               **pm) as dst:
                dst.write(li_ton, 1)

            # calculate the mass of lithium extracted in 2022
            # conversions:
            # 1 g = 1000 mg
            # 1 kg = 1000 g
            # 1 metric ton = 1000 kg
            smack_li_prod = smack_prod * smack_li / (1000 * 1000 * 1000)
            # mask, no data = NAN
            smack_li_prod = np.where(m == 1, smack_li_prod, np.nan)
            li_sum_tn_ex = np.round(np.nansum(smack_li_prod), 0)
            print('    ...mass of Lithium Extracted in 2022: {} metric tons'.format(li_sum_tn_ex))
            print('\t')

            # load values into dictionary (average brine volume, average Li concentration, summed Li mass, summed Li extracted)
            kDict[k] = [vol_avg_L, vol_sum_L, li_avg_mgL, li_sum_tn, li_sum_tn_ex]

        # convert lithium dictionary to dataframe
        pdf = pd.DataFrame.from_dict(kDict, orient='index', columns=['avgVol_L', 'sumVol_L', 'avgLi_mgL', 'sumLi_ton', 'sumLi_ton_ext'])
        pdf['model'] = pdf.index
        pdf['porosity_perc'] = p
        # append dataframe to list
        lidfs.append(pdf)

    # concatentate dataframes into summary data frame
    df = pd.concat(lidfs)

    # convert tons of Li to lithium carbonate (Li2CO3) equivalent (LCE)
    # conversions:
    # 1 metric ton = 1000 kg
    # 2 mol Li = 1 mol Li2CO3
    # Li = 6.941 g/mol
    # Li2CO3 = 73.89 g/mol
    df['sumLi_LCE'] = np.round(df['sumLi_ton'] * (73.89/(6.941*2)), 0)

    # write out
    df = df[['model', 'avgLi_mgL', 'porosity_perc', 'avgVol_L', 'sumVol_L',  'sumLi_ton', 'sumLi_LCE', 'sumLi_ton_ext']]
    df['perc_ext'] = np.round(df['sumLi_ton_ext'] / df['sumLi_ton'] * 100,4)
    dt = time.strftime('%Y_%m%d', time.localtime())
    df.to_csv(os.path.join(ws, 'output', 'SAR_smackover_Liestimate_{}.csv'.format(dt)), index=False)










if __name__ == '__main__':
    ws = os.getcwd()
    print('current workspace:', ws)
    print('\t')

    # user entry to change porosity values
    # to re-create the published lithium mass estimates, use 10, 20, and 30% porosity values.
    porosity = [10,20,30]
    LithiumEstimate(porosity, plot_on='yes')