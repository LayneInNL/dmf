import logging

from dmf.analysis.pointsto import PointsToAnalysis
from dmf.py2flows.py2flows.main import construct_CFG

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    CFG = construct_CFG("../examples/test.py")
    analysis = PointsToAnalysis(CFG)
    analysis.iteration()
    print(analysis.data_stack)
    print(analysis.store)
