import io 

class FileLikeObject(io.RawIOBase):

    """
    Wrapper for S3 Objects that can process a large objects in S3 without downloading whole thing.
    Its a file-like object that return bytes since S3 deals entirely in bytes.
    S3 Objects Streaming Body its already a file-like object  we just have to implement missing methods so we could use zipfile module, which are seek() and read().
    Gold mine:https://docs.python.org/3/library/io.html.
    https://docs.python.org/3/library/io.html?highlight=io#raw-i-o


    """

    def __init__(self,s3object) -> None:

 
        
        self.s3object = s3object
        self.position: int = 0


    @property
    def size(self) -> int:
        "Returns file size in bytes"
        return self.s3object.content_length

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

        return self.s3object.get(Range=range_header)["Body"].read()

    def readable(self) -> bool:
        return True    
