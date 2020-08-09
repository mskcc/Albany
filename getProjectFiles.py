#!/usr/bin/env python3

import limsETL
import datetime

try:
    from cachier import cachier
except ModuleNotFoundError:
    print("No Cachier Module so no cacheing")
    def cachier(*args,**kwargs):
        def inner(f):
            return f
        return inner

sampleFields="""
investigatorSampleId
cmoSampleName
sampleName
cmoPatientId
igoId
baitSet
cmoSampleClass
tumorOrNormal
preservation
sampleOrigin
specimenType
oncoTreeCode
tissueLocation
collectionYear
sex
species
""".strip().split()

def getRequestSamples(projectNo):
    return limsETL.getRequestSamples(projectNo)

@cachier(cache_dir='./__cache__',stale_after=datetime.timedelta(days=1))
def getSampleManifest(sampleId):
    print("Pulling sample",sampleId,"...",end="")
    sampleManifest=limsETL.getSampleManifest(sampleId)
    print(" done")
    return sampleManifest

missingSampleMessage="""
No FASTQ files for:
            igoId: %s
       sampleName: %s
   investSampleId: %s
"""

@cachier(cache_dir='./__cache__',stale_after=datetime.timedelta(days=1))
def getSampleMappingData(sampleObj):
    sampleMappingData=[]
    for lib in sampleObj.libraries:
        for runs in lib.runs:
            if runs.machineRuns != None:
                for runIds in runs.machineRuns:
                    mRun=runs.machineRuns[runIds]
                    sampleMappingData.append([runIds,mRun.fastqDir,mRun.runType])
            else:

                print(missingSampleMessage % (
                        sampleObj.igoId,
                        sampleObj.sampleName,
                        sampleObj.investigatorSampleId
                        )
                )


    return(sampleMappingData)

if __name__ == "__main__":

    import sys

    projectNo=sys.argv[1]
    print("\n  Project No = %s" % projectNo)

    requestData=getRequestSamples(projectNo)
    sampleRequestDb=dict([(x.igoSampleId,x) for x in requestData.samples])

    samples=[getSampleManifest(xx.igoSampleId) for xx in requestData.samples]

    # for sample in requestData.samples:
    #     print("Pulling sample",sample.igoSampleId,"...")
    #     samples.append(limsETL.getSampleManifest(sample.igoSampleId))
    #     print("\n")

    #
    # Dump request file
    #

    requestFieldsToIgnore=set(("samples","pooledNormals"))

    requestFile="Proj_%s_metadata.yaml" % projectNo
    mappingFile="Proj_%s_sample_mapping.txt" % projectNo
    manifestFile="Proj_%s_metadata_samples.txt" % projectNo

    species=",".join(set([s.species for s in samples]))
    requestData.Species=species
    requestData.NumberOfSamples=len(samples)

    baitsUsed=set()

    with open(mappingFile,"w") as fp:
        for sample in samples:
            print(sample.igoId,sampleRequestDb[sample.igoId])
            baitsUsed.add(sample.baitSet)
            if sampleRequestDb[sample.igoId].igocomplete:
                out0=["_1","s_"+sample.investigatorSampleId]
                for ri in getSampleMappingData(sample):
                    if ri[0]!="":
                        out=out0+ri
                        fp.write(("\t".join(out)+"\n"))

    print("\nBaitsUsed =",";".join(baitsUsed))
    requestData.baitsUsed=";".join(baitsUsed)

    with open(requestFile,"w") as fp:
        for rField in requestData.__dict__:
            if rField not in requestFieldsToIgnore:
                fp.write("%s: \"%s\"\n" % (rField,getattr(requestData,rField)))

    with open(manifestFile,"w") as fp:
        fp.write(("\t".join(sampleFields)+"\n"))
        for sample in samples:
            out=[]
            for fi in sampleFields:
                out.append(str(sample.__dict__[fi]))
            fp.write(("\t".join(out)+"\n"))
