from s3_wrapper import FileLikeObject
import boto3   #type: ignore
from typing import Optional,Tuple, List, Union, Dict 
from boto3_type_annotations.s3 import ServiceResource #type: ignore 
import zipfile
import io 
from tqdm import tqdm #type: ignore
import argparse



def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')

def noneargument(v):

    if isinstance(v, list) and len(v) == 1 and v[0].lower() in ('none'):
        return None
    elif isinstance(v, list) and len(v) == 1 and v[0].lower() not in ('none'):
        return v[0]
    else:
        return v



def _setup_parser():
    "Setup Pythons ArgumentParser with arguments"
    parser = argparse.ArgumentParser()
    parser.add_argument('--bucket_name', '-b', type=str, help='Name of your S3 Bucket')
    parser.add_argument('--object_key', '-o', nargs="+", default=None, help='Object key for unziping and uploading.')
    parser.add_argument("--aws_creds", '-c', nargs="+", default=None, help='Should be --aws_creds aws_access_key_id aws_secret_access_id')
    parser.add_argument('--threshold', '-t', type=int, default=1073741824, help='Threshold of which is gona determine if its gona stream file or fit whole file into memory.')
    parser.add_argument('--verbose', '-v', type=str2bool,default=True, help='If True, show progressbar while uploading unzipped content to S3 Bucket.')
    parser.add_argument('--delete', '-d', type=str2bool, default=False, help='If True delete ZIP file after uploading UNZIPPED content')
    
    return parser.parse_args()



class FlammaAWS:
    """
    ZIP file should be first uploaded to S3 Bucket.Idea is to  use s3 wrapper for streaming objects if file cant fit into memory.
    Thats why there is a threshold argument.Just test it out since its  a waste of time if we stream file that can fit into memory at once.
    With zipfile module we unzip a content from file and upload it back to S3.

    """
    def __init__(self, bucket_name: str, object_key:Union[str,List[str],None]=None, aws_credentials:Optional[Tuple[str, str]] =None) -> None:

        """
        Initialize S3 Bucket Resources.

        Parameters:
        ----------

        bucket_name: string
            Name of your S3 Bucket
        object_key: string, list of strings or None
            I took in account every possible situation.
            U can specify single object_key, list of object_keys and if object key is None it will look for all .zip files in Bucket and use them.
            Path of files within bucket should be included as well.
            Example:
            If there is an object withing s3://bucketname/folder1/folder2/object.zip, argument should be object_key = folder1/folder2/object.zip
        aws_credentials:optional
            If specified its gona overwrite defualt credentials if found.It should be (aws_access_key_id, aws_secret_access_key)


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
        """
        Unzip ZIP files from S3 Bucket and upload them back to Bucket.

        Parameters:
        ----------

        threshold: int 
        This will decide if its gona stream file or move whole file into memory.Default value is 1GB.
        verbose:bool
            Info while uploading
        delete:bool
            If True its gona delete .zip file after unziping and uploading
            
        """

        object_sizes = self._get_object_byte_size()

        object_keys = self._get_object_keys()

        for i in object_keys:
            s3object = self.s3_bucket.Object(i)
            if object_sizes[i] < threshold:
                print(f'Object size ({object_sizes[i] / 1024 / 1024 :.4f} MB) is less than threshold ({threshold / 1024 / 1024 } MB).Fit whole file into memory.')
                streaming = self._tiny(s3object=s3object)
            elif object_sizes[i] > threshold:
                print(f'Object size ({object_sizes[i] / 1024 / 1024 :.4f} MB) is greater than threshold ({threshold / 1024 / 1024 } MB).Using s3 wrapper to stream file.')
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

    args = _setup_parser()

    flamma = FlammaAWS(bucket_name=args.bucket_name, object_key=noneargument(args.object_key), aws_credentials=noneargument(args.aws_creds))
    flamma.unzip_upload(threshold=args.threshold, verbose=args.verbose, delete=args.delete)
