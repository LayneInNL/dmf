import logging

from dmf.analysis.dmf import MFP
from dmf.py2flows.py2flows.main import construct_CFG

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    CFG = construct_CFG("../examples/test.py")
    mfp = MFP(CFG)
    mfp.compute_fixed_point()
    mfp.pprint()
