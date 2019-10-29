import json

import os
import sys
import datetime
import re
import csv
import urllib
import time
import paramiko
import boto3
import logging
from epv import PasswordVault
logger = logging.getLogger()
logger.setLevel(logging.INFO)
s3_client = boto3.client('s3', region_name='us-east-1')
batch = boto3.client('batch')
#lambda_client=boto3.client('lambda',region_name='us-east-1')
''' 
Listener to MRP Events , All events are registered once irrespective of number of active environemnts
'''
def lambda_handler(event, context):



    # hostname and command can be taken from the json input to the lambda, if not, it will read from environment variables
    print(event)
    hostname = event.get("hostname")
    command = event.get("command")
    if (hostname is None):
        hostname = os.environ['hostname']
    if (command is None):
        command = os.environ['command']
    if "EventType" in event:
        if event["detail"]["EventType"] =="fre01-mrpdata-mstr-hao":
            command="/appl/cmbi"+os.environ['APP_ENV_CD']+"_"+os.environ['APP_ENV_NO']+"/cmbi-microstrategy/workflow/HAO/HAO_to_s3"
        if event["detail"]["EventType"] =="fre01-mrpdata-mstr-ec":  
            command="/appl/cmbi"+os.environ['APP_ENV_CD']+"_"+os.environ['APP_ENV_NO']+"/cmbi-microstrategy/workflow/EC/EC_to_s3"

    
 
    # username and password can be taken from the json input to the lambda, if not, it will read from PAM file to get username and password
    username = event.get("username")
    password = event.get("password") 
    
    if (not username )  or (not password) :
        
        frepv=PasswordVault(os.environ['PAM_APP_CD'],os.environ['PAM_ENV_CD'],os.environ['PAM_OBJ_REF'])
         
        username = frepv.getAccount()
        password = frepv.getPassword()
        #logger.info(" host {} / login {} /passwd {}".format(os.environ['hostname'],username,password)) 

    dt = datetime.datetime.now()
   
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print("[INFO] Successfully imported paramiko")
    print("[INFO] Trying to connect to the I-server...")
    print("[INFO] Using MicroStrategy I-server: " + hostname)
    try:
        c.connect(hostname, username = username, password = password)
    except:
        print ('[ERROR] FRE01EMMFAIL:MSTRCNTRL: Cannot connect to ec2. Ending...')
        raise
    print( "[INFO] Successfully created SSH Client ....")
 
    
    print ("\n********")
    print ("[INFO]: Executing: ")
    print (command)
    print (" On: ")
    print (hostname)
    transport = c.get_transport()
    channel = transport.open_session()
    channel.exec_command(command)
    #stdin , stdout, stderr = c.exec_command(command)
    #for line in stdout.readlines():
    #    print(line)
    print ("[INFO] wait for 10s after executing command...")
    time.sleep(10)
    print ("[INFO] wait completed, now closing ssh connection")
    c.close()
    print ("[INFO] SSH connection closed.")
    #print (stdout.read())
    #print (stderr.read())

    
    {
        'message' : "Script execution completed. See Cloudwatch logs for complete output"
    }
if __name__ == "__main__":
    context = []
    event={"Key1":"Val1"}
    lambda_handler(event, context)

