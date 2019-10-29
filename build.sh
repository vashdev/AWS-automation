#!/bin/bash 
# Build script is used to download source from code commit repo
# zip artifacts from repo
# package the zip files from source using cloudformaiton and upload to artifacts bucket.
#copyBatch,copyJobDetail,copyScripts,copyPHFiles,copySRDBConfig,copyIRDBConfig,copyVarCpdsConfig,copyEsbConfig,copySamConfig,copyPortConfig,copyJobEvents,createDocker,ddl-to-glue,CopyMigrationPkg,glueAdhocScript,updateS3Trigger

aws configure set default.s3.multipart_threshold 200MB
ACL="bucket-owner-full-control"
REGION="us-east-1"
AWS_ACCOUNT_NUMBER=`aws sts get-caller-identity --output text --query 'Account'`

#get config values
echo "loading config values ..."
chmod +x ./buildscripts/build-config-${ENV_CD}.sh
. ./buildscripts/build-config-${ENV_CD}.sh

echo "loading Environment vars from s3"
aws s3 cp s3://${CUR_SOURCE_BUCKET}/app/mrpdata/candidate/Env-vars-${ENV_CD}_${ENV_NO}.json .

ACTIONS=$(cat Env-vars-${ENV_CD}_${ENV_NO}.json | grep ACTIONS\": | sed s/' '//g | awk -F':\"' '{ print $2 }' | sed s/\",// | sed s/\"//)
#ACTIONS=$(cat Env-vars-${ENV_CD}_${ENV_NO}.json | grep ACTIONS\": | sed s/ACTIONS\":// | sed s/\",// | sed s/\"//g | sed s/' '//g)
BATCH_SOURCE_ENV=$(cat Env-vars-${ENV_CD}_${ENV_NO}.json | grep BATCH_SOURCE_ENV\": | sed s/' '//g | awk -F':\"' '{ print $2 }' | sed s/\",// | sed s/\"//)
S3_SOURCE_SCRIPT=$(cat Env-vars-${ENV_CD}_${ENV_NO}.json | grep S3_SOURCE_SCRIPT\": | sed s/' '//g | awk -F':\"' '{ print $2 }' | sed s/\",// | sed s/\"//)
PROMOTE_VERSION=$(cat Env-vars-${ENV_CD}_${ENV_NO}.json | grep PROMOTE_VERSION\": | sed s/' '//g | awk -F':\"' '{ print $2 }' | sed s/\",// | sed s/\"//)

echo ENV_CD=${ENV_CD}
echo ENV_NO=${ENV_NO}
echo BATCH_SOURCE_ENV=${BATCH_SOURCE_ENV}
echo S3_SOURCE_SCRIPT=${S3_SOURCE_SCRIPT}
echo PROMOTE_VERSION=${PROMOTE_VERSION}
echo ACTIONS=${ACTIONS}
echo "-------"
echo ""

#create artifact folder if it does not exist
date '+%Y%m%d%H%M%S'
path=$(pwd)
cd ${path}

pwd
#ls
set
########
#1. Package in source zip to move to next environment
#echo ${path}:
#ls -ltr
#echo "/dataFiles":
#ls -ltr dataFiles/
#echo "/dataFiles/JobDefinitions/":
#ls -ltr dataFiles/JobDefinitions/
zip -rq ${path}/source.zip .

#create zip files needed for cloud formation yaml

echo ""
echo "creating zip files ..."
cd fre01-mrpdata-event-controller ;                     zip -r ../fre01-mrpdata-event-controller.zip . * ; cd ..
cd fre01-mrpdata-log-job-start-event  ;                 zip -rq ../fre01-mrpdata-log-job-start-event.zip . * ; cd ..
cd fre01-mrpdata-log-valuation-job-start-event ;        zip -rq ../fre01-mrpdata-log-valuation-job-start-event.zip . * ; cd ..
cd fre01-mrpdata-log-job-failed-event ;                 zip -rq ../fre01-mrpdata-log-job-failed-event.zip . * ; cd ..
cd fre01-mrpdata-log-job-success-event ;                zip -rq ../fre01-mrpdata-log-job-success-event.zip . * ; cd ..
cd fre01-mrpdata-dgp-redshift-sql-executor ;            zip -rq ../fre01-mrpdata-dgp-redshift-sql-executor.zip . * ; cd ..
cd fre01-mrpdata-dgp-batch-job-trigger ;                zip -rq ../fre01-mrpdata-dgp-batch-job-trigger.zip . * ; cd ..    
cd fre01-mrpdata-gdc ;                                  zip -rq ../fre01-mrpdata-gdc.zip . * ; cd ..    
cd fre01-mrpdata-gdc-invalid-partition ;                zip -rq ../fre01-mrpdata-gdc-invalid-partition.zip . * ; cd ..      
cd fre01-mrpdata-portfolio-combiner-readiness-check ;   zip -rq ../fre01-mrpdata-portfolio-combiner-readiness-check.zip . * ; cd ..
cd fre01-mrpdata-mstr-controller ;                      zip -rq ../fre01-mrpdata-mstr-controller.zip . * ; cd ..    
cd fre01-mrpdata-mstr-job-status ;                      zip -rq ../fre01-mrpdata-mstr-job-status.zip . * ; cd ..  
cd fre01-dblayer    ;                                    zip -rq ../fre01-dblayer.zip . * ; cd ..
cd fre01-mstrLayer    ;                                    zip -rq ../fre01-mstrLayer.zip . * ; cd ..
   
echo " Zip file list"       
ls -ltr *.zip
#take backup of deployed code in CURRENT environment
echo ""
echo "sending source.zip ..."

curdt=$(date +%Y%m%d)
echo curdt=${curdt}
echo aws s3 cp ${path}/source.zip s3://${CUR_SOURCE_BUCKET}/app/mrpdata/deployed/${ENV_CD}_${ENV_NO}/source${curdt}.zip  --sse 'AES256' --acl ${ACL}
aws s3 cp ${path}/source.zip s3://${CUR_SOURCE_BUCKET}/app/mrpdata/deployed/${ENV_CD}_${ENV_NO}/source${curdt}.zip  --sse 'AES256' --acl ${ACL}

#Upload candidate code to NEXT environment
if [[ ${#NEXT_SOURCE_BUCKET} -ne 0 ]] && [[ ${#PROMOTE_VERSION} -ne 0 ]]
then
   echo aws s3 cp ${path}/source.zip s3://${NEXT_SOURCE_BUCKET}/app/mrpdata/candidate/${ENV_CD}_${ENV_NO}/${PROMOTE_VERSION}/source.zip  --sse 'AES256' --acl ${ACL}
   aws s3 cp ${path}/source.zip s3://${NEXT_SOURCE_BUCKET}/app/mrpdata/candidate/${ENV_CD}_${ENV_NO}/${PROMOTE_VERSION}/source.zip  --sse 'AES256' --acl ${ACL}
fi
echo "removing source.zip as not needed any more"
rm ${path}/source.zip


#########
#2. Perform optional actions based on parameter to deploy different components like building docker, copying dependent files
if [[ ${ACTIONS} == *"createDocker"* ]]
then
   echo ""
   echo "creating docker image ..."
   docker info
    
   #aws ecr get-login --no-include-email
   echo "logining into ECR"
   $(aws ecr get-login --no-include-email --region us-east-1)

   cd ${path}/docker/fetch-and-run    
   echo "Current Dir=${path}"
	pwd
   ls -ltr    

   #building docker image
 	DockerName=mrp-fetch-and-run-java8-${ENV_NO}
   ENV=`echo "${Environment//-}"`
   echo ENV=${ENV}

   echo "creation of docker with ECR=${ECR_REPO_NAME} and Docker=${DockerName}"
   #echo docker build -t ${DockerName} --build-arg AWS_ACCOUNT_NUMBER=${AWS_ACCOUNT_NUMBER} --build-arg ENV=${ENV} .
   #docker build -t ${DockerName} --build-arg AWS_ACCOUNT_NUMBER=${AWS_ACCOUNT_NUMBER} --build-arg ENV=${ENV} .
   docker build -t ${DockerName}  .
    
   docker images --filter reference=${DockerName}   
    
   echo "adding the docker to tag"
   docker tag ${DockerName}:latest ${AWS_ACCOUNT_NUMBER}.dkr.ecr.us-east-1.amazonaws.com/${ECR_REPO_NAME}:${DockerName}
   echo "pushing the docker to ECR"
   docker push ${AWS_ACCOUNT_NUMBER}.dkr.ecr.us-east-1.amazonaws.com/${ECR_REPO_NAME}:${DockerName}
 
	cd ${path}
fi
   
if [[ ${ACTIONS} == *"copyJobDetail"* ]] || [[ ${ACTIONS} == *"TypicalDeploy"* ]]
then
    echo ""
   echo "copying job definition list ..."

   #Take back up of current files in EDL bucket before overwriting
   aws s3 cp s3://${CUR_EDL_BUCKET}/config/app/mrpdata/${ENV_CD}_${ENV_NO}/JobDefinitions/JobDefinitionList.json s3://${CUR_SOURCE_BUCKET}/app/mrpdata/backup/${curdt}/${ENV_CD}_${ENV_NO}/JobDefinitionList.json  --sse AES256
   if [[ $? -ne 0 ]]; then
      echo "No need to backup as old job definitions do not exist"
   fi

   if [ "${Environment}" == "acpt-edl" ]
   then
      echo replacing db param for acpt
      cat dataFiles/JobDefinitions/JobDefinitionList.json | sed s/SFLoans_Launcher_run.sh/'SFLoans_Launcher_run.sh --context_param JOB_EDI_DB_NAME_CIN=fn2ln1_acptedl_ent_edw_ln_isgt_acpt1 --context_param JOB_EDI_DB_NAME_CRS=fn2ln1_acptedl_ent_edw_ln_isgt_acpt1'/g >  dataFiles/JobDefinitions/JobDefinitionList1.json
      cp dataFiles/JobDefinitions/JobDefinitionList1.json dataFiles/JobDefinitions/JobDefinitionList.json
   fi
   
   #Now overwrite files in EDL bucket
   echo aws s3 cp dataFiles/JobDefinitions/JobDefinitionList.json s3://${CUR_EDL_BUCKET}/config/app/mrpdata/${ENV_CD}_${ENV_NO}/JobDefinitions/JobDefinitionList.json --sse aws:kms --sse-kms-key-id alias/fnma/app/fre01
   aws s3 cp dataFiles/JobDefinitions/JobDefinitionList.json s3://${CUR_EDL_BUCKET}/config/app/mrpdata/${ENV_CD}_${ENV_NO}/JobDefinitions/JobDefinitionList.json --sse aws:kms --sse-kms-key-id alias/fnma/app/fre01
fi
#
if [[ ${ACTIONS} == *"copyBatch"* ]] || [[ ${ACTIONS} == *"TypicalDeploy"* ]]
then
   echo ""
   echo "copying batch files ..."

   #take back up of current zipes before overwriting
   aws s3 mv s3://${CUR_EDL_BUCKET}/deploy/app/mrpdata/${ENV_CD}_${ENV_NO}/batch/ s3://${CUR_SOURCE_BUCKET}/app/mrpdata/backup/${curdt}/${ENV_CD}_${ENV_NO}/batch/ --recursive --sse AES256
   if [[ $? -ne 0 ]]; then
      echo "No need to backup as old batch files do not exist"
   fi

   #copy zips from source/candidate bucket to deploy folder for devl/non-devl environments respectively
   if [ "${Environment}" == "devl-edl" ]
   then
      echo aws s3 cp s3://${CUR_SOURCE_BUCKET}/app/mrpdata/source/${BATCH_SOURCE_ENV}/batch/ s3://${CUR_EDL_BUCKET}/deploy/app/mrpdata/${ENV_CD}_${ENV_NO}/batch/ --recursive --sse aws:kms --sse-kms-key-id alias/fnma/app/fre01
      aws s3 cp s3://${CUR_SOURCE_BUCKET}/app/mrpdata/source/${BATCH_SOURCE_ENV}/batch/ s3://${CUR_EDL_BUCKET}/deploy/app/mrpdata/${ENV_CD}_${ENV_NO}/batch/ --recursive --sse aws:kms --sse-kms-key-id alias/fnma/app/fre01
   else
      echo aws s3 cp s3://${CUR_SOURCE_BUCKET}/app/mrpdata/candidate/${BATCH_SOURCE_ENV}/batch/ s3://${CUR_EDL_BUCKET}/deploy/app/mrpdata/${ENV_CD}_${ENV_NO}/batch/ --recursive --sse aws:kms --sse-kms-key-id alias/fnma/app/fre01
      aws s3 cp s3://${CUR_SOURCE_BUCKET}/app/mrpdata/candidate/${BATCH_SOURCE_ENV}/batch/ s3://${CUR_EDL_BUCKET}/deploy/app/mrpdata/${ENV_CD}_${ENV_NO}/batch/ --recursive --sse aws:kms --sse-kms-key-id alias/fnma/app/fre01
   fi
    
   #copy zips to next environment
   # devl copy from source to next env candidate else move candidate of current env to candidate of next.
   echo "NEXT source bucket="${NEXT_SOURCE_BUCKET}
   if [[ ${#NEXT_SOURCE_BUCKET} -ne 0 ]] && [[ ${#PROMOTE_VERSION} -ne 0 ]]
   then
      echo aws s3 rm s3://${NEXT_SOURCE_BUCKET}/app/mrpdata/candidate/${ENV_CD}_${ENV_NO}/${PROMOTE_VERSION}/batch --recursive
      aws s3 rm s3://${NEXT_SOURCE_BUCKET}/app/mrpdata/candidate/${ENV_CD}_${ENV_NO}/${PROMOTE_VERSION}/batch --recursive
      echo aws s3 cp s3://${CUR_EDL_BUCKET}/deploy/app/mrpdata/${ENV_CD}_${ENV_NO}/batch/ s3://${NEXT_SOURCE_BUCKET}/app/mrpdata/candidate/${ENV_CD}_${ENV_NO}/${PROMOTE_VERSION}/batch/ --recursive  --sse 'AES256' --acl ${ACL}
      aws s3 cp s3://${CUR_EDL_BUCKET}/deploy/app/mrpdata/${ENV_CD}_${ENV_NO}/batch/ s3://${NEXT_SOURCE_BUCKET}/app/mrpdata/candidate/${ENV_CD}_${ENV_NO}/${PROMOTE_VERSION}/batch/ --recursive  --sse 'AES256' --acl ${ACL}
   fi
fi
#
if [[ ${ACTIONS} == *"copyPHFiles"* ]] || [[ ${ACTIONS} == *"TypicalDeploy"* ]]
then
   echo ""
   echo "copying product heirarchy files ..."

   #Take back up of current files in EDL bucket before overwriting
   aws s3 cp s3://${CUR_EDL_BUCKET}/config/app/mrpdata/${ENV_CD}_${ENV_NO}/prdct_hierarchy/ s3://${CUR_SOURCE_BUCKET}/app/mrpdata/backup/${curdt}/${ENV_CD}_${ENV_NO}/prdct_hierarchy/ --recursive --sse AES256
   if [[ $? -ne 0 ]]; then
      echo "No need to backup as old product hierarchy files do not exist"
   fi

   #Now overwrite files in EDL bucket
   echo aws s3 cp ${path}/dataFiles/prdct_hierarchy/ s3://${CUR_EDL_BUCKET}/config/app/mrpdata/${ENV_CD}_${ENV_NO}/prdct_hierarchy/ --recursive --sse aws:kms --sse-kms-key-id alias/fnma/app/fre01
   aws s3 cp ${path}/dataFiles/prdct_hierarchy/ s3://${CUR_EDL_BUCKET}/config/app/mrpdata/${ENV_CD}_${ENV_NO}/prdct_hierarchy/ --recursive --sse aws:kms --sse-kms-key-id alias/fnma/app/fre01
fi
#
if [[ ""${ACTIONS}"" == *"copySRDBConfig"* ]] || [[ ${ACTIONS} == *"TypicalDeploy"* ]]
then
   echo ""
   echo "copying SRDB config files ..."

   #Take back up of current files in EDL bucket before overwriting
   aws s3 cp s3://${CUR_EDL_BUCKET}/config/app/mrpdata/${ENV_CD}_${ENV_NO}/srdb/ s3://${CUR_SOURCE_BUCKET}/app/mrpdata/backup/${curdt}/${ENV_CD}_${ENV_NO}/srdb/ --recursive --sse AES256
   if [[ $? -ne 0 ]]; then
      echo "No need to backup as old srdb files do not exist"
   fi

   #Now overwrite files in EDL bucket
   echo aws s3 cp ${path}/dataFiles/srdb/ s3://${CUR_EDL_BUCKET}/config/app/mrpdata/${ENV_CD}_${ENV_NO}/srdb/ --recursive --sse aws:kms --sse-kms-key-id alias/fnma/app/fre01
   aws s3 cp ${path}/dataFiles/srdb/ s3://${CUR_EDL_BUCKET}/config/app/mrpdata/${ENV_CD}_${ENV_NO}/srdb/ --recursive --sse aws:kms --sse-kms-key-id alias/fnma/app/fre01
fi
#
if [[ ""${ACTIONS}"" == *"copyIRDBConfig"* ]] || [[ ${ACTIONS} == *"TypicalDeploy"* ]]
then
   echo ""
   echo "copying IRDB config files ..."

   #Take back up of current files in irdb bucket before overwriting
   aws s3 cp s3://${CUR_EDL_BUCKET}/config/app/mrpdata/${ENV_CD}_${ENV_NO}/irdb/ s3://${CUR_SOURCE_BUCKET}/app/mrpdata/backup/${curdt}/${ENV_CD}_${ENV_NO}/irdb/ --recursive --sse AES256
   if [[ $? -ne 0 ]]; then
      echo "No need to backup as old irdb files do not exist"
   fi

   #Now overwrite files in EDL bucket
   echo aws s3 cp ${path}/dataFiles/irdb/ s3://${CUR_EDL_BUCKET}/config/app/mrpdata/${ENV_CD}_${ENV_NO}/irdb/ --recursive --sse aws:kms --sse-kms-key-id alias/fnma/app/fre01
   aws s3 cp ${path}/dataFiles/irdb/ s3://${CUR_EDL_BUCKET}/config/app/mrpdata/${ENV_CD}_${ENV_NO}/irdb/ --recursive --sse aws:kms --sse-kms-key-id alias/fnma/app/fre01
fi
#
if [[ ""${ACTIONS}"" == *"copyVarCpdsConfig"* ]] || [[ ${ACTIONS} == *"TypicalDeploy"* ]]
then
   echo ""
   echo "copying var config files ..."

   #Take back up of current files in EDL bucket before overwriting
   aws s3 cp s3://${CUR_EDL_BUCKET}/config/app/mrpdata/${ENV_CD}_${ENV_NO}/var/ s3://${CUR_SOURCE_BUCKET}/app/mrpdata/backup/${curdt}/${ENV_CD}_${ENV_NO}/var/ --recursive --sse AES256
   if [[ $? -ne 0 ]]; then
      echo "No need to backup as old var file does not exist"
   fi
   aws s3 cp s3://${CUR_EDL_BUCKET}/config/app/mrpdata/${ENV_CD}_${ENV_NO}/cpds/ s3://${CUR_SOURCE_BUCKET}/app/mrpdata/backup/${curdt}/${ENV_CD}_${ENV_NO}/cpds/ --recursive --sse AES256
   if [[ $? -ne 0 ]]; then
      echo "No need to backup as old cpds file does not exist"
   fi

   #Now overwrite files in EDL bucket
   echo aws s3 cp ${path}/dataFiles/var/ s3://${CUR_EDL_BUCKET}/config/app/mrpdata/${ENV_CD}_${ENV_NO}/var/ --recursive --sse aws:kms --sse-kms-key-id alias/fnma/app/fre01
   aws s3 cp ${path}/dataFiles/var/ s3://${CUR_EDL_BUCKET}/config/app/mrpdata/${ENV_CD}_${ENV_NO}/var/ --recursive --sse aws:kms --sse-kms-key-id alias/fnma/app/fre01

   echo aws s3 cp ${path}/dataFiles/cpds/ s3://${CUR_EDL_BUCKET}/config/app/mrpdata/${ENV_CD}_${ENV_NO}/cpds/ --recursive --sse aws:kms --sse-kms-key-id alias/fnma/app/fre01
   aws s3 cp ${path}/dataFiles/cpds/ s3://${CUR_EDL_BUCKET}/config/app/mrpdata/${ENV_CD}_${ENV_NO}/cpds/ --recursive --sse aws:kms --sse-kms-key-id alias/fnma/app/fre01
fi

if [[ ""${ACTIONS}"" == *"copyEsbConfig"* ]] || [[ ${ACTIONS} == *"TypicalDeploy"* ]]
then
   echo ""
   echo "copying esb config files ..."

   #Take back up of current files in EDL bucket before overwriting
   aws s3 cp s3://${CUR_EDL_BUCKET}/config/app/mrpdata/${ENV_CD}_${ENV_NO}/esb/ s3://${CUR_SOURCE_BUCKET}/app/mrpdata/backup/${curdt}/${ENV_CD}_${ENV_NO}/esb/ --recursive --sse AES256
   if [[ $? -ne 0 ]]; then
      echo "No need to backup as old esb files do not exist"
   fi

   #Now overwrite files in EDL bucket
   echo aws s3 cp ${path}/dataFiles/esb/amtm_${ENV_CD}/ s3://${CUR_EDL_BUCKET}/config/app/mrpdata/${ENV_CD}_${ENV_NO}/esb/amtm/ --recursive --sse aws:kms --sse-kms-key-id alias/fnma/app/fre01
   aws s3 cp ${path}/dataFiles/esb/amtm_${ENV_CD}/ s3://${CUR_EDL_BUCKET}/config/app/mrpdata/${ENV_CD}_${ENV_NO}/esb/amtm/ --recursive --sse aws:kms --sse-kms-key-id alias/fnma/app/fre01
fi

if [[ ""${ACTIONS}"" == *"copySamConfig"* ]] || [[ ${ACTIONS} == *"TypicalDeploy"* ]]
then
   echo ""
   echo "copying sam config files ..."

   #Take back up of current files in EDL bucket before overwriting
   aws s3 cp s3://${CUR_EDL_BUCKET}/config/app/mrpdata/${ENV_CD}_${ENV_NO}/sam/ s3://${CUR_SOURCE_BUCKET}/app/mrpdata/backup/${curdt}/${ENV_CD}_${ENV_NO}/sam/ --recursive --sse AES256
   if [[ $? -ne 0 ]]; then
      echo "No need to backup as old sam files do not exist"
   fi

   #Now overwrite files in EDL bucket
   echo aws s3 cp ${path}/dataFiles/sam/ s3://${CUR_EDL_BUCKET}/config/app/mrpdata/${ENV_CD}_${ENV_NO}/sam/ --recursive --sse aws:kms --sse-kms-key-id alias/fnma/app/fre01
   aws s3 cp ${path}/dataFiles/sam/ s3://${CUR_EDL_BUCKET}/config/app/mrpdata/${ENV_CD}_${ENV_NO}/sam/ --recursive --sse aws:kms --sse-kms-key-id alias/fnma/app/fre01
fi

if [[ ""${ACTIONS}"" == *"copyPortConfig"* ]] || [[ ${ACTIONS} == *"TypicalDeploy"* ]]
then
   echo ""
   echo "copying port dim fact config file ..."

   #Take back up of current files in EDL bucket before overwriting
   aws s3 cp s3://${CUR_EDL_BUCKET}/config/app/mrpdata/${ENV_CD}_${ENV_NO}/port_dim_fact/ s3://${CUR_SOURCE_BUCKET}/app/mrpdata/backup/${curdt}/${ENV_CD}_${ENV_NO}/port_dim_fact/ --recursive --sse AES256
   if [[ $? -ne 0 ]]; then
      echo "No need to backup as old sam files do not exist"
   fi

   #Now overwrite files in EDL bucket
   echo aws s3 cp ${path}/dataFiles/port_dim_fact/ s3://${CUR_EDL_BUCKET}/config/app/mrpdata/${ENV_CD}_${ENV_NO}/port_dim_fact/ --recursive --sse aws:kms --sse-kms-key-id alias/fnma/app/fre01
   aws s3 cp ${path}/dataFiles/port_dim_fact/ s3://${CUR_EDL_BUCKET}/config/app/mrpdata/${ENV_CD}_${ENV_NO}/port_dim_fact/ --recursive --sse aws:kms --sse-kms-key-id alias/fnma/app/fre01
fi

if [[ ""${ACTIONS}"" == *"copyJobEvents"* ]] || [[ ${ACTIONS} == *"TypicalDeploy"* ]]
then
   echo ""
   echo "copying job event files ..."

   #Take back up of current files in EDL bucket before overwriting
   aws s3 cp s3://${CUR_EDL_BUCKET}/config/app/mrpdata/${ENV_CD}_${ENV_NO}/JobEvents/ s3://${CUR_SOURCE_BUCKET}/app/mrpdata/backup/${curdt}/${ENV_CD}_${ENV_NO}/JobEvents/ --recursive --sse AES256
   if [[ $? -ne 0 ]]; then
      echo "No need to backup as old sam files do not exist"
   fi

   #Now overwrite files in EDL bucket
   echo aws s3 cp ${path}/dataFiles/JobEvents/ s3://${CUR_EDL_BUCKET}/config/app/mrpdata/${ENV_CD}_${ENV_NO}/JobEvents/ --recursive --sse aws:kms --sse-kms-key-id alias/fnma/app/fre01
   aws s3 cp ${path}/dataFiles/JobEvents/ s3://${CUR_EDL_BUCKET}/config/app/mrpdata/${ENV_CD}_${ENV_NO}/JobEvents/ --recursive --sse aws:kms --sse-kms-key-id alias/fnma/app/fre01
fi

if [[ ""${ACTIONS}"" == *"copyScripts"* ]] || [[ ${ACTIONS} == *"TypicalDeploy"* ]]
then
   echo ""
   echo "copying scripts ..."

   aws s3 cp ${path}/dataFiles/scripts/fre01_job_runner.sh  s3://${CUR_EDL_BUCKET}/deploy/app/mrpdata/${ENV_CD}_${ENV_NO}/scripts/ --sse aws:kms --sse-kms-key-id alias/fnma/app/fre01

   #upload scripts in s3 for future execution
   cat dataFiles/scripts/uploadIsgtFiles1.sh | sed s/'${ENV_CD}'/${ENV_CD}/g | sed s/'${ENV_NO}'/${ENV_NO}/g > dataFiles/scripts/uploadIsgtFiles.sh
   cat dataFiles/scripts/uploadLandFiles1.sh | sed s/'${ENV_CD}'/${ENV_CD}/g | sed s/'${ENV_NO}'/${ENV_NO}/g > dataFiles/scripts/uploadLandFiles.sh
   cat dataFiles/scripts/uploadPrepFiles1.sh | sed s/'${ENV_CD}'/${ENV_CD}/g | sed s/'${ENV_NO}'/${ENV_NO}/g > dataFiles/scripts/uploadPrepFiles.sh
   cat dataFiles/scripts/uploadHist1.sh | sed s/'${ENV_CD}'/${ENV_CD}/g | sed s/'${ENV_NO}'/${ENV_NO}/g > dataFiles/scripts/uploadHist.sh

   cat dataFiles/scripts/sas/sas_execute_script1.sh | sed s/'${ENV_CD}'/${ENV_CD}/g | sed s/'${ENV_NO}'/${ENV_NO}/g > dataFiles/scripts/sas/sas_execute_script.sh

   cat dataFiles/scripts/RS/RS1_CMDS_CLOUD_REPOSITORY_DDL1.sql | sed s/'${ENV_CD}'/${ENV_CD}/g | sed s/'${ENV_NO}'/${ENV_NO}/g > dataFiles/scripts/RS/RS1_CMDS_CLOUD_REPOSITORY_DDL.sql
   cat dataFiles/scripts/RS/RS2_CMBI_CLOUD_REPOSITORY_DDL1.sql | sed s/'${ENV_CD}'/${ENV_CD}/g | sed s/'${ENV_NO}'/${ENV_NO}/g > dataFiles/scripts/RS/RS2_CMBI_CLOUD_REPOSITORY_DDL.sql
   cat dataFiles/scripts/RS/RS3_Create_Functions1.sql | sed s/'${ENV_CD}'/${ENV_CD}/g | sed s/'${ENV_NO}'/${ENV_NO}/g > dataFiles/scripts/RS/RS3_Create_Functions.sql
   cat dataFiles/scripts/RS/RS4_CMDS_VIEWS1.sql | sed s/'${ENV_CD}'/${ENV_CD}/g | sed s/'${ENV_NO}'/${ENV_NO}/g > dataFiles/scripts/RS/RS4_CMDS_VIEWS.sql
   cat dataFiles/scripts/RS/RS5_CMBI_CLOUD_VIEWS1.sql | sed s/'${ENV_CD}'/${ENV_CD}/g | sed s/'${ENV_NO}'/${ENV_NO}/g > dataFiles/scripts/RS/RS5_CMBI_CLOUD_VIEWS.sql
   cat dataFiles/scripts/RS/RS6_GRANT_VIEW_PRIVILEGES1.sql | sed s/'${ENV_CD}'/${ENV_CD}/g | sed s/'${ENV_NO}'/${ENV_NO}/g > dataFiles/scripts/RS/RS6_GRANT_VIEW_PRIVILEGES.sql
   cat dataFiles/scripts/RS/RS7_GRANT_VIEW_PRIVILEGES1.sql  | sed s/'${ENV_CD}'/${ENV_CD}/g | sed s/'${ENV_NO}'/${ENV_NO}/g > dataFiles/scripts/RS/RS7_GRANT_VIEW_PRIVILEGES.sql
   cat dataFiles/scripts/RS/RS8_GRANT_VIEW_PRIVILEGES1.sql | sed s/'${ENV_CD}'/${ENV_CD}/g | sed s/'${ENV_NO}'/${ENV_NO}/g > dataFiles/scripts/RS/RS8_GRANT_VIEW_PRIVILEGES.sql
   cat dataFiles/scripts/RS/RS9_TABLE_DDL1.sql  | sed s/'${ENV_CD}'/${ENV_CD}/g | sed s/'${ENV_NO}'/${ENV_NO}/g > dataFiles/scripts/RS/RS9_TABLE_DDL.sql
   cat dataFiles/scripts/RS/RS10_HIST_VIEW1.sql  | sed s/'${ENV_CD}'/${ENV_CD}/g | sed s/'${ENV_NO}'/${ENV_NO}/g > dataFiles/scripts/RS/RS10_HIST_VIEW.sql
   cat dataFiles/scripts/RS/RS11_PRIMA_VIEW1.sql  | sed s/'${ENV_CD}'/${ENV_CD}/g | sed s/'${ENV_NO}'/${ENV_NO}/g > dataFiles/scripts/RS/RS11_PRIMA_VIEW.sql

   rm dataFiles/scripts/uploadIsgtFiles1.sh
   rm dataFiles/scripts/uploadLandFiles1.sh
   rm dataFiles/scripts/uploadPrepFiles1.sh
   rm dataFiles/scripts/uploadHist1.sh
   rm dataFiles/scripts/sas/sas_execute_script1.sh
   rm dataFiles/scripts/COPYRIGHT
   rm dataFiles/scripts/RS/RS*.sql

   echo aws s3 cp ${path}/dataFiles/scripts/ s3://${CUR_EDL_BUCKET}/config/app/mrpdata/${ENV_CD}_${ENV_NO}/scripts/ --recursive --sse aws:kms --sse-kms-key-id alias/fnma/app/fre01
   aws s3 cp ${path}/dataFiles/scripts/ s3://${CUR_EDL_BUCKET}/config/app/mrpdata/${ENV_CD}_${ENV_NO}/scripts/ --recursive --sse aws:kms --sse-kms-key-id alias/fnma/app/fre01

   echo aws s3 cp ${path}/dataFiles/deploy/ s3://${CUR_EDL_BUCKET}/deploy/app/mrpdata/${ENV_CD}_${ENV_NO}/ --recursive --sse aws:kms --sse-kms-key-id alias/fnma/app/fre01
   aws s3 cp ${path}/dataFiles/deploy/ s3://${CUR_EDL_BUCKET}/deploy/app/mrpdata/${ENV_CD}_${ENV_NO}/ --recursive --sse aws:kms --sse-kms-key-id alias/fnma/app/fre01
fi

if [[ ""${ACTIONS}"" == *"CopyMigrationPkg"* ]]
then
   echo ""
   echo "Sending migration package ot next environment ..."

   #copy zips to next environment
   echo "NEXT source bucket="${NEXT_SOURCE_BUCKET}
   if [[ ${#NEXT_SOURCE_BUCKET} -ne 0 ]] && [[ ${#PROMOTE_VERSION} -ne 0 ]]
   then
      if [ "${Environment}" == "devl-edl" ]
      then
         echo aws s3 cp s3://${CUR_SOURCE_BUCKET}/app/mrpdata/source/${BATCH_SOURCE_ENV}/data_migration/ s3://${NEXT_SOURCE_BUCKET}/app/mrpdata/candidate/${ENV_CD}_${ENV_NO}/${PROMOTE_VERSION}/data_migration/ --recursive  --sse 'AES256' --acl ${ACL}
         aws s3 cp s3://${CUR_SOURCE_BUCKET}/app/mrpdata/source/${BATCH_SOURCE_ENV}/data_migration/ s3://${NEXT_SOURCE_BUCKET}/app/mrpdata/candidate/${ENV_CD}_${ENV_NO}/${PROMOTE_VERSION}/data_migration/ --recursive  --sse 'AES256' --acl ${ACL}
      else
         echo aws s3 cp s3://${CUR_SOURCE_BUCKET}/app/mrpdata/candidate/${BATCH_SOURCE_ENV}/data_migration/ s3://${NEXT_SOURCE_BUCKET}/app/mrpdata/candidate/${ENV_CD}_${ENV_NO}/${PROMOTE_VERSION}/data_migration/ --recursive  --sse 'AES256' --acl ${ACL}
         aws s3 cp s3://${CUR_SOURCE_BUCKET}/app/mrpdata/candidate/${BATCH_SOURCE_ENV}/data_migration/ s3://${NEXT_SOURCE_BUCKET}/app/mrpdata/candidate/${ENV_CD}_${ENV_NO}/${PROMOTE_VERSION}/data_migration/ --recursive  --sse 'AES256' --acl ${ACL}
      fi
   fi
fi

if [[ ""${ACTIONS}"" == *"ddl-to-glue"* ]]
then
   echo ""
   echo "Running ddl to create tables in glue ..."

   #copy zips to next environment
   echo "NEXT source bucket="${NEXT_SOURCE_BUCKET}
   if [[ ${#NEXT_SOURCE_BUCKET} -ne 0 ]] && [[ ${#PROMOTE_VERSION} -ne 0 ]]
   then
      echo aws s3 rm s3://${NEXT_SOURCE_BUCKET}/app/mrpdata/candidate/${ENV_CD}_${ENV_NO}/${PROMOTE_VERSION}/ddl-to-glue --recursive
      aws s3 rm s3://${NEXT_SOURCE_BUCKET}/app/mrpdata/candidate/${ENV_CD}_${ENV_NO}/${PROMOTE_VERSION}/ddl-to-glue --recursive
      if [ "${Environment}" == "devl-edl" ]
      then
         echo aws s3 cp s3://${CUR_SOURCE_BUCKET}/app/mrpdata/source/${BATCH_SOURCE_ENV}/ddl-to-glue/ s3://${NEXT_SOURCE_BUCKET}/app/mrpdata/candidate/${ENV_CD}_${ENV_NO}/${PROMOTE_VERSION}/ddl-to-glue/ --recursive  --sse 'AES256' --acl ${ACL}
         aws s3 cp s3://${CUR_SOURCE_BUCKET}/app/mrpdata/source/${BATCH_SOURCE_ENV}/ddl-to-glue/ s3://${NEXT_SOURCE_BUCKET}/app/mrpdata/candidate/${ENV_CD}_${ENV_NO}/${PROMOTE_VERSION}/ddl-to-glue/ --recursive  --sse 'AES256' --acl ${ACL}
      else
         echo aws s3 cp s3://${CUR_SOURCE_BUCKET}/app/mrpdata/candidate/${BATCH_SOURCE_ENV}/ddl-to-glue/ s3://${NEXT_SOURCE_BUCKET}/app/mrpdata/candidate/${ENV_CD}_${ENV_NO}/${PROMOTE_VERSION}/ddl-to-glue/ --recursive  --sse 'AES256' --acl ${ACL}
         aws s3 cp s3://${CUR_SOURCE_BUCKET}/app/mrpdata/candidate/${BATCH_SOURCE_ENV}/ddl-to-glue/ s3://${NEXT_SOURCE_BUCKET}/app/mrpdata/candidate/${ENV_CD}_${ENV_NO}/${PROMOTE_VERSION}/ddl-to-glue/ --recursive  --sse 'AES256' --acl ${ACL}
      fi
   fi

   #get java utility from s3 source bucket
   cd dataFiles/ddl-to-glue

   if [ "${Environment}" == "devl-edl" ]
   then
      echo aws s3 cp s3://${CUR_SOURCE_BUCKET}/app/mrpdata/source/${BATCH_SOURCE_ENV}/ddl-to-glue/ddl-to-glue.zip .
      aws s3 cp s3://${CUR_SOURCE_BUCKET}/app/mrpdata/source/${BATCH_SOURCE_ENV}/ddl-to-glue/ddl-to-glue.zip .
   else
      echo aws s3 cp s3://${CUR_SOURCE_BUCKET}/app/mrpdata/candidate/${BATCH_SOURCE_ENV}/ddl-to-glue/ddl-to-glue.zip .
      aws s3 cp s3://${CUR_SOURCE_BUCKET}/app/mrpdata/candidate/${BATCH_SOURCE_ENV}/ddl-to-glue/ddl-to-glue.zip .
   fi
   
   unzip -q ddl-to-glue.zip
   echo $PWD":"
   ls
   echo "./ddl-to-glue/:"
   ls ddl-to-glue/
   chmod -R +x ddl-to-glue/
   export ABSOLUTEPATH=$PWD
   echo "ABSOLUTEPATH="$ABSOLUTEPATH
   echo "TERM="${TERM}
   echo "saml properties:"
   cat ./ddl-to-glue/conf/saml.properties
   echo "spark properties:"
   cat ./ddl-to-glue/conf/spark-conf.properties

   echo ""
   echo "Checking databases..."
   aws glue get-database --name fre01_${ENV_CD}edl_app_mrp_isgt_${ENV_NO}
   if [ $? -eq 0 ]
   then
        echo S3 igst db exist
   else
        echo aws glue create-database --database-input Name=fre01_${ENV_CD}edl_app_mrp_isgt_${ENV_NO},Description=fre01-${ENV_CD}-${ENV_NO},LocationUri=s3://${CUR_EDL_BUCKET}/insight/cin/dflt/hive/${ENV_CD}_${ENV_NO}/warehouse/
        aws glue create-database --database-input Name=fre01_${ENV_CD}edl_app_mrp_isgt_${ENV_NO},Description=fre01-${ENV_CD}-${ENV_NO},LocationUri=s3://${CUR_EDL_BUCKET}/insight/cin/dflt/hive/warehouse/
   fi

   aws glue get-database --name fre01_${ENV_CD}edl_app_mrp_prep_${ENV_NO}
   if [ $? -eq 0 ]
   then
        echo s3 prep db exist
   else
        echo aws glue create-database --database-input Name=fre01_${ENV_CD}edl_app_mrp_prep_${ENV_NO},Description=fre01-${ENV_CD}-${ENV_NO},LocationUri=s3://${CUR_EDL_BUCKET}/insight/cin/dflt/hive/${ENV_CD}_${ENV_NO}/warehouse/
        aws glue create-database --database-input Name=fre01_${ENV_CD}edl_app_mrp_prep_${ENV_NO},Description=fre01-${ENV_CD}-${ENV_NO},LocationUri=s3://${CUR_EDL_BUCKET}/insight/cin/dflt/hive/warehouse/
   fi

   aws glue get-database --name fre01_${ENV_CD}edl_app_mrp_land_${ENV_NO}
   if [ $? -eq 0 ]
   then
        echo S3 land db exist
   else
        echo aws glue create-database --database-input Name=fre01_${ENV_CD}edl_app_mrp_land_${ENV_NO},Description=fre01-${ENV_CD}-${ENV_NO},LocationUri=s3://${CUR_EDL_BUCKET}/insight/cin/dflt/hive/${ENV_CD}_${ENV_NO}/warehouse/
        aws glue create-database --database-input Name=fre01_${ENV_CD}edl_app_mrp_land_${ENV_NO},Description=fre01-${ENV_CD}-${ENV_NO},LocationUri=s3://${CUR_EDL_BUCKET}/insight/cin/dflt/hive/warehouse/
   fi

   echo ""
   echo "Executing scripts..."
   export GLUE_DDL_SCRIPTS="1CMDS_CLOUD_STG_XFRM_TABLES_DDL.sql,1CMDS_CLOUD_REPOSITORY_TABLES_DDL.sql,1CMBI_CLOUD_REPOSITORY_TABLES_DDL.sql,1land_tables_ddl_for_cmbi.sql,1land_tables_ddl_for_cmds.sql"
#   export GLUE_DDL_SCRIPTS="1DDL.sql,2DDL.sql"
   cat ./ddl-to-glue/conf/spark-conf.properties | sed 's/${GLUE_DDL_SCRIPTS}/'${GLUE_DDL_SCRIPTS}'/g' > ./ddl-to-glue/conf/spark-conf1.properties
   cp ./ddl-to-glue/conf/spark-conf1.properties ./ddl-to-glue/conf/spark-conf.properties

   cat CMDS_CLOUD_STG_XFRM_TABLES_DDL.sql | sed 's/${ENV_CD}/'${ENV_CD}'/g' | sed 's/_${ENV_NO}/_'${ENV_NO}'/g' > 1CMDS_CLOUD_STG_XFRM_TABLES_DDL.sql
   cat CMDS_CLOUD_REPOSITORY_TABLES_DDL.sql | sed 's/${ENV_CD}/'${ENV_CD}'/g' | sed 's/_${ENV_NO}/_'${ENV_NO}'/g' > 1CMDS_CLOUD_REPOSITORY_TABLES_DDL.sql
   cat CMBI_CLOUD_REPOSITORY_TABLES_DDL.sql | sed 's/${ENV_CD}/'${ENV_CD}'/g' | sed 's/_${ENV_NO}/_'${ENV_NO}'/g' > 1CMBI_CLOUD_REPOSITORY_TABLES_DDL.sql
   cat land_tables_ddl_for_cmds.sql | sed 's/${ENV_CD}/'${ENV_CD}'/g' | sed 's/_${ENV_NO}/_'${ENV_NO}'/g' > 1land_tables_ddl_for_cmds.sql
   cat land_tables_ddl_for_cmbi.sql | sed 's/${ENV_CD}/'${ENV_CD}'/g' | sed 's/_${ENV_NO}/_'${ENV_NO}'/g' > 1land_tables_ddl_for_cmbi.sql

   #cp 1CMDS_CLOUD_STG_XFRM_TABLES_DDL.sql CMDS_CLOUD_STG_XFRM_TABLES_DDL.sql
   #cp 1CMDS_CLOUD_REPOSITORY_TABLES_DDL.sql CMDS_CLOUD_REPOSITORY_TABLES_DDL.sql
   #cp 1CMBI_CLOUD_REPOSITORY_TABLES_DDL.sql CMBI_CLOUD_REPOSITORY_TABLES_DDL.sql
   #cp 1land_tables_ddl_for_cmds.sql land_tables_ddl_for_cmds.sql
   #cp 1land_tables_ddl_for_cmbi.sql land_tables_ddl_for_cmbi.sql

#   ls -al 1land_tables_ddl_for_cmbi.sql
#   cat 1land_tables_ddl_for_cmbi.sql

#   cat MRP_CREATE_DATABASE_S3.sql
#   cat testDDL2.sql | sed 's/_${ENV_CD}/_'${ENV_CD}'/g' | sed 's/_${ENV_NO}/_'${ENV_NO}'/g' > 2DDL.sql
#   cp 2DDL.sql testDDL1.sql

   cat ./ddl-to-glue/conf/spark-conf.properties | grep file.sequence
   echo ""
   echo Executing ./ddl-to-glue/bin/run_utility.sh $ABSOLUTEPATH $ABSOLUTEPATH
   ./ddl-to-glue/bin/run_utility.sh $ABSOLUTEPATH $ABSOLUTEPATH > ddlGlue.log

   #copy log for reference
   echo aws s3 cp ddlGlue.log s3://${CUR_SOURCE_BUCKET}/app/mrpdata/deployed/${ENV_CD}_${ENV_NO}/ddlGlue${curdt}.log --sse "AES256"
   aws s3 cp ddlGlue.log s3://${CUR_SOURCE_BUCKET}/app/mrpdata/deployed/${ENV_CD}_${ENV_NO}/ddlGlue${curdt}.log --sse "AES256"
fi

if [[ ""${ACTIONS}"" == *"glueAdhocScript"* ]]
then
   echo ""
   echo "Running adhoc script for glue..."

   if [ "${Environment}" == "devl-edl" ]
   then
      echo aws s3 cp s3://${CUR_SOURCE_BUCKET}/app/mrpdata/source/${BATCH_SOURCE_ENV}/ddl-to-glue/ddl-to-glue.zip .
      aws s3 cp s3://${CUR_SOURCE_BUCKET}/app/mrpdata/source/${BATCH_SOURCE_ENV}/ddl-to-glue/ddl-to-glue.zip .
   else
      echo aws s3 cp s3://${CUR_SOURCE_BUCKET}/app/mrpdata/candidate/${BATCH_SOURCE_ENV}/ddl-to-glue/ddl-to-glue.zip .
      aws s3 cp s3://${CUR_SOURCE_BUCKET}/app/mrpdata/candidate/${BATCH_SOURCE_ENV}/ddl-to-glue/ddl-to-glue.zip .
   fi
   unzip -q ddl-to-glue.zip
   chmod -R +x ddl-to-glue/

   echo "Downloading S3_SOURCE_SCRIPT="${S3_SOURCE_SCRIPT}
   echo aws s3 cp ${S3_SOURCE_SCRIPT} DDLScript.sql
   aws s3 cp ${S3_SOURCE_SCRIPT} DDLScript.sql
   ls
   export GLUE_DDL_SCRIPTS=DDLScript.sql
   cat ./ddl-to-glue/conf/spark-conf.properties | sed 's/${GLUE_DDL_SCRIPTS}/'${GLUE_DDL_SCRIPTS}'/g' > ./ddl-to-glue/conf/spark-conf1.properties
   cp ./ddl-to-glue/conf/spark-conf1.properties ./ddl-to-glue/conf/spark-conf.properties
   
   echo Executing ./ddl-to-glue/bin/run_utility.sh $PWD $PWD
   ./ddl-to-glue/bin/run_utility.sh $PWD $PWD
fi

#########
#3. Package CF template to deploy in current environment
echo "sending template ..."
#rm -r ${path}/dataFiles/batch/
cd ${path}
aws cloudformation package --template-file MRP-Build-CF.yml --s3-bucket ${ARTIFACTS_BUCKET} --output-template-file New-MRP-Build-CF.yml

#Create s3 triggers
#aws s3api put-bucket-notification-configuration --bucket fnma-fre01-devl-edl-us-east-1-edl --notification-configuration file://buildscripts/s3_triggers-devl.json
#aws s3api put-bucket-notification-configuration --bucket fnma-fre01-acpt-edl-us-east-1-edl --notification-configuration file://buildscripts/s3_triggers-acpt.json
#aws s3api put-bucket-notification-configuration --bucket fnma-fre01-prod-edl-us-east-1-edl --notification-configuration file://buildscripts/s3_triggers-prod.json
#
#pipeline update
#aws codepipeline get-pipeline --name #pipeline-name > devl-pl.json
#remote metadata section from devl-pl.json
#aws codepipeline update-pipeline --cli-input-json file://devl-pl.json
