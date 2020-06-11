args=commandArgs(trailing=T)
if(len(args)!=1) {
    cat("\n    usage: makeChIPSeqProject.R limsMetaDataFile.yaml\n\n")
    quit()
}

## TODO 2020-06-09
# Here are the requests for the new request file template:

# -RunNumber needs to be an integer not a floating point.
# -Please add: ProjectID, ProjectFolder, DeliverTo_Name,
#     DeliverTo_Email, NumberOfSamples, CCFN

# Once the template is updated, we want to test it with a project
#that has already been completed
# (/ifs/projects/BIC/rnaseq/Proj_10827_B/Proj_10827_B_request.txt).

# Then to run 10864, we will still need mapping file. This was not
# in /ifs/projects/BIC/drafts/Proj_10864/.



normalizeName<-function(nn) {

    pn=strsplit(nn," ")[[1]]
    paste0(pn[2],", ",pn[1])

}

require(yaml)
require(tidyverse)

rFile=args[1]

request=read_yaml(rFile)
mapping=read_tsv(gsub("metadata.yaml","sample_mapping.txt",rFile),col_names=F,col_types=cols())

requestChIP=list(
    ProjectID=cc("Proj",request$requestId),
    Run_Pipeline="chipseq",
    Institution="bic",
    RunNumber="1",
    NumberOfSamples=mapping %>% distinct(X2) %>% nrow,

    Species = request$Species,

    PI_Name = normalizeName(request$labHeadName),
    PI = gsub("@.*$","",request$labHeadEmail),
    "PI_E-mail" = request$labHeadEmail,

    Investigator_Name = normalizeName(request$investigatorName),
    Investigator = gsub("@.*$","",request$investigatorEmail),
    "Investigator_E-mail" = request$investigatorEmail,

    ProjectFolder=file.path("/ifs/projects/BIC/chipseq",request$requestId),

    Pipelines="ChIP-seq Mapping",

    `Charges-CCFN`="",
    `Charges-Division`="BIC",
    `Charges-ProjectNumber`=request$requestId,
    `Charges-Qty`=mapping %>% distinct(X2) %>% nrow,
    `Charges-Service`="NG-CHIPSEQ-MACS2_V2"

    )


yy=as.yaml(requestChIP)
yy=gsub("'","",yy)
write(yy,"_request")

