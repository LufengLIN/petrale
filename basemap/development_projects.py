﻿# coding: utf-8

import os, sys
import arcpy
import logging

#log file setup
if os.getenv("USERNAME")=="lzorn":
	LOG_FILE = "M:/Data/GIS layers/UrbanSim smelt/2020 02 24/devproj.log"
elif os.getenv("USERNAME")=="blu":
	LOG_FILE = "D:/Users/blu/Desktop/devproj.log"
else:
	LOG_FILE = "E:/baydata/devproj.log"
# create logger
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
# console handler
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p'))
logger.addHandler(ch)
# file handler
fh = logging.FileHandler(LOG_FILE, mode='w')
fh.setLevel(logging.DEBUG)
fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p'))
logger.addHandler(fh)


# set working environment
if os.getenv("USERNAME")=="lzorn":
	arcpy.env.workspace = "M:/Data/GIS layers/UrbanSim smelt/2020 02 24/smelt.gdb"
elif os.getenv("USERNAME")=="blu":
	arcpy.env.workspace = "D:/Users/blu/Box/baydata/smelt/2020 02 24/smelt.gdb"
else:
	arcpy.env.workspace = "E:/baydata/smelt.gdb"


# This script brings together many different datasets that each offer some info
# on development in the region from 2011 on. Overall approach is to:
# 1 spatially join parcels to each point file of new buildings
# 2 recompute all fields in each point file so that they exactly the same schema 
# 3 clean out old fields 
# 4 merge point files into one shapefile (pipeline) including only records w incl=1
# 5 merge point file of opportunity sites with pipeline to form development_projects
# 6 run diagnostics
# 7 remove duplicates by manually or automatically switching incl to 0 or another code
# 8 build a shapefile of buildings to demolish
# 9 export a csv file with buildings to build and demolish

###BL: I am organizing the process by data sources, so that it is easy to replicate the process

### First need to know what's in the geodatabase, for now I couldn't find a way to list all datasets, feature, and tables using a code.
### but afte I made the fold connection, it shows that smelt.gdb contains 2 tables, 3 feature classes. and 2 feature datasets - built and dp1620

# SET VARS
# input
p10_pba50 = "p10_pba50" # 2010 parcels, polygon feature class

### costar data
cs1620 = "cs1620" # costar data  2016-2020, point feature class
cs1115 = "cs1115" # costar data  2011-2015, point feature class

### redfin data
rfsfr1619 = "rf19_sfr1619" # redfin SFD data 2016-2019
rfmu1619 = "rf19_multiunit1619" # redin MFD data 2016-2019
rfsfr1115 = "rf19_sfr1115" # redfin SFD data 2011-2015
rfcondo1115 = "rf19_condounits1115" # redfin condo data 2011-2015
rfother1115 = "rf19_othertypes1115" # redfin other data 2011-2015

### BASIS pipleline data
basis_pipeline = "basis_pipeline_20200113" 

### manually maintained pipeline data
manual_dp = "manual_dp_20200131" 

# opportunity sites that keep their scen status from gis file
opp_sites = "oppsites_20200214" 

logging.info("workspace: {}".format(arcpy.env.workspace))
for dataset in arcpy.ListDatasets():
	logging.info("  dataset: {}".format(dataset))
	logging.info("    feature classes: {} ".format(arcpy.ListFeatureClasses(feature_dataset=dataset)))

logging.info("  feature classes: {} ".format(arcpy.ListFeatureClasses()))
logging.info("  tables: {} ".format(arcpy.ListTables()))

#get an empty list to add feature class to so that they can be merged in the end all together
dev_projects_temp_layers = []

#set up a process to make sure all incl = 1 records are in the results (also need to make sure that the feature class has column "incl")
def countRow (fc):
	if  arcpy.ListFields(fc, "incl"):
		arcpy.MakeTableView_management(fc,"fcInc1","incl = 1")
		count = arcpy.GetCount_management("fcInc1")
		result = int(count[0])
		return result
	else:
		print("incl is not a variable in this file")

# output
# pipeline shp
# development_projects shp
# development_projects csv
# demolish csv

### for costar data
### create a list of feature class
cs = [cs1115,cs1620]
for fc in cs:
	countOne = countRow(fc)
	logging.info("Feature Class {} has {} of records with incl = 1".format(fc, countOne))
	joinFN = 'ttt_' + arcpy.Describe(fc).name + '__p10_pba50'
	dev_projects_temp_layers.append(joinFN)

	# check if it exists already with rows-- if it does, skip
	try:
		count = arcpy.GetCount_management(joinFN)
		if int(count[0]) > 100:
			print("Found layer {} with {} rows -- skipping creation".format(joinFN, int(count[0])))
			continue
	except:
		# go ahead and create it
		pass

	### 1 SPATIAL JOINS
	logging.info("Creating layer {} by spatial joining costar ({}) and parcels ({})".format(joinFN, fc, p10_pba50))
	arcpy.SpatialJoin_analysis(fc, p10_pba50, joinFN)
	### 2 VARIABLE CLEANING 
	
	# rename any conflicting field names
	arcpy.AlterField_management(joinFN, "building_name", "cs_building_name")
	arcpy.AlterField_management(joinFN, "city", "cs_city")
	arcpy.AlterField_management(joinFN, "Zip", "cs_zip")
	arcpy.AlterField_management(joinFN, "rent_type", "cs_rent_type")
	arcpy.AlterField_management(joinFN, "year_built", "cs_year_built")
	arcpy.AlterField_management(joinFN, "last_sale_price", "cs_last_sale_price")
	arcpy.AlterField_management(joinFN, "last_sale_date", "cs_last_sale_date")
	arcpy.AlterField_management(joinFN, "Average_Weighted_Rent", "cs_average_weighted_rent")
	arcpy.AlterField_management(joinFN, "x", "p_x") # this is from the parcel centroid
	arcpy.AlterField_management(joinFN, "y", "p_y") # this is from the parcel centroid
	arcpy.AlterField_management(joinFN, "geom_id", "p_geom_id") # this is from the parcel 

	# add fields and calc values
	# full list development_projects_id,raw_id,building_name,site_name,action,scen0,scen1,
	# address,city,zip,county,x,y,geom_id,year_built,duration,building_type_id,building_type,building_sqft,non_residential_sqft,
	# residential_units,unit_ave_sqft,tenure,rent_type,stories,parking_spaces,Average Weighted Rent,rent_ave_sqft,rent_ave_unit,
	# last_sale_year,last_sale_price,source,edit_date,editor,version
	# AddField(in_table, field_name, field_type, {field_precision}, {field_scale}, {field_length}, {field_alias}, {field_is_nullable}, {field_is_required}, {field_domain})
	arcpy.AddField_management(joinFN, "development_projects_id", "SHORT")
	arcpy.AddField_management(joinFN, "raw_id", "LONG")
	arcpy.AddField_management(joinFN, "building_name", "TEXT","","",200)
	arcpy.AddField_management(joinFN, "site_name", "TEXT","","",50)
	arcpy.AddField_management(joinFN, "action", "TEXT","","",10)
	arcpy.AddField_management(joinFN, "scen0", "SHORT")
	arcpy.AddField_management(joinFN, "scen1", "SHORT") ### added this line, seems like we have two scenarios
	arcpy.AddField_management(joinFN, "address", "TEXT","","",200)
	arcpy.AddField_management(joinFN, "city", "TEXT","","",50)
	arcpy.AddField_management(joinFN, "zip",  "TEXT","","",50) ## this is changed from LONG to TEXT because cs1115 file has some text formatted zipcode with "-"
	arcpy.AddField_management(joinFN, "county", "TEXT","","",50)
	arcpy.AddField_management(joinFN, "x", "FLOAT")
	arcpy.AddField_management(joinFN, "y", "FLOAT")
	arcpy.AddField_management(joinFN, "geom_id", "TEXT","","",50)
	arcpy.AddField_management(joinFN, "year_built", "SHORT")
	arcpy.AddField_management(joinFN, "duration", "SHORT")
	arcpy.AddField_management(joinFN, "building_type_id", "LONG")
	arcpy.AddField_management(joinFN, "building_type", "TEXT","","",4)
	arcpy.AddField_management(joinFN, "building_sqft", "LONG")
	arcpy.AddField_management(joinFN, "non_residential_sqft", "LONG")
	arcpy.AddField_management(joinFN, "residential_units", "SHORT")
	arcpy.AddField_management(joinFN, "unit_ave_sqft", "FLOAT")
	arcpy.AddField_management(joinFN, "tenure", "TEXT","","",5)
	arcpy.AddField_management(joinFN, "rent_type", "TEXT","","",25)
	arcpy.AddField_management(joinFN, "stories", "SHORT")
	arcpy.AddField_management(joinFN, "parking_spaces", "SHORT")
	arcpy.AddField_management(joinFN, "average_weighted_rent", "TEXT")
	arcpy.AddField_management(joinFN, "rent_ave_sqft", "FLOAT")
	arcpy.AddField_management(joinFN, "rent_ave_unit", "SHORT")
	###using date for now, as I tried to use datetime.datetime.strptime('cs_sale_date','%m/%d/%Y %I:%M:%S %p').strftime('%Y')) it didn't work
	arcpy.AddField_management(joinFN, "last_sale_year", "DATE") 
	arcpy.AddField_management(joinFN, "last_sale_price", "DOUBLE")
	arcpy.AddField_management(joinFN, "source", "TEXT","","",10)
	arcpy.AddField_management(joinFN, "edit_date", "DATE")
	arcpy.AddField_management(joinFN, "editor", "TEXT","","",50)
	arcpy.AddField_management(joinFN, "version", "SHORT")
	if not arcpy.ListFields(joinFN, "incl"):
		arcpy.AddField_management(joinFN, "incl", "SHORT")

	arcpy.CalculateField_management(joinFN, "raw_id", '!PropertyID!')
	arcpy.CalculateField_management(joinFN, "building_name", '!cs_building_name!')
	arcpy.CalculateField_management(joinFN, "site_name", '!Building_Park!')
	arcpy.CalculateField_management(joinFN, "action", "'build'")# need to quote marks here
	arcpy.CalculateField_management(joinFN, "scen0", 1) # these are committed so 1 for all scens 
	arcpy.CalculateField_management(joinFN, "address", '!Building_Address!')
	arcpy.CalculateField_management(joinFN, "city", '!cs_city!')
	arcpy.CalculateField_management(joinFN, "zip", '!cs_zip!')
	arcpy.CalculateField_management(joinFN, "county", '!County_Name!')
	arcpy.CalculateField_management(joinFN, "x", '!p_x!') 
	arcpy.CalculateField_management(joinFN, "y", '!p_y!') 
	arcpy.CalculateField_management(joinFN, "geom_id", '!p_geom_id!')
	arcpy.CalculateField_management(joinFN, "year_built", '!cs_year_built!')
	#arcpy.CalculateField_management(joinFN, "duration", )
	#arcpy.CalculateField_management(joinFN, "building_type_id", )
	arcpy.CalculateField_management(joinFN, "building_type", '!det_bldg_type!')
	arcpy.CalculateField_management(joinFN, "building_sqft", '!Rentable_Building_Area!') # how often null for res
	arcpy.CalculateField_management(joinFN, "non_residential_sqft", '!Rentable_Building_Area!') # need to zero out for res
	arcpy.CalculateField_management(joinFN, "residential_units", '!Number_Of_Units!')
	arcpy.CalculateField_management(joinFN, "unit_ave_sqft", '!Avg_Unit_SF!')
	arcpy.CalculateField_management(joinFN, "tenure", "'Rent'")
	arcpy.CalculateField_management(joinFN, "rent_type", '!cs_rent_type!') # need to clean
	arcpy.CalculateField_management(joinFN, "stories", '!Number_Of_Stories!')
	#there is a worng parking space value is one of the tables, so adding this to work around
	with arcpy.da.UpdateCursor(joinFN, ["Number_Of_Parking_Spaces","parking_spaces"]) as cursor:
    		for row in cursor:
    			if len(str((row[0]))) <= 5: ##short integer has value less than 32700
    				row[1] = row[0]
    				cursor.updateRow(row)
	#arcpy.CalculateField_management(joinFN, "parking_spaces", '!Number_Of_Parking_Spaces!')
	arcpy.CalculateField_management(joinFN, "average_weighted_rent", '!cs_average_weighted_rent!')
	#arcpy.CalculateField_management(joinFN, "rent_ave_sqft", )
	#arcpy.CalculateField_management(joinFN, "rent_ave_unit", )
	arcpy.CalculateField_management(joinFN, "last_sale_year", '!cs_last_sale_date!') #need to make into year
	arcpy.CalculateField_management(joinFN, "last_sale_price", '!cs_last_sale_price!')
	arcpy.CalculateField_management(joinFN, "source", "'cs'")
	arcpy.CalculateField_management(joinFN, "edit_date", "'Jan 2020'")
	arcpy.CalculateField_management(joinFN, "editor", "'MKR'")
	#arcpy.CalculateField_management(joinFN, "version", )

	#remove row where incl != 1
	with arcpy.da.UpdateCursor(joinFN, "incl") as cursor:
		for row in cursor:
			if row[0] != 1:
				cursor.deleteRow()

	#check all incl = 1 records are included 
	countTwo = countRow(joinFN)
	if countTwo == countOne:
		logging.info('All records with incl = 1 in feature class {} is included in the temp file'.format(fc))
	else:
		logging.debug('Something is wrong in the code, please check')


	### 3 DELETE OTHER FIELDS AND TEMP FILES
	FCfields = [f.name for f in arcpy.ListFields(joinFN)]
	#add "rent_ave_sqft", "rent_ave_unit","version", "duration", "building_type_id" if needed
	DontDeleteFields = ["OBJECTID","Shape","PARCEL_ID", "ZONE_ID","development_projects_id", "raw_id", "building_name", "site_name",  "action", "scen0",  "address",  "city",  "zip",  "county", "x", "y",
	"geom_id", "year_built","building_type", "building_sqft", "non_residential_sqft", "residential_units", "unit_ave_sqft", 
	"tenure", "rent_type", "stories", "parking_spaces", "average_weighted_rent", "last_sale_year", "last_sale_price", "source", "edit_date", "editor", "Shape_Length", "Shape_Area"]
	fields2Delete = list(set(FCfields) - set(DontDeleteFields))
	arcpy.DeleteField_management(joinFN, fields2Delete)
	
### for redfin data
### create a list of feature class
rf = [rfsfr1619, rfmu1619, rfsfr1115, rfcondo1115, rfother1115]
for fc in rf:
	countOne = countRow(fc)
	logging.info("Feature Class {} has {} of records with incl = 1".format(fc, countOne))
	joinFN = 'ttt_' + arcpy.Describe(fc).name + '__p10_pba50'
	dev_projects_temp_layers.append(joinFN)

	# check if it exists already with rows-- if it does, skip
	try:
		count = arcpy.GetCount_management(joinFN)
		if int(count[0]) > 100:
			print("Found layer {} with {} rows -- skipping creation".format(joinFN, int(count[0])))
			continue
	except:
		# go ahead and create it
		pass

	### 1 SPATIAL JOINS
	logging.info("Creating layer {} by spatial joining redfin ({}) and parcels ({})".format(joinFN, fc, p10_pba50))
	arcpy.SpatialJoin_analysis(fc, p10_pba50, joinFN)
	### 2 VARIABLE CLEANING 
	
	# rename any conflicting field names
	arcpy.AlterField_management(joinFN, "CITY", "rf_city")
	arcpy.AlterField_management(joinFN, "COUNTY", "rf_county")
	arcpy.AlterField_management(joinFN, "YEAR_BUILT", "rf_year_built")
	arcpy.AlterField_management(joinFN, "ADDRESS", "rf_address")
	arcpy.AlterField_management(joinFN, "x", "p_x") # this is from the parcel centroid
	arcpy.AlterField_management(joinFN, "y", "p_y") # this is from the parcel centroid
	arcpy.AlterField_management(joinFN, "geom_id", "p_geom_id") # this is from the parcel 

	# add fields and calc values
	# full list development_projects_id,raw_id,building_name,site_name,action,scen0,scen1,
	# address,city,zip,county,x,y,geom_id,year_built,duration,building_type_id,building_type,building_sqft,non_residential_sqft,
	# residential_units,unit_ave_sqft,tenure,rent_type,stories,parking_spaces,Average Weighted Rent,rent_ave_sqft,rent_ave_unit,
	# last_sale_year,last_sale_price,source,edit_date,editor,version
	# AddField(in_table, field_name, field_type, {field_precision}, {field_scale}, {field_length}, {field_alias}, {field_is_nullable}, {field_is_required}, {field_domain})
	arcpy.AddField_management(joinFN, "development_projects_id", "SHORT")
	arcpy.AddField_management(joinFN, "raw_id", "LONG")
	arcpy.AddField_management(joinFN, "building_name", "TEXT","","",200)
	arcpy.AddField_management(joinFN, "site_name", "TEXT","","",50)
	arcpy.AddField_management(joinFN, "action", "TEXT","","",10)
	arcpy.AddField_management(joinFN, "scen0", "SHORT")
	arcpy.AddField_management(joinFN, "scen1", "SHORT") ### added this line, seems like we have two scenarios
	arcpy.AddField_management(joinFN, "address", "TEXT","","",200)
	arcpy.AddField_management(joinFN, "city", "TEXT","","",50)
	arcpy.AddField_management(joinFN, "zip", "TEXT","","",50)
	arcpy.AddField_management(joinFN, "county", "TEXT","","",50)
	arcpy.AddField_management(joinFN, "x", "FLOAT")
	arcpy.AddField_management(joinFN, "y", "FLOAT")
	arcpy.AddField_management(joinFN, "geom_id", "TEXT","","",50)
	arcpy.AddField_management(joinFN, "year_built", "SHORT")
	arcpy.AddField_management(joinFN, "duration", "SHORT")
	arcpy.AddField_management(joinFN, "building_type_id", "LONG")
	arcpy.AddField_management(joinFN, "building_type", "TEXT","","",4)
	arcpy.AddField_management(joinFN, "building_sqft", "LONG")
	arcpy.AddField_management(joinFN, "non_residential_sqft", "LONG")
	arcpy.AddField_management(joinFN, "residential_units", "SHORT")
	arcpy.AddField_management(joinFN, "unit_ave_sqft", "FLOAT")
	arcpy.AddField_management(joinFN, "tenure", "TEXT","","",5)
	arcpy.AddField_management(joinFN, "rent_type", "TEXT","","",25)
	arcpy.AddField_management(joinFN, "stories", "SHORT")
	arcpy.AddField_management(joinFN, "parking_spaces", "SHORT")
	arcpy.AddField_management(joinFN, "average_weighted_rent", "TEXT")
	arcpy.AddField_management(joinFN, "rent_ave_sqft", "FLOAT")
	arcpy.AddField_management(joinFN, "rent_ave_unit", "SHORT")
	arcpy.AddField_management(joinFN, "last_sale_year", "DATE")
	arcpy.AddField_management(joinFN, "last_sale_price", "DOUBLE")
	arcpy.AddField_management(joinFN, "source", "TEXT","","",10)
	arcpy.AddField_management(joinFN, "edit_date", "DATE")
	arcpy.AddField_management(joinFN, "editor", "TEXT","","",50)
	arcpy.AddField_management(joinFN, "version", "SHORT")
	if not arcpy.ListFields(joinFN, "incl"):
		arcpy.AddField_management(joinFN, "incl", "SHORT")

	arcpy.CalculateField_management(joinFN, "raw_id", '!redfinid!')
	arcpy.CalculateField_management(joinFN, "action", "'build'")
	arcpy.CalculateField_management(joinFN, "scen0", 1) # these are committed so 1 for all scens 
	arcpy.CalculateField_management(joinFN, "address", '!rf_address!')
	arcpy.CalculateField_management(joinFN, "city", '!rf_city!')
	arcpy.CalculateField_management(joinFN, "county", '!rf_county!')
	arcpy.CalculateField_management(joinFN, "x", '!p_x!') 
	arcpy.CalculateField_management(joinFN, "y", '!p_y!') 
	arcpy.CalculateField_management(joinFN, "geom_id", '!p_geom_id!')
	arcpy.CalculateField_management(joinFN, "year_built", '!rf_year_built!')
	if 'sfr' in arcpy.Describe(fc).name:
		arcpy.CalculateField_management(joinFN, "building_type", "'HS'")
	else:
		arcpy.CalculateField_management(joinFN, "building_type", "'HM'")
	arcpy.CalculateField_management(joinFN, "building_sqft", '!SQFT!') # how often null for res
	arcpy.CalculateField_management(joinFN, "non_residential_sqft", 0) # seems redfin data are all residential
	arcpy.CalculateField_management(joinFN, "residential_units", '!UNITS!')
	###ideally, everything could be done using cursor since it is much faster to run
	with arcpy.da.UpdateCursor(joinFN, ["SQFT", "UNITS", "unit_ave_sqft"]) as cursor:
    		for row in cursor:
        		row[2] = row[0] / row[1] 
        		cursor.updateRow(row)
	arcpy.CalculateField_management(joinFN, "tenure", "'Sale'") #is redfin data rental?
	arcpy.CalculateField_management(joinFN, "last_sale_year", '!SOLD_DATE!') #need to make into year
	arcpy.CalculateField_management(joinFN, "last_sale_price", '!PRICE!')
	arcpy.CalculateField_management(joinFN, "source", "'rf'")
	arcpy.CalculateField_management(joinFN, "edit_date", "'Jan 2020'")
	arcpy.CalculateField_management(joinFN, "editor", "'MKR'")
	
	#remove row where incl != 1
	with arcpy.da.UpdateCursor(joinFN, "incl") as cursor:
		for row in cursor:
			if row[0] != 1:
				cursor.deleteRow()

	countTwo = countRow(joinFN)
	if countTwo == countOne:
		logging.info('All records with incl = 1 in feature class {} is included in the temp file'.format(fc))
	else:
		logging.debug('Something is wrong in the code, please check')

	### 3 DELETE OTHER FIELDS AND TEMP FILES
	FCfields = [f.name for f in arcpy.ListFields(joinFN)]
	#add "rent_ave_sqft", "rent_ave_unit","version", "duration", "building_type_id" if needed
	DontDeleteFields = ["OBJECTID","Shape","PARCEL_ID", "ZONE_ID","development_projects_id", "raw_id", "building_name", "site_name",  "action", "scen0",  "address",  "city",  "zip",  "county", "x", "y",
	"geom_id", "year_built","building_type", "building_sqft", "non_residential_sqft", "residential_units", "unit_ave_sqft", 
	"tenure", "rent_type", "stories", "parking_spaces", "average_weighted_rent", "last_sale_year", "last_sale_price", "source", "edit_date", "editor", "Shape_Length", "Shape_Area"]
	fields2Delete = list(set(FCfields) - set(DontDeleteFields))
	arcpy.DeleteField_management(joinFN, fields2Delete)


### for BASIS pipeline data
countOne = countRow(basis_pipeline)
logging.info("Feature Class {} has {} of records with incl = 1".format(basis_pipeline, countOne))
joinFN = 'ttt_basispp_p10_pba50'
dev_projects_temp_layers.append(joinFN)

# check if it exists already with rows-- if it does, skip
try:
	count = arcpy.GetCount_management(joinFN)
	if int(count[0]) > 100:
		print("Found layer {} with {} rows -- skipping creation".format(joinFN, int(count[0])))
except:
	# go ahead and create it

	### 1 SPATIAL JOINS
	logging.info("Creating layer {} by spatial joining BASIS pipeline data ({}) and parcels ({})".format(joinFN, basis_pipeline, p10_pba50))
	arcpy.SpatialJoin_analysis(basis_pipeline, p10_pba50, joinFN)
	### 2 VARIABLE CLEANING 
	
	# rename any conflicting field names
	arcpy.AlterField_management(joinFN, "county", "b_county")
	arcpy.AlterField_management(joinFN, "raw_id", "b_id")
	arcpy.AlterField_management(joinFN, "year_built", "b_year_built")
	arcpy.AlterField_management(joinFN, "zip", "b_zip")
	arcpy.AlterField_management(joinFN, "stories", "b_stories")
	arcpy.AlterField_management(joinFN, "x", "p_x") # this is from the parcel centroid
	arcpy.AlterField_management(joinFN, "y", "p_y") # this is from the parcel centroid
	arcpy.AlterField_management(joinFN, "geom_id", "p_geom_id") # this is from the parcel 
	
	# add fields and calc values
	# full list development_projects_id,raw_id,building_name,site_name,action,scen0,scen1,
	# address,city,zip,county,x,y,geom_id,year_built,duration,building_type_id,building_type,building_sqft,non_residential_sqft,
	# residential_units,unit_ave_sqft,tenure,rent_type,stories,parking_spaces,Average Weighted Rent,rent_ave_sqft,rent_ave_unit,
	# last_sale_year,last_sale_price,source,edit_date,editor,version
	# AddField(in_table, field_name, field_type, {field_precision}, {field_scale}, {field_length}, {field_alias}, {field_is_nullable}, {field_is_required}, {field_domain})
	arcpy.AddField_management(joinFN, "development_projects_id", "SHORT")
	arcpy.AddField_management(joinFN, "raw_id", "LONG")
	arcpy.AddField_management(joinFN, "building_name", "TEXT","","",200)
	arcpy.AddField_management(joinFN, "site_name", "TEXT","","",50)
	arcpy.AddField_management(joinFN, "action", "TEXT","","",10)
	arcpy.AddField_management(joinFN, "scen0", "SHORT")
	arcpy.AddField_management(joinFN, "address", "TEXT","","",200)
	arcpy.AddField_management(joinFN, "city", "TEXT","","",50)
	arcpy.AddField_management(joinFN, "zip", "TEXT","","",50)
	arcpy.AddField_management(joinFN, "county", "TEXT","","",50)
	arcpy.AddField_management(joinFN, "x", "FLOAT")
	arcpy.AddField_management(joinFN, "y", "FLOAT")
	arcpy.AddField_management(joinFN, "geom_id", "TEXT","","",50)
	arcpy.AddField_management(joinFN, "year_built", "SHORT")
	arcpy.AddField_management(joinFN, "duration", "SHORT")
	arcpy.AddField_management(joinFN, "building_type_id", "LONG")
	arcpy.AddField_management(joinFN, "building_type", "TEXT","","",4)
	arcpy.AddField_management(joinFN, "building_sqft", "LONG")
	arcpy.AddField_management(joinFN, "non_residential_sqft", "LONG")
	arcpy.AddField_management(joinFN, "residential_units", "SHORT")
	arcpy.AddField_management(joinFN, "unit_ave_sqft", "FLOAT")
	arcpy.AddField_management(joinFN, "tenure", "TEXT","","",5)
	arcpy.AddField_management(joinFN, "rent_type", "TEXT","","",25)
	arcpy.AddField_management(joinFN, "stories", "SHORT")
	arcpy.AddField_management(joinFN, "parking_spaces", "SHORT")
	arcpy.AddField_management(joinFN, "average_weighted_rent", "TEXT")
	arcpy.AddField_management(joinFN, "rent_ave_sqft", "FLOAT")
	arcpy.AddField_management(joinFN, "rent_ave_unit", "SHORT")
	###using date for now, as I tried to use datetime.datetime.strptime('cs_sale_date','%m/%d/%Y %I:%M:%S %p').strftime('%Y')) it didn't work
	arcpy.AddField_management(joinFN, "last_sale_year", "DATE") 
	arcpy.AddField_management(joinFN, "last_sale_price", "DOUBLE")
	arcpy.AddField_management(joinFN, "source", "TEXT","","",10)
	arcpy.AddField_management(joinFN, "edit_date", "DATE")
	if not arcpy.ListFields(joinFN, "incl"):
		arcpy.AddField_management(joinFN, "incl", "SHORT")
	
	arcpy.CalculateField_management(joinFN, "building_name", '!project_na!')
	arcpy.CalculateField_management(joinFN, "action", "'build'")# need to quote marks here
	arcpy.CalculateField_management(joinFN, "scen0", 1) # these are committed so 1 for all scens 
	arcpy.CalculateField_management(joinFN, "address", '!street_add!')
	arcpy.CalculateField_management(joinFN, "city", '!mailing_ci!')
	##arcpy.CalculateField_management(joinFN, "zip", '!b_zip!') ##not sure how to convert text to long data type
	arcpy.CalculateField_management(joinFN, "county", '!b_county!')
	arcpy.CalculateField_management(joinFN, "x", '!p_x!') 
	arcpy.CalculateField_management(joinFN, "y", '!p_y!') 
	arcpy.CalculateField_management(joinFN, "geom_id", '!p_geom_id!')
	arcpy.CalculateField_management(joinFN, "year_built", '!b_year_built!')
	arcpy.CalculateField_management(joinFN, "building_type", '!building_type_det!')
	arcpy.CalculateField_management(joinFN, "building_sqft", '!building_s!') # how often null for res
	arcpy.CalculateField_management(joinFN, "non_residential_sqft", '!non_reside!') # need to zero out for res
	arcpy.CalculateField_management(joinFN, "residential_units", '!residentia!')
	arcpy.CalculateField_management(joinFN, "tenure", "'Rent'") ##what is tenure
	arcpy.CalculateField_management(joinFN, "stories", '!b_stories!')
	arcpy.CalculateField_management(joinFN, "source", "'basis'")
	arcpy.CalculateField_management(joinFN, "edit_date", "'Jan 2020'")
	#arcpy.CalculateField_management(joinFN, "version", )

	#remove row where incl != 1
	with arcpy.da.UpdateCursor(joinFN, "incl") as cursor:
		for row in cursor:
			if row[0] != 1:
				cursor.deleteRow()

	#check all incl = 1 records are included 
	countTwo = countRow(joinFN)
	if countTwo == countOne:
		logging.info('All records with incl = 1 in feature class {} is included in the temp file'.format(basis_pipeline))
	else:
		logging.debug('Something is wrong in the code, please check')

	### 3 DELETE OTHER FIELDS
	FCfields = [f.name for f in arcpy.ListFields(joinFN)]
	#add "rent_ave_sqft", "rent_ave_unit","version", "duration", "building_type_id" if needed
	DontDeleteFields = ["OBJECTID","Shape","PARCEL_ID", "ZONE_ID","development_projects_id", "raw_id", "building_name", "site_name",  "action", "scen0",  "address",  "city",  "zip",  "county", "x", "y",
	"geom_id", "year_built","building_type", "building_sqft", "non_residential_sqft", "residential_units", "unit_ave_sqft", 
	"tenure", "rent_type", "stories", "parking_spaces", "average_weighted_rent", "last_sale_year", "last_sale_price", "source", "edit_date", "editor", "Shape_Length", "Shape_Area"]
	fields2Delete = list(set(FCfields) - set(DontDeleteFields))
	arcpy.DeleteField_management(joinFN, fields2Delete)

#Manual
countOne = countRow(manual_dp)
logging.info("Feature Class {} has {} of records with incl = 1".format(manual_dp, countOne))
joinFN = 'ttt_manual_p10_pba50'
dev_projects_temp_layers.append(joinFN)

try:
	count = arcpy.GetCount_management(joinFN)
	if int(count[0]) > 100:
		print("Found layer {} with {} rows -- skipping creation".format(joinFN, int(count[0])))
except:
	# go ahead and create it
	### 1 SPATIAL JOINS
	logging.info("Creating layer {} by spatial joining manual pipeline data ({}) and parcels ({})".format(joinFN, manual_dp, p10_pba50))
	arcpy.SpatialJoin_analysis(manual_dp, p10_pba50, joinFN)
	# rename any conflicting field names
	
	arcpy.AlterField_management(joinFN, "building_name", "m_building_name")
	arcpy.AlterField_management(joinFN, "year_built", "m_year_built")
	arcpy.AlterField_management(joinFN, "last_sale_price", "m_last_sale_price")
	arcpy.AlterField_management(joinFN, "last_sale_year", "m_sale_date")
	arcpy.AlterField_management(joinFN, "stories", "m_stories")
	arcpy.AlterField_management(joinFN, "residential_units", "m_residential_units")
	arcpy.AlterField_management(joinFN, "unit_ave_sqft", "m_unit_ave_sqft")
	arcpy.AlterField_management(joinFN, "zip", "m_zips")
	arcpy.AlterField_management(joinFN, "Average_Weighted_Rent", "m_average_weighted_rent")
	arcpy.AlterField_management(joinFN, "x", "p_x") # this is from the parcel centroid
	arcpy.AlterField_management(joinFN, "y", "p_y") # this is from the parcel centroid
	arcpy.AlterField_management(joinFN, "geom_id", "p_geom_id") # this is from the parcel 
	
	# add fields and calc values
	# full list development_projects_id,raw_id,building_name,site_name,action,scen0,scen1,
	# address,city,zip,county,x,y,geom_id,year_built,duration,building_type_id,building_type,building_sqft,non_residential_sqft,
	# residential_units,unit_ave_sqft,tenure,rent_type,stories,parking_spaces,Average Weighted Rent,rent_ave_sqft,rent_ave_unit,
	# last_sale_year,last_sale_price,source,edit_date,editor,version
	# AddField(in_table, field_name, field_type, {field_precision}, {field_scale}, {field_length}, {field_alias}, {field_is_nullable}, {field_is_required}, {field_domain})
	arcpy.AddField_management(joinFN, "development_projects_id", "SHORT")
	arcpy.AddField_management(joinFN, "raw_id", "LONG")
	arcpy.AddField_management(joinFN, "building_name", "TEXT","","",200)
	arcpy.AddField_management(joinFN, "scen0", "SHORT")
	arcpy.AddField_management(joinFN, "scen1", "SHORT") ### added this line, seems like we have two scenarios
	arcpy.AddField_management(joinFN, "zip", "TEXT","","",50)
	arcpy.AddField_management(joinFN, "x", "FLOAT")
	arcpy.AddField_management(joinFN, "y", "FLOAT")
	arcpy.AddField_management(joinFN, "geom_id", "TEXT","","",50)
	arcpy.AddField_management(joinFN, "year_built", "SHORT")
	arcpy.AddField_management(joinFN, "residential_units", "SHORT")
	arcpy.AddField_management(joinFN, "unit_ave_sqft", "FLOAT")
	arcpy.AddField_management(joinFN, "stories", "SHORT")
	arcpy.AddField_management(joinFN, "average_weighted_rent", "TEXT")
	arcpy.AddField_management(joinFN, "rent_ave_sqft", "FLOAT")
	arcpy.AddField_management(joinFN, "rent_ave_unit", "SHORT")
	###using date for now, as I tried to use datetime.datetime.strptime('cs_sale_date','%m/%d/%Y %I:%M:%S %p').strftime('%Y')) it didn't work
	arcpy.AddField_management(joinFN, "last_sale_year", "DATE") 
	arcpy.AddField_management(joinFN, "last_sale_price", "DOUBLE")
	arcpy.AddField_management(joinFN, "source", "TEXT","","",10)
	arcpy.AddField_management(joinFN, "edit_date", "DATE")
	arcpy.AddField_management(joinFN, "editor", "TEXT","","",50)
	arcpy.AddField_management(joinFN, "version", "SHORT")
	if not arcpy.ListFields(joinFN, "incl"):
		arcpy.AddField_management(joinFN, "incl", "SHORT")
	
	arcpy.CalculateField_management(joinFN, "raw_id", '!manual_dp_id!')
	arcpy.CalculateField_management(joinFN, "building_name", '!m_building_name!')
	arcpy.CalculateField_management(joinFN, "scen0", 1) # these are committed so 1 for all scens 
	#not sure how to change zip field type
	#arcpy.CalculateField_management(joinFN, "zip", '!m_zip!')
	arcpy.CalculateField_management(joinFN, "x", '!p_x!') 
	arcpy.CalculateField_management(joinFN, "y", '!p_y!') 
	arcpy.CalculateField_management(joinFN, "geom_id", '!p_geom_id!')
	arcpy.CalculateField_management(joinFN, "year_built", '!m_year_built!')
	#arcpy.CalculateField_management(joinFN, "duration", )
	arcpy.CalculateField_management(joinFN, "residential_units", '!m_residential_units!')
	arcpy.CalculateField_management(joinFN, "unit_ave_sqft", '!m_unit_ave_sqft!')
	arcpy.CalculateField_management(joinFN, "stories", '!m_stories!')
	arcpy.CalculateField_management(joinFN, "average_weighted_rent", '!m_average_weighted_rent!')
	#arcpy.CalculateField_management(joinFN, "rent_ave_sqft", )
	#arcpy.CalculateField_management(joinFN, "rent_ave_unit", )
	arcpy.CalculateField_management(joinFN, "last_sale_year", '!m_sale_date!') #need to make into year
	arcpy.CalculateField_management(joinFN, "last_sale_price", '!m_last_sale_price!')
	arcpy.CalculateField_management(joinFN, "source", "'manual'")
	arcpy.CalculateField_management(joinFN, "edit_date", "'Jan 2020'")
	arcpy.CalculateField_management(joinFN, "editor", "'MKR'")
	#arcpy.CalculateField_management(joinFN, "version", )
	
	#remove row where incl != 1
	with arcpy.da.UpdateCursor(joinFN, "incl") as cursor:
		for row in cursor:
			if row[0] != 1:
				cursor.deleteRow()	

	#check to make sure that the number of remaining records in the temp file (which should still have var incl) is the same as the raw file
	countTwo = countRow(joinFN)
	if countTwo == countOne:
		logging.info('All records with incl = 1 in feature class {} is included in the temp file'.format(manual_dp))
	else:
		logging.debug('Something is wrong in the code, please check')
	
	### 3 DELETE OTHER FIELDS
	FCfields = [f.name for f in arcpy.ListFields(joinFN)]
	#add "rent_ave_sqft", "rent_ave_unit","version", "duration", "building_type_id" if needed
	DontDeleteFields = ["OBJECTID","Shape","PARCEL_ID", "ZONE_ID","development_projects_id", "raw_id", "building_name", "site_name",  "action", "scen0",  "address",  "city",  "zip",  "county", "x", "y",
	"geom_id", "year_built","building_type", "building_sqft", "non_residential_sqft", "residential_units", "unit_ave_sqft", 
	"tenure", "rent_type", "stories", "parking_spaces", "average_weighted_rent", "last_sale_year", "last_sale_price", "source", "edit_date", "editor", "Shape_Length", "Shape_Area"]
	fields2Delete = list(set(FCfields) - set(DontDeleteFields))
	arcpy.DeleteField_management(joinFN, fields2Delete)

### 4 MERGE ALL INCL=1 POINTS INTO A SINGLE SHP FILE CALLED PIPELINE
### For now, every file in that temp layer list should only contain records where incl = 1 
pipeline_fc = "pipeline"
logging.info("Merging feature classes {} into {}".format(dev_projects_temp_layers, pipeline_fc))
# if this exists already, delete it
if arcpy.Exists(pipeline_fc): arcpy.Delete_management(pipeline_fc)
#merge
arcpy.Merge_management(dev_projects_temp_layers, pipeline_fc)
count = arcpy.GetCount_management(pipeline_fc)
logging.info("  Results in {} rows in {}".format(int(count[0]), pipeline_fc))

#export csv to folder -- remember to change fold path when run on other machines
arcpy.TableToTable_conversion(pipeline_fc, 'D:/Users/blu/Desktop', "pipeline.csv")

### 5 MERGE OPPSITES SHP WITH PIPELINE TO GET DEVELOPMENT PROJECTS 
#opportunity sites
joinFN = 'ttt_opp_p10_pba50'
dev_projects_temp_layers.append(joinFN)

try:
	count = arcpy.GetCount_management(joinFN)
	if int(count[0]) > 100:
		print("Found layer {} with {} rows -- skipping creation".format(joinFN, int(count[0])))
except:
	# go ahead and create it
	logging.info("Creating layer {} by spatial joining opps sites data ({}) and parcels ({})".format(joinFN, opp_sites, p10_pba50))
	arcpy.SpatialJoin_analysis(opp_sites, p10_pba50, joinFN)
	
	arcpy.AlterField_management(joinFN, "year_built", "o_year_built")
	arcpy.AlterField_management(joinFN, "last_sale_price", "o_last_sale_price")
	arcpy.AlterField_management(joinFN, "last_sale_year", "o_sale_date")
	arcpy.AlterField_management(joinFN, "stories", "o_stories")

	arcpy.AlterField_management(joinFN, "scen0", "o_scen0")
	arcpy.AlterField_management(joinFN, "duration", "o_duration")
	arcpy.AlterField_management(joinFN, "parking_spaces", "o_parking_spaces")
	arcpy.AlterField_management(joinFN, "residential_units", "o_residential_units")
	arcpy.AlterField_management(joinFN, "unit_ave_sqft", "o_unit_ave_sqft")
	arcpy.AlterField_management(joinFN, "rent_ave_sqft", "o_rent_ave_sqft")
	arcpy.AlterField_management(joinFN, "rent_ave_unit", "o_rent_ave_unit")
	arcpy.AlterField_management(joinFN, "zip", "o_zips")
	arcpy.AlterField_management(joinFN, "Average_Weighted_Rent", "average_weighted_rent")
	arcpy.AlterField_management(joinFN, "x", "p_x") # this is from the parcel centroid
	arcpy.AlterField_management(joinFN, "y", "p_y") # this is from the parcel centroid
	arcpy.AlterField_management(joinFN, "geom_id", "p_geom_id") 
	
	arcpy.AddField_management(joinFN, "raw_id", "LONG")
	arcpy.AddField_management(joinFN, "scen0", "SHORT")
	#arcpy.AddField_management(joinFN, "scen1", "SHORT") ### added this line, seems like we have two scenarios
	arcpy.AddField_management(joinFN, "zip", "TEXT","","",50)
	arcpy.AddField_management(joinFN, "x", "FLOAT")
	arcpy.AddField_management(joinFN, "y", "FLOAT")
	arcpy.AddField_management(joinFN, "geom_id", "TEXT","","",50)
	arcpy.AddField_management(joinFN, "year_built", "SHORT")
	arcpy.AddField_management(joinFN, "duration", "SHORT")
	arcpy.AddField_management(joinFN, "residential_units", "SHORT")
	arcpy.AddField_management(joinFN, "unit_ave_sqft", "FLOAT")
	arcpy.AddField_management(joinFN, "stories", "SHORT")
	arcpy.AddField_management(joinFN, "parking_spaces", "SHORT")
	arcpy.AddField_management(joinFN, "rent_ave_sqft", "FLOAT")
	arcpy.AddField_management(joinFN, "rent_ave_unit", "SHORT")
	###using date for now, as I tried to use datetime.datetime.strptime('cs_sale_date','%m/%d/%Y %I:%M:%S %p').strftime('%Y')) it didn't work
	arcpy.AddField_management(joinFN, "last_sale_year", "DATE") 
	arcpy.AddField_management(joinFN, "last_sale_price", "DOUBLE")
	arcpy.AddField_management(joinFN, "edit_date", "DATE")
	arcpy.AddField_management(joinFN, "editor", "TEXT","","",50)
	arcpy.AddField_management(joinFN, "version", "SHORT")
	
	# NOTE THAT OPPSITES HAS SCEN SET IN GIS FILE
	arcpy.CalculateField_management(joinFN, "scen0", 0) # committed projects are 1, opp sites are 0 for now.
	#arcpy.CalculateField_management(joinFN, "zip", '!o_zip!')
	arcpy.CalculateField_management(joinFN, "x", '!p_x!') 
	arcpy.CalculateField_management(joinFN, "y", '!p_y!') 
	arcpy.CalculateField_management(joinFN, "geom_id", '!p_geom_id!')
	arcpy.CalculateField_management(joinFN, "year_built", '!o_year_built!')
	arcpy.CalculateField_management(joinFN, "residential_units", '!o_residential_units!')
	arcpy.CalculateField_management(joinFN, "unit_ave_sqft", '!o_unit_ave_sqft!')
	arcpy.CalculateField_management(joinFN, "stories", '!o_stories!')
	arcpy.CalculateField_management(joinFN, "rent_ave_sqft", "!o_rent_ave_sqft!" )
	arcpy.CalculateField_management(joinFN, "rent_ave_unit", "!o_rent_ave_unit!")
	arcpy.CalculateField_management(joinFN, "last_sale_year", '!o_sale_date!') #need to make into year
	arcpy.CalculateField_management(joinFN, "last_sale_price", '!o_last_sale_price!')
	arcpy.CalculateField_management(joinFN, "source", "'opp'")
	arcpy.CalculateField_management(joinFN, "edit_date", "'Jan 2020'")
	arcpy.CalculateField_management(joinFN, "editor", "'MKR'")
	
	FCfields = [f.name for f in arcpy.ListFields(joinFN)]
	#add "rent_ave_sqft", "rent_ave_unit","version", "duration", "building_type_id" if needed
	DontDeleteFields = ["OBJECTID","Shape","PARCEL_ID", "ZONE_ID","development_projects_id", "raw_id", "building_name", "site_name",  "action", "scen0",  "address",  "city",  "zip",  "county", "x", "y",
	"geom_id", "year_built","building_type", "building_sqft", "non_residential_sqft", "residential_units", "unit_ave_sqft", 
	"tenure", "rent_type", "stories", "parking_spaces", "average_weighted_rent", "last_sale_year", "last_sale_price", "source", "edit_date", "editor", "Shape_Length", "Shape_Area"]
	fields2Delete = list(set(FCfields) - set(DontDeleteFields))
	arcpy.DeleteField_management(joinFN, fields2Delete)

#all non opp sites should be in the list dev_projects_temp_layers already
devproj_fc = "development_project"
logging.info("Merging feature classes {} into {}".format(dev_projects_temp_layers, devproj_fc))
# if this exists already, delete it
if arcpy.Exists(devproj_fc): arcpy.Delete_management(devproj_fc)

arcpy.Merge_management(dev_projects_temp_layers, devproj_fc)
count = arcpy.GetCount_management(devproj_fc)
logging.info("  Results in {} rows in {}".format(int(count[0]), devproj_fc))

#assign unique incremental development_id
i = 1
with arcpy.da.UpdateCursor(devproj_fc, "development_projects_id") as cursor:
		for row in cursor:
			if i <= int(count[0]) :
				row[0] = i
				i  = i + 1
				cursor.updateRow(row)

#export csv to folder -- remember to change fold path when run on other machines
arcpy.TableToTable_conversion(devproj_fc, 'D:/Users/blu/Desktop', "development_project.csv")

# delete temporary join files
for temp_fc in dev_projects_temp_layers:
  if arcpy.Exists(temp_fc):
    arcpy.Delete_management(temp_fc)
    logging.info("Deleting temporary layer {}".format(temp_fc))

#adding the two map files into a new gdb
#first create that new gdb -- right now save and locally and upload manually
out_folder_path = "D:/Users/blu/Documents/ArcGIS"
out_name = "devproj.gdb"
arcpy.CreateFileGDB_management(out_folder_path, out_name)

#second, move file to the new gdb
fcs = [pipeline_fc, devproj_fc]
for fc in fcs:
	arcpy.FeatureClassToFeatureClass_conversion(fc, out_folder_path + "/" + out_name, arcpy.Describe(fc).name)

# 6 DIAGNOSTICS

#number of units total by year
arcpy.Statistics_analysis(devproj_fc, 'res_stats_y', [["residential_units", "SUM"]], "year_built")
#then calculate the total 
arcpy.Statistics_analysis(devproj_fc, 'res_stats_a', [["residential_units", "SUM"]])
#get the total result and write into log
cursor = arcpy.SearchCursor('res_stats_a','','', 'SUM_residential_units')
row = cursor.next()
sum_value = row.getValue('SUM_residential_units')
logging.info("Total number of residential units in the development project file is {} units".format(int(sum_value)))

#number of nonres sqft by year
arcpy.Statistics_analysis(devproj_fc, 'nonres_stats_y', [["non_residential_sqft", "SUM"]], "year_built")
#then calculate the total 
arcpy.Statistics_analysis(devproj_fc, 'nonres_stats_a', [["non_residential_sqft", "SUM"]])
#get the total result and write into log
cursor = arcpy.SearchCursor('nonres_stats_a','','', 'SUM_non_residential_sqft')
row = cursor.next()
sum_value = row.getValue('SUM_non_residential_sqft')
logging.info("Total number of non residential square footage in the development project file is {} square feet".format(int(sum_value)))

#count parcels with more than one points on them - pipeline
#first, there is no development projects id for them, so set value for that
count = arcpy.GetCount_management(pipeline_fc)
i = 1
with arcpy.da.UpdateCursor(pipeline_fc, "development_projects_id") as cursor:
		for row in cursor:
			if i <= int(count[0]) :
				row[0] = i
				i  = i + 1
				cursor.updateRow(row)

arcpy.Statistics_analysis(pipeline_fc, "p_pipeline", [["development_projects_id", "COUNT"]], "geom_id")
p_pipeline = 'p_pipeline'
#there are projects with geom_id null, so in order to count, delete those first
with arcpy.da.UpdateCursor(p_pipeline, "geom_id") as cursor:
	for row in cursor:
		if row[0] is None:
			cursor.deleteRow()	
arcpy.MakeTableView_management(p_pipeline,"ppCount","COUNT_development_projects_id > 1")
ppCount = 'ppCount'
countParcelP = arcpy.GetCount_management(ppCount)
logging.info("There are {} of parcels with multiple project points (more than 1) on them in the pipeline file".format(countParcelP))

#count parcels with more than one points on them - development projects
arcpy.Statistics_analysis(devproj_fc, "p_dev", [["development_projects_id", "COUNT"]], "geom_id")
p_dev = 'p_dev'
#there are projects with geom_id null, so in order to count, delete those first
with arcpy.da.UpdateCursor(p_dev, "geom_id") as cursor:
	for row in cursor:
		if row[0] is None:
			cursor.deleteRow()	
arcpy.MakeTableView_management(p_dev,"pdCount","COUNT_development_projects_id > 1")
pdCount = 'pdCount'
countParcelD = arcpy.GetCount_management(pdCount)
logging.info("There are {} of parcels with multiple project points (more than 1) on them".format(countParcelD))


# 7 REMOVE DUPLICATES
# manually: go ahead and recode a 1 to 0 in the GIS file to not use a record 

# automatically switching incl to 0 or another code using hierarchy
# keep multiple points on same parcel from WITHIN the same dataset but don't add additional from lower datasets
# manual_dp is best, then cs, then BASIS, then redfin SFD, then all other redfin, then oppsites 


# 8 BUILDINGS TO ADD INSTEAD OF BUILD
# change a short list of activity to add
# first doing it for the pipeline file
pList_pipeline= [row[0] for row in arcpy.da.SearchCursor(ppCount, 'geom_id')]
if  "8016918253805" not in pList_pipeline:
	pList_pipeline.append('8016918253805')
if "9551692992638" not in pList_pipeline:
	pList_pipeline.append('9551692992638')
with arcpy.da.UpdateCursor(pipeline_fc, ["geom_id","action"]) as cursor:
    		for row in cursor:
    			if row[0] in pList_pipeline: 
    				row[1] = 'add'
    				cursor.updateRow(row)
# second doing it for the development project file
pList_dev= [row[0] for row in arcpy.da.SearchCursor(pdCount, 'geom_id')]
if  "8016918253805" not in pList_pipeline:
	pList_dev.append('8016918253805')
if "9551692992638" not in pList_pipeline:
	pList_dev.append('9551692992638')
with arcpy.da.UpdateCursor(devproj_fc, ["geom_id","action"]) as cursor:
    		for row in cursor:
    			if row[0] in pList_dev: 
    				row[1] = 'add'
    				cursor.updateRow(row)

arcpy.TableToTable_conversion(pipeline_fc, 'D:/Users/blu/Desktop', "pipeline_wActionAdd.csv")
arcpy.TableToTable_conversion(devproj_fc, 'D:/Users/blu/Desktop', "development_project_wActionAdd.csv")
fcs = [pipeline_fc, devproj_fc]
for fc in fcs:
	arcpy.FeatureClassToFeatureClass_conversion(fc, out_folder_path + "/" + out_name, arcpy.Describe(fc).name + 'wActionAdd')



# 9 EXPORT CSV W BUILDINGS TO BUILD AND DEMOLISH


