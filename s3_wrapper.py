import io 
import boto3 # type: ignore
from boto3_type_annotations.s3 import ServiceResource # type: ignore
from typing import Union, Tuple, Optional
import zipfile


class FileLikeObject(io.RawIOBase):

    """
    Wrapper for S3 Objects that can process a large objects in S3 without downloading whole thing.
    Its a file-like object that return bytes since S3 deals entirely in bytes.
    S3 Objects Streaming Body its already a file-like object  we just have to implement missing methods so we could use zipfile module, which are seek() and read().
    Gold mine:https://docs.python.org/3/library/io.html.
    https://docs.python.org/3/library/io.html?highlight=io#raw-i-o


    """

    def __init__(self, bucket_name: str, object_key: str, aws_credentials: Optional[Tuple[(str, str)]] = None) -> None:

        """
        Parameters:
        -----------
        bucket_name: string
            Name of S3 Bucket.

        object_key: string

            Name of Object inside of S3 Bucket, including path.
            if object is on path s3://bucket_name/folder1/folder2/file
            object_key would be folder1/folder2/file

        aws_credentials: Optional
            Your aws access key id at index 0 and aws secret access key at index 1 

        """
        if aws_credentials is not None:

            aws_access_key_id = aws_credentials[0]
            aws_secret_access_key = aws_credentials[1]
            s3_resource: ServiceResource = boto3.resource('s3', aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)
        else:
            s3_resource: ServiceResource = boto3.resource('s3')
        self.bucket: ServiceResource = s3_resource.Bucket(bucket_name)
        self.s3_object = self.bucket.Object(object_key)
        self.position: int = 0


    @property
    def size(self) -> int:
        "Returns file size in bytes"
        return self.s3_object.content_length

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        """
        https://docs.python.org/3/library/io.html?highlight=io#io.IOBase.seek

        Change the stream position to the given byte offset.Offset is interpreted relative to the position indicated by whence.
        The default value for whence is SEEK_SET. 
        Values for whence are:
        SEEK_SET or 0 – start of the stream (the default); offset should be zero or positive
        SEEK_CUR or 1 – current stream position; offset may be negative
        SEEK_END or 2 – end of the stream; offset is usually negative

        Return the new absolute position.
        """

        if whence == io.SEEK_SET:
            self.position = offset
        elif whence == io.SEEK_CUR:
            self.position += offset
        elif whence == io.SEEK_END:
            self.position = self.size + offset
        else:
            raise ValueError('Invalid whence')
        
        return self.position

    def seekable(self) -> bool:
        return True
    
    def read(self, size: int =-1) -> bytes:
        """
        https://docs.python.org/3/library/io.html?highlight=io#io.RawIOBase.read

        Read up to size bytes from the object and return them.
         As a convenience, if size is unspecified or -1, all bytes until EOF are returned.
        Otherwise, only one system call is ever made.
        Fewer than size bytes may be returned if the operating system call returns fewer than size bytes.
        If 0 bytes are returned, and size was not 0, this indicates end of file.
        If the object is in non-blocking mode and no bytes are available, None is returned.

        """

        if size == -1:
            # Read to the end of the file
            range_header = "bytes=%d-" % self.position
            self.seek(offset=0, whence=io.SEEK_END)
        else:
            new_position = self.position + size

            # If we're going to read beyond the end of the object, return
            # the entire object.
            if new_position >= self.size:
                return self.read()

            range_header = "bytes=%d-%d" % (self.position, new_position - 1)
            self.seek(offset=size, whence=io.SEEK_CUR)

        return self.s3_object.get(Range=range_header)["Body"].read()

    def readable(self) -> bool:
        return True    
