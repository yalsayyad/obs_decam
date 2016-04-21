#
# LSST Data Management System
# Copyright 2012,2015 LSST Corporation.
#
# This product includes software developed by the
# LSST Project (http://www.lsst.org/).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the LSST License Statement and
# the GNU General Public License along with this program.  If not,
# see <http://www.lsstcorp.org/LegalNotices/>.
#
import os
import re
import lsst.afw.image as afwImage
from lsst.pipe.tasks.ingest import ParseTask, IngestTask, IngestArgumentParser


class DecamIngestArgumentParser(IngestArgumentParser):
    def __init__(self, *args, **kwargs):
        super(DecamIngestArgumentParser, self).__init__(*args, **kwargs)
        self.add_argument("--filetype", default="instcal", choices=["instcal", "raw"],
                          help="Data processing level of the files to be ingested")
        self.description = "To ingest instcal data, the following directory structure is expected:"\
            "\n    dqmask/ instcal/ wtmap/"\
            "\nThe science pixels, mask, and weight (inverse variance) are stored in"\
            "\nseparate files each with a unique name but with a common unique identifier"\
            "\nEXPNUM in the FITS header. The 3 files of the same EXPNUM will be aggregated."\
            "\nFor example, the user creates the registry by running"\
            "\n    ingestImagesDecam.py outputRepository --mode=link instcal/*fits"


class DecamIngestTask(IngestTask):
    ArgumentParser = DecamIngestArgumentParser
    def __init__(self, *args, **kwargs):
        super(DecamIngestTask, self).__init__(*args, **kwargs)
        
    def run(self, args):
        """Ingest all specified files and add them to the registry"""
        if args.filetype == "instcal":
            root = args.input
            with self.register.openRegistry(root, create=args.create, dryrun=args.dryrun) as registry:
                for infile in args.files:
                    fileInfo, hduInfoList = self.parse.getInfo(infile, args.filetype)
                    if len(hduInfoList) > 0:
                        outfileInstcal = os.path.join(root, self.parse.getDestination(args.butler,
                                                      hduInfoList[0], infile, "instcal"))
                        outfileDqmask = os.path.join(root, self.parse.getDestination(args.butler,
                                                     hduInfoList[0], infile, "dqmask"))
                        outfileWtmap = os.path.join(root, self.parse.getDestination(args.butler,
                                                    hduInfoList[0], infile, "wtmap"))

                        ingestedInstcal = self.ingest(fileInfo["instcal"], outfileInstcal,
                                                      mode=args.mode, dryrun=args.dryrun)
                        ingestedDqmask = self.ingest(fileInfo["dqmask"], outfileDqmask,
                                                     mode=args.mode, dryrun=args.dryrun)
                        ingestedWtmap = self.ingest(fileInfo["wtmap"], outfileWtmap,
                                                    mode=args.mode, dryrun=args.dryrun)

                        if not (ingestedInstcal or ingestedDqmask or ingestedWtmap):
                            continue

                    for info in hduInfoList:
                        info['hdu'] = None
                        self.register.addRow(registry, info, dryrun=args.dryrun, create=args.create)

                self.register.addVisits(registry, dryrun=args.dryrun)
        elif args.filetype == "raw":
            IngestTask.run(self, args)


class DecamParseTask(ParseTask):
    def __init__(self, *args, **kwargs):
        super(ParseTask, self).__init__(*args, **kwargs)
        
        self.expnumMapper  = None

        # Note that these should be syncronized with the fields in
        # root.register.columns defined in config/ingest.py
        self.instcalPrefix = "instcal"
        self.dqmaskPrefix  = "dqmask"
        self.wtmapPrefix   = "wtmap"

    def _listdir(self, path, prefix):
        for file in os.listdir(path):
            fileName = os.path.join(path, file)
            md = afwImage.readMetadata(fileName)
            if "EXPNUM" not in md.names():
                return
            expnum = md.get("EXPNUM")
            if expnum not in self.expnumMapper.keys():
                self.expnumMapper[expnum] = {self.instcalPrefix: None,
                                             self.wtmapPrefix: None,
                                             self.dqmaskPrefix: None}
            self.expnumMapper[expnum][prefix] = fileName
            
    def buildExpnumMapper(self, basepath):
        self.expnumMapper = {}
        
        instcalPath = basepath
        dqmaskPath  = re.sub(self.instcalPrefix, self.dqmaskPrefix, instcalPath)
        wtmapPath   = re.sub(self.instcalPrefix, self.wtmapPrefix, instcalPath)
        if instcalPath == dqmaskPath:
            raise RuntimeError("instcal and mask directories are the same")
        if instcalPath == wtmapPath:
            raise RuntimeError("instcal and weight map directories are the same")
            
        if not os.path.isdir(dqmaskPath):
            raise OSError("Directory %s does not exist" % (dqmaskPath))
        if not os.path.isdir(wtmapPath):
            raise OSError("Directory %s does not exist" % (wtmapPath))

        # Traverse each directory and extract the expnums
        for path, prefix in zip((instcalPath, dqmaskPath, wtmapPath),
                                (self.instcalPrefix, self.dqmaskPrefix, self.wtmapPrefix)):
            self._listdir(path, prefix)
        
    def getInfo(self, filename, filetype="raw"):
        """
        The science pixels, mask, and weight (inverse variance) are
        stored in separate files each with a unique name but with a
        common unique identifier EXPNUM in the FITS header.  We have
        to aggregate the 3 filenames for a given EXPNUM and return
        this information along with that returned by the base class.

        We expect a directory structure that looks like the following:

          dqmask/ instcal/ wtmap/

        The user creates the registry by running

          ingestImagesDecam.py outputRepository --mode=link instcal/*fits
        """
        if filetype == "instcal":
            if self.expnumMapper is None:
                self.buildExpnumMapper(os.path.dirname(os.path.abspath(filename)))

            # Note that phuInfo will have
            #   'side': 'X', 'ccd': 0
            phuInfo, infoList = super(DecamParseTask, self).getInfo(filename)
            expnum = phuInfo["visit"]
            phuInfo[self.instcalPrefix] = self.expnumMapper[expnum][self.instcalPrefix]
            phuInfo[self.dqmaskPrefix]  = self.expnumMapper[expnum][self.dqmaskPrefix]
            phuInfo[self.wtmapPrefix]   = self.expnumMapper[expnum][self.wtmapPrefix]
            for idx, info in enumerate(infoList):
                expnum = info["visit"]
                info[self.instcalPrefix] = self.expnumMapper[expnum][self.instcalPrefix]
                info[self.dqmaskPrefix]  = self.expnumMapper[expnum][self.dqmaskPrefix]
                info[self.wtmapPrefix]   = self.expnumMapper[expnum][self.wtmapPrefix]
        elif filetype == "raw":
            md = afwImage.readMetadata(filename, self.config.hdu)
            phuInfo = self.getInfoFromMetadata(md)
            # Some data IDs can not be extracted from the zeroth extension
            # of the MEF. Add them so Butler does not try to find them
            # in the registry which may still yet to be created.
            for key in ("ccdnum", "hdu"):
                if key not in phuInfo:
                    phuInfo[key] = 0
            extnames = set(self.config.extnames)
            extnum = 1
            infoList = []
            while len(extnames) > 0:
                extnum += 1
                try:
                    md = afwImage.readMetadata(filename, extnum)
                except:
                    self.log.warn("Error reading %s extensions %s" % (filename, extnames))
                    break
                ext = self.getExtensionName(md)
                if ext in extnames:
                    info = self.getInfoFromMetadata(md, info=phuInfo.copy())
                    info['hdu'] = extnum - 1
                    info[self.instcalPrefix] = ""
                    info[self.dqmaskPrefix] = ""
                    info[self.wtmapPrefix] = ""
                    infoList.append(info)
                    extnames.discard(ext)
        return phuInfo, infoList
    
    @staticmethod
    def getExtensionName(md):
        return md.get('EXTNAME')

    def getDestination(self, butler, info, filename, filetype="raw"):
        """Get destination for the file

        @param butler      Data butler
        @param info        File properties, used as dataId for the butler
        @param filename    Input filename
        @return Destination filename
        """
        raw = butler.get("%s_filename"%(filetype), info)[0]
        # Ensure filename is devoid of cfitsio directions about HDUs
        c = raw.find("[")
        if c > 0:
            raw = raw[:c]
        return raw


