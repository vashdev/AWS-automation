import os
import logging
import psycopg2
from epv import PasswordVault
logger = logging.getLogger()
logger.setLevel(logging.INFO)
def getCredential(pamappcd,pamenvcd,pamobjref):
    try:

       return PasswordVault(pamappcd,pamenvcd,pamobjref)
    except Exception as ERROR:
       logger.error("PAM  connection issue: " )
       logger.error("FRE01EMMFAIL:LAYER: exception:")
       
def getconn(dbName,user,pswd,port,endpoint,schema):
       try:
          REDSHIFT_SEARCHPATH='fre01'
          conn= psycopg2.connect(
                  dbname=dbName,
                  user=user,
                  password=pswd,
                  port=port,
                  host=endpoint,
                  options=f'-c search_path={schema}',)
          conn.set_session(autocommit=True)
          return conn
       except Exception as ERROR:
              logger.error("DB connection  issue: " )
              logger.error("FRE01EMMFAIL:LAYER: exception:")
              raise ERROR 
