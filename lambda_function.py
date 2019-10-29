import boto3
import os
import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO) 
glue = boto3.client(service_name='glue', region_name='us-east-1',
              endpoint_url='https://glue.us-east-1.amazonaws.com')

def create_partition_list(db_name, table_name, parts):
    response = glue.get_table(CatalogId=os.environ['catalogId'],  DatabaseName=db_name, Name=table_name)
    
    # Parsing table info required to create partitions from table
    input_format = response['Table']['StorageDescriptor']['InputFormat']
    output_format = response['Table']['StorageDescriptor']['OutputFormat']
    table_location = response['Table']['StorageDescriptor']['Location']
    serde_info = response['Table']['StorageDescriptor']['SerdeInfo']
    partition_keys = response['Table']['PartitionKeys']
    input_list = []
    for i in range(len(parts)) :
        #print(parts[i])
        response = glue.batch_delete_partition(
                CatalogId=os.environ['catalogId'],  
                DatabaseName=db_name,
                TableName=table_name,
                PartitionsToDelete=[
                    {
                        'Values': [parts[i]]
                    }
                ]
            )

        input_dict = {
                'Values': [
                    parts[i]
                ],
                'StorageDescriptor': {
                    'Location': table_location + '/port_dt=' + parts[i].replace(':','%3A') + '/',
                    'InputFormat': input_format,
                    'OutputFormat': output_format,
                    'SerdeInfo': serde_info
                }
            }
        input_list.append(input_dict.copy())
    print (table_location)
    return input_list

def create_partition(event, context):
    for i in range(len(event['TableNames'])) :
        input_list = create_partition_list(event['DatabaseName'], event['TableNames'][i], event['PortfolioDate'])        
        #print('Adding partitions for table - ' + event['TableNames'][i] + ' @ ' + input_list[1]['StorageDescriptor']['Location'])
    
        create_partition_response = glue.batch_create_partition(
                CatalogId=os.environ['catalogId'],  
                DatabaseName=event['DatabaseName'],
                TableName=event['TableNames'][i],
                PartitionInputList=input_list
            )

    return ('Partition added for ' + event['TableNames'][i])
    
def update_table(event, context):
    for i in range(len(event['TableNames'])) :
        response = glue.get_table(CatalogId=os.environ['catalogId'],  DatabaseName=event['DatabaseName'], Name=event['TableNames'][i])

        glue.update_table(
        CatalogId=os.environ['catalogId'],   
        DatabaseName=event['DatabaseName'], 
        TableInput={
            'Name': event['TableNames'][i],
            'StorageDescriptor': {
                'Columns': response['Table']['StorageDescriptor']['Columns'],
                'Location': str(response['Table']['StorageDescriptor']['Location']).replace("devl","acpt"),
                'InputFormat': response['Table']['StorageDescriptor']['InputFormat'],
                'OutputFormat': response['Table']['StorageDescriptor']['OutputFormat'],
                'SerdeInfo': response['Table']['StorageDescriptor']['SerdeInfo']
            }
        }

    )
    return ('Partition added for ' + event['TableNames'][i])
def drop_table(event, context):
    for i in range(len(event['TableNames'])) :
        response = glue.delete_table(
            CatalogId=os.environ['catalogId'],   
            DatabaseName=event['DatabaseName'], 
            Name=event['TableNames'][i]
        )
def drop_invalid_partition(event, context):
    for i in range(len(event['TableNames'])) :
        response = glue.delete_partition(
            CatalogId=os.environ['catalogId'],   
            DatabaseName=event['DatabaseName'], 
            Name=event['TableNames'][i],
            PartitionValues=[
                'load_id=__HIVE_DEFAULT_PARTITION__'
            ]
        )

def RemoveDupes(duplicate): 
    final_list = [] 
    for item in duplicate: 
        if item not in final_list: 
            final_list.append(item) 
    return final_list 
    
def create_Additional_partitions(event):
    logger.info(" Adding multiple partitions ..")
    delresp={ }
    for i in range(len(event['TableNames'])) :
        #for prtn in event['partitionlist']:
            logger.info("partn list")
            logger.info(event['partitionlist'])
            #logger.info("****"+prtn)
            cleanList=RemoveDupes(event['partitionlist'])
            
            input_list = create_additional_partition_list(event['DatabaseName'], event['TableNames'][i], cleanList,event['Deletefirst'],event['TableLocationPath'])        
            logger.info(" Partition List")
            logger.info(input_list)
        
            create_partition_response = glue.batch_create_partition(
                CatalogId=os.environ['catalogId'],  
                DatabaseName=event['DatabaseName'],
                TableName=event['TableNames'][i],
                PartitionInputList=input_list
            )
            print("Input list")
            print(input_list)
    
    return ('Partition added for ' + event['TableNames'][i])



def create_additional_partition_list(db_name, table_name, parts,delflag,loc):
    response = glue.get_table(CatalogId=os.environ['catalogId'],  DatabaseName=db_name, Name=table_name)
    # Parsing table info required to create partitions from table
    input_format = response['Table']['StorageDescriptor']['InputFormat']
    output_format = response['Table']['StorageDescriptor']['OutputFormat']
    #table_location = response['Table']['StorageDescriptor']['Location']
    if not loc:
        table_location = response['Table']['StorageDescriptor']['Location']
    else:
        table_location =loc
    print(table_location)
    serde_info = response['Table']['StorageDescriptor']['SerdeInfo']
    
        
    for part in parts :
        input_list=[]
        fldrval=[]
        logger.info("part="+part)
        pathlist=part.split("/")
        
        for fldr in pathlist:
                logger.info("folder="+fldr)
                fldrval.append(fldr.split('=')[1])
        logger.info(" partition ::{}  folderval ::{}".format(part,fldrval))
        input_dict = {
                'Values':fldrval,
                'StorageDescriptor': {
                    'Location': table_location+'/'+part.replace(':','%3A')+'/',
                    'InputFormat': input_format,
                    'OutputFormat': output_format,
                    'SerdeInfo': serde_info
                }
            }
        input_list.append(input_dict.copy())
        logger.info(input_list)
        if delflag=="true":
            delresp = glue.batch_delete_partition(
                CatalogId=os.environ['catalogId'],  
                DatabaseName=db_name,
                TableName=table_name,
                PartitionsToDelete=[ { 'Values': fldrval } ]
                )
            if delresp['Errors']:
                logger.info(" Delete Has error")
                logger.info(delresp)
            else:
                logger.info("deleted partition")
    #logger.info(input_list)
    return input_list    
def lambda_handler(event, contxt):
    # TODO implement
    # response = glue.get_table(CatalogId='703959857724',  DatabaseName='fre01_acptedl_app_mrp_isgt_01', Name=event['TableName'])
    if event['Action'] in ['AddPartitions'] :
        print('Executing action :: ' + event['Action'] + ' on tabled :: '+str(event['TableNames']))
        create_partition(event, contxt)    
    elif event['Action'] in ['UpdateTable'] :
        print('Executing action :: ' + event['Action'] + ' on tabled :: '+str(event['TableNames']))
        update_table(event, contxt)    
    elif event['Action'] in ['AddAdditionalPartitions'] :
         logger.info('Executing action :: ' + event['Action'] + ' on table :: '+str(event['TableNames']))
         resp=create_Additional_partitions(event) 
    #elif event['Action'] in ['xDropTable'] :
    #    print('Executing action :: ' + event['Action'] + ' on tabled :: '+str(event['TableNames']))
    #    drop_table(event, contxt)    
    elif event['Action'] in ['DropInvalidPartitions'] :
        print('Executing action :: ' + event['Action'] + ' on tabled :: '+str(event['TableNames']))
        drop_invalid_partition(event, contxt)        
    
    
    return 'Success'
