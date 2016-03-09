#Tests

To run these tests you need to create a second database as per the details found in the
`tests/config/pool_config` file.  
It is not recommended to run the tests against any database  that has been used to run 
a functional pool as some tests add and remove orders and credits so will cause data 
loss.  
  
The tests can be run from the ALP-Server root directory with this command:  
`python -m unittest discover -s tests`  
  
