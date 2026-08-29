# Script to tune a random forest model of lithium
# Author: Katherine J. Knierim
# Date: October 25, 2023
library(glue)
library(doParallel)
library(ggplot2)
# library(hydroGOF) # for fit stats
library(fastshap) # for shap approximations
library(shapviz) # for plotting shap
library(sf) # read shapefiles
library(terra) # read and write rasters
library(tidyverse)
library(recipes)
library(tidymodels)


##### READ AND PREPARE DATA #####
# set working directory
setwd(dirname(rstudioapi::getSourceEditorContext()$path))
wdir = getwd()
wdir

# read prepared csv file
df <- read.csv('input/SAR_MLinput.txt')
df[df == -9999] <- NA # replace missing flag

# force categories to factors (for one-hot encoding)
df$buckner_facies   <- as.factor(df$buckner_facies)
df$smackover_facies <- as.factor(df$smackover_facies)
df$FRM_GRP          <- as.factor(df$FRM_GRP)

## Calculate depth where missing
# create well bottom alt (relative to sea level)
df$DEPTH_ALT <- df$DEM_1km_m - df$DEPTH_m

# calculate mid-point depth based on unit
df$ALT_FILL <- ifelse(is.na(df$DEPTH_m) & df$FRM_GRP == 'Smackover', 
                      df$smackover_alt - df$smackover_thick/2, # else
                      ifelse(is.na(df$DEPTH_m) & df$FRM_GRP == 'Nuevo Leon Grp', 
                             df$hosston_alt - df$hosston_thickness/2, # else
                             ifelse(is.na(df$DEPTH_m) & df$FRM_GRP == 'Cotton Valley', 
                                    df$cottonvalley_alt - df$cottonvalley_thickness/2, # else
                                    df$DEPTH_ALT)))

# create new depth column (with missing alt filled)
df$DEPTH_FILL <- ifelse(is.na(df$DEPTH_m), df$DEM_1km_m - df$ALT_FILL, df$DEPTH_m)
df$DEPTH_FILL <- round(df$DEPTH_FILL,0)

# compare depth columns (orig vs filled)
boxplot(df$DEPTH_m, df$DEPTH_FILL,
        names = c("Original depth, ft", "Filled depth, ft"))

# drop extra depth columns, missing depth filled in using geologic framework
df <- df[, !names(df) %in% c('DEM_1km_m','DEPTH_m', 'DEPTH_ALT', 'ALT_FILL', 'smackover_middepth','hosston_alt','cottonvalley_alt')]
summary(df)


#### SPLIT DATA #####

# create split object with 80% of the data stratified to formation
# set seed to reproduce random splitting for purpose of model documentation
set.seed(31849)
df_split <- rsample::initial_split(df, prop=0.8, strata = FRM_GRP)

# separate training (80%) and holdout (20%)
df_trn <- rsample::training(df_split)
df_hld <- rsample::testing(df_split)

# compare training and holdout data
boxplot(df_trn$Li, df_hld$Li,names = c("Training", "Holdout"), ylab='Lithium (milligrams per liter)')
summary(df$Li)
summary(df_trn$Li)
summary(df_hld$Li)

# plot explanatory variables to visualize distribution between training and holdout data
exvars <- names(df)[8:17]
for (i in exvars){
  boxplot(df_trn[[i]], df_hld[[i]],
          names = c("train", "holdout"), ylab=i)
}

rm(df_split)

### SET UP RF MODEL ####

# create recipe
rf_recipe <- recipe(formula = Li ~., data = df_trn) %>%  # response is lithium
  update_role(c(DSOURCE, SITEID, LATITUDE, LONGITUDE, Li_rmk), new_role = "Extras") %>% 
  step_dummy(buckner_facies, smackover_facies, FRM_GRP, one_hot = TRUE)

rf_recipe

# set model specifications
rf_spec <- parsnip::rand_forest(mtry = tune(), 
                                min_n = tune(),
                                trees = tune()) %>%  
  set_mode("regression") %>%
  set_engine("ranger")

# create workflow set
models <- workflow_set(
  preproc = list(onehotrf = rf_recipe),
  models = list(rf = rf_spec),
  cross = FALSE)

# create tuning grid
trees <- c(20,30,40,50,60,70,80,100,125,150,200,300,400,500,800,1000)
mtry <- seq(3,8, by=1) # suggest max 8
min_n <- seq(2,10, by=2)

rf_grid <- expand.grid(trees=trees,
                       mtry=mtry,
                       min_n=min_n)

# assign grid to model
models <- models %>% option_add(grid = rf_grid, id = "onehotrf_rf")
models

##### TUNE RF MODEL ####

# create folds for cross validation hyperparameter tuning
# set set to reproduce random cross validation splitting for purpose of model documentation 
set.seed(123)
v_folds <- vfold_cv(df_trn, v = 10) 

# set up parallel processing
cl <- makePSOCKcluster(10) # use the same number of cores as resamples, since parallel over resamples below
registerDoParallel(cl)

# set up grid control
grid_ctrl <- control_grid(
    save_pred = TRUE,
    parallel_over = "resamples",
    save_workflow = TRUE, 
    verbose = TRUE)

# tune
# set set to reproduce random cross validation folds for purpose of model documentation 
grid_results <- models %>%
  workflow_map(
    seed = 1503,                 
    resamples = v_folds,         
    control = grid_ctrl)                              

# stop parallel cluster
stopCluster(cl)
rm(cl, grid_ctrl, v_folds, rf_spec, models, rf_grid, min_n, mtry, trees, i) # remove tuning objs to clean env

##### INSPECT RESULTS #####

# view all results and plot
df_rank <- rank_results(grid_results, rank_metric = "rmse")
autoplot(grid_results, id = "onehotrf_rf", metric = "rmse")

# select best model 
rf_params <- grid_results %>% 
  extract_workflow_set_result("onehotrf_rf") %>% 
  select_best(metric = "rmse") 

# select model within one standard error (one-se) of best model
rf_params_se <- grid_results %>% 
  extract_workflow_set_result("onehotrf_rf") %>% 
  select_by_one_std_err(metric = "rmse", mtry)  # less mtry = less complex

rf_params # best model 
rf_params_se # onese model

### filter onese models

# filter for rmse metric
rf_rank <- df_rank %>%
  filter(wflow_id == 'onehotrf_rf'& .metric=='rmse')
# extract workflows and filter for hyperparameters and model
rfx <-  grid_results %>%
  extract_workflow_set_result("onehotrf_rf") 
rfxx <- rfx[[3]][[10]] %>% filter(.metric=='rmse') %>% select(mtry,trees,min_n,.config)
# join hyperparams to model performance results
df_rankj <- left_join(rf_rank, rfxx, by='.config')
# filter onese models based on rank
se_rank <- df_rankj[df_rankj$.config == rf_params_se$.config,]$rank
rf_rank_se <- df_rankj %>%
  filter(rank <= se_rank)
# sort by complexity
rf_rank_se_sort <- rf_rank_se %>% arrange(desc(min_n), mtry, trees)
rf_rank_se_sort$complexity <- as.numeric(row.names(rf_rank_se_sort))

rm(rf_rank, rfx, rfxx, df_rankj, se_rank, rf_rank_se) # remove intermediate dataframes to clean up env

# plot onese models
ggplot(rf_rank_se_sort, aes(x=complexity, y=mean)) + geom_point(aes(color=min_n))

# based on tuning results, pick model rank=14
rf_params_x <- dplyr::filter(rf_rank_se_sort, rank==14)
rf_params_x # final model


# fit model with final hyperparams
# set set to reproduce final tuned model for purpose of model documentation 
set.seed(1879)
rf_fitted <- grid_results %>% 
  extract_workflow("onehotrf_rf") %>% 
  finalize_workflow(rf_params_x) %>% 
  fit(data = df_trn) # train the finalized model on training data

# extract model object from fitted workflow
rf_mod <- extract_fit_engine(rf_fitted)


##### PREDICT TO TRAINING AND HOLDOUT #####

# Predict from a fitted workflow will apply the preprocessing specified in the recipe to any new data
df_trn_preds <- df_trn %>% mutate(rf_pred = predict(rf_fitted, df_trn) %>% pull(.pred)) 
df_trn_preds$mtype <- 'train'
df_hld_preds <- df_hld %>% mutate(rf_pred = predict(rf_fitted, df_hld) %>% pull(.pred)) 
df_hld_preds$mtype <- 'holdout'

# combine predictions into dataframe
df_preds <- rbind(df_trn_preds, df_hld_preds)
df_preds$rf_pred <- round(df_preds$rf_pred, 1)
df_preds$pred_dif <- round(df_preds$Li - df_preds$rf_pred, 1)


# plot predicted versus observed for training and holdout data
ggplot(df_preds) + geom_point(aes(x = Li, y = rf_pred, color=mtype)) + geom_abline() +
  ylab("Model Predicted Lithium (mg/L)") + xlab("Observed Lithium (mg/L)") +
  coord_obs_pred()

# summarize model performance 
mset <- yardstick::metric_set(rsq,rmse,mae,mape,mpe)
fit_trn <- mset(df_trn_preds, Li, rf_pred)
fit_hld <- mset(df_hld_preds, Li, rf_pred)


# compare published predicted values with values predicted during this R session
# summary should be all zeros; that is R script re-created published lithium predictions
df_pub <- read.csv('output/SAR_Lipreds.csv')
newdf <- merge(df_preds[,c('SITEID','mtype','rf_pred')], df_pub, by = 'SITEID')
newdf$dif <- newdf$Li_pred - newdf$rf_pred
summary(newdf$dif)
rm(df_pub, newdf, df_trn_preds, df_hld_preds) # remove intermediate objs to clean env

#### INSPECT EXPLANATORY VARIABLES ####

# create prediction wrapper function (to use with extracted fitted ranger model)
pfun_rf <- function(object, newdata) {
  predict(object, data = newdata)$predictions
}

# prep training data
rf_recipe_prep <- prep(rf_recipe, df_trn)
train_data_rf <- bake(rf_recipe_prep, df_trn) %>% select(-c(DSOURCE, SITEID, LATITUDE, LONGITUDE, Li_rmk, Li))

# compute SHAP values for ranger model with fastshap package
# adjust = TRUE gives shap values relative to the mean training data prediction (bias)
shap_rf <- fastshap::explain(rf_mod, X = data.frame(train_data_rf), pred_wrapper = pfun_rf, 
                             nsim = 100, adjust = TRUE)

# check that the total shap plus the mean training data prediction (bias) equals the prediction
all.equal(rowSums(shap_rf) + mean(predict(rf_mod, train_data_rf)$predictions), predict(rf_mod, train_data_rf)$predictions)
# show plot of SHAP values versus predictions
plot(rowSums(shap_rf) + mean(predict(rf_mod, train_data_rf)$predictions), predict(rf_mod, train_data_rf)$predictions)
abline(0,1)  # equal-value (1:1) line

# create SHAP plots with shapviz package
rf_viz <- shapviz::shapviz(shap_rf, X = train_data_rf)

# shap summary/beeswarm plot
sv_importance(rf_viz, kind = "beeswarm")

# shap importance as bar chart
sv_importance(rf_viz, kind = "bar")

# shap dependence plots

# depth
sv_dependence(rf_viz, v = "DEPTH_FILL", color='auto') # color by potential strongest interaction

# thickness of Buckner Formation
sv_dependence(rf_viz, v = "buckner_thick", color='auto') # color by potential strongest interaction

# Smackover temperature
sv_dependence(rf_viz, v = "smck_temp_int", color='auto') # color by potential strongest interaction

# h2S
sv_dependence(rf_viz, v = "h2s_class", color='auto') # color by potential strongest interaction

rm(rf_recipe_prep, train_data_rf) # remove intermediate objs to clean env


##### PREDICT TO MODEL DOMAIN #####

# read raster stack of explanatory variables across model domain
rdf <- read.csv('input/exvars/SAR_modeldomain_rasterstack.txt')
names(rdf)

# rename smackover depth to match well data (DEPTH_FILL)
rdf$DEPTH_FILL <- rdf$smackover_middepth

# keep only relevant columns
rdf <- rdf[, !names(rdf) %in% c('nacatoch_alt','hosston_alt','cottonvalley_alt', "smackover_middepth")]
summary(rdf)

# create FRM_GRP column - only predicting to Smackover Formation
rdf['FRM_GRP'] <- "Smackover"

# force factor columns
rdf$buckner_facies <- as.factor(rdf$buckner_facies)
rdf$FRM_GRP <- as.factor(rdf$FRM_GRP)
rdf$smackover_facies <- as.factor(rdf$smackover_facies)

# note that facies = 1 is in raster stack but not training data
# reset facies 1 to 0 (missing), and do not include model predictions for that facies (need to mask)
rdf$smackover_facies[rdf$smackover_facies==1] <- 0

# prep recipe with training data and bake on rstack data
newrf_rec <- update_role_requirements(rf_recipe, role = "Extras", bake = FALSE)
newrf_prep <- prep(newrf_rec)
rdf_baked <- bake(newrf_prep, rdf)

summary(rdf_baked)
rm(newrf_rec, newrf_prep) # remove intermediate objs to clean env

# predict using baked raster stack dataframe
r <- predict(rf_mod, rdf_baked)$predictions
r <- round(r,0)
summary(r)

# fill values into template raster
maskras <- terra::rast('grid/SAR_modeldomain_mask.tif')
outras <- maskras
values(outras) <- r

# mask out areas where training data are missing
outras[maskras==0] <- -99
plot(outras)
terra::writeRaster(outras,'output/smackover_Li_preds_new.tif', overwrite=TRUE)

# read published li predictions to compare to predictions from this session
r_pub <- terra::rast('output/smackover_Li_preds.tif')
plot(r_pub)

# compare published raster to raster created during this session
# summary should be all zeros; that is R script re-created published lithium predictions
r_dif <- outras - r_pub
plot(r_dif)
summary(r_dif)


#### PREDICT ONE STANDARD ERROR MODELS ####

# create directory
dir.create('output/uncertainty')

# prep training data
rf_recipe_prep <- prep(rf_recipe, df_trn)
train_data_rf <- bake(rf_recipe_prep, df_trn) %>% select(-c(DSOURCE, SITEID, LATITUDE, LONGITUDE, Li_rmk))

for (i in seq_len(nrow(rf_rank_se_sort))){
  # pull hyperparams
  t = rf_rank_se_sort$trees[[i]]
  n = rf_rank_se_sort$min_n[[i]]
  m =  rf_rank_se_sort$mtry[[i]]
  
  # set model specification
  rf_reg_spec <- 
    parsnip::rand_forest(trees=t, min_n=n, mtry=m) %>% 
    set_mode("regression") %>% 
    set_engine("ranger")
  
  # train model with hyperparams
  # set set to reproduce final one-standard error models for purpose of model documentation 
  set.seed(1)
  rf_reg_fit <- rf_reg_spec %>% fit(Li ~., data = train_data_rf)
  
  # predict using baked raster stack dataframe
  r <- predict(rf_reg_fit, rdf_baked)$.pred
  r <- round(r,0)
  
  # burn values into raster
  outras <- maskras
  values(outras) <- r
  
  # mask out areas where training data are missing
  outras[maskras==0] <- -99
  
  # write out
  terra::writeRaster(outras, glue('output/uncertainty/smackover_RF_{i}.tif'), overwrite=TRUE)
}
