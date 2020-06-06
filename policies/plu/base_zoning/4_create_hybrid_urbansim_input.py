USAGE="""

  Given a hybrid configuration index, generates UrbanSim inpput files.

  Input:  p10_plu_boc_allAttrs.csv, p10 combined with pba40 and basis boc data output by 1_PLU_BOC_data_combine.py
          hybrid configuration index indicating which variable/jurisdiction will use BASIS data verus PBA40 data

  Output: 

"""

import pandas as pd
import numpy as np
import argparse, os, logging, sys, time


if os.getenv('USERNAME')    =='ywang':
    BOX_DIR                 = 'C:\\Users\\{}\\Box\\Modeling and Surveys\\Urban Modeling\\Bay Area UrbanSim 1.5\\PBA50'.format(os.getenv('USERNAME'))
    GITHUB_PETRALE_DIR      = 'C:\\Users\\{}\\Documents\\GitHub\\petrale\\'.format(os.getenv('USERNAME'))
elif os.getenv('USERNAME')  =='lzorn':
    BOX_DIR                 = 'C:\\Users\\lzorn\\Box\\Modeling and Surveys\\Urban Modeling\\Bay Area UrbanSim 1.5\\PBA50'.format(os.getenv('USERNAME'))
    GITHUB_PETRALE_DIR      = 'X:\\petrale'


# input file locations
PLU_BOC_DIR                 = os.path.join(BOX_DIR, 'Policies\\Base zoning\\outputs')
PLU_BOC_FILE                = os.path.join(PLU_BOC_DIR, '2020_06_03_p10_plu_boc_allAttrs.csv')
HYBRID_INDEX_DIR            = os.path.join(GITHUB_PETRALE_DIR, 'policies\\plu\\base_zoning\\hybrid_index')
# TODO: change to idx_urbansim.csv when we have one
HYBRID_INDEX_FILE           = os.path.join(HYBRID_INDEX_DIR, "idx_urbansim_heuristic.csv")

PBA40_ZONING_BOX_DIR        = os.path.join(BOX_DIR, 'OLD Horizon Large General Input Data')
PBA50_ZONINGMOD_DIR         = os.path.join(BOX_DIR, 'Policies\\Zoning Modifications')

# output file locations
HYBRID_ZONING_OUTPUT_DIR    = os.path.join(BOX_DIR, 'Policies\\Base zoning\\outputs\\hybrid_base_zoning')
ZONING_FOR_URBANSIM_DIR     = os.path.join(BOX_DIR, 'Policies\\Base zoning\\outputs\\for_urbansim')

# human-readable idx values
USE_PBA40 = 0
USE_BASIS = 1

if __name__ == '__main__':


    for hybrid_idx_file in list(glob.glob(HYBRID_INDEX_DIR+'/*.csv')):
        hybrid_name = os.path.basename(hybrid_idx_file).split('.')[0][4:]
        logger.info('Hybrid version: {}'.format(hybrid_name))
        hybrid_idx = pd.read_csv(hybrid_idx_file)
        hybrid_idx.rename(columns = {'MAX_FAR_idx'   : 'max_far_idx', 
                                     'MAX_DUA_idx'   : 'max_dua_idx',
                                     'MAX_HEIGHT_idx': 'max_height_idx'}, inplace = True)

        hybrid_idx.set_index('juris_name',inplace = True)
        juris_list = list(hybrid_idx.index.values)

        logger.debug("hybrid_idx.head():\n{}".format(hybrid_idx.head()))

        # make a copy so we don't modify the zoning data before hybrid
        plu_boc_before_hybrid = plu_boc.copy()
        
        for devType in dev_capacity_calculation_module.ALLOWED_BUILDING_TYPE_CODES:
            logger.info('Before applying index, parcel counts by data source for development type {}\n{}'.format(devType,
                        plu_boc_before_hybrid[devType+'_idx'].value_counts()))
              
        plu_boc_hybrid = create_hybrid_parcel_data_from_juris_idx(plu_boc_before_hybrid,hybrid_idx)
        
        for devType in dev_capacity_calculation_module.ALLOWED_BUILDING_TYPE_CODES:
            logger.info('After applying index, parcel counts by data source for development type {}:\n{}'.format(devType,
                        plu_boc_hybrid[devType+'_idx'].value_counts()))
            
        for intensity in ['max_far','max_far','max_height']:
            logger.info('Parcel counts by data source for density type {}:\n{}'.format(intensity,
                        logger.info(plu_boc_hybrid[intensity+'_idx'].value_counts())))
            
        # recalculate 'allow_res' and 'allow_nonres' based on the allowable development type
        allowed_basis    = dev_capacity_calculation_module.set_allow_dev_type(plu_boc_hybrid,'basis')
        allowed_pba40    = dev_capacity_calculation_module.set_allow_dev_type(plu_boc_hybrid,'pba40')
        allowed_urbansim = dev_capacity_calculation_module.set_allow_dev_type(plu_boc_hybrid,'urbansim')
        
        # drop the previous 'allow_res' and 'allow_nonres' and insert the new ones
        plu_boc_hybrid.drop(columns = ['allow_res_basis', 'allow_nonres_basis', 
                                       'allow_res_pba40', 'allow_nonres_pba40'], inplace = True)
        plu_boc_hybrid = plu_boc_hybrid.merge(allowed_basis, 
                                              on = 'PARCEL_ID', 
                                              how = 'left').merge(allowed_pba40, 
                                                                  on = 'PARCEL_ID', 
                                                                  how = 'left').merge(allowed_urbansim,
                                                                                      on = 'PARCEL_ID', 
                                                                                      how = 'left' ) 

        logger.info('Export hybrid zoning of {} record:'.format(len(plu_boc_hybrid)))
        logger.info(plu_boc_hybrid.dtypes)

        # export hybrind zoning file to "interim" or "final" folder based on if they are for evaluation or for UrbanSim use
        if process == 'interim':
            HYBRID_ZONING_OUTPUT_DIR = INTERIM_HYBRIND_ZONING_DIR
        
        plu_boc_hybrid.to_csv(os.path.join(HYBRID_ZONING_OUTPUT_DIR, today+'_p10_plu_boc_'+hybrid_name+'.csv'),index = False)


        # For urbansim version of the hybrid, create BAUS base zoning input files and export
        if hybrid_name == 'urbansim':
            logger.info('Create BAUS base zoning input files:')

            # select hybrid fields
            plu_boc_urbansim_cols = ['PARCEL_ID','geom_id','county_id','county_name', 'juris_zmod', 'jurisdiction_id', 'ACRES',
                                     'pba50zoningmodcat_zmod','nodev_zmod','name_pba40','plu_code_basis'] + [
                                     devType + '_urbansim' for devType in dev_capacity_calculation_module.ALLOWED_BUILDING_TYPE_CODES] + [
                                     intensity + '_urbansim' for intensity in ['max_dua','max_far','max_height']]

            plu_boc_urbansim = plu_boc_hybrid[plu_boc_urbansim_cols]

            # rename the fields to remove '_urbansim'
            plu_boc_urbansim.columns = ['PARCEL_ID','geom_id','county_id','county_name', 'juris_zmod', 'jurisdiction_id', 'ACRES',
                                        'pba50zoningmodcat_zmod','nodev_zmod','name_pba40','plu_code_basis'] + dev_capacity_calculation_module.ALLOWED_BUILDING_TYPE_CODES + [
                                        'max_dua','max_far','max_height']

            # convert allowed types to integer
            for attr in dev_capacity_calculation_module.ALLOWED_BUILDING_TYPE_CODES:
                plu_boc_urbansim[attr] = plu_boc_urbansim[attr].fillna(-1).astype(int)
            plu_boc_urbansim.replace({-1: None}, inplace = True)

            # create zoning_lookup table with unique jurisdiction and zoning attributes
            zoning_lookup_pba50 = plu_boc_urbansim[['county_name','juris_zmod'] + dev_capacity_calculation_module.ALLOWED_BUILDING_TYPE_CODES + ['max_dua','max_far','max_height']].drop_duplicates()     

            # sort zoning type by county and jurisdiction and assign zoning_id
            zoning_lookup_pba50.sort_values(by=['county_name', 'juris_zmod'], inplace = True)
            zoning_lookup_pba50['zoning_id_pba50'] = range(1,len(zoning_lookup_pba50) + 1)
            logger.info('Zoning lookup table has {} unique types (juris + zoning attributes), header:'.format(len(zoning_lookup_pba50)))
            logger.info(zoning_lookup_pba50.head())
            
            # create zoning_parcels file and attach zoning_id 
            plu_boc_urbansim_ID = plu_boc_urbansim.merge(zoning_lookup_pba50,
                                                         on = list(zoning_lookup_pba50)[:-1],
                                                         how = 'left')
            zoning_parcels_pba50 = plu_boc_urbansim_ID[['PARCEL_ID','geom_id','juris_zmod','jurisdiction_id','zoning_id_pba50','nodev_zmod']]

            # bring into other attributes from Horizon:
            zoning_parcels_pba40_file = os.path.join(PBA40_ZONING_BOX_DIR, '2015_12_21_zoning_parcels.csv')
            zoning_parcels_pba40 = pd.read_csv(zoning_parcels_pba40_file, 
                              usecols = ['geom_id','prop'])
            zoning_parcels_pba50 = zoning_parcels_pba50.merge(zoning_parcels_pba40, on = 'geom_id', how = 'left')          


            ## assign zoning name to each zoning_id based on the most frequent occurance of zoning name among all the parcels with the same zoning_id
            zoning_names = plu_boc_urbansim[['PARCEL_ID','name_pba40','plu_code_basis']]

            # merge zoning names of pba40 and BASIS into zoning_parcels
            zoning_names['name_pba40'] = zoning_names['name_pba40'].apply(lambda x: str(x)+'_pba40')
            zoning_names['plu_code_basis'] = zoning_names['plu_code_basis'].apply(lambda x: str(x)+'_basis')
            parcel_zoning_names = zoning_parcels_pba50[['PARCEL_ID','zoning_id_pba50']].merge(zoning_names,
                                                                                              on = 'PARCEL_ID',
                                                                                              how = 'left')
            # use name_pba40 as the default for pab50 zoning name, unless it is null, then use basis zoning name
            parcel_zoning_names['zoning_name_pba50'] = zoning_names['name_pba40']
            name_null_index = parcel_zoning_names.name_pba40.isnull()
            parcel_zoning_names.loc[name_null_index,'zoning_name_pba50'] = parcel_zoning_names.loc[name_null_index,'plu_code_basis']

            # find the most frenquent zoning name of each zoning_id
            name_by_zone = parcel_zoning_names[['zoning_id_pba50','zoning_name_pba50']].groupby(['zoning_id_pba50']).agg(lambda x:x.value_counts().index[0]).reset_index()
            zoning_lookup_pba50 = zoning_lookup_pba50.merge(name_by_zone,
                                                            on = 'zoning_id_pba50',
                                                            how = 'left')
            # attach zoning name to the zoning lookup table
            zoning_lookup_pba50 = zoning_lookup_pba50[['zoning_id_pba50','juris_zmod','zoning_name_pba50','max_dua','max_far','max_height'] + \
                                                       dev_capacity_calculation_module.ALLOWED_BUILDING_TYPE_CODES]

            # change field names to be consistent with the previous version
            zoning_lookup_pba50.rename(columns = {'zoning_id_pba50'  :'id',
                                'juris_zmod'       :'juris',
                                'zoning_name_pba50':'name'}, inplace = True)
            logger.info('zoning_lookup has {} unique zoning_ids; zoning_lookup table header:'.format(len(zoning_lookup_pba50)))
            logger.info(zoning_lookup_pba50.head())
            
            # export
            logger.info('Export zoning_lookup table with the following attributes: {}'.format(zoning_lookup_pba50.dtypes))
            zoning_parcels_pba50.to_csv(os.path.join(ZONING_FOR_URBANSIM_DIR, today+'_zoning_parcels_pba50.csv'),index = False)            

            # lastly, append zone name to zoning_parcel
            zoning_parcels_pba50 = zoning_parcels_pba50.merge(zoning_lookup_pba50[['id','name']], 
                                                              left_on = 'zoning_id_pba50', 
                                                              right_on = 'id',
                                                              how = 'left')
            # rename fields to be consistent with the model
            zoning_parcels_pba50.rename(columns = {'juris_zmod'     : 'juris_id',
                                                   'zoning_id_pba50': 'zoning_id',
                                                   'jurisdiction_id': 'juris',
                                                   'nodev_zmod'     : 'nodev',
                                                   'name'           : 'zoning'}, inplace = True)
            logger.info('zoning_parcels_pba50 has {} records; table header:'.format(len(zoning_parcels_pba50)))
            logger.info(zoning_parcels_pba50.head())

            # export 
            logger.info('Export zoning_parcels table with the following attributes: {}'.format(zoning_parcels_pba50.dtypes))
            zoning_lookup_pba50.to_csv(os.path.join(ZONING_FOR_URBANSIM_DIR, today+'_zoning_lookup_pba50.csv'),index = False)