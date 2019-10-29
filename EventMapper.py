'''
parse Event Data based on configurationId
'''

import json
import os
import sys
import datetime
import csv
import urllib
import time
import boto3
import ast
from io import BytesIO
from botocore.client import Config
import MrpEvents
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)
def logError(err,methodName):
    err=" "+err + " in method {"+methodName+ "}"
    logger.error(err)  
    
class S3EventParser(object):

    def __init__(self,configurationId,bucket_name,key_name):

                  self.configurationId=configurationId
                  self.bucket_name=bucket_name
                  self.key_name=key_name

    def source_to_key(self):
        # Get the method or  Default to a lambda.
        method = getattr(self, self.configurationId,lambda: "Invalid Interface")
        # Call the method as we return it
        return method()
 
    def PVRVALNCLOUD(self):
        print(' Processing PVR manifest')
        rtndict={'configId' : self.configurationId}
        return rtndict
    
    def prima_valuation_s3_manifest(self):
        
        rtndict={'external_id':'','dmr_load_id':''}
        s3_client=boto3.client('s3')
        obj = s3_client.get_object(Bucket=self.bucket_name, Key= self.key_name)
        line_count = 0
        line_data_bytes = b''
        while line_count <= 4 :
        
            incoming = obj['Body'].read(1)
            if incoming == b'\n':
                line_count = line_count + 1
        
            line_data_bytes = line_data_bytes + incoming

        line_data = line_data_bytes.split(b'\n')
        for l in line_data:
            if "#EXTERNAL_ID=" in str(l):
                rtndict['external_id'] = str(l).split('=')[1].replace('\"\'', '').replace('"','')
            if "#DMR_LOAD_ID=" in str(l):
                rtndict['dmr_load_id'] = str(l).split('=')[1].replace('\"\'', '').replace('"','')
        
        logger.info( ' Valuation S3 Manifest Load Ids {}'.format(rtndict))
        return rtndict    

    def prima_valuation_s3(self):
        
        rtndict={'external_id':'','dmr_load_id':''}
        s3client=boto3.resource('s3')
        obj = s3client.Object(self.bucket_name, self.key_name)
        resp=obj.get()['Body'].read().decode('utf-8') 
        manifest_content=json.loads(resp) 
         
        try:
            external_id=manifest_content.get('eventParameters', {}).get('externalId')
            dmr_load_id=manifest_content.get('eventParameters', {}).get('dmr_load_id')
            rtndict.update({ "external_id":external_id ,"dmr_load_id":dmr_load_id } )
        except :
            logError( " Exception In getting external or DMR ID ","prima_valuation_s3")
            raise
        
        logger.info( ' Valuation S3 Manifest Load Ids {}'.format(rtndict))
        return rtndict

    def datamart_s3(self):

        s3client=boto3.client('s3',config=Config(signature_version='s3v4'))
        resp = s3client.get_object(
                    Bucket=self.bucket_name, Key=self.key_name
                )
        manifest_content = resp["Body"].read().decode("utf-8")
        data = json.loads(manifest_content)
        return data["manifest"][0]
    
class CWEventParser(object):

    def __init__(self, src, event):
        self.event=event
        self.src=src

    def source_to_key(self):
        # Get the method or  Default to a lambda.
        method = getattr(self, self.src,lambda: "Invalid Interface ")
        # Call the method as we return it
        return method()
     
        
    def cwsource(self):
        logger.info("***********Return the CW event detail ******************")
        return self.event['detail']
class SNSEventParser(object):

    def __init__(self, src, event,eventNm,entityNm):
        self.event=event
        self.src=src
        self.eventNm=eventNm
        self.entityNm=entityNm

    def source_to_key(self):
        # Get the method or  Default to a lambda.
        method = getattr(self, self.src,lambda: "Invalid Interface ")
        # Call the matching  method and  return it
        return method()
           
    def edisource(self):
        resultdict={}
        portDt=''
        tblNm=''
         
        
        try:
                logger.info(' Get Job typ name / Portfolio Date /job type for EDI  Event '+ self.eventNm)
                logger.info(" tbl type="+MrpEvents.mrpPortfolioSourceEventDict[self.eventNm][0])
                resultdict['jobtypeName']=MrpEvents.mrpPortfolioSourceEventDict[self.eventNm][1]
                resultdict['dataSrc']=MrpEvents.mrpPortfolioSourceEventDict[self.eventNm][2]
                resultdict['configurationId']=self.eventNm 
                resultdict['portfolio_date']=self.getediportfoliodates(MrpEvents.mrpPortfolioSourceEventDict[self.eventNm][0],self.event)
        except :
            logger.info(" Moving message to SQS")
            self.MoveSqs(self.event)
            logError( 'Unable to get All Event Parameters for EDI configId '+self.configId , "SNSEventParser")
            raise
        return resultdict
            
    # AMTM-Start            
    def amtm_source(self):
        resultdict={}

        #configurationId= self.event['MessageAttributes']['EntityType']['Value']
        configurationId= self.entityNm
        logger.info(' Parsing AMTM Event  details for '+ configurationId)
        msg = self.event['Sns']['Message']
        if isinstance(msg,(bytes,str)):
            print('convert str/unicode to dict explicitly')
            msg = ast.literal_eval(msg) # convert string to dict explicitly
            print(msg)
        resultdict['event_type']=self.eventNm
        resultdict['input_file']=msg["datasets"][0]["dataSetPrefix"]
        
        if(configurationId[-4:] == '_EOD'):
            resultdict['entity_type']=configurationId[0:-4]        
            resultdict['configurationId']=configurationId[0:-4].lower()

        return resultdict
    # AMTM-End

    def MoveSqs(self,event):
            try:
                sqs = boto3.resource('sqs')
                dlq = sqs.get_queue_by_name(QueueName=os.environ['AWS_SQS_DEAD_LETTER_QUEUE_NM'])
                #response=dlq.send_message(dlq.url,MessageBody=str(event))
                logger.info(' Message moved to DLQ')
                return response
            except Exception as ERROR:
                    logger.info(' ERROR')
                    raise
    def getediportfoliodate(self,tblNm, edievent):
            
            # Parse Idiotic EDI messages
            rptDt=''
            msg=edievent["Sns"]["Message"][self.entityNm][0] or edievent["Sns"]["body"][self.entityNm][0] 
            rptDt=(msg[tblNm][0]['filepath']).split('=')[1]
            return rptDt   
    
    def getediportfoliodates(self,mrpSrcTblNm, edievent):

            # Parse  EDI messages
            rptDt=''
            msgs= edievent["Sns"]["Message"]
            for entity  in msgs:
                if entity==self.entityNm:
                    tablesdict=msgs[entity]
                    for tbls in tablesdict:
                        for tbl in tbls:
                           if mrpSrcTblNm==tbl:
                              dsets=tbls[mrpSrcTblNm]
                              for ds in dsets:
                                  flist=ds["filepath"].split('/')
                                  if mrpSrcTblNm  in flist:
                                     rptDt=ds["filepath"].split('=')[1]
            return rptDt

 
     
                   
class SQSEventParser(object):

    def __init__(self, src, event,eventNm,entityNm):
        self.event=event
        self.src=src
        self.eventNm=eventNm
        self.entityNm=entityNm
        
    def source_to_key(self):
        # Get the method or  Default to a lambda.
        method = getattr(self, self.src,lambda: "Invalid Interface ")
        # Call the method as we return it
        return method()
        # disable since EOM dates are different format 
    def mrpdataPortfolio(self):
        rtndict={}
        rtndict['job_data_src']=self.event['body']['JOB_DATA_SRC']
        rtndict['portfolio_date']=self.event['body']['PORTFOLIO_DATE']
        rtndict['configurationId']='portfolio_combiner'
        return rtndict
            
    def is_json(self,myjson):
        try:
           json_object = json.loads(myjson)
        except ValueError:
               return False
        return True 
        
    def amtm_source(self):
        resultdict={}
        logger.info( "Processing AMTM SQS Message ")
        logger.info(" message"+json.dumps(self.event))
        configurationId= self.entityNm
        #self.event.get('Records') or self.event.get('records') or []
        #msgdict=json.loads(self.event['Message']) or json.loads(self.event['message'])
        print(" Event Info:::")
        print(json.dumps(self.event))
        msgs=self.event.get('Message') or self.event.get('message') 
        if msgs.find("SUBMIT_MARKS_REQ") >-1 or msgs.find("SUBMIT_LOAN_MARKS_REQ")  > -1:
                        
            # AMTMAMTM Commitment Request 
            resultdict['event_type']=self.entityNm
            resultdict['input_file']=''
            resultdict['entity_type']=self.entityNm
            resultdict['configurationId']=self.entityNm
            
            return resultdict
        else:
            logger.info(' Getting AMTM  details for '+ configurationId)
            # some reason zepplin based events is messing this up ...
            try:
                msgdict=json.loads(msgs)
            except:
                msgdict=self.event
            resultdict['event_type']=self.eventNm
            resultdict['input_file']=msgdict["datasets"][0]["dataSetPrefix"] 
            if(configurationId[-4:] == '_EOD'):
               resultdict['entity_type']=configurationId[0:-4]        
               resultdict['configurationId']=configurationId[0:-4].lower()
            return resultdict
    
        
    def amtm_source_hack(self):
        resultdict={}
        print( "Processing AMTM SQS Message")
        configurationId= self.entityNm
        msgdict=self.event['Message']
        logger.info(' Getting AMTM  details for '+ configurationId)
        #for k,v in msgdict.items():
        #    print("k "+k)
        #    if k.strip()=="datasets":
        #       resultdict['input_file']=msgdict["datasets "][0]["dataSetPrefix"]    
        resultdict['event_type']=self.eventNm
        resultdict['input_file']=msgdict["datasets"][0]["dataSetPrefix"]
        if(configurationId[-4:] == '_EOD'):
            resultdict['entity_type']=configurationId[0:-4]        
            resultdict['configurationId']=configurationId[0:-4].lower()

        return resultdict
    # AMTM-End
    # EDI Start
    def edisource(self):
        
        print(" processing EDI Source in SQS ")
        print(json.dumps(self.event) )
        resultdict={}
        portDt=''
        tblNm=''
         
        
        try:
                logger.info(' Get Job typ name & Portfolio Date   for EDI  Event {} and Entity {} '.format( self.eventNm , self.entityNm))
                logger.info(" table name  to lookup ="+MrpEvents.mrpPortfolioSourceEventDict[self.eventNm][0])
                resultdict['jobtypeName']=MrpEvents.mrpPortfolioSourceEventDict[self.eventNm][1]
                resultdict['dataSrc']=MrpEvents.mrpPortfolioSourceEventDict[self.eventNm][2]
                resultdict['configurationId']=self.eventNm 
                resultdict['portfolio_date']=self.getediportfoliodate(MrpEvents.mrpPortfolioSourceEventDict[self.eventNm][0],self.event)

        except :
                  #self.MoveSqs(self.event)
                  logError( 'Unable to get Portfolio date Event Parameters for EDI  Event','edisource')
                  raise
        return resultdict
   
     
    def getediportfoliodate(self,mrpSrcTblNm, snsbody):

           # Parse  EDI messages
            rptDt=''
            msgDict={}
            msgs=''
            dateListpertbl=[]
            dtfrmt=''
            
            #try:
            logger.info( "try getting message content from SNS body ..")
            msgs=snsbody.get("Message") or json.dumps(snsbody) or ' '
            # Clean Message    
            if ( msgs.startswith('"') and msgs.endswith('"') ) or ( msgs.startswith('\'') and msgs.endswith('\'') )  :
                msgs = msgs[1:-1]
                msgs=msgs.replace(r'\n',"")
                msgs=msgs.replace('\\',"")
            msgDict=json.loads(msgs)
            #print(type(msgDict))
            print(json.dumps(msgDict))
            for dslist in msgDict["datasets"]:
                # some EDI events dont have partitions as lists 
                if isinstance(dslist, list):
                   for prtn in dslist:
                       flist=prtn["datasetPrefix"].split('/')
                       if mrpSrcTblNm.lower()  in [item.lower() for item in flist]:
                           rptDt=(prtn["datasetPrefix"].split('=')[1]).strip()
                           logger.info("self.eventNm ="+self.eventNm + " rpt dt="+rptDt)
                           if self.eventNm in ['INFO.SF_LN_CRTD_EOM_SNAPSHOT','INFO.SF_LNCMT_CRTD_EOM_SNAPSHOT']:
                              logger.info(" rpt date with YYYYMM format ")
                              dtfrmt='YYYYMM'
                              dateListpertbl.append( datetime.datetime.strptime(rptDt,"%Y%m"))
                           else:
                              dateListpertbl.append( datetime.datetime.strptime(rptDt,"%Y-%m-%d"))
                else:
                    # split DS"
                    flist=dslist["datasetPrefix"].split('/')
                    if mrpSrcTblNm.lower()  in [item.lower() for item in flist]:
                       rptDt=(dslist["datasetPrefix"].split('=')[1]).strip()
                       logger.info(" self.eventNm ="+self.eventNm+ " rpt dt="+rptDt)
                       if self.eventNm in ['INFO.SF_LN_CRTD_EOM_SNAPSHOT','INFO.SF_LNCMT_CRTD_EOM_SNAPSHOT']:
                              logger.info(" rpt date with YYYYMM format ")
                              dateListpertbl.append( datetime.datetime.strptime(rptDt,"%Y%m"))
                       else:
                              dateListpertbl.append( datetime.datetime.strptime(rptDt,"%Y-%m-%d"))
                       
            
            # in case where we have multiple dates for a table take the max
            dateListpertbl.sort(reverse=True)
            logger.info("dateListpertbl ")
            logger.info(dateListpertbl)
            
            # datetime %Y%m format returns date 
            if self.eventNm in ['INFO.SF_LN_CRTD_EOM_SNAPSHOT','INFO.SF_LNCMT_CRTD_EOM_SNAPSHOT']:
                rptDt=(dateListpertbl[0].strftime('%Y%m'))
            else:
                rptDt=(dateListpertbl[0].strftime('%Y-%m-%d'))
            logger.info("report Date:"+rptDt) 
            
            if not rptDt:
                   logError(" Portfolio Report Date is Blank OR source Table name MRPData looks for is not avialable in datasets","getediportfoliodate")
                   exit(5)
            return rptDt

            

    
      
    def MoveSqs(self,event):
            try:
                sqs = boto3.resource('sqs')
                dlq = sqs.get_queue_by_name(QueueName=os.environ['AWS_SQS_DEAD_LETTER_QUEUE_NM'])
                response=dlq.send_message(dlq.url,MessageBody=str(event))
                logger.info(' Message moved to DLQ')
                return response
            except Exception as ERROR:
                    logger.info(' ERROR')
                    raise
                    
if __name__ == "__main__":
    context = []
    lambda_handler(event, context)

