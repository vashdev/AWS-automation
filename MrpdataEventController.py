'''
Lambda to pocess MRP Data Events
MrpEvents, Has list of configurationId's the lambda can digest
EventMapper, Has fucntions that can parse same event type in differnt ways based on ConfigurationId , and send relevant data  back to caller 
MrpdataEventController, is the main lambda that reacts to an event and populates a json that can be passed to batch jobs and step fucntions. 
StateData, Json structure remains same for all events 
Inputs:  
        JOB_CONFIG_LIST_NM  S3 path for Jobs runtime parrameters
        Event               aws events
        SQS Events: EDI and  portfolio Combiner
Output:
    Trigger relavent statemachin, StateMAchineArn
'''

import json
import os
import re
import sys
import datetime
import csv
import time
from urllib.parse import unquote
import boto3
from botocore.client import Config
import logging
import EventMapper 
import MrpEvents
from datetime import date, timedelta                                    
''' from Mrpdataconstants import stateMachineData  '''
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    
          
    try:
        
        ''' Set common variables and build persistant json for batch job to use  '''  
        on_hold='false'
        logger.info('got scheduled event {}  '.format(event))
        batch_job_id=time.time_ns()
        app_env_cd = os.environ['APP_ENV_CD'] 
        app_env_no = os.environ['APP_ENV_NO']
        app_aws_account =os.environ['ACCOUNT_NO']
        app_mrpdata_joblist_bucket_name= "fnma-fre01-" + app_env_cd + "-edl-us-east-1-edl"
        app_mrpdata_joblist_object_key = "config/app/mrpdata/" + app_env_cd + "_" +app_env_no + "/" + os.environ['MRP_BATCH_JOB_DEF_LIST']
        queue_url='https://sqs.us-east-1.amazonaws.com/'+os.environ['ACCOUNT_NO']+"/"+os.environ['AWS_SQS_QUEUE_NM']
        stateData={ 'batch_job_id' : '','app_env_cd' : '','app_env_no' : '','app_aws_account' : '','jobQueue':'', 'jobDefinition':'','configurationId' : '','objkey':'','sqsMsg':'','QueueUrl':'','jobName':'', 'jobparameters':'', 'ContainerOverrides': {'Vcpus':'','Memory':'', 'Command':'',"Environment": [                   {                      "Name": "SPARK_LOCAL_IP",                      "Value": ""                   },                   {                      "Name": "BATCH_FILE_S3_URL",                      "Value": ""                   },                   {                      "Name": "BATCH_FILE_TYPE",                      "Value": "" },   {"Name": "BATCH_LIB_S3_URL","Value": ""  } ]    },'attempts':'','stateMachineJobExecutionArn':'','stateMachineJobExecutionName':'', 'EventName':'', 'EntityName':'','portfolio_date':''}
        logger.info(' Start with clean slate {}'+json.dumps(stateData))
        stateData.update({'app_env_cd':app_env_cd,
                    'batch_job_id':str(batch_job_id),
                   'app_env_no':app_env_no,
                   'app_aws_account':app_aws_account,
                   'jobQueue':os.environ['AWS_BATCH_JOB_QUEUE_NAME'],
                   'QueueUrl':queue_url,
                   'jobDefinition':os.environ['AWS_BATCH_JOB_DEF_TEMPLATE_30']
        })
        
        # Parse Event and populate stateData    
        get_event_parameters(event,stateData)  
                 
        # Parse Job Definitions and get matching Job parameters  and populate stateData- MSTR event is used ot trigger step function it dosent have batch job component
        if stateData['configurationId']!='mstr' :
            get_job_details(event,app_mrpdata_joblist_bucket_name, app_mrpdata_joblist_object_key,stateData)
            logger.info('Final Json  {}  '.format(stateData))
            if stateData['onhold']=='true':
               logger.info( "Job On Hold- use above json in step fucntion to run this instance")
               return 'on Hold'
        # Trigger the Workflow 
        InitialPayLoad={"configData":stateData}
        step_client = boto3.client('stepfunctions')
        response = step_client.start_execution(
            stateMachineArn=stateData['stateMachineJobExecutionArn'],
            name=stateData['stateMachineJobExecutionName'][:80],
            input= json.dumps(InitialPayLoad)
            )
        logger.info(' Started ...'+ stateData['stateMachineJobExecutionName'][:80] + ' with Payload ')
        return 'Success'

    except  : 
        logErrorEMMAlert("Controller lambda failed to process Event in lambda_handler","lambda_handler")
        raise 
 
                
def get_event_parameters(event,stateData):
    try:
           
        eventType=get_event_type(event)
        if eventType=='aws:s3':
           get_s3_event_params(event,stateData)
        elif(eventType=='aws.events'):
            get_cw_event_params(event,stateData)
        elif(eventType=='aws:sqs'):
            get_sqs_event_params(event,stateData)
        elif(eventType=='aws:sns'):
            get_sns_event_params(event,stateData)
        else:
             logError("Unsupported Aws event ","get_event_parameters")
             exit(1)
    except :
           logError("Failed to Process request  ", "get_event_parameters")
           raise
 
def get_sns_event_params(event,stateData):
    records = event.get('Records') or event.get('records') or []
    msgKeys={ }
    for rec in records:
        msgKeys=getEventAndEntityName(rec)
        stateData['EventName']=msgKeys['EventName']
        stateData['EntityName']=msgKeys['EntityName']
        # Perform Event Specific logic 
        try:
            print ( "list element ot check "+msgKeys['EntityName'])
            if msgKeys['EventName'] in MrpEvents.mrpPortfolioSourceEventDict:
                logger.info("MRP Matching EDI Event Found" +msgKeys['EventName']  )
                ep = EventMapper.SNSEventParser('edisource', rec,msgKeys['EventName'],msgKeys['EntityName'])
                parserResult=ep.source_to_key()
                set_edi_event_jobParameters(stateData,parserResult)
            elif msgKeys['EntityName'] in MrpEvents.mrpAmtmEventEntityList:
                logger.info("MRP Matching AMTM Event Found" +msgKeys['EventName']  )
                ep = EventMapper.SNSEventParser('amtm_source', rec,msgKeys['EventName'],msgKeys['EntityName'])
                parserResult=ep.source_to_key()
                set_amtm_event_jobParameters(stateData,parserResult)
                
            else :
                 logError("Unsupported Aws event EventName/EntityName found in  ","get_sns_event_params")
                 exit(2)
        except :
            logError( 'Error Processing request  ','get_sns_event_params')
            raise
# AMTM and EDI has different Names for event and entity ... Values can be Stringvalue or value ...
def getEventAndEntityName(event):
    rdict={}
    for k, v in event.items():
        if(v is None):
            return 'InvalidValues'
        if isinstance(v,dict):
            if(k=='EventName' or  k=='EventType'):
                if 'stringValue' in v :
                    value=v['stringValue'].strip() 
                if 'Value' in v:
                    value=v['Value'].strip() 
                rdict.update({'EventName':value})
            if(k=='EntityName' or  k=='EntityType'):
                print("Entity Name")
                if 'stringValue' in v :
                    value=v['stringValue'].strip() 
                if 'Value' in v:
                    value=v['Value'].strip() 
                rdict.update({'EntityName':value})
            if( len(rdict)==2):
                print(rdict)
                return rdict
            val = getEventAndEntityName(v)
            if val is not None:
                return val
   

 
    
def get_job_details(event,app_mrpdata_joblist_bucket_name, app_mrpdata_joblist_object_key,stateData):

        """ Read Job Definitions from S3 Config get Job Definition Parameters for matching source event ConfigurationId """
        s3client=boto3.client('s3',config=Config(signature_version='s3v4'))
        Obj = s3client.get_object(Bucket=app_mrpdata_joblist_bucket_name, Key=app_mrpdata_joblist_object_key)
        jobStream=Obj['Body'].read().decode('utf-8')
        jdefs=json.loads(jobStream)
        _isJobExists=0
        logger.info('Job definition for  , '+stateData['configurationId'])
        for jobdefConfigId, jobdetail in jdefs.items():

                
            if(jobdefConfigId==stateData['configurationId']):
                 _isJobExists=1
                 jobdetails=dict(jobdetail)
                 stateData.update({"onhold":jobdetails['on_hold']})
                 stateData['ContainerOverrides']['Command']=jobdetails['command'].split()
                 stateData['ContainerOverrides']['Vcpus']=jobdetails['vcpus']
                 stateData['ContainerOverrides']['Memory']=jobdetails['memory']
                 stateData['ContainerOverrides']['Environment'][1]['Value']='s3://'+app_mrpdata_joblist_bucket_name+'/deploy/app/mrpdata/'+os.environ['APP_ENV_CD']+'_'+os.environ['APP_ENV_NO']+'/batch/'+jobdetails['batch_file_name']
                 stateData['ContainerOverrides']['Environment'][3]['Value']='s3://'+app_mrpdata_joblist_bucket_name+'/deploy/app/mrpdata/'+os.environ['APP_ENV_CD']+'_'+os.environ['APP_ENV_NO']+'/batch/'+'talend_lib.zip'
                 stateData['ContainerOverrides']['Environment'][2]['Value']=jobdetails['batch_file_type']
                 stateData['ContainerOverrides']['Environment'][0]['Value']=jobdetails['spark_local_ip']
                 stateData['jobDefinition']=os.environ['AWS_BATCH_JOB_DEF_TEMPLATE_'+str(jobdetails['attemptDurationMin'])]
                 stateData['attempts']=jobdetails['attempts']
                 stateData['DependencyCheckResult']=jobdetails.get('DependencyCheckResult') or ''
                 stateData['DependencyCheckSql']=jobdetails.get('DependencyCheckSql') or ''
                 stateData['maxIterations']=jobdetails['maxIterations']
                 # events that process multiple requests in one invocation 
                 #stateData['batch_job_id']=str(batch_job_id) 
                 
        if(_isJobExists==0):
            logError(" No matching job definition found ","get_job_details") 
            exit(7)
        return 1


def get_event_type(event):
    """Get Source event type."""
    records = event.get('Records') or event.get('records') or []
    
    if records:
        eventType=dict(
            zip(map(lambda x: str(x).lower(), records[0].keys()), records[0].values())
        ).get('eventsource')
        logger.info(' Event Type : '+ eventType)
    if not records:
       eventType = event.get('source')
    if not eventType:       
       logError("  EventSource not found ","get_job_details")  
       exit(2)
       
    return eventType
    
    
def get_s3_event_params(event,stateData):
    try:
        """ Parse Events and Build StateData JSON based on Config ID for S3"""
        for record in event.get('Records'):
            s3client=boto3.client('s3',config=Config(signature_version='s3v4'))
            s3_bucket_key = record.get('s3', {})
            configurationId=record['s3']['configurationId']
                
            bucket_name, key_name = ( (s3_bucket_key['bucket']['name']), (s3_bucket_key['object']['key']))
            
            logger.info( "fetching file::{}/{} for config Id {}".format(bucket_name, key_name, configurationId))

            # Support multiple sub environments
            if(configurationId.endswith('_01') or configurationId.endswith('_02') or configurationId.endswith('_03')):
                configurationId = configurationId[:-3]
           
            print('configurationId   ='+configurationId)

            stateData['configurationId'] = configurationId
            stateData['objkey']=key_name
            stateData['jobName']='fre01-mrpdata-'+stateData['app_env_cd']+stateData['app_env_no']+'-'+configurationId+'-'+str(stateData['batch_job_id'])
            stateData['sqsMsg']='valType='+stateData['configurationId'] +','+'batchJobId='+str(stateData['batch_job_id'])
            stateData['stateMachineJobExecutionName']='fre01-mrpdata-'+os.environ['APP_ENV_NO']+configurationId+'-'+str(stateData['batch_job_id'])+'-wrkflow'
            
            # Event specific parameter settings 
            if configurationId in  ['mrp_datamart_manifest' ,'mrp_portfolio_datamart_manifest','portfolio_combiner_guaranty']:
                logger.info("Processing  datamart manifest ")
                emap=EventMapper.S3EventParser('datamart_s3',bucket_name,key_name)
                parser=emap.source_to_key()
                logger.info("Manifest Parse Result")
                print(json.dumps(parser,indent=2))
                set_datamart_event_job_params(event, stateData, parser)
            elif(configurationId in (MrpEvents.mrpOtherEventList )):
                set_file_event_job_params(event, stateData)
            elif(configurationId in (MrpEvents.mrpPrimaEventList)):
                # Valuation and EPL common code
                print( 'parse the Manifest  - configiurationId specific ')
                ep=EventMapper.S3EventParser('prima_valuation_s3_manifest',bucket_name,key_name)
                parser=ep.source_to_key()
                set_prima_event_job_params(event, stateData, parser)
            else:
                logError("   S3 config Id  processing Error - unknown configId "+configurationId,"get_job_details")  
                exit(5)
        # exceptions ...exceptions...exceptions ....override Step arn for MF data dpeendency checks and triggering Portfolio
        if configurationId in ['amtm_mf_prices','ccfa_loan_profile','amtm_rpl']:
            stateData['stateMachineJobExecutionArn']=os.environ['PORTFOLIO_DATA_SOURCE_EVENT_STEPFUNC_ARN']
            
        return 'Success'
    except:
        logError("   S3 config Id  processing Exception   "+configurationId,"get_job_details")  
        
def get_s3_event_params_updated(s3event,stateData):

            """ Parse Events and Build StateData JSON based on Config ID for S3"""
            logger.info( " Processing S3 event ...")
            s3client=boto3.client('s3',config=Config(signature_version='s3v4'))
            s3_bucket_key = s3event.get('s3', {})
            configurationId=s3event['s3']['configurationId']
                
            bucket_name, key_name = ( (s3_bucket_key['bucket']['name']), (s3_bucket_key['object']['key']))
            
            logger.info( "fetching file::{}/{} for config Id {}".format(bucket_name, key_name, configurationId))

            # Support multiple sub environments
            if(configurationId.endswith('_01') or configurationId.endswith('_02') or configurationId.endswith('_03')):
                configurationId = configurationId[:-3]
           
            print('configurationId   ='+configurationId)

            stateData['configurationId'] = configurationId
            stateData['objkey']=key_name
            stateData['jobName']='fre01-mrpdata-'+stateData['app_env_cd']+stateData['app_env_no']+'-'+configurationId+'-'+str(stateData['batch_job_id'])
            stateData['sqsMsg']='valType='+stateData['configurationId'] +','+'batchJobId='+str(stateData['batch_job_id'])
            stateData['stateMachineJobExecutionName']='fre01-mrpdata-'+configurationId+'-'+str(stateData['batch_job_id'])+'-wrkflow'
            
            # Event specific parameter settings 
            if configurationId in  ['mrp_datamart_manifest' ,'mrp_portfolio_datamart_manifest','portfolio_combiner_guaranty']:
                logger.info("Processing  datamart manifest /portfolio_combiner_guaranty ")
                emap=EventMapper.S3EventParser('datamart_s3',bucket_name,key_name)
                parser=emap.source_to_key()
                logger.info("Manifest Parse Result")
                print(json.dumps(parser,indent=2))
                set_datamart_event_job_params(s3event, stateData, parser)
            elif(configurationId in (MrpEvents.mrpOtherEventList )):
                set_file_event_job_params(s3event, stateData)
            elif(configurationId in (MrpEvents.mrpPrimaEventList)):
                # Valuation and EPL common code
                print( 'parse the Manifest  - configiurationId specific ')
                ep=EventMapper.S3EventParser('prima_valuation_s3_manifest',bucket_name,key_name)
                parser=ep.source_to_key()
                set_prima_event_job_params(s3event, stateData, parser)
            else:
                logError("S3 config Id  processing Error - unknown configId "+ configurationId , "get_s3_event_params_updated")
            return 'Success'

def set_prima_event_job_params(event, stateData, parser):
        stateData['jobparameters']={"APP_ENV_NO":"APP_ENV_NO="+stateData['app_env_no'],"APP_ENV_CD":"APP_ENV_CD="+stateData['app_env_cd'],"manifest" : "JOB_PRIMA_MANIFEST_FILE_KEY_PREFIX="+ stateData['objkey'],"external_id":parser['external_id'],"dmr_load_id":'dmr_load_id',"configurationId":stateData['configurationId'] , "batch_job_id" : "BATCH_JOB_ID="+str(stateData['batch_job_id'])}
        stateData['stateMachineJobExecutionArn']=os.environ['PRIMA_EVENT_STEPFUNC_ARN']
        return 'Success'

def set_datamart_event_job_params(event, stateData, parser):
        stateData['jobparameters']={"APP_ENV_NO":"APP_ENV_NO="+stateData['app_env_no'],"APP_ENV_CD":"APP_ENV_CD="+stateData['app_env_cd'], "input_file" : "JOB_MANIFEST_FILE_KEY_PREFIX="+ stateData['objkey'], "dataset" : "JOB_DATA_SET="+ parser['DATA_SET'] , "batch_job_id" : "BATCH_JOB_ID="+str(stateData['batch_job_id'])}
        stateData['stateMachineJobExecutionArn']=os.environ['COMMON_EVENT_STEPFUNC_ARN']
        #if stateData['configurationId']=='mrp_portfolio_datamart_manifest':
            #stateData['stateMachineJobExecutionArn']=os.environ['CMBI_STEPFUNC_ARN']
        return 'Success'
        
def set_file_event_job_params(event, stateData):
        stateData['jobparameters']={"APP_ENV_NO":"APP_ENV_NO="+stateData['app_env_no'],"APP_ENV_CD":"APP_ENV_CD="+stateData['app_env_cd'], "input_file" : "JOB_INPUT_FILE_KEY_PREFIX="+ stateData['objkey'], "entity_type" : "JOB_ENTITY_TYPE="+ stateData['configurationId'] , "batch_job_id" : "BATCH_JOB_ID="+str(stateData['batch_job_id'])}
        stateData['stateMachineJobExecutionArn']=os.environ['COMMON_EVENT_STEPFUNC_ARN']
        return 'Success'
def set_scheduled_event_job_params(event, stateData, eventDetails):
        stateData['jobparameters']={"APP_ENV_NO":"APP_ENV_NO="+stateData['app_env_no'],"APP_ENV_CD":"APP_ENV_CD="+stateData['app_env_cd'], "input_file" : "JOB_DATA_SRC="+ stateData['objkey'], "entity_type" : "JOB_ENTITY_TYPE="+ stateData['configurationId'] , "batch_job_id" : "BATCH_JOB_ID="+str(stateData['batch_job_id'])}
        stateData['stateMachineJobExecutionArn']=os.environ['COMMON_EVENT_STEPFUNC_ARN']
        return 'Success'

def get_cw_event_params(event,stateData):
          logger.info(' CloudWatch event processing')
          ep = EventMapper.CWEventParser('cwsource', event)
          parserResult=ep.source_to_key()
          logger.info(json.dumps(parserResult))
          if parserResult['PORTFOLIO_DATE'] == 'sysDate-1':
              parserResult['PORTFOLIO_DATE']=str((datetime.datetime.today() - timedelta(days=1)).strftime('%Y-%m-%d'))
          if parserResult['PORTFOLIO_DATE'] == 'sysDate':
              parserResult['PORTFOLIO_DATE']=str((datetime.datetime.today() - timedelta(days=0)).strftime('%Y-%m-%d'))
          set_cw_event_jobParameters(stateData,parserResult)
           
          return 'success'
 
           
# only Internal portfolio Messages Come to here, EDI has saperate Procedure
def get_sqs_event_params(event,stateData):
                # Handle AMTM
                records = event.get('Records') or event.get('records') or []
                msgAttrs={ }
                msgKeys=''
                # SQS- SNS interfaces 
                for rec in records:
                    #body has json wrapped in string 
                    if not isinstance(rec.get('body'),dict) :
                        
                        # SQS body has   content as string
                        sqsbody = json.loads(rec.get('body'))
                        # get Keys from SQS Body  -AMTM
                        msgAttrs=dict( zip(map(lambda x: str(x).lower(), sqsbody.keys()), sqsbody.values())
                                           ).get('messageattributes')
                        if not msgAttrs  :
                            
                            logger.info(" messageattributes is null Look for S3 event")
                            s3records = sqsbody.get('Records') or sqsbody.get('records') or []
                            for s3rec in s3records:
                                if s3rec.get("eventSource") =="aws:s3":
                                    logger.info(" Processing SQS S3 rec")
                                    get_s3_event_params_updated(s3rec,stateData)
                                    return "Success"
                                
                                 
                            logger.info(" Look for Cloud Watch Events ")
                            if sqsbody.get("Source")=="aws.events" or  sqsbody.get("source")=="aws.events":
                                logger.info(" Processing SQS- CloudWatch Event")
                                get_cw_event_params(sqsbody,stateData)
                                return "Success"
                             
                            logger.info("get keys from record message attributes itself -EDI")                                           
                            msgAttrs=dict( zip(map(lambda x: str(x).lower(), rec.keys()), rec.values())
                                           ).get('messageattributes') 
                        if not msgAttrs :
                            print(" Try parsing SQS body and look for entity -Event ")
                            msgAttrs=json.loads(sqsbody)
                            
                        print(" messageattributes:")
                        logger.info(msgAttrs)
                        msgKeys=getEventAndEntityName(msgAttrs)
                      
                        if not msgKeys:
                              logError("Event and Entity could not be resolved  ","get_sqs_event_params" )
                              exit(9)
                        
                        stateData['EventName']=msgKeys['EventName']
                        stateData['EntityName']=msgKeys['EntityName']
                                    
                        # Perform Event Specific logic 
                        logger.info(" Event and Entity Name ".format(json.dumps(msgKeys)))
                        try:
                            logger.info( "Processing  Event "+msgKeys['EventName'])
                            if    msgKeys['EventName'] in MrpEvents.mrpPortfolioSourceEventDict:
                                    logger.info("MRP Matching EDI Event Found "    )
                                    ep = EventMapper.SQSEventParser('edisource', sqsbody,msgKeys['EventName'],msgKeys['EntityName'])
                                    parserResult=ep.source_to_key()
                                    set_edi_event_jobParameters(stateData,parserResult)
                                    
                            elif  msgKeys['EntityName'] in MrpEvents.mrpAmtmEventEntityList:
                                    logger.info("MRP Matching AMTM Event Found" +msgKeys['EventName']  )
                                    if msgKeys['EventName']=="SUBMIT_MARKS_REQ"  or  msgKeys['EventName']=="SUBMIT_LOAN_MARKS_REQ":
                                        stateData.update({'portfolio_date':msgAttrs['PORTFOLIO_DATE']['stringValue']})
                                    ep = EventMapper.SQSEventParser('amtm_source', sqsbody,msgKeys['EventName'],msgKeys['EntityName'])
                                    parserResult=ep.source_to_key()
                                    set_amtm_event_jobParameters(stateData,parserResult)
                
                            elif  msgKeys['EntityName']=='TRIGGER_PORTFOLIO':
                                    logger.info( "portfolio Trigger for  {%s}   ",{msgKeys['EntityName'] })
                                    # disable  becuase portfolio EOM dates are not consistant  - 06/25 
                                    #ep = EventMapper.SQSEventParser('mrpdataPortfolio',sqsbody, msgKeys['EventName'],msgKeys['EntityName'])
                                    #parserResult=ep.source_to_key()
                                    parserResult={}
                                    parserResult.update({ "job_data_src":msgAttrs["PORTFOLIO_SOURCE"],"portfolio_date":msgAttrs["PORTFOLIO_DATE"] ,"configurationId":'portfolio_combiner'})
                                    logger.info(parserResult)
                                    set_mrpdata_portfolio_event_jobparameters(stateData,parserResult)
                            else :
                                  logError("  Unrecognised SQS Event","get_sqs_event_params")
                                  exit(9)
                            
                                    
                        except :
                                    logError( ' Error processing SQS event ',"get_sqs_event_params")
                                    raise
                    else:
                        logger.info( " AMTM temporary method for manual JSON test ")
                        msgKeys=getEventAndEntityName( rec.get('body'))
                        print(json.dumps(msgKeys))
                        if  msgKeys['EntityName'] in MrpEvents.mrpAmtmEventEntityList:
                                    logger.info("MRP Matching AMTM Event Found" +msgKeys['EventName']  )
                                    ep = EventMapper.SQSEventParser('amtm_source_hack', rec.get('body'),msgKeys['EventName'],msgKeys['EntityName'])
                                    parserResult=ep.source_to_key()
                                    print( "parser result") 
                                    print(json.dumps(parserResult,indent=2))
                                    set_amtm_event_jobParameters(stateData,parserResult)
    

 
def set_edi_event_jobParameters(stateData,parserResult):
    logger.info(json.dumps(parserResult,indent=2))
    stateData['configurationId'] = parserResult['configurationId']
    #stateData['batch_job_id']=str(stateData['batch_job_id'])
    stateData['job_data_src']=parserResult['dataSrc']
    stateData['portfolio_date']=parserResult['portfolio_date']
    stateData['jobName']='fre01-mrpdata-'+stateData['app_env_cd']+stateData['app_env_no']+'-'+parserResult['jobtypeName']+'-'+str(stateData['batch_job_id'])
    stateData['jobparameters']={"BATCH_JOB_ID" :"BATCH_JOB_ID="+str(stateData['batch_job_id']) ,"JOB_DATA_SRC": "JOB_DATA_SRC="+parserResult['dataSrc'],"JOB_PORTFOLIO_DATE":"JOB_PORTFOLIO_DATE="+parserResult['portfolio_date'], "APP_ENV_NO":"APP_ENV_NO="+os.environ['APP_ENV_NO'],"APP_ENV_CD":"APP_ENV_CD="+os.environ['APP_ENV_CD']}
    stateData['sqsMsg']=' { "body":{ "JOB_DATA_SRC": "'+parserResult['dataSrc'] + '","PORTFOLIO_DATE":"'+parserResult['portfolio_date']+'","EventName":{"Type":"String","Value":"'+parserResult['dataSrc']+'"},"EntityName":{"Type":"String","Value":"TRIGGER_PORTFOLIO"}}}'

    #stateData['sqsMsg']='JOB_DATA_SRC='+parserResult['dataSrc'] +',PORTFOLIO_DATE='+parserResult['portfolio_date']
    stateData['stateMachineJobExecutionArn']=os.environ['PORTFOLIO_DATA_SOURCE_EVENT_STEPFUNC_ARN']
    stateData['stateMachineJobExecutionName']='fre01-mrpdata-edi-src-wf-'+str(stateData['batch_job_id'])
    #stateData.update({'jobDefinition':os.environ['AWS_BATCH_JOB_DEF_TEMPLATE_90']})

    
def set_cw_event_jobParameters(stateData,parserResult):
    stateData['configurationId'] =parserResult['EventType']
    stateData['portfolio_date']=parserResult['PORTFOLIO_DATE']
    stateData['jobName']='fre01-mrpdata-'+stateData['app_env_cd']+stateData['app_env_no']+'-'+parserResult['EventType']+'-'+str(stateData['batch_job_id'])
    stateData['jobparameters']={"batch_job_id" :"BATCH_JOB_ID="+str(stateData['batch_job_id']) , "portfolio_date":"JOB_PORTFOLIO_DATE="+parserResult['PORTFOLIO_DATE'],"entity_type" : "JOB_ENTITY_TYPE="+ stateData['configurationId'], "APP_ENV_NO":"APP_ENV_NO="+os.environ['APP_ENV_NO'],"APP_ENV_CD":"APP_ENV_CD="+os.environ['APP_ENV_CD'] }
    if parserResult['EventType'] in [ 'dgp_daily_outbound' , 'DGP_MONTHLY_OUTBOUND_EOD' , 'DGP_MONTHLY_OUTBOUND_EOM'] :
        stateData['stateMachineJobExecutionArn']=os.environ['DGP_EVENT_STEPFUNC_ARN']
        stateData['sqlQuieres'] =parserResult['sqlQuieres']
    elif parserResult['EventType'] == 'mstr':
         stateData['stateMachineJobExecutionArn']=os.environ['MSTR_EVENT_STEPFUNC_ARN']
    else:
        stateData['stateMachineJobExecutionArn']=os.environ['COMMON_EVENT_STEPFUNC_ARN']
    if parserResult['EventType'] in ['dgp_planb'] :
       stateData['jobparameters'].update({"position_date":"JOB_POSITION_DATE="+parserResult['POSITION_DATE'],"entity_source":"ENTITY_SOURCE="+parserResult['EntitySource'] })
       

    stateData['stateMachineJobExecutionName']='fre01-mrpdata-'+parserResult['EventType']+'-'+str(stateData['batch_job_id'])
    #stateData.update({'jobDefinition':os.environ['AWS_BATCH_JOB_DEF_TEMPLATE_30']})
    

def set_mrpdata_portfolio_event_jobparameters(stateData,parserResult):
     stateData['jobparameters']={"BATCH_JOB_ID" :"BATCH_JOB_ID="+str(stateData['batch_job_id']) ,"JOB_DATA_SRC": "JOB_DATA_SRC="+parserResult['job_data_src']['stringValue'],"JOB_PORTFOLIO_DATE":"JOB_PORTFOLIO_DATE="+parserResult['portfolio_date']['stringValue'], "APP_ENV_NO":"APP_ENV_NO="+os.environ['APP_ENV_NO'],"APP_ENV_CD":"APP_ENV_CD="+os.environ['APP_ENV_CD'], "JOB_SCRATCH_DIR":"JOB_SCRATCH_DIR=/data/tmp"}
     stateData['configurationId'] = 'PORTFOLIO_COMBINER'
     stateData['job_data_src']=parserResult['job_data_src']['stringValue']
     stateData['portfolio_date']=parserResult['portfolio_date']['stringValue']
     stateData['jobName']='fre01-mrpdata-portcombiner-'+str(stateData['batch_job_id'])
     stateData['stateMachineJobExecutionArn']=os.environ['COMMON_EVENT_STEPFUNC_ARN']
     stateData['stateMachineJobExecutionName']='fre01-mrpdata-portfoliocombiner-wf-'+str(stateData['batch_job_id'])
     #stateData.update({'jobDefinition':os.environ['AWS_BATCH_JOB_DEF_TEMPLATE_90']})


def set_amtm_event_jobParameters(stateData,parserResult):
    logger.info(json.dumps(parserResult,indent=2))
    stateData['configurationId'] = parserResult['configurationId']
    stateData['input_file']=parserResult['input_file']
    stateData['entity_type']=parserResult['configurationId']
	#AMTM commitments need portfolio date
    if parserResult['configurationId']=="SUBMIT_MARKS_REQ"  or  parserResult['configurationId']=="SUBMIT_LOAN_MARKS_REQ":
        stateData['jobparameters']={"APP_ENV_NO":"APP_ENV_NO="+stateData['app_env_no'],"APP_ENV_CD":"APP_ENV_CD="+stateData['app_env_cd'], "input_file" : "JOB_INPUT_FILE_KEY_PREFIX="+ stateData['input_file'], "entity_type" : "JOB_PRICE_DATA_SRC="+ stateData['entity_type'] , "batch_job_id" : "BATCH_JOB_ID="+str(stateData['batch_job_id']), "JOB_PORTFOLIO_DATE" : "JOB_PORTFOLIO_DATE="+stateData['portfolio_date']}
    else:
       stateData['jobparameters']={"APP_ENV_NO":"APP_ENV_NO="+stateData['app_env_no'],"APP_ENV_CD":"APP_ENV_CD="+stateData['app_env_cd'], "input_file" : "JOB_INPUT_FILE_KEY_PREFIX="+ stateData['input_file'], "entity_type" : "JOB_PRICE_DATA_SRC="+ stateData['entity_type'] , "batch_job_id" : "BATCH_JOB_ID="+str(stateData['batch_job_id'])}
    stateData['jobName']='fre01-mrpdata-'+stateData['app_env_cd']+stateData['app_env_no']+'-'+parserResult['entity_type']+'-'+str(stateData['batch_job_id'])
    stateData['stateMachineJobExecutionArn']=os.environ['COMMON_EVENT_STEPFUNC_ARN']
    stateData['stateMachineJobExecutionName']='fre01-mrpdata-'+parserResult['configurationId']+'-'+str(stateData['batch_job_id'])
    return 'Success'
    
def logError(err,methodName):
    err="  "+err
    logger.error(err)
    
def logErrorEMMAlert(err,methodName):
    #disable
    #err="FRE01EMMFAIL:LEVCNTRL: "+err
    logger.error(err)
if __name__ == "__main__":
    s3event={   "Records": [     {       "eventVersion": "2.0",       "eventSource": "aws:s3",       "awsRegion": "us-east-1",       "eventTime": "1970-01-01T00:00:00.000Z",       "eventName": "ObjectCreated:Put",       "userIdentity": {         "principalId": "EXAMPLE"       },       "requestParameters": {         "sourceIPAddress": "127.0.0.1"       },       "responseElements": {         "x-amz-request-id": "EXAMPLE123456789",         "x-amz-id-2": "EXAMPLE123/5678abcdefghijklambdaisawesome/mnopqrstuvwxyzABCDEFGH"       },       "s3": {         "s3SchemaVersion": "1.0",         "configurationId": "prima_valuation_krd",         "bucket": {           "name": "fnma-fre01-devl-edl-us-east-1-edl",           "ownerIdentity": {             "principalId": "EXAMPLE"           },           "arn": "arn:aws:s3:::fnma-fre01-devl-edl-us-east-1-edl"         },         "object": {           "key": "land/cin/dflt/prima/devl_01/DSET00000000/valuation/krd/20181129154936185.PRIMA000.KRD00000.manifest",           "size": 1024,           "eTag": "0123456789abcdef0123456789abcdef",           "sequencer": "0A1B2C3D4E5F678901"         }       }     }   ] }
    s3testevent={   "Records": [     {       "eventVersion": "2.0",       "eventSource": "aws:s3",       "awsRegion": "us-east-1",       "eventTime": "1970-01-01T00:00:00.000Z",       "eventName": "ObjectCreated:Put",       "userIdentity": {         "principalId": "EXAMPLE"       },       "requestParameters": {         "sourceIPAddress": "127.0.0.1"       },       "responseElements": {         "x-amz-request-id": "EXAMPLE123456789",         "x-amz-id-2": "EXAMPLE123/5678abcdefghijklambdaisawesome/mnopqrstuvwxyzABCDEFGH"       },       "s3": {         "s3SchemaVersion": "1.0",         "configurationId": "PVRVALNCLOUD",         "bucket": {           "name": "fnma-fre01-devl-edl-us-east-1-edl",           "ownerIdentity": {             "principalId": "EXAMPLE"           },           "arn": "arn:aws:s3:::fnma-fre01-devl-edl-us-east-1-edl"         },         "object": {           "key": "land/cin/dflt/prima/devl_01/DSET00000000/valuation/epl/20190214133940232.PRIMA000.EPL00000.manifest",           "size": 1024,           "eTag": "0123456789abcdef0123456789abcdef",           "sequencer": "0A1B2C3D4E5F678901"         }       }     }   ] }

    context = []
    lambda_handler(s3testevent, context)
