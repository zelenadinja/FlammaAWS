import urllib.parse
import boto3
from s3_wrapper import FileLikeObject
import zipfile 
import tqdm
import io 
from boto3_type_annotations.s3 import ServiceResource

s3:ServiceResource = boto3.resource('s3')

def lambda_handler(event, context):
    #print("Received event: " + json.dumps(event, indent=2))

    # Get the object from the event and show its content type
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')

    file_object = s3.Object(bucket, key)
    filesize = file_object.content_length
    
    if filesize > 2147483648:
        print('Object size is greater than 2GB so use Wrapper to stream file')
        streaming = FileLikeObject(file_object)
    else:
        print('Object size is less than 2GB so stream whole file at once')
        streaming = io.BytesIO(file_object.get()['Body'].read())
    
    zfile = zipfile.ZipFile(streaming)
    
    for filename in zfile.namelist():
        fileinfo = zfile.getinfo(filename)
        
        with tqdm.tqdm(total=fileinfo.file_size, unit='B', unit_scale=True, desc=filename) as pbar:
            s3.meta.client.upload_fileobj(
                zfile.open(filename),
                Bucket=bucket,
                Key=filename,
                Callback = lambda bytes_:pbar.update(bytes_),
                
                )
        