Knierim, K.J., Blondes, M.S., Freeman, P.A., Masterson, A.L., McDevitt, B., Herzberg, A.S., Doolan, C., Chenault, J., Jubb, A.M., and Croke, M.R., 2024, Lithium observations, machine-learning predictions, and mass estimates from the Smackover Formation brines in southern Arkansas: U.S. Geological Survey data release, https://doi.org/10.5066/P9QPRYZN.  

[https://www.sciencebase.gov/catalog/item/65395410d34ee4b6e05bbc08  ]  

Related Interpretive Product: Knierim, K.J., Blondes, M.S., Masterson, A.L., Freeman, P.A., McDevitt, B., Herzberg, A.S., Li, P., Mills, C., Doolan, C., Jubb, A.M., Ausbrooks, S.M., Chenault, J., 2024, Evaluation of the lithium resource in the Smackover Formation brines of southern Arkansas using machine learning: Science Advances, v. 10, no. 39, 10.1126/sciadv.adp8149.


METADATA DATE: 12/01/2023

PRIMARY USGS CONTACT: 	Katherine Knierim	  
           		U.S. Geological Survey (USGS)           	
         		Lower Mississippi-Gulf Water Science Center           
                401 Hardin Road	 
	 	     	Little Rock, AR  
                voice: 501-228-3600  
                email: kknierim@usgs.gov 

SECONDARY USGS CONTACT: Madalyn Blondes  
          		U.S. Geological Survey (USGS)           	
         		Geology, Energy & Minerals Science Center           
                Reston, VA  
                voice: 703-648-6509  
                email: mblondes@usgs.gov   

# INTRODUCTION
Global demand for lithium, the primary component of lithium-ion batteries, greatly exceeds known supplies and this imbalance is expected to increase as the world transitions away from fossil fuel energy sources. The goal of this work was to calculate the total lithium mass in brines of the Reynolds oolite unit of the Smackover Formation in southern Arkansas using predicted lithium concentrations from a machine-learning model. This research was completed collaboratively between the U.S. Geological Survey and the Arkansas Department of Energy and Environment—Office of the State Geologist.  

The Smackover Formation is a laterally extensive petroleum and brine system in the Gulf Coast region that includes locally high concentrations of bromide and lithium in southern Arkansas. This data release contains input files, Python scripts, and an R script used to prepare input files, create a random forest (RF) machine-learning model to predict lithium concentrations, and compute uncertainty in brines of the Reynolds oolite unit of the Smackover Formation in southern Arkansas. This data release also contains a Python script to calculate the total mass of lithium in brines of the Reynolds oolite unit of the Smackover Formation in southern Arkansas based on porosity. Sophisticated data-science and knowledge of Python and R programming languages is a prerequisite for executing the workflow associated with this product. Users can execute the scripts to prepare input data, train a RF machine-learning model, compute uncertainty, and calculate lithium mass. Explanatory variables used to train the RF model included geologic, geochemical, and temperature data from either published datasets or created and documented in this data release and the associated companion publication (Knierim and others, 2024). See the associated metadata for details.

This data release also includes output files (csvs [comma-delimited, plain-text] and rasters [geospatial grids]) of lithium concentration predictions from the RF model, uncertainty ranges, and lithium mass. The depth of prediction of lithium concentration represents the mid-point depth of the Reynolds oolite unit which varies between approximately 3,500 and 11,300 feet deep (below land-surface datum) and 0 and 400 feet thick across the model domain. For a full explanation of methods and results, see the companion manuscript Knierim and others (2024).

***
***

# SOFTWARE AND ADDITIONAL DETAILS
Any use of trade, firm, or product names is for descriptive purposes only and does not imply endorsement by the U.S. Government.

Operating System and Software Versions:  
* Windows 10 Enterprise Version 22H2
* RStudio v. 6.2
* R v. 4.3
* Python v. 3.9

Total file input and output approximately 120 MB. 
Run times for workflow approximately 10 minutes.

# FILE AND DIRECTORY ORGANIZATION
## INPUT DATA STRUCTURES FOR WORKFLOW
This data release is organized with two files and one zipped directory of the model archive on the main landing page:

* readme.md: Describes the contents of all files and directories for executing model archives  

* southAR_li.xml: metadata file describing data associated with this data release

* sar_li.zip: zipped directory containing model archive (input and output);
	* grid/ (dir): directory of the model grid with six files;
		* readme.txt: description of grid directory
		* SAR_modeldomain_4269.shp: shapefile representing the model domain grid (including .dbf, .prj, .shp, .shx extensions)
		* SAR_modeldomain_mask.tif: tif file representing a masking layer for model output 
	* input/ (dir): input directory with four subdirectories and ten files
		* brine/ (dir): subdirectory of brine production and oil to water ratio data  
			* readme.txt: description of brine directory  
			* smackover_H2Oprod_2022.tif: raster file of brine production data from 2022 (S&P Global,2023)  
			* smackover_H2Oratios.tif: raster file of oil to water ratios in oil reservoirs (Nehring Associates, 2019)  
		* exvars/ (dir): subdirectory of explanatory variable files
			* readme.txt: description of exvars directory
			* SAR_explanatoryvars.txt: comma-delimited text file of explanatory variable values at locations of brine samples
			* SAR_modeldomain_rasterstack.txt: comma-delimited text file of explanatory variable values at cell locations across the model domain
		* usgs_pwgd (dir): subdirectory of USGS Produced Waters Geochemical Database v3 brine data and well depth metadata  
			* readme.txt: description of usgs_pwgd directory
			* sar_pwgdv3_updateddepths.csv: well depth information for wells that were missing depth in the USGS Produced Waters Geochemical Database v3  
		* usgs_southAR (dir): subdirectory of newly collected brine data
			* readme.txt: description of usgs_southAR directory
			* southAR_brines_2022.txt: text file of brine data from samples collected in August 2022 by the USGS  
	* output/ (dir): output directory with eight files
		* SAR_Lipreds.csv: csv file of lithium observations and predictions for brine samples
		* SAR_smackover_Liestimate.csv: csv file of estimated lithium mass for 6 model versions
		* smackover_Li_preds.tif: output tif of predicted lithium concentrations  
		* smackover_Li_uncertainty_p5.tif: output tif of the 5th percentile of predicted lithium concentrations from one-standard error (one-SE) models 
		* smackover_Li_uncertainty_p50.tif: output tif of the 50th percentile (median) of predicted lithium concentrations from one-standard error (one-SE) models 		
		* smackover_Li_uncertainty_p95.tif: output tif of the 95th percentile of predicted lithium concentrations from one-standard error (one-SE) models  
		* smackover_Li_uncertainty_rngp.tif: output tif of the difference between the 95th and 5th percentiles of predicted lithium concentrations from one-standard error (one-SE) models  
		* smackover_Li_uncertainty_qualunc.tif: output tif of the qualitative uncertainty of predicted lithium concentrations by equalities and inequalities (=, equal; > greater than; < less than; >=, greater than or equal to) being > 100 milligrams per liter (mg/L); (0 = very likely <100 mg/L, 1 = likely <100mg/L, 2 = likely >= 100 mg/L, 3 = likely > 100 mg/L)  

	* 1_SARLi_dataprep.py: Python script to prepare and merge data for modeling

	* 2_SARLi_RFmodel.R: R script to train a RF model to predict lithium

	* 3_SARLi_uncertainty.py: Python script to compute uncertainty in lithium predictions

	* 4_SARLi_estimate.py: Python script to calculate the lithium resource in southern Arkansas
	
	* DISCLAIMER.md: Markdown file with USGS software disclaimer
	
	* LICENSE.md: Markdown file with USGS license disclaimer

	* modelgeoref.txt: Describes model corner and geospatial projection information

## DATA RELEASE STRUCTURE
The workflow will run successfully only if all listed files are present and the original directory structure is preserved.
The complete directory structure of this archive is:


readme.md  
southAR_li.xml  
[sar_li.zip]  
----| [grid/] 
--------| readme.txt   
--------|SAR_modeldomain_4269.dbf  
--------|SAR_modeldomain_4269.prj  
--------|SAR_modeldomain_4269.shp  
--------|SAR_modeldomain_4269.shx  
--------|SAR_modeldomain_mask.tif   
----| [input/]   
--------| [brine/]  
------------|readme.txt  
------------|smackover_H2Oprod_2022.tif  
------------|smackover_H2Oratios.tif   
--------|[exvars/]  
------------|readme.txt  
------------|SAR_explanatoryvars.txt  
------------|SAR_modeldomain_rasterstack.txt  
--------|[usgs_pwgd/]  
------------|readme.txt    
------------|sar_pwgdv3_updateddepths.csv  
--------|[usgs_southAR/]  
------------|readme.txt    
------------|SAR_brines_2022.txt   
----|[output/]    
--------|SAR_Lipreds.csv  
--------|SAR_smackover_Liestimate.csv  
--------|smackover_Li_preds.tif  
--------|smackover_Li_uncertainty_p5.tif
--------|smackover_Li_uncertainty_p50.tif  
--------|smackover_Li_uncertainty_p95.tif  
--------|smackover_Li_uncertainty_qualunc.tif  
--------|smackover_Li_uncertainty_rngp.tif  
----|1_SARLi_dataprep.py  
----|2_SARLi_RFmodel.R  
----|3_SARLi_uncertainty.py  
----|4_SARLi_estimate.py  
----|DISCLAIMER.md  
----|LICENSE.md
----|modelgeoref.txt


# INSTRUCTIONS			

(1) Download all files from https://doi.org/10.5066/P9QPRYZN and extract the zipped files  
(2) Open the file "readme.md" for a listing of the files contained within the model archive
(3) Ensure that the file structure of the downloaded files match the description in the readme.md file
(4) Prepare data for modeling (pre-processing): 
	a) create a Python environment with the following packages: numpy (v1.25), pandas (v1.5), geopandas (v0.12), rasterio (v1.2), matplotlib (v3.7)  
	b) activate Python environment  
	c) execute script 1_SARLi_dataprep.py to create file  input/southAR_MLinput.txt
(5) Tune the RF model and predict lithium  
	a) open R studio (reminder that RStudio is not R itself but an interface on top of R used by the author) 
	b) install the following R packages: doParallel (v1.0), ggplot2 (v3.4), hydroGOF (v0.4), fastshap (v0.1), shapviz (v0.9), sf (v1.0), terra (v1.7), tidyverse (v2.0), recipes (v1.0), tidymodels (v1.1)  	
	c) run script 2_SARLi_dataprep.py to create output/smackover_Li_preds_new.tif  
(6) Compute uncertainty:  
	a)  execute script 3_SARLi_uncertainty.py to create uncertainty tifs
(7) Estimate lithium in southern AR:  
	a) execute script 4_SARLi_estimate.py to create output/SAR_smackover_Liestimate.csv; default porosity values are 10, 20, and 30% but the user can change values to compare calculations


## WORKFLOW OUTPUTS

The workflow will download and create files when the python and R scripts are executed. The following files are created or downloaded:
* input/gulfcoast_brines/gulfcoast_brines.shp: shapefile of brine data from the Gulf Coast, including the USGS Produced Waters Geochemical Database v3 and southern Arkansas brine data collected in 2022
* input/usgs_pwgd/USGS_NPWGDv3_excel.xlsx: Excel sheet (well-known commercial spreadsheet format) downloaded from the USGS Produced Waters Geochemical Database v3 (https://www.sciencebase.gov/catalog/item/64fa1e71d34ed30c2054ea11)
* input/southAR_MLinput.txt: comma-delimited, plain text file used as input for the random forest machine-learning model
* output/li_est/brine_vol_ML_XX.tif: tif file(s) of brine volume estimates (in million liters), where XX is porosity values entered by the user; default porosity is 10, 20, and 30%
* output/li_est/li_tons_MMMM_XX.tif: tif file(s) of lithium mass (in tons) for three different lithium concentration models, where MMMM is the model [either low (5th percentile), median (50th percentile), or high (95th percentile)] for XX porosity values entered by the user; default porosity is 10, 20, and 30%
* output/smackover_Li_preds_new.tif: tif file of predicted lithium concentrations in Smackover Formation brines, created by user
* output/SAR_smackover_Liestimate_{dt}.csv: comma-delimited, plain text file of lithium mass estimates for the Smackover Formation in southern Arkansas, created by user with dt as the YYYY_MMDD date stamp
* output/smackover_Li_uncertainty_p5_{dt}.tif: output tif of the 5th percentile of predicted lithium concentrations from one-standard error (one-SE) models, created by user with dt as the YYYY_MMDD date stamp
* output/smackover_Li_uncertainty_p50_{dt}.tif: output tif of the 50th percentile of predicted lithium concentrations from one-standard error (one-SE) models, created by user with dt as the YYYY_MMDD date stamp
* output/smackover_Li_uncertainty_p95_{dt}.tif: output tif of the 95th percentile of predicted lithium concentrations from one-standard error (one-SE) models, created by user with dt as the YYYY_MMDD date stamp
* output/smackover_Li_uncertainty_qualunc_{dt}.tif: output tif of the qualitative uncertainty of predicted lithium concentrations by equalities and inequalities (=, equal; > greater than; < less than; >=, greater than or equal to) being > 100 mg/L (0 = very likely <100 mg/L, 1 = likely <100mg/L, 2 = likely >= 100 mg/L, 3 = likely > 100 mg/L), created by user with dt as the YYYY_MMDD date stamp
* output/smackover_Li_uncertainty_rngp_{dt}.tif: output tif of the difference between the 95th and 5th percentiles of predicted lithium concentrations from one-standard error (one-SE) models, created by user with dt as the YYYY_MMDD date stamp