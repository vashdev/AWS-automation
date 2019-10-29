import json
import os
import sys
import datetime
import re
import csv
import urllib
import time
import psycopg2
import boto3
import string
from io import StringIO
from epv import PasswordVault
from constants import edcMsg
from dbconn import getCredential,getconn
import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
sqsclient=boto3.client('sqs')


def lambda_handler(event,context):

    frepv=PasswordVault(os.environ['PAM_APP_CD'],os.environ['PAM_ENV_CD'],os.environ['PAM_OBJ_REF'])
    REDSHIFT_DATABASE = os.environ['CMDS_DATABASE']
    REDSHIFT_USER = frepv.getAccount()
    REDSHIFT_PASSWD = frepv.getPassword()
    REDSHIFT_PORT = os.environ['CMDS_PORT']
    REDSHIFT_ENDPOINT=os.environ['CMDS_ENDPOINT']
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    dt = datetime.datetime.now()
    logger.info(json.dumps(event))
    conn=None
    try:
       conn=getconn(os.environ['CMDS_DATABASE'],frepv.getAccount(),frepv.getPassword(),os.environ['CMDS_PORT'],os.environ['CMDS_ENDPOINT'],os.environ['CMDS_SCHEMA'])
       logger.info(' Process Success Event ')
       batchid=str(event['configData']['batch_job_id'])  
       logstream=event['batchResult']['Container']['LogStreamName'] 
       loadtblupdt=" update t_load_log set status=%s, file_url=%s , end_ts=%s where seq=%s" 
       cursor = conn.cursor()
       cursor.execute("begin transaction")
       cursor.execute(loadtblupdt,('Completed',logstream,datetime.datetime.now(), batchid))
       cursor.execute("end transaction")
       # EDC Processing
       if event['configData']['configurationId'] in ['mrp_datamart_manifest']:
           # load is performed on manifest Job ID
           l= event['configData']['objkey'].split("/")
           m= [x for x in l if '.manifest' in x]
           batchid = str(re.findall(r'\d+',m[0]))
           logger.info(" batch id from manifest {}".format(batchid))
       cursor.close()
       conn.commit()
       # EDC
       try:
           sendEdcMsg(conn,batchid)
       except:
           logger.error("Execution Issue: EDC message Failed No Alerts for EDC  failures" )
    except Exception as ERROR:
        logger.error("Execution Issue: " )
        logger.error( ERROR)
        if conn is not None:
           conn.close()
           exit(1)
    finally:
       if conn is not None:
          conn.close()

 
def sendEdcMsg(conn,batchid):
        logger.info( " EDC message processing ")
        Dataset_ID=""
        Bucket_Name="fnma-fre01-"+os.environ['APP_ENV_CD']+"-edl-us-east-1-edl"
        Member_Key_Prefix=""
        ENT_DATA_CATALOG_URL="https://sqs.us-east-1.amazonaws.com/"+os.environ['ACCOUNT_NUM']+"/fdc03-us-east-1-devl-Applications-operational-messages.fifo"
        edcQuery="select  tgt_tab, records_written,location,partition_key,end_ts from  t_load_log join svv_external_partitions on upper(tgt_tab)=upper(tablename) where partition_key is not null and status='Completed' and load_seconds is null and records_written > 0 and data_load_aud_log_id ="+batchid+" and values like '%"+batchid +"%'"
        edcQuery=edcQuery+"and schemaname='fre01_"+os.environ['APP_ENV_CD']+"edl_app_mrp_isgt_"+os.environ['APP_ENV_NO']+"'"
        dsetExpn=re.compile(r'DSET[0-9]+')
        pat = re.compile(r'\s+')
        edcCursor = conn.cursor()
        edcCursor.execute(edcQuery)
        if(edcCursor.rowcount>0):
            logger.info("row count=="+str(edcCursor.rowcount))
            count=0
            for row in edcCursor:
                count+=1
                (tbl,total,loc,pk,ts)=row
                Dataset_ID=dsetExpn.findall(loc)[0]
                mkey=("/insight/cin/dflt/mrpdata/"+os.environ['APP_ENV_CD']+"_"+os.environ['APP_ENV_NO']+"/"+Dataset_ID+"/"+tbl+"/"+("/".join(pk.split(","))))
                edcMsg['Bucket_Name']= loc.split('/')[2]
                edcMsg['Dataset_ID']=Dataset_ID
                edcMsg['Member_Key_Prefix']=(mkey.replace("'","")).replace(" ","")
                edcMsg['Member_File_Count']="1"
                edcMsg['Member_Record_Count']=total
                edcMsg['Member_Size']=""
                edcMsg['Instance_Group']="2018_Jan, 2018_Q1"
                edcMsg['Message_DML_Type']="INSERT"
                edcMsg['Dataset_Version']=""
                edcMsg['Control_Totals']=''
                edcMsg['Comments']="fre01 MRPDATA Insight datasets"
                edcMsg['Additional_Operational_Metadata']="contact=L2-ERMRISKSUPP@fanniemae.com"
                edcMsg['Ingest_Timestamp']=str(ts)
                logger.info(edcMsg)
                dt = datetime.datetime.now()
                sqsclient.send_message(
                        QueueUrl=os.environ['ENT_DATA_CATALOG_QUEUE_URL'],
                        MessageBody=json.dumps(edcMsg,indent=2),
                        MessageGroupId="MRPDATA-"+os.environ['APP_ENV_CD']+'_'+os.environ['APP_ENV_NO'],
                        MessageDeduplicationId=str(batchid)+"-"+str(dt).replace(" ","")
                                   )
                
                
               
                
        logger.info(" EDC Message end")        
        edcCursor.close()        
        
        return 'Success' 
    
         

        
if __name__ == "__main__":
    successevent={"Attempts": [{"Container": {"ContainerInstanceArn": "arn:aws:ecs:us-east-1:742458541136:container-instance/7a6f3712-e9ff-4d8a-8c44-bdf7fb651b0f","ExitCode": 0,"LogStreamName": "fre01-mrpdata-valuation-pvr/default/8fab1921-ffac-47db-b008-1a274833ecc0","TaskArn": "arn:aws:ecs:us-east-1:742458541136:task/8fab1921-ffac-47db-b008-1a274833ecc0"},"StartedAt": 1546390014351,"StatusReason": "Essential container in task exited","StoppedAt": 1546390747259}],"Container": {"Command": ["Valuation_Launcher/Valuation_Launcher_run.sh","--context_param","JOB_PRIMA_MANIFEST_FILE_KEY_PREFIX=land/cin/dflt/prima/devl_01/DSET00000000/valuation/pvr/20190101194618047.PRIMA000.PVR00000.manifest","--context_param","BATCH_JOB_ID=1546389987604943725"],"ContainerInstanceArn": "arn:aws:ecs:us-east-1:742458541136:container-instance/7a6f3712-e9ff-4d8a-8c44-bdf7fb651b0f","Environment": [{"Name": "BATCH_FILE_S3_URL","Value": "s3://fnma-fre01-devl-edl-us-east-1-edl/deploy/app/mrpdata/devl_01/batch/Valuation_Launcher_0.1.zip"},{"Name": "APP_ENV_NO","Value": "01"},{"Name": "APP_ENV_CD","Value": "devl"},{"Name": "MANAGED_BY_AWS","Value": "STARTED_BY_STEP_FUNCTIONS"},{"Name": "BATCH_FILE_TYPE","Value": "zip"},{"Name": "SPARK_LOCAL_IP","Value": "localhost"}],"ExitCode": 0,"Image": "742458541136.dkr.ecr.us-east-1.amazonaws.com/fre01-mrp-devl-ecr-repository:mrp-fetch-and-run-java8","JobRoleArn": "arn:aws:iam::742458541136:role/fnma-fre01-devl-edl-instance-role-edl","LogStreamName": "fre01-mrpdata-valuation-pvr/default/8fab1921-ffac-47db-b008-1a274833ecc0","Memory": 14000,"MountPoints": [],"TaskArn": "arn:aws:ecs:us-east-1:742458541136:task/8fab1921-ffac-47db-b008-1a274833ecc0","Ulimits": [],"Vcpus": 4,"Volumes": []},"CreatedAt": 1546389988869,"DependsOn": [],"JobDefinition": "arn:aws:batch:us-east-1:742458541136:job-definition/fre01-mrpdata-valuation-pvr:6","JobId": "8c6aad5c-a95c-40f4-bd98-e4892731a6a7","JobName": "fre01-mrpdata-Valuation-PVR-1546389987604943725","JobQueue": "arn:aws:batch:us-east-1:742458541136:job-queue/fre01-talend-job-queue","Parameters": {"manifest": "JOB_PRIMA_MANIFEST_FILE_KEY_PREFIX=land/cin/dflt/prima/devl_01/DSET00000000/valuation/pvr/20190101194618047.PRIMA000.PVR00000.manifest","external_id": "dlfin-ap151:8010:gausuj:60497:15116","dmr_load_id": "U","valuationType": "PRiMA Valuation Run","batch_job_id": "BATCH_JOB_ID=1546389987604943725"},"RetryStrategy": {"Attempts": 2},"StartedAt": 1546390014351,"Status": "SUCCEEDED","StatusReason": "Essential container in task exited","StoppedAt": 1546390747259,"Timeout": {"AttemptDurationSeconds": 1200}}
    failevent={   "Error": "States.TaskFailed",  "Cause": "{\"Attempts\":[{\"Container\":{\"ContainerInstanceArn\":\"arn:aws:ecs:us-east-1:742458541136:container-instance/7a6f3712-e9ff-4d8a-8c44-bdf7fb651b0f\",\"ExitCode\":4,\"LogStreamName\":\"BatchsyncTestFailDef/default/412ec0f2-9f20-4758-955c-31cdfba66c28\",\"TaskArn\":\"arn:aws:ecs:us-east-1:742458541136:task/412ec0f2-9f20-4758-955c-31cdfba66c28\"},\"StartedAt\":1545128832047,\"StatusReason\":\"Essential container in task exited\",\"StoppedAt\":1545128835206}],\"Container\":{\"Command\":[\"BatchsyncTestFail/BatchsyncTestFail_run.sh\"],\"ContainerInstanceArn\":\"arn:aws:ecs:us-east-1:742458541136:container-instance/7a6f3712-e9ff-4d8a-8c44-bdf7fb651b0f\",\"Environment\":[{\"Name\":\"BATCH_FILE_S3_URL\",\"Value\":\"s3://fnma-fre01-devl-edl-us-east-1-edl/deploy/app/mrpdata/devl_01/batch/BatchsyncTestFail_0.1.zip\"},{\"Name\":\"MANAGED_BY_AWS\",\"Value\":\"STARTED_BY_STEP_FUNCTIONS\"},{\"Name\":\"BATCH_FILE_TYPE\",\"Value\":\"zip\"},{\"Name\":\"SPARK_LOCAL_IP\",\"Value\":\"localhost\"}],\"ExitCode\":4,\"Image\":\"742458541136.dkr.ecr.us-east-1.amazonaws.com/fre01-mrp-devl-ecr-repository:mrp-fetch-and-run-java8\",\"JobRoleArn\":\"arn:aws:iam::742458541136:role/fnma-fre01-devl-edl-instance-role-edl\",\"LogStreamName\":\"BatchsyncTestFailDef/default/412ec0f2-9f20-4758-955c-31cdfba66c28\",\"Memory\":1024,\"MountPoints\":[],\"TaskArn\":\"arn:aws:ecs:us-east-1:742458541136:task/412ec0f2-9f20-4758-955c-31cdfba66c28\",\"Ulimits\":[],\"Vcpus\":1,\"Volumes\":[]},\"CreatedAt\":1545128829886,\"DependsOn\":[],\"JobDefinition\":\"arn:aws:batch:us-east-1:742458541136:job-definition/BatchsyncTestFailDef:2\",\"JobId\":\"e9001881-f056-4e64-a64b-5f44a2ae5395\",\"JobName\":\"fre01-mrpdata-PVRVALNCLOUD-1545128829756819843\",\"JobQueue\":\"arn:aws:batch:us-east-1:742458541136:job-queue/fre01-talend-job-queue\",\"Parameters\":{\"manifest\":\"JOB_PRIMA_EPL_MANIFEST_FILE_KEY_PREFIX=key\",\"batch_job_id\":\"BATCH_JOB_ID=1545128829756819843\"},\"StartedAt\":1545128832047,\"Status\":\"FAILED\",\"StatusReason\":\"Essential container in task exited\",\"StoppedAt\":1545128835206}" }
    context = []
    lambda_handler(successevent, context)
