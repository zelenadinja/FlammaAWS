# Why need for this?
  First of all, [S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html) is all static, once u upload a file u cant commit any changes on S3.
  If u want to unzip a file from S3 most of the time u do something like this:
  
  ```python
  
  import boto3
  import zipfile 
  
  boto3.client('s3').Bucket(bucket_name).download_file(key, filename) #download to disk
  
  with open('filename', 'wb') as data:
    boto3.client('s3').Bucket(bucket_name).download_fileobj(key, data) # to memory
    
  with zipfile.ZipFile(key) as zipf:
    print(zipf.namelist())
    ...
    
  ```
 This is a fair solution if u are dealing with small size file, download file, whether to disk or in-memory([file-like object](https://stackoverflow.com/questions/4359495/what-is-exactly-a-file-like-object-in-python)) and work with copy.It gets harder if u are 
dealing with large files(hundreds of gigabytes or even terabytes),working in constraints environment or even if u have gone serverless on [AWS Lambda](https://aws.amazon.com/lambda/) where u can get only 10GB of memory.
Simple solution for this is to stream the ZIP file from the source bucket and write its content on the fly 
with [zipfile module](https://docs.python.org/3/library/zipfile.html).Zipfile can read file-like objects, so we could
read the entire file into memory with BytesIO from [io module](https://docs.python.org/3/library/io.html), iterate over file and upload unzipped content.

  ```python
  
  import boto3
  import zipfile 
  import io 
  
  object_ = boto3.resource('s3').Object(bucketname, key) #get object
  object_body = object_.get()['Body'] #get object body
  buffer = io.BytesIO(object_body.read()) #file like object
  
<<<<<<< HEAD

  with zipfile.ZipFile(buffer) as zipf:
      for filename in zipf.namelsit():
        boto3.client('s3').upload_fileobj(zipf.open(filename), bucketname, key)
    ...
    
  ```
  This is best alternative to just downloading and working with file, because nothing was ever stored on local disk.It introduces a [python bug](https://bugs.python.org/issue42853).For me, it happens when i try to move files larger than 2 gigabytes into memory.
  So idea is to get a file-like object, so we could iterate over it with zipmodule, write it back to S3 Bucket and also not to stream whole file into memory at once.
 
 
## FileLikeObject
Main component here is a class FileLikeObject which is used to stream a file into memory byte by byte.Streaming body of S3 Object is already a file like object which responds to read() and allows to stream file into memory but does not have necessary methods  which zipfile module uses.We needed to implement seek() and read().
The [io docs](https://docs.python.org/3/library/io.html?highlight=io#io.IOBase.seek) explain how seek() works.This is simply saying, where are we currently located,how far through we are, and what part of the object are we looking at right now.When we read  file on disk, OS handles it,but when file is in memory we have to track it ourselves.
The [io docs](https://docs.python.org/3/library/io.html?highlight=io#io.RawIOBase.read) explain how read() works.
To implement this method, we have to remember that we read from the position set by seek(),not necessarily the start of object. And when we read some bytes, we need to advance the position.
To read a specific section of an S3 object, we pass an HTTP Range header into the get() call, which defines what part of the object we want to read.

## Usage

### From Terminal

```
  git clone https://github.com/zelenadinja/FlammaAWS.git
  cd FlammaAWS
  python -m main --bucket_name  --object_key  --aws_credentials --threshold  --verbose --delete
  
  #--bucket_name: Name of your S3 Bucket
  #--object_key:Three possible options:None,single bject, list of Objects.If None its gona search for all zip files.
  #--aws_credentials:If provided its gona overwrite default one.
  #--threshold:Based on threshold it decides should it stream whole file into memory or use FileLikeObject.Test it out.
  #--verbose:progress bar
  #--delete:After uploding unzipped content,zip files are deleted.
  
  #Examples:
  python -m main --bucket_name testflamma --object_key None --verbose True --delete True
  
  #This is gona search for all zip files,use default creds,use default threshold(1GB),
  #print progressbar and delete zip files when uploading is done
  
  python -m main --bucket_name testflamma --object_key obj1.zip obj2.zip --verbose False --delete False --aws_credentials string1 string2
  
  #This is going to search for obj1.zip and obj2.zip,use default threshold, 
  #string1 as use aws_access_key_id and string2 as aws_secret_acess_key, use progessbar,
  #and it wont delete zipfiles.
  
```


### Notebooks and Scripts

```python
!git clone https://github.com/zelenadinja/FlammaAWS.git
!cd FlammaAWS
from main import flammaAWS
```


```python
flamma = flammaAWS(bucket_name='testflamma', object_key=None, aws_credentials=None)
#First option is to set object_key to None, its gona search for all zip objects.
```

```python
!aws s3 ls s3://testflamma
```

    2021-11-15 09:10:47      51538 assignment1_colab.zip
    2021-11-17 10:00:58     309211 assignment2_colab.zip
    2021-11-17 10:01:06    4156401 assignment3_colab.zip


```python
flamma.unzip_upload(threshold=1024*1024*1024, verbose=True, delete=True)
#If size of file is less than threshold its gona stream whole file at once.If size of file is greater than threshold
#its gona use FileLikeObject.Thats subjective, for me it was 2GB limit before getting python bug.Thresholds is in bytes.
#Verbose for progressbar
#delete, if true its gona delete .zip files after upload


#So this is going to unzip all three files, and delete .zip after uploading back to Bucket.
```

    Object size (0.0492 MB) is less than threshold (1024.0 MB).Fit whole file into memory.


    assignment1/collectSubmission.sh: 100%|███| 1.15k/1.15k [00:00<00:00, 7.24kB/s]
    assignment1/cs231n/: 0.00B [00:00, ?B/s]
    assignment1/README.md: 100%|██████████████████| 131/131 [00:00<00:00, 1.27kB/s]
    assignment1/makepdf.py: 100%|█████████████| 1.07k/1.07k [00:00<00:00, 9.14kB/s]
    assignment1/cs231n/optim.py: 100%|████████| 2.06k/2.06k [00:00<00:00, 14.4kB/s]
    assignment1/cs231n/layer_utils.py: 100%|██████| 737/737 [00:00<00:00, 7.03kB/s]
    assignment1/cs231n/vis_utils.py: 100%|████| 2.32k/2.32k [00:00<00:00, 21.2kB/s]
    assignment1/cs231n/layers.py: 100%|███████| 7.08k/7.08k [00:00<00:00, 61.6kB/s]
    ...

    Deleting object...
    Object size (0.2949 MB) is less than threshold (1024.0 MB).Fit whole file into memory.


    assignment2/requirements.txt: 100%|███████| 1.11k/1.11k [00:00<00:00, 10.4kB/s]
    assignment2/cs231n/: 0.00B [00:00, ?B/s]
    assignment2/makepdf.py: 100%|█████████████| 1.07k/1.07k [00:00<00:00, 10.7kB/s]
    assignment2/collectSubmission.sh: 100%|███| 1.11k/1.11k [00:00<00:00, 8.67kB/s]
    assignment2/cs231n/layer_utils.py: 100%|██| 3.89k/3.89k [00:00<00:00, 34.3kB/s]
    assignment2/cs231n/solver.py: 100%|████████| 12.3k/12.3k [00:00<00:00, 110kB/s]
    assignment2/cs231n/gradient_check.py: 100%|█| 3.98k/3.98k [00:00<00:00, 27.3kB/
    assignment2/cs231n/datasets/: 0.00B [00:00, ?B/s]
    assignment2/cs231n/notebook_images/: 0.00B [00:00, ?B/s]
    assignment2/cs231n/__init__.py: 0.00B [00:00, ?B/s]
    ...


    Deleting object...
    Object size (3.9639 MB) is less than threshold (1024.0 MB).Fit whole file into memory.


    assignment3/gan-checks.npz: 100%|█████████| 2.19k/2.19k [00:00<00:00, 20.3kB/s]
    assignment3/requirements.txt: 100%|███████| 1.11k/1.11k [00:00<00:00, 10.5kB/s]
    assignment3/images/: 0.00B [00:00, ?B/s]
    assignment3/cs231n/: 0.00B [00:00, ?B/s]
    assignment3/style-transfer-checks.npz: 100%|█| 66.3k/66.3k [00:00<00:00, 226kB/
    assignment3/makepdf.py: 100%|█████████████| 1.16k/1.16k [00:00<00:00, 6.21kB/s]
    assignment3/simclr_sanity_check.key: 100%|█| 26.7k/26.7k [00:00<00:00, 191kB/s]
    assignment3/collectSubmission.sh: 100%|███| 1.24k/1.24k [00:00<00:00, 10.2kB/s]
    assignment3/images/kitten.jpg: 100%|███████| 21.4k/21.4k [00:00<00:00, 135kB/s]
    assignment3/images/simclr_fig2.png: 100%|████| 272k/272k [00:01<00:00, 212kB/s]
    assignment3/images/gan_outputs_pytorch.png: 100%|█| 64.3k/64.3k [00:00<00:00, 2
    assignment3/images/styles/: 0.00B [00:00, ?B/s]
    assignment3/images/sky.jpg: 100%|████████████| 148k/148k [00:00<00:00, 201kB/s]
    assignment3/images/example_styletransfer.png: 100%|█| 1.47M/1.47M [00:07<00:00,
    assignment3/images/styles/the_scream.jpg: 100%|█| 217k/217k [00:00<00:00, 231kB
    assignment3/images/styles/composition_vii.jpg: 100%|█| 202k/202k [00:01<00:00, 
    assignment3/images/styles/tubingen.jpg: 100%|█| 407k/407k [00:02<00:00, 187kB/s
    assignment3/images/styles/muse.jpg: 100%|████| 704k/704k [00:04<00:00, 173kB/s]
    assignment3/images/styles/starry_night.jpg: 100%|█| 613k/613k [00:04<00:00, 150

    ...

    Deleting object...


```python
!aws s3 ls s3://testflamma
```

                               PRE assignment1/
                               PRE assignment2/
                               PRE assignment3/



```python
flamma = flammaAWS(bucket_name='testflamma', object_key=['assignment1_colab.zip', 'assignment2_colab.zip'])
#Second option is to provide a list of object_keys.
!aws s3 ls s3://testflamma
```

    2021-11-17 10:28:49      51538 assignment1_colab.zip
    2021-11-17 10:28:55     309211 assignment2_colab.zip
    2021-11-17 10:29:02    4156401 assignment3_colab.zip



```python
flamma.unzip_upload(threshold=1024*1024*1024, verbose=False, delete=False)
#Lets not use progressbar and dont delete zip files after uploading unzipped content
```

    Object size (0.0492 MB) is less than threshold (1024.0 MB).Fit whole file into memory.
    Object size (0.2949 MB) is less than threshold (1024.0 MB).Fit whole file into memory.



```python
#Now S3 Bucket should containt all zip files and 2 DIRs assignment1 and assignment2 
!aws s3 ls s3://testflamma
```

                               PRE assignment1/
                               PRE assignment2/
    2021-11-17 10:28:49      51538 assignment1_colab.zip
    2021-11-17 10:28:55     309211 assignment2_colab.zip
    2021-11-17 10:29:02    4156401 assignment3_colab.zip



```python
flamma = flammaAWS(bucket_name='testflamma', object_key='assignment3_colab.zip')
#Third option is to provide single object key 
!aws s3 ls s3://testflamma
```

    2021-11-17 10:28:49      51538 assignment1_colab.zip
    2021-11-17 10:28:55     309211 assignment2_colab.zip
    2021-11-17 10:29:02    4156401 assignment3_colab.zip



```python
flamma.unzip_upload(verbose=True, delete=True)
#Lets leave threshold to default value which is 1GB
#Use progressbar
#Delete zip file
```

    Object size (3.9639 MB) is less than threshold (1024.0 MB).Fit whole file into memory.


    assignment3/gan-checks.npz: 100%|█████████| 2.19k/2.19k [00:00<00:00, 9.63kB/s]
    assignment3/requirements.txt: 100%|███████| 1.11k/1.11k [00:00<00:00, 8.30kB/s]
    assignment3/images/: 0.00B [00:00, ?B/s]
    assignment3/cs231n/: 0.00B [00:00, ?B/s]
    assignment3/style-transfer-checks.npz: 100%|█| 66.3k/66.3k [00:00<00:00, 306kB/
    assignment3/makepdf.py: 100%|█████████████| 1.16k/1.16k [00:00<00:00, 10.9kB/s]
    assignment3/simclr_sanity_check.key: 100%|█| 26.7k/26.7k [00:00<00:00, 223kB/s]
    assignment3/collectSubmission.sh: 100%|███| 1.24k/1.24k [00:00<00:00, 11.0kB/s]
    assignment3/images/kitten.jpg: 100%|███████| 21.4k/21.4k [00:00<00:00, 183kB/s]
    assignment3/images/simclr_fig2.png: 100%|████| 272k/272k [00:01<00:00, 226kB/s]
    assignment3/images/gan_outputs_pytorch.png: 100%|█| 64.3k/64.3k [00:00<00:00, 1
    assignment3/images/styles/: 0.00B [00:00, ?B/s]
    assignment3/images/sky.jpg: 100%|████████████| 148k/148k [00:00<00:00, 219kB/s]
    assignment3/images/example_styletransfer.png: 100%|█| 1.47M/1.47M [00:08<00:00,
    assignment3/images/styles/the_scream.jpg: 100%|█| 217k/217k [00:01<00:00, 187kB
    assignment3/images/styles/composition_vii.jpg: 100%|█| 202k/202k [00:01<00:00, 
    assignment3/images/styles/tubingen.jpg: 100%|█| 407k/407k [00:02<00:00, 169kB/s
    assignment3/images/styles/muse.jpg: 100%|████| 704k/704k [00:03<00:00, 182kB/s]
    assignment3/images/styles/starry_night.jpg: 100%|█| 613k/613k [00:03<00:00, 175



    Deleting object...
    

```python
#Now S3Bucket should containt assignment3 DIR, and there should not be assignemnt3_colab.zip file
!aws s3 ls s3://testflamma
```

                               PRE assignment3/
    2021-11-17 10:28:49      51538 assignment1_colab.zip
    2021-11-17 10:28:55     309211 assignment2_colab.zip



```python

```
  
  
## Lambda Function

Best use case for this is to use as lambda function.Upload lambda_dep.zip  and copy content of lambda_function.py to your lambda function.
Make PUT and Multipart upload completed on.Allow Lambda to access S3 and cloudwatch logs.

=======

  with zipfile.ZipFile(buffer) as zipf:
      for filename in zipf.namelsit():
        boto3.client('s3').upload_fileobj(zipf.open(filename), bucketname, key)
    ...
    
  ```
  This is best alternative to just downloading and working with file, because nothing was ever stored on local disk.It introduces a [python bug](https://bugs.python.org/issue42853).For me, it happens when i try to move files larger than 2 gigabytes into memory.
  So idea is to get a file-like object, so we could iterate over it with zipmodule, write it back to S3 Bucket and also not to stream whole file into memory at once.
 
 
## FileLikeObject
Main component here is a class FileLikeObject which is used to stream a file into memory byte by byte.Streaming body of S3 Object is already a file like object which responds to read() and allows to stream file into memory but does not have necessary methods  which zipfile module uses.We needed to implement seek() and read().
The [io docs](https://docs.python.org/3/library/io.html?highlight=io#io.IOBase.seek) explain how seek() works.This is simply saying, where are we currently located,how far through we are, and what part of the object are we looking at right now.When we read  file on disk, OS handles it,but when file is in memory we have to track it ourselves.
The [io docs](https://docs.python.org/3/library/io.html?highlight=io#io.RawIOBase.read) explain how read() works.
To implement this method, we have to remember that we read from the position set by seek(),not necessarily the start of object. And when we read some bytes, we need to advance the position.
To read a specific section of an S3 object, we pass an HTTP Range header into the get() call, which defines what part of the object we want to read.

## Usage

### From Terminal

```
  git clone https://github.com/zelenadinja/FlammaAWS.git
  cd FlammaAWS
  python -m main --bucket_name  --object_key  --aws_credentials --threshold  --verbose --delete
  
  #--bucket_name: Name of your S3 Bucket
  #--object_key:Three possible options:None,single bject, list of Objects.If None its gona search for all zip files.
  #--aws_credentials:If provided its gona overwrite default one.
  #--threshold:Based on threshold it decides should it stream whole file into memory or use FileLikeObject.Test it out.
  #--verbose:progress bar
  #--delete:After uploding unzipped content,zip files are deleted.
  
  #Examples:
  python -m main --bucket_name testflamma --object_key None --verbose True --delete True
  
  #This is gona search for all zip files,use default creds,use default threshold(1GB),
  #print progressbar and delete zip files when uploading is done
  
  python -m main --bucket_name testflamma --object_key obj1.zip obj2.zip --verbose False --delete False --aws_credentials string1 string2
  
  #This is going to search for obj1.zip and obj2.zip,use default threshold, 
  #string1 as use aws_access_key_id and string2 as aws_secret_acess_key, use progessbar,
  #and it wont delete zipfiles.
  
```


### Notebooks and Scripts

```python
!git clone https://github.com/zelenadinja/FlammaAWS.git
!cd FlammaAWS
from main import flammaAWS
```


```python
flamma = flammaAWS(bucket_name='testflamma', object_key=None, aws_credentials=None)
#First option is to set object_key to None, its gona search for all zip objects.
```

```python
!aws s3 ls s3://testflamma
```

    2021-11-15 09:10:47      51538 assignment1_colab.zip
    2021-11-17 10:00:58     309211 assignment2_colab.zip
    2021-11-17 10:01:06    4156401 assignment3_colab.zip


```python
flamma.unzip_upload(threshold=1024*1024*1024, verbose=True, delete=True)
#If size of file is less than threshold its gona stream whole file at once.If size of file is greater than threshold
#its gona use FileLikeObject.Thats subjective, for me it was 2GB limit before getting python bug.Thresholds is in bytes.
#Verbose for progressbar
#delete, if true its gona delete .zip files after upload


#So this is going to unzip all three files, and delete .zip after uploading back to Bucket.
```

    Object size (0.0492 MB) is less than threshold (1024.0 MB).Fit whole file into memory.


    assignment1/collectSubmission.sh: 100%|███| 1.15k/1.15k [00:00<00:00, 7.24kB/s]
    assignment1/cs231n/: 0.00B [00:00, ?B/s]
    assignment1/README.md: 100%|██████████████████| 131/131 [00:00<00:00, 1.27kB/s]
    assignment1/makepdf.py: 100%|█████████████| 1.07k/1.07k [00:00<00:00, 9.14kB/s]
    assignment1/cs231n/optim.py: 100%|████████| 2.06k/2.06k [00:00<00:00, 14.4kB/s]
    assignment1/cs231n/layer_utils.py: 100%|██████| 737/737 [00:00<00:00, 7.03kB/s]
    assignment1/cs231n/vis_utils.py: 100%|████| 2.32k/2.32k [00:00<00:00, 21.2kB/s]
    assignment1/cs231n/layers.py: 100%|███████| 7.08k/7.08k [00:00<00:00, 61.6kB/s]
    ...

    Deleting object...
    Object size (0.2949 MB) is less than threshold (1024.0 MB).Fit whole file into memory.


    assignment2/requirements.txt: 100%|███████| 1.11k/1.11k [00:00<00:00, 10.4kB/s]
    assignment2/cs231n/: 0.00B [00:00, ?B/s]
    assignment2/makepdf.py: 100%|█████████████| 1.07k/1.07k [00:00<00:00, 10.7kB/s]
    assignment2/collectSubmission.sh: 100%|███| 1.11k/1.11k [00:00<00:00, 8.67kB/s]
    assignment2/cs231n/layer_utils.py: 100%|██| 3.89k/3.89k [00:00<00:00, 34.3kB/s]
    assignment2/cs231n/solver.py: 100%|████████| 12.3k/12.3k [00:00<00:00, 110kB/s]
    assignment2/cs231n/gradient_check.py: 100%|█| 3.98k/3.98k [00:00<00:00, 27.3kB/
    assignment2/cs231n/datasets/: 0.00B [00:00, ?B/s]
    assignment2/cs231n/notebook_images/: 0.00B [00:00, ?B/s]
    assignment2/cs231n/__init__.py: 0.00B [00:00, ?B/s]
    ...


    Deleting object...
    Object size (3.9639 MB) is less than threshold (1024.0 MB).Fit whole file into memory.


    assignment3/gan-checks.npz: 100%|█████████| 2.19k/2.19k [00:00<00:00, 20.3kB/s]
    assignment3/requirements.txt: 100%|███████| 1.11k/1.11k [00:00<00:00, 10.5kB/s]
    assignment3/images/: 0.00B [00:00, ?B/s]
    assignment3/cs231n/: 0.00B [00:00, ?B/s]
    assignment3/style-transfer-checks.npz: 100%|█| 66.3k/66.3k [00:00<00:00, 226kB/
    assignment3/makepdf.py: 100%|█████████████| 1.16k/1.16k [00:00<00:00, 6.21kB/s]
    assignment3/simclr_sanity_check.key: 100%|█| 26.7k/26.7k [00:00<00:00, 191kB/s]
    assignment3/collectSubmission.sh: 100%|███| 1.24k/1.24k [00:00<00:00, 10.2kB/s]
    assignment3/images/kitten.jpg: 100%|███████| 21.4k/21.4k [00:00<00:00, 135kB/s]
    assignment3/images/simclr_fig2.png: 100%|████| 272k/272k [00:01<00:00, 212kB/s]
    assignment3/images/gan_outputs_pytorch.png: 100%|█| 64.3k/64.3k [00:00<00:00, 2
    assignment3/images/styles/: 0.00B [00:00, ?B/s]
    assignment3/images/sky.jpg: 100%|████████████| 148k/148k [00:00<00:00, 201kB/s]
    assignment3/images/example_styletransfer.png: 100%|█| 1.47M/1.47M [00:07<00:00,
    assignment3/images/styles/the_scream.jpg: 100%|█| 217k/217k [00:00<00:00, 231kB
    assignment3/images/styles/composition_vii.jpg: 100%|█| 202k/202k [00:01<00:00, 
    assignment3/images/styles/tubingen.jpg: 100%|█| 407k/407k [00:02<00:00, 187kB/s
    assignment3/images/styles/muse.jpg: 100%|████| 704k/704k [00:04<00:00, 173kB/s]
    assignment3/images/styles/starry_night.jpg: 100%|█| 613k/613k [00:04<00:00, 150

    ...

    Deleting object...


```python
!aws s3 ls s3://testflamma
```

                               PRE assignment1/
                               PRE assignment2/
                               PRE assignment3/



```python
flamma = flammaAWS(bucket_name='testflamma', object_key=['assignment1_colab.zip', 'assignment2_colab.zip'])
#Second option is to provide a list of object_keys.
!aws s3 ls s3://testflamma
```

    2021-11-17 10:28:49      51538 assignment1_colab.zip
    2021-11-17 10:28:55     309211 assignment2_colab.zip
    2021-11-17 10:29:02    4156401 assignment3_colab.zip



```python
flamma.unzip_upload(threshold=1024*1024*1024, verbose=False, delete=False)
#Lets not use progressbar and dont delete zip files after uploading unzipped content
```

    Object size (0.0492 MB) is less than threshold (1024.0 MB).Fit whole file into memory.
    Object size (0.2949 MB) is less than threshold (1024.0 MB).Fit whole file into memory.



```python
#Now S3 Bucket should containt all zip files and 2 DIRs assignment1 and assignment2 
!aws s3 ls s3://testflamma
```

                               PRE assignment1/
                               PRE assignment2/
    2021-11-17 10:28:49      51538 assignment1_colab.zip
    2021-11-17 10:28:55     309211 assignment2_colab.zip
    2021-11-17 10:29:02    4156401 assignment3_colab.zip



```python
flamma = flammaAWS(bucket_name='testflamma', object_key='assignment3_colab.zip')
#Third option is to provide single object key 
!aws s3 ls s3://testflamma
```

    2021-11-17 10:28:49      51538 assignment1_colab.zip
    2021-11-17 10:28:55     309211 assignment2_colab.zip
    2021-11-17 10:29:02    4156401 assignment3_colab.zip



```python
flamma.unzip_upload(verbose=True, delete=True)
#Lets leave threshold to default value which is 1GB
#Use progressbar
#Delete zip file
```

    Object size (3.9639 MB) is less than threshold (1024.0 MB).Fit whole file into memory.


    assignment3/gan-checks.npz: 100%|█████████| 2.19k/2.19k [00:00<00:00, 9.63kB/s]
    assignment3/requirements.txt: 100%|███████| 1.11k/1.11k [00:00<00:00, 8.30kB/s]
    assignment3/images/: 0.00B [00:00, ?B/s]
    assignment3/cs231n/: 0.00B [00:00, ?B/s]
    assignment3/style-transfer-checks.npz: 100%|█| 66.3k/66.3k [00:00<00:00, 306kB/
    assignment3/makepdf.py: 100%|█████████████| 1.16k/1.16k [00:00<00:00, 10.9kB/s]
    assignment3/simclr_sanity_check.key: 100%|█| 26.7k/26.7k [00:00<00:00, 223kB/s]
    assignment3/collectSubmission.sh: 100%|███| 1.24k/1.24k [00:00<00:00, 11.0kB/s]
    assignment3/images/kitten.jpg: 100%|███████| 21.4k/21.4k [00:00<00:00, 183kB/s]
    assignment3/images/simclr_fig2.png: 100%|████| 272k/272k [00:01<00:00, 226kB/s]
    assignment3/images/gan_outputs_pytorch.png: 100%|█| 64.3k/64.3k [00:00<00:00, 1
    assignment3/images/styles/: 0.00B [00:00, ?B/s]
    assignment3/images/sky.jpg: 100%|████████████| 148k/148k [00:00<00:00, 219kB/s]
    assignment3/images/example_styletransfer.png: 100%|█| 1.47M/1.47M [00:08<00:00,
    assignment3/images/styles/the_scream.jpg: 100%|█| 217k/217k [00:01<00:00, 187kB
    assignment3/images/styles/composition_vii.jpg: 100%|█| 202k/202k [00:01<00:00, 
    assignment3/images/styles/tubingen.jpg: 100%|█| 407k/407k [00:02<00:00, 169kB/s
    assignment3/images/styles/muse.jpg: 100%|████| 704k/704k [00:03<00:00, 182kB/s]
    assignment3/images/styles/starry_night.jpg: 100%|█| 613k/613k [00:03<00:00, 175



    Deleting object...
    

```python
#Now S3Bucket should containt assignment3 DIR, and there should not be assignemnt3_colab.zip file
!aws s3 ls s3://testflamma
```

                               PRE assignment3/
    2021-11-17 10:28:49      51538 assignment1_colab.zip
    2021-11-17 10:28:55     309211 assignment2_colab.zip



```python

```
  
  
## Lambda Function

Best use case for this is to use as lambda function.Upload lambda_dep.zip  and copy content of lambda_function.py to your lambda function.
Make PUT and Multipart upload completed on.Allow Lambda to access S3 and cloudwatch logs.
>>>>>>> 98a7560bb9d5d87065faa0e22f14e6292fe0b445
