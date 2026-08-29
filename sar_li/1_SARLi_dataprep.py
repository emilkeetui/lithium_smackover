'''
Script to prepare the input data for the machine-learning model of lithium. Steps include:

1) Download the U.S. Geological Survey's National Produced Waters Geochemical Database v 3.0
from ScienceBase. If the user is unable to use the 'sciencebasepy' package, manually download
the 'USGS_NPWGDv3_excel.xlsx' file from: https://www.sciencebase.gov/catalog/item/64fa1e71d34ed30c2054ea11
2) Prepare and merge the USGS Produced Waters Geochemical Database v 3.0 and the 2022 sample results
3) Merge the response variable (Li) with explanatory variable file

Author: Katherine J. Knierim
Date:   October 13, 2023
'''

import os, sys
import time
import sciencebasepy
import numpy as np
import pandas as pd
from shapely.geometry import Point
import geopandas as gp


# Function to download the U.S. Geological Survey's Produced Waters Geochemical Database version 3
# If the user is unable to use the 'sciencebasepy' package, manually download
# the 'USGS_NPWGDv3_excel.xlsx' file from: https://www.sciencebase.gov/catalog/item/64fa1e71d34ed30c2054ea11
def DownloadPWGD():
    # create folder
    pw_ws = os.path.join(ws, 'input', 'usgs_pwgd')
    if not os.path.exists(pw_ws):
        os.mkdir(pw_ws)

    # check if file already downloaded
    filename = 'USGS_NPWGDv3_excel.xlsx'
    SBID = '64fa1e71d34ed30c2054ea11'

    if not os.path.exists(os.path.join(pw_ws, filename)):
        print('USGS Produced Waters Geochemical Database is downloaded...')
        print('    ...downloading')
        # Instantiate method
        sb = sciencebasepy.SbSession()
        sb_json = sb.get_item(SBID)

        # Get item info
        sb_info = sb.get_item_file_info(sb_json)
        print('There are {} items'.format(len(sb_info)))

        item_names = {}
        for i in sb_info:
            nm = i['name']
            url = i['url']
            item_names[nm] = url
        print(item_names)
        print('\t')

        # download from url
        sb.download_file(item_names[filename], filename, pw_ws)
        print('    ...downloaded: {}'.format(filename))


# function to filter and prepare U.S. Geological Survey's Produced Waters Geochemical Database version 3 database
def PreparePWGD():
    ##################################
    ##          READ FILE          ###
    ##################################
    # read downloaded USGS PWGD v3 file
    # If the user is unable to use the 'sciencebasepy' package, manually download
    # the 'USGS_NPWGDv3_excel.xlsx' file from: https://www.sciencebase.gov/catalog/item/64fa1e71d34ed30c2054ea11
    pwdb_file = os.path.join('input', 'usgs_pwgd', 'USGS_NPWGDv3_excel.xlsx')
    df = pd.read_excel(pwdb_file, dtype={'IDUSGS':str})
    print('USGS PRODUCED WATERS DATABASE:', df.shape)
    print(df.columns.tolist())

    ##################################
    ##       FILTER AND PREP       ###
    ##################################
    # filter for relevant metadata columns
    mcols = ['IDUSGS', 'IDORIG', 'IDDB', 'SOURCE', 'REFERENCE', 'API', 'WELLNAME', 'FIELD',
             'STATE', 'COUNTY', 'LATITUDE', 'LONGITUDE',
             'REGION', 'PROVINCE', 'BASIN', 'DEPTHUPPER', 'DEPTHLOWER', 'FORMATION',
             'DATESAMPLE']
    # filter for relevant wq columns
    wqcols = ['POROSITY', 'TEMP', 'PRESSURE', 'SG', 'SPGRAV', 'SPGRAVT', 'RESIS', 'RESIST',
              'COND', 'PH', 'TDS', 'TDSDESC',
              'Ag', 'Al', 'As', 'Au', 'B', 'BO3', 'Ba', 'Be', 'Bi', 'Br', 'CO3', 'HCO3', 'Ca', 'Cd', 'Cl', 'Co',
              'Cr', 'Cs', 'Cu', 'F', 'FeTot', 'FeIII', 'FeII', 'FeS', 'FeAl', 'FeAl2O3', 'Hg', 'I', 'K', 'KNa', 'Li',
              'Mg', 'Mn', 'Mo', 'N', 'NO2', 'NO3', 'NO3NO2', 'NH4', 'TKN', 'Na', 'Ni', 'OH', 'P', 'PO4', 'Pb', 'Rh',
              'Rb', 'S', 'SO3', 'SO4', 'HS', 'Sb', 'Sc', 'Se', 'Si', 'Sn', 'Sr', 'Ti', 'Tl', 'U', 'V', 'W', 'Zn',
              'ALKALINITY', 'DIC', 'DOC', 'TOC',
              'Ar', 'CH4', 'C2H6', 'CO2', 'H2', 'H2S', 'He', 'N2', 'NH3', 'O2',
              'dD', 'd18O']
    df = df.loc[:, mcols + wqcols]

    # add dataset id
    df.insert(0, 'DSOURCE', 'PWDB_v3')

    # filter for states of interest
    state_list = ['Arkansas', 'Louisiana', 'Mississippi', 'Alabama', 'Texas']
    df = df.loc[df['STATE'].isin(state_list)]
    print('... filtered for {}:'.format(state_list), df.shape)

    # filter for region of interest
    df = df.loc[df['REGION'] == 'Gulf Coast']
    print('... filtered for Gulf Coast:', df.shape)

    # filter for provinces of interest
    prov_list = ['East Texas Basin', 'Louisiana-Mississippi Salt Basins']
    df = df.loc[df['PROVINCE'].isin(prov_list)]
    print('... filtered for {}:'.format(prov_list), df.shape)

    # convert columns to numeric
    for c in wqcols:
        df[c] = pd.to_numeric(df[c], errors='coerce')

    # include H2S field with NDs (-8888) for Moldovanyi H2S samples
    df['H2Sx'] = df['H2S']
    df.loc[(df['IDDB'] == 'MOLDOVANYI') & (df['H2S'].isna()), 'H2Sx'] = -8888  # NDs
    df['H2S'] = df['H2Sx']
    df = df.drop(['H2Sx'], axis=1)

    # crosswalk column names
    col_names = {'IDUSGS':'SITEID',
                'd18O': 'd18O_H2O',
                 'dD': 'dD_H2O'}
    df = df.rename(columns=col_names)

    ##################################
    ##     PREP FORMATIONS         ###
    ##################################
    # Group formations and summarize
    df['FRM_GRP'] = 'Other'
    df.loc[df['FORMATION'].str.lower().str.contains('unknown'), 'FRM_GRP'] = 'Other'

    # TERTIARY UNITS
    df.loc[df['FORMATION'].str.lower().str.contains('jackson|vicksburg'), 'FRM_GRP'] = 'Vicksburg'
    df.loc[df['FORMATION'].str.lower().str.contains('claiborne|sparta|sprt'), 'FRM_GRP'] = 'Claiborne'
    df.loc[df['FORMATION'].str.lower().str.contains('wilcox|wlcx'), 'FRM_GRP'] = 'Wilcox'
    df.loc[df['FORMATION'].str.lower().str.contains('midway'), 'FRM_GRP'] = 'Midway'

    # NACATOCH
    df.loc[df['FORMATION'].str.lower().str.contains('nacatoch'), 'FRM_GRP'] = 'Nacatoch'
    df.loc[df['FORMATION'].str.lower().str.contains('meakin'), 'FRM_GRP'] = 'Nacatoch'
    df.loc[df['FORMATION'].str.lower().str.contains('meekin'), 'FRM_GRP'] = 'Nacatoch'  # assume misspelled
    df.loc[df['FORMATION'].str.lower().str.contains('graves'), 'FRM_GRP'] = 'Nacatoch'
    df.loc[df['FORMATION'].str.lower().str.contains('blossom'), 'FRM_GRP'] = 'Nacatoch'

    # TOKIO
    df.loc[df['FORMATION'].str.lower().str.contains('tokio'), 'FRM_GRP'] = 'Tokio'
    df.loc[df['FORMATION'].str.lower().str.contains('takio'), 'FRM_GRP'] = 'Tokio'  # assume misspelled

    # TUSCALOOSA GROUP
    df.loc[df['FORMATION'].str.lower().str.contains('tuscaloosa'), 'FRM_GRP'] = 'Tuscaloosa Grp'

    # WASHITA GROUP
    df.loc[df['FORMATION'].str.lower().str.contains('paluxy'), 'FRM_GRP'] = 'Washita Grp'

    # TRINITY GROUP - Includes Glen Rose Subgroup = Pine Island, Rodessa, Mooringsport Formations
    df.loc[df['FORMATION'].str.lower().str.contains('glen rose'), 'FRM_GRP'] = 'Trinity Grp'  # subgroup
    df.loc[df['FORMATION'].str.lower().str.contains('glenn rose'), 'FRM_GRP'] = 'Trinity Grp'  # subgroup, assume misspelling
    df.loc[
        df['FORMATION'].str.lower().str.contains('rodessa'), 'FRM_GRP'] = 'Trinity Grp'  # formation within GR subgroup
    df.loc[df['FORMATION'].str.lower().str.contains('jeter'), 'FRM_GRP'] = 'Trinity Grp'  # member of Rodessa
    df.loc[df['FORMATION'].str.lower().str.contains('gloyd'), 'FRM_GRP'] = 'Trinity Grp'  # member of Rodessa
    df.loc[df['FORMATION'].str.lower().str.contains('mitchell'), 'FRM_GRP'] = 'Trinity Grp'  # informal
    df.loc[df['FORMATION'].str.lower().str.contains('hill'), 'FRM_GRP'] = 'Trinity Grp'  # TX reservoir within Rodessa
    df.loc[df['FORMATION'].str.lower().str.contains('young'), 'FRM_GRP'] = 'Trinity Grp'  # informal
    df.loc[df['FORMATION'].str.lower().str.contains('kilpatrick'), 'FRM_GRP'] = 'Trinity Grp'  # informal
    df.loc[df['FORMATION'].str.lower().str.contains(
        'kit patrick'), 'FRM_GRP'] = 'Trinity Grp'  # assume misspelling of kilpatrick
    df.loc[df['FORMATION'].str.lower().str.contains('james'), 'FRM_GRP'] = 'Trinity Grp'

    # NUEVO LEON
    # Sligo / Pettet / Pettit
    df.loc[df['FORMATION'].str.lower().str.contains('sligo'), 'FRM_GRP'] = 'Nuevo Leon Grp'
    df.loc[df['FORMATION'].str.lower().str.contains('pettet'), 'FRM_GRP'] = 'Nuevo Leon Grp'
    df.loc[df['FORMATION'].str.lower().str.contains('pettit'), 'FRM_GRP'] = 'Nuevo Leon Grp'  # TX reservoir spelling
    df.loc[df['FORMATION'].str.lower().str.contains('petit'), 'FRM_GRP'] = 'Nuevo Leon Grp'  # TX reservoir spelling
    # Travis Peak / Hosston
    df.loc[df['FORMATION'].str.lower().str.contains('travis peak'), 'FRM_GRP'] = 'Nuevo Leon Grp'
    df.loc[df['FORMATION'].str.lower().str.contains('hosston'), 'FRM_GRP'] = 'Nuevo Leon Grp'

    # COTTON VALLEY
    df.loc[df['FORMATION'].str.lower().str.contains('cotton valley'), 'FRM_GRP'] = 'Cotton Valley'

    # HAYNESVILLE
    df.loc[df['FORMATION'].str.lower().str.contains('haynesville'), 'FRM_GRP'] = 'Haynesville'

    # SMACKOVER
    df.loc[df['FORMATION'].str.lower().str.contains('smackover|smkv'), 'FRM_GRP'] = 'Smackover'
    df.loc[df['FORMATION'].str.lower().str.contains('reynolds'), 'FRM_GRP'] = 'Smackover'

    # NORPHLET
    df.loc[df['FORMATION'].str.lower().str.contains('norphlet'), 'FRM_GRP'] = 'Norphlet'

    ##################################
    ##         PREP DEPTHS         ###
    ##################################
    # read updated depth file and filter columns
    dep_new = pd.read_csv(os.path.join(ws, 'input', 'usgs_pwgd', 'sar_pwgdv3_updateddepths.csv'), dtype={'IDUSGS': str})
    dep_new['SITEID'] = dep_new['IDUSGS']
    dep_new['SITEID'] = dep_new['SITEID'].astype(str)
    dep_new = dep_new.loc[:, ['SITEID', 'DEPTHUPPER', 'DEPTHLOWER']]

    # merge with pwdb v3 and replace depths
    df = df.merge(dep_new, on='SITEID', how='outer')
    df = df.replace(np.nan, -9999)
    df['DEPTHUPPER'] = df['DEPTHUPPER_x']
    df.loc[df['DEPTHUPPER_x'] == -9999, 'DEPTHUPPER'] = df['DEPTHUPPER_y']
    df['DEPTHLOWER'] = df['DEPTHLOWER_x']
    df.loc[df['DEPTHLOWER_x'] == -9999, 'DEPTHLOWER'] = df['DEPTHLOWER_y']
    df = df.drop(labels=['DEPTHUPPER_x', 'DEPTHUPPER_y', 'DEPTHLOWER_x', 'DEPTHLOWER_y'], axis=1)

    print('\t')
    return df


# function to merge data collected in August 2022 with the U.S. Geological Survey's Produced Waters Geochemical Database version 3
def PrepareMLFile():
    # download and prepare USGS Produced Waters Geochemical Database version 3
    DownloadPWGD()
    pwdf = PreparePWGD()

    # read the 2022 brine sample file
    ardf = pd.read_csv(os.path.join('input', 'usgs_southAR', 'southAR_brines_2022.txt'))
    print('SOUTHERN AR 2022 SAMPLES:', ardf.shape)
    print('\t')

    # merge datasets
    df = pd.concat([pwdf, ardf], axis=0).reset_index()
    print('MERGED DATA: {:,}'.format(df.shape[0]))
    print('\t')

    # create combined depth field
    df = df.replace(np.nan, -9999)
    df['DEPTH'] = df['DEPTHLOWER']
    df.loc[df['DEPTHLOWER'] == -9999, 'DEPTH'] = df['DEPTHUPPER']
    # convert to meters
    df['DEPTH_m'] = np.round(df['DEPTH'] / 3.281, 0)
    df.loc[df['DEPTH'] == -9999, 'DEPTH_m'] = -9999

    # create numeric lithium column and separate censoring flag
    df['Li_orig'] = df['Li'].astype(str)
    df['Li'] = df['Li_orig'].str.replace('<', '')
    df['Li'] = pd.to_numeric(df['Li'], errors='coerce')
    df['Li_rmk'] = 'xx'
    df.loc[df['Li_orig'].str.contains('<'), 'Li_rmk'] = '<'

    # create geopandas object
    df['DATESAMPLE'] = df['DATESAMPLE'].astype(str)
    df['geometry'] = df.apply(lambda x: Point(float(x['LONGITUDE']), float(x['LATITUDE'])), axis=1)
    gpdf = gp.GeoDataFrame(df, geometry='geometry')
    gpdf.crs = 'EPSG:4269'  # NAD83
    gpdf.to_file(os.path.join('input','gulfcoast_brines'))

    # clip to model domain
    modeldom_clip = gp.read_file(os.path.join(ws, 'grid', 'SAR_modeldomain_4269.shp'))
    newdf = gp.clip(gpdf, modeldom_clip)
    print('... dataset clipped to southern AR model domain:', newdf.shape)
    print('\t')

    # filter for relevant columns
    newdf = newdf.loc[:, ['DSOURCE', 'SITEID', 'LATITUDE', 'LONGITUDE', 'FRM_GRP', 'DEPTH_m', 'Li_rmk', 'Li']]

    # read explanatory variable file
    evdf = pd.read_csv(os.path.join(ws, 'input', 'exvars', 'SAR_explanatoryvars.txt'))
    print('EXPLANATORY VARIABLES: ', evdf.shape)

    # merge
    outdf = newdf.merge(evdf, how='right', on='SITEID')
    print('FINAL MERGED FILE FOR ML MODEL: ', outdf.shape)

    # write out
    outdf.to_csv(os.path.join('input', 'SAR_MLinput.txt'), index=False, sep=',')





if __name__ == '__main__':
    ws = os.getcwd()
    print('current workspace:', ws)
    print('\t')

    PrepareMLFile()


