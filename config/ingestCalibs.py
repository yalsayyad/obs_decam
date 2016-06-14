from lsst.obs.decam.ingestCalibs import DecamCalibsParseTask
config.parse.retarget(DecamCalibsParseTask)
config.parse.hdu = 1
# N30 is not included becasue it is not functional.
config.parse.extnames = ['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8', 'S9', 'S10', 'S11', 'S12', 'S13',
                       'S14', 'S15', 'S16', 'S17', 'S18', 'S19', 'S20', 'S21', 'S22', 'S23', 'S24', 'S25',
                       'S26', 'S27', 'S28', 'S29', 'S30', 'S31', 'N1', 'N2', 'N3', 'N4', 'N5', 'N6', 'N7',
                       'N8', 'N9', 'N10', 'N11', 'N12', 'N13', 'N14', 'N15', 'N16', 'N17', 'N18', 'N19',
                       'N20', 'N21', 'N22', 'N23', 'N24', 'N25', 'N26', 'N27', 'N28', 'N29', 'N31',
                       ]
config.parse.translators = {'filter': 'translate_filter',
                          'ccdnum': 'translate_ccdnum',
                          'calibDate': 'translate_date',
                          }
config.register.columns = {'filter': 'text',
                         'ccdnum': 'int',
                         'path': 'text',
                         'calibDate': 'text',
                         'validStart': 'text',
                         'validEnd': 'text',
                         }
config.register.detector = ['filter', 'ccdnum']
config.register.unique = ['filter', 'ccdnum', 'calibDate']
config.register.tables = ['bias', 'flat', 'fringe', 'defect', 'dark']
config.register.visit = ['calibDate']
