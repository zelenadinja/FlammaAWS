from s3_wrapper import FileLikeObject
import boto3   #type: ignore
from typing import Optional,Tuple, List, Union, Dict 
from boto3_type_annotations.s3 import ServiceResource #type: ignore 
import zipfile
import io 
from tqdm import tqdm #type: ignore
import argparse



class FlammaAWS:

    def __init__(self, bucket_name: str, object_key:Union[str,List[str],None]=None, aws_credentials:Optional[Tuple[str, str]] =None) -> None:

        """
        Initialize S3 Bucket Resources.If aws credentials are not provided its gona use
        default credentials from config file.If object_key is not provided its gona search for all
        ZIP files on S3 Bucket.

        """
        if aws_credentials is None:
            self.s3_resource: ServiceResource = boto3.resource('s3')
        else:
            self.s3_resource: ServiceResource = boto3.resource(
                's3',
                aws_access_key_id = aws_credentials[0],
                aws_secret_access_key = aws_credentials[1],
            )

        self.bucket_name = bucket_name
        self.s3_bucket: ServiceResource = self.s3_resource.Bucket(self.bucket_name)
        self.object_key = object_key

    def _get_object_keys(self) -> List[str]:

        if self.object_key is None:
            zip_objects = []
            for obj in self.s3_bucket.objects.all():
                if obj.key.endswith('.zip'):
                    zip_objects.append(obj.key)

        elif type(self.object_key) == list:
            zip_objects = self.object_key

        elif type(self.object_key) == str:
            zip_objects = [self.object_key]

        else:
            raise ValueError('Object key or List of object keys is provided')
        
        return zip_objects

    
    def _get_object_byte_size(self) -> Dict[str, int]:

        object_sizes = {}

        if self.object_key is None:
            object_keys = self._get_object_keys()

        elif type(self.object_key) is list:
            object_keys = self.object_key

        else:
            object_keys = self.object_key

        for obj in self.s3_bucket.objects.all():
            if obj.key.endswith('.zip'):
                object_sizes[obj.key] = obj.size
        
        return object_sizes

    def unzip_upload(self, threshold: int = 1073741824,verbose:bool = False, delete: bool=  False) -> None:

        object_sizes = self._get_object_byte_size()

        object_keys = self._get_object_keys()

        for i in object_keys:
            s3object = self.s3_bucket.Object(i)
            if object_sizes[i] < threshold:
                print(f"Object filesize is less than {threshold}bytes(object_size:{ object_sizes[i] / 1024 / 1024 :.2f} MB) so move whole file into memory.")
                streaming = self._tiny(s3object=s3object)
            elif object_sizes[i] > threshold:
                print(f"Object filesize is greater than {threshold}(object_size:{object_sizes[i] / 1024 / 1024 :.2f} MB) so stream file.")
                streaming = self._large(s3object=s3object)
            
            self._run(streaming_body=streaming, verbose=verbose)

            if delete:
                print('Deleting object...')
                s3object.delete()
        
    def _tiny(self, s3object):

        """
        Since file is less than given threshold we can fit whole file into memory.

        """
        object_body = s3object.get()['Body'].read()
        streaming_file = io.BytesIO(object_body)

        return streaming_file

    def _large(self, s3object):
        "Since file size is greater than given threshold we will use our S3 Wrapper to stream file"
        streaming_file = FileLikeObject(s3object)

        return streaming_file

    def _run(self, streaming_body, verbose) -> None:

        zfile = zipfile.ZipFile(file=streaming_body)
        for filename in zfile.namelist():
            fileinfo = zfile.getinfo(filename)

            if verbose:
                with tqdm(total=fileinfo.file_size, unit='B', unit_scale=True, desc=filename) as progressbar:
                    self.s3_resource.meta.client.upload_fileobj(
                        zfile.open(filename),
                        Bucket = self.bucket_name,
                        Key = filename,
                        Callback = lambda bytes_: progressbar.update(bytes_),
                    )
            else:
                self.s3_resource.meta.client.upload_fileobj(
                        zfile.open(filename),
                        Bucket = self.bucket_name,
                        Key = filename,
                    )


if __name__ == '__main__':

    obj = FlammaAWS(bucket_name='testflamma', object_key=['assignment1_colab.zip','assignment2_colab.zip'])
    #objects = obj._get_object_keys()
    #print(objects)
    #objz = obj._get_object_byte_size()
    #print(objz)
    obj.unzip_upload(threshold=1073741824, verbose=True, delete=False)


