#!/usr/bin/env python3

import limsETL

from cachier import cachier
import datetime

def getRequestSamples(projectNo):
    return limsETL.getRequestSamples(projectNo)

@cachier(cache_dir='./__cache__',stale_after=datetime.timedelta(days=1))
def getSampleManifest(sampleId):
    print("Pulling sample",sampleId,"...",end="")
    sampleManifest=limsETL.getSampleManifest(sampleId)
    print(" done")
    return sampleManifest

@cachier(cache_dir='./__cache__',stale_after=datetime.timedelta(days=1))
def getSampleMappingData(sampleObj):
    sampleMappingData=[]
    for lib in sampleObj.libraries:
        for runs in lib.runs:
            sampleMappingData.append([runs.runId,runs.fastqDir,runs.runType])

    return(sampleMappingData)

if __name__ == "__main__":

    import sys

    projectNo=sys.argv[1]
    print("\n  Project No = %s" % projectNo)

    requestData=getRequestSamples(projectNo)
    samples=[getSampleManifest(xx.igoSampleId) for xx in requestData.samples]

    # for sample in requestData.samples:
    #     print("Pulling sample",sample.igoSampleId,"...")
    #     samples.append(limsETL.getSampleManifest(sample.igoSampleId))
    #     print("\n")

    #
    # Dump request file
    #

    requestFieldsToIgnore=set(("samples","pooledNormals"))

    requestFile="Proj_%s_request.txt" % projectNo
    mappingFile="Proj_%s_sample_mapping.txt" % projectNo

    species=",".join(set([s.species for s in samples]))
    requestData.Species=species
    requestData.NumberOfSamples=len(samples)

    with open(requestFile,"w") as fp:
        for rField in requestData.__dict__:
            if rField not in requestFieldsToIgnore:
                fp.write("%s: %s\n" % (rField,getattr(requestData,rField)))

    with open(mappingFile,"w") as fp:
        for sample in samples:
            out0=["_1","s_"+sample.investigatorSampleId]
            for ri in getSampleMappingData(sample):
                out=out0+ri
                fp.write(("\t".join(out)+"\n"))
