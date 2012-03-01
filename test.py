#!/usr/bin/python
import sys
import os
import unittest
import tests
                                                                                                                      
def runtests():                                                                                                       
    # based on Smart's test.py:                                                                                       
    loader  = unittest.TestLoader()                                                                                   
    runner = unittest.TextTestRunner()                                                                                
    testsdir = os.path.dirname(tests.__file__)                                                                        
    filenames = os.listdir(testsdir)                                                                                  
    failure_count = 0                                                                                                 
    test_count = 0                                                                                                    
    for filename in filenames:                                                                                        
        if filename != "__init__.py" and filename.endswith(".py"):                                                    
            modname = tests.__name__+ "." + filename[:-3]                                                             
            module = __import__(modname, None, None, [modname])                                                       
            testcase = loader.loadTestsFromModule(module)                                                             
            result = runner.run(testcase)                                                                             
            failure_count += len(result.failures)                                                                     
            test_count += testcase.countTestCases()                                                                   
    print "total: fails: %d, tests: %d" % (failure_count,                                                             
            test_count)                                                                                               
                                                                                                                      
if __name__ == "__main__":                                                                                            
    runtests()
